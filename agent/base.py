import os
import re
import json
import time
import logging
from typing import Any, Dict, Optional
from langchain_openai import ChatOpenAI

logger = logging.getLogger("agent")


class BaseAgent:
    """
    Base class for all specialized micro-agents.
    Provides uniform logging, execution timing, LLM connectivity, and robust JSON extraction.
    """

    def __init__(self, name: str, role: str):
        self.name = name
        self.role = role

    def get_llm(self, temperature: float = 0.2, timeout: int = 45) -> ChatOpenAI:
        """
        Initializes the configured LLM client strictly from environment variables.
        Prioritizes OpenRouter, falling back to local Ollama if configured.
        Raises RuntimeError if required configuration is missing.
        """
        api_key = os.getenv("OPENROUTER_API_KEY")
        openrouter_model = os.getenv("OPENROUTER_MODEL")
        openrouter_base_url = os.getenv("OPENROUTER_BASE_URL")

        if api_key and openrouter_model and openrouter_base_url:
            return ChatOpenAI(
                model=openrouter_model,
                api_key=api_key,
                base_url=openrouter_base_url,
                temperature=temperature,
                timeout=timeout,
                max_retries=1,
            )

        # Fallback to local Ollama if configured
        ollama_model = os.getenv("OLLAMA_MODEL")
        ollama_base_url = os.getenv("OLLAMA_BASE_URL")
        if ollama_model and ollama_base_url:
            return ChatOpenAI(
                model=ollama_model,
                api_key="ollama",
                base_url=ollama_base_url,
                temperature=temperature,
                timeout=timeout * 2,
                max_retries=1,
            )

        raise RuntimeError(
            "No LLM provider configured. Please define OPENROUTER_API_KEY, "
            "OPENROUTER_MODEL, and OPENROUTER_BASE_URL (or OLLAMA_MODEL and OLLAMA_BASE_URL) "
            "in your environment or .env file."
        )

    def extract_json(self, raw_text: str) -> Dict[str, Any]:
        """
        Robustly extracts JSON from LLM output, stripping reasoning tags and markdown blocks.
        """
        cleaned = re.sub(r"<think>.*?</think>", "", raw_text, flags=re.DOTALL).strip()

        if "```json" in cleaned:
            cleaned = cleaned.split("```json")[1].split("```")[0].strip()
        elif "```" in cleaned:
            cleaned = cleaned.split("```")[1].split("```")[0].strip()

        start = cleaned.find("{")
        end = cleaned.rfind("}")
        if start != -1 and end != -1:
            cleaned = cleaned[start:end + 1]

        try:
            return json.loads(cleaned, strict=False)
        except Exception:
            # Fallback array check
            start_arr = cleaned.find("[")
            end_arr = cleaned.rfind("]")
            if start_arr != -1 and end_arr != -1:
                return {"items": json.loads(cleaned[start_arr:end_arr + 1], strict=False)}
            raise ValueError(f"Failed to parse JSON from agent output: {raw_text[:200]}")

    def execute(self, *args, **kwargs) -> Dict[str, Any]:
        """
        Executes the agent's primary task with error handling and timing metrics.
        """
        start_time = time.time()
        logger.info(f"[{self.name}] Started task execution.")
        try:
            result = self.run(*args, **kwargs)
            duration = round(time.time() - start_time, 2)
            logger.info(f"[{self.name}] Completed task in {duration}s.")
            return {
                "success": True,
                "agent": self.name,
                "duration_seconds": duration,
                "data": result,
            }
        except Exception as e:
            duration = round(time.time() - start_time, 2)
            logger.error(f"[{self.name}] Failed after {duration}s: {e}")
            return {
                "success": False,
                "agent": self.name,
                "duration_seconds": duration,
                "error": str(e),
            }

    def run(self, *args, **kwargs) -> Any:
        raise NotImplementedError("Each specialized agent must implement its run() method.")

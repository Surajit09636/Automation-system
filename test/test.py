
import os
from dotenv import load_dotenv
from langchain_openai import ChatOpenAI

load_dotenv()

api_key = os.getenv("OPENROUTER_API_KEY")
model_name = os.getenv("OPENROUTER_MODEL")

if not api_key:
    raise ValueError("OPENROUTER_API_KEY is missing from .env")

print(f"Testing OpenRouter model: {model_name}")

try:
    llm = ChatOpenAI(
        model=model_name,
        api_key=api_key,
        base_url="https://openrouter.ai/api/v1",
        temperature=0,
        timeout=60,
        max_retries=1,
    )

    response = llm.invoke(
        "Reply with exactly: OpenRouter is working!"
    )

    print("\nSUCCESS: Model responded.")
    print("Model:", response.response_metadata.get("model_name", model_name))
    print("Response:", response.content)

except Exception as e:
    print("\nFAILED: OpenRouter request did not succeed.")
    print("Error type:", type(e).__name__)
    print("Details:", str(e)[:1000])

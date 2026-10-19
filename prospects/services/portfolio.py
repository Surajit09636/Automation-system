import json
from langchain_core.prompts import ChatPromptTemplate
from prospects.models import ServiceProfile
from prospects.services.scraper import extract_website_content
from prospects.services.analyzer import Openrouter_llm, local_llm, extract_json
from prospects.services.embeddings import get_text_embedding

PORTFOLIO_ANALYSIS_PROMPT = """
You are an expert agency strategist and B2B client acquisition director.
Analyze the following portfolio or business website content to understand the freelancer or agency's core capabilities, skills, and target market.

### PORTFOLIO WEBSITE CONTENT:
URL: {url}
Title: {title}
Description: {meta_description}
Page Content:
{text}

### TASK:
Analyze the portfolio and return ONLY a valid JSON object with the following fields:
1. "service_description": Comprehensive summary of all services offered, technical stack (languages, frameworks, databases, automations), and types of problems solved.
2. "target_icps": A list of 3 to 5 specific business niches or company types that would benefit most from hiring this person or agency (e.g. "Direct-to-consumer apparel brands", "B2B SaaS startups", "Real estate firms needing CRM pipelines").
3. "search_queries": A list of 3 to 5 exact search queries to discover these target businesses on the public web (e.g. "boutique apparel brand shopify", "b2b saas logistics").

Output ONLY valid JSON. Do not write any preamble, reasoning, or markdown outside the JSON.
"""


def execute_llms_custom_prompt(prompt: ChatPromptTemplate, chain_input: dict) -> tuple[dict, str]:
    """Helper to execute custom prompt through OpenRouter with Ollama fallback."""
    openrouter = Openrouter_llm()
    if openrouter:
        try:
            print("[LLM] Analyzing portfolio via OpenRouter...")
            chain = prompt | openrouter
            res = chain.invoke(chain_input)
            return extract_json(res.content), "OpenRouter"
        except Exception as e:
            print(f"[Warning] OpenRouter failed: {e}. Switching to local Ollama...")

    print("[LLM] Analyzing portfolio via local Ollama...")
    ollama = local_llm()
    chain = prompt | ollama
    res = chain.invoke(chain_input)
    return extract_json(res.content), "Local Ollama"


def analyze_and_sync_portfolio(portfolio_url: str) -> tuple[ServiceProfile, list[str]]:
    """
    1. Scrapes your live portfolio or agency website.
    2. Extracts all services, tech stacks, and derives high-match target ICPs.
    3. Generates and stores 384-dim vector embedding into PostgreSQL.
    4. Returns the updated ServiceProfile and a list of target search queries.
    """
    print(f"\n[Portfolio] Scraping and analyzing portfolio: {portfolio_url}")
    scraped = extract_website_content(portfolio_url)
    if scraped.get("error"):
        raise ValueError(f"Could not read portfolio website: {scraped['error']}")

    prompt = ChatPromptTemplate.from_template(PORTFOLIO_ANALYSIS_PROMPT)
    chain_input = {
        "url": scraped["url"],
        "title": scraped["title"],
        "meta_description": scraped["meta_description"],
        "text": scraped["text"][:5000],
    }

    data, provider_used = execute_llms_custom_prompt(prompt, chain_input)

    service_desc = data.get("service_description", scraped["text"][:500])
    target_icps = data.get("target_icps", [])
    search_queries = data.get("search_queries", [])

    icp_criteria_str = "\n".join([f"- {icp}" for icp in target_icps])

    print("[Portfolio] Generating local 384-dim vector embedding...")
    embedding_vector = get_text_embedding(service_desc)

    profile, _ = ServiceProfile.objects.update_or_create(
        name="Auto-Synced Portfolio Profile",
        defaults={
            "portfolio_url": portfolio_url,
            "service_description": service_desc,
            "target_icp_criteria": icp_criteria_str,
            "embedding": embedding_vector,
            "is_active": True,
        }
    )

    print(f"[Portfolio] Profile saved. Identified {len(target_icps)} target ICPs and {len(search_queries)} search strategies.")
    return profile, search_queries

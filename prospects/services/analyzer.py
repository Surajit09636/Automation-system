import json
import os
import re
from langchain_openai import ChatOpenAI
from langchain_core.prompts import ChatPromptTemplate
from prospects.models import ServiceProfile, Prospect, OpportunityFinding, OutreachDraft
from prospects.services.embeddings import get_text_embedding

# LLM configure
def Openrouter_llm():
    api_key = os.getenv("OPENROUTER_API_KEY")
    if not api_key:
        return None
    return ChatOpenAI(
        model=os.getenv("OPENROUTER_MODEL"),
        api_key=api_key,
        base_url=os.getenv("OPENROUTER_BASE_URL"),
        temperature=0.2,
        timeout=45,
        max_retries=1,
    )

# fallback to local LLM
def local_llm():
    return ChatOpenAI(
        model=os.getenv("OLLAMA_MODEL", "qwen3:4b"),
        api_key="ollama",
        base_url=os.getenv("OLLAMA_BASE_URL"),
        temperature=0.2,
        timeout=90,
        max_retries=1,
    )

# Analysis Prompt
ANALYSIS_PROMPT = """
You are a senior technical analyst evaluating target business websites for a web development & automation agency.
### OUR SERVICES & OFFERINGS:
{service_description}
### TARGET WEBSITE DETAILS:
- URL: {url}
- Title: {title}
- Meta Description: {meta_description}
- Page Content:
{text}
### TASK:
Analyze the business and return ONLY a valid JSON object with the following fields:
1. "company_name": Name of the company.
2. "business_summary": 2-sentence summary of what they do.
3. "match_score": Fit rating from 0.0 to 100.0 based on how well our services match their needs.
4. "qualification_notes": 1-2 sentence explanation of why they are or aren't a good fit.
5. "opportunities": A list of 1 to 3 technical or automation opportunities. Each item must have:
   - "category": MUST be one of: "WEB_DEV", "BACKEND", "AUTOMATION", "PERFORMANCE", "UX_UI"
   - "title": Short title (e.g. "Slow product catalog load time")
   - "description": Why this hurts their business and how modernizing it helps
   - "evidence_snippet": Observed detail, quote, or flow from their site
6. "outreach_drafts": A dictionary containing platform-specific outreach messages:
   - "email_subject": Short, intriguing cold email subject line (under 7 words).
   - "email_body": Personalized cold email (under 120 words) citing one concrete observation from their site.
   - "linkedin_message": Professional LinkedIn connection note or InMail (under 300 characters).
   - "twitter_dm": Punchy, casual X/Twitter DM (under 240 characters) starting with a curiosity hook.
   - "instagram_dm": Friendly, conversational Instagram DM (under 240 characters) tailored to their brand aesthetic/operations.

Output ONLY valid JSON. Do not write any preamble, reasoning, or markdown outside the JSON.
"""

def extract_json(raw_text: str) -> dict:
    # Try to extract JSON from model output, handling think tags or markdown fences.
    cleaned = re.sub(r"<think>.*?</think>", "", raw_text, flags=re.DOTALL).strip()

    if "```json" in cleaned:
        cleaned = cleaned.split("```json")[1].split("```")[0].strip()
    elif "```" in cleaned:
        cleaned = cleaned.split("```")[1].split("```")[0].strip()

    start = cleaned.find("{")
    end = cleaned.rfind("}")
    if start != -1 and end != -1:
        cleaned = cleaned[start:end + 1]

    return json.loads(cleaned, strict=False)

def execute_llms(chain_input: dict) -> tuple[dict, str]:
    prompt = ChatPromptTemplate.from_template(ANALYSIS_PROMPT)
    openrouter_llm = Openrouter_llm()

    if openrouter_llm:
        try:
            print("First Trying the primary LLM (openrouter)...")
            chain = prompt | openrouter_llm
            response = chain.invoke(chain_input)
            data = extract_json(response.content)
            print("Openrouter response received and parsed successfully.")
            return data, "OpenRouter"
        except Exception as e:
            print(f"Primary LLM failed: {type(e).__name__} ({str(e)[:150]})")
            print("Switching to local LLM...")
    else:
        print("Openrouter API Key Not found switching to Local LLM. Please configure the API key first for better performance.")

    try:
        ollama_llm = local_llm()
        chain = prompt | ollama_llm
        response = chain.invoke(chain_input)
        data = extract_json(response.content)
        print("Local LLM Response Received and Parsed Successfully.")
        return data, "Local Ollama"
    except Exception as e:
        print(f"Both OpenRouter and local ones failed to respond: {e}")
        raise RuntimeError(f"ALL LLM providers failed to analyze Website: {e}")

# main orchestration function
def analyze_and_save(scraped_data: dict) -> Prospect:
    """
    Orchestrates website analysis with automatic LLM fallback,
    generates local embeddings, saves prospects with multi-channel contacts,
    and generates platform-specific OutreachDrafts for Email, LinkedIn, X, and Instagram.
    """
    if scraped_data.get("error"):
        raise ValueError(scraped_data["error"])

    # fetch Active service profile
    profile = ServiceProfile.objects.filter(is_active=True).first()
    service_desc = (
        profile.service_description
        if profile and profile.service_description
        else "Full-stack web development, Django backend APIs, PostgreSQL, and business automation."
    )

    # Execute LLM with fallback 
    chain_input = {
        "service_description": service_desc,
        "url": scraped_data["url"],
        "title": scraped_data["title"],
        "meta_description": scraped_data["meta_description"],
        "text": scraped_data["text"][:4000],
    }
    data, provider_used = execute_llms(chain_input)

    summary_text = data.get("business_summary", "")
    summary_vec = get_text_embedding(summary_text)

    # Save the prospect with all harvested contact channels
    contacts = scraped_data.get("contacts", {})
    match_score = float(data.get("match_score", 0.0))
    qualification_notes = f"[{provider_used}] " + data.get("qualification_notes", "")

    prospect, _ = Prospect.objects.update_or_create(
        website_url=scraped_data["url"],
        defaults={
            "company_name": data.get("company_name", scraped_data["domain"]),
            "domain": scraped_data["domain"],
            "contact_email": contacts.get("email"),
            "linkedin_url": contacts.get("linkedin_url"),
            "X_url": contacts.get("x_url"),
            "instagram_url": contacts.get("instagram_url"),
            "buisness_summery": summary_text,
            "summary_embedding": summary_vec,
            "match_score": match_score,
            "qualification_notes": qualification_notes,
            "status": "QUALIFIED" if match_score >= 60.0 else "DISCOVERED"
        }
    )

    # Save Opportunity Findings
    valid_categories = ["WEB_DEV", "BACKEND", "AUTOMATION", "PERFORMANCE", "UX_UI"]
    prospect.findings.all().delete()
    for opp in data.get("opportunities", []):
        cat = opp.get("category", "WEB_DEV")
        if cat not in valid_categories:
            cat = "WEB_DEV"

        OpportunityFinding.objects.create(
            prospect=prospect,
            category=cat,
            title=opp.get("title", "Identified Opportunity"),
            description=opp.get("description", ""),
            evidence_snippet=opp.get("evidence_snippet", ""),
            evidence_url=scraped_data["url"]
        )

    # Save Multi-Channel Outreach Drafts (Email, LinkedIn, X, Instagram)
    drafts_data = data.get("outreach_drafts", {})
    prospect.drafts.all().delete()

    # 1. Cold Email
    email_body = drafts_data.get("email_body") or data.get("email_body", "")
    email_subject = drafts_data.get("email_subject") or data.get("email_subject", "Quick observation regarding your website")
    if email_body:
        OutreachDraft.objects.create(
            prospect=prospect,
            channel="EMAIL",
            subject=email_subject,
            body=email_body,
            status="PENDING_REVIEW",
        )

    # 2. LinkedIn InMail / Message
    linkedin_msg = drafts_data.get("linkedin_message")
    if linkedin_msg:
        OutreachDraft.objects.create(
            prospect=prospect,
            channel="LINKEDIN",
            subject="LinkedIn Message",
            body=linkedin_msg,
            status="PENDING_REVIEW",
        )

    # 3. Twitter / X DM
    twitter_dm = drafts_data.get("twitter_dm")
    if twitter_dm:
        OutreachDraft.objects.create(
            prospect=prospect,
            channel="TWITTER",
            subject="X / Twitter DM",
            body=twitter_dm,
            status="PENDING_REVIEW",
        )

    # 4. Instagram DM
    instagram_dm = drafts_data.get("instagram_dm")
    if instagram_dm:
        OutreachDraft.objects.create(
            prospect=prospect,
            channel="INSTAGRAM",
            subject="Instagram DM",
            body=instagram_dm,
            status="PENDING_REVIEW",
        )

    return prospect
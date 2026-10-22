from typing import Any, Dict
from langchain_core.prompts import ChatPromptTemplate
from agent.base import BaseAgent

COPYWRITING_PROMPT_TEMPLATE = """
You are a direct-response copywriter writing genuine, personal outreach to a business owner.
Avoid corporate buzzwords, excessive flattery, and generic templates.
Speak like a skilled, helpful developer reaching out with a specific observation.

PROSPECT DETAILS:
- Company Name: {company_name}
- Category: {category}
- Website URL: {url}
- Observed Technical Gaps:
{findings_text}

OFFER POSITIONING:
- Offer Title: {offer_title}
- Angle: {target_angle}

TASK:
Write 4 platform-specific outreach messages tailored to this business owner:
1. "email_subject": Short, curiosity-inducing subject line (under 7 words, e.g. "quick observation on {company_name}'s site").
2. "email_body": Concise cold email (under 120 words) citing one concrete observation from their site and how fixing it helps them.
3. "linkedin_message": Professional LinkedIn connection message or InMail (under 280 characters).
4. "twitter_dm": Casual, punchy X/Twitter direct message (under 240 characters).
5. "instagram_dm": Conversational, direct Instagram DM (under 240 characters).

Return ONLY valid JSON matching this schema:
{{
  "email_subject": "...",
  "email_body": "...",
  "linkedin_message": "...",
  "twitter_dm": "...",
  "instagram_dm": "..."
}}
Do not write any preamble, commentary, or markdown outside the JSON.
"""


class CopywriterAgent(BaseAgent):
    """
    Copywriter Agent: Crafts hyper-personalized, channel-native outreach drafts
    in a single structured pass, strictly adhering to platform character limits.
    """

    def __init__(self):
        super().__init__(name="CopywriterAgent", role="Multi-Channel Outreach Copywriter")

    def run(self, company_name: str, category: str, url: str, findings: list[dict], strategy: dict) -> Dict[str, str]:
        llm = self.get_llm(temperature=0.3, timeout=35)
        prompt = ChatPromptTemplate.from_template(COPYWRITING_PROMPT_TEMPLATE)

        findings_text = "\n".join([f"- {f.get('title')}: {f.get('description')}" for f in findings]) or "General modernization"

        chain = prompt | llm
        response = chain.invoke({
            "company_name": company_name,
            "category": category,
            "url": url,
            "findings_text": findings_text,
            "offer_title": strategy.get("offer_title", "Custom Web & Automation"),
            "target_angle": strategy.get("target_angle", "Modernizing digital customer acquisition"),
        })

        return self.extract_json(response.content)

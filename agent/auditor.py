from typing import Any, Dict, List
from langchain_core.prompts import ChatPromptTemplate
from agent.base import BaseAgent

AUDIT_PROMPT_TEMPLATE = """
You are a fast technical auditor assessing a business website for a freelance web developer/automation specialist.

TARGET NICHE CATEGORY: {category}
WEBSITE URL: {url}
WEBSITE TITLE: {title}
META DESCRIPTION: {meta_description}
PAGE TEXT SNIPPET:
{text_snippet}

ZERO-LATENCY HEURISTICS DETECTED:
- Mobile Viewport Defined: {has_viewport}
- WhatsApp Click-to-Chat Detected: {has_whatsapp}
- Interactive Form Detected: {has_form}
- Booking Widget (Calendly/Cal.com) Detected: {has_booking}

TASK:
Identify 1 to 3 realistic, concrete operational or technical gaps on their site that a solo developer or freelancer can fix.
Focus strictly on realistic problems:
- For LOCAL_BUSINESS: No direct WhatsApp enquiry, outdated/missing mobile booking, static non-responsive design.
- For STARTUP_FOUNDER: Needs backend APIs, user authentication, database models, dashboard, or MVP features.
- For SMALL_AGENCY: Needs white-label development support, overflow backend capacity, or custom API integrations.
- For CONSULTANT: Needs lead capture dashboard, form-to-CRM syncing, automated email follow-up.
- For CREATOR: Needs custom portfolio website, automated booking flow, or newsletter capture.

Return ONLY a valid JSON object matching this schema:
{{
  "company_name": "Inferred clean business name",
  "business_summary": "1-2 sentence description of what they do",
  "findings": [
    {{
      "category": "WEB_DEV" or "BACKEND" or "AUTOMATION" or "PERFORMANCE" or "UX_UI",
      "title": "Short punchy gap title (e.g. Missing WhatsApp Instant Enquiry Button)",
      "description": "Why this hurts their conversions or operations",
      "evidence_snippet": "Observed evidence from page content or heuristics"
    }}
  ]
}}
Do not include any explanation or markdown outside the JSON.
"""


class AuditorAgent(BaseAgent):
    """
    Auditor Agent: Combines instant heuristic signals with targeted AI gap analysis
    to detect tangible opportunities on candidate business websites.
    """

    def __init__(self):
        super().__init__(name="AuditorAgent", role="Technical and Operational Gap Auditor")

    def run(self, probed_data: Dict[str, Any]) -> Dict[str, Any]:
        heuristics = probed_data.get("heuristics", {})
        category = probed_data.get("category", "LOCAL_BUSINESS")

        llm = self.get_llm(temperature=0.1, timeout=30)
        prompt = ChatPromptTemplate.from_template(AUDIT_PROMPT_TEMPLATE)

        chain = prompt | llm
        response = chain.invoke({
            "category": category,
            "url": probed_data.get("url", ""),
            "title": probed_data.get("title", ""),
            "meta_description": probed_data.get("meta_description", ""),
            "text_snippet": probed_data.get("text", "")[:1800],
            "has_viewport": heuristics.get("has_viewport", True),
            "has_whatsapp": heuristics.get("has_whatsapp", False),
            "has_form": heuristics.get("has_form", False),
            "has_booking": heuristics.get("has_booking", False),
        })

        parsed = self.extract_json(response.content)

        # Fallback if company name not extracted cleanly
        if not parsed.get("company_name"):
            raw_title = probed_data.get("title", "")
            parsed["company_name"] = raw_title.split("|")[0].split("-")[0].strip() or probed_data.get("url")

        return parsed

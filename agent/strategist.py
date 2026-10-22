from typing import Any, Dict
from agent.base import BaseAgent

CATEGORY_OFFERS = {
    "LOCAL_BUSINESS": {
        "offer_title": "Mobile-Responsive Website with Direct WhatsApp Enquiry System",
        "deliverables": [
            "Fast 3-page business website optimized for local SEO",
            "Direct click-to-chat WhatsApp button for instant customer conversions",
            "Simple contact/booking form sending email or SMS alerts",
        ],
        "target_angle": "Stop losing local search visitors to outdated or missing mobile booking flows.",
    },
    "STARTUP_FOUNDER": {
        "offer_title": "Django REST Framework APIs, Authentication & MVP Development",
        "deliverables": [
            "Clean PostgreSQL database architecture and models",
            "Token-based user authentication and permission tiers",
            "Scalable REST endpoints and third-party webhook integrations",
        ],
        "target_angle": "Ship your product faster with production-grade backend APIs without a full-time hire.",
    },
    "SMALL_AGENCY": {
        "offer_title": "White-Label Backend Development & Overflow Integration Partner",
        "deliverables": [
            "Seamless white-label execution of backend/API client requests",
            "Custom integrations and business process automations",
            "Zero client-facing overhead with direct Git handoffs",
        ],
        "target_angle": "Take on complex technical client projects without hiring full-time developers.",
    },
    "CONSULTANT": {
        "offer_title": "Lead-Management Dashboard & Automated CRM Follow-Up Workflow",
        "deliverables": [
            "Centralized dashboard tracking incoming inquiries across channels",
            "Automated instant email and WhatsApp follow-ups",
            "Form-to-CRM syncing to eliminate lost high-ticket leads",
        ],
        "target_angle": "Save 5+ hours weekly and prevent missed leads with automated follow-ups.",
    },
    "CREATOR": {
        "offer_title": "Custom Branded Portfolio, Landing Pages & Direct Booking System",
        "deliverables": [
            "Modern personal brand website replacing generic link-in-bio tools",
            "Seamless appointment booking and automated client intake form",
            "Newsletter signup integration to own your audience directly",
        ],
        "target_angle": "Elevate your brand presence and own your client booking funnel.",
    },
}


class StrategistAgent(BaseAgent):
    """
    Strategist Agent: Matches detected technical gaps to practical, high-converting
    beginner freelancer offers tailored to the specific niche category.
    """

    def __init__(self):
        super().__init__(name="StrategistAgent", role="Niche Positioning and Offer Matcher")

    def run(self, category: str, company_name: str, findings: list[dict], heuristics: dict) -> Dict[str, Any]:
        offer = CATEGORY_OFFERS.get(category, CATEGORY_OFFERS["LOCAL_BUSINESS"])

        # Calculate a deterministic, grounded match score based on tangible gaps
        score = 65.0
        if not heuristics.get("has_whatsapp") and category == "LOCAL_BUSINESS":
            score += 15.0
        if not heuristics.get("has_booking") and category in ["LOCAL_BUSINESS", "CONSULTANT", "CREATOR"]:
            score += 10.0
        if not heuristics.get("has_viewport"):
            score += 10.0
        if len(findings) >= 2:
            score += 10.0

        match_score = min(round(score, 1), 98.0)

        # Build qualification summary
        top_findings_str = "; ".join(f.get("title", "") for f in findings[:2])
        qualification_notes = (
            f"Strong fit for {offer['offer_title']}. "
            f"Key opportunities detected: {top_findings_str}."
        )

        return {
            "category": category,
            "match_score": match_score,
            "offer_title": offer["offer_title"],
            "deliverables": offer["deliverables"],
            "target_angle": offer["target_angle"],
            "qualification_notes": qualification_notes,
        }

import time
import logging
from urllib.parse import urlparse
from concurrent.futures import ThreadPoolExecutor, as_completed
from typing import Any, Dict, List, Optional
from django.db import transaction

from agent.base import BaseAgent
from agent.scout import ScoutAgent
from agent.auditor import AuditorAgent
from agent.strategist import StrategistAgent
from agent.copywriter import CopywriterAgent
from prospects.models import Prospect, OpportunityFinding, OutreachDraft

logger = logging.getLogger("agent.coordinator")


class AgentCoordinator(BaseAgent):
    """
    Coordinator / Supervisor Agent:
    Orchestrates the multi-agent workflow concurrently across discovered candidate businesses.
    Fans out Auditor, Strategist, and Copywriter agents in parallel workers for maximum speed.
    """

    def __init__(self):
        super().__init__(name="AgentCoordinator", role="Pipeline Orchestrator")
        self.scout = ScoutAgent()
        self.auditor = AuditorAgent()
        self.strategist = StrategistAgent()
        self.copywriter = CopywriterAgent()

    def process_single_candidate(self, candidate: Dict[str, Any], category: str) -> Optional[Prospect]:
        """
        Executes Auditor -> Strategist -> Copywriter pipeline for a single candidate business
        and persists the records into PostgreSQL inside a database transaction.
        """
        url = candidate.get("url")
        if not url:
            return None

        parsed_url = urlparse(url)
        domain = parsed_url.netloc.lower()
        if domain.startswith("www."):
            domain = domain[4:]

        try:
            # 1. Auditor Agent: Evaluate technical & operational gaps
            audit_result = self.auditor.run(candidate)
            company_name = audit_result.get("company_name") or candidate.get("title", "")[:50] or domain
            summary = audit_result.get("business_summary") or candidate.get("meta_description") or ""
            findings_data = audit_result.get("findings", [])

            # 2. Strategist Agent: Match with niche value proposition
            strategy = self.strategist.run(
                category=category,
                company_name=company_name,
                findings=findings_data,
                heuristics=candidate.get("heuristics", {}),
            )

            # 3. Copywriter Agent: Draft multi-channel outreach
            drafts_data = self.copywriter.run(
                company_name=company_name,
                category=category,
                url=url,
                findings=findings_data,
                strategy=strategy,
            )

            # 4. Save to PostgreSQL
            with transaction.atomic():
                contacts = candidate.get("contacts", {})
                detected_tech = []
                if candidate.get("heuristics", {}).get("has_whatsapp"):
                    detected_tech.append("WhatsApp Click-to-Chat")
                if candidate.get("heuristics", {}).get("has_booking"):
                    detected_tech.append("Online Booking Widget")

                prospect, _ = Prospect.objects.update_or_create(
                    website_url=url,
                    defaults={
                        "company_name": company_name,
                        "domain": domain,
                        "industry": category.replace("_", " ").title(),
                        "category": category,
                        "location": candidate.get("location", ""),
                        "contact_email": contacts.get("email", ""),
                        "linkedin_url": contacts.get("linkedin_url") or None,
                        "X_url": contacts.get("x_url") or None,
                        "instagram_url": contacts.get("instagram_url") or None,
                        "buisness_summery": summary,
                        "match_score": strategy.get("match_score", 70.0),
                        "qualification_notes": strategy.get("qualification_notes", ""),
                        "tech_stack_detected": detected_tech,
                        "status": "QUALIFIED" if strategy.get("match_score", 0) >= 65 else "DISCOVERED",
                    }
                )

                # Persist findings
                prospect.findings.all().delete()
                for f in findings_data:
                    OpportunityFinding.objects.create(
                        prospect=prospect,
                        category=f.get("category", "WEB_DEV"),
                        title=f.get("title", "Modernization Opportunity"),
                        description=f.get("description", ""),
                        evidence_snippet=f.get("evidence_snippet", ""),
                        evidence_url=url,
                    )

                # Persist drafts
                prospect.drafts.all().delete()
                channel_map = [
                    ("EMAIL", drafts_data.get("email_subject", f"Quick observation for {company_name}"), drafts_data.get("email_body", "")),
                    ("LINKEDIN", f"LinkedIn Connection - {company_name}", drafts_data.get("linkedin_message", "")),
                    ("TWITTER", f"X DM - {company_name}", drafts_data.get("twitter_dm", "")),
                    ("INSTAGRAM", f"Instagram DM - {company_name}", drafts_data.get("instagram_dm", "")),
                ]

                for channel, subject, body in channel_map:
                    if body:
                        OutreachDraft.objects.create(
                            prospect=prospect,
                            channel=channel,
                            subject=subject,
                            body=body,
                            status="PENDING_REVIEW",
                        )

            return prospect

        except Exception as e:
            logger.error(f"[Coordinator] Error processing candidate {url}: {e}")
            return None

    def run(
        self,
        category: str = "LOCAL_BUSINESS",
        niche: str = "gym",
        location: str = "Bangalore",
        max_prospects: int = 3,
    ) -> Dict[str, Any]:
        """
        Runs the full concurrent multi-agent prospecting pipeline.
        """
        pipeline_start = time.time()

        # Step 1: Scout Agent discovers and probes candidates
        candidates = self.scout.run(
            category=category,
            niche=niche,
            location=location,
            max_candidates=max_prospects,
        )

        if not candidates:
            return {
                "category": category,
                "niche": niche,
                "location": location,
                "total_discovered": 0,
                "prospects": [],
                "duration_seconds": round(time.time() - pipeline_start, 2),
            }

        # Step 2: Concurrent Fan-out across all discovered candidates
        saved_prospects = []
        max_workers = min(len(candidates), 4)

        with ThreadPoolExecutor(max_workers=max_workers) as executor:
            future_to_cand = {
                executor.submit(self.process_single_candidate, cand, category): cand
                for cand in candidates
            }
            for future in as_completed(future_to_cand):
                prospect = future.result()
                if prospect:
                    saved_prospects.append(prospect)

        duration = round(time.time() - pipeline_start, 2)
        logger.info(f"[Coordinator] Processed {len(saved_prospects)} prospects in {duration}s.")

        return {
            "category": category,
            "niche": niche,
            "location": location,
            "total_discovered": len(saved_prospects),
            "prospects": saved_prospects,
            "duration_seconds": duration,
        }

import os
import sys
from pathlib import Path

# 1. Add project root to sys.path so 'prospects' can be imported
BASE_DIR = Path(__file__).resolve().parent.parent
sys.path.append(str(BASE_DIR))

# Ensure UTF-8 output on Windows console
if sys.platform == "win32":
    try:
        sys.stdout.reconfigure(encoding="utf-8")
    except Exception:
        pass

# 2. Initialize Django settings & apps
os.environ.setdefault("DJANGO_SETTINGS_MODULE", "config.settings")
import django
django.setup()

# 3. Import prospecting orchestrator
from prospects.services.orchestrator import run_portfolio_driven_prospecting

# Set your portfolio or agency website URL here:
MY_PORTFOLIO_URL = "https://surajitsutradhar.in"

print("==========================================")
print("[Pipeline] Starting Portfolio-Driven Client Discovery")
print(f"[Pipeline] Portfolio URL: {MY_PORTFOLIO_URL}")
print("==========================================")

# Runs full flow: Portfolio Analysis -> Niche Discovery -> Contact Harvesting -> Multi-Channel Drafting
prospects = run_portfolio_driven_prospecting(
    portfolio_url=MY_PORTFOLIO_URL,
    max_prospects_per_niche=2
)

print(f"\n==========================================")
print(f"[Results] Total Prospects Discovered & Analyzed: {len(prospects)}")
print("==========================================")

for p in prospects:
    print(f"\n--- Company: {p.company_name} ({p.website_url}) ---")
    print(f"Match Score: {p.match_score}/100 | Status: {p.status}")
    print(f"Contacts: Email={p.contact_email} | LinkedIn={p.linkedin_url} | X={p.X_url} | IG={p.instagram_url}")
    print(f"Findings: {p.findings.count()} opportunities identified")
    
    print("\nOutreach Drafts:")
    for draft in p.drafts.all():
        print(f"  [{draft.get_channel_display()}]")
        if draft.subject:
            print(f"  Subject: {draft.subject}")
        print(f"  Message: {draft.body}")
        print("  " + "-" * 35)

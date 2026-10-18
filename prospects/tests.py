import os
import sys
from pathlib import Path

# 1. Add project root to sys.path so 'prospects' can be imported
BASE_DIR = Path(__file__).resolve().parent.parent
sys.path.append(str(BASE_DIR))

# 2. Initialize Django settings & apps
os.environ.setdefault("DJANGO_SETTINGS_MODULE", "config.settings")
import django
django.setup()

# 3. Now import your services
from prospects.services.scraper import extract_website_content
from prospects.services.analyzer import analyze_and_save

# 4. Scrape target website
print("Scraping website...")
scraped = extract_website_content("https://stripe.com")

# 5. Analyze with fallback & save to DB
print("Analyzing with LLM...")
prospect = analyze_and_save(scraped)

print(f"\n Company: {prospect.company_name}")
print(f" Match Score: {prospect.match_score}/100")
print(f" Status: {prospect.status}")
print(f" Findings Count: {prospect.findings.count()}")
if prospect.drafts.exists():
    print(f" Draft Subject: {prospect.drafts.first().subject}")
    print(f"\n Draft Email Body:\n{prospect.drafts.first().body}")

import time
from prospects.models import ServiceProfile, Prospect
from prospects.services.portfolio import analyze_and_sync_portfolio
from prospects.services.discovery import discover_candidate_urls
from prospects.services.scraper import extract_website_content
from prospects.services.analyzer import analyze_and_save


def run_portfolio_driven_prospecting(portfolio_url: str = None, max_prospects_per_niche: int = 2) -> list[Prospect]:
    """
    Complete Autonomous Client Acquisition Pipeline:
    1. Analyzes your portfolio website to learn your services and target customer profiles.
    2. Searches the public web to find real client websites matching your derived ICPs.
    3. Scrapes each candidate business and extracts Email, LinkedIn, X, and Instagram handles.
    4. Evaluates fit and writes platform-native cold outreach drafts grounded in your portfolio.
    5. Saves everything into PostgreSQL.
    """
    # 1. Sync or retrieve profile
    if portfolio_url:
        profile, search_queries = analyze_and_sync_portfolio(portfolio_url)
    else:
        profile = ServiceProfile.objects.filter(is_active=True).first()
        if not profile:
            raise ValueError("No active ServiceProfile found. Please provide a portfolio_url.")
        search_queries = [line.replace("- ", "").strip() for line in profile.target_icp_criteria.splitlines() if line.strip()]

    print(f"\n[Pipeline] Active Service Profile: {profile.name}")
    print(f"[Pipeline] Targeting {len(search_queries)} search niches derived from your portfolio.")

    all_saved_prospects = []

    # 2. Iterate through niches derived from your portfolio
    for niche_idx, query in enumerate(search_queries[:3], 1):
        print(f"\n==========================================")
        print(f"[Niche {niche_idx}/{len(search_queries)}] Finding prospects for: '{query}'")
        print(f"==========================================")

        candidates = discover_candidate_urls(query, max_candidates=max_prospects_per_niche * 2)
        print(f"[Discovery] Found {len(candidates)} candidate domains.")

        for url in candidates:
            if len(all_saved_prospects) >= (max_prospects_per_niche * 3):
                break

            print(f"\n[Analyze] Visiting: {url}")
            try:
                # Scrape content and contact handles
                scraped = extract_website_content(url)
                if scraped.get("error"):
                    print(f"[Skip] {scraped['error']}")
                    continue

                contacts = scraped.get("contacts", {})
                print(f"  Contacts: Email={contacts.get('email')}, LinkedIn={bool(contacts.get('linkedin_url'))}, X={bool(contacts.get('x_url'))}, IG={bool(contacts.get('instagram_url'))}")

                # Analyze opportunities and write drafts
                prospect = analyze_and_save(scraped)
                all_saved_prospects.append(prospect)

                print(f"  Saved: {prospect.company_name} | Match Score: {prospect.match_score}/100 | Drafts: {prospect.drafts.count()}")
                time.sleep(1)

            except Exception as e:
                print(f"[Error] Failed analyzing {url}: {e}")

    print(f"\n[Complete] Prospecting finished. Total clients saved: {len(all_saved_prospects)}")
    return all_saved_prospects

import re
import time
from urllib.parse import urlparse
from ddgs import DDGS
from prospects.models import ServiceProfile, Prospect
from prospects.services.scraper import extract_website_content
from prospects.services.analyzer import analyze_and_save

# Domains to ignore (directories, platforms, social networks, aggregators)
EXCLUDED_DOMAINS = {
    "wikipedia.org", "en.wikipedia.org", "amazon.com", "ebay.com", "yelp.com",
    "yellowpages.com", "facebook.com", "instagram.com", "twitter.com", "x.com",
    "linkedin.com", "youtube.com", "reddit.com", "pinterest.com", "tiktok.com",
    "shopify.com", "wordpress.org", "wordpress.com", "medium.com", "github.com",
    "quora.com", "clutch.co", "g2.com", "trustpilot.com", "tripadvisor.com"
}


def is_valid_prospect_url(url: str) -> bool:
    """
    Checks if a URL belongs to a real independent business rather than an aggregator or directory.
    """
    if not url or not url.startswith(("http://", "https://")):
        return False

    parsed = urlparse(url)
    domain = parsed.netloc.lower()
    
    # Strip 'www.'
    if domain.startswith("www."):
        domain = domain[4:]

    # Exclude directories and search engines
    for excluded in EXCLUDED_DOMAINS:
        if domain == excluded or domain.endswith("." + excluded):
            return False

    # Ignore search ad redirect links
    if "bing.com/aclick" in url or "google.com/aclk" in url:
        return False

    return True


def discover_candidate_urls(query: str, max_candidates: int = 10) -> list[str]:
    """
    Uses DuckDuckGo search to find candidate business website URLs matching the target ICP.
    """
    candidates = []
    seen_domains = set()

    # Search variations to find real businesses
    search_queries = [
        f"{query} official website",
        f"{query} site:.com",
    ]

    try:
        with DDGS() as ddgs:
            for q in search_queries:
                print(f"[Search] Searching: '{q}'...")
                results = ddgs.text(q, max_results=max_candidates * 2)
                for r in results:
                    href = r.get("href", "")
                    if is_valid_prospect_url(href):
                        domain = urlparse(href).netloc.lower()
                        if domain not in seen_domains:
                            seen_domains.add(domain)
                            # Get root homepage URL
                            parsed = urlparse(href)
                            root_url = f"{parsed.scheme}://{parsed.netloc}"
                            candidates.append(root_url)

                    if len(candidates) >= max_candidates:
                        break

                if len(candidates) >= max_candidates:
                    break
    except Exception as e:
        print(f"[Warning] Search error: {e}")

    return candidates[:max_candidates]


def discover_and_analyze_prospects(target_icp: str, max_prospects: int = 5) -> list[Prospect]:
    """
    Full End-to-End Discovery Pipeline:
    1. Finds candidate business websites matching your target client query.
    2. Scrapes each website and harvests Email, LinkedIn, X, and Instagram handles.
    3. Runs AI research to find genuine opportunities and gaps.
    4. Generates platform-specific outreach drafts for each channel.
    5. Saves prospects and findings into PostgreSQL.
    """
    print(f"\n[Discovery] Starting lead discovery for target: '{target_icp}'")
    candidate_urls = discover_candidate_urls(target_icp, max_candidates=max_prospects * 2)
    print(f"[Discovery] Discovered {len(candidate_urls)} candidate business websites.")

    saved_prospects = []

    for i, url in enumerate(candidate_urls, 1):
        if len(saved_prospects) >= max_prospects:
            break

        print(f"\n--- [{i}/{len(candidate_urls)}] Analyzing: {url} ---")
        try:
            # 1. Scrape content and harvest contact channels
            scraped = extract_website_content(url)
            if scraped.get("error"):
                print(f"[Skip] Skipping {url}: {scraped['error']}")
                continue

            contacts = scraped.get("contacts", {})
            print(f"   [Contacts] Found: Email={contacts.get('email')}, LinkedIn={bool(contacts.get('linkedin_url'))}, X={bool(contacts.get('x_url'))}, IG={bool(contacts.get('instagram_url'))}")

            # 2. Run analysis and save into PostgreSQL
            prospect = analyze_and_save(scraped)
            saved_prospects.append(prospect)

            print(f"   [Saved] {prospect.company_name} | Match Score: {prospect.match_score}/100 | Drafts: {prospect.drafts.count()}")

            # Polite delay between requests
            time.sleep(1)

        except Exception as e:
            print(f"   [Error] Error analyzing {url}: {e}")

    print(f"\n[Complete] Discovery complete. Successfully processed and saved {len(saved_prospects)} prospects.")
    return saved_prospects

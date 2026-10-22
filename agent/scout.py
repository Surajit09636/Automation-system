import re
from urllib.parse import urlparse
from concurrent.futures import ThreadPoolExecutor, as_completed
import requests
from bs4 import BeautifulSoup
from ddgs import DDGS
from agent.base import BaseAgent

EXCLUDED_DOMAINS = {
    "wikipedia.org", "en.wikipedia.org", "amazon.com", "ebay.com", "yelp.com",
    "yellowpages.com", "facebook.com", "instagram.com", "twitter.com", "x.com",
    "linkedin.com", "youtube.com", "reddit.com", "pinterest.com", "tiktok.com",
    "shopify.com", "wordpress.org", "wordpress.com", "medium.com", "github.com",
    "quora.com", "clutch.co", "g2.com", "trustpilot.com", "tripadvisor.com",
    "justdial.com", "indiamart.com", "forbes.com", "bloomberg.com", "techcrunch.com",
    "crunchbase.com", "glassdoor.com", "indeed.com"
}

NICHE_SEARCH_TEMPLATES = {
    "LOCAL_BUSINESS": [
        '{niche} in {location} "contact" "phone"',
        '{niche} centre in {location} "enquiry" OR "whatsapp"',
        'best {niche} in {location} official website -site:justdial.com -site:yelp.com',
    ],
    "STARTUP_FOUNDER": [
        '"launching" "{niche}" MVP "founder"',
        '"Show HN" "{niche}"',
        '"{niche}" startup "early access" OR "waitlist" -site:forbes.com',
    ],
    "SMALL_AGENCY": [
        '"digital agency" OR "creative agency" "{niche}" {location} "our team"',
        '"web design agency" {location} "services" "contact us"',
        'boutique "{niche}" agency {location} -site:clutch.co',
    ],
    "CONSULTANT": [
        '"{niche} consultant" {location} "book a consultation" OR "work with me"',
        '"{niche} coach" "schedule a call" "contact"',
        'independent "{niche}" advisor "contact us"',
    ],
    "CREATOR": [
        '"{niche}" educator OR creator "newsletter" "work with me"',
        '"{niche}" "course" "enroll" "contact" -site:udemy.com -site:coursera.org',
        '"{niche}" portfolio "book a call" "about me"',
    ],
}


class ScoutAgent(BaseAgent):
    """
    Scout Agent: Rapidly discovers candidate businesses matching specific niche categories
    and harvests contact channels (Email, Phone, WhatsApp, Socials) concurrently.
    """

    def __init__(self):
        super().__init__(name="ScoutAgent", role="Target Discovery and Contact Harvester")
        self.headers = {
            "User-Agent": (
                "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
                "AppleWebKit/537.36 (KHTML, like Gecko) "
                "Chrome/124.0.0.0 Safari/537.36"
            ),
            "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
        }

    def is_valid_candidate_domain(self, url: str) -> bool:
        if not url or not url.startswith(("http://", "https://")):
            return False

        parsed = urlparse(url)
        domain = parsed.netloc.lower()
        if domain.startswith("www."):
            domain = domain[4:]

        for excluded in EXCLUDED_DOMAINS:
            if domain == excluded or domain.endswith("." + excluded):
                return False

        if "bing.com/aclick" in url or "google.com/aclk" in url:
            return False

        return True

    def build_queries(self, category: str, niche: str, location: str) -> list[str]:
        templates = NICHE_SEARCH_TEMPLATES.get(category, NICHE_SEARCH_TEMPLATES["LOCAL_BUSINESS"])
        clean_niche = niche.strip() if niche else "service business"
        clean_location = location.strip() if location else ""

        queries = []
        for t in templates:
            q = t.format(niche=clean_niche, location=clean_location).strip()
            # Clean empty double spaces
            q = re.sub(r"\s+", " ", q)
            queries.append(q)
        return queries

    def search_candidates(self, queries: list[str], max_urls: int = 8) -> list[str]:
        seen_domains = set()
        candidate_urls = []

        try:
            with DDGS() as ddgs:
                for q in queries:
                    if len(candidate_urls) >= max_urls:
                        break
                    try:
                        results = ddgs.text(q, max_results=max_urls * 2)
                        for r in results:
                            href = r.get("href", "")
                            if self.is_valid_candidate_domain(href):
                                parsed = urlparse(href)
                                domain = parsed.netloc.lower()
                                if domain not in seen_domains:
                                    seen_domains.add(domain)
                                    root_url = f"{parsed.scheme}://{parsed.netloc}"
                                    candidate_urls.append(root_url)
                                    if len(candidate_urls) >= max_urls:
                                        break
                    except Exception:
                        continue
        except Exception:
            pass

        return candidate_urls[:max_urls]

    def quick_probe_and_extract(self, url: str) -> dict:
        """
        Lightweight HTTP GET probe with short timeout to fetch page title,
        detect WhatsApp links, emails, and social handles without heavy parsing.
        """
        result = {
            "url": url,
            "reachable": False,
            "title": "",
            "meta_description": "",
            "text": "",
            "contacts": {
                "email": "",
                "phone": "",
                "whatsapp_url": "",
                "linkedin_url": "",
                "x_url": "",
                "instagram_url": "",
            },
            "heuristics": {
                "has_whatsapp": False,
                "has_form": False,
                "has_booking": False,
                "has_viewport": True,
                "is_responsive": True,
            },
        }

        try:
            resp = requests.get(url, headers=self.headers, timeout=5, allow_redirects=True)
            if resp.status_code >= 400:
                return result

            result["reachable"] = True
            html = resp.text
            soup = BeautifulSoup(html[:150000], "html.parser")

            # Title & Meta
            title_tag = soup.find("title")
            result["title"] = title_tag.get_text(strip=True) if title_tag else ""
            meta_desc = soup.find("meta", attrs={"name": "description"}) or soup.find("meta", attrs={"property": "og:description"})
            result["meta_description"] = meta_desc.get("content", "").strip() if meta_desc else ""

            # Check Viewport (Mobile responsiveness signal)
            viewport = soup.find("meta", attrs={"name": "viewport"})
            result["heuristics"]["has_viewport"] = bool(viewport)

            # Check Forms and Bookings
            forms = soup.find_all("form")
            result["heuristics"]["has_form"] = len(forms) > 0
            booking_cues = ["calendly", "cal.com", "book", "appointment", "schedule"]
            result["heuristics"]["has_booking"] = any(cue in html.lower() for cue in booking_cues)

            # WhatsApp Detection
            wa_match = re.search(r'(https?://(?:api\.whatsapp\.com/send\?phone=|wa\.me/)[0-9+]+)', html)
            if wa_match:
                result["contacts"]["whatsapp_url"] = wa_match.group(1)
                result["heuristics"]["has_whatsapp"] = True

            # Email Extraction
            email_match = re.search(r'[a-zA-Z0-9_.+-]+@[a-zA-Z0-9-]+\.[a-zA-Z0-9-.]+', html)
            if email_match:
                candidate_email = email_match.group(0)
                # Ignore assets
                if not candidate_email.endswith(('.png', '.jpg', '.webp', '.svg', '.js', '.css')):
                    result["contacts"]["email"] = candidate_email

            # Social Links
            for a in soup.find_all("a", href=True):
                href = a["href"].strip()
                if "linkedin.com/company" in href or "linkedin.com/in/" in href:
                    if not result["contacts"]["linkedin_url"]:
                        result["contacts"]["linkedin_url"] = href
                elif "twitter.com/" in href or "x.com/" in href:
                    if not any(ign in href for ign in ["share", "intent", "twitter.com/home"]):
                        if not result["contacts"]["x_url"]:
                            result["contacts"]["x_url"] = href
                elif "instagram.com/" in href:
                    if not any(ign in href for ign in ["/p/", "/reel/", "/explore/"]):
                        if not result["contacts"]["instagram_url"]:
                            result["contacts"]["instagram_url"] = href

            # Body text summary
            for s in soup(["script", "style", "noscript", "svg", "nav", "footer"]):
                s.decompose()
            text = soup.get_text(separator=" ", strip=True)
            result["text"] = re.sub(r"\s+", " ", text)[:2500]

        except Exception:
            pass

        return result

    def run(self, category: str = "LOCAL_BUSINESS", niche: str = "gym", location: str = "Bangalore", max_candidates: int = 4) -> list[dict]:
        """
        Executes search and concurrent probing.
        """
        queries = self.build_queries(category, niche, location)
        candidate_urls = self.search_candidates(queries, max_urls=max_candidates * 2)

        discovered = []
        with ThreadPoolExecutor(max_workers=5) as executor:
            future_to_url = {executor.submit(self.quick_probe_and_extract, url): url for url in candidate_urls}
            for future in as_completed(future_to_url):
                res = future.result()
                if res["reachable"] and (res["title"] or res["text"]):
                    res["category"] = category
                    res["location"] = location
                    discovered.append(res)
                    if len(discovered) >= max_candidates:
                        break

        return discovered[:max_candidates]

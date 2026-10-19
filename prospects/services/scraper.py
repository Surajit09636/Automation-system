import re
import requests
from bs4 import BeautifulSoup
from urllib.parse import urlparse

HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
        "AppleWebKit/537.36 (KHTML, like Gecko) Chrome/127.0.0.0 Safari/537.36"
    )
}

def extract_contacts_and_socials(soup: BeautifulSoup, raw_html: str) -> dict:
    """
    Extracts email, LinkedIn, X/Twitter, and Instagram handles from <a> tags and raw HTML.
    """
    contacts = {
        "email": None,
        "linkedin_url": None,
        "x_url": None,
        "instagram_url": None,
    }

    # 1. Scan all anchor links
    for a in soup.find_all("a", href=True):
        href = a["href"].strip()
        href_lower = href.lower()

        # Email from mailto:
        if href_lower.startswith("mailto:") and not contacts["email"]:
            email = href[7:].split("?")[0].strip()
            if "@" in email and "." in email:
                contacts["email"] = email

        # LinkedIn Company or Profile
        if ("linkedin.com/company/" in href_lower or "linkedin.com/in/" in href_lower) and not contacts["linkedin_url"]:
            contacts["linkedin_url"] = href

        # X / Twitter
        if ("twitter.com/" in href_lower or "x.com/" in href_lower) and not contacts["x_url"]:
            if not any(skip in href_lower for skip in ["/intent/", "/share", "/widgets", "/search", "twitter.com/home"]):
                contacts["x_url"] = href

        # Instagram
        if "instagram.com/" in href_lower and not contacts["instagram_url"]:
            if not any(skip in href_lower for skip in ["/p/", "/reel/", "/stories/", "/explore"]):
                contacts["instagram_url"] = href

    # 2. Fallback regex search for email in page text
    if not contacts["email"]:
        email_pattern = r'[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}'
        found_emails = re.findall(email_pattern, raw_html)
        ignored_extensions = ('.png', '.jpg', '.jpeg', '.gif', '.webp', '.svg', '.js', '.css')
        for em in found_emails:
            if not any(em.lower().endswith(ext) for ext in ignored_extensions):
                contacts["email"] = em
                break

    return contacts


def extract_website_content(url: str, max_chars: int = 6000) -> dict:
    """
    Fetches and extracts clean textual content, titles, metadata,
    and multi-channel contact handles (Email, LinkedIn, X, Instagram) from a given URL.
    """
    if not url.startswith(("http://", "https://")):
        url = "https://" + url

    domain = urlparse(url).netloc

    try:
        response = requests.get(url, headers=HEADERS, timeout=15)
        response.raise_for_status()
        raw_html = response.text
    except Exception as e:
        return {
            "url": url,
            "domain": domain,
            "error": f"Failed to fetch {url}: {str(e)}",
            "text": "",
            "contacts": {
                "email": None,
                "linkedin_url": None,
                "x_url": None,
                "instagram_url": None,
            }
        }

    soup = BeautifulSoup(raw_html, "html.parser")

    # Harvest contact handles BEFORE removing script/tag elements
    contacts = extract_contacts_and_socials(soup, raw_html)

    # Remove non-content elements
    for tag in soup(["script", "style", "svg", "noscript", "iframe"]):
        tag.decompose()

    # Extract meta tags
    title = soup.title.string.strip() if soup.title and soup.title.string else domain
    meta_desc = ""
    desc_tag = soup.find("meta", attrs={"name": "description"}) or soup.find("meta", attrs={"property": "og:description"})
    if desc_tag and desc_tag.get("content"):
        meta_desc = desc_tag["content"].strip()

    body_text = " ".join(soup.stripped_strings)
    truncated_text = body_text[:max_chars]

    return {
        "url": url,
        "domain": domain,
        "title": title,
        "meta_description": meta_desc,
        "text": truncated_text,
        "contacts": contacts,
        "error": None
    }
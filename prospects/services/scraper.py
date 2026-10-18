import requests
from bs4 import BeautifulSoup
from urllib.parse import urlparse

HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64)"
        "AppleWebKit/537.36 (KHTML, Like Gecko) Chrome/127.0.0.0 Safari/537.36"
    )
}

def extract_website_content(url: str, max_chars: int = 6000) -> dict:
    """
    Fetches and extract clean textual content, titles, and metadata from a given url
    """
    if not url.startswith(("http://", "https://")):
        url = "https://" + url

    domain = urlparse(url).netloc

    try:
        response = requests.get(url, headers = HEADERS, timeout = 15)
        response.raise_for_status()
    except Exception as e:
        return {
            "url": url,
            "domain": domain,
            "error": f"failed to fetch {url}: {str(e)}",
            "text": ""
        }

    soup = BeautifulSoup(response.text, "html.parser")

    # remove the non-content elements
    for tag in soup(["script", "style", "svg", "noscript", "iframe"]):
        tag.decompose()

    # Extract meta tags
    title = soup.title.string.strip() if soup.title and soup.title.string else domain
    meta_desc = ""
    desc_tag = soup.find("meta", attrs={"name": "description"}) or soup.find("meta", attrs = {"property": "og:description"})
    if desc_tag and desc_tag.get("content"):
        meta_desc = desc_tag["content"].strip()

    body_text = " ".join(soup.stripped_strings)

    turncated_text = body_text[:max_chars]

    return {
        "url": url,
        "domain": domain,
        "title": title,
        "meta_description": meta_desc,
        "text": turncated_text,
        "error": None
    }
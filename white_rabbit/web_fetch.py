from __future__ import annotations

from dataclasses import dataclass
from urllib.parse import urlsplit

import fitz
import httpx
from bs4 import BeautifulSoup


BLOCKED_HOST_MARKERS = (
    "tandfonline.com",
    "westlaw.com",
    "content.next.westlaw.com",
    "jstor.org",
    "sciencedirect.com",
    "link.springer.com",
    "wiley.com",
    "academic.oup.com",
)

GROUNDING_HOSTS = (
    "vertexaisearch.cloud.google.com",
    "grounding-api-redirect",
)


@dataclass
class FetchedPage:
    url: str
    title: str
    text: str
    content_type: str


def host_of(url: str) -> str:
    try:
        return urlsplit(url).netloc.lower()
    except Exception:
        return ""


def is_grounding_redirect(url: str) -> bool:
    host = host_of(url)
    path = urlsplit(url).path.lower() if url else ""
    return "vertexaisearch.cloud.google.com" in host or "grounding-api-redirect" in path or "grounding-api-redirect" in url


def is_blocked_source(url: str) -> bool:
    host = host_of(url)
    return any(marker in host for marker in BLOCKED_HOST_MARKERS)


def resolve_public_url(url: str, timeout: int = 20) -> str:
    """Follow redirects so Gemini grounding wrappers become real pages when possible."""
    headers = {
        "User-Agent": (
            "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
            "(KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36"
        ),
        "Accept": "text/html,application/xhtml+xml,application/pdf;q=0.9,*/*;q=0.8",
    }
    try:
        with httpx.Client(timeout=timeout, follow_redirects=True, headers=headers) as client:
            r = client.head(url)
            if r.status_code >= 400 or is_grounding_redirect(str(r.url)):
                r = client.get(url)
            return str(r.url)
    except Exception:
        return url


def fetch_page(url: str, timeout: int = 30) -> FetchedPage:
    headers = {
        "User-Agent": (
            "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
            "(KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36"
        ),
        "Accept": "text/html,application/xhtml+xml,application/pdf;q=0.9,*/*;q=0.8",
    }
    with httpx.Client(timeout=timeout, follow_redirects=True, headers=headers) as client:
        r = client.get(url)
        r.raise_for_status()
        ctype = (r.headers.get("content-type") or "").lower()
        final_url = str(r.url)
        if is_grounding_redirect(final_url):
            raise ValueError("citation is a Google grounding redirect with no public page text")
        if "application/pdf" in ctype or final_url.lower().endswith(".pdf"):
            doc = fitz.open(stream=r.content, filetype="pdf")
            text = "\n".join(page.get_text("text") for page in doc)
            return FetchedPage(final_url, final_url.rsplit("/", 1)[-1], text, "application/pdf")
        soup = BeautifulSoup(r.text, "html.parser")
        for tag in soup(["script", "style", "noscript", "svg", "nav", "footer"]):
            tag.decompose()
        title = soup.title.get_text(" ", strip=True) if soup.title else final_url
        main = soup.find("main") or soup.find("article") or soup.body or soup
        text = main.get_text("\n", strip=True)
        return FetchedPage(final_url, title, text, ctype or "text/html")

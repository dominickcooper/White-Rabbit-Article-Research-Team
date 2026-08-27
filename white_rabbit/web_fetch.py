from __future__ import annotations

import io
from dataclasses import dataclass

import fitz
import httpx
from bs4 import BeautifulSoup


@dataclass
class FetchedPage:
    url: str
    title: str
    text: str
    content_type: str


def fetch_page(url: str, timeout: int = 30) -> FetchedPage:
    headers = {
        "User-Agent": "Mozilla/5.0 (compatible; WhiteRabbitResearcher/0.1; research bot)"
    }
    with httpx.Client(timeout=timeout, follow_redirects=True, headers=headers) as client:
        r = client.get(url)
        r.raise_for_status()
        ctype = (r.headers.get("content-type") or "").lower()
        final_url = str(r.url)
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

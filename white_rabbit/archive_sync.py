from __future__ import annotations

import hashlib
import json
import random
import re
import time
import xml.etree.ElementTree as ET
from dataclasses import dataclass
from datetime import datetime, timezone
from email.utils import parsedate_to_datetime
from pathlib import Path
from urllib.parse import urljoin, urlsplit, urlunsplit

import httpx
from bs4 import BeautifulSoup, Tag
from markdownify import markdownify as to_markdown

from .archive_db import ArchiveDB


PAYWALL_MARKERS = (
    "subscribe to continue reading",
    "this post is for paid subscribers",
    "this post is for subscribers",
    "upgrade to paid",
    "become a paid subscriber",
)

CONTENT_SELECTORS = (
    "div.available-content",
    "div.body.markup",
    "div.post-content",
    "div[class*='available-content']",
    "div[class*='body markup']",
    "article",
)


@dataclass(frozen=True)
class ArticleSnapshot:
    title: str
    slug: str
    canonical_url: str
    published_date: str | None
    author: str | None
    markdown: str
    links: list[dict]
    content_status: str

    @property
    def content_hash(self) -> str:
        return hashlib.sha256(self.markdown.encode("utf-8")).hexdigest()

    @property
    def word_count(self) -> int:
        return len(re.findall(r"\b\w+\b", self.markdown))


class SubstackArchiveSync:
    def __init__(
        self,
        *,
        publication_url: str,
        archive_root: Path,
        db_path: Path,
        timeout: int = 30,
        sitemap_url: str = "",
        request_delay_ms: int = 120,
        max_retries: int = 6,
        backoff_base_seconds: float = 2.0,
        max_backoff_seconds: float = 90.0,
    ):
        self.publication_url = publication_url.rstrip("/")
        self.archive_root = Path(archive_root)
        self.articles_root = self.archive_root / "articles"
        self.sync_root = self.archive_root / "sync"
        self.imports_root = self.archive_root / "imports" / "substack_exports"
        for d in (self.articles_root, self.sync_root, self.imports_root):
            d.mkdir(parents=True, exist_ok=True)
        self.db = ArchiveDB(db_path)
        self.timeout = timeout
        self.sitemap_url = sitemap_url.strip() or f"{self.publication_url}/sitemap.xml"
        requested_delay = max(0, int(request_delay_ms))
        # The legacy MVP used 120ms, which is too aggressive for a large first-time
        # Substack archive crawl. Preserve 0 for tests, otherwise enforce a safer floor.
        self.request_delay_ms = 0 if requested_delay == 0 else max(1500, requested_delay)
        self.max_retries = max(0, int(max_retries))
        self.backoff_base_seconds = max(0.25, float(backoff_base_seconds))
        self.max_backoff_seconds = max(self.backoff_base_seconds, float(max_backoff_seconds))
        self.client = httpx.Client(
            timeout=self.timeout,
            follow_redirects=True,
            headers={
                "User-Agent": "WhiteRabbitResearcher/0.2 (+local archive sync; publication owner)",
                "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
            },
        )

    def close(self) -> None:
        self.client.close()
        self.db.close()

    @staticmethod
    def normalize_url(url: str) -> str:
        p = urlsplit(url.strip())
        scheme = p.scheme or "https"
        return urlunsplit((scheme, p.netloc.lower(), p.path.rstrip("/") or "/", "", ""))

    def _is_post_url(self, url: str) -> bool:
        try:
            p = urlsplit(url)
            return p.scheme in {"http", "https"} and "/p/" in p.path
        except Exception:
            return False

    @staticmethod
    def _retry_after_seconds(response: httpx.Response) -> float | None:
        raw = response.headers.get("Retry-After")
        if not raw:
            return None
        raw = raw.strip()
        try:
            return max(0.0, float(raw))
        except ValueError:
            try:
                dt = parsedate_to_datetime(raw)
                if dt.tzinfo is None:
                    dt = dt.replace(tzinfo=timezone.utc)
                return max(0.0, (dt - datetime.now(timezone.utc)).total_seconds())
            except Exception:
                return None

    def _get(self, url: str) -> httpx.Response:
        last_response: httpx.Response | None = None
        for attempt in range(self.max_retries + 1):
            response = self.client.get(url)
            last_response = response

            retryable = response.status_code == 429 or 500 <= response.status_code <= 599
            if retryable and attempt < self.max_retries:
                server_wait = self._retry_after_seconds(response) or 0.0
                exponential = min(
                    self.max_backoff_seconds,
                    self.backoff_base_seconds * (2 ** attempt),
                )
                cooldown = max(server_wait, exponential) + random.uniform(0.25, 1.25)
                reason = "rate limited (429)" if response.status_code == 429 else f"server error ({response.status_code})"
                print(
                    f"        {reason}; retry {attempt + 1}/{self.max_retries} "
                    f"after cooldown"
                )
                time.sleep(cooldown)
                continue

            response.raise_for_status()
            if self.request_delay_ms:
                base = self.request_delay_ms / 1000.0
                time.sleep(base + random.uniform(0.15, 0.65))
            return response

        assert last_response is not None
        last_response.raise_for_status()
        return last_response

    @staticmethod
    def _salvage_sitemap_locs(text: str) -> list[str]:
        """Recover <loc> entries even when a publisher emits malformed XML.

        Substack occasionally serves a sitemap containing an invalid XML token in one
        entry. A strict ElementTree parse then discards the entire sitemap. The URLs
        themselves are still recoverable, so use a deliberately narrow fallback that
        extracts only <loc> bodies.
        """
        from html import unescape

        locs: list[str] = []
        for raw in re.findall(r"<loc(?:\s[^>]*)?>(.*?)</loc>", text, flags=re.I | re.S):
            value = re.sub(r"<[^>]+>", "", raw)
            value = unescape(value).strip()
            if value.startswith(("http://", "https://")):
                locs.append(value)
        return locs

    def _discover_from_sitemap(self, url: str, seen_maps: set[str] | None = None) -> set[str]:
        seen_maps = seen_maps or set()
        url = self.normalize_url(url)
        if url in seen_maps or len(seen_maps) >= 30:
            return set()
        seen_maps.add(url)
        try:
            response = self._get(url)
        except Exception as exc:
            print(f"      sitemap unavailable: {url} ({exc})")
            return set()

        text = response.text
        is_index = "<sitemapindex" in text.lower()
        try:
            root = ET.fromstring(text)
            tag = root.tag.rsplit("}", 1)[-1].lower()
            is_index = tag == "sitemapindex"
            locs = [
                el.text.strip()
                for el in root.iter()
                if el.tag.rsplit("}", 1)[-1].lower() == "loc" and el.text
            ]
        except Exception as exc:
            locs = self._salvage_sitemap_locs(text)
            if locs:
                print(f"      sitemap XML malformed; recovered {len(locs)} URL entries from {url}")
            else:
                print(f"      sitemap unavailable: {url} ({exc})")
                return set()

        found: set[str] = set()
        if is_index:
            for child in locs:
                found |= self._discover_from_sitemap(child, seen_maps)
        else:
            for loc in locs:
                if self._is_post_url(loc):
                    found.add(self.normalize_url(loc))
        return found

    def _discover_from_feed(self) -> set[str]:
        found: set[str] = set()
        try:
            root = ET.fromstring(self._get(f"{self.publication_url}/feed").text)
        except Exception as exc:
            print(f"      feed unavailable ({exc})")
            return found
        for el in root.iter():
            name = el.tag.rsplit("}", 1)[-1].lower()
            if name == "link":
                href = el.attrib.get("href") or (el.text or "")
                if href and self._is_post_url(href):
                    found.add(self.normalize_url(href))
        return found

    def _discover_from_archive_page(self) -> set[str]:
        found: set[str] = set()
        try:
            soup = BeautifulSoup(self._get(f"{self.publication_url}/archive").text, "html.parser")
        except Exception as exc:
            print(f"      archive page unavailable ({exc})")
            return found
        for a in soup.find_all("a", href=True):
            href = urljoin(self.publication_url + "/", a["href"])
            if self._is_post_url(href):
                found.add(self.normalize_url(href))
        return found

    def discover_post_urls(self) -> list[str]:
        # Older project configs may still point at /sitemap. Substack's canonical
        # machine-readable endpoint is /sitemap.xml; try both so a malformed legacy
        # endpoint cannot silently collapse archive discovery to the feed's ~20 posts.
        sitemap_candidates: list[str] = []
        for candidate in (self.sitemap_url, f"{self.publication_url}/sitemap.xml"):
            normalized = self.normalize_url(candidate)
            if normalized not in sitemap_candidates:
                sitemap_candidates.append(normalized)

        urls: set[str] = set()
        for candidate in sitemap_candidates:
            urls |= self._discover_from_sitemap(candidate)
        urls |= self._discover_from_feed()
        urls |= self._discover_from_archive_page()
        return sorted(urls)

    @staticmethod
    def _best_content_root(soup: BeautifulSoup) -> Tag:
        candidates: list[Tag] = []
        for selector in CONTENT_SELECTORS:
            candidates.extend([x for x in soup.select(selector) if isinstance(x, Tag)])
        if not candidates:
            body = soup.body
            if isinstance(body, Tag):
                return body
            raise ValueError("No article body found")
        # The largest readable candidate is usually the complete post body.
        return max(candidates, key=lambda x: len(x.get_text(" ", strip=True)))

    def extract_snapshot(self, html: str, requested_url: str) -> ArticleSnapshot:
        soup = BeautifulSoup(html, "html.parser")
        canonical = soup.find("link", rel="canonical")
        canonical_url = self.normalize_url(
            canonical.get("href") if canonical and canonical.get("href") else requested_url
        )

        title = ""
        og_title = soup.find("meta", attrs={"property": "og:title"})
        if og_title and og_title.get("content"):
            title = og_title["content"].strip()
        if not title:
            h1 = soup.find("h1")
            title = h1.get_text(" ", strip=True) if h1 else "Untitled White Rabbit article"

        published_date = None
        for attrs in (
            {"property": "article:published_time"},
            {"name": "article:published_time"},
            {"itemprop": "datePublished"},
        ):
            meta = soup.find("meta", attrs=attrs)
            if meta and meta.get("content"):
                published_date = meta["content"].strip()
                break

        author = None
        for attrs in ({"name": "author"}, {"property": "article:author"}):
            meta = soup.find("meta", attrs=attrs)
            if meta and meta.get("content"):
                author = meta["content"].strip()
                break

        root = self._best_content_root(soup)
        for bad in root.select("script, style, noscript, form, button, svg"):
            bad.decompose()

        links: list[dict] = []
        seen: set[tuple[str, str]] = set()
        publication_host = urlsplit(self.publication_url).netloc.lower()
        for a in root.find_all("a", href=True):
            anchor = a.get_text(" ", strip=True)
            href = urljoin(canonical_url, a["href"])
            if not anchor or not href.startswith(("http://", "https://")):
                continue
            href = self.normalize_url(href)
            key = (anchor, href)
            if key in seen:
                continue
            seen.add(key)
            parsed = urlsplit(href)
            link_type = "internal" if parsed.netloc.lower() == publication_host and "/p/" in parsed.path else "external"
            links.append({"anchor": anchor, "url": href, "type": link_type})

        markdown = to_markdown(str(root), heading_style="ATX", bullets="-")
        markdown = re.sub(r"\n{3,}", "\n\n", markdown).strip()
        if len(markdown) < 100:
            raise ValueError("Extracted article text is unexpectedly short")

        page_text = soup.get_text(" ", strip=True).lower()
        content_status = "preview_only" if any(marker in page_text for marker in PAYWALL_MARKERS) else "full"
        slug_match = re.search(r"/p/([^/?#]+)", canonical_url)
        slug = slug_match.group(1) if slug_match else re.sub(r"[^a-z0-9]+", "-", title.lower()).strip("-")[:90]

        return ArticleSnapshot(
            title=title,
            slug=slug,
            canonical_url=canonical_url,
            published_date=published_date,
            author=author,
            markdown=markdown,
            links=links,
            content_status=content_status,
        )

    @staticmethod
    def _year(snapshot: ArticleSnapshot) -> str:
        if snapshot.published_date:
            m = re.match(r"(\d{4})", snapshot.published_date)
            if m:
                return m.group(1)
        return str(datetime.now(timezone.utc).year)

    def store_snapshot(self, snapshot: ArticleSnapshot) -> tuple[str, bool, bool]:
        article_dir = self.articles_root / self._year(snapshot) / snapshot.slug
        article_dir.mkdir(parents=True, exist_ok=True)
        existing = self.db.get_by_url(snapshot.canonical_url)
        changed = existing is None or existing.content_hash != snapshot.content_hash or existing.content_status != snapshot.content_status

        if changed or not (article_dir / "article.md").exists():
            (article_dir / "article.md").write_text(snapshot.markdown + "\n", encoding="utf-8")
            (article_dir / "links.json").write_text(
                json.dumps(snapshot.links, indent=2, ensure_ascii=False) + "\n", encoding="utf-8"
            )

        article, created, db_changed = self.db.upsert_article(
            title=snapshot.title,
            slug=snapshot.slug,
            canonical_url=snapshot.canonical_url,
            published_date=snapshot.published_date,
            author=snapshot.author,
            content_hash=snapshot.content_hash,
            content_status=snapshot.content_status,
            local_dir=str(article_dir.resolve()),
            word_count=snapshot.word_count,
        )
        self.db.replace_links(snapshot.canonical_url, snapshot.links)
        metadata = {
            "article_id": article.wr_id,
            "title": snapshot.title,
            "slug": snapshot.slug,
            "canonical_url": snapshot.canonical_url,
            "published_date": snapshot.published_date,
            "author": snapshot.author,
            "content_hash": f"sha256:{snapshot.content_hash}",
            "content_status": snapshot.content_status,
            "word_count": snapshot.word_count,
            "indexed": True,
        }
        (article_dir / "metadata.json").write_text(
            json.dumps(metadata, indent=2, ensure_ascii=False) + "\n", encoding="utf-8"
        )
        return article.wr_id, created, (changed or db_changed)

    def sync(self, *, refresh_existing: bool = False) -> dict:
        urls = self.discover_post_urls()
        report = {
            "publication_url": self.publication_url,
            "discovered": len(urls),
            "new": [],
            "updated": [],
            "unchanged": [],
            "skipped_existing": [],
            "preview_only": [],
            "errors": [],
            "started_at": datetime.now(timezone.utc).isoformat(),
        }
        print(f"      discovered {len(urls)} published post URLs")
        for index, url in enumerate(urls, start=1):
            existing = self.db.get_by_url(url)
            if existing and not refresh_existing:
                self.db.mark_seen(url)
                report["skipped_existing"].append({"id": existing.wr_id, "title": existing.title, "url": existing.canonical_url})
                continue
            try:
                print(f"      [{index}/{len(urls)}] {url}")
                snapshot = self.extract_snapshot(self._get(url).text, url)
                wr_id, created, changed = self.store_snapshot(snapshot)
                if snapshot.content_status == "preview_only":
                    report["preview_only"].append({"id": wr_id, "title": snapshot.title, "url": snapshot.canonical_url})
                if created:
                    report["new"].append({"id": wr_id, "title": snapshot.title, "url": snapshot.canonical_url})
                elif changed:
                    report["updated"].append({"id": wr_id, "title": snapshot.title, "url": snapshot.canonical_url})
                else:
                    report["unchanged"].append({"id": wr_id, "title": snapshot.title, "url": snapshot.canonical_url})
            except Exception as exc:
                if existing:
                    self.db.mark_seen(url)
                report["errors"].append({"url": url, "error": str(exc)})
                print(f"        WARNING: {exc}")

        report["finished_at"] = datetime.now(timezone.utc).isoformat()
        report["database"] = self.db.status()
        (self.sync_root / "sync_report.json").write_text(
            json.dumps(report, indent=2, ensure_ascii=False) + "\n", encoding="utf-8"
        )
        return report

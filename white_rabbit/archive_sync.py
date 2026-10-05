from __future__ import annotations

import hashlib
import csv
import html as html_lib
import io
import json
import random
import re
import time
import xml.etree.ElementTree as ET
import zipfile
from collections import Counter
from dataclasses import dataclass
from datetime import datetime, timezone
from email.utils import parsedate_to_datetime
from pathlib import Path
from urllib.parse import urljoin, urlsplit, urlunsplit

import httpx
from bs4 import BeautifulSoup, Tag
from markdownify import markdownify as to_markdown

from .archive_db import ArchiveDB


PREVIEW_BOUNDARY_PHRASES = (
    "subscribe to continue reading",
    "this post is for paid subscribers",
    "this post is for subscribers",
    "continue reading this post for free in the substack app",
)

CONTENT_SELECTORS = (
    "div.body.markup",
    "div.post-content",
    "div[class*='available-content']",
    "div[class*='body markup']",
    "div.available-content",
    "article",
)

SUBSTACK_UI_SELECTORS = (
    "script", "style", "noscript", "form", "button", "svg",
    "div.digestPostEmbed-flwiST",
    "div[class*='digestPostEmbed']",
    "div.subscription-widget-wrap",
    "div[class*='subscription-widget']",
    ".button-wrapper",
    "[data-component-name='SubscribeWidgetToDOM']",
    "[data-component-name='CommentPrompt']",
    "[data-component-name='Recommendations']",
    "[data-component-name='PostFooter']",
)

ACCESS_LEVELS = {
    "FULL_PUBLIC", "FULL_AUTHOR_EXPORT", "PARTIAL_PREVIEW", "TITLE_ONLY", "FETCH_FAILED",
}


def source_priority(*, source_origin: str, access_level: str) -> int:
    """Return the archive replacement priority for one captured body."""
    if access_level == "FULL_AUTHOR_EXPORT":
        return 500
    if source_origin == "verified_local_author_copy":
        return 400
    return {
        "FULL_PUBLIC": 300,
        "PARTIAL_PREVIEW": 200,
        "TITLE_ONLY": 100,
        "FETCH_FAILED": 0,
    }.get(access_level, 0)


def detect_preview_boundary(markdown: str) -> str | None:
    """Return the Substack continuation boundary found near the captured text's end.

    Ordinary subscription invitations are not preview boundaries. The detector uses
    explicit continuation language and limits matching to the tail of the captured
    article, where Substack inserts its paywall/continuation block.
    """
    normalized = re.sub(r"\s+", " ", markdown).strip().lower()
    tail = normalized[-2500:]
    for phrase in PREVIEW_BOUNDARY_PHRASES:
        if phrase in tail:
            return phrase
    if (
        "purchase a paid subscription" in tail
        and re.search(r"continue reading(?: this post)?", tail)
    ):
        return "purchase a paid subscription after continue-reading boundary"
    if (
        "upgrade to paid" in tail
        and re.search(r"(?:continue|unlock|read the rest)", tail)
    ):
        return "upgrade to paid continuation boundary"
    return None


def reconcile_local_preview_statuses(
    archive_root: Path,
    db_path: Path,
    *,
    report_path: Path | None = None,
    sync_report_path: Path | None = None,
) -> dict:
    """Reclassify captured archive previews without changing captured article text."""
    archive_root = Path(archive_root)
    db = ArchiveDB(db_path)
    records: list[dict] = []
    changed = 0
    try:
        for metadata_path in sorted(archive_root.glob("articles/*/*/metadata.json")):
            metadata = json.loads(metadata_path.read_text(encoding="utf-8"))
            article_path = metadata_path.with_name("article.md")
            if not article_path.is_file():
                continue
            markdown = article_path.read_text(encoding="utf-8")
            boundary = detect_preview_boundary(markdown)
            if not boundary:
                continue
            old_status = str(metadata.get("content_status", "full"))
            new_status = "preview_only"
            if old_status != new_status:
                metadata["content_status"] = new_status
                metadata_path.write_text(
                    json.dumps(metadata, indent=2, ensure_ascii=False) + "\n",
                    encoding="utf-8",
                )
                changed += 1
            article = db.get_by_url(str(metadata["canonical_url"]))
            if article is None:
                raise KeyError(f"Archive metadata missing from database: {metadata_path}")
            if article.content_status != new_status:
                db.update_content_status(str(metadata["canonical_url"]), new_status)
            records.append({
                "article_id": metadata.get("article_id"),
                "slug": metadata.get("slug"),
                "old_status": old_status,
                "new_status": new_status,
                "reason": "Captured article terminates at an explicit Substack continuation boundary.",
                "detected_boundary_phrase": boundary,
                "word_count": metadata.get("word_count"),
            })

        report = {
            "scanned_metadata_files": len(list(archive_root.glob("articles/*/*/metadata.json"))),
            "boundary_records": len(records),
            "reclassified_records": changed,
            "records": records,
            "database": db.status(),
        }
        if report_path is not None:
            report_path.parent.mkdir(parents=True, exist_ok=True)
            report_path.write_text(
                json.dumps(report, indent=2, ensure_ascii=False) + "\n",
                encoding="utf-8",
            )
        if sync_report_path is not None and sync_report_path.is_file():
            sync_report = json.loads(sync_report_path.read_text(encoding="utf-8"))
            new_by_id = {
                str(row.get("id")): row for row in sync_report.get("new", [])
            }
            sync_report["preview_only"] = [
                {
                    "id": row["article_id"],
                    "title": new_by_id[str(row["article_id"])]["title"],
                    "url": new_by_id[str(row["article_id"])]["url"],
                }
                for row in records if str(row["article_id"]) in new_by_id
            ]
            sync_report["database"] = db.status()
            sync_report_path.write_text(
                json.dumps(sync_report, indent=2, ensure_ascii=False) + "\n",
                encoding="utf-8",
            )
        return report
    finally:
        db.close()


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
    updated_date: str | None = None
    series: str | None = None
    tags: tuple[str, ...] = ()
    access_level: str = "FULL_PUBLIC"
    discovery_sources: tuple[str, ...] = ()
    http_status: int | None = None
    source_origin: str = "public_web"
    subtitle: str | None = None
    export_post_id: str | None = None
    publication_status: str = "published"
    audience: str | None = None
    source_reference: str | None = None

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
        self.discovery_sources: dict[str, set[str]] = {}
        self.sitemap_urls_reached: set[str] = set()
        self.sitemap_urls_failed: dict[str, str] = {}

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
            self.sitemap_urls_reached.add(url)
        except Exception as exc:
            self.sitemap_urls_failed[url] = str(exc)
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
                self.sitemap_urls_failed[url] = f"HTTP {response.status_code}; XML parse failed: {exc}"
                print(f"      sitemap unavailable: {url} ({exc})")
                return set()

        found: set[str] = set()
        if is_index:
            for child in locs:
                found |= self._discover_from_sitemap(child, seen_maps)
        else:
            for loc in locs:
                if self._is_post_url(loc):
                    normalized = self.normalize_url(loc)
                    found.add(normalized)
                    self.discovery_sources.setdefault(normalized, set()).add(f"sitemap:{url}")
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
                    normalized = self.normalize_url(href)
                    found.add(normalized)
                    self.discovery_sources.setdefault(normalized, set()).add("feed")
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
                normalized = self.normalize_url(href)
                found.add(normalized)
                self.discovery_sources.setdefault(normalized, set()).add("archive_page")
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

    def probe_discovery(self) -> dict:
        """Run a read-only discovery smoke test and persist endpoint diagnostics."""
        urls = self.discover_post_urls()
        report = {
            "publication_url": self.publication_url,
            "discovered": len(urls),
            "sitemap_urls_reached": sorted(self.sitemap_urls_reached),
            "sitemap_urls_failed": self.sitemap_urls_failed,
            "discovery_source_counts": dict(sorted(Counter(
                source for sources in self.discovery_sources.values() for source in sources
            ).items())),
        }
        path = self.sync_root / "discovery_probe.json"
        path.write_text(json.dumps(report, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
        return report

    @staticmethod
    def _best_content_root(soup: BeautifulSoup) -> Tag:
        # Prefer the first purpose-built post-body selector. Choosing the globally
        # largest node tends to select the enclosing <article>, which includes byline,
        # recommendations, share controls and other Substack UI.
        for selector in CONTENT_SELECTORS:
            candidates = [x for x in soup.select(selector) if isinstance(x, Tag)]
            if candidates:
                return max(candidates, key=lambda x: len(x.get_text(" ", strip=True)))
        body = soup.body
        if isinstance(body, Tag):
            return body
        raise ValueError("No article body found")

    @staticmethod
    def _article_json_ld(soup: BeautifulSoup) -> dict:
        for script in soup.find_all("script", attrs={"type": "application/ld+json"}):
            try:
                data = json.loads(script.string or script.get_text() or "{}")
            except (TypeError, json.JSONDecodeError):
                continue
            candidates = data if isinstance(data, list) else [data]
            for item in candidates:
                if isinstance(item, dict) and str(item.get("@type", "")).lower() in {
                    "article", "newsarticle", "blogposting",
                }:
                    return item
        return {}

    @staticmethod
    def _series_name(soup: BeautifulSoup) -> str | None:
        for anchor in soup.find_all("a", href=True):
            if "/s/" not in str(anchor.get("href", "")):
                continue
            text = anchor.get_text(" ", strip=True)
            if text and len(text) <= 120:
                return text
        return None

    def extract_snapshot(self, html: str, requested_url: str) -> ArticleSnapshot:
        soup = BeautifulSoup(html, "html.parser")
        structured = self._article_json_ld(soup)
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

        published_date = str(structured.get("datePublished") or "").strip() or None
        for attrs in (
            {"property": "article:published_time"},
            {"name": "article:published_time"},
            {"itemprop": "datePublished"},
        ):
            meta = soup.find("meta", attrs=attrs)
            if not published_date and meta and meta.get("content"):
                published_date = meta["content"].strip()
                break

        updated_date = None
        modified = soup.find("meta", attrs={"property": "article:modified_time"})
        if modified and modified.get("content"):
            updated_date = modified["content"].strip()
        if not updated_date:
            updated_date = str(structured.get("dateModified") or "").strip() or None

        author = None
        for attrs in ({"name": "author"}, {"property": "article:author"}):
            meta = soup.find("meta", attrs=attrs)
            if meta and meta.get("content"):
                author = meta["content"].strip()
                break

        root = self._best_content_root(soup)
        for bad in root.select(", ".join(SUBSTACK_UI_SELECTORS)):
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
        boundary = detect_preview_boundary(markdown)
        accessible = structured.get("isAccessibleForFree")
        body_word_count = len(re.findall(r"\b\w+\b", markdown))
        if boundary or accessible is False:
            access_level = "PARTIAL_PREVIEW"
        elif body_word_count < 20:
            access_level = "TITLE_ONLY"
        else:
            access_level = "FULL_PUBLIC"
        content_status = "preview_only" if access_level in {"PARTIAL_PREVIEW", "TITLE_ONLY"} else "full"
        markdown = f"# {title}\n\n{markdown}".strip()
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
            updated_date=updated_date,
            series=self._series_name(soup),
            tags=(),
            access_level=access_level,
        )

    def refresh_url(self, url: str) -> dict:
        """Refresh one canonical post and reconcile it into the latest sync report."""
        url = self.normalize_url(url)
        if not self._is_post_url(url):
            raise ValueError("Expected a canonical Substack /p/ post URL.")
        response = self._get(url)
        snapshot = self.extract_snapshot(response.text, url)
        snapshot = ArticleSnapshot(**{
            **snapshot.__dict__,
            "discovery_sources": tuple(sorted(self.discovery_sources.get(url, ()))) or ("targeted_refresh",),
            "http_status": response.status_code,
        })
        wr_id, created, changed = self.store_snapshot(snapshot)
        result = {
            "id": wr_id,
            "title": snapshot.title,
            "url": snapshot.canonical_url,
            "created": created,
            "changed": changed,
            "access_level": snapshot.access_level,
            "http_status": response.status_code,
        }
        report_path = self.sync_root / "sync_report.json"
        if report_path.is_file():
            report = json.loads(report_path.read_text(encoding="utf-8"))
            report["errors"] = [row for row in report.get("errors", []) if row.get("url") != url]
            report.setdefault("targeted_refreshes", []).append(result)
            report["database"] = self.db.status()
            report_path.write_text(json.dumps(report, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
        return result

    @staticmethod
    def _year(snapshot: ArticleSnapshot) -> str:
        if snapshot.published_date:
            m = re.match(r"(\d{4})", snapshot.published_date)
            if m:
                return m.group(1)
        return str(datetime.now(timezone.utc).year)

    def store_snapshot(self, snapshot: ArticleSnapshot) -> tuple[str, bool, bool]:
        if snapshot.access_level not in ACCESS_LEVELS:
            raise ValueError(f"Unsupported archive access level: {snapshot.access_level}")
        article_dir = self.articles_root / self._year(snapshot) / snapshot.slug
        existing = self.db.get_by_url(snapshot.canonical_url)
        existing_metadata: dict = {}
        if existing:
            old_dir = Path(existing.local_dir)
            old_metadata_path = old_dir / "metadata.json"
            if old_metadata_path.is_file():
                try:
                    existing_metadata = json.loads(old_metadata_path.read_text(encoding="utf-8"))
                except (OSError, json.JSONDecodeError):
                    existing_metadata = {}

            # The author export is the highest-fidelity publication source. Public
            # crawls remain useful as observations, but may never replace that body
            # with a paywall preview, title shell, failed response, or divergent
            # public rendering. Preserve the author body and record what was seen.
            if (
                existing_metadata.get("access_level") == "FULL_AUTHOR_EXPORT"
                and snapshot.source_origin == "public_web"
            ):
                existing_metadata["latest_public_observation"] = {
                    "observed_at": datetime.now(timezone.utc).isoformat(),
                    "access_level": snapshot.access_level,
                    "content_hash": f"sha256:{snapshot.content_hash}",
                    "http_status": snapshot.http_status,
                    "updated_date": snapshot.updated_date,
                    "discovery_sources": list(snapshot.discovery_sources),
                    "body_differs_from_author_export": existing.content_hash != snapshot.content_hash,
                }
                existing_metadata["source_precedence"] = (
                    "author_export retained over subsequent public-web observation"
                )
                old_metadata_path.write_text(
                    json.dumps(existing_metadata, indent=2, ensure_ascii=False) + "\n",
                    encoding="utf-8",
                )
                self.db.mark_seen(snapshot.canonical_url)
                return existing.wr_id, False, False

            existing_priority = source_priority(
                source_origin=str(existing_metadata.get("source_origin") or "public_web"),
                access_level=str(existing_metadata.get("access_level") or (
                    "PARTIAL_PREVIEW" if existing.content_status == "preview_only" else "FULL_PUBLIC"
                )),
            )
            incoming_priority = source_priority(
                source_origin=snapshot.source_origin,
                access_level=snapshot.access_level,
            )
            if existing_metadata and incoming_priority < existing_priority:
                existing_metadata["latest_lower_priority_observation"] = {
                    "observed_at": datetime.now(timezone.utc).isoformat(),
                    "source_origin": snapshot.source_origin,
                    "access_level": snapshot.access_level,
                    "content_hash": f"sha256:{snapshot.content_hash}",
                    "http_status": snapshot.http_status,
                    "body_differs_from_retained_source": existing.content_hash != snapshot.content_hash,
                }
                existing_metadata["source_precedence"] = (
                    "higher-priority stored source retained over lower-priority observation"
                )
                old_metadata_path.write_text(
                    json.dumps(existing_metadata, indent=2, ensure_ascii=False) + "\n",
                    encoding="utf-8",
                )
                self.db.mark_seen(snapshot.canonical_url)
                return existing.wr_id, False, False

            archive_root = self.articles_root.resolve()
            try:
                safe_old = old_dir.resolve().is_relative_to(archive_root)
            except OSError:
                safe_old = False
            if safe_old and old_dir != article_dir and old_dir.is_dir() and not article_dir.exists():
                article_dir.parent.mkdir(parents=True, exist_ok=True)
                old_dir.replace(article_dir)
        article_dir.mkdir(parents=True, exist_ok=True)
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
        from .archive_voice import extract_authored_paragraphs
        authored_paragraphs, _ = extract_authored_paragraphs(snapshot.markdown)
        metadata = {
            "article_id": article.wr_id,
            "title": snapshot.title,
            "slug": snapshot.slug,
            "canonical_url": snapshot.canonical_url,
            "published_date": snapshot.published_date,
            "updated_date": snapshot.updated_date,
            "author": snapshot.author,
            "series": snapshot.series,
            "tags": list(snapshot.tags),
            "content_hash": f"sha256:{snapshot.content_hash}",
            "content_status": snapshot.content_status,
            "access_level": snapshot.access_level,
            "source_origin": snapshot.source_origin,
            "discovery_sources": list(snapshot.discovery_sources),
            "http_status": snapshot.http_status,
            "subtitle": snapshot.subtitle,
            "export_post_id": snapshot.export_post_id,
            "publication_status": snapshot.publication_status,
            "audience": snapshot.audience,
            "source_reference": snapshot.source_reference,
            "source_precedence": (
                "author_export is authoritative for this published body"
                if snapshot.source_origin == "author_export"
                else "verified local author copy"
                if snapshot.source_origin == "verified_local_author_copy"
                else "public web capture"
            ),
            "word_count": snapshot.word_count,
            "author_paragraph_count": len(authored_paragraphs),
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
            "sitemap_urls_reached": [],
            "sitemap_urls_failed": {},
            "missing_from_latest_discovery": [],
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
                response = self._get(url)
                snapshot = self.extract_snapshot(response.text, url)
                snapshot = ArticleSnapshot(
                    **{
                        **snapshot.__dict__,
                        "discovery_sources": tuple(sorted(self.discovery_sources.get(url, ()))),
                        "http_status": response.status_code,
                    }
                )
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
                status = getattr(getattr(exc, "response", None), "status_code", None)
                report["errors"].append({
                    "url": url,
                    "error": str(exc),
                    "http_status": status,
                    "access_level": "FETCH_FAILED",
                    "discovery_sources": sorted(self.discovery_sources.get(url, ())),
                })
                print(f"        WARNING: {exc}")

        discovered_set = set(urls)
        if self.sitemap_urls_reached:
            report["missing_from_latest_discovery"] = [
                {"id": article.wr_id, "title": article.title, "url": article.canonical_url}
                for article in self.db.list_articles()
                if article.canonical_url not in discovered_set
            ]
        report["sitemap_urls_reached"] = sorted(self.sitemap_urls_reached)
        report["sitemap_urls_failed"] = self.sitemap_urls_failed
        report["finished_at"] = datetime.now(timezone.utc).isoformat()
        report["database"] = self.db.status()
        (self.sync_root / "sync_report.json").write_text(
            json.dumps(report, indent=2, ensure_ascii=False) + "\n", encoding="utf-8"
        )
        return report

    @staticmethod
    def _export_identity(row: dict[str, str]) -> tuple[str, str, str]:
        raw_id = str(row.get("post_id") or row.get("id") or "").strip()
        explicit_slug = str(row.get("slug") or row.get("post_slug") or "").strip()
        match = re.fullmatch(r"(\d+)\.(.+)", raw_id)
        if match:
            return match.group(1), explicit_slug or match.group(2), raw_id
        return raw_id, explicit_slug, raw_id

    @staticmethod
    def _published_export_row(row: dict[str, str]) -> bool:
        if "is_published" not in row and "published" not in row:
            # Older owner-export layouts contained only published posts and did not
            # include an explicit publication flag.
            return True
        value = str(row.get("is_published") or row.get("published") or "").strip().casefold()
        return value in {"true", "1", "yes", "published"}

    def import_author_export(self, export_path: Path) -> dict:
        """Import post bodies from an owner export without touching subscriber data.

        Accept a Substack ZIP, posts.csv file, or extracted directory. For ZIPs the
        importer opens only posts.csv and the matching posts/*.html files. Subscriber,
        email-list, delivery, open, payment, and pledge data are never read or copied.
        """
        export_path = Path(export_path)
        archive: zipfile.ZipFile | None = None
        csv_path: Path | None = None
        rows: list[dict[str, str]]
        source_name: str
        private_entries_ignored = 0
        analytics_entries_ignored = 0

        if export_path.suffix.casefold() == ".zip":
            if not export_path.is_file():
                raise ValueError(f"Substack export ZIP not found: {export_path}")
            archive = zipfile.ZipFile(export_path, "r")
            names = set(archive.namelist())
            if "posts.csv" not in names:
                archive.close()
                raise ValueError("Substack export ZIP does not contain posts.csv at its root.")
            private_entries_ignored = sum(
                1 for name in names
                if any(token in name.casefold() for token in ("email_list", "subscriber", "payment", "pledge"))
            )
            analytics_entries_ignored = sum(
                1 for name in names if name.casefold().endswith((".opens.csv", ".delivers.csv"))
            )
            with archive.open("posts.csv", "r") as raw:
                with io.TextIOWrapper(raw, encoding="utf-8-sig", newline="") as handle:
                    rows = list(csv.DictReader(handle))
            source_name = export_path.name

            def read_body(row: dict[str, str], slug: str, raw_id: str, numeric_id: str) -> tuple[str, str | None]:
                candidates = [
                    f"posts/{raw_id}.html",
                    f"posts/{numeric_id}.{slug}.html" if numeric_id and slug else "",
                    f"posts/{raw_id}.md",
                ]
                for name in candidates:
                    if name and name in names:
                        return archive.read(name).decode("utf-8-sig"), name
                return "", None
        else:
            csv_path = export_path / "posts.csv" if export_path.is_dir() else export_path
            if csv_path.name.lower() != "posts.csv" or not csv_path.is_file():
                raise ValueError("Expected a Substack export ZIP, extracted directory, or posts.csv file.")
            with csv_path.open("r", encoding="utf-8-sig", newline="") as handle:
                rows = list(csv.DictReader(handle))
            source_name = csv_path.parent.name

            def read_body(row: dict[str, str], slug: str, raw_id: str, numeric_id: str) -> tuple[str, str | None]:
                candidates = [
                    csv_path.parent / "posts" / f"{raw_id}.html",
                    csv_path.parent / "posts" / f"{numeric_id}.{slug}.html",
                    csv_path.parent / "posts" / f"{raw_id}.md",
                    csv_path.parent / "posts" / f"{slug}.html",
                    csv_path.parent / "posts" / f"{slug}.md",
                ]
                source = next((path for path in candidates if path.is_file()), None)
                return (source.read_text(encoding="utf-8-sig"), source.as_posix()) if source else ("", None)

        imported: list[dict] = []
        skipped: list[dict] = []
        excluded_unpublished: list[dict] = []
        try:
            for row in rows:
                numeric_id, slug, raw_id = self._export_identity(row)
                title = str(row.get("title") or "").strip()
                if not self._published_export_row(row):
                    excluded_unpublished.append({
                        "export_post_id": raw_id,
                        "title": title,
                        "reason": "is_published is not true",
                    })
                    continue
                if not slug or not title:
                    skipped.append({"export_post_id": raw_id, "title": title, "reason": "missing title or slug"})
                    continue
                body = str(row.get("body_html") or row.get("body") or row.get("content") or "").strip()
                source_reference = "posts.csv:inline-body" if body else None
                if not body:
                    body, source_reference = read_body(row, slug, raw_id, numeric_id)
                if not body:
                    skipped.append({
                        "export_post_id": raw_id, "title": title, "slug": slug,
                        "reason": "no exported post body",
                    })
                    continue
                canonical_url = self.normalize_url(
                    str(row.get("canonical_url") or row.get("post_url") or f"{self.publication_url}/p/{slug}")
                )
                existing = self.db.get_by_url(canonical_url)
                previous_access = None
                if existing:
                    existing_meta_path = Path(existing.local_dir) / "metadata.json"
                    if existing_meta_path.is_file():
                        try:
                            previous_access = json.loads(existing_meta_path.read_text(encoding="utf-8")).get("access_level")
                        except (OSError, json.JSONDecodeError):
                            previous_access = None
                if "<" in body and ">" in body:
                    wrapper = (
                        "<html><head>"
                        f"<link rel='canonical' href='{html_lib.escape(canonical_url, quote=True)}'>"
                        f"<meta property='og:title' content='{html_lib.escape(title, quote=True)}'>"
                        "</head><body><div class='body markup'>"
                        f"{body}</div></body></html>"
                    )
                    snapshot = self.extract_snapshot(wrapper, canonical_url)
                    markdown = snapshot.markdown
                    links = snapshot.links
                    exported_access = "FULL_AUTHOR_EXPORT" if snapshot.word_count >= 20 else "TITLE_ONLY"
                else:
                    markdown = body if body.lstrip().startswith("# ") else f"# {title}\n\n{body}"
                    links = []
                    exported_access = (
                        "FULL_AUTHOR_EXPORT"
                        if len(re.findall(r"\b\w+\b", markdown)) >= 20
                        else "TITLE_ONLY"
                    )
                snapshot = ArticleSnapshot(
                    title=title,
                    slug=slug,
                    canonical_url=canonical_url,
                    published_date=str(row.get("post_date") or row.get("published_at") or "").strip() or None,
                    author=str(row.get("author") or "The White Rabbit Report").strip(),
                    markdown=markdown.strip(),
                    links=links,
                    content_status="full" if exported_access == "FULL_AUTHOR_EXPORT" else "preview_only",
                    updated_date=str(row.get("updated_at") or "").strip() or None,
                    access_level=exported_access,
                    discovery_sources=("author_export:posts.csv",),
                    source_origin="author_export",
                    subtitle=str(row.get("subtitle") or "").strip() or None,
                    export_post_id=raw_id,
                    publication_status="published",
                    audience=str(row.get("audience") or "").strip() or None,
                    source_reference=source_reference,
                )
                wr_id, created, changed = self.store_snapshot(snapshot)
                imported.append({
                    "id": wr_id,
                    "export_post_id": raw_id,
                    "title": title,
                    "url": canonical_url,
                    "created": created,
                    "changed": changed,
                    "previous_access_level": previous_access,
                    "access_level": exported_access,
                })
        finally:
            if archive is not None:
                archive.close()

        report = {
            "source_archive": source_name,
            "manifest_rows": len(rows),
            "published_rows": sum(1 for row in rows if self._published_export_row(row)),
            "unpublished_rows_excluded": len(excluded_unpublished),
            "private_entries_ignored": private_entries_ignored,
            "analytics_entries_ignored": analytics_entries_ignored,
            "imported": imported,
            "skipped": skipped,
            "excluded_unpublished": excluded_unpublished,
            "summary": {
                "matched_existing": sum(1 for item in imported if not item["created"]),
                "new_published": sum(1 for item in imported if item["created"]),
                "repaired_partial_previews": sum(
                    1 for item in imported
                    if item["previous_access_level"] == "PARTIAL_PREVIEW"
                    and item["access_level"] == "FULL_AUTHOR_EXPORT"
                ),
                "repaired_title_only": sum(
                    1 for item in imported
                    if item["previous_access_level"] == "TITLE_ONLY"
                    and item["access_level"] == "FULL_AUTHOR_EXPORT"
                ),
                "full_author_export": sum(
                    1 for item in imported if item["access_level"] == "FULL_AUTHOR_EXPORT"
                ),
                "title_only_after_export": sum(
                    1 for item in imported if item["access_level"] == "TITLE_ONLY"
                ),
            },
        }
        report_path = self.sync_root / "author_export_import_report.json"
        report_path.write_text(json.dumps(report, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
        return report

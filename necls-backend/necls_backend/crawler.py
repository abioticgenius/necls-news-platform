"""Robust HTML/article extraction (class‑based wrapper around NewsPlease)."""
from __future__ import annotations

import base64
import gzip, hashlib, json, re, xml.etree.ElementTree as ET
import uuid
from datetime import datetime, timezone
import time
from pathlib import Path
from typing import Any, Dict, List, Optional, Sequence, Set, Tuple
from urllib.parse import urljoin, urlparse
from types import SimpleNamespace
import feedparser, requests, schedule, tls_client
from bs4 import BeautifulSoup
from dateutil import parser as dateparser
from newsplease import NewsPlease
from .config import settings
from .db import engine, articles, pg_insert
from .constants import REUTERS_HEADERS

# ---------------------------------------------------------------------------
# Utility helpers (kept outside class so they can be unit‑tested directly)

_ILLEGAL_XML_RE = re.compile(r"[\x00-\x08\x0B\x0C\x0E-\x1F]")

def strip_illegal(b: bytes) -> str:
    return _ILLEGAL_XML_RE.sub('', b.decode('utf-8', 'replace'))

def clean_html(b: bytes) -> str:
    return str(BeautifulSoup(strip_illegal(b), "html.parser"))

def jsonify(obj: Any):
    if isinstance(obj, datetime):
        return obj.isoformat()
    if isinstance(obj, dict):
        return {k: jsonify(v) for k, v in obj.items()}
    if isinstance(obj, (list, tuple)):
        return [jsonify(v) for v in obj]
    return obj

def is_valid_image_url(image_url: str | None) -> bool:
    """
    Validate if an image URL is actually an image URL based on file extension.
    
    Args:
        image_url: The URL to validate
        
    Returns:
        True if the URL appears to be a valid image URL, False otherwise
    """
    if not image_url:
        return False
    
    # Convert to lowercase for case-insensitive matching
    url_lower = image_url.lower()
    
    # Remove query parameters and fragments for extension checking
    url_clean = url_lower.split('?')[0].split('#')[0]
    
    # Check if URL ends with valid image extensions
    valid_extensions = ['jpg', 'jpeg', 'png', 'gif', 'webp']
    return any(url_clean.endswith(f'.{ext}') for ext in valid_extensions)


def extract_publish_date_from_html(html: str):
    """Extract publish date from HTML using meta tags and JSON-LD (BeautifulSoup only)."""
    try:
        soup = BeautifulSoup(html, "html.parser")
        meta_props = [
            ("property", "article:published_time"),
            ("name", "pubdate"),
            ("name", "publish-date"),
            ("name", "date"),
            ("itemprop", "datePublished"),
        ]
        for attr, value in meta_props:
            tag = soup.find("meta", attrs={attr: value})
            if tag and tag.get("content"):
                return dateparser.parse(tag["content"], fuzzy=True)
        for script in soup.find_all("script", type="application/ld+json"):
            data = script.string
            if not data:
                continue
            match = re.search(r'"datePublished"\s*:\s*"([^"]+)"', data)
            if match:
                return dateparser.parse(match.group(1), fuzzy=True)
    except Exception as e:
        print(f"[ERROR] Failed to parse publish date from HTML: {e}")
    return None


def _fetch_espn_html(url: str, timeout_goto: int = 45000) -> Tuple[Optional[bytes], Optional[Dict[str, Any]]]:
    """
    Fetch an ESPN article page with Playwright, waiting for ESPN-specific content.
    Returns (html_bytes, metadata_dict) or (None, None) on failure.
    """
    try:
        from playwright.sync_api import sync_playwright
    except ImportError:
        return None, None

    metadata: Dict[str, Any] = {}
    try:
        with sync_playwright() as p:
            browser = p.chromium.launch(headless=True)
            try:
                page = browser.new_page()
                page.goto(url, wait_until="domcontentloaded", timeout=timeout_goto)
                time.sleep(2)  # Let ESPN's JavaScript initialize

                # Wait for ESPN article content to load
                # ESPN typically loads article body in article-specific containers
                try:
                    page.wait_for_function(
                        """() => {
                            // Check for various ESPN article content containers
                            const article = document.querySelector('article') ||
                                          document.querySelector('[data-module="article"]') ||
                                          document.querySelector('.article-body') ||
                                          document.querySelector('.article-content') ||
                                          document.querySelector('main');
                            return article && article.innerText && article.innerText.length > 100;
                        }""",
                        timeout=20000,
                    )
                except Exception:
                    # Content might have loaded anyway, continue
                    pass

                time.sleep(1)  # Additional wait for any remaining content
                html = page.content()
                html_bytes = html.encode("utf-8") if isinstance(html, str) else html

                # Extract metadata from structured data
                json_ld_text = page.evaluate("""
                    () => {
                        const script = document.querySelector('script[type="application/ld+json"]');
                        return script ? script.textContent : null;
                    }
                """)
                if json_ld_text:
                    try:
                        data = json.loads(json_ld_text)
                        if isinstance(data, list):
                            data = data[0] if data else {}
                        metadata["title"] = data.get("headline") or data.get("name")
                        metadata["description"] = data.get("description")
                        raw_date = data.get("datePublished")
                        if raw_date:
                            metadata["date_publish"] = dateparser.parse(raw_date)
                        else:
                            metadata["date_publish"] = None
                    except (json.JSONDecodeError, TypeError):
                        metadata["date_publish"] = None
            finally:
                browser.close()
    except Exception as e:
        print(f"[ERROR] ESPN Playwright fetch failed for {url}: {e}")
        return None, None

    return html_bytes, metadata


def _fetch_pti_html(url: str, timeout_goto: int = 45000, sleep_after: float = 3.0) -> Tuple[Optional[bytes], Optional[Dict[str, Any]]]:
    """
    Fetch a PTI article page with Playwright and return rendered HTML plus metadata
    for fallback when NewsPlease does not extract maintext. Lazy-imports Playwright.
    Returns (html_bytes, metadata_dict) or (None, None) on failure.
    """
    try:
        from playwright.sync_api import sync_playwright
    except ImportError:
        return None, None

    metadata: Dict[str, Any] = {}
    try:
        with sync_playwright() as p:
            browser = p.chromium.launch(headless=True)
            try:
                page = browser.new_page()
                page.goto(url, wait_until="domcontentloaded", timeout=timeout_goto)
                time.sleep(sleep_after)
                try:
                    page.wait_for_function(
                        "() => (document.querySelector('app-root')?.innerText?.length || 0) > 100",
                        timeout=20000,
                    )
                except Exception:
                    pass
                html = page.content()
                html_bytes = html.encode("utf-8") if isinstance(html, str) else html

                json_ld_text = page.evaluate("""
                    () => {
                        const script = document.querySelector('script[type="application/ld+json"]');
                        return script ? script.textContent : null;
                    }
                """)
                if json_ld_text:
                    try:
                        data = json.loads(json_ld_text)
                        if isinstance(data, list):
                            data = data[0] if data else {}
                        metadata["title"] = data.get("headline") or data.get("name")
                        metadata["description"] = data.get("description")
                        raw_date = data.get("datePublished")
                        if raw_date:
                            metadata["date_publish"] = dateparser.parse(raw_date)
                        else:
                            metadata["date_publish"] = None
                    except (json.JSONDecodeError, TypeError):
                        metadata["date_publish"] = None

                body_text = page.evaluate("() => document.querySelector('app-root')?.innerText || ''")
                metadata["body_text"] = (body_text or "").strip()
            finally:
                browser.close()
    except Exception as e:
        print(f"[ERROR] PTI Playwright fetch failed for {url}: {e}")
        return None, None

    return html_bytes, metadata


def _fetch_sitemap_with_playwright(url: str, timeout_goto: int = 45000, timeout_total: int = 90) -> Optional[bytes]:
    """
    Fetch a sitemap with Playwright to bypass WAF/CloudFront blocking.
    Returns raw content bytes or None on failure.
    Used for ESPN and other WAF-protected sitemaps.

    timeout_total: Hard timeout in seconds - if Playwright takes longer, return None
    """
    import threading

    result = {"content": None, "error": None}

    def _playwright_fetch():
        try:
            from playwright.sync_api import sync_playwright
        except ImportError:
            result["error"] = "Playwright not installed"
            return

        try:
            with sync_playwright() as p:
                browser = p.chromium.launch(headless=True)
                try:
                    page = browser.new_page()
                    page.goto(url, wait_until="domcontentloaded", timeout=timeout_goto)
                    time.sleep(1)  # Wait for any dynamic content

                    # Get the page content as XML/text
                    content = page.content()
                    result["content"] = content.encode("utf-8") if isinstance(content, str) else content
                finally:
                    browser.close()
        except Exception as e:
            result["error"] = str(e)

    # Run Playwright in a thread with timeout protection
    thread = threading.Thread(target=_playwright_fetch, daemon=True)
    thread.start()
    thread.join(timeout=timeout_total)

    if thread.is_alive():
        print(f"[WARN] Playwright fetch for {url} exceeded {timeout_total}s timeout, giving up")
        return None

    if result["error"]:
        print(f"[ERROR] Playwright sitemap fetch failed for {url}: {result['error']}")
        return None

    return result["content"]


# Minimal response-like object for parse_article when we have HTML from Playwright.
class _FakeResponse(SimpleNamespace):
    content: bytes
    status_code: int = 200
    headers: Dict[str, str]

    def __init__(self, content: bytes, status_code: int = 200):
        super().__init__(
            content=content,
            status_code=status_code,
            headers={"Content-Type": "text/html; charset=utf-8"},
        )


# ---------------------------------------------------------------------------
class ArticleExtractor:
    """Single responsibility: fetch → parse → normalised dict."""

    USER_AGENT = ("Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/138.0.0.0 Safari/537.36")

    def __init__(self, session: requests.Session | None = None, tls_session=None):
        self.session = session or requests.Session()
        self.session.cookies.set("CONSENT", "YES+cb.20220419-08-p0.cs+FX+111")
        self.session.headers.update({"user-agent": self.USER_AGENT})
        self.tls_session = tls_session or tls_client.Session(
            client_identifier="chrome_120",
            random_tls_extension_order=True,
        )
    # -------------------------- low‑level helpers -------------------------
    @staticmethod
    def canonical_url(url: str) -> str:
        return url.strip().lower().rstrip('/')

    @classmethod
    def make_id(cls, url: str) -> str:
        return hashlib.sha256(cls.canonical_url(url).encode()).hexdigest()

    def fetch(self, url: str, timeout: int = 10, headers: Dict[str, str] | None = None, retries: int = 1):
        """Try normal requests first, fall back to tls‑client for stubborn hosts."""
        parsed = urlparse(url)
        default_headers = {
            "accept": "text/html,application/xhtml+xml,application/xml;q=0.9,image/webp,*/*;q=0.8",
            "user-agent": ("Mozilla/5.0 (Windows NT 10.0; Win64; x64)"
                           " AppleWebKit/537.36 (KHTML, like Gecko)"
                           " Chrome/125.0.0.0 Safari/537.36"),
            "referer": f"{parsed.scheme}://{parsed.netloc}/",
            "accept-language": "en-US,en;q=0.9",
            "accept-encoding": "gzip, deflate, br",
        }
        if headers:
            req_headers = default_headers | headers
        else:
            req_headers = default_headers

        # Retry logic for problematic domains
        for attempt in range(retries):
            # Try TLS client first
            try:
                r = self.tls_session.get(url, headers=req_headers,  allow_redirects=True)
                if r.status_code == 200:
                    return r
                if r.status_code == 429:
                    print(f"[WARN] Rate limited for {url}, retrying after cooldown...")
                    time.sleep(121)
                    r = self.tls_session.get(url, headers=req_headers, allow_redirects=True)
                    if r.status_code == 200:
                        return r
            except Exception as exc:
                if attempt == retries - 1:  # Last attempt
                    print(f"[ERROR] tls-client fetch failed for {url}: {exc}")
                else:
                    print(f"[WARN] tls-client fetch failed for {url}, retrying... ({attempt+1}/{retries})")
                    time.sleep(2 ** attempt)  # Exponential backoff

            # Fall back to regular requests
            try:
                r = self.session.get(url, timeout=timeout, allow_redirects=True, headers=req_headers)
                if r.status_code == 200:
                    return r
                if r.status_code == 429:
                    print(f"[WARN] Rate limited for {url}, retrying after cooldown...")
                    time.sleep(121)
                    r = self.session.get(url, timeout=timeout, allow_redirects=True, headers=req_headers)
                    if r.status_code == 200:
                        return r
            except Exception as exc:
                if attempt == retries - 1:  # Last attempt
                    print(f"[ERROR] requests fetch failed for {url}: {exc}")
                else:
                    print(f"[WARN] requests fetch failed for {url}, retrying... ({attempt+1}/{retries})")
                    time.sleep(2 ** attempt)  # Exponential backoff

        # All retries failed
        return None

    # -------------------------- sitemap / robots -------------------------
    def _discover_sitemaps(self, robots_url: str) -> List[str]:
        try:
            txt = self.fetch(robots_url).text
        except Exception as e:
            print(f"[ERROR] Failed to discover sitemaps from {robots_url}: {e}")
            return []
        return [line.split(":",1)[1].strip() for line in txt.splitlines() if line.lower().startswith("sitemap:")]

    def _decompress_if_needed(self, url: str, data: bytes) -> bytes:
        return gzip.decompress(data) if url.endswith((".gz", ".xml.gz")) else data

    def _parse_sitemap(self, url: str) -> List[Dict[str, Any]]:
        # Use more retries for problematic domains like espn.in
        retries = 3 if "espn.in" in url else 1
        try:
            resp = self.fetch(url, timeout=30, retries=retries)
            if resp is None:
                # If regular fetch failed for ESPN, try Playwright to bypass WAF
                if "espn.in" in url:
                    print(f"[INFO] Regular fetch failed for ESPN sitemap, trying Playwright...")
                    data = _fetch_sitemap_with_playwright(url)
                    if data is None:
                        print(f"[ERROR] Playwright also failed for {url}")
                        return []
                else:
                    print(f"[WARN] Failed to fetch sitemap {url} (timeout/blocked/no response after {retries} attempts)")
                    return []
            else:
                data = self._decompress_if_needed(url, resp.content)
        except Exception as e:
            print(f"[ERROR] Failed to parse sitemap {url}: {e}")
            return []
        try:
            root = ET.fromstring(strip_illegal(data))
        except ET.ParseError:
            return []

        # recurse through <sitemapindex>
        results: List[Dict[str, Any]] = []
        for sm in root.findall('.//{*}sitemap'):
            loc = sm.find('{*}loc')
            if loc is not None and loc.text:
                child = urljoin(url, loc.text.strip())
                if child.endswith((".xml", ".xml.gz", ".gz")):
                    results.extend(self._parse_sitemap(child))

        # if not a sitemapindex, treat as urlset
        if not results:
            for u in root.findall('.//{*}url'):
                loc = u.find('{*}loc')
                if loc is None or not loc.text:
                    continue
                item: Dict[str, Any] = {"loc": urljoin(url, loc.text.strip())}
                for child in u:
                    tag = child.tag.split('}')[-1]
                    if tag == 'loc':
                        continue
                    if child.text:
                        item[tag] = child.text.strip()
                results.append(item)
        return results

    # -------------------------- link resolver ----------------------------
    def resolve_link(self, url: str, timeout: int = 10) -> tuple[str, requests.Response | None]:
        """Unwrap Google News redirectors etc."""
        # For non-Google News URLs, don't fetch - just return URL
        # Let extract() handle fetching with proper TLS client
        if "news.google." not in url:
            return url, None
        
        # For Google News URLs, need to fetch to unwrap redirect
        try:
            # Use TLS client for Google News too (better success rate)
            resp = self.tls_session.get(url, timeout=timeout, allow_redirects=True)
        except Exception as e:
            try:
                resp = self.session.get(url, timeout=timeout, allow_redirects=True)
            except Exception as e2:
                print(f"[ERROR] Failed to resolve Google News link {url}: {e2}")
                return url, None

        # Google News RSS hackery (identical to original script)
        soup = BeautifulSoup(resp.text, "html.parser")
        a = soup.find("a", href=True)
        if a and a["href"].startswith(("http://", "https://")) and "news.google." not in a["href"]:
            return a["href"], None

        wiz = soup.select_one('c-wiz[data-p]')
        if wiz:
            try:
                # Google's payload is a weird JS array literal starting with %.@.
                data_p = wiz["data-p"].replace('%.@.', '["garturlreq",')
                arr = json.loads(data_p)
                # Build batchexecute RPC payload per community reverse-engineering:
                payload = {
                    'f.req': json.dumps([[[
                        'Fbv4je',
                        json.dumps(arr[:-6] + arr[-2:]),
                        'null',
                        'generic'
                    ]]])
                }
                post = self.session.post('https://news.google.com/_/DotsSplashUi/data/batchexecute',
                              data=payload, timeout=timeout)
                cleaned = post.text.lstrip(")]}'")
                parsed = json.loads(cleaned)[0][2]
                article_url = json.loads(parsed)[1]
                if article_url and "news.google." not in article_url:
                    return article_url, None
            except Exception as e:
                print(f"[ERROR] Google News batchexecute failed for {url}: {e}")

        # try base64 token decoding fallback
        m = re.search(r"/rss/articles/([^?]+)", url)
        if m:
            token = m.group(1)
            for cand in re.findall(r"[A-Za-z0-9_-]{8,}", token):
                try:
                    pad = '=' * (-len(cand) % 4)
                    dec = base64.urlsafe_b64decode(cand + pad).decode('utf-8', 'ignore')  # type: ignore
                    if dec.startswith(("http://", "https://")) and "news.google." not in dec:
                        return dec, None
                except Exception:
                    continue
        return url, None

    def parse_article(
        self,
        resp: requests.Response | None,
        url: str,
        rss_entry: Dict[str, Any] | None,
    ) -> Dict[str, Any] | None:
        """Convert an HTTP response into our normalised article dict."""
        if resp is None or resp.status_code != 200:
            return None
        
        try:
            ctype = resp.headers.get("Content-Type", "").lower()
            if "html" not in ctype and "text" not in ctype:
                return None
            html = clean_html(resp.content)
            art = NewsPlease.from_html(html, url=url)
        except Exception as e:
            print(f"[ERROR] Failed to parse article {url}: {e}")
            return None

        if not art:
            if "espn.in" in url:
                print(f"[DEBUG] ESPN article parse returned None (NewsPlease failed): {url[:80]}")
            return None

        if not art.maintext:
            if "espn.in" in url:
                print(f"[DEBUG] ESPN article has no maintext extracted: {url[:80]} (title: {(art.title or 'N/A')[:50]})")
            return None

        date_publish = extract_publish_date_from_html(html)
        if date_publish is None:
            date_publish = rss_entry and rss_entry.get("published")
        # Normalize to UTC so DB stores UTC (e.g. meta "2026-02-03T08:49:07.177Z" -> 08:49:07+00:00)
        if date_publish is not None and isinstance(date_publish, datetime):
            if date_publish.tzinfo is None:
                date_publish = date_publish.replace(tzinfo=timezone.utc)
            else:
                date_publish = date_publish.astimezone(timezone.utc)

        return {
            "id": self.make_id(url),
            "url": url,
            "title": art.title or (rss_entry and rss_entry.get("title")),
            "authors": art.authors,
            "date_publish": date_publish,
            "description": art.description or (rss_entry and rss_entry.get("summary")),
            "image_url": art.image_url if is_valid_image_url(art.image_url) else None,
            "language": art.language,
            "source_domain": art.source_domain,
            "text": art.maintext,
            "fetched_at": datetime.now(timezone.utc),
            "feed_data": rss_entry,
            # "raw":           {},  # raw field filled in FeedCrawler.bulk_store
        }

    def _build_pti_article_from_metadata(
        self,
        url: str,
        rss_entry: Dict[str, Any] | None,
        metadata: Dict[str, Any],
    ) -> Dict[str, Any]:
        """Build normalised article dict from PTI Playwright metadata when parse_article returns None."""
        title = metadata.get("title") or (rss_entry and rss_entry.get("title"))
        description = metadata.get("description") or (rss_entry and rss_entry.get("summary"))
        body_text = metadata.get("body_text") or description or ""
        date_publish = metadata.get("date_publish")
        if date_publish is None and rss_entry:
            raw = rss_entry.get("publication_date") or rss_entry.get("lastmod") or rss_entry.get("published")
            if raw:
                try:
                    date_publish = dateparser.parse(raw)
                except Exception:
                    pass
        if date_publish is not None and isinstance(date_publish, datetime):
            if date_publish.tzinfo is None:
                date_publish = date_publish.replace(tzinfo=timezone.utc)
            else:
                date_publish = date_publish.astimezone(timezone.utc)
        return {
            "id": self.make_id(url),
            "url": url,
            "title": title,
            "authors": [],
            "date_publish": date_publish,
            "description": description,
            "image_url": None,
            "language": "en",
            "source_domain": "www.ptinews.com",
            "text": body_text,
            "fetched_at": datetime.now(timezone.utc),
            "feed_data": rss_entry,
        }

    # -------------------------- article extraction -----------------------
    def extract(self, url: str, rss_entry: Dict[str, Any] | None = None, resp: requests.Response | None = None) -> Dict[str, Any] | None:
        # uniindia http works as https
        if "uniindia.com" in url and url.startswith("http://"):
            url = url.replace("http://", "https://", 1)
        try:
            if resp is not None:
                if not resp:
                    return None
                return self.parse_article(resp, url, rss_entry)

            if "espn.in" in (urlparse(url).netloc or "").lower():
                # Use ESPN-specific Playwright fetch to bypass ESPN's anti-bot protection
                html_bytes, metadata = _fetch_espn_html(url, timeout_goto=30000)
                if html_bytes is None:
                    return None
                resp_like = _FakeResponse(html_bytes)
                art = self.parse_article(resp_like, url, rss_entry)
                if art is not None:
                    return art
                if metadata:
                    return self._build_pti_article_from_metadata(url, rss_entry, metadata)
                return None

            if "ptinews.com" in (urlparse(url).netloc or "").lower():
                html_bytes, metadata = _fetch_pti_html(url)
                if html_bytes is None:
                    return None
                resp_like = _FakeResponse(html_bytes)
                art = self.parse_article(resp_like, url, rss_entry)
                if art is not None:
                    return art
                if metadata:
                    return self._build_pti_article_from_metadata(url, rss_entry, metadata)
                return None

            resp = self.fetch(url, timeout=15)
            if not resp:
                return None
            return self.parse_article(resp, url, rss_entry)
        except Exception as e:
            print(f"[ERROR] Extraction failed for {url}: {e}")
            return None

    def extract_for_reuters(self, url: str, rss_entry: Dict[str, Any] | None = None, resp: requests.Response | None = None) -> Dict[str, Any] | None:
        try:
            if resp is None:
                resp = self.fetch(url, timeout=10, headers=REUTERS_HEADERS)
            if not resp:
                return None
            return self.parse_article(resp, url, rss_entry)
        except Exception as e:
            print(f"[ERROR] Reuters extraction failed for {url}: {e}")
            return None


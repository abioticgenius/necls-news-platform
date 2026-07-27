from __future__ import annotations

import argparse
import json
import os
import re
import sys
import traceback
from datetime import datetime
from pathlib import Path
from typing import Any

import requests
from bs4 import BeautifulSoup
from dateutil import parser as dateparser
from langchain_core.messages import HumanMessage, SystemMessage
from langchain_openai import ChatOpenAI
from newsplease import NewsPlease


REPO_ROOT = Path(__file__).resolve().parents[1]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from necls_backend.output_structure.structure import MultiLanguageSummaryNew
from necls_backend.prompts.summary import SUMMARY_PROMPT


DEFAULT_MODEL = "gpt-5-mini"
DEFAULT_TIMEOUT_SECONDS = 20
USER_AGENT = (
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
    "AppleWebKit/537.36 (KHTML, like Gecko) "
    "Chrome/125.0.0.0 Safari/537.36"
)


def log(message: str) -> None:
    print(message, flush=True)


def load_dotenv(path: Path) -> None:
    if not path.exists():
        return
    for raw_line in path.read_text(encoding="utf-8").splitlines():
        line = raw_line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, value = line.split("=", 1)
        key = key.strip()
        value = value.strip().strip('"').strip("'")
        if key and key not in os.environ:
            os.environ[key] = value


def parse_publish_date(html: str) -> datetime | str | None:
    soup = BeautifulSoup(html, "html.parser")
    selectors = [
        ("property", "article:published_time"),
        ("property", "og:published_time"),
        ("name", "pubdate"),
        ("name", "publish-date"),
        ("name", "date"),
        ("itemprop", "datePublished"),
    ]
    for attr, value in selectors:
        tag = soup.find("meta", attrs={attr: value})
        if tag and tag.get("content"):
            return parse_date(tag["content"])

    for script in soup.find_all("script", type="application/ld+json"):
        text = script.string or script.get_text()
        if not text:
            continue
        match = re.search(r'"datePublished"\s*:\s*"([^"]+)"', text)
        if match:
            return parse_date(match.group(1))
    return None


def parse_date(value: str) -> datetime | str | None:
    try:
        return dateparser.parse(value)
    except Exception:
        return value


def json_default(value: Any) -> str:
    if isinstance(value, datetime):
        return value.isoformat()
    return str(value)


def compact_text(text: str | None, max_chars: int) -> str:
    text = re.sub(r"\s+", " ", text or "").strip()
    if max_chars > 0 and len(text) > max_chars:
        return text[:max_chars].rsplit(" ", 1)[0] + "..."
    return text


def extract_article(url: str, timeout: int, max_text_chars: int) -> dict[str, Any]:
    headers = {
        "User-Agent": USER_AGENT,
        "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
        "Accept-Language": "en-US,en;q=0.9",
    }
    response = requests.get(url, headers=headers, timeout=timeout)
    response.raise_for_status()

    html = response.text
    article = NewsPlease.from_html(html, url=url)
    title = article.title if article else None
    text = article.maintext if article else None
    date_publish = parse_publish_date(html)

    if not title:
        soup = BeautifulSoup(html, "html.parser")
        title_tag = soup.find("title")
        title = title_tag.get_text(" ", strip=True) if title_tag else url

    if not text:
        soup = BeautifulSoup(html, "html.parser")
        paragraphs = [p.get_text(" ", strip=True) for p in soup.find_all("p")]
        text = " ".join(p for p in paragraphs if p)

    return {
        "url": url,
        "date_publish": date_publish,
        "title": compact_text(title, 500),
        "text": compact_text(text, max_text_chars),
    }


def load_cluster_articles(cluster_id: str, max_text_chars: int) -> list[dict[str, Any]]:
    import sqlalchemy as sa

    from necls_backend.db import articles, engine, story_members

    stmt = (
        sa.select(
            articles.c.url,
            articles.c.date_publish,
            articles.c.title,
            articles.c.text,
        )
        .select_from(story_members.join(articles, articles.c.id == story_members.c.article_id))
        .where(story_members.c.cluster_id == sa.bindparam("cluster_id"))
        .where(articles.c.language == "en")
        .order_by(articles.c.date_publish.desc().nullslast())
    )

    with engine.connect() as conn:
        rows = conn.execute(stmt, {"cluster_id": cluster_id}).mappings().all()

    cluster_articles = []
    for row in rows:
        article = dict(row)
        article["title"] = compact_text(article.get("title"), 500)
        article["text"] = compact_text(article.get("text"), max_text_chars)
        cluster_articles.append(article)
    return cluster_articles


def build_prompt(articles: list[dict[str, Any]]) -> str:
    return SUMMARY_PROMPT + "\n Articles: \n" + json.dumps(
        articles,
        ensure_ascii=False,
        default=json_default,
    )


def generate_summary(prompt: str, model: str, api_key: str):
    llm = ChatOpenAI(model=model, api_key=api_key)
    structured_llm = llm.with_structured_output(MultiLanguageSummaryNew)
    return structured_llm.invoke([SystemMessage(content=prompt), HumanMessage(content=" ")])


def cli() -> int:
    parser = argparse.ArgumentParser(
        description=(
            "One-off tester: fetch article URLs or load an existing story cluster, "
            "then run summary.py."
        )
    )
    parser.add_argument("urls", nargs="*", help="Article URLs to process as one cluster")
    parser.add_argument("--cluster-id", help="Existing story_clusters.cluster_id to process directly from DB1")
    parser.add_argument("--url", action="append", dest="url_flags", default=[], help="Article URL; can be repeated")
    parser.add_argument("--model", default=os.getenv("OPENAI_MODEL", DEFAULT_MODEL))
    parser.add_argument("--api-key-env", default="OPENAI_API_KEY", help="Environment variable containing the API key")
    parser.add_argument("--env-file", default=".env", help="Optional .env file to load before reading the API key")
    parser.add_argument("--timeout", type=int, default=DEFAULT_TIMEOUT_SECONDS)
    parser.add_argument(
        "--max-text-chars",
        type=int,
        default=15000,
        help="Max text chars per article before sending to the LLM. Use 0 for no truncation.",
    )
    parser.add_argument("--save-output", help="Write the structured LLM output JSON to this path")
    parser.add_argument("--save-articles", help="Write extracted article payload JSON to this path")
    parser.add_argument("--print-articles", action="store_true", help="Print extracted article payload before LLM output")
    parser.add_argument("--skip-llm", action="store_true", help="Only load/extract articles; do not call the LLM")
    args = parser.parse_args()

    load_dotenv(REPO_ROOT / args.env_file)

    urls = [*args.urls, *args.url_flags]
    if bool(args.cluster_id) == bool(urls):
        parser.error("Provide either --cluster-id or article URL(s), not both.")

    api_key = os.getenv(args.api_key_env)
    if not args.skip_llm and not api_key:
        parser.error(f"{args.api_key_env} is not set. Put it in env or {args.env_file}.")

    if args.cluster_id:
        log(f"Loading cluster {args.cluster_id} from DB1...")
        articles = load_cluster_articles(args.cluster_id, args.max_text_chars)
        if not articles:
            raise RuntimeError(f"No English articles found for cluster {args.cluster_id}")
        for article in articles:
            if not article["text"]:
                raise RuntimeError(f"Cluster article has no text: {article.get('url')}")
        log(f"Loaded {len(articles)} English article(s) from DB1.")
    else:
        articles = []
        for index, url in enumerate(urls, start=1):
            log(f"[{index}/{len(urls)}] Extracting {url}")
            article = extract_article(url, timeout=args.timeout, max_text_chars=args.max_text_chars)
            if not article["text"]:
                raise RuntimeError(f"No article text extracted from {url}")
            articles.append(article)
        log(f"Extracted {len(articles)} article(s) from URL input.")

    if args.save_articles:
        Path(args.save_articles).write_text(
            json.dumps(articles, ensure_ascii=False, indent=2, default=json_default),
            encoding="utf-8",
        )
        log(f"Wrote extracted article payload to {args.save_articles}")

    if args.print_articles:
        print(json.dumps({"articles": articles}, ensure_ascii=False, indent=2, default=json_default))

    if args.skip_llm:
        log("Skipping LLM call because --skip-llm was passed.")
        return 0

    if not api_key:
        parser.error(f"{args.api_key_env} is not set. Put it in env or {args.env_file}.")

    log(f"Running {args.model} with {len(articles)} article(s)...")
    result = generate_summary(build_prompt(articles), model=args.model, api_key=api_key)
    output = result.model_dump(mode="json")
    output_json = json.dumps(output, ensure_ascii=False, indent=2)

    if args.save_output:
        Path(args.save_output).write_text(output_json + "\n", encoding="utf-8")
        log(f"Wrote structured LLM output to {args.save_output}")

    print(output_json)
    return 0


if __name__ == "__main__":
    try:
        raise SystemExit(cli())
    except SystemExit:
        raise
    except BaseException:
        traceback.print_exc()
        raise SystemExit(1)

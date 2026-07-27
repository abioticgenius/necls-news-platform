from __future__ import annotations

import argparse
import datetime as dt
import json
import os
import random
import sys
import time
import traceback
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Iterable

import sqlalchemy as sa
from dotenv import load_dotenv
from langchain_core.messages import HumanMessage, SystemMessage
from langchain_openai import ChatOpenAI


ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

load_dotenv(ROOT / ".env")
if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8")
if hasattr(sys.stderr, "reconfigure"):
    sys.stderr.reconfigure(encoding="utf-8")

from necls_backend.db import articles, db2_links, engine, generations, sources, story_clusters, story_members, summary_localized  # noqa: E402
from necls_backend.output_structure.structure import MultiLanguageSummaryNew  # noqa: E402
from necls_backend.prompts.summary import SUMMARY_PROMPT  # noqa: E402


DEFAULT_STATUSES = ("manual_approved", "editorial_approved", "auto_approved")


@dataclass
class ClusterCase:
    cluster_id: str
    filter_status: str
    cluster_headline: str
    size: int | None
    created_at: str
    updated_at: str
    articles: list[dict[str, Any]]
    existing_output: dict[str, Any] | None


@dataclass
class EvalResult:
    case: ClusterCase
    output: dict[str, Any] | None
    error: str | None = None


def _parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description=(
            "Batch-test necls_backend.prompts.summary.SUMMARY_PROMPT against "
            "existing story clusters, using the same article payload shape as prod."
        )
    )
    parser.add_argument(
        "--cluster-id",
        action="append",
        default=[],
        help="Specific story_clusters.cluster_id to process. Can be repeated.",
    )
    parser.add_argument(
        "--db2-event-id",
        action="append",
        default=[],
        help="Specific db2_links.db2_event_id to process. Can be repeated.",
    )
    parser.add_argument(
        "--status",
        action="append",
        choices=("manual_approved", "editorial_approved", "auto_approved", "pending", "editorial_rejected"),
        help=(
            "Cluster filter_status to sample. Can be repeated. "
            "Default: manual_approved, editorial_approved, auto_approved."
        ),
    )
    parser.add_argument("--limit", type=int, default=3, help="Max clusters to process when sampling by status.")
    parser.add_argument("--days", type=int, default=3, help="Look back this many days by story_clusters.updated_at.")
    parser.add_argument(
        "--since",
        help="Override --days with an IST timestamp/date, e.g. '2026-05-02 00:00' or '2026-05-02'.",
    )
    parser.add_argument(
        "--order",
        choices=("latest", "random"),
        default="latest",
        help="Choose newest matching clusters or a random sample within the window.",
    )
    parser.add_argument("--model", default=os.getenv("OPENAI_MODEL", "gpt-5-mini"), help="OpenAI model to use.")
    parser.add_argument("--api-key-env", default="OPENAI_API_KEY", help="Environment variable containing the API key.")
    parser.add_argument("--temperature", type=float, default=0.0)
    parser.add_argument(
        "--max-text-chars",
        type=int,
        default=0,
        help=(
            "Optional max text chars per article before sending to the LLM. "
            "Default 0 mirrors prod by sending full article text."
        ),
    )
    parser.add_argument(
        "--max-articles",
        type=int,
        default=0,
        help="Optional max articles per cluster, newest first. Default 0 mirrors prod by sending all English articles.",
    )
    parser.add_argument("--sleep", type=float, default=0.0, help="Seconds to sleep between LLM calls.")
    parser.add_argument("--output-json", default="", help="Optional path to write the printed comparison JSON.")
    parser.add_argument(
        "--save-prompts",
        help="Optional directory where the exact prompt payload for each cluster will be written.",
    )
    parser.add_argument("--print-full", action="store_true", help="Print full structured JSON for every cluster.")
    parser.add_argument("--skip-llm", action="store_true", help="Only load cluster article payloads; do not call the LLM.")
    return parser.parse_args()


def _ist() -> dt.timezone:
    return dt.timezone(dt.timedelta(hours=5, minutes=30))


def _since_from_args(args: argparse.Namespace) -> dt.datetime:
    tz = _ist()
    if args.since:
        raw = args.since.strip()
        if len(raw) == 10:
            parsed = dt.datetime.strptime(raw, "%Y-%m-%d")
        else:
            parsed = dt.datetime.fromisoformat(raw)
        if parsed.tzinfo is None:
            parsed = parsed.replace(tzinfo=tz)
        return parsed
    return dt.datetime.now(tz) - dt.timedelta(days=args.days)


def _json_default(value: Any) -> str:
    if isinstance(value, (dt.datetime, dt.date)):
        return value.isoformat()
    return str(value)


def _clean(value: object, limit: int | None = None) -> str:
    text = "" if value is None else str(value)
    text = " ".join(text.split())
    if limit and len(text) > limit:
        return text[: limit - 3].rstrip() + "..."
    return text


def _clip_text(value: object, max_chars: int) -> str:
    text = "" if value is None else str(value)
    if max_chars > 0 and len(text) > max_chars:
        return text[:max_chars].rsplit(" ", 1)[0] + "..."
    return text


def _fetch_cluster_ids(args: argparse.Namespace) -> list[str]:
    explicit_ids = [cluster_id.strip() for cluster_id in args.cluster_id if cluster_id.strip()]
    db2_event_ids = [event_id.strip() for event_id in args.db2_event_id if event_id.strip()]
    if db2_event_ids:
        explicit_ids.extend(_cluster_ids_from_db2_event_ids(db2_event_ids))
    if explicit_ids:
        return list(dict.fromkeys(explicit_ids))

    statuses = tuple(args.status or DEFAULT_STATUSES)
    since = _since_from_args(args)
    stmt = (
        sa.select(story_clusters.c.cluster_id)
        .where(story_clusters.c.filter_status.in_(statuses))
        .where(story_clusters.c.updated_at >= sa.bindparam("since"))
        .order_by(story_clusters.c.updated_at.desc())
        .limit(args.limit)
    )

    with engine.connect() as conn:
        rows = conn.execute(stmt, {"since": since}).scalars().all()

    ids = [str(row) for row in rows]
    if args.order == "random":
        random.shuffle(ids)
        return ids[: args.limit]
    return ids


def _cluster_ids_from_db2_event_ids(db2_event_ids: list[str]) -> list[str]:
    stmt = (
        sa.select(db2_links.c.cluster_id)
        .where(db2_links.c.db2_event_id == sa.bindparam("db2_event_id"))
    )
    cluster_ids: list[str] = []
    with engine.connect() as conn:
        for db2_event_id in db2_event_ids:
            rows = conn.execute(stmt, {"db2_event_id": db2_event_id}).scalars().all()
            if not rows:
                print(f"[LOAD ERROR] db2_event_id={db2_event_id} error=No linked cluster found")
            cluster_ids.extend(str(row) for row in rows)
    return cluster_ids


def _fetch_case(cluster_id: str, args: argparse.Namespace) -> ClusterCase:
    meta_stmt = (
        sa.select(
            story_clusters.c.cluster_id,
            story_clusters.c.filter_status,
            story_clusters.c.headline,
            story_clusters.c.size,
            story_clusters.c.created_at,
            story_clusters.c.updated_at,
        )
        .where(story_clusters.c.cluster_id == sa.bindparam("cluster_id"))
    )
    article_stmt = (
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
    if args.max_articles > 0:
        article_stmt = article_stmt.limit(args.max_articles)

    with engine.connect() as conn:
        meta_row = conn.execute(meta_stmt, {"cluster_id": cluster_id}).mappings().first()
        article_rows = conn.execute(article_stmt, {"cluster_id": cluster_id}).mappings().all()
        existing_output = _fetch_existing_output(conn, cluster_id)

    if not meta_row:
        raise RuntimeError(f"Cluster not found: {cluster_id}")
    if not article_rows:
        raise RuntimeError(f"No English articles found for cluster: {cluster_id}")

    article_payloads: list[dict[str, Any]] = []
    for row in article_rows:
        article_payloads.append(
            {
                "url": row["url"],
                "date_publish": _json_default(row["date_publish"]) if row["date_publish"] else None,
                "title": row["title"],
                "text": _clip_text(row["text"], args.max_text_chars),
            }
        )

    return ClusterCase(
        cluster_id=str(meta_row["cluster_id"]),
        filter_status=meta_row["filter_status"] or "",
        cluster_headline=meta_row["headline"] or "",
        size=meta_row["size"],
        created_at=_json_default(meta_row["created_at"]) if meta_row["created_at"] else "",
        updated_at=_json_default(meta_row["updated_at"]) if meta_row["updated_at"] else "",
        articles=article_payloads,
        existing_output=existing_output,
    )


def _fetch_existing_output(conn: sa.Connection, cluster_id: str) -> dict[str, Any] | None:
    generation_stmt = (
        sa.select(
            generations.c.id,
            generations.c.created_at,
            generations.c.extra,
        )
        .where(generations.c.cluster_id == sa.bindparam("cluster_id"))
        .where(generations.c.artifact == "summary")
        .order_by(generations.c.created_at.desc())
        .limit(1)
    )
    generation = conn.execute(generation_stmt, {"cluster_id": cluster_id}).mappings().first()
    if not generation:
        return None

    localized_stmt = (
        sa.select(
            summary_localized.c.language_id,
            summary_localized.c.last_updated_at,
            summary_localized.c.headline,
            summary_localized.c.bullets,
            summary_localized.c.audio_text,
        )
        .where(summary_localized.c.generation_id == sa.bindparam("generation_id"))
    )
    source_stmt = (
        sa.select(sources.c.url, sources.c.title, sources.c.article_date)
        .where(sources.c.generation_id == sa.bindparam("generation_id"))
    )

    localized = conn.execute(localized_stmt, {"generation_id": generation["id"]}).mappings().all()
    source_rows = conn.execute(source_stmt, {"generation_id": generation["id"]}).mappings().all()

    by_lang = {row["language_id"]: row for row in localized}
    en = by_lang.get("en")
    hi = by_lang.get("hi")
    extra = generation["extra"] or {}

    output = {
        "title_en": en["headline"] if en else None,
        "title_hi": hi["headline"] if hi else None,
        "summary_en": (en["bullets"] or [None])[0] if en else None,
        "summary_hi": (hi["bullets"] or [None])[0] if hi else None,
        "last_updated_at": _json_default(en["last_updated_at"]) if en and en["last_updated_at"] else None,
        "classification": (extra.get("classification") if isinstance(extra, dict) else None),
        "tags": (extra.get("tags") if isinstance(extra, dict) else None),
        "faqs_en": (extra.get("faqs_en") if isinstance(extra, dict) else None),
        "faqs_hi": (extra.get("faqs_hi") if isinstance(extra, dict) else None),
        "audio_scripts_summary": {
            "en": en["audio_text"] if en else None,
            "hi": hi["audio_text"] if hi else None,
        },
        "google_news_queries": (extra.get("google_news_queries") if isinstance(extra, dict) else None),
        "sources": [
            {
                "url": row["url"],
                "title": row["title"],
                "article_date": _json_default(row["article_date"]) if row["article_date"] else None,
            }
            for row in source_rows
        ],
        "_stored_generation_id": str(generation["id"]),
        "_stored_created_at": _json_default(generation["created_at"]) if generation["created_at"] else None,
    }
    return output


def _build_prompt(case: ClusterCase) -> str:
    # Mirrors necls_backend.llm_pipeline.pipeline._get_llm_data:
    # SUMMARY_PROMPT + "\n Articles: \n" + json.dumps(articles_info)
    return SUMMARY_PROMPT + "\n Articles: \n" + json.dumps(
        case.articles,
        ensure_ascii=False,
        default=_json_default,
    )


def _build_llm(args: argparse.Namespace):
    api_key = os.getenv(args.api_key_env)
    if not api_key:
        raise RuntimeError(f"{args.api_key_env} must be set.")
    return ChatOpenAI(
        model=args.model,
        api_key=api_key,
        temperature=args.temperature,
    ).with_structured_output(MultiLanguageSummaryNew)


def _save_prompt(case: ClusterCase, prompt: str, prompt_dir: Path) -> None:
    prompt_dir.mkdir(parents=True, exist_ok=True)
    path = prompt_dir / f"{case.cluster_id}.txt"
    path.write_text(prompt, encoding="utf-8")


def _evaluate(cases: Iterable[ClusterCase], args: argparse.Namespace) -> list[EvalResult]:
    llm = None if args.skip_llm else _build_llm(args)
    prompt_dir = Path(args.save_prompts) if args.save_prompts else None
    results: list[EvalResult] = []

    for idx, case in enumerate(cases, 1):
        prompt = _build_prompt(case)
        if prompt_dir:
            _save_prompt(case, prompt, prompt_dir)

        if args.skip_llm:
            output = None
            error = None
        else:
            try:
                assert llm is not None
                response = llm.invoke([SystemMessage(content=prompt), HumanMessage(content=" ")])
                output = response.model_dump(mode="json")
                error = None
            except Exception as exc:
                output = None
                error = repr(exc)

        results.append(EvalResult(case=case, output=output, error=error))
        _print_comparison(case, output, error)
        if args.sleep:
            time.sleep(args.sleep)

    return results


def _comparison_payload(case: ClusterCase, output: dict[str, Any] | None, error: str | None) -> dict[str, Any]:
    current_output: dict[str, Any] | None
    if error:
        current_output = {"error": error}
    else:
        current_output = output
    return {
        "cluster_id": case.cluster_id,
        "existing_output": case.existing_output,
        "current_output": current_output,
    }


def _print_comparison(case: ClusterCase, output: dict[str, Any] | None, error: str | None) -> None:
    print(json.dumps(_comparison_payload(case, output, error), ensure_ascii=False, indent=2, default=_json_default))


def _result_to_dict(result: EvalResult) -> dict[str, Any]:
    case = result.case
    return {
        "cluster_id": case.cluster_id,
        **_comparison_payload(case, result.output, result.error),
    }


def _write_json(results: list[EvalResult], output_path: str) -> None:
    if not output_path:
        return
    path = Path(output_path)
    path.parent.mkdir(parents=True, exist_ok=True)
    payload = {
        "generated_at": dt.datetime.now(_ist()).isoformat(),
        "results": [_result_to_dict(result) for result in results],
    }
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=2, default=_json_default) + "\n", encoding="utf-8")


def main() -> int:
    args = _parse_args()
    cluster_ids = _fetch_cluster_ids(args)
    if not cluster_ids:
        print("No clusters matched the requested filters.")
        return 1

    cases: list[ClusterCase] = []
    for cluster_id in cluster_ids:
        try:
            cases.append(_fetch_case(cluster_id, args))
        except Exception as exc:
            print(f"[LOAD ERROR] id={cluster_id} error={exc}")

    if not cases:
        print("No usable clusters found.")
        return 1

    results = _evaluate(cases, args)
    errors = sum(1 for result in results if result.error)
    _write_json(results, args.output_json)
    return 1 if errors else 0


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except SystemExit:
        raise
    except BaseException:
        traceback.print_exc()
        raise SystemExit(1)

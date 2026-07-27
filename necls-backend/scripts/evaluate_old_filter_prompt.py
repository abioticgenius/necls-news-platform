from __future__ import annotations

import argparse
import csv
import datetime as dt
import os
import random
import sys
import time
from dataclasses import dataclass
from pathlib import Path
from typing import Iterable

import sqlalchemy as sa
from dotenv import load_dotenv
from langchain_core.messages import HumanMessage
from langchain_openai import ChatOpenAI

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

load_dotenv(ROOT / ".env")

from necls_backend.db import engine  # noqa: E402
from necls_backend.output_structure.structure import FilterOutput  # noqa: E402
from necls_backend.prompts.old_prompt import FILTER_PROMPT  # noqa: E402


DEFAULT_STATUSES = ("manual_approved", "editorial_rejected")
EXPECTED_BY_STATUS = {
    "manual_approved": "YES",
    "editorial_approved": "YES",
    "auto_approved": "YES",
    "editorial_rejected": "NO",
}


@dataclass
class ClusterCase:
    cluster_id: str
    original_status: str
    expected_status: str | None
    cluster_headline: str
    headline: str
    description: str
    article_title: str
    source_domain: str
    size: int | None
    created_at: str
    updated_at: str


@dataclass
class EvalResult:
    case: ClusterCase
    prompt_status: str
    matches_expected: bool | None
    error: str | None = None


def _parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description=(
            "Evaluate necls_backend.prompts.old_prompt.FILTER_PROMPT against "
            "recent manual-approved and rejected clusters."
        )
    )
    parser.add_argument("--manual-limit", type=int, default=25, help="Max manual_approved clusters to test.")
    parser.add_argument("--rejected-limit", type=int, default=25, help="Max editorial_rejected clusters to test.")
    parser.add_argument(
        "--approved-limit",
        type=int,
        default=0,
        help="Optional editorial_approved clusters to include as additional YES controls.",
    )
    parser.add_argument("--days", type=int, default=3, help="Look back this many days by updated_at.")
    parser.add_argument(
        "--since",
        help="Override --days with an IST timestamp/date, e.g. '2026-05-02 00:00' or '2026-05-02'.",
    )
    parser.add_argument(
        "--order",
        choices=("latest", "random"),
        default="latest",
        help="Choose the newest clusters or a random sample within the window.",
    )
    parser.add_argument("--model", default="gpt-4o-mini", help="OpenAI model to use.")
    parser.add_argument("--temperature", type=float, default=0.0)
    parser.add_argument("--sleep", type=float, default=0.0, help="Seconds to sleep between LLM calls.")
    parser.add_argument("--max-text-chars", type=int, default=400, help="Fallback text length when description is empty.")
    parser.add_argument("--csv", dest="csv_path", help="Optional CSV output path.")
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


def _clean(value: object, limit: int | None = None) -> str:
    text = "" if value is None else str(value)
    text = " ".join(text.split())
    if limit and len(text) > limit:
        return text[: limit - 1] + "…"
    return text


def _limits_from_args(args: argparse.Namespace) -> dict[str, int]:
    limits = {
        "manual_approved": args.manual_limit,
        "editorial_rejected": args.rejected_limit,
    }
    if args.approved_limit:
        limits["editorial_approved"] = args.approved_limit
    return {status: limit for status, limit in limits.items() if limit > 0}


def _fetch_cases(args: argparse.Namespace) -> list[ClusterCase]:
    since = _since_from_args(args)
    limits = _limits_from_args(args)
    all_cases: list[ClusterCase] = []

    query = sa.text(
        """
        WITH reps AS (
            SELECT
                sc.cluster_id::text AS cluster_id,
                sc.filter_status,
                sc.headline AS cluster_headline,
                sc.size,
                sc.created_at,
                sc.updated_at,
                a.title AS article_title,
                a.description,
                a.text AS article_text,
                a.source_domain,
                a.date_publish,
                row_number() OVER (
                    PARTITION BY sc.cluster_id
                    ORDER BY a.date_publish DESC NULLS LAST
                ) AS rn
            FROM story_clusters sc
            LEFT JOIN story_members sm ON sm.cluster_id = sc.cluster_id
            LEFT JOIN articles a ON a.id = sm.article_id
            WHERE sc.filter_status = :status
              AND sc.updated_at >= :since
        )
        SELECT *
        FROM reps
        WHERE rn = 1
        ORDER BY updated_at DESC
        LIMIT :limit
        """
    )

    with engine.connect() as conn:
        for status, limit in limits.items():
            rows = list(conn.execute(query, {"status": status, "since": since, "limit": limit}).mappings())
            for row in rows:
                cluster_headline = _clean(row["cluster_headline"])
                # Mirror production filtering in llm_pipeline.pipeline.filter_cluster:
                # prod chooses the most recent article and sends that article's title
                # plus description/text fallback to the filter prompt. The cluster
                # headline is kept only as context in exports.
                headline = _clean(row["article_title"] or row["cluster_headline"])
                description = _clean(row["description"])
                if not description:
                    description = _clean(row["article_text"], args.max_text_chars)
                all_cases.append(
                    ClusterCase(
                        cluster_id=row["cluster_id"],
                        original_status=row["filter_status"],
                        expected_status=EXPECTED_BY_STATUS.get(row["filter_status"]),
                        cluster_headline=cluster_headline,
                        headline=headline,
                        description=description,
                        article_title=_clean(row["article_title"]),
                        source_domain=_clean(row["source_domain"]),
                        size=row["size"],
                        created_at=row["created_at"].isoformat() if row["created_at"] else "",
                        updated_at=row["updated_at"].isoformat() if row["updated_at"] else "",
                    )
                )

    if args.order == "random":
        random.shuffle(all_cases)
    return all_cases


def _format_prompt(case: ClusterCase) -> str:
    return FILTER_PROMPT.replace("{{headline}}", case.headline).replace("{{description}}", case.description)


def _build_llm(args: argparse.Namespace):
    api_key = os.getenv("OPENAI_API_KEY2") or os.getenv("OPENAI_API_KEY")
    if not api_key:
        raise RuntimeError("OPENAI_API_KEY2 or OPENAI_API_KEY must be set.")
    return ChatOpenAI(
        model=args.model,
        api_key=api_key,
        temperature=args.temperature,
    ).with_structured_output(FilterOutput)


def _evaluate(cases: Iterable[ClusterCase], args: argparse.Namespace) -> list[EvalResult]:
    llm = _build_llm(args)
    results: list[EvalResult] = []
    for idx, case in enumerate(cases, 1):
        try:
            response = llm.invoke([HumanMessage(content=_format_prompt(case))])
            prompt_status = response.status
            error = None
        except Exception as exc:  # Keep going; one bad call should not hide the rest.
            prompt_status = "ERROR"
            error = repr(exc)
        matches = None
        if case.expected_status:
            matches = prompt_status == case.expected_status
        results.append(EvalResult(case=case, prompt_status=prompt_status, matches_expected=matches, error=error))
        marker = "OK" if matches is True else "FLIP" if matches is False else "?"
        cluster_note = ""
        if case.cluster_headline and case.cluster_headline != case.headline:
            cluster_note = f" | cluster={_clean(case.cluster_headline, 80)}"
        print(
            f"[{idx:03d}] {marker:4s} original={case.original_status:<18s} "
            f"expected={case.expected_status or '-':<3s} prompt={prompt_status:<5s} "
            f"id={case.cluster_id[:8]} prod_headline={_clean(case.headline, 110)}{cluster_note}"
        )
        if error:
            print(f"      error={error}")
        if args.sleep:
            time.sleep(args.sleep)
    return results


def _summary(results: list[EvalResult]) -> None:
    print("\nSUMMARY")
    total = len(results)
    print(f"Total evaluated: {total}")
    by_pair: dict[tuple[str, str], int] = {}
    by_status: dict[str, dict[str, int]] = {}
    for result in results:
        original = result.case.original_status
        prompt = result.prompt_status
        by_pair[(original, prompt)] = by_pair.get((original, prompt), 0) + 1
        by_status.setdefault(original, {"total": 0, "matches": 0, "flips": 0, "errors": 0})
        by_status[original]["total"] += 1
        if result.error:
            by_status[original]["errors"] += 1
        elif result.matches_expected:
            by_status[original]["matches"] += 1
        elif result.matches_expected is False:
            by_status[original]["flips"] += 1

    print("\nBy original status:")
    for status, counts in sorted(by_status.items()):
        print(
            f"- {status}: total={counts['total']} "
            f"matches={counts['matches']} flips={counts['flips']} errors={counts['errors']}"
        )

    print("\nOriginal -> prompt result:")
    for (original, prompt), count in sorted(by_pair.items()):
        print(f"- {original} -> {prompt}: {count}")

    flips = [r for r in results if r.matches_expected is False]
    if flips:
        print("\nFLIPS / MISMATCHES")
        for result in flips:
            case = result.case
            print(
                f"- {case.cluster_id} original={case.original_status} "
                f"expected={case.expected_status} prompt={result.prompt_status} "
                f"headline={case.headline}"
            )


def _write_csv(results: list[EvalResult], csv_path: str) -> None:
    path = Path(csv_path)
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", newline="", encoding="utf-8") as fh:
        writer = csv.DictWriter(
            fh,
            fieldnames=[
                "cluster_id",
                "original_status",
                "expected_status",
                "prompt_status",
                "matches_expected",
                "cluster_headline",
                "headline",
                "description",
                "article_title",
                "source_domain",
                "size",
                "created_at",
                "updated_at",
                "error",
            ],
        )
        writer.writeheader()
        for result in results:
            case = result.case
            writer.writerow(
                {
                    "cluster_id": case.cluster_id,
                    "original_status": case.original_status,
                    "expected_status": case.expected_status,
                    "prompt_status": result.prompt_status,
                    "matches_expected": result.matches_expected,
                    "cluster_headline": case.cluster_headline,
                    "headline": case.headline,
                    "description": case.description,
                    "article_title": case.article_title,
                    "source_domain": case.source_domain,
                    "size": case.size,
                    "created_at": case.created_at,
                    "updated_at": case.updated_at,
                    "error": result.error,
                }
            )
    print(f"\nCSV written: {path}")


def main() -> int:
    args = _parse_args()
    cases = _fetch_cases(args)
    if not cases:
        print("No clusters matched the requested filters.")
        return 1

    print(
        f"Evaluating old_prompt.FILTER_PROMPT with model={args.model}; "
        f"cases={len(cases)}; since={_since_from_args(args).isoformat()}"
    )
    print()
    results = _evaluate(cases, args)
    _summary(results)
    if args.csv_path:
        _write_csv(results, args.csv_path)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

import json, uuid, hashlib, datetime as dt
import sqlalchemy as sa
from sqlalchemy import select
from sqlalchemy.dialects.postgresql import insert as pg_insert
from typing import Optional, Dict, Any, List

from ..db import (
    engine,
    generations, sources,
    summary_localized, slides, slide_localized,
    llm_runs,
)

def _strip_nul(s):
    if s is None:
        return None
    # ensure string, then remove NULs and normalize special characters
    s = str(s)
    if "\x00" in s:
        s = s.replace("\x00", "")
    # Replace common problematic Unicode characters with standard equivalents
    # Bullet points and similar characters → dash
    s = s.replace("•", "-").replace("▪", "-").replace("▫", "-").replace("‣", "-")
    s = s.replace("→", "-").replace("⇒", "-")
    # Em dash and en dash → regular dash
    s = s.replace("—", "-").replace("–", "-")
    # Other common problematic characters
    s = s.replace("'", "'").replace("'", "'")  # Smart quotes → straight quotes
    s = s.replace(""", '"').replace(""", '"')
    # Remove zero-width characters
    s = s.replace("\u200b", "").replace("\u200c", "").replace("\u200d", "")
    s = s.replace("\ufeff", "")  # BOM
    return s

def _sanitize(obj):
    """Recursively remove NULs from any string(s) inside Python structures."""
    if obj is None:
        return None
    if isinstance(obj, str):
        return _strip_nul(obj)
    if isinstance(obj, list):
        return [ _sanitize(v) for v in obj ]
    if isinstance(obj, tuple):
        return tuple(_sanitize(v) for v in obj)
    if isinstance(obj, dict):
        return { _sanitize(k): _sanitize(v) for k, v in obj.items() }
    # leave numbers, bools, datetimes as-is
    return obj

def _normalize_tag_name(name: str) -> str:
    """Normalize tag name: lowercase and replace spaces with underscores."""
    if not name:
        return name
    # Convert to lowercase and replace spaces with underscores
    return name.lower().replace(" ", "_")

def _normalize_seo_tag_name(name: str) -> str:
    """Normalize SEO tag name: lowercase and replace spaces with underscores."""
    if not name:
        return ""
    normalized = name.strip()
    if normalized.startswith("#"):
        normalized = normalized.lstrip("#").strip()
    # Convert to lowercase and replace spaces with underscores
    return normalized.lower().replace(" ", "_")

def _normalize_seo_tags(seo_tags: List[dict]) -> List[dict]:
    """Normalize all SEO tag names in a list, lowercasing and replacing spaces with underscores."""
    if not seo_tags:
        return seo_tags
    
    normalized_tags = []
    for tag in seo_tags:
        if isinstance(tag, dict) and "name" in tag:
            normalized_tag = tag.copy()
            normalized_tag["name"] = _normalize_seo_tag_name(tag["name"])
            # Also normalize linked_to_tag if present
            if "linked_to_tag" in normalized_tag and normalized_tag["linked_to_tag"]:
                normalized_tag["linked_to_tag"] = _normalize_seo_tag_name(normalized_tag["linked_to_tag"])
            normalized_tags.append(normalized_tag)
        else:
            normalized_tags.append(tag)
    
    return normalized_tags

def _normalize_tags(tags: List[dict]) -> List[dict]:
    """Normalize all tag names in a list of tag dictionaries."""
    if not tags:
        return tags

    normalized_tags = []
    for tag in tags:
        if isinstance(tag, dict) and "name" in tag:
            normalized_tag = tag.copy()
            normalized_tag["name"] = _normalize_tag_name(tag["name"])
            normalized_tags.append(normalized_tag)
        else:
            normalized_tags.append(tag)

    return normalized_tags

# ---------------- helpers ----------------
def _sha256(o: Any) -> str:
    return hashlib.sha256(
        json.dumps(o, sort_keys=True, ensure_ascii=False, default=str).encode("utf-8")
    ).hexdigest()

def _parse_ts(s: Optional[str]) -> Optional[dt.datetime]:
    if not s:
        return None
    try:
        return dt.datetime.fromisoformat(s.replace("Z", "+00:00"))
    except Exception:
        return None

def _normalize_datetime(dt_obj: Optional[dt.datetime]) -> Optional[dt.datetime]:
    """Normalize datetime to timezone-aware (UTC) for comparison."""
    if dt_obj is None:
        return None
    if dt_obj.tzinfo is None:
        # Make naive datetime timezone-aware (assume UTC)
        return dt_obj.replace(tzinfo=dt.timezone.utc)
    # Already timezone-aware, return as-is
    return dt_obj

def _normalize_url(url: Optional[str]) -> Optional[str]:
    if not url:
        return None
    return url.split("#", 1)[0].rstrip("/")

def _record_run(conn, cluster_id: uuid.UUID, artifact: str, generation_id: Optional[uuid.UUID], token_meta: Optional[dict]):
    if not token_meta:
        return
    tu = token_meta.get("token_usage") or {}
    conn.execute(
        pg_insert(llm_runs).values(
            id=uuid.uuid4(),
            cluster_id=cluster_id,
            generation_id=generation_id,
            artifact=artifact,
            model_name=token_meta.get("model_name"),
            system_fingerprint=token_meta.get("system_fingerprint"),
            provider_response_id=token_meta.get("id"),
            finish_reason=token_meta.get("finish_reason"),
            prompt_tokens=tu.get("prompt_tokens"),
            completion_tokens=tu.get("completion_tokens"),
            total_tokens=tu.get("total_tokens"),
            prompt_tokens_details=tu.get("prompt_tokens_details"),
            completion_tokens_details=tu.get("completion_tokens_details"),
            logprobs=token_meta.get("logprobs"),
            raw_payload=token_meta,
        )
    )

def _record_run_autonomous(cluster_id: uuid.UUID, artifact: str, generation_id: Optional[uuid.UUID], token_meta: Optional[dict]):
    if not token_meta:
        return
    with engine.begin() as c2:
        _record_run(c2, cluster_id, artifact, generation_id, token_meta)

def _insert_generation(conn, cluster_id: uuid.UUID, artifact: str, payload: dict, model_name: Optional[str], meta_block: dict) -> uuid.UUID:
    gid = uuid.uuid4()
    ih = _sha256(payload)
    ins = (
        pg_insert(generations)
        .values(
            id=gid,
            cluster_id=cluster_id,
            artifact=artifact,
            model_name=model_name,
            input_hash=ih,
            sources_used=(meta_block.get("sources_used") or []),
            sources_excluded=(meta_block.get("sources_excluded") or []),
            last_updated_article=_parse_ts(meta_block.get("last_updated_article")),
            confidence_score=meta_block.get("confidence_score"),
            extra=meta_block.get("extra"),
        )
        .on_conflict_do_update(
            index_elements=[generations.c.cluster_id, generations.c.artifact, generations.c.input_hash],
            set_={
                "model_name": sa.text("EXCLUDED.model_name"),
                "sources_used": sa.text("EXCLUDED.sources_used"),
                "sources_excluded": sa.text("EXCLUDED.sources_excluded"),
                "last_updated_article": sa.text("EXCLUDED.last_updated_article"),
                "confidence_score": sa.text("EXCLUDED.confidence_score"),
                "extra": sa.text("EXCLUDED.extra"),
            },
        )
        .returning(generations.c.id)
    )
    return conn.execute(ins).scalar_one()

# --------- dedup + upsert sources (fixes ON CONFLICT second-hit error) ----------
def _upsert_sources(conn, generation_id: uuid.UUID, srcs: List[dict]):
    if not srcs:
        return

    by_url = {}
    for s in srcs:
        url = _normalize_url(_strip_nul(s.get("url")))
        if not url:
            continue
        ad = _parse_ts(_strip_nul(s.get("date")))
        title = _strip_nul(s.get("title"))
        logo  = _strip_nul(s.get("logo"))

        if url not in by_url:
            by_url[url] = {"url": url, "title": title, "article_date": ad, "logo": logo}
        else:
            if title:
                by_url[url]["title"] = title
            if logo:
                by_url[url]["logo"] = logo
            if ad:
                normalized_ad = _normalize_datetime(ad)
                existing_date = _normalize_datetime(by_url[url]["article_date"])
                if existing_date is None or (normalized_ad and existing_date and normalized_ad > existing_date):
                    by_url[url]["article_date"] = ad

    rows = [
        {
            "id": uuid.uuid4(),
            "generation_id": generation_id,
            "url": v["url"],
            "title": _strip_nul(v.get("title")),
            "article_date": v.get("article_date"),
            "logo": _strip_nul(v.get("logo")),
        }
        for v in by_url.values()
    ]

    if rows:
        ins = pg_insert(sources).values(rows)
        conn.execute(
            ins.on_conflict_do_update(
                index_elements=[sources.c.generation_id, sources.c.url],
                set_={
                    "title": ins.excluded.title,
                    "article_date": ins.excluded.article_date,
                    "logo": ins.excluded.logo,
                },
            )
        )

# ---------- SEO Tags ----------
def save_seo_tags_to_db1(cluster_id: str, tags_data: dict) -> Optional[uuid.UUID]:
    """Save SEO tags to the summary generation's extra field."""
    cid = uuid.UUID(cluster_id)
    seo_tags = tags_data.get("seo_tags", [])
    
    if not seo_tags:
        return None
    
    # Normalize seo_tags before saving (replace spaces with underscores, preserve case)
    normalized_seo_tags = _normalize_seo_tags(seo_tags)
    
    try:
        with engine.begin() as conn:
            # Get the latest summary generation for this cluster
            gen = conn.execute(
                select(generations.c.id, generations.c.extra)
                .where(generations.c.cluster_id == cid, generations.c.artifact == "summary")
                .order_by(generations.c.created_at.desc())
                .limit(1)
            ).fetchone()
            
            if gen:
                extra = gen[1] or {}
                extra["seo_tags"] = _sanitize(normalized_seo_tags)
                
                conn.execute(
                    sa.update(generations)
                    .where(generations.c.id == gen[0])
                    .values(extra=extra)
                )
                return gen[0]
            else:
                # If no summary exists yet, create a minimal generation entry for tags
                meta_block = {"extra": {"seo_tags": _sanitize(normalized_seo_tags)}}
                gid = _insert_generation(conn, cid, "tags", tags_data, None, meta_block)
                return gid
    except Exception as e:
        print(f"Failed to save SEO tags: {e}")
        return None

# ---------- Summary ----------
def _save_summary(conn, cluster_id: uuid.UUID, data: dict, audio_by_lang: Optional[Dict[str, Dict[str, str]]]) -> uuid.UUID:
    data = _sanitize(data)  # <--- sanitize the whole payload early
    # NEW: Data is flat structure, not nested by language
    # NEW: No metadata field in new structure
    extra = {
        "classification": {
            "categories": data.get("classification", {}).get("categories", [])  # NEW: Only categories
        },
        "tags": _normalize_tags(data.get("tags", [])),  # NEW: Weighted tags with {name, weight}
        "faqs_en": data.get("faqs_en", []),  # NEW: Separate for each language
        "faqs_hi": data.get("faqs_hi", []),  # NEW: Separate for each language
        "google_news_queries": data.get("google_news_queries", [])  # NEW: Plain text queries
    }
    # sanitize extra as well (strings inside)
    md = {"extra": _sanitize(extra)}  # NEW: No metadata

    gid = _insert_generation(conn, cluster_id, "summary", data, None, md)  # NEW: No model_name from metadata
    _upsert_sources(conn, gid, data.get("sources"))

    def upsert_loc(lang_id: str, block: dict):
        # NEW: Extract from flat top-level data dict
        # NEW: No facts or quotes processing

        # NEW: Use title_en/hi directly for headline
        headline = _strip_nul(data.get("title_en") if lang_id == "en" else data.get("title_hi"))
        # Ensure headline is not empty or None - fallback to summary if needed
        if not headline or (isinstance(headline, str) and headline.strip() == ""):
            summary = data.get("summary_en") if lang_id == "en" else data.get("summary_hi")
            headline = _strip_nul(summary)
        # If still empty, use a generic fallback
        if not headline or (isinstance(headline, str) and headline.strip() == ""):
            headline = "News Update"
        if headline and headline[0].lower() != headline[0]:
            # Only capitalize if not already capitalized
            headline = headline[0].upper() + headline[1:] if len(headline) > 1 else headline[0].upper()
        # NEW: Use summary_en/hi directly, store as single-item array
        bullets = [data.get("summary_en") if lang_id == "en" else data.get("summary_hi")]
        # NEW: Get audio script from audio_scripts_summary
        audio_scripts = data.get("audio_scripts_summary") or {}
        audio_text = _strip_nul(audio_scripts.get(lang_id))

        # New: parse last_updated_at from payload, fallback to current time
        last_updated_at = _parse_ts(data.get("last_updated_at") or data.get("date"))
        if last_updated_at is None:
            last_updated_at = sa.func.now()
        
        # Extract audio URLs - handle both old format (dict[str, str]) and new format (dict[str, dict[str, str]])
        lang_audio = (audio_by_lang or {}).get(lang_id) or {}
        if isinstance(lang_audio, str):
            # Old format: direct string path
            audio_gist_url = lang_audio
            audio_full_story_url = None
        else:
            # New format: nested dict with 'gist' and 'full_story' keys
            audio_gist_url = lang_audio.get("gist")
            audio_full_story_url = lang_audio.get("full_story")
        
        ins = pg_insert(summary_localized).values(
            id=uuid.uuid4(),
            generation_id=gid,
            language_id=_strip_nul(lang_id),
            last_updated_at=last_updated_at,
            headline=headline,  # NEW: From title_en/hi
            mini_headline=None,  # NEW: Removed - set to None
            mini_summary=None,   # NEW: Removed - set to None
            audio_text=audio_text,  # NEW: From audio_scripts_summary (40-60 words)
            audio_s3_url=_strip_nul(audio_gist_url),
            audio_full_story_s3_url=_strip_nul(audio_full_story_url),
            bullets=bullets,  # NEW: Single-item array with summary text
            quotes=None,  # NEW: Removed - set to None
            facts=None,   # NEW: Removed - set to None
        )
        conn.execute(
            ins.on_conflict_do_update(
                index_elements=[summary_localized.c.generation_id, summary_localized.c.language_id],
                set_={
                    "last_updated_at": ins.excluded.last_updated_at,
                    "headline": ins.excluded.headline,
                    "mini_headline": None,  # NEW: Always set to None
                    "mini_summary": None,   # NEW: Always set to None
                    "audio_text": ins.excluded.audio_text,
                    "audio_s3_url": sa.func.coalesce(ins.excluded.audio_s3_url, summary_localized.c.audio_s3_url),
                    "audio_full_story_s3_url": sa.func.coalesce(ins.excluded.audio_full_story_s3_url, summary_localized.c.audio_full_story_s3_url),
                    "bullets": ins.excluded.bullets,
                    "quotes": None,  # NEW: Always set to None
                    "facts": None,   # NEW: Always set to None
                },
            )
        )

    upsert_loc("en", {})  # NEW: Empty dict, extract from top-level data
    upsert_loc("hi", {})  # NEW: Empty dict, extract from top-level data
    return gid

# ---------- Story So Far ----------
def _save_story_so_far(conn, cluster_id: uuid.UUID, data: dict) -> uuid.UUID:
    data = _sanitize(data)
    story = data.get("story_so_far") or {}
    audio_script = data.get("audio_script") or {}

    extra = {
        "story_type": story.get("type"),
        "title": story.get("title"),
        "audio_script": audio_script,
        "skipped_reason": story.get("reason"),
    }
    md = {"extra": _sanitize(extra)}

    gid = _insert_generation(conn, cluster_id, "story_so_far", data, None, md)
    _upsert_sources(conn, gid, data.get("sources"))

    seq = 1

    def upsert_loc_slide(slide_id, lang_id, block):
        if not block:
            return
        block = _sanitize(block)
        ins = pg_insert(slide_localized).values(
            id=uuid.uuid4(),
            slide_id=slide_id,
            language_id=_strip_nul(lang_id),
            success=bool(block.get("success")) or False,
            failure_reason=_strip_nul(block.get("failure_reason")),
            heading=_strip_nul(block.get("heading")),
            content_type="raw",
            content=_sanitize(block.get("content") or []),
        )
        conn.execute(
            ins.on_conflict_do_update(
                index_elements=[slide_localized.c.slide_id, slide_localized.c.language_id],
                set_={
                    "success": ins.excluded.success,
                    "failure_reason": ins.excluded.failure_reason,
                    "heading": ins.excluded.heading,
                    "content_type": ins.excluded.content_type,
                    "content": ins.excluded.content,
                },
            )
        )

    def insert_slide(slide_type: str, en_block: dict, hi_block: dict):
        nonlocal seq
        sid = conn.execute(
            pg_insert(slides)
            .values(id=uuid.uuid4(), generation_id=gid, type=_strip_nul(slide_type), sequence=seq)
            .returning(slides.c.id)
        ).scalar_one()
        seq += 1
        upsert_loc_slide(sid, "en", en_block)
        upsert_loc_slide(sid, "hi", hi_block)

    def build_blocks(heading_en: Optional[str], heading_hi: Optional[str], content_en, content_hi):
        en_block = {
            "success": True,
            "failure_reason": None,
            "heading": heading_en,
            "content": content_en,
        }
        hi_block = {
            "success": True,
            "failure_reason": None,
            "heading": heading_hi,
            "content": content_hi,
        }
        return en_block, hi_block

    story_type = story.get("type")
    title_block = story.get("title") or {}

    if story_type == "timeline":
        entries = story.get("entries") or []
        content_en = [
            {
                "date": e.get("date"),
                "text": e.get("event"),
                "source_id": e.get("source_id") or [],
            }
            for e in entries
        ]
        content_hi = [
            {
                "date": e.get("date"),
                "text": e.get("event_hi"),
                "source_id": e.get("source_id") or [],
            }
            for e in entries
        ]
        en_block, hi_block = build_blocks(title_block.get("en"), title_block.get("hi"), content_en, content_hi)
        insert_slide("timeline", en_block, hi_block)

    elif story_type == "concepts_decoded":
        concepts = story.get("concepts") or []
        content_en = [
            {
                "heading": c.get("concept_en") or c.get("concept"),
                "text": [c.get("explanation_en")],
                "source_id": c.get("source_id") or [],
            }
            for c in concepts
        ]
        content_hi = [
            {
                "heading": c.get("concept_hi") or c.get("concept"),
                "text": [c.get("explanation_hi")],
                "source_id": c.get("source_id") or [],
            }
            for c in concepts
        ]
        en_block, hi_block = build_blocks(title_block.get("en"), title_block.get("hi"), content_en, content_hi)
        insert_slide("concepts_decoded", en_block, hi_block)

    # If skipped, we intentionally do not create slides (reason captured in metadata)

    return gid


# ---------- Looking Ahead ----------
def _map_sentiment_to_impact(sentiment: str) -> str:
    """Convert new sentiment values to database impact format."""
    sentiment_lower = (sentiment or "").lower()
    if sentiment_lower in ("hopeful", "supportive"):
        return "positive"
    elif sentiment_lower in ("worried", "opposed"):
        return "negative"
    else:  # neutral, uncertain, or any other
        return "neutral"


def _save_looking_ahead(conn, cluster_id: uuid.UUID, data: dict) -> uuid.UUID:
    """Save looking ahead data with new looking_ahead.py structure."""
    # Extract FAQs in same format as summary
    faqs_data = data.get("faqs", {})
    extra = {
        "faqs_en": faqs_data.get("faqs_en", []),
        "faqs_hi": faqs_data.get("faqs_hi", []),
        "audio_script": data.get("audio_script", {})
    }
    
    # No metadata in new structure, so pass empty dict
    gid = _insert_generation(conn, cluster_id, "looking_ahead", data, None, {"extra": extra})
    _upsert_sources(conn, gid, data.get("sources"))

    seq = 1

    def maybe_make_slide(slide_type, en_block, hi_block):
        nonlocal seq
        if not ((en_block or {}).get("content") or (hi_block or {}).get("content")): 
            return None
        sid = conn.execute(
            pg_insert(slides)
            .values(id=uuid.uuid4(), generation_id=gid, type=slide_type, sequence=seq)
            .returning(slides.c.id)
        ).scalar_one()
        seq += 1
        return sid

    def upsert_loc_slide(slide_id, lang_id, block):
        if not block:
            return
        block = _sanitize(block)
        ins = pg_insert(slide_localized).values(
            id=uuid.uuid4(),
            slide_id=slide_id,
            language_id=_strip_nul(lang_id),
            success=bool(block.get("success")),
            failure_reason=_strip_nul(block.get("failure_reason")),
            heading=_strip_nul(block.get("heading")),
            content_type="raw",
            content=_sanitize(block.get("content") or []),
        )
        conn.execute(
            ins.on_conflict_do_update(
                index_elements=[slide_localized.c.slide_id, slide_localized.c.language_id],
                set_={
                    "success": ins.excluded.success,
                    "failure_reason": ins.excluded.failure_reason,
                    "heading": ins.excluded.heading,
                    "content_type": ins.excluded.content_type,
                    "content": ins.excluded.content,
                },
            )
        )

    # Process stakeholder impact from new structure
    stakeholder_impact_slide = data.get("stakeholder_impact_slide", {})
    entries = stakeholder_impact_slide.get("entries", [])
    
    if entries:
        # Transform to existing StakeHolderContent format
        # Store both original sentiment and mapped impact for backward compatibility
        en_content = [
            {
                "heading": entry.get("stakeholder_name_en") or entry.get("stakeholder_name", ""),
                "text": [entry.get("stakeholder_impact_en", "")],
                "source_id": [],
                "impact": _map_sentiment_to_impact(entry.get("stakeholder_sentiment", "")),
                "sentiment": (entry.get("stakeholder_sentiment", "")).lower()
            }
            for entry in entries
        ]
        hi_content = [
            {
                "heading": entry.get("stakeholder_name_hi") or entry.get("stakeholder_name", ""),
                "text": [entry.get("stakeholder_impact_hi", "")],
                "source_id": [],
                "impact": _map_sentiment_to_impact(entry.get("stakeholder_sentiment", "")),
                "sentiment": (entry.get("stakeholder_sentiment", "")).lower()
            }
            for entry in entries
        ]
        
        en_block = {
            "success": True,
            "failure_reason": None,
            "heading": "Ripple Effect",  # Default title
            "content": en_content
        }
        hi_block = {
            "success": True,
            "failure_reason": None,
            "heading": "इसका असर",  # Default title
            "content": hi_content
        }
        
        sid = maybe_make_slide("stakeholder_impact", en_block, hi_block)
        if sid:
            upsert_loc_slide(sid, "en", en_block)
            upsert_loc_slide(sid, "hi", hi_block)

    # Process scenarios from new structure
    scenarios_section = data.get("scenarios", {})
    scenario_entries = scenarios_section.get("entries", [])
    
    if scenario_entries:
        # Transform to existing ScenarioContent format
        en_scenario_content = []
        hi_scenario_content = []
        
        for entry in scenario_entries:
            scenario_en_raw = entry.get("scenario_en", [])
            scenario_hi_raw = entry.get("scenario_hi", [])
            
            # Handle backward compatibility: convert strings to arrays, preserve arrays
            if isinstance(scenario_en_raw, list):
                # New format: already an array
                scenario_en = scenario_en_raw if scenario_en_raw else []
            elif isinstance(scenario_en_raw, str) and scenario_en_raw.strip():
                # Old format: single sentence string -> convert to single-item array
                scenario_en = [scenario_en_raw.strip()]
            else:
                # Empty or invalid -> use empty array
                scenario_en = []
            
            if isinstance(scenario_hi_raw, list):
                # New format: already an array
                scenario_hi = scenario_hi_raw if scenario_hi_raw else []
            elif isinstance(scenario_hi_raw, str) and scenario_hi_raw.strip():
                # Old format: single sentence string -> convert to single-item array
                scenario_hi = [scenario_hi_raw.strip()]
            else:
                # Empty or invalid -> use empty array
                scenario_hi = []
            
            time_horizon = entry.get("time_horizon", "")
            probability = entry.get("probability_pct", 50)
            scenario_type = entry.get("scenario_type", "neutral")
            
            # Map scenario_type to sentiment format (capitalize first letter)
            sentiment_map = {
                "positive": "Positive",
                "negative": "Negative",
                "neutral": "Neutral"
            }
            sentiment = sentiment_map.get(scenario_type, "Neutral")
            
            # For description and implications, join array for backward compatibility with existing structure
            scenario_en_str = " | ".join(scenario_en) if scenario_en else ""
            scenario_hi_str = " | ".join(scenario_hi) if scenario_hi else ""
            
            en_scenario_content.append({
                "scenario": scenario_en,  # Save as array
                "description": scenario_en_str,  # Joined string for backward compatibility
                "probability": probability,
                "implications": scenario_en_str,  # Joined string for backward compatibility
                "source_id": [],
                "timeframe": time_horizon,
                "sentiment": sentiment
            })
            hi_scenario_content.append({
                "scenario": scenario_hi,  # Save as array
                "description": scenario_hi_str,  # Joined string for backward compatibility
                "probability": probability,
                "implications": scenario_hi_str,  # Joined string for backward compatibility
                "source_id": [],
                "timeframe": time_horizon,
                "sentiment": sentiment
            })
        
        en_scenario_block = {
            "success": True,
            "failure_reason": None,
            "heading": "Next Drop",  # Default title
            "content": en_scenario_content
        }
        hi_scenario_block = {
            "success": True,
            "failure_reason": None,
            "heading": "आगे क्या?",  # Default title
            "content": hi_scenario_content
        }
        
        sid = maybe_make_slide("scenarios", en_scenario_block, hi_scenario_block)
        if sid:
            upsert_loc_slide(sid, "en", en_scenario_block)
            upsert_loc_slide(sid, "hi", hi_scenario_block)

    return gid

# ---------- Public entrypoint (per-artifact tx + safe failure logging) ----------
def save_llm_outputs_to_db1(
    cluster_id: str,
    summary: Optional[dict] = None,
    story_so_far_dict: Optional[dict] = None,
    looking_ahead_dict: Optional[dict] = None,
    token_meta_summary: Optional[dict] = None,
    token_meta_story: Optional[dict] = None,
    token_meta_looking: Optional[dict] = None,
    audio_by_lang: Optional[Dict[str, Dict[str, str]]] = None,
    seo_tags: Optional[dict] = None,
) -> dict:
    cid = uuid.UUID(cluster_id)
    out = {"summary": None, "story_so_far": None, "looking_ahead": None, "seo_tags": None}

    # summary
    try:
        if summary:
            with engine.begin() as conn:
                gid = _save_summary(conn, cid, summary, audio_by_lang)
                out["summary"] = gid
                _record_run(conn, cid, "summary", gid, token_meta_summary)
        elif token_meta_summary:
            _record_run_autonomous(cid, "summary", None, token_meta_summary)
    except Exception:
        _record_run_autonomous(cid, "summary", None, token_meta_summary)
        raise

    # story so far
    try:
        if story_so_far_dict:
            with engine.begin() as conn:
                gid = _save_story_so_far(conn, cid, story_so_far_dict)
                out["story_so_far"] = gid
                _record_run(conn, cid, "story_so_far", gid, token_meta_story)
        elif token_meta_story:
            _record_run_autonomous(cid, "story_so_far", None, token_meta_story)
    except Exception:
        _record_run_autonomous(cid, "story_so_far", None, token_meta_story)
        raise

    # looking ahead
    try:
        if looking_ahead_dict:
            with engine.begin() as conn:
                gid = _save_looking_ahead(conn, cid, looking_ahead_dict)
                out["looking_ahead"] = gid
                _record_run(conn, cid, "looking_ahead", gid, token_meta_looking)
        elif token_meta_looking:
            _record_run_autonomous(cid, "looking_ahead", None, token_meta_looking)
    except Exception:
        _record_run_autonomous(cid, "looking_ahead", None, token_meta_looking)
        raise

    # SEO tags
    if seo_tags:
        try:
            tag_gid = save_seo_tags_to_db1(cluster_id, seo_tags)
            out["seo_tags"] = tag_gid
        except Exception as e:
            print(f"Failed to save SEO tags: {e}")

    return out

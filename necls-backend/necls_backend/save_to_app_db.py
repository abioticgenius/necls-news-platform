import uuid
import os
import json
from typing import Optional, List, Dict
import sqlalchemy as sa
from sqlalchemy.dialects.postgresql import insert as pg_insert

from .db import (
    # DB1 meta/engine are not required here; pass engines to the fn below
    generations, summary_localized, slides, slide_localized, sources as db1_sources, db2_links,
    articles,
    story_members,
    ensure_db1_schema,
)

from .app_db import (
    meta2,
    category, event, event_analysis, event_so_far, source,
    localized_event_data, localized_event_so_far, localized_event_analysis,
    language as language_tbl, logos, seo_tag, event_seo_tag, event_faq,
    collection, collection_seo_tag, app_config,
)

from .output_structure.structure import transform_slide_content, _approved_categories, _COUNTRY_NAMES

def _get_placeholder_patterns(db2) -> List[str]:
    """
    Fetch active placeholder patterns from the app_config table.
    
    Returns a list of pattern strings that should be filtered out.
    """
    try:
        result = db2.execute(
            sa.select(app_config.c.config_value)
            .where(app_config.c.config_key == 'image_placeholder_patterns')
        ).scalar_one_or_none()
        
        if result:
            # config_value is JSONB array, convert to list of strings
            if isinstance(result, list):
                return [str(p) for p in result if p]
            elif isinstance(result, dict) and 'patterns' in result:
                # Handle object format if needed
                return [str(p) for p in result.get('patterns', []) if p]
            else:
                # Try to parse as JSON if it's a string
                import json
                if isinstance(result, str):
                    parsed = json.loads(result)
                    if isinstance(parsed, list):
                        return [str(p) for p in parsed if p]
        
        # If no config found or invalid format, return default patterns
        return _get_default_placeholder_patterns()
    except Exception as e:
        return _get_default_placeholder_patterns()

def _get_default_placeholder_patterns() -> List[str]:
    """Return default placeholder patterns as fallback."""
    return [
        'placeholder', 'default', 'logo', 'branding', 'favicon', 
        'icon', 'watermark',
        '/logo.', '/icon.', '/favicon.', '/branding.', '/watermark.',
        'logo.png', 'logo.jpg', 'logo.jpeg', 'logo.gif',
        'icon.png', 'icon.jpg', 'favicon.ico',
        'branding.png', 'branding.jpg',
        'theprint', 'ap-news', 'apnews', 'associated-press', 'associatedpress',
        'site-logo', 'site_logo', 'header-logo', 'header_logo',
        'footer-logo', 'footer_logo', 'nav-logo', 'nav_logo',
    ]

def _is_placeholder_image(image_url: Optional[str], placeholder_patterns: List[str]) -> bool:
    """
    Check if an image URL is likely a placeholder, logo, or branding image.
    
    Args:
        image_url: The image URL to check
        placeholder_patterns: List of patterns to match against
    
    Returns True if the image URL matches any placeholder pattern.
    """
    if not image_url:
        return True
    
    url_lower = image_url.lower()
    return any(pattern.lower() in url_lower for pattern in placeholder_patterns)

def _build_image_filter_conditions(image_column, placeholder_patterns: List[str]):
    """
    Build SQLAlchemy conditions to filter out placeholder images.
    
    Args:
        image_column: The SQLAlchemy column to filter
        placeholder_patterns: List of patterns to filter out
    
    Returns a list of conditions that can be used in .where() clauses.
    """
    # Convert patterns to SQL LIKE patterns (add % wildcards)
    sql_patterns = [f'%{pattern}%' for pattern in placeholder_patterns]
    
    # Build conditions: image_url NOT LIKE each pattern
    conditions = [~image_column.ilike(pattern) for pattern in sql_patterns]
    return conditions

def _lookup_logo_id(db2, url: str):
    if not url:
        return None
    def host(expr):
        return sa.func.regexp_replace(
            sa.func.split_part(sa.func.split_part(sa.func.lower(expr), '://', 2), '/', 1),
            r'^www\.', ''
        )
    source_host = host(sa.literal(url))
    logo_host = host(logos.c.website)
    join_cond = sa.or_(
        source_host == logo_host,
        source_host.like(sa.func.concat('%.', logo_host))
    )
    stmt = sa.select(logos.c.id).where(join_cond).limit(1)
    return db2.execute(stmt).scalar_one_or_none()

def _ensure_language(db2, lang_id: str):
    name = {"en": "English", "hi": "Hindi"}.get(lang_id, lang_id)
    db2.execute(
        pg_insert(language_tbl)
        .values(id=lang_id, name=name)
        .on_conflict_do_update(index_elements=[language_tbl.c.id], set_={"name": sa.text("EXCLUDED.name")})
    )

def _ensure_category(db2, name: str) -> uuid.UUID:
    row = db2.execute(sa.select(category.c.id).where(category.c.name == name)).scalar_one_or_none()
    if row: return row
    cid = uuid.uuid4()
    db2.execute(pg_insert(category).values(id=cid, name=name).on_conflict_do_nothing(index_elements=[category.c.name]))
    return cid

def _normalize_seo_tag_name(tag_name: str) -> str:
    """Normalize SEO tag name: lowercase and replace spaces with underscores."""
    if not tag_name:
        return ""
    normalized = tag_name.strip()
    if normalized.startswith("#"):
        normalized = normalized.lstrip("#").strip()
    # Convert to lowercase and replace spaces with underscores
    return normalized.lower().replace(" ", "_")

def _is_approved_primary_category_name(name: str) -> bool:
    cats = _approved_categories()  # DB-backed, 5-min cache, falls back to hardcoded default
    return bool(name and name.strip().lower() in {c.lower() for c in cats})

def _ensure_seo_tag(db2, tag_name: str, tag_type: str = "tag") -> Optional[uuid.UUID]:
    """Get or create a SEO tag by name + type. Returns SEO tag ID.
    Handles case-sensitivity by querying case-insensitively first.
    Normalizes tag names by lowercasing and replacing spaces with underscores.
    """
    normalized = _normalize_seo_tag_name(tag_name)
    if not normalized:
        return None

    # Check for existing tag (case-insensitive match)
    existing_row = db2.execute(
        sa.select(seo_tag.c.id)
        .where(
            sa.func.lower(seo_tag.c.name) == normalized.lower(),
            seo_tag.c.type == tag_type,
        )
    ).first()
    
    if existing_row:
        return existing_row[0]

    # Create new tag (constraint handles duplicates from race conditions)
    # Use index_elements instead of constraint name for better compatibility
    seo_tag_id = uuid.uuid4()
    db2.execute(
        pg_insert(seo_tag)
        .values(id=seo_tag_id, name=normalized, type=tag_type)
        .on_conflict_do_nothing(index_elements=["name", "type"])
    )

    # Re-fetch in case of race condition (another process inserted it)
    row = db2.execute(
        sa.select(seo_tag.c.id)
        .where(
            sa.func.lower(seo_tag.c.name) == normalized.lower(),
            seo_tag.c.type == tag_type,
        )
    ).scalar_one_or_none()
    return row or seo_tag_id


def _delete_event_seo_tags_of_type(db2, event_id: uuid.UUID, tag_type: str):
    subquery = (
        sa.select(seo_tag.c.id)
        .where(seo_tag.c.type == tag_type)
        .scalar_subquery()
    )
    db2.execute(
        sa.delete(event_seo_tag).where(
            event_seo_tag.c.event_id == event_id,
            event_seo_tag.c.seo_tag_id.in_(subquery),
        )
    )


def _sync_weighted_seo_tags(
    db2,
    event_id: uuid.UUID,
    items: list,
    tag_type: str,
    default_weight: int = 50,
    strip_hash: bool = False,
):
    if not items:
        return

    normalized_items = []
    for item in items:
        if isinstance(item, dict):
            name = (item.get("name") or "").strip()
            weight = item.get("weight", default_weight)
        else:
            name = str(item).strip()
            weight = default_weight

        if strip_hash:
            name = name.lstrip("#").strip()

        if not name:
            continue

        try:
            weight_int = int(weight)
        except (TypeError, ValueError):
            weight_int = default_weight
        weight_int = max(0, min(100, weight_int))

        normalized_items.append((name, weight_int))

    if not normalized_items:
        return

    tag_ids = []
    for name, weight in normalized_items:
        seo_tag_id = _ensure_seo_tag(db2, name, tag_type)
        if seo_tag_id:
            tag_ids.append((seo_tag_id, weight))

    if not tag_ids:
        return

    _delete_event_seo_tags_of_type(db2, event_id, tag_type)

    for seo_tag_id, weight in tag_ids:
        db2.execute(
            pg_insert(event_seo_tag)
            .values(
                id=uuid.uuid4(),
                event_id=event_id,
                seo_tag_id=seo_tag_id,
                weight=weight,
            )
            .on_conflict_do_update(
                index_elements=[event_seo_tag.c.event_id, event_seo_tag.c.seo_tag_id],
                set_={"weight": weight, "created_date": sa.func.now()},
            )
        )


def _sync_event_faqs(db2, event_id: uuid.UUID, faqs: list, language_id: str):
    """Replace FAQs for an event in a specific language."""
    _ensure_language(db2, language_id)
    
    if not faqs:
        # Delete all FAQs if empty list provided
        db2.execute(
            sa.delete(event_faq).where(
                event_faq.c.event_id == event_id,
                event_faq.c.language_id == language_id
            )
        )
        return

    # Delete existing FAQs for this event/language first
    db2.execute(
        sa.delete(event_faq).where(
            event_faq.c.event_id == event_id,
            event_faq.c.language_id == language_id
        )
    )

    # Insert new FAQs (use upsert pattern to handle any race conditions)
    for idx, faq in enumerate(faqs):
        question = (faq.get("question") or "").strip()
        answer = (faq.get("answer") or "").strip()
        if not question or not answer:
            continue

        db2.execute(
            pg_insert(event_faq)
            .values(
                id=uuid.uuid4(),
                event_id=event_id,
                language_id=language_id,
                question=question,
                answer=answer,
                sequence=idx,
            )
            .on_conflict_do_update(
                index_elements=[event_faq.c.event_id, event_faq.c.language_id, event_faq.c.question],
                set_={
                    "answer": sa.text("EXCLUDED.answer"),
                    "sequence": sa.text("EXCLUDED.sequence"),
                    "created_date": sa.func.now()
                }
            )
        )

def _sync_seo_tags(db2, event_id: uuid.UUID, seo_tags_list: list):
    """Sync SEO tags for an event. Removes old SEO tags and adds new ones."""
    if not seo_tags_list:
        return

    # Process tags with new structure: {name, type, relevance_type, linked_to_tag, weight}
    tags_to_save = []
    tag_name_to_id_map = {}  # Map tag names to their IDs for resolving linked_to_tag
    
    # First pass: create/get all tags and build name-to-id map
    for t in seo_tags_list:
        if isinstance(t, dict):
            tag_name = (t.get("name") or "").strip()
            tag_type = t.get("type", "tag")  # Default to "tag" for backward compatibility
            weight = t.get("weight", 60)
            
            if not tag_name:
                continue

            # Guard 1: country names must always be Place, never Entity
            if tag_type == "Entity" and tag_name.lower() in _COUNTRY_NAMES:
                tag_type = "Place"

            # Guard 2: approved category names must always be saved as Category type
            if tag_type != "Category" and _is_approved_primary_category_name(tag_name):
                tag_type = "Category"

            if str(tag_type).strip().lower() == "category" and not _is_approved_primary_category_name(tag_name):
                continue
            
            # Normalize tag name before processing (replace spaces with underscores)
            normalized_tag_name = _normalize_seo_tag_name(tag_name)
            if not normalized_tag_name:
                continue
            
            # Ensure tag exists and get its ID
            seo_tag_id = _ensure_seo_tag(db2, normalized_tag_name, tag_type)
            if seo_tag_id:
                tags_to_save.append({
                    "seo_tag_id": seo_tag_id,
                    "name": normalized_tag_name,  # Store normalized name
                    "type": tag_type,
                    # Enforce wiring rules — never trust stored value for typed tags
                    "relevance_type": (
                        "Core" if tag_type in ("Category", "Core Event")
                        else "Contextual" if tag_type in ("Sub Category", "Associated Event", "Impact")
                        else t.get("relevance_type") or "Contextual"  # Entity / Place: trust LLM
                    ),
                    "linked_to_tag": t.get("linked_to_tag"),  # Can be None or string (will be normalized when used)
                    "weight": max(0, min(100, int(weight) if isinstance(weight, (int, float)) else 60))
                })
                # Use normalized name for lookup
                tag_name_to_id_map[normalized_tag_name.lower()] = seo_tag_id
        elif isinstance(t, str):
            # Handle string format (backward compatibility)
            tag_name = t.strip().lstrip("#").strip()
            if tag_name:
                normalized_tag_name = _normalize_seo_tag_name(tag_name)
                if normalized_tag_name:
                    seo_tag_id = _ensure_seo_tag(db2, normalized_tag_name, "tag")
                    if seo_tag_id:
                        tags_to_save.append({
                            "seo_tag_id": seo_tag_id,
                            "name": normalized_tag_name,  # Store normalized name
                            "type": "tag",
                            "relevance_type": "Contextual",
                            "linked_to_tag": None,
                            "weight": 60
                        })
                        # Use normalized name for lookup
                        tag_name_to_id_map[normalized_tag_name.lower()] = seo_tag_id
    
    if not tags_to_save:
        return
    
    # Delete existing tags for this event (only tags that will be replaced)
    # Get unique tag IDs that will be saved
    tag_ids_to_replace = [tag["seo_tag_id"] for tag in tags_to_save]
    if tag_ids_to_replace:
        db2.execute(
            sa.delete(event_seo_tag).where(
                sa.and_(
                    event_seo_tag.c.event_id == event_id,
                    event_seo_tag.c.seo_tag_id.in_(tag_ids_to_replace)
                )
            )
        )
    
    # Second pass: save tags with role and linked_to_tag_id
    for tag_data in tags_to_save:
        seo_tag_id = tag_data["seo_tag_id"]
        relevance_type = tag_data["relevance_type"]
        linked_to_tag_name = tag_data["linked_to_tag"]

        # Map relevance_type to role
        role = "core" if relevance_type == "Core" else "contextual"

        # Resolve linked_to_tag_id - normalize the linked_to_tag name before lookup
        linked_to_tag_id = None
        if linked_to_tag_name:
            normalized_linked_name = _normalize_seo_tag_name(linked_to_tag_name)
            if normalized_linked_name and normalized_linked_name.lower() in tag_name_to_id_map:
                linked_to_tag_id = tag_name_to_id_map[normalized_linked_name.lower()]

        # Save event_seo_tag
        db2.execute(
            pg_insert(event_seo_tag)
            .values(
                id=uuid.uuid4(),
                event_id=event_id,
                seo_tag_id=seo_tag_id,
                weight=tag_data["weight"],
                role=role,
                linked_to_tag_id=linked_to_tag_id,
            )
            .on_conflict_do_update(
                index_elements=[event_seo_tag.c.event_id, event_seo_tag.c.seo_tag_id],
                set_={
                    "weight": tag_data["weight"],
                    "role": role,
                    "linked_to_tag_id": linked_to_tag_id,
                    "created_date": sa.func.now()
                },
            )
        )
    
def _get_backup_image_s3_uri(categories_list: list, event_id: uuid.UUID) -> Optional[str]:
    """
    Generate S3 URI for backup image based on event category.
    
    Args:
        categories_list: List of category dicts from classification.categories
        event_id: Event UUID for deterministic image selection
    
    Returns:
        S3 URI string (e.g., 's3://necls-backend-adhoc/backup-images/Sports/3.jpg') or None
    """
    # Read config from env
    bucket = os.getenv("BACKUP_IMAGES_BUCKET", "necls-backend-adhoc")
    prefix = os.getenv("BACKUP_IMAGES_PREFIX", "backup-images")
    
    # Determine category name
    category_name = "Explainers & Features"  # Default fallback
    
    if categories_list and len(categories_list) > 0:
        first_cat = categories_list[0]
        if isinstance(first_cat, dict):
            cat_name = first_cat.get("name", "").strip()
            if cat_name:
                category_name = cat_name
    
    # All categories have 4 backup images
    image_count = 4
    
    # Deterministic index selection
    event_id_str = str(event_id)
    hash_val = abs(hash(event_id_str))
    index = 1 + (hash_val % image_count)
    
    # Construct S3 URI - normalize path to avoid double slashes
    # Remove any leading/trailing slashes and join properly
    prefix_clean = prefix.strip('/')
    category_clean = category_name.strip('/')
    key = f"{prefix_clean}/{category_clean}/{index}.png"
    s3_uri = f"s3://{bucket}/{key}"
    
    return s3_uri

def _get_or_create_event(
    db1,
    db2,
    cluster_id: uuid.UUID,
    ts,
    image_url: str,
    article_type: Optional[str] = None,
    sources_used_urls: Optional[set] = None,
    placeholder_patterns: Optional[List[str]] = None,
    image_source_url: Optional[str] = None,
) -> uuid.UUID:
    link = db1.execute(
        sa.select(db2_links.c.db2_event_id).where(db2_links.c.cluster_id == cluster_id)
    ).scalar_one_or_none()
    if link:
        # Verify the event actually exists (handle orphaned links)
        event_exists = db2.execute(
            sa.select(event.c.id).where(event.c.id == link)
        ).scalar_one_or_none()
        
        if event_exists:
            # Event exists, update it
            update_payload = {
                "time_stamp": ts,
                "article_type": article_type,
            }
            # Only update image if we have a new one and it's better than the current one
            if image_url and placeholder_patterns and not _is_placeholder_image(image_url, placeholder_patterns):
                current_image = db2.execute(
                    sa.select(event.c.image).where(event.c.id == link)
                ).scalar_one_or_none()
                
                # Check if current image is missing or looks like a placeholder
                is_placeholder = _is_placeholder_image(current_image, placeholder_patterns) if placeholder_patterns else False
                
                # Only update if current image is missing/placeholder, or if new image is from a source_used article
                should_update_image = False
                if not current_image or is_placeholder:
                    should_update_image = True
                elif sources_used_urls:
                    # Check if new image is from a more relevant source (used in summary)
                    # Use passed image_source_url if available, otherwise query for it
                    new_article_url = image_source_url
                    if not new_article_url:
                        new_article_url = db1.execute(
                            sa.select(articles.c.url)
                            .join(story_members, story_members.c.article_id == articles.c.id)
                            .where(
                                story_members.c.cluster_id == cluster_id,
                                articles.c.image_url == image_url
                            )
                            .limit(1)
                        ).scalar_one_or_none()
                    
                    if new_article_url and new_article_url in sources_used_urls:
                        # Check if current image is also from a source_used article
                        current_article_url = db1.execute(
                            sa.select(articles.c.url)
                            .join(story_members, story_members.c.article_id == articles.c.id)
                            .where(
                                story_members.c.cluster_id == cluster_id,
                                articles.c.image_url == current_image
                            )
                            .limit(1)
                        ).scalar_one_or_none()
                        
                        # Update if new image is from source_used but current is not
                        if not (current_article_url and current_article_url in sources_used_urls):
                            should_update_image = True
                
                if should_update_image:
                    update_payload["image"] = image_url
                    if image_source_url:
                        update_payload["image_source_url"] = image_source_url
            
            db2.execute(sa.update(event).where(event.c.id == link).values(**update_payload))
            db1.execute(
                sa.update(db2_links)
                .where(db2_links.c.cluster_id == cluster_id)
                .values(last_synced_at=sa.func.now())
            )
            return link
        else:
            # Link exists but event doesn't - orphaned link, create new event
            print(f"WARN: Orphaned link found for cluster {cluster_id}, creating new event")
            # Fall through to create new event below
    ev_id = uuid.uuid4()
    db2.execute(
        pg_insert(event).values(
            id=ev_id,
            image=image_url,
            image_source_url=image_source_url,
            time_stamp=ts,
            article_type=article_type,
        )
    )
    db1.execute(
        pg_insert(db2_links)
        .values(cluster_id=cluster_id, db2_event_id=ev_id)
        .on_conflict_do_update(
            index_elements=[db2_links.c.cluster_id],
            set_={
                "db2_event_id": sa.text("EXCLUDED.db2_event_id"),
                "last_synced_at": sa.func.now(),
            },
        )
    )
    return ev_id


def _upsert_source(db2, event_id: uuid.UUID, url: str, title: str):
    if not url:
        return
    logo_id = _lookup_logo_id(db2, url)
    values = {"title": title, "logo_id": logo_id}
    sid = uuid.uuid4()
    db2.execute(
        pg_insert(source)
        .values(id=sid, event_id=event_id, source_url=url, **values)
        .on_conflict_do_update(
            index_elements=[source.c.event_id, source.c.source_url],
            set_=values
        )
    )
    # Return the ID (either newly inserted or existing)
    return db2.execute(
        sa.select(source.c.id).where(
            source.c.event_id == event_id, source.c.source_url == url
        )
    ).scalar_one()

def _get_or_create_seq(db2, table, event_id: uuid.UUID, sequence: int) -> uuid.UUID:
    rid = uuid.uuid4()
    result = db2.execute(
        pg_insert(table)
        .values(id=rid, event_id=event_id, sequence=sequence)
        .on_conflict_do_nothing(
            index_elements=[table.c.event_id, table.c.sequence]
        )
        .returning(table.c.id)
    )
    inserted_id = result.scalar_one_or_none()
    if inserted_id:
        return inserted_id
    # If conflict occurred, fetch existing row
    return db2.execute(
        sa.select(table.c.id).where(
            table.c.event_id == event_id, table.c.sequence == sequence
        )
    ).scalar_one()

def _replace_localized(db2, table, fk_col, fk_id, lang_id: str, content, content_type: str, extra_cols: dict = None):
    _ensure_language(db2, lang_id)
    db2.execute(sa.delete(table).where(fk_col == fk_id, table.c.language_id == lang_id))
    payload = {"id": uuid.uuid4(), "language_id": lang_id, fk_col.name: fk_id,
               "content": content, "content_type": content_type}
    if extra_cols:
        payload.update(extra_cols)
    db2.execute(pg_insert(table).values(**payload))

# ---------- main ETL ----------
def export_cluster_to_db2(cluster_id: str, db1_engine, db2_engine) -> dict:
    """
    Pulls the latest per-artifact generations from DB1 (minimal schema) and writes to DB2 (snake_case).
    Returns: {"event_id": UUID, "so_far": {seq:id}, "analysis": {seq:id}}
    
    Ensures DB1 schema is up to date before syncing (creates tables and adds missing columns).
    """
    # Ensure DB1 schema is initialized (creates tables and adds missing columns)
    ensure_db1_schema()
    
    # ensure_seo_tag_enum() is called once in sync_app_db.py before any syncs
    
    cid = uuid.UUID(cluster_id)
    result = {"event_id": None, "so_far": {}, "analysis": {}}

    with db1_engine.begin() as db1, db2_engine.begin() as db2:
        # Fetch active placeholder patterns from database
        placeholder_patterns = _get_placeholder_patterns(db2)
        
        # latest generation per artifact
        def latest_gen(artifact: str):
            return db1.execute(
                sa.select(generations.c.id, generations.c.extra, generations.c.last_updated_article)
                .where(generations.c.cluster_id == cid, generations.c.artifact == artifact)
                .order_by(generations.c.created_at.desc())
                .limit(1)
            ).mappings().first()

        g_summary = latest_gen("summary")
        g_story   = latest_gen("story_so_far")
        g_look    = latest_gen("looking_ahead")

        if not g_summary:
            return result  # can't form an event without a summary

        # Check if all headlines are the fallback "News Update" (indicates content generation failed)
        gen_summary_id = g_summary["id"]
        headlines = db1.execute(
            sa.select(summary_localized.c.headline)
            .where(summary_localized.c.generation_id == gen_summary_id)
        ).scalars().all()

        # Skip sync if all headlines are just "News Update" (content generation fallback)
        if headlines and all(h and h.strip() == "News Update" for h in headlines):
            print(f"[SKIP] Cluster {cluster_id}: All headlines are 'News Update' (content generation failed)")
            return result

        extra = g_summary.get("extra") or {}
        classification = extra.get("classification") or {}
        
        categories_list = classification.get("categories") or []
        article_type = classification.get("article_type")

        # choose event timestamp: use max fetched_at from articles in cluster
        event_ts = db1.execute(
            sa.select(sa.func.max(articles.c.fetched_at))
            .join(story_members, story_members.c.article_id == articles.c.id)
            .where(story_members.c.cluster_id == cid)
        ).scalar_one_or_none()

        # Get sources_used from the summary generation to prefer images from relevant articles
        # Need to fetch the full generation record to get sources_used
        gen_full = db1.execute(
            sa.select(generations.c.sources_used)
            .where(generations.c.id == gen_summary_id)
        ).scalar_one_or_none()
        sources_used = gen_full if gen_full else []
        sources_used_urls = set(sources_used) if sources_used else set()

        # First, try to get image from articles that were actually used in the summary
        image_url = None
        image_source_url = None
        if sources_used_urls:
            image_row = db1.execute(
                sa.select(articles.c.image_url, articles.c.url)
                .select_from(
                    articles.join(
                        story_members, story_members.c.article_id == articles.c.id
                    )
                )
                .where(
                    story_members.c.cluster_id == cid,
                    articles.c.image_url.isnot(None),
                    articles.c.url.in_(sources_used_urls),  # Prefer sources used in summary
                    ~articles.c.source_domain.ilike('%uniindia%'),  # Exclude uniindia sources
                    ~articles.c.source_domain.ilike('%ptinews%'),  # Exclude PTI sources
                    # Filter out placeholder images using comprehensive pattern matching
                    *_build_image_filter_conditions(articles.c.image_url, placeholder_patterns),
                )
                .order_by(articles.c.date_publish.desc())  # Newest first
                .limit(1)
            ).first()
            
            if image_row:
                image_url = image_row[0]  # First column is image_url
                image_source_url = image_row[1]  # Second column is url

        # Fallback: if no image from sources_used, get from any article in cluster
        if not image_url:
            image_row = db1.execute(
                sa.select(articles.c.image_url, articles.c.url)
                .select_from(
                    articles.join(
                        story_members, story_members.c.article_id == articles.c.id
                    )
                )
                .where(
                    story_members.c.cluster_id == cid,
                    articles.c.image_url.isnot(None),
                    ~articles.c.source_domain.ilike('%uniindia%'),  # Exclude uniindia sources
                    ~articles.c.source_domain.ilike('%ptinews%'),  # Exclude PTI sources
                    # Filter out placeholder images using comprehensive pattern matching
                    *_build_image_filter_conditions(articles.c.image_url, placeholder_patterns),
                )
                .order_by(articles.c.date_publish.desc())  # Newest first (changed from .asc())
                .limit(1)
            ).first()
            
            if image_row:
                image_url = image_row[0]  # First column is image_url
                image_source_url = image_row[1]  # Second column is url

        # Filter out placeholder images before creating/updating event
        final_image_url = image_url if image_url and not _is_placeholder_image(image_url, placeholder_patterns) else None
        final_image_source_url = image_source_url if final_image_url else None

        # If no image found, use backup image based on category
        if not final_image_url:
            # categories_list is already extracted at line 719, so it's available
            backup_uri = _get_backup_image_s3_uri(categories_list, cid)  # Use cluster_id as event_id isn't created yet
            if backup_uri:
                final_image_url = backup_uri
                final_image_source_url = None  # No source URL for backup images
        

        ev_id = _get_or_create_event(
            db1,
            db2,
            cid,
            event_ts,
            final_image_url,  # This will be backup S3 URI if no article image found
            article_type=article_type,
            sources_used_urls=sources_used_urls,
            placeholder_patterns=placeholder_patterns,
            image_source_url=final_image_source_url,
        )

        result["event_id"] = ev_id


        # Process categories: all categories stored as type='Category' with their weights
        
        # Delete existing category associations for this event
        db2.execute(
            sa.delete(event_seo_tag)
            .where(
                event_seo_tag.c.event_id == ev_id,
                event_seo_tag.c.seo_tag_id.in_(
                    sa.select(seo_tag.c.id).where(seo_tag.c.type == "Category")
                )
            )
        )
        
        # Store categories with type='Category' and their weights
        if categories_list:
            for cat in categories_list:
                if not isinstance(cat, dict):
                    continue
                    
                tag_name = cat.get("name")
                weight = cat.get("weight", 50)
                
                if not tag_name:
                    continue
                
                if not _is_approved_primary_category_name(tag_name):
                    continue
                
                seo_tag_id = _ensure_seo_tag(db2, tag_name, tag_type="Category")
                if seo_tag_id:
                    db2.execute(
                        pg_insert(event_seo_tag)
                        .values(
                            id=uuid.uuid4(),
                            event_id=ev_id,
                            seo_tag_id=seo_tag_id,
                            weight=weight,
                            role="core",  # Category tags are ALWAYS Core
                        )
                        .on_conflict_do_update(
                            index_elements=[event_seo_tag.c.event_id, event_seo_tag.c.seo_tag_id],
                            set_={"weight": weight, "role": "core", "created_date": sa.func.now()},
                        )
                    )
        
        # Topic (main subject/entity) stored as type='topic'
        topic_name = classification.get("topic")
        if topic_name:
            # Delete existing topic associations
            db2.execute(
                sa.delete(event_seo_tag)
                .where(
                    event_seo_tag.c.event_id == ev_id,
                    event_seo_tag.c.seo_tag_id.in_(
                        sa.select(seo_tag.c.id).where(seo_tag.c.type == "topic")
                    )
                )
            )
            
            topic_id = _ensure_seo_tag(db2, topic_name, tag_type="topic")
            if topic_id:
                db2.execute(
                    pg_insert(event_seo_tag)
                    .values(
                        id=uuid.uuid4(),
                        event_id=ev_id,
                        seo_tag_id=topic_id,
                        weight=95,
                    )
                    .on_conflict_do_update(
                        index_elements=[event_seo_tag.c.event_id, event_seo_tag.c.seo_tag_id],
                        set_={"weight": 95, "created_date": sa.func.now()},
                    )
                )
        
        # Sync SEO tags from summary extra field (preferred - new format with relations)
        seo_tags_list = extra.get("seo_tags") or []
        if seo_tags_list:
            _sync_seo_tags(db2, ev_id, seo_tags_list)
        else:
            # Fallback to old tags format only if seo_tags doesn't exist
            tags_list = extra.get("tags") or []
            if tags_list:
                _sync_seo_tags(db2, ev_id, tags_list)

        # Handle both old and new FAQ formats with backward compatibility
        # Extract FAQs from summary generation
        summary_faqs_en = extra.get("faqs_en") or []
        summary_faqs_hi = extra.get("faqs_hi") or []
        old_faqs = extra.get("faqs") or []

        # Extract FAQs from looking_ahead generation (if exists)
        looking_faqs_en = []
        looking_faqs_hi = []
        if g_look:
            look_extra = g_look.get("extra") or {}
            looking_faqs_en = look_extra.get("faqs_en") or []
            looking_faqs_hi = look_extra.get("faqs_hi") or []

        # Combine FAQs: summary first, then looking_ahead
        combined_faqs_en = summary_faqs_en + looking_faqs_en
        combined_faqs_hi = summary_faqs_hi + looking_faqs_hi

        # Sync English FAQs (new format or old format fallback)
        if combined_faqs_en:
            _sync_event_faqs(db2, ev_id, combined_faqs_en, "en")
        elif old_faqs:
            _sync_event_faqs(db2, ev_id, old_faqs, "en")

        # Sync Hindi FAQs (only new format)
        if combined_faqs_hi:
            _sync_event_faqs(db2, ev_id, combined_faqs_hi, "hi")

        # upsert sources (union across present generations)
        gen_ids = [gen_summary_id] + [g_story["id"]] * bool(g_story) + [g_look["id"]] * bool(g_look)
        if gen_ids:
            for row in db1.execute(
                sa.select(db1_sources.c.url,
                          db1_sources.c.title)
                .where(db1_sources.c.generation_id.in_(gen_ids))
            ).mappings().all():
                _upsert_source(db2, ev_id, row["url"],  row.get("title"))

        # LocalizedEventData from summary_localized
        locs = db1.execute(
            sa.select(
                summary_localized.c.language_id,
                summary_localized.c.headline,
                summary_localized.c.audio_s3_url,
                summary_localized.c.audio_full_story_s3_url,
                summary_localized.c.bullets,
                summary_localized.c.quotes
            ).where(summary_localized.c.generation_id == gen_summary_id)
        ).mappings().all()
        for loc in locs:
            # Extract summary text from bullets array (summary_en/hi stored as first item)
            bullets_array = loc.get("bullets") or []
            summary_text = bullets_array[0] if bullets_array else None
            
            _replace_localized(
                db2, localized_event_data, localized_event_data.c.event_id, ev_id,
                loc["language_id"],
                content=summary_text, content_type="text",
                extra_cols={
                    "title": loc["headline"],
                    "description": None,  # Description should be empty - summary is in content field
                    "audio": loc["audio_s3_url"],
                    "audio_full_story": loc["audio_full_story_s3_url"],
                    "quotes": loc["quotes"],
                }
            )

        # STORY SO FAR -> event_so_far / localized_event_so_far
        if g_story:
            story_gen_id = g_story["id"]
            srows = db1.execute(
                sa.select(slides.c.id, slides.c.sequence, slides.c.type)
                .where(slides.c.generation_id == story_gen_id)
                .order_by(slides.c.sequence.asc())
            ).mappings().all()
            for sr in srows:
                seq = sr["sequence"] or 1
                esf_id = _get_or_create_seq(db2, event_so_far, ev_id, seq)
                result["so_far"][seq] = esf_id

                lrows = db1.execute(
                    sa.select(slide_localized.c.language_id, slide_localized.c.heading, slide_localized.c.content)
                    .where(slide_localized.c.slide_id == sr["id"])
                ).mappings().all()
                for lr in lrows:
                    ctype, content = transform_slide_content(sr["type"], lr["content"], lr.get("heading"))
                    _replace_localized(
                        db2, localized_event_so_far, localized_event_so_far.c.event_so_far_id, esf_id,
                        lr["language_id"], content, ctype
                    )

            # LOOKING AHEAD -> event_analysis / localized_event_analysis
        if g_look:
            look_gen_id = g_look["id"]
            arows = db1.execute(
                sa.select(slides.c.id, slides.c.sequence, slides.c.type)
                .where(slides.c.generation_id == look_gen_id)
                .order_by(slides.c.sequence.asc())
            ).mappings().all()
            for ar in arows:
                seq = ar["sequence"] or 1
                ea_id = _get_or_create_seq(db2, event_analysis, ev_id, seq)
                result["analysis"][seq] = ea_id

                lrows = db1.execute(
                    sa.select(slide_localized.c.language_id, slide_localized.c.heading, slide_localized.c.content)
                    .where(slide_localized.c.slide_id == ar["id"])
                ).mappings().all()
                for lr in lrows:
                    ctype, content = transform_slide_content(ar["type"], lr["content"], lr.get("heading"))
                    _replace_localized(
                        db2, localized_event_analysis, localized_event_analysis.c.event_analysis_id, ea_id,
                        lr["language_id"], content, ctype
                    )
        
        # Index assistant chunks for this event (automatic after sync)
        try:
            # Try to import index_assistant_chunks if it exists (optional feature)
            try:
                from .index_assistant_chunks import index_event
            except ImportError:
                # Module doesn't exist, skip indexing (this is optional)
                return
            from .config import settings
            from fastembed import TextEmbedding
            # Initialize embedding model (reuse if possible, but create new for each sync to avoid issues)
            embedding_model = TextEmbedding(settings.model_id)
            # Delete existing chunks first (in case of re-sync)
            db2.execute(sa.text("DELETE FROM assistant_chunks WHERE event_id = :event_id"), {"event_id": str(ev_id)})
            # Index the event
            chunks_created = index_event(str(ev_id), db2, embedding_model, verbose=False)
        except ImportError:
            pass  # Optional module not installed
        except Exception as e:
            # Don't fail the entire sync if chunk indexing fails
            print(f"[ERROR] Failed to index assistant chunks for event {ev_id}: {e}")
        
        return result


def delete_cluster_from_db2(cluster_id: str, db1_engine, db2_engine) -> bool:
    """Delete a cluster's event from DB2 and remove its db2_links row.

    Returns True if an event was found and removed, allowing the cluster to be
    re-exported cleanly.
    """
    cid = uuid.UUID(cluster_id)
    with db1_engine.begin() as db1:
        ev_id = db1.execute(
            sa.select(db2_links.c.db2_event_id).where(db2_links.c.cluster_id == cid)
        ).scalar_one_or_none()
        if not ev_id:
            return False
        with db2_engine.begin() as db2:
            # remove localized analysis and analysis rows
            ea_ids = sa.select(event_analysis.c.id).where(event_analysis.c.event_id == ev_id)
            db2.execute(
                sa.delete(localized_event_analysis).where(
                    localized_event_analysis.c.event_analysis_id.in_(ea_ids)
                )
            )
            db2.execute(sa.delete(event_analysis).where(event_analysis.c.event_id == ev_id))

            # remove localized story-so-far and story rows
            esf_ids = sa.select(event_so_far.c.id).where(event_so_far.c.event_id == ev_id)
            db2.execute(
                sa.delete(localized_event_so_far).where(
                    localized_event_so_far.c.event_so_far_id.in_(esf_ids)
                )
            )
            db2.execute(sa.delete(event_so_far).where(event_so_far.c.event_id == ev_id))

            # remove event metadata (event_seo_tag will be auto-deleted via CASCADE)
            db2.execute(sa.delete(localized_event_data).where(localized_event_data.c.event_id == ev_id))
            db2.execute(sa.delete(source).where(source.c.event_id == ev_id))
            db2.execute(sa.delete(event).where(event.c.id == ev_id))

        db1.execute(sa.delete(db2_links).where(db2_links.c.cluster_id == cid))
        return True

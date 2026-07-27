"""Standalone SVD tag vectorization script.

Computes 128-dimensional SVD embeddings for seo_tag rows using the
event_seo_tag co-occurrence matrix, with blending across linked tags
via event_seo_tag.linked_to_tag_id.

First run: recomputes ALL tags.
Subsequent runs: only rewrites embeddings for tags where vector_updated_at IS NULL
or where new event_seo_tag rows appeared after the last vector_updated_at.

Usage (from repo root):
    python -m scripts.compute_tag_vectors
"""
from __future__ import annotations

import sys
import uuid
import logging
from datetime import datetime, timezone
from pathlib import Path

import gc
import numpy as np
from scipy.sparse import lil_matrix, csr_matrix, coo_matrix
from sklearn.decomposition import TruncatedSVD
from sklearn.feature_extraction.text import TfidfTransformer
from sklearn.preprocessing import normalize
import sqlalchemy as sa

ROOT = Path(__file__).resolve().parent.parent
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from necls_backend.app_db import (
    engine, seo_tag, event_seo_tag
)

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
log = logging.getLogger(__name__)

N_COMPONENTS = 128
LINK_WEIGHT = 0.4   # weight multiplier for events blended in via linked_to_tag_id
MIN_EVENTS = 5      # tags with fewer distinct events get embedding=NULL (falls back to match_count)


def _fetch_data(conn: sa.engine.Connection):
    """Return all tags, events, and event-tag rows needed to build the matrix."""
    tags = conn.execute(sa.select(seo_tag.c.id, seo_tag.c.vector_updated_at)).fetchall()
    tag_id_list = [r[0] for r in tags]
    tag_index = {tid: i for i, tid in enumerate(tag_id_list)}

    events = conn.execute(
        sa.select(sa.func.distinct(event_seo_tag.c.event_id))
    ).fetchall()
    event_id_list = [r[0] for r in events]
    event_index = {eid: i for i, eid in enumerate(event_id_list)}

    est_rows = conn.execute(
        sa.select(
            event_seo_tag.c.seo_tag_id,
            event_seo_tag.c.event_id,
            event_seo_tag.c.weight,
            event_seo_tag.c.role,
            event_seo_tag.c.linked_to_tag_id,
        )
    ).fetchall()

    return tag_id_list, tag_index, event_id_list, event_index, est_rows


def _build_matrix(tag_id_list, tag_index, event_id_list, event_index, est_rows):
    """Build the sparse tag x event co-occurrence matrix.

    Blending: when tag A declares linked_to_tag_id = B on any event, A and B
    exchange event signals at LINK_WEIGHT so their embeddings are pulled together.
    """
    n_tags = len(tag_id_list)
    n_events = len(event_index)

    mat = lil_matrix((n_tags, n_events), dtype=np.float32)

    # Direct event contributions
    for seo_tag_id, event_id, weight, role, _link in est_rows:
        ti = tag_index.get(seo_tag_id)
        ei = event_index.get(event_id)
        if ti is None or ei is None:
            continue
        score = (weight / 100.0) * (1.5 if role == "core" else 1.0)
        mat[ti, ei] += score

    # Vectorised link blending: build a sparse tag→tag adjacency matrix then
    # blend via matrix multiplication instead of nested Python loops.
    # Equivalent semantics to the original loop but runs in seconds rather
    # than tens of minutes on large datasets.
    link_i, link_j = [], []
    seen_links: set = set()
    for seo_tag_id, _eid, _w, _r, linked_to_tag_id in est_rows:
        if linked_to_tag_id is None:
            continue
        ti_src = tag_index.get(seo_tag_id)
        ti_dst = tag_index.get(linked_to_tag_id)
        if ti_src is None or ti_dst is None:
            continue
        key = (ti_src, ti_dst)
        if key not in seen_links:
            seen_links.add(key)
            link_i.append(ti_src)
            link_j.append(ti_dst)

    mat_csr = csr_matrix(mat)
    if link_i:
        ones = np.ones(len(link_i), dtype=np.float32)
        link_mat = coo_matrix(
            (ones, (link_i, link_j)), shape=(n_tags, n_tags)
        ).tocsr()
        # Symmetric blend: each tag absorbs event signals from tags it links to
        # AND from tags that link back to it — same as the original loop logic.
        blend = LINK_WEIGHT * (link_mat.dot(mat_csr) + link_mat.T.dot(mat_csr))
        mat_csr = mat_csr + blend

    return mat_csr


def _detect_dirty_tags(tags_with_ts, est_rows) -> set:
    """Return IDs of tags that need their embedding refreshed.

    A tag is dirty when:
      - vector_updated_at IS NULL
      - OR any of its event_seo_tag rows were created after vector_updated_at
        (we approximate this by checking if vector_updated_at is not None; the
         full incremental query runs in SQL below via _fetch_dirty_tag_ids)
    """
    return {tid for tid, ts in tags_with_ts if ts is None}


def _fetch_dirty_tag_ids(conn: sa.engine.Connection) -> set:
    """Tags with NULL vector_updated_at OR with new event_seo_tag rows since last update."""
    rows = conn.execute(sa.text("""
        SELECT DISTINCT st.id
        FROM seo_tag st
        WHERE st.vector_updated_at IS NULL
           OR EXISTS (
               SELECT 1 FROM event_seo_tag est
               WHERE est.seo_tag_id = st.id
                 AND est.created_date > st.vector_updated_at
           )
    """)).fetchall()
    return {r[0] for r in rows}


def main() -> None:
    log.info("Starting tag SVD vectorization")

    with engine.begin() as conn:
        tag_id_list, tag_index, event_id_list, event_index, est_rows = _fetch_data(conn)

    n_tags = len(tag_id_list)
    n_events = len(event_index)
    n_links = sum(1 for *_, linked_id in est_rows if linked_id is not None)
    log.info("Loaded %d tags, %d events, %d event-tag rows (%d with linked_to_tag_id)",
             n_tags, n_events, len(est_rows), n_links)

    if n_tags == 0 or n_events == 0:
        log.warning("Nothing to compute — no tags or events found")
        return

    # Determine which tags need a write (partial rebuild optimisation)
    with engine.connect() as conn:
        dirty_tag_ids = _fetch_dirty_tag_ids(conn)

    log.info("%d tags are dirty and need embedding updates", len(dirty_tag_ids))
    if not dirty_tag_ids:
        log.info("All embeddings are up-to-date, nothing to do")
        return

    # Build the full co-occurrence matrix (SVD is always global)
    log.info("Building tag x event matrix (%d x %d)", n_tags, n_events)
    mat = _build_matrix(tag_id_list, tag_index, event_id_list, event_index, est_rows)

    # Count distinct events per tag before est_rows is freed.
    # Used below to skip the embedding for tags with too few events.
    tag_event_sets: dict = {}
    for seo_tag_id, event_id, *_ in est_rows:
        if seo_tag_id not in tag_event_sets:
            tag_event_sets[seo_tag_id] = set()
        tag_event_sets[seo_tag_id].add(event_id)
    events_per_tag = {tid: len(evts) for tid, evts in tag_event_sets.items()}
    del tag_event_sets

    del est_rows, tag_id_list, event_id_list, event_index
    gc.collect()

    # Apply TF-IDF weighting before SVD (standard LSA approach).
    # IDF down-weights events shared by many tags so that tags with few events
    # are no longer projected onto the same dominant "popular topics" direction,
    # preventing sparse tags from collapsing to near-identical embeddings.
    log.info("Applying TF-IDF weighting to co-occurrence matrix")
    tfidf = TfidfTransformer(norm=None, use_idf=True, smooth_idf=True, sublinear_tf=True)
    mat = tfidf.fit_transform(mat)

    # Run TruncatedSVD
    n_components = max(1, min(N_COMPONENTS, n_tags - 1, n_events - 1))
    log.info("Running TruncatedSVD(n_components=%d)", n_components)
    svd = TruncatedSVD(n_components=n_components, random_state=42)
    embeddings = svd.fit_transform(mat)          # shape: (n_tags, n_components)
    embeddings = normalize(embeddings, norm="l2") # unit-length vectors

    # Pad to 128 dims if matrix was too small for full 128 components
    if embeddings.shape[1] < N_COMPONENTS:
        pad = np.zeros((embeddings.shape[0], N_COMPONENTS - embeddings.shape[1]), dtype=np.float32)
        embeddings = np.hstack([embeddings, pad])

    now = datetime.now(timezone.utc)

    # Bulk-write only dirty tags.
    # Tags with fewer than MIN_EVENTS distinct events receive embedding=NULL so
    # the query falls back to match_count ordering instead of using a low-signal
    # embedding that would collapse to the same "default" vector as other sparse tags.
    log.info("Writing embeddings for %d dirty tags", len(dirty_tag_ids))
    vec_updates = []
    null_updates = []
    for tid in dirty_tag_ids:
        ti = tag_index.get(tid)
        if ti is None:
            continue
        if events_per_tag.get(tid, 0) < MIN_EVENTS:
            null_updates.append({"_id": str(tid), "_ts": now})
        else:
            vec = embeddings[ti].tolist()
            vec_updates.append({"_id": str(tid), "_embedding": vec, "_ts": now})

    NULL_CHUNK = 2000   # rows per IN-clause batch for NULL updates
    with engine.begin() as conn:
        if null_updates:
            # executemany issues one SQL round-trip per row, which is far too slow
            # for ~50k rows. Use WHERE id IN (...) batches instead — one query per
            # chunk, reducing 50k round-trips to ~25.
            null_ids = [uuid.UUID(u["_id"]) for u in null_updates]
            for i in range(0, len(null_ids), NULL_CHUNK):
                chunk = null_ids[i:i + NULL_CHUNK]
                conn.execute(
                    sa.update(seo_tag)
                    .where(seo_tag.c.id.in_(chunk))
                    .values(embedding=None, vector_updated_at=now)
                )
        if vec_updates:
            conn.execute(sa.text("""
                UPDATE seo_tag
                SET embedding = CAST(:_embedding AS vector(128)),
                    vector_updated_at = :_ts
                WHERE id = CAST(:_id AS uuid)
            """), vec_updates)

    log.info("Done — updated %d tag embeddings (%d with vectors, %d set to NULL)",
             len(vec_updates) + len(null_updates), len(vec_updates), len(null_updates))


if __name__ == "__main__":
    main()

"""Incremental two‑phase clustering rewritten into a class."""
from __future__ import annotations

import argparse, uuid, datetime as dt
from typing import Dict, List, Sequence
from datetime import datetime
from zoneinfo import ZoneInfo
import numpy as np
import sqlalchemy as sa
from pgvector.sqlalchemy import Vector
from sklearn.cluster import AgglomerativeClustering
from fastembed import TextEmbedding

from .config import settings
from .db import (engine, articles, article_vectors, story_clusters, story_members, meta_clusters, meta_members,
                 pg_insert, EMB_DIM)


def cos_sim(a: np.ndarray, b: np.ndarray) -> np.ndarray:
    """Cosine similarity for 1D or 2D vectors."""
    a = np.atleast_2d(a)
    b = np.atleast_2d(b)
    a_norm = a / np.linalg.norm(a, axis=1, keepdims=True)
    b_norm = b / np.linalg.norm(b, axis=1, keepdims=True)
    return a_norm @ b_norm.T


class StoryClusterer:
    """Attach fresh articles → residual mini‑batch clustering."""

    THETA = 0.55  # centroid attach threshold (cos‑sim) - can be overridden in cluster_once()

    def __init__(self, model_id: str | None = None):
        self.model = TextEmbedding(model_id or settings.model_id)

    # ------------------- helpers -------------------
    @staticmethod
    def _to_utc(ts) -> dt.datetime:
        if isinstance(ts, dt.datetime):
            if ts.tzinfo is None:
                # If naive, assume it's in IST for legacy data (most common case)
                # This should rarely happen as dates should already be UTC from extractor
                return ts.replace(tzinfo=ZoneInfo("Asia/Kolkata")).astimezone(dt.timezone.utc)
            # Already timezone-aware, convert to UTC
            return ts.astimezone(dt.timezone.utc)
        return dt.datetime.now(dt.timezone.utc)

    def _article_ts(self, row: Dict) -> dt.datetime:
        return self._to_utc(row.get("date_publish") or row.get("fetched_at"))

    # ------------------- DB fetch / embed -------------
    def _fetch_unclustered(self) -> List[Dict]:
        with engine.connect() as conn:
            query = (
                sa.select(
                    articles.c.id,
                    articles.c.url,
                    articles.c.title,
                    articles.c.description,
                    articles.c.date_publish,
                    articles.c.fetched_at,
                )
                .outerjoin(
                    story_members,
                    story_members.c.article_id == articles.c.id,
                )
                .where(story_members.c.article_id.is_(None))
                .where(sa.or_(articles.c.is_gnews.is_(None), articles.c.is_gnews.is_(False)))
            )
            result = conn.execute(query)
            return result.mappings().all()

    def _embed(self, rows: Sequence[Dict]) -> np.ndarray:
        texts = [(r.get("title") or "") + " " + (r.get("description") or "")[:140] for r in rows]
        vecs = [np.array(v) for v in self.model.embed(texts)]
        return np.vstack(vecs) if vecs else np.empty((0, EMB_DIM))

    # ------------------- centroid attach --------------
    def _load_centroids(self, conn, center: dt.datetime, win: dt.timedelta | None):
        sel = sa.select(story_clusters.c.cluster_id,
                        story_clusters.c.centroid,
                        story_clusters.c.first_date,
                        story_clusters.c.last_date,
                        story_clusters.c.size)
        if win is not None:
            start = center - win
            end   = center + win
            sel = sel.where(story_clusters.c.first_date <= end,
                             story_clusters.c.last_date  >= start)
        return [(cid, np.array(cent), self._to_utc(f), self._to_utc(l), size)
                for cid, cent, f, l, size in conn.execute(sel)]

    def _load_centroids_range(self, conn, start: dt.datetime, end: dt.datetime):
        sel = sa.select(story_clusters.c.cluster_id,
                        story_clusters.c.centroid,
                        story_clusters.c.first_date,
                        story_clusters.c.last_date,
                        story_clusters.c.size)
        sel = sel.where(story_clusters.c.first_date <= end,
                        story_clusters.c.last_date >= start)
        return [(cid, np.array(cent), self._to_utc(f), self._to_utc(l), size)
                for cid, cent, f, l, size in conn.execute(sel)]
    
    def _load_all_centroids(self, conn):
        """Load all centroids without any date filtering."""
        sel = sa.select(story_clusters.c.cluster_id,
                        story_clusters.c.centroid,
                        story_clusters.c.first_date,
                        story_clusters.c.last_date,
                        story_clusters.c.size)
        return [(cid, np.array(cent), self._to_utc(f), self._to_utc(l), size)
                for cid, cent, f, l, size in conn.execute(sel)]

    def _centroid_attach(self, conn, vec: np.ndarray, ts: dt.datetime, win: dt.timedelta | None,
                         centroids: Sequence[tuple] | None = None):
        best_id, best_sim = None, -1.0
        cand = centroids if centroids is not None else self._load_centroids(conn, ts, win)
        for cid, cent, f, l, *_ in cand:
            if win is not None and (f > ts + win or l < ts - win or ts - f > win):
                continue
            sim = float(cos_sim(vec, cent)[0][0])
            if sim > best_sim:
                best_id, best_sim = cid, sim
        return best_id if best_sim >= self.THETA else None

    # ------------------- residual batched clustering ---
    def _group_by_time(self, rows: List[Dict], win: dt.timedelta | None):
        if not rows:
            return []
        if win is None:
            return [rows]
        rows_sorted = sorted(rows, key=self._article_ts)
        batches: List[List[Dict]] = []
        current = [rows_sorted[0]]
        start_ts = self._article_ts(rows_sorted[0])
        for r in rows_sorted[1:]:
            ts = self._article_ts(r)
            if ts - start_ts <= (win * 2):
                current.append(r)
            else:
                batches.append(current)
                current = [r]
                start_ts = ts
        batches.append(current)
        return batches

    def _cluster_alg(self, vecs: np.ndarray, algo: str, thr: float, min_size: int, min_samples: int):
        if len(vecs) == 1:
            return np.array([0])
        if algo == "agglom":
            model = AgglomerativeClustering(n_clusters=None, metric="cosine", linkage="average", distance_threshold=thr)
            return model.fit_predict(vecs)

    def _prepare_centroid_cache(self, centroids: Sequence[tuple] | None):
        """Convert centroid tuples into numpy arrays for fast lookup."""
        if not centroids:
            return None
        ids = np.array([cid for cid, *_ in centroids], dtype=object)
        vecs = np.vstack([cent for _, cent, *_ in centroids])
        first = np.array([f.timestamp() for _, _, f, _, _ in centroids])
        last = np.array([l.timestamp() for _, _, _, l, _ in centroids])
        return ids, vecs, first, last

    def _centroid_attach_fast(self, vec: np.ndarray, ts: dt.datetime,
                              win: dt.timedelta | None, cache, theta: float | None = None, debug: bool = False):
        """Vectorised centroid attach using precomputed arrays."""
        if cache is None:
            return None
        ids, cents, first, last = cache
        ts_val = ts.timestamp()
        
        if win is not None:
            w = win.total_seconds()
            mask = (first <= ts_val + w) & (last >= ts_val - w) & ((ts_val - first) <= w)
            if not mask.any():
                return None
            cents = cents[mask]
            ids = ids[mask]
        
        sims = cos_sim(vec, cents)[0]
        best = int(np.argmax(sims))
        best_sim = float(sims[best])
        threshold = theta if theta is not None else self.THETA
        
        if best_sim >= threshold:
            return ids[best]
        else:
            return None

    # ------------------- write helpers -------------------
    def _write_cluster(self, conn, members: Sequence[Dict], vecs: np.ndarray):
        cid = uuid.uuid4()
        ts_first = min(self._article_ts(r) for r in members)
        ts_last  = max(self._article_ts(r) for r in members)
        headline = members[0].get("title") or members[0]["url"]
        centroid = np.mean(vecs, axis=0).tolist()
        conn.execute(story_clusters.insert().values(
            cluster_id=cid, headline=headline,
            first_date=ts_first, last_date=ts_last,
            size=len(members), centroid=centroid,
        ))
        conn.execute(
            pg_insert(story_members)
            .values([{"cluster_id": cid, "article_id": r["id"]} for r in members])
            .on_conflict_do_update(index_elements=["cluster_id", "article_id"], set_={"updated_at": sa.func.now()})
        )

    def _time_split(self, members: List[Dict], win: dt.timedelta | None):
        """Yield sub-lists whose timestamps form an interval-connected component.

        A sub-list never spans more than 2·win in publication time.
        """
        if win is None or len(members) <= 1:
            yield members
            return

        members_sorted = sorted(members, key=self._article_ts)
        batches, batch = [], [members_sorted[0]]
        window_end = self._article_ts(batch[0]) + win

        for r in members_sorted[1:]:
            ts = self._article_ts(r)
            if ts - win <= window_end:  # overlaps running window
                batch.append(r)
                window_end = max(window_end, ts + win)  # extend union
            else:  # gap ⇒ start new component
                batches.append(batch)
                batch, window_end = [r], ts + win

        batches.append(batch)
        for b in batches:
            yield b

    # ------------------- public entrypoint -------------------
    def cluster_once(self, algo: str = "agglom", threshold: float = 0.25, min_size: int = 1,
                     min_samples: int = 2, days: float | None = None, theta: float | None = None, verbose: bool = False):
        win = dt.timedelta(days=days) if days is not None else None
        # Allow overriding THETA threshold for Phase 1 attach
        attach_theta = theta if theta is not None else self.THETA
        
        with engine.connect() as conn:
            skipped_gnews = conn.execute(
                sa.select(sa.func.count())
                .select_from(articles)
                .outerjoin(story_members, story_members.c.article_id == articles.c.id)
                .where(story_members.c.article_id.is_(None))
                .where(articles.c.is_gnews.is_(True))
            ).scalar() or 0

        fresh = self._fetch_unclustered()
        print(f"[CLUSTER][story] input_articles={len(fresh)} skipped_gnews={skipped_gnews}")
        if not fresh:
            return
        
        vecs = self._embed(fresh)
        residual_rows: List[Dict] = []
        residual_vecs: List[np.ndarray] = []
        with engine.begin() as conn:
            # embeddings table upsert
            conn.execute(
                pg_insert(article_vectors)
                .values([{"article_id": r["id"], "emb": v.tolist()} for r, v in zip(fresh, vecs)])
                .on_conflict_do_update(index_elements=["article_id"], set_={"emb": sa.text("EXCLUDED.emb"), "updated_at": sa.func.now()})
            )
            # Load ALL centroids when win is None (no time window filtering)
            if win is not None:
                ts_all = [self._article_ts(r) for r in fresh]
                start = min(ts_all) - win
                end = max(ts_all) + win
                centroids_all = self._load_centroids_range(conn, start, end)
            else:
                # No time window: load all centroids
                centroids_all = self._load_all_centroids(conn)
            
            cent_cache = self._prepare_centroid_cache(centroids_all)

            attachments: Dict[uuid.UUID, Dict] = {}
            attach_count = 0
            residual_count = 0
            
            # Track which clusters have been updated in this batch (for cache staleness detection)
            updated_clusters = set()
            
            for idx, (row, vec) in enumerate(zip(fresh, vecs)):
                ts = self._article_ts(row)
                cid = self._centroid_attach_fast(vec, ts, win, cent_cache, attach_theta, debug=False)
                
                if cid:
                    attach_count += 1
                    updated_clusters.add(cid)  # Track that this cluster was updated
                    att = attachments.get(cid)
                    if att is None:
                        attachments[cid] = {
                            "vec_sum": vec.copy(),
                            "count": 1,
                            "last_date": ts,
                            "members": [row["id"]],
                        }
                    else:
                        att["vec_sum"] += vec
                        att["count"] += 1
                        att["last_date"] = max(att["last_date"], ts)
                        att["members"].append(row["id"])
                else:
                    residual_count += 1
                    residual_rows.append(row)
                    residual_vecs.append(vec)
            
            if verbose:
                print(f"\n[DEBUG] [PHASE 1 SUMMARY]")
                print(f"  Total articles: {len(fresh)}")
                print(f"  Attached to clusters: {attach_count} ({attach_count/len(fresh)*100:.1f}%)")
                print(f"  Residuals: {residual_count} ({residual_count/len(fresh)*100:.1f}%)")
                print(f"  Clusters updated: {len(attachments)}")
                print(f"  Clusters updated multiple times: {sum(1 for att in attachments.values() if att['count'] > 1)}")

            if attachments:
                sel = sa.select(story_clusters.c.cluster_id,
                                story_clusters.c.size,
                                story_clusters.c.centroid,
                                story_clusters.c.last_date)
                sel = sel.where(story_clusters.c.cluster_id.in_(attachments.keys()))
                updates: List[Dict] = []
                member_rows: List[Dict] = []
                for cid, size, cent, last in conn.execute(sel):
                    info = attachments[cid]
                    new_size = size + info["count"]
                    new_cent = ((np.array(cent) * size) + info["vec_sum"]) / new_size
                    new_last = max(last, info["last_date"])
                    updates.append({
                        "pk": cid,
                        "size": new_size,
                        "centroid": new_cent.tolist(),
                        "last_date": new_last,
                    })
                    member_rows.extend({"cluster_id": cid, "article_id": m} for m in info["members"])

                if updates:
                    conn.execute(
                        story_clusters.update()
                        .where(story_clusters.c.cluster_id == sa.bindparam("pk"))
                        .values(size=sa.bindparam("size"),
                                centroid=sa.bindparam("centroid"),
                                last_date=sa.bindparam("last_date"),
                                updated_at=sa.func.now()),
                        updates,
                    )

                if member_rows:
                    conn.execute(
                        pg_insert(story_members)
                        .values(member_rows)
                        .on_conflict_do_update(index_elements=["cluster_id", "article_id"],
                                               set_={"updated_at": sa.func.now()})
                    )


            # phase 2 – residuals
            if residual_rows:
                full_vecs = np.vstack(residual_vecs)
                labels = self._cluster_alg(full_vecs, algo, threshold,
                                           min_size, min_samples)
                label2idxs: Dict[int, List[int]] = {}
                for i, lab in enumerate(labels):
                    label2idxs.setdefault(lab, []).append(i)

                new_clusters = 0
                noise_clusters = 0
                with engine.begin() as conn:
                    for lab, idxs in label2idxs.items():
                        if lab == -1:  # noise → one-article clusters
                            noise_clusters += len(idxs)
                            for i in idxs:
                                self._write_cluster(conn, [residual_rows[i]],
                                                    full_vecs[i:i + 1])
                            continue

                        members = [residual_rows[i] for i in idxs]
                        mvecs = full_vecs[idxs]

                        # --- NEW: split by time and write each sub-cluster -----------
                        for sub in self._time_split(members, win):
                            if not sub:
                                continue
                            svecs = np.vstack([mvecs[members.index(r)] for r in sub])
                            self._write_cluster(conn, sub, svecs)
                            new_clusters += 1
                
                if verbose:
                    print("Phase 2 done: ", datetime.now())
                    print(f"\n[DEBUG] [PHASE 2 SUMMARY]")
                    print(f"  New clusters created: {new_clusters}")
                    print(f"  Noise clusters (size=1): {noise_clusters}")
                    print(f"  Total new clusters: {new_clusters + noise_clusters}")


class MetaClusterer:
    """Incrementally cluster existing story clusters into meta clusters."""

    THETA = StoryClusterer.THETA

    @staticmethod
    def _to_utc(ts) -> dt.datetime:
        return StoryClusterer._to_utc(ts)

    def _cluster_ts(self, row: Dict) -> dt.datetime:
        return self._to_utc(row.get("last_date") or row.get("first_date"))

    # ------------------- DB helpers -------------------
    def _fetch_unclustered(self) -> List[Dict]:
        with engine.connect() as conn:
            query = (
                sa.select(
                    story_clusters.c.cluster_id,
                    story_clusters.c.headline,
                    story_clusters.c.first_date,
                    story_clusters.c.last_date,
                    story_clusters.c.centroid,
                )
                .outerjoin(
                    meta_members,
                    meta_members.c.cluster_id == story_clusters.c.cluster_id,
                )
                .where(meta_members.c.cluster_id.is_(None))
            )
            result = conn.execute(query)
            return result.mappings().all()

    def _load_centroids(self, conn, center: dt.datetime, win: dt.timedelta | None):
        sel = sa.select(meta_clusters.c.meta_id,
                        meta_clusters.c.centroid,
                        meta_clusters.c.first_date,
                        meta_clusters.c.last_date,
                        meta_clusters.c.size)
        if win is not None:
            start = center - win
            end = center + win
            sel = sel.where(meta_clusters.c.first_date <= end,
                            meta_clusters.c.last_date >= start)
        return [(cid, np.array(cent), self._to_utc(f), self._to_utc(l), size)
                for cid, cent, f, l, size in conn.execute(sel)]

    def _load_centroids_range(self, conn, start: dt.datetime, end: dt.datetime):
        sel = sa.select(meta_clusters.c.meta_id,
                        meta_clusters.c.centroid,
                        meta_clusters.c.first_date,
                        meta_clusters.c.last_date,
                        meta_clusters.c.size)
        sel = sel.where(meta_clusters.c.first_date <= end,
                        meta_clusters.c.last_date >= start)
        return [(cid, np.array(cent), self._to_utc(f), self._to_utc(l), size)
                for cid, cent, f, l, size in conn.execute(sel)]

    def _centroid_attach(self, conn, vec: np.ndarray, ts: dt.datetime, win: dt.timedelta | None,
                         centroids: Sequence[tuple] | None = None):
        best_id, best_sim = None, -1.0
        cand = centroids if centroids is not None else self._load_centroids(conn, ts, win)
        for cid, cent, f, l, *_ in cand:
            if win is not None and (f > ts + win or l < ts - win or ts - f > win):
                continue
            sim = float(cos_sim(vec, cent)[0][0])
            if sim > best_sim:
                best_id, best_sim = cid, sim
        return best_id if best_sim >= self.THETA else None

    # ------------------- helpers duplicated from StoryClusterer -------------------
    @staticmethod
    def _cluster_alg(vecs: np.ndarray, algo: str, thr: float, min_size: int, min_samples: int):
        if len(vecs) == 1:
            return np.array([0])
        if algo == "agglom":
            model = AgglomerativeClustering(n_clusters=None, metric="cosine", linkage="average", distance_threshold=thr)
            return model.fit_predict(vecs)

    @staticmethod
    def _time_split(members: List[Dict], win: dt.timedelta | None):
        if win is None or len(members) <= 1:
            yield members
            return

        members_sorted = sorted(members, key=lambda m: MetaClusterer._to_utc(m.get("last_date") or m.get("first_date")))
        batches, batch = [], [members_sorted[0]]
        window_end = MetaClusterer._to_utc(batch[0].get("last_date") or batch[0].get("first_date")) + win

        for r in members_sorted[1:]:
            ts = MetaClusterer._to_utc(r.get("last_date") or r.get("first_date"))
            if ts - win <= window_end:
                batch.append(r)
                window_end = max(window_end, ts + win)
            else:
                batches.append(batch)
                batch, window_end = [r], ts + win

        batches.append(batch)
        for b in batches:
            yield b

    def _prepare_centroid_cache(self, centroids: Sequence[tuple] | None):
        """Convert centroid tuples into numpy arrays for fast lookup."""
        if not centroids:
            return None
        ids = np.array([cid for cid, *_ in centroids], dtype=object)
        vecs = np.vstack([cent for _, cent, *_ in centroids])
        first = np.array([f.timestamp() for _, _, f, _, _ in centroids])
        last = np.array([l.timestamp() for _, _, _, l, _ in centroids])
        return ids, vecs, first, last

    def _centroid_attach_fast(self, vec: np.ndarray, ts: dt.datetime,
                              win: dt.timedelta | None, cache):
        """Vectorised centroid attach using precomputed arrays."""
        if cache is None:
            return None
        ids, cents, first, last = cache
        ts_val = ts.timestamp()
        if win is not None:
            w = win.total_seconds()
            mask = (first <= ts_val + w) & (last >= ts_val - w) & ((ts_val - first) <= w)
            if not mask.any():
                return None
            cents = cents[mask]
            ids = ids[mask]
        sims = cos_sim(vec, cents)[0]
        best = int(np.argmax(sims))
        return ids[best] if sims[best] >= self.THETA else None

    # ------------------- write helper -------------------
    def _write_cluster(self, conn, members: Sequence[Dict], vecs: np.ndarray):
        cid = uuid.uuid4()
        ts_first = min(self._cluster_ts(r) for r in members)
        ts_last = max(self._cluster_ts(r) for r in members)
        headline = members[0].get("headline") or str(members[0]["cluster_id"])
        centroid = np.mean(vecs, axis=0).tolist()
        conn.execute(meta_clusters.insert().values(
            meta_id=cid, headline=headline,
            first_date=ts_first, last_date=ts_last,
            size=len(members), centroid=centroid,
        ))
        conn.execute(
            pg_insert(meta_members)
            .values([{"meta_id": cid, "cluster_id": r["cluster_id"]} for r in members])
            .on_conflict_do_update(index_elements=["meta_id", "cluster_id"],
                                   set_={"updated_at": sa.func.now()})
        )

    # ------------------- entrypoint -------------------
    def cluster_once(self, algo: str = "agglom", threshold: float = 0.25, min_size: int = 1,
                     min_samples: int = 2, days: float | None = None, verbose: bool = False):
        if verbose:
            print("Started Cluster Once: ", datetime.now())
        win = dt.timedelta(days=days) if days is not None else None
        fresh = self._fetch_unclustered()
        print(f"[CLUSTER][meta] input_story_clusters={len(fresh)}")
        if verbose:
            print("Got Fresh Clusters Once", len(fresh), datetime.now())
        if not fresh:
            if verbose:
                print("no new clusters", datetime.now())
            return

        vecs = np.vstack([np.array(r["centroid"]) for r in fresh])

        residual_rows: List[Dict] = []
        residual_vecs: List[np.ndarray] = []
        with engine.begin() as conn:
            ts_all = [self._cluster_ts(r) for r in fresh]
            start = min(ts_all)
            end = max(ts_all)
            if win is not None:
                start -= win
                end += win
            if verbose:
                print("Start:", start, "End:", end, " :", datetime.now())
            centroids_all = self._load_centroids_range(conn, start, end)
            cent_cache = self._prepare_centroid_cache(centroids_all)
            if verbose:
                print("Got cluster centroids", datetime.now())

            attachments: Dict[uuid.UUID, Dict] = {}
            for row, vec in zip(fresh, vecs):
                ts = self._cluster_ts(row)
                cid = self._centroid_attach_fast(vec, ts, win, cent_cache)
                if cid:
                    att = attachments.get(cid)
                    if att is None:
                        attachments[cid] = {
                            "vec_sum": vec.copy(),
                            "count": 1,
                            "last_date": ts,
                            "members": [row["cluster_id"]],
                        }
                    else:
                        att["vec_sum"] += vec
                        att["count"] += 1
                        att["last_date"] = max(att["last_date"], ts)
                        att["members"].append(row["cluster_id"])
                else:
                    residual_rows.append(row)
                    residual_vecs.append(vec)

            if attachments:
                sel = sa.select(meta_clusters.c.meta_id,
                                meta_clusters.c.size,
                                meta_clusters.c.centroid,
                                meta_clusters.c.last_date)
                sel = sel.where(meta_clusters.c.meta_id.in_(attachments.keys()))
                updates: List[Dict] = []
                member_rows: List[Dict] = []
                for cid, size, cent, last in conn.execute(sel):
                    info = attachments[cid]
                    new_size = size + info["count"]
                    new_cent = ((np.array(cent) * size) + info["vec_sum"]) / new_size
                    new_last = max(last, info["last_date"])
                    updates.append({
                        "pk": cid,
                        "size": new_size,
                        "centroid": new_cent.tolist(),
                        "last_date": new_last,
                    })
                    member_rows.extend({"meta_id": cid, "cluster_id": m} for m in info["members"])

                if updates:
                    conn.execute(
                        meta_clusters.update()
                        .where(meta_clusters.c.meta_id == sa.bindparam("pk"))
                        .values(size=sa.bindparam("size"),
                                centroid=sa.bindparam("centroid"),
                                last_date=sa.bindparam("last_date"),
                                updated_at=sa.func.now()),
                        updates,
                    )

                if member_rows:
                    conn.execute(
                        pg_insert(meta_members)
                        .values(member_rows)
                        .on_conflict_do_update(index_elements=["meta_id", "cluster_id"],
                                               set_={"updated_at": sa.func.now()})
                    )

            if verbose:
                print("Phase 1 done", datetime.now())

            if verbose:
                print("residual_rows len:", len(residual_rows), datetime.now())

            if residual_rows:
                full_vecs = np.vstack(residual_vecs)
                labels = self._cluster_alg(full_vecs, algo, threshold,
                                           min_size, min_samples)

                label2idxs: Dict[int, List[int]] = {}
                for i, lab in enumerate(labels):
                    label2idxs.setdefault(lab, []).append(i)

                for lab, idxs in label2idxs.items():
                    if lab == -1:
                        for i in idxs:
                            self._write_cluster(conn, [residual_rows[i]], full_vecs[i:i + 1])
                        continue

                    members = [residual_rows[i] for i in idxs]
                    mvecs = full_vecs[idxs]

                    for sub in self._time_split(members, win):
                        if not sub:
                            continue
                        svecs = np.vstack([mvecs[members.index(r)] for r in sub])
                        self._write_cluster(conn, sub, svecs)
                if verbose:
                    print("Phase 2 done", datetime.now())

        if verbose:
            print(f"✅ meta-clustered {len(fresh)} clusters ({len(residual_rows)} residual after phase‑1)")


def cli():
    parser = argparse.ArgumentParser(description="Incremental clustering for news‑pipeline")
    parser.add_argument("--algo", choices=["agglom"], default="agglom")
    parser.add_argument("--threshold", type=float, default=0.25)
    parser.add_argument("--min-size", type=int, default=3)
    parser.add_argument("--min-samples", type=int, default=2)
    parser.add_argument("--days", type=float, default=None, help="±time window in days for centroid attach/batching")
    parser.add_argument("--verbose", action="store_true")
    args = parser.parse_args()
    StoryClusterer().cluster_once(algo=args.algo, threshold=args.threshold, min_size=args.min_size,
                                  min_samples=args.min_samples, days=args.days, verbose=args.verbose)

if __name__ == "__main__":
    cli()

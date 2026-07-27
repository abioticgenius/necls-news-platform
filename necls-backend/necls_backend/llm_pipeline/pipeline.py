from __future__ import annotations

import json
from typing import Iterable, List, Optional
import uuid
import os
import pandas as pd
from concurrent.futures import ThreadPoolExecutor, as_completed
from .audio import AudioService
from .llm_client import LLMClient
from .llm_save import save_llm_outputs_to_db1
from .repository import ArticleRepository
from ..output_structure.structure import (
    MultiLanguageSummaryNew,
    MultiLanguageStorySoFar,
    MultiLanguageLookingAhead,
    MultiLanguageFullStoryAudio,
    FilterOutput,
)
from ..prompts.summary import SUMMARY_PROMPT
from ..prompts.story_so_far import STORY_SO_FAR_PROMPT
from ..prompts.looking_ahead import LOOKING_AHEAD_PROMPT
from ..prompts.full_story_audio import FULL_STORY_AUDIO_PROMPT
from ..prompts.filter import FILTER_PROMPT
from ..single_rss_fetcher import RssFetcher
from ..db import story_clusters, engine
import sqlalchemy as sa


def _parse_bool_env(env_var: str, default: bool = True) -> bool:
    """Parse boolean from environment variable. Only accepts 'TRUE' or 'FALSE' (case-insensitive).
    Defaults to True if not set or invalid value provided."""
    value = os.environ.get(env_var, "").strip().upper()
    if value == "":
        return default
    elif value == "TRUE":
        return True
    elif value == "FALSE":
        return False
    else:
        print(f"[WARNING] Invalid value for {env_var}: '{value}'. Must be 'TRUE' or 'FALSE'. Using default: {default}")
        return default


class ClusterPipeline:
    """High-level orchestration for processing story clusters."""

    def __init__(
        self,
        repo: Optional[ArticleRepository] = None,
        llm_client: Optional[LLMClient] = None,
        audio_service: Optional[AudioService] = None,
    ):
        self.repo = repo or ArticleRepository()
        self.llm = llm_client or LLMClient(api_key=os.getenv("OPENAI_API_KEY"), key_label="KEY1")
        self.llm2 = llm_client or LLMClient(api_key=os.getenv("OPENAI_API_KEY2"), key_label="KEY2")
        # Initialize AudioService with S3 configuration
        if audio_service:
            self.audio = audio_service
        else:
            bucket = os.getenv("AUDIO_BUCKET")
            prefix = os.getenv("AUDIO_PREFIX", "")
            if not bucket:
                raise ValueError("AUDIO_BUCKET environment variable is required for S3 storage")
            self.audio = AudioService(bucket=bucket, prefix=prefix)

    # ------------------------------------------------------------------
    # Helper functions
    # ------------------------------------------------------------------
    @staticmethod
    def _get_gnews_results(
        search_queries: Iterable[str],
        headline: str,
        summary: str,
        date: str,
        today_articles: Iterable[str],
    ) -> List[dict]:
        from urllib.parse import quote_plus  # NEW: Import for URL encoding
        rss_fetcher = RssFetcher()
        results: List[dict] = []
        # Keep date handling consistent with the rest of the pipeline via pandas parsing.
        end_ts = pd.to_datetime(date, errors="coerce", utc=True)
        if pd.isna(end_ts):
            end_ts = pd.Timestamp.utcnow()
        gnews_max_years = int(os.getenv("GNEWS_MAX_YEARS", "3"))
        if gnews_max_years < 0:
            gnews_max_years = 0
        start_ts = end_ts - pd.DateOffset(years=gnews_max_years)
        end_date = end_ts.date().isoformat()
        start_date = start_ts.date().isoformat()

        for search_query in search_queries:
            # NEW: URL-encode the plain text query
            encoded_query = quote_plus(search_query)
            url = (
                f"https://news.google.com/rss/search?q={encoded_query}%20AND%20after%3A{start_date}%20AND%20before%3A{end_date}%20AND%20"
                "(site%3Areuters.com%20OR%20site%3Aianslive.in%20OR%20site%3Abusiness-standard.com%20"
                "OR%20site%3Ahindustantimes.com%20OR%20site%3Aeconomictimes.indiatimes.com%20"
                "OR%20site%3Andtv.com%20OR%20site%3Ascroll.in%20OR%20site%3Atheprint.in%20"
                "OR%20site%3Aindianexpress.com%20OR%20site%3Atribuneindia.com%20OR%20site%3Alivemint.com%20"
                "OR%20site%3Aptinews.com%20OR%20site%3Auniindia.com%20OR%20site%3Atimesofindia.indiatimes.com%20"
                "OR%20site%3Athehindu.com%20OR%20site%3Aapnews.com)&hl=en-IN&gl=IN&ceid=IN%3Aen"
            )
            # NEW: Use summary (truncate if too long) instead of mini_summary
            summary_text = (summary[:200] + "...") if len(summary) > 200 else summary
            needed = headline + ". " + summary_text  # NEW: Use summary instead of mini_summary
            results.extend(rss_fetcher.fetch(rss_url=url, title=needed, threshold=0.3))
            if results and len(results) > 30:
                break

        results = [item for item in results if item["url"] not in today_articles]

        if len(results) > 20:
            re_refined = rss_fetcher.sample_one_per_day(results)
        else:
            re_refined = results

        filtered = [
            {k: str(d[k]) for k in ("url", "text", "date_publish", "title")}
            for d in re_refined
        ]
        return filtered

    @staticmethod
    def _truncate_article_text(text: str, max_words: int = 300) -> str:
        """
        Truncate article text to max_words, preserving complete sentences.
        
        Args:
            text: Full article text
            max_words: Maximum number of words to keep (default: 500)
        
        Returns:
            Truncated text ending at a complete sentence
        """
        if not text or not isinstance(text, str):
            return text
        
        words = text.split()
        if len(words) <= max_words:
            return text
        
        # Truncate to max_words
        truncated = ' '.join(words[:max_words])
        
        # Find last complete sentence (period, exclamation, or question mark)
        last_sentence_end = max(
            truncated.rfind('.'),
            truncated.rfind('!'),
            truncated.rfind('?')
        )
        
        # If we found a sentence ending within reasonable distance (80% of max_words),
        # use it; otherwise return truncated as-is
        if last_sentence_end > max_words * 0.8:
            return truncated[:last_sentence_end + 1]
        
        return truncated

    @staticmethod
    def _get_result_array(df_meta_clusters: pd.DataFrame, filtered: List[dict]):
        re_refined_urls = [ref["url"] for ref in filtered]
        df_meta_clusters["date_publish"] = df_meta_clusters["date_publish"].astype(str)
        meta_array = df_meta_clusters[~df_meta_clusters["url"].isin(re_refined_urls)][
            ["url", "text", "title", "date_publish"]
        ].to_dict(orient="records")
        
        # Truncate article text to reduce token usage
        max_words = int(os.getenv("PAST_ARTICLE_MAX_WORDS", "300"))
        
        # Truncate meta_clusters articles
        for article in meta_array:
            if "text" in article:
                article["text"] = ClusterPipeline._truncate_article_text(
                    article["text"], max_words
                )
        
        # Truncate Google News articles
        for article in filtered:
            if "text" in article:
                article["text"] = ClusterPipeline._truncate_article_text(
                    article["text"], max_words
                )
        
        # Combine all articles
        past_articles = meta_array + filtered
        
        # Sort chronologically (oldest first) to ensure timeline coverage
        def get_date_key(article):
            date_str = article.get("date_publish", "")
            if not date_str:
                return "9999-12-31"  # Put articles without dates at the end
            try:
                # Handle various date formats
                from datetime import datetime
                # Try ISO format first
                try:
                    return datetime.fromisoformat(date_str.replace("Z", "+00:00")).date().isoformat()
                except:
                    # Try other common formats
                    for fmt in ["%Y-%m-%d", "%Y/%m/%d", "%d/%m/%Y"]:
                        try:
                            return datetime.strptime(date_str[:10], fmt).date().isoformat()
                        except:
                            continue
                return date_str[:10] if len(date_str) >= 10 else "9999-12-31"
            except:
                return "9999-12-31"
        
        past_articles.sort(key=get_date_key)
        
        # Apply limit while preserving chronological distribution
        max_articles = int(os.getenv("MAX_PAST_ARTICLES", "15"))
        if len(past_articles) > max_articles:
            # Evenly sample across the date range to preserve timeline coverage
            step = len(past_articles) / max_articles
            indices = [int(i * step) for i in range(max_articles)]
            # Ensure we include the most recent article
            if indices[-1] != len(past_articles) - 1:
                indices[-1] = len(past_articles) - 1
            past_articles = [past_articles[i] for i in indices]
        
        return past_articles

    # ------------------------------------------------------------------
    # Editorial filtering
    # ------------------------------------------------------------------
    def filter_cluster(self, cluster_id: str, llm_fn: LLMClient) -> tuple[bool, str]:
        """
        Filter a cluster using prompt0.txt (editorial filter).
        Returns: (is_approved: bool, status: "editorial_approved" | "editorial_rejected")
        """
        try:
            df_articles = self.repo.get_articles(cluster_id)
            if df_articles.empty:
                print(f"[WARN] Cluster {cluster_id} has no articles, marking as rejected")
                return (False, "editorial_rejected")
            
            # Select representative article (most recent by date_publish)
            df_articles["date_publish"] = pd.to_datetime(df_articles["date_publish"], errors="coerce")
            representative = df_articles.nlargest(1, "date_publish").iloc[0]
            
            headline = representative.get("title") or ""
            description = representative.get("description") or ""
            
            # If description is empty, use first 200 characters of text
            if not description and representative.get("text"):
                description = str(representative["text"])[:200]
            
            # Format prompt with placeholders
            formatted_prompt = FILTER_PROMPT.replace("{{headline}}", headline).replace("{{description}}", description)
            
            # Call LLM with FILTER_PROMPT and FilterOutput
            filter_response = llm_fn.generate(formatted_prompt, FilterOutput, need_token_data=True)
            filter_response = filter_response[0] if isinstance(filter_response, tuple) else filter_response
            
            # Return appropriate status based on result
            if filter_response.status == "YES":
                return (True, "editorial_approved")
            else:
                return (False, "editorial_rejected")
        except Exception as exc:
            print(f"[ERROR] Failed to filter cluster {cluster_id}: {exc}")
            # On error, keep as pending (don't auto-reject)
            return (False, "pending")
    
    def _update_filter_status(self, cluster_id: str, status: str) -> None:
        """Update filter_status in story_clusters table."""
        try:
            with engine.begin() as conn:
                stmt = (
                    sa.update(story_clusters)
                    .where(story_clusters.c.cluster_id == sa.bindparam("cid"))
                    .values(filter_status=sa.bindparam("filter_status"))
                )
                conn.execute(stmt, {"cid": cluster_id, "filter_status": status})
        except Exception as exc:
            print(f"[ERROR] Failed to update filter_status for cluster {cluster_id}: {exc}")
            raise

    # ------------------------------------------------------------------
    # LLM pipeline per cluster
    # ------------------------------------------------------------------
    def _get_llm_data(self, cluster_id: str, date: str, llm_fn: LLMClient):
        df_articles = self.repo.get_articles(cluster_id)
        articles_info = df_articles[["url", "date_publish", "title", "text"]].to_dict(
            orient="records"
        )
        content = SUMMARY_PROMPT + "\n Articles: \n" + json.dumps(articles_info)
        p1_response, p1_token = llm_fn.generate(
            content, MultiLanguageSummaryNew, need_token_data=True
        )

        parsed_output = p1_response.model_dump()
        df_meta_clusters = self.repo.get_meta_clusters(cluster_id)
        today_articles = [a["url"] for a in articles_info]
        gnews_data = self._get_gnews_results(
            search_queries=parsed_output["google_news_queries"],  # NEW: google_news_queries
            headline=parsed_output["title_en"],  # NEW: Flat structure, use title_en
            summary=parsed_output["summary_en"],  # NEW: Use summary_en instead of mini_summary
            date=date,
            today_articles=today_articles,
        )
        past_articles = self._get_result_array(df_meta_clusters=df_meta_clusters, filtered=gnews_data)
        # NEW: Update preset_article_output to use new flat structure
        preset_article_output = json.dumps({
            "title_en": parsed_output.get("title_en"),
            "title_hi": parsed_output.get("title_hi"),
            "summary_en": parsed_output.get("summary_en"),
            "summary_hi": parsed_output.get("summary_hi"),
            "sources": parsed_output.get("sources", [])
        })

        prompt2_contents = (
            STORY_SO_FAR_PROMPT
            + "\n present articles output: "
            + preset_article_output
            + "\n Past Articles which should also be used for creating the slides. "
            + "Create new source_ids for these \n : "
            + json.dumps(past_articles)
        )

        prompt3_contents = (
            LOOKING_AHEAD_PROMPT
            + "\n present articles output: "
            + preset_article_output
            + "\n Past Articles which should also be used for creating the slides. "
            + "Create new source_ids for these \n : "
            + json.dumps(past_articles)
        )

        with ThreadPoolExecutor(max_workers=2) as executor:
            f_story = executor.submit(
                llm_fn.generate,
                prompt2_contents,
                MultiLanguageStorySoFar,
                True,
            )
            f_look = executor.submit(
                llm_fn.generate,
                prompt3_contents,
                MultiLanguageLookingAhead,
                True,
            )
            p2_response, p2_token = f_story.result()
            p3_response, p3_token = f_look.result()

        return (
            p1_response,
            p2_response,
            p3_response,
            p1_token,
            p2_token,
            p3_token,
            articles_info,
            past_articles,
        )

    def process_cluster(self, cluster_id: str, date: str, llm_fn: LLMClient) -> None:
        (
            p1_response,
            p2_response,
            p3_response,
            p1_token,
            p2_token,
            p3_token,
            articles_info,
            past_articles,
        ) = self._get_llm_data(cluster_id, date, llm_fn)

        # Generate full story audio text
        p1_dump = p1_response.model_dump()
        p2_dump = p2_response.model_dump()
        p3_dump = p3_response.model_dump()
        
        # Extract tags from Model B output (p1_response contains MultiLanguageSummaryNew)
        # Check if Model_b_presentation wrapper exists, otherwise use direct tags field
        seo_tags_list = None
        if "Model_b_presentation" in p1_dump:
            seo_tags_list = p1_dump["Model_b_presentation"].get("tags")
        elif "tags" in p1_dump:
            seo_tags_list = p1_dump["tags"]

        # Convert to dict format expected by save_llm_outputs_to_db1
        seo_tags_dict = None
        if seo_tags_list:
            # Convert Pydantic models to dicts if needed
            if seo_tags_list and isinstance(seo_tags_list[0], dict):
                tags_as_dicts = seo_tags_list  # Already dicts
            else:
                tags_as_dicts = [tag.model_dump() if hasattr(tag, 'model_dump') else tag for tag in seo_tags_list]
            # NOTE: Do NOT call apply_tag_wiring() after model_dump()!
            # The Pydantic validator (enforce_tag_wiring) already ran during model instantiation and:
            # 1. Validated all tags against approved categories
            # 2. Applied sub-category alias transformations (e.g., "Markets" → "Stock Markets")
            # Calling apply_tag_wiring() on the dumped output only causes problems because:
            # - It filters based on short names only (e.g., "Markets")
            # - But the dumped tags have already been transformed to aliases (e.g., "Stock Markets")
            # - This causes aliased tags to be incorrectly filtered out
            seo_tags_dict = {"seo_tags": tags_as_dicts}
            # Write tags into p1_dump so _save_summary also receives them
            if "Model_b_presentation" in p1_dump:
                p1_dump["Model_b_presentation"]["tags"] = tags_as_dicts
            elif "tags" in p1_dump:
                p1_dump["tags"] = tags_as_dicts
        
        # Extract audio scripts from the three prompts
        # INPUT 1: Core News (always present)
        audio_scripts_p1 = p1_dump.get("audio_scripts_summary") or {}
        input1 = {
            "audio_script": {
                "en": audio_scripts_p1.get("en", ""),
                "hi": audio_scripts_p1.get("hi", "")
            }
        }
        
        # INPUT 2: Backstory (may be skipped)
        input2 = None
        audio_script_p2 = p2_dump.get("audio_script")
        if audio_script_p2:
            input2 = {
                "audio_script": {
                    "en": audio_script_p2.get("en", ""),
                    "hi": audio_script_p2.get("hi", "")
                }
            }
        
        # INPUT 3: Impact & Scenarios (check if present and not empty)
        input3 = None
        p3_audio_script = p3_dump.get("audio_script")
        if p3_audio_script:
            audio_en = p3_audio_script.get("audio_en", "")
            audio_hi = p3_audio_script.get("audio_hi", "")
            if audio_en and audio_hi:
                input3 = {
                    "audio_script": {
                        "en": audio_en,
                        "hi": audio_hi
                    }
                }
        
        # Construct the new prompt
        prompt_parts = [FULL_STORY_AUDIO_PROMPT]
        prompt_parts.append("\nINPUT 1 — Prompt 1 (Core News):")
        prompt_parts.append(json.dumps(input1, ensure_ascii=False))
        
        if input2:
            prompt_parts.append("\nINPUT 2 — Prompt 2 (Backstory):")
            prompt_parts.append(json.dumps(input2, ensure_ascii=False))
        else:
            prompt_parts.append("\nINPUT 2 — Prompt 2 (Backstory): SKIPPED")
        
        if input3:
            prompt_parts.append("\nINPUT 3 — Prompt 3 (Impact & Scenarios):")
            prompt_parts.append(json.dumps(input3, ensure_ascii=False))
        else:
            prompt_parts.append("\nINPUT 3 — Prompt 3 (Impact & Scenarios): SKIPPED")
        
        full_story_prompt = "\n".join(prompt_parts)
        
        full_story_response = llm_fn.generate(
            full_story_prompt, MultiLanguageFullStoryAudio, need_token_data=True
        )
        full_story_token_meta = full_story_response[1] if isinstance(full_story_response, tuple) else None
        full_story_response = full_story_response[0] if isinstance(full_story_response, tuple) else full_story_response
        
        # Get audio texts
        # Get from audio_scripts_summary for gist audio
        audio_scripts = p1_dump.get("audio_scripts_summary") or {}
        p1_en_atext = audio_scripts.get("en", "")
        p1_hi_atext = audio_scripts.get("hi", "")
        # Get full story audio from new response structure
        full_story_response_dump = full_story_response.model_dump()
        full_story_en_atext = full_story_response_dump["audio_scripts_full_story"]["en"]
        full_story_hi_atext = full_story_response_dump["audio_scripts_full_story"]["hi"]
        
        # Read environment variables to control audio generation
        # ENABLE_GIST_AUDIO and ENABLE_FULL_STORY_AUDIO must be "TRUE" or "FALSE" (case-insensitive)
        # Defaults to True (enabled) if not set
        enable_gist_audio = _parse_bool_env("ENABLE_GIST_AUDIO", default=True)
        enable_full_story_audio = _parse_bool_env("ENABLE_FULL_STORY_AUDIO", default=True)
        
        # NEW: Use title_en instead of mini_headline
        file_name = p1_dump.get("title_en", "")
        file_name_uuid = str(uuid.uuid5(uuid.NAMESPACE_DNS, file_name))
        
        # Generate audio files based on environment variable configuration
        # Both gist and full story audio can be independently enabled/disabled via env vars
        english_gist_file = file_name_uuid + '_en_gist.wav'
        hindi_gist_file = file_name_uuid + '_hi_gist.wav'
        english_full_file = file_name_uuid + '_en_full.wav'
        hindi_full_file = file_name_uuid + '_hi_full.wav'

        audio_results: dict[str, dict[str, str]] = {}
        
        # Calculate number of audio files to generate (0-4) to determine max_workers
        num_audio_files = 0
        if enable_gist_audio:
            num_audio_files += 2  # English and Hindi gist
        if enable_full_story_audio:
            num_audio_files += 2  # English and Hindi full story
        
        # Generate audio if at least one type is enabled
        if num_audio_files > 0:
            max_workers = num_audio_files
            with ThreadPoolExecutor(max_workers=max_workers) as executor:
                # Build futures dictionary conditionally based on environment variables
                futures = {}
                if enable_gist_audio:
                    futures[executor.submit(self.audio.generate_and_save, p1_en_atext, english_gist_file, "en-IN", os.environ.get("GEMINI_API_KEY"))] = ("en", "gist")
                    futures[executor.submit(self.audio.generate_and_save, p1_hi_atext, hindi_gist_file, "hi-IN", os.environ.get("GEMINI_API_KEY2"))] = ("hi", "gist")
                if enable_full_story_audio:
                    futures[executor.submit(self.audio.generate_and_save, full_story_en_atext, english_full_file, "en-IN", os.environ.get("GEMINI_API_KEY"))] = ("en", "full_story")
                    futures[executor.submit(self.audio.generate_and_save, full_story_hi_atext, hindi_full_file, "hi-IN", os.environ.get("GEMINI_API_KEY2"))] = ("hi", "full_story")
                
                for fut in as_completed(futures):
                    lang, audio_type = futures[fut]
                    try:
                        _, s3_path = fut.result()
                        if lang not in audio_results:
                            audio_results[lang] = {}
                        audio_results[lang][audio_type] = s3_path
                    except Exception as exc:
                        print(f"[ERROR] Audio generation failed ({lang} {audio_type}): {exc}")

        save_llm_outputs_to_db1(
            cluster_id,
            p1_dump,
            p2_response.model_dump(),
            p3_response.model_dump(),
            p1_token,
            p2_token,
            p3_token,
            audio_results,
            seo_tags=seo_tags_dict,
        )

    def _safe_process_cluster(self, cluster_id: str, date: str, llm_fn: LLMClient) -> None:
        try:
            self.process_cluster(cluster_id, date, llm_fn)
        except Exception as exc:  # pragma: no cover - runtime/LLM failure
            print(f"[ERROR] Failed to process cluster {cluster_id}: {exc}")


    def execute_for_date(self, date: str) -> None:
        # Get recency hours from environment (same as EXTRACT_HOURS_RECENCY)
        recency_hours = None
        env_recency = os.getenv("EXTRACT_HOURS_RECENCY")
        if env_recency:
            try:
                recency_hours = float(env_recency)
            except ValueError:
                pass
        
        df_today = self.repo.get_today_clusters(date, recency_hours=recency_hours)
        cluster_ids: List[str] = []
        llm_list = [self.llm, self.llm2]
        
        
        # Filter clusters by status and apply editorial filter if needed
        for row in df_today.itertuples():
            cluster_id = str(row.cluster_id)
            
            # Skip if already processed
            if self.repo.has_llm_output(cluster_id):
                print(cluster_id, " cluster already exists in db2_links")
                continue
            
            # Get filter_status (handle case where column might not exist yet)
            filter_status = getattr(row, 'filter_status', None) or 'pending'
            
            # Skip rejected clusters
            if filter_status in ("editorial_rejected", "manual_rejected"):
                print(f"Cluster {cluster_id} is {filter_status}, skipping")
                continue
            
            # Process approved clusters directly
            if filter_status in ("editorial_approved", "manual_approved"):
                cluster_ids.append(cluster_id)
                continue
            
            # Filter pending clusters
            if filter_status == "pending" or filter_status is None:
                is_approved, new_status = self.filter_cluster(cluster_id, llm_list[0])
                self._update_filter_status(cluster_id, new_status)
                
                if is_approved and new_status == "editorial_approved":
                    cluster_ids.append(cluster_id)
        print(f"[INFO] Total clusters going for LLM processing: {len(cluster_ids)}")

        # Process clusters in batches (configurable via CLUSTER_BATCH_SIZE env variable, default: 6)
        batch_size = int(os.getenv("CLUSTER_BATCH_SIZE", "6"))
        for i in range(0, len(cluster_ids), batch_size):
            batch = cluster_ids[i:i + batch_size]
            with ThreadPoolExecutor(max_workers=batch_size) as executor:
                futures = [executor.submit(self._safe_process_cluster, cid, date, llm_list[j % 2]) for j, cid in enumerate(batch)]
                for fut in futures:
                    fut.result()

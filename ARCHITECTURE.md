# ThinkO News Platform - Technical Architecture & Design Decisions

This document covers the architectural design of ThinkO, the key decisions that shaped it, and technical trade-offs.

---

## 1. System Design Overview

### Service Separation: Why Two Languages?

The platform splits into two specialized services:

**NECLS Backend (Python)** handles:
- Heavy compute: embedding generation, clustering algorithms
- External integrations: RSS crawling, multiple LLM APIs, Google Gemini TTS
- Asynchronous workflows: batch processing, scheduled tasks
- Data transformation: SQLAlchemy ORM flexibility

**Core Service (Node.js)** handles:
- Real-time API requests: low-latency response times critical
- Concurrent connections: EventEmitter-based I/O scaling
- Firebase integration: seamless auth token verification
- Frontend-friendly responses: JSON serialization, streaming

**Trade-offs:**
- ✅ Each service uses optimal language/runtime for its domain
- ✅ Independent scaling and deployment
- ✅ Clear separation of concerns
- ❌ Increased operational complexity
- ❌ Dual SDK maintenance (Python + Node.js)

**Mitigated by:** Shared PostgreSQL database (single source of truth), minimal service-to-service communication.

---

## 2. Data Architecture

### Two-Database Strategy

```
FEEDCRAWLER_DB (DB1 - Processing)     APP_DB (DB2 - Customer-facing)
├─ Raw articles                        ├─ Curated events
├─ Story clusters                      ├─ Validated content
├─ Staging tables                      ├─ User data
├─ LLM outputs                         └─ Metrics & analytics
└─ Editorial review status
```

**Why two databases?**

| Aspect | DB1 (Processing) | DB2 (Customer) |
|--------|------------------|-----------------|
| Schema | Denormalized, staging-heavy | Normalized, curated |
| Data Lifecycle | Transient, versioned | Permanent, trusted |
| Writes | High-volume from pipeline | Selective from sync process |
| Reads | Heavy during processing | Frequent from API |
| Latency SLA | Best-effort | <100ms for API calls |

**Alternative considered:** Single database with versioning
- ❌ Would require complex multi-tenancy logic
- ❌ Hard to rollback incorrect LLM outputs
- ❌ Mixing pipeline chaos with customer trust

**Current approach benefits:**
- ✅ Editorial review happens between DB1 and DB2
- ✅ Failed pipeline runs don't affect customers
- ✅ Easy A/B testing (test sync logic before production)
- ✅ Clear audit trail

---

## 3. Article Processing Pipeline

### End-to-End Flow (Updated Every Hour)

```
1. EXTRACTION (10-15 min)
   - FeedCrawler polls 15+ sources
   - BeautifulSoup + News-Please extracts content
   - URL normalization & deduplication
   - Stores raw articles in DB1.articles
   - Idempotent: duplicate URLs skipped

2. CLUSTERING - PHASE 1: Centroid Attachment (5-10 min)
   - Embed new articles: sentence-transformers (384 dims, local)
   - Calculate cosine similarity to existing cluster centroids
   - Attach articles with similarity >= CLUSTERING_THETA (default 0.55)
   - Update affected cluster centroids
   - Benefits: Incremental, fast, respects existing groups

3. CLUSTERING - PHASE 2: Agglomerative (5-10 min)
   - Group remaining unattached articles
   - scikit-learn AgglomerativeClustering with cosine distance
   - Time-windowed: articles must be within ±6-24 hours
   - Distance threshold: CLUSTERING_THRESHOLD (default 0.6)
   - Creates new clusters for novel topics

4. META-CLUSTERING (5 min)
   - Apply clustering to clusters (like dimensionality reduction)
   - Creates topic hierarchies for editorial context
   - Useful for "top stories" or "trending topics" sections

5. LLM ENRICHMENT (15-30 min)
   - Fetch all articles in each cluster
   - Google News RSS backfill (historical context)
   - Generate summaries (OpenAI structured outputs)
   - Generate timelines ("story so far")
   - Generate forecasts ("looking ahead")
   - Create TTS audio (Google Gemini + OpenAI fallback)
   - Store in DB1.generations, summary_localized, slides

6. EDITORIAL REVIEW (Manual, Async)
   - Webadmin UI: Flask app on port 8000
   - Reviewers approve/reject clusters
   - Edit summaries, reorder slides
   - Manual sync to DB2 if needed

7. APP DB SYNC (5 min)
   - Transform DB1 cluster → DB2 event
   - Validate & clean images
   - Map logos via domain matching
   - Link SEO tags with weighting
   - Update user notifications
   - Complete audit trail in db2_links table
```

**Total Pipeline Time:** ~30-60 minutes per cycle (tunable)

### Why This Design?

**Two-Phase Clustering:**
- Phase 1 (centroid): Fast incremental updates to existing clusters
- Phase 2 (agglomerative): Discovers completely new topics
- Combined: Balances speed vs. coverage
- Alternative (pure agglomerative): Would be O(n²) on all articles, too slow

**Time Windows:**
- Prevents "temporal clustering" (Monday article + Friday article about same topic shouldn't group)
- Configurable per source (sports = 24h window, politics = 72h)
- Reduces false positives significantly

**Incremental Processing:**
- Only processes articles from last 24 hours
- Skips already-processed articles (hash-based deduplication)
- Old articles never re-clustered unless explicitly triggered

---

## 4. AI Assistant (RAG) Architecture

### 9-Step Query Processing Pipeline

```
Step 1: PREPROCESSING
  - Normalize whitespace & punctuation
  - Detect language (Hindi/English)
  - Translate Hindi → English if needed (OpenAI API)

Step 2: QUICK CHECKS (Rule-based Shortcuts)
  Pattern Detection:
  - Greeting ("Hi", "नमस्ते") → Return localized greeting
  - DB Info ("latest update") → Return DB timestamp
  - Temporal ("last week", "Jan 2024") → Filtered search
  - Generic ("what's happening") → Latest articles + LLM summary

Step 3: ENTITY EXTRACTION
  - Parse question for keywords
  - Remove stop words (180+ curated words per language)
  - Detect capitalized names (Trump, Modi, Apple)
  - Handle abbreviations (AI = Artificial Intelligence)
  - Output: ["entity1", "entity2", ...]

Step 4: ENTITY EXPANSION
  - Map entities to semantic equivalents
  - Example: "AI" → ["artificial_intelligence", "ml", "deep_learning"]
  - Hardcoded ENTITY_EXPANSIONS map (~40+ mappings)
  - Increases recall for related articles

Step 5: VECTOR EMBEDDING
  - Embed user question using Xenova (384 dims)
  - Local model, no API cost, ~15ms latency
  - Same model as clustering (vector space consistency)

Step 6: THREE-PASS VECTOR SEARCH (pgvector + IVFflat)
  Pass 1: Last 5 days
    - Fetch 20 candidate articles by cosine similarity
    - Filter by recency (prefer fresh news)

  Pass 2: Last 10 days (if Pass 1 empty)
    - Expand time window

  Pass 3: All-time (if Pass 2 empty)
    - Minimum similarity threshold: 0.45
    - Ensures we find something

Step 7: CHUNK SELECTION & SCORING
  - Score each chunk: Similarity + RecencyBonus
  - RecencyBonus = max(0, 0.12 - (ageDays * 0.01))
  - Select top 8 chunks, max 2 per article
  - Format for LLM context

Step 8: LLM PROCESSING
  - Model: gpt-5-nano (configurable)
  - Timeout: 10 seconds (fallback if slow)
  - Max tokens: 250 (targets 120-150 words)
  - Temperature: 0.7 (balanced creativity/accuracy)
  - System prompt: "You are a ThinkO news assistant..."

Step 9: RESPONSE ASSEMBLY
  - Parse LLM output
  - Extract cited articles from context
  - Build references: { id, title, date, relevance_score, image_url }
  - Return: { answer, references, confidence }

Fallback: If LLM timeout, return formatted references without answer
```

**Latency Breakdown (typical):**
- Embedding: ~15ms (local)
- Vector search: ~50ms (indexed query)
- LLM inference: ~2000ms (OpenAI API)
- Total: ~2065ms (2.1 seconds)

**Why This Complexity?**

Single query might match 0-100 articles. Need strategic filtering:
- Time window: Prefer recent news unless asking historically
- Entity expansion: Catch related articles user might not explicitly search
- Multi-pass search: Graceful degradation if few results
- Relevance scoring: Balance similarity with freshness

Alternative (simple keyword search):
- ❌ Would miss synonyms (BERT ≠ LLM != Large Language Model)
- ❌ Would struggle with implicit questions
- ❌ No quality ranking

---

## 5. Embedding Strategy

### Model Choice: Xenova all-MiniLM-L6-v2

**Why this specific model?**

| Dimension | Choice | Rationale |
|-----------|--------|-----------|
| Dimensions | 384 | Sweet spot: enough expressiveness, not too large (vs. 768, 1536) |
| Model | all-MiniLM-L6-v2 | Lightweight, fast, pre-trained on semantic similarity |
| Deployment | Local (ONNX) | No API dependency, deterministic, real-time |
| License | MIT | Production-friendly, no commercial restrictions |

**Trade-offs:**
- ✅ Fast: ~15ms per query (local inference)
- ✅ Cost-effective: zero API charges for embeddings
- ✅ Consistent: same model in both services (no vector space mismatch)
- ✅ Lightweight: 500MB cache, fits in memory
- ❌ Moderate quality: not state-of-the-art (vs. OpenAI's text-embedding-3-large)
- ❌ Fixed dimensions: can't easily switch models without recomputing

**Alternative considered:** OpenAI text-embedding-3-large
- Would provide better quality
- Would cost ~$0.02 per 1M tokens
- Would require API calls (adds latency)
- Not chosen for cost & real-time requirements

**Vector Space Consistency:**
- Both NECLS and Core Service use same model
- Embeddings generated during clustering compatible with RAG queries
- No vector space mismatch (critical for search quality)

---

## 6. Database Schema Optimization

### DB2 (Customer-Facing) Schema

**Core Tables:**

```sql
-- Stories/Events
event (
  id UUID PRIMARY KEY,
  title, description, time_stamp, image,
  article_type ENUM, created_date
)

-- Multilingual content
localized_event_data (
  id UUID PRIMARY KEY,
  event_id FK,
  language_id (en/hi),
  title, description, content,
  audio_s3_url  -- TTS narration
)

-- Story progression
event_so_far (  -- Timeline of events leading to story
  id, event_id FK, sequence, content JSONB
)

-- Future outlook
event_analysis (  -- Impact, scenarios, forecast
  id, event_id FK, type ENUM (text/bullets/timeline/table),
  content JSONB, sequence
)

-- Sources
source (
  id, event_id FK, source_url, title, date, logo_id
)

-- Taxonomy
seo_tag (
  id, name, type ENUM, embedding VECTOR(128)
)

event_seo_tag (
  id, event_id FK, seo_tag_id FK, weight, role
)

-- Semantic search (RAG)
assistant_chunk (  -- 384-dim vectors for question answering
  id, event_id FK, chunk_text, embedding VECTOR(384),
  chunk_type ENUM (title/description/content/story_so_far/analysis)
)
```

**Indexes:**
```sql
CREATE INDEX idx_events_time_stamp ON event(time_stamp DESC);
CREATE INDEX idx_localized_data_event_id ON localized_event_data(event_id);
CREATE INDEX idx_event_analysis_event_id ON event_analysis(event_id);
CREATE INDEX idx_assistant_chunks_event_id ON assistant_chunk(event_id);

-- Vector search index
CREATE INDEX idx_assistant_embedding ON assistant_chunk
  USING ivfflat (embedding vector_cosine_ops);
```

**Why this schema?**

1. **Denormalized for read performance**
   - `localized_event_data` duplicates title/description
   - Avoids N+1 joins for multi-language queries
   - Single query gets all content

2. **JSONB for flexible data**
   - Slides (timeline, table, bullets) stored as JSONB
   - Can evolve without migrations
   - Searchable & indexable in PostgreSQL 14+

3. **Vector columns for embeddings**
   - pgvector extension: native support
   - IVFflat index: fast approximate nearest neighbor
   - 384-dim vectors: balanced size/quality

4. **Semantic content split**
   - `assistant_chunk` separate from `event`
   - Allows fine-grained search (search specific sections)
   - Supports multiple embeddings per event

**Alternative considered:** Single monolithic event table
- ❌ Would require JSON arrays (less performant)
- ❌ Harder to update individual translations
- ❌ N+1 queries for multi-language apps

---

## 7. Multi-Language Support

### Hindi ↔ English Workflow

```
USER SENDS HINDI QUERY
  ↓
Language Detection (text analysis)
  ↓
IF Hindi:
  OpenAI Translate → English
  Process in English
  (LLM returns English)
  Optionally Translate Back → Hindi
ELSE:
  Process in English directly
  Return in English

USER SENDS HINDI ARTICLE QUERY
  ↓
FETCH from DB2.localized_event_data
  WHERE language_id = 'hi'
  (Pre-translated by NECLS during sync)
  ↓
Return Hindi summaries, timeline, audio
```

**Storage Strategy:**
- DB2 stores both English and Hindi versions
- NECLS generates both languages during LLM enrichment
- No runtime translation needed for articles (cached)
- Only translate user questions if needed

**Why?**
- ✅ Pre-computed translations are fast (cached)
- ✅ Editors can refine translations manually
- ✅ No runtime translation latency
- ❌ Higher storage (duplicate content)
- ❌ Requires NECLS to handle both languages

**TTS Strategy:**
- Google Gemini: Natural Indian voices (Alloy for EN, Nova for HI)
- OpenAI fallback: If Gemini fails
- Generated during NECLS enrichment, stored as S3 URLs
- No runtime TTS (no latency, cost-effective)

---

## 8. Gamification System

### Badge & Milestone Architecture

**User Milestones Model:**
```typescript
{
  streak: {
    current: 7,                           // 7-day streak
    rest_days_used_this_week: 1,         // Can use 1 per week
    last_activity_date: "2024-01-27"
  },
  articles_read: { total: 42 },
  shares_made: { total: 3 },
  assistant_queries: { total: 12 }
}
```

**Streak Logic:**
```
Monday:   Activity ✓ (streak = 1)
Tuesday:  Activity ✓ (streak = 2)
Wednesday: No activity ✗ (use 1 rest day)
Thursday: Activity ✓ (streak = 3)
...
Sunday: Activity ✓ (streak = 7)
(Next week: rest_days_used_this_week resets to 0)
```

**Badge Thresholds:**

| Badge | Threshold | Metric |
|-------|-----------|--------|
| IGNITE | 3 | Streak |
| SPARK | 7 | Streak |
| PRO | 21 | Streak |
| CENTURY | 100 | Streak |
| STARTER | 10 | Articles Read |
| INFORMED | 50 | Articles Read |
| WELL_READ | 200 | Articles Read |
| NEWS_ROOM | 500 | Articles Read |
| (+ 10 more) | ... | Various metrics |

**Why This Design?**

1. **Client-side free**
   - Calculation happens on API, not frontend
   - Consistent across platforms
   - Can't be cheated by manipulating app storage

2. **Incremental tracking**
   - Simple `activity_dates` array
   - No complex state machine
   - Easy to audit & debug

3. **Streak with rest days**
   - Encourages consistency but realistic
   - People forget - give them one pass per week
   - Prevents burnout

**Alternative considered:** Server-side event sourcing
- Would track every action (view, click, hover)
- Could enable more nuanced badges
- Would be 10-100x more data storage
- Not chosen for cost/complexity

---

## 9. Content Sync Strategy (DB1 → DB2)

### Controlled Pipeline with Manual Gate

```
DB1 (Processing)                   Webadmin UI                    DB2 (Customer)
├─ Generate summaries  ──→  [Editorial Review]  ──→  Sync if Approved  ──→  Event
├─ Create timeline                └─ Approve/Reject                          Localized Data
├─ Forecast scenarios             └─ Manual Edit                            (Customers see)
├─ Generate audio                 └─ Manual Sync Button
└─ Store metadata

Sync tracks: db2_links.last_synced_at, cluster_id, event_id
```

**Why manual gate?**

1. **Quality Control**
   - Editor reviews LLM outputs
   - Can reject low-confidence content
   - Can manually fix problematic summaries

2. **Error Recovery**
   - LLM hallucinations caught before publishing
   - Failed audio generation won't reach customers
   - Bad clustering fixed before customer sees

3. **A/B Testing**
   - Can test different LLM models
   - Can version content (store both old & new)
   - Rollback capability

**Alternative considered:** Automatic sync
- ❌ Would publish LLM errors to customers
- ❌ No quality control
- ❌ Harder to debug issues

---

## 10. Performance Optimization Techniques

### 1. Vector Index Optimization
```sql
-- IVFflat: Approximate nearest neighbor
-- Faster than exact L2/cosine, good for 384-dim vectors
CREATE INDEX ON assistant_chunk USING ivfflat (embedding vector_cosine_ops)
  WITH (lists = 100);  -- ~sqrt(table_size)
```

### 2. Connection Pooling
```
Node.js Sequelize:   max: 5, min: 0, idle: 10s
Python SQLAlchemy:   pool_size: 10, max_overflow: 20
```
Avoids connection exhaustion under load.

### 3. Query Optimization
```sql
-- Prefetch related data
SELECT event.*, localized_event_data.*, source.*
FROM event
JOIN localized_event_data ON event.id = localized_event_data.event_id
JOIN source ON event.id = source.event_id
WHERE localized_event_data.language_id = 'en';

-- Not N+1 queries (1 query per event)
```

### 4. Caching Strategies
- Frontend: Presigned S3 URLs (1 hour TTL)
- API: Response headers (no backend cache)
- Database: Connection pooling + indexes
- Model: Xenova embeddings cached in-memory

### 5. LLM Token Optimization
```
Query summarization (max 50 tokens) → Faster inference
Article summaries (max 250 tokens) → Fits in token budget
Timeline generation (max 120 tokens) → Fast & concise
```

Shorter prompts = faster responses + lower costs.

---

## 11. Error Handling & Fallbacks

### LLM Query Timeout
```
Timeout (10 sec) → Return formatted references without LLM answer
LLM Error → Fallback: "Based on the sources below:"
```

### Vector Search Empty
```
Pass 1 (5 days) empty? → Try Pass 2 (10 days)
Pass 2 empty? → Try Pass 3 (all-time)
Pass 3 empty? → Return "No matching articles found"
```

### Translation Failure
```
Hindi detection error? → Return English version
Translation timeout? → Fall back to English
```

### Audio Generation Failure
```
Google Gemini fails → Try OpenAI TTS
OpenAI fails → Mark as "audio unavailable"
Customer sees text-only content (graceful degradation)
```

**Philosophy:** Never crash. Always return something useful.

---

## 12. Security Architecture

### Authentication Flow
```
Frontend User
  ↓ (Email + Password)
Firebase Auth
  ↓ (JWT Token)
Core Service
  ↓ (Verify Token)
app/firebase/verifyFirebaseToken.ts
  ↓ (Extract UID)
req.user = { uid, email, name }
  ↓
Protected Route Handler
```

### Data Security
- **Secrets:** Environment variables (never in code)
- **Credentials:** Firebase service account (rotated quarterly)
- **API keys:** Separate for development/production
- **SQL Injection:** Parameterized queries (Sequelize/SQLAlchemy)
- **XSS:** JSON responses (no HTML templates)

### Audit Trail
```sql
-- Track who changed what
db2_links (cluster_id, event_id, synced_by, last_synced_at)
review_status (cluster_id, reviewer_id, approval_status, timestamp)
```

---

## 13. Deployment Architecture

### Local Development
```
docker-compose up -d
→ Postgres (DB1, DB2)
→ Core Service (Node.js)
→ NECLS Pipeline (Python)
→ Webadmin (Flask)
```

### Production (AWS)
```
Core Service:
  → ECS Fargate + ALB (auto-scaling)
  → RDS PostgreSQL 16 with read replicas
  → CloudFront for image CDN

NECLS Pipeline:
  → Fargate scheduled task (hourly via EventBridge)
  → Logs to CloudWatch
  → Alerts to Slack

Storage:
  → S3 for images/audio (Versioning enabled)
  → Backup to separate S3 (cross-region)

Monitoring:
  → CloudWatch for metrics
  → X-Ray for tracing
  → PagerDuty for alerts
```

---

## 14. Trade-offs & Future Improvements

### Current Limitations
1. **Single-threaded LLM processing** → Could parallelize across OpenAI clients
2. **Clustering uses cosine only** → Could try Manhattan distance
3. **Fixed 384-dim embeddings** → Could experiment with larger models
4. **No caching layer** → Could add Redis for hot articles

### Future Enhancements
- **Real-time updates:** WebSocket support instead of polling
- **Advanced analytics:** User behavior tracking & dashboards
- **Recommendation engine:** Collaborative filtering
- **Multilingual expansion:** Support 5+ languages
- **Mobile apps:** Native iOS/Android with offline support

---

## 15. Key Takeaways

This architecture demonstrates:
1. **Separation of concerns** — Pipeline ≠ API
2. **Scalability** — Horizontal scaling friendly
3. **Reliability** — Graceful degradation & fallbacks
4. **Observability** — Clear data flow & audit trails
5. **User engagement** — Gamification + personalization
6. **Production-ready** — Security, error handling, monitoring

It's a blueprint for building enterprise AI systems that serve millions of users reliably.

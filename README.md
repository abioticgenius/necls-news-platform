# ThinkO News Platform — Full-Stack News AI System

A production-grade enterprise platform for automated news aggregation, intelligent story clustering, AI-powered enrichment, and customer-facing content delivery. This system demonstrates a complete end-to-end AI pipeline with semantic search, multi-language support, and real-time user engagement tracking.

**Status:** Complete working replica with full documentation and Docker support for local development.

---

## Quick Start (5 Minutes)

```bash
# 1. Clone and navigate to the repo
cd ~/Desktop/thinko-news-platform

# 2. Create environment file
cp .env.example .env
# Edit .env with your actual API keys (optional for demo)

# 3. Start the entire stack
docker-compose up -d

# 4. Verify services are running
sleep 10
curl http://localhost:7090/health      # Core Service
curl http://localhost:8000/             # Webadmin (editorial UI)
psql -h localhost -U admin -d app_db    # Database (password: changeme)

# 5. View logs
docker-compose logs -f core-service    # API logs
docker-compose logs -f necls-pipeline   # Pipeline logs
docker-compose logs -f necls-webadmin   # Webadmin logs
```

**Ports:**
- Core Service API: http://localhost:7090
- NECLS Webadmin UI: http://localhost:8000
- PostgreSQL: localhost:5432

---

## System Architecture

```
┌─────────────────────────────────────────────────────────────────────────────┐
│                         NECLS BACKEND (Python)                               │
│                    Hourly News Processing Pipeline                           │
├─────────────────────────────────────────────────────────────────────────────┤
│                                                                              │
│  15+ News Sources  ──→  Extract   ──→  Cluster   ──→  Meta-Cluster         │
│  (RSS, Sitemaps,         Articles        Stories      (Group Topics)       │
│   Reuters API)           (1-5 min)      (2-10 min)    (5 min)              │
│                                                                              │
│                            ↓ (DB1 - Pipeline DB)                            │
│                                                                              │
│  LLM Enrichment  ──→  Editorial Review  ──→  Sync to DB2                   │
│  (Summaries,          (Webadmin UI)         (Transform &                   │
│   Timelines,          Flask Web App         Validate)                       │
│   Forecasts,          Port 8000             (1-5 min)                       │
│   Audio TTS)                                                                │
│  (10-30 min)                                                                │
│                                                                              │
└─────────────────────────────────────────────────────────────────────────────┘
                                        ↓
                    ┌───────────────────────────────────────┐
                    │   PostgreSQL DB2 (Customer App Data) │
                    │   - Events/Articles                  │
                    │   - Stories/Analyses                 │
                    │   - Localized Content (EN/HI)        │
                    │   - SEO Tags & Relationships         │
                    │   - User Data                        │
                    └───────────────────────────────────────┘
                                        ↓
┌─────────────────────────────────────────────────────────────────────────────┐
│                      CORE SERVICE (Node.js/Express)                          │
│                    Customer-Facing REST API Server                           │
├─────────────────────────────────────────────────────────────────────────────┤
│                                                                              │
│  GET /api/articles          Article Retrieval     ↑                        │
│  GET /api/articles/:id      Article Detail       │                        │
│  POST /api/assistant/query  AI Q&A (RAG)   ──→ Vector Search               │
│  GET /api/user/milestones   Gamification        (pgvector)                 │
│  POST /api/user/profile     Profile Mgmt         │                        │
│  POST /api/voice/transcribe Voice Recognition   ↓                        │
│                                                                              │
│  Firebase Auth  │  S3 Image Delivery  │  FCM Push Notifications            │
│  OpenAI LLM     │  Embeddings (Xenova)│  Badge System & Activity Tracking  │
│                                                                              │
└─────────────────────────────────────────────────────────────────────────────┘
                                        ↓
                    ┌───────────────────────────────────────┐
                    │   Mobile/Web Frontend                 │
                    │   (User Engagement)                   │
                    └───────────────────────────────────────┘
```

---

## Services Overview

### 1. **NECLS Backend (Python)**
Automated hourly pipeline that transforms raw news into editorial content.

**Key Responsibilities:**
- 🔗 **Extraction**: Ingest articles from 15+ news sources (RSS, sitemaps, APIs)
- 🎯 **Clustering**: Group related articles into coherent stories using embeddings
- 🧠 **LLM Enrichment**: Generate bilingual summaries, timelines, forecasts
- 📻 **Audio Generation**: Create TTS narration in English & Hindi
- ✅ **Editorial Review**: Flask web UI for human curation
- 📤 **Sync**: Mirror processed content to customer database

**Technology:**
- Python 3 with FastAPI/Flask
- PostgreSQL + pgvector (semantic search)
- OpenAI (GPT-4/GPT-5), Google Gemini (TTS)
- scikit-learn (clustering algorithms)
- BeautifulSoup, feedparser (web scraping)

**Runtime:** ~30-60 minutes per hour (hourly cron or AWS EventBridge)

### 2. **Core Service (Node.js/TypeScript)**
24/7 REST API serving content and AI features to users.

**Key Responsibilities:**
- 📰 **Article Delivery**: Cursor-based pagination, localization, filtering
- 🤖 **AI Assistant**: RAG-based semantic Q&A using pgvector
- 👤 **User Management**: Profiles, activity tracking, interests
- 🏆 **Gamification**: Badges, streaks, milestones
- 🔊 **Voice Processing**: Audio transcription via OpenAI Whisper
- 📬 **Notifications**: Firebase Cloud Messaging for push alerts

**Technology:**
- Node.js 20 + TypeScript + Express.js 5
- Sequelize ORM for PostgreSQL
- Xenova transformers (local embedding model)
- Firebase Admin SDK (auth, notifications)
- AWS SDK (S3 for image delivery)

**Runtime:** Continuous (Docker container or VM)

---

## Tech Stack Matrix

| Component | Technology | Role |
|-----------|-----------|------|
| **Backend (Pipeline)** | Python 3 | News processing orchestration |
| **Backend (API)** | Node.js 20 + TypeScript | REST API & AI features |
| **Database** | PostgreSQL 16 + pgvector | Data storage & vector search |
| **ORM (Python)** | SQLAlchemy | Data modeling (NECLS) |
| **ORM (Node)** | Sequelize | Data modeling (Core Service) |
| **LLM** | OpenAI (GPT-5-nano/GPT-4) | Chat, summaries, analysis |
| **Embeddings** | Xenova all-MiniLM-L6-v2 | Semantic search (384 dims) |
| **TTS** | Google Gemini + OpenAI | Audio narration generation |
| **Web Scraping** | BeautifulSoup, News-Please | Article extraction |
| **Clustering** | scikit-learn | Story grouping algorithm |
| **Vector Search** | pgvector + IVFflat | Efficient similarity search |
| **Authentication** | Firebase Admin | User login & device tokens |
| **Push Notifications** | Firebase Cloud Messaging | Real-time alerts |
| **Storage** | AWS S3 | Images, audio, backups |
| **Web Admin UI** | Flask + Flask-Login | Editorial review interface |
| **Containerization** | Docker + Docker Compose | Local & cloud deployment |
| **Version Control** | Git | Source code management |

---

## Portfolio Highlights

### 🎯 **Scalable Architecture**
- Separated concerns: pipeline (Python) vs. API (Node.js)
- Horizontal scaling: multiple pipeline workers, parallel LLM processing
- Connection pooling and optimized queries for production workloads

### 🚀 **Advanced RAG Implementation**
- 9-step semantic query pipeline with fallback strategies
- Entity extraction and synonym expansion
- Multi-pass vector search (5-day → 10-day → all-time fallback)
- Recency-weighted scoring to balance freshness and relevance

### 📊 **Intelligent Clustering**
- Two-phase clustering: centroid attachment + agglomerative clustering
- Time-windowed grouping to prevent false positives
- Incremental updates to avoid re-clustering all articles

### 🌐 **Multi-Language Support**
- Bilingual content: English & Hindi
- Automatic language detection and translation
- Localized TTS with culturally-appropriate voices

### 🎮 **User Engagement System**
- Real-time badge unlocking with configurable thresholds
- Streak tracking with 1 rest-day-per-week flexibility
- Activity-based milestone progression
- Seamless Firebase integration for authentication

### 📈 **Production-Grade Reliability**
- Idempotent operations (safe to retry)
- Comprehensive error handling and fallbacks
- Token usage tracking for cost optimization
- Input hash deduplication to prevent re-processing
- Database connection pooling and query optimization

---

## Quick API Examples

### Get Latest Articles
```bash
curl "http://localhost:7090/api/articles?locale=en&limit=5"
```

### Ask AI Assistant a Question
```bash
curl -X POST "http://localhost:7090/api/assistant/query?locale=en" \
  -H "Content-Type: application/json" \
  -H "Authorization: Bearer YOUR_FIREBASE_TOKEN" \
  -d '{"question": "What is happening with AI and job markets?"}'
```

### Get Article Details with Analysis
```bash
curl "http://localhost:7090/api/articles/ARTICLE_ID?locale=en" \
  -H "Authorization: Bearer YOUR_FIREBASE_TOKEN"
```

### Update User Profile
```bash
curl -X POST "http://localhost:7090/api/user/profile" \
  -H "Content-Type: application/json" \
  -H "Authorization: Bearer YOUR_FIREBASE_TOKEN" \
  -d '{"interests": ["AI", "Finance", "Technology"]}'
```

### Get User Milestones
```bash
curl "http://localhost:7090/api/user/milestones" \
  -H "Authorization: Bearer YOUR_FIREBASE_TOKEN"
```

---

## Project Structure

```
thinko-news-platform/
├── README.md                      # This file
├── ARCHITECTURE.md                # Technical deep-dive
├── PERFORMANCE.md                 # Performance benchmarks
├── docker-compose.yml             # Full-stack orchestration
├── .env.example                   # Environment variables template
├── .gitignore                     # Git exclusions (prevents secret commits)
│
├── core-service/                  # Node.js REST API
│   ├── src/
│   │   ├── index.ts               # Server entry point
│   │   ├── app/                   # Route handlers
│   │   │   ├── article/           # Article endpoints
│   │   │   ├── assistant/         # AI Q&A endpoints
│   │   │   ├── user/              # User management
│   │   │   ├── firebase/          # Auth middleware
│   │   │   ├── notification/      # Push notifications
│   │   │   ├── badge/             # Badge system
│   │   │   └── ...                # (15+ route groups)
│   │   ├── db/
│   │   │   └── app-db/
│   │   │       ├── index.ts       # Sequelize initialization
│   │   │       └── models/        # 21 data models
│   │   └── config/                # Configuration
│   ├── scripts/
│   │   ├── seed.ts                # Database seeding
│   │   └── migrations/            # SQL migrations
│   ├── package.json               # Node.js dependencies
│   ├── tsconfig.json              # TypeScript config
│   ├── Dockerfile                 # Container image
│   └── .env.example               # Service-specific env vars
│
├── necls-backend/                 # Python Pipeline
│   ├── necls_backend/
│   │   ├── config.py              # Configuration loading
│   │   ├── extractor.py           # Feed crawling
│   │   ├── clustering.py          # Story clustering
│   │   ├── embeddings.py          # Vector embeddings
│   │   ├── db.py                  # DB1 schema (SQLAlchemy)
│   │   ├── app_db.py              # DB2 schema (SQLAlchemy)
│   │   ├── llm_pipeline/          # LLM orchestration
│   │   │   ├── pipeline.py        # Main LLM workflow
│   │   │   ├── llm_client.py      # OpenAI wrapper
│   │   │   ├── audio.py           # TTS integration
│   │   │   └── repository.py      # Data access layer
│   │   ├── prompts/               # LLM prompt templates
│   │   ├── webadmin/
│   │   │   └── app.py             # Flask editorial UI
│   │   └── __init__.py            # Package init
│   ├── scripts/
│   │   ├── run_pipeline.py        # Main orchestrator
│   │   ├── extract_articles.py    # Step 1: extraction
│   │   ├── cluster_articles.py    # Step 2: clustering
│   │   ├── llm_pipeline.py        # Step 4: enrichment
│   │   ├── sync_app_db.py         # Step 5: sync to DB2
│   │   └── ...                    # (12 total scripts)
│   ├── debug_scripts/             # Development utilities
│   ├── feeds.json                 # News source configuration
│   ├── requirements.txt           # Python dependencies
│   ├── Dockerfile                 # Container image
│   └── .env.example               # Service-specific env vars
│
├── infrastructure/                # Deployment & setup
│   ├── postgres/
│   │   ├── init.sql               # Database initialization
│   │   └── seed.sql               # Demo seed data
│   └── migrations/                # Database migrations
│
└── docs/                          # Detailed documentation
    ├── api-reference.md           # REST API reference
    ├── data-flow.md               # Pipeline data flows
    └── local-setup.md             # Detailed setup guide
```

---

## Local Development Setup

### Prerequisites
- Docker & Docker Compose (or PostgreSQL 16 + pgvector locally)
- Node.js 20 & npm (for Core Service development)
- Python 3.10+ (for NECLS Backend development)
- Git

### Full Stack (Docker)
```bash
# Start all services
docker-compose up -d

# Check service health
docker-compose ps

# View logs
docker-compose logs -f

# Stop all services
docker-compose down
```

### Core Service Only (Local Development)
```bash
cd core-service
npm install
npm run dev           # Starts on port 7090
```

### NECLS Backend Only (Local Development)
```bash
cd necls-backend
python -m venv venv
source venv/bin/activate  # Windows: venv\Scripts\activate
pip install -r requirements.txt
python scripts/run_pipeline.py
```

See [docs/local-setup.md](docs/local-setup.md) for detailed instructions.

---

## Key Features

### 📰 Content Aggregation
- Crawls 15+ news sources (RSS, sitemaps, Reuters API)
- Automatic URL deduplication
- Multi-language support (English, Hindi)
- Article enrichment with metadata

### 🎯 Intelligent Story Clustering
- Semantic embeddings (384-dimensional vectors)
- Two-phase clustering algorithm
- Time-windowed grouping
- Automatic headline generation

### 🧠 AI-Powered Enrichment
- GPT-powered summaries & bullet points
- Timeline generation ("story so far")
- Scenario forecasting ("looking ahead")
- Multi-language support

### 📻 Audio Generation
- Text-to-speech in English & Hindi
- Google Gemini (natural voices) with OpenAI fallback
- S3 storage with presigned URLs
- Configurable audio quality

### 💬 Semantic Q&A
- User questions answered using news content
- 384-dimensional vector embeddings
- Multi-pass search with recency weighting
- 2-4 second average response time

### 👤 User Management
- Firebase authentication
- Interest-based personalization
- Activity tracking & analytics
- Custom collections & bookmarks

### 🏆 Gamification
- 18+ achievement badges
- Streaks with rest-day flexibility
- Milestone progression
- Push notifications for unlocks

### 🌐 Multi-Language
- Automatic Hindi ↔ English translation
- Localized content (titles, descriptions, audio)
- Language detection
- Culture-appropriate voices

---

## Configuration

### Environment Variables
All services read from `.env` file. Copy `.env.example` and fill in:

```bash
cp .env.example .env
# Edit .env with your API keys
```

Key variables:
- `OPENAI_API_KEY` — OpenAI GPT API access
- `GEMINI_API_KEY` — Google TTS API access
- `FIREBASE_SERVICE_ACCOUNT` — Firebase auth & notifications
- `AWS_ACCESS_KEY_ID`, `AWS_SECRET_ACCESS_KEY` — S3 storage
- `DB_USER`, `DB_PASSWORD` — Database credentials

### Pipeline Scheduling
- `PIPELINE_INTERVAL_MIN=0` — Run once and exit
- `PIPELINE_INTERVAL_MIN=60` — Run every 60 minutes
- In production: Use AWS EventBridge or cron for orchestration

### Clustering Thresholds
- `CLUSTERING_THETA=0.55` — Centroid similarity (0.0-1.0)
- `CLUSTERING_THRESHOLD=0.6` — Agglomerative distance (0.0-1.0)
- Lower = more liberal clustering; higher = stricter grouping

---

## Performance Characteristics

- **RAG Query Latency**: ~2-4 seconds (embedding + search + LLM)
- **Embedding Model**: Xenova all-MiniLM-L6-v2 (local, no API cost)
- **Vector Similarity**: pgvector with IVFflat indexing (~50ms for 10K vectors)
- **Pipeline Throughput**: 100-500 articles/hour (tunable)
- **Concurrent Users**: 1000+ (horizontal scaling ready)
- **Database**: 5-connection pool, <100ms queries on indexed fields

See [PERFORMANCE.md](PERFORMANCE.md) for detailed benchmarks.

---

## Security Considerations

⚠️ **Important**: This is a portfolio project demonstrating architecture and capabilities.

- Never commit `.env` files (added to `.gitignore`)
- Never copy `.env` into Docker images
- Always use environment variables for secrets in production
- Implement rate limiting on API endpoints
- Validate and sanitize user input
- Use HTTPS in production
- Rotate API keys regularly
- Implement database SSL connections

---

## Deployment

### Docker
```bash
docker build -t thinko-core:latest ./core-service
docker build -t thinko-necls:latest ./necls-backend
docker run --env-file .env -p 7090:7090 thinko-core:latest
```

### Kubernetes
See deployment manifests in `infrastructure/` (create separate PR)

### AWS
- **NECLS Pipeline**: Fargate + EventBridge (hourly schedule)
- **Core Service**: ECS or EC2 + ALB
- **Database**: RDS PostgreSQL + Aurora
- **Storage**: S3 for images and audio

---

## Troubleshooting

**Database connection fails:**
```bash
# Check PostgreSQL is running
docker-compose ps postgres

# Verify credentials match .env
docker-compose logs postgres
```

**API returns 500 errors:**
```bash
# Check logs
docker-compose logs core-service

# Verify database tables exist
psql -h localhost -U admin -d app_db
```

**LLM queries fail:**
- Verify `OPENAI_API_KEY` is valid
- Check OpenAI API quota
- See logs for rate limit errors

**Audio generation times out:**
- Verify `GEMINI_API_KEY` is valid
- Check network connectivity
- Fall back to `OPENAI_API_KEY` for TTS

---

## Contributing

This is a complete working system. Feel free to:
- ✅ Extend with new APIs
- ✅ Improve clustering algorithms
- ✅ Add new LLM prompts
- ✅ Enhance UI
- ✅ Add metrics & observability

Do **not**:
- ❌ Commit secrets or API keys
- ❌ Remove authentication checks
- ❌ Simplify without maintaining reliability

---

## License

**For Portfolio/Educational Use Only**

This project is a demonstration of enterprise architecture and AI/ML engineering practices. It is intended for portfolio, educational, and interview demonstration purposes only.

---

## Architecture Decisions

See [ARCHITECTURE.md](ARCHITECTURE.md) for detailed technical decisions including:
- Why separate Python (pipeline) and Node.js (API) services
- Clustering algorithm design (two-phase approach)
- Vector embedding strategy (384 dimensions)
- Multi-language support implementation
- Gamification system design
- Database schema optimization

---

## Support

For questions about architecture, design decisions, or implementation details, refer to:
- [ARCHITECTURE.md](ARCHITECTURE.md) — Technical deep-dive
- [PERFORMANCE.md](PERFORMANCE.md) — Performance analysis
- [docs/api-reference.md](docs/api-reference.md) — API documentation
- [docs/data-flow.md](docs/data-flow.md) — Pipeline documentation
- [docs/local-setup.md](docs/local-setup.md) — Setup guide

---

**Built with ❤️ as a comprehensive portfolio piece demonstrating full-stack AI/ML engineering.**

# Local Development Setup Guide

Complete step-by-step guide to run ThinkO News Platform locally.

---

## Option 1: Docker Compose (Recommended - 5 Minutes)

**Prerequisites:**
- Docker & Docker Compose installed
- 4GB RAM, 10GB disk space available

**Steps:**

```bash
# 1. Navigate to project directory
cd ~/Desktop/thinko-news-platform

# 2. Copy environment template
cp .env.example .env

# 3. (Optional) Edit .env with your API keys
# For demo/testing, you can skip this - dummy keys are provided in docker-compose.yml
# For production use, add:
#   OPENAI_API_KEY=sk-your-key
#   GEMINI_API_KEY=your-gemini-key
#   AWS_ACCESS_KEY_ID=your-aws-key
#   etc.

# 4. Start all services
docker-compose up -d

# 5. Wait for services to start (30-60 seconds)
docker-compose logs -f postgres
# Wait for: "database system is ready to accept connections"
# Press Ctrl+C to exit logs

# 6. Check service health
docker-compose ps
# Should show:
#   postgres          UP
#   core-service      UP
#   necls-pipeline    UP (will exit after running once)
#   necls-webadmin    UP

# 7. Test the API
curl http://localhost:7090/health
# Should return: {"status": "ok"}

# 8. Access web interfaces
# Core Service API:    http://localhost:7090
# Webadmin Editorial:  http://localhost:8000
#   Username: admin
#   Password: changeme
```

**Verify Everything Works:**

```bash
# View API logs
docker-compose logs core-service | head -20

# View pipeline logs
docker-compose logs necls-pipeline | head -20

# Check database
docker-compose exec postgres psql -U admin -d app_db -c "SELECT COUNT(*) FROM events;"
# Should show: count=3 (from seed data)

# View running containers
docker-compose ps
```

**Stop Services:**
```bash
# Stop all services (keep data)
docker-compose stop

# Stop & remove containers (keep data volume)
docker-compose down

# Full cleanup (delete all data)
docker-compose down -v
```

---

## Option 2: Local Installation (Advanced - 20 Minutes)

**Prerequisites:**
- PostgreSQL 16 with pgvector extension
- Node.js 20 & npm
- Python 3.10+
- Git

### Step 1: Install PostgreSQL with pgvector

**macOS (Homebrew):**
```bash
brew install postgresql@16
brew install pgvector
brew services start postgresql@16

# Verify
psql --version
```

**Ubuntu/Debian:**
```bash
sudo apt-get update
sudo apt-get install postgresql-16 postgresql-contrib-16

# Install pgvector
sudo apt-get install postgresql-16-pgvector

sudo systemctl start postgresql
```

**Windows (WSL2 Recommended):**
```bash
# Inside WSL2 Ubuntu:
sudo apt-get update
sudo apt-get install postgresql postgresql-contrib postgresql-16-pgvector

sudo service postgresql start
```

### Step 2: Create Databases

```bash
# Connect to PostgreSQL
psql -U postgres

# Inside psql:
CREATE USER admin WITH PASSWORD 'changeme';
CREATE DATABASE feedcrawler_db OWNER admin;
CREATE DATABASE app_db OWNER admin;

# Enable pgvector
\c feedcrawler_db
CREATE EXTENSION vector;
CREATE EXTENSION "uuid-ossp";

\c app_db
CREATE EXTENSION vector;
CREATE EXTENSION "uuid-ossp";

\q
```

**Verify:**
```bash
psql -U admin -d app_db -c "\dx"
# Should show: vector | public | extension
```

### Step 3: Setup Core Service (Node.js)

```bash
# Navigate to service
cd core-service

# Install dependencies
npm install

# Copy environment
cp .env.example .env

# Update .env with your database:
# APP_DB_HOST=localhost
# APP_DB_PORT=5432
# APP_DB_USER=admin
# APP_DB_PASSWORD=changeme
# APP_DB_NAME=app_db

# Build TypeScript
npm run build

# Run migrations (Sequelize will create tables)
npm run migrate

# Start development server
npm run dev
# Should log: "Server listening on port 7090"
```

**Test Core Service:**
```bash
curl http://localhost:7090/health
# Should return: {"status": "ok"}

curl http://localhost:7090/api/articles?limit=1
# Should return articles (may be empty if no data seeded)
```

### Step 4: Setup NECLS Backend (Python)

```bash
# Navigate to service
cd necls-backend

# Create virtual environment
python -m venv venv
source venv/bin/activate  # Windows: venv\Scripts\activate

# Install dependencies
pip install -r requirements.txt

# Copy environment
cp .env.example .env

# Update .env with your database:
# FEEDCRAWLER_DB_HOST=localhost
# APP_DB_HOST=localhost
# (etc. - same as core-service)

# Run once to initialize DB & test
python scripts/run_pipeline.py
# Should extract articles, cluster them, and sync to DB2
# This may take 5-15 minutes on first run
```

**Test NECLS:**
```bash
# Check database
psql -U admin -d feedcrawler_db -c "SELECT COUNT(*) FROM articles;"

# Check if events synced to app_db
psql -U admin -d app_db -c "SELECT COUNT(*) FROM events;"
```

### Step 5: Run Webadmin (Editorial UI)

```bash
# In necls-backend directory (with venv activated)
python -m necls_backend.webadmin.app
# Should log: "Running on http://127.0.0.1:8000"

# Access at http://localhost:8000
# Login: admin / changeme
```

---

## Configuration & Customization

### Environment Variables

**Create .env file from template:**
```bash
cp .env.example .env
```

**Key variables to customize:**

```bash
# API Keys (get from services below)
OPENAI_API_KEY=sk-your-openai-key
GEMINI_API_KEY=your-gemini-api-key
AWS_ACCESS_KEY_ID=your-aws-key
AWS_SECRET_ACCESS_KEY=your-aws-secret

# Database (local dev)
DB_USER=admin
DB_PASSWORD=changeme
APP_DB_HOST=localhost
FEEDCRAWLER_DB_HOST=localhost

# Pipeline settings
PIPELINE_INTERVAL_MIN=0      # 0 = run once, 60 = hourly
EXTRACT_HOURS_RECENCY=24     # Extract articles from last 24 hours
CLUSTERING_THETA=0.55        # Centroid similarity threshold
CLUSTERING_THRESHOLD=0.6     # Agglomerative distance threshold

# Admin credentials (webadmin UI)
INITIAL_ADMIN_USERNAME=admin
INITIAL_ADMIN_PASSWORD=changeme

# Webadmin
CORE_SERVICE_URL=http://localhost:7090
```

### Getting API Keys

**OpenAI:**
1. Go to https://platform.openai.com/api-keys
2. Create new secret key
3. Paste into .env: `OPENAI_API_KEY=sk-...`

**Google Gemini (Text-to-Speech):**
1. Go to https://makersuite.google.com/app/apikey
2. Create new API key
3. Paste into .env: `GEMINI_API_KEY=...`

**Firebase (Optional):**
1. Go to https://console.firebase.google.com
2. Create project
3. Download service account JSON
4. Paste entire JSON into .env: `FIREBASE_SERVICE_ACCOUNT='{"type":"service_account",...}'`

**AWS S3 (Optional):**
1. Go to https://console.aws.amazon.com/iam
2. Create IAM user with S3 access
3. Get access key & secret
4. Paste into .env

---

## Troubleshooting

### PostgreSQL Connection Failed
```
Error: connect ECONNREFUSED 127.0.0.1:5432

Solutions:
1. Check PostgreSQL is running:
   ps aux | grep postgres

2. Restart PostgreSQL:
   # macOS:
   brew services restart postgresql@16

   # Linux:
   sudo service postgresql restart

3. Check credentials:
   psql -U admin -h localhost
   (enter password: changeme)
```

### "pgvector extension not found"
```
Error: EXTENSION vector does not exist

Solutions:
1. Install pgvector:
   # macOS: brew install pgvector
   # Linux: sudo apt-get install postgresql-16-pgvector

2. Create extension:
   psql -U admin -d app_db
   CREATE EXTENSION vector;
```

### Node.js "Cannot find module"
```
Error: Cannot find module 'express'

Solutions:
1. Install dependencies:
   npm install

2. Check Node version:
   node --version  (should be v20+)

3. Clear cache:
   rm -rf node_modules package-lock.json
   npm install
```

### Python "ModuleNotFoundError"
```
Error: ModuleNotFoundError: No module named 'openai'

Solutions:
1. Activate venv:
   source venv/bin/activate  # or: venv\Scripts\activate

2. Install dependencies:
   pip install -r requirements.txt

3. Check Python version:
   python --version  (should be 3.10+)
```

### API Returns Empty Results
```
curl http://localhost:7090/api/articles
# Returns: {"articles": []}

Solutions:
1. Seed data:
   # Run NECLS pipeline to generate articles
   python necls-backend/scripts/run_pipeline.py

2. Check database:
   psql -U admin -d app_db -c "SELECT COUNT(*) FROM events;"

3. Check sync:
   docker-compose logs necls-pipeline | grep "synced"
```

### LLM Queries Fail (401 Unauthorized)
```
Error: 401 Unauthorized from OpenAI API

Solutions:
1. Check API key is valid:
   curl https://api.openai.com/v1/models \
     -H "Authorization: Bearer sk-YOUR_KEY"

2. Check key format:
   Should start with "sk-"
   Should be in .env: OPENAI_API_KEY=sk-...

3. Check quota:
   Go to https://platform.openai.com/account/usage/overview
```

### Docker Compose Fails to Start
```
Error: Cannot connect to Docker daemon

Solutions:
1. Check Docker is running:
   docker ps

2. Start Docker:
   # macOS: Open Docker Desktop
   # Linux: sudo systemctl start docker

3. Check permissions:
   sudo usermod -aG docker $USER
   newgrp docker
```

---

## Performance Tuning

### Increase Concurrency
```env
# In .env:
# Node.js connection pool (core-service)
DB_POOL_MAX=10
DB_POOL_MIN=5

# Python connection pool (necls-backend)
DB_POOL_SIZE=15
DB_MAX_OVERFLOW=25
```

### Faster LLM Responses
```env
OPENAI_ASSISTANT_MODEL=gpt-4o-mini  # Faster than gpt-5-nano
```

### Limit Pipeline Scope
```env
EXTRACT_HOURS_RECENCY=6    # Only last 6 hours (faster extraction)
MAX_CLUSTERS_TO_PROCESS=20 # Process only 20 clusters per run
```

### Vector Search Optimization
```bash
# Create IVFflat index manually
psql -U admin -d app_db << 'EOF'
CREATE INDEX IF NOT EXISTS idx_chunks_embedding
  ON assistant_chunk USING ivfflat (embedding vector_cosine_ops)
  WITH (lists=100);
EOF
```

---

## Common Tasks

### Seed Demo Data
```bash
# Docker:
docker-compose exec postgres psql -U admin -d app_db \
  -f /docker-entrypoint-initdb.d/02-seed.sql

# Local:
psql -U admin -d app_db -f infrastructure/postgres/seed.sql
```

### Clear All Data
```bash
# Docker:
docker-compose down -v   # Removes data volumes

# Local:
psql -U admin -d app_db -c "DROP SCHEMA public CASCADE; CREATE SCHEMA public;"
```

### View Logs in Real-Time
```bash
# Docker:
docker-compose logs -f core-service
docker-compose logs -f necls-pipeline

# Local:
# Press Ctrl+C in service terminal
# Restart with: npm run dev (Node) or python scripts/run_pipeline.py (Python)
```

### Debug Database Queries
```bash
# Connect to database
psql -U admin -d app_db

# List tables
\dt

# View table structure
\d events

# Run queries
SELECT * FROM events LIMIT 5;
SELECT COUNT(*) FROM assistant_chunk WHERE event_id = 'UUID';
```

### Test Vector Search
```bash
# Connect to database
psql -U admin -d app_db

# Run similarity search
SELECT id, event_id, 1 - (embedding <=> '[0.1, 0.2, ...]'::vector) as similarity
FROM assistant_chunk
ORDER BY similarity DESC
LIMIT 5;
```

---

## Next Steps

1. **Explore the API:** Read [api-reference.md](api-reference.md)
2. **Understand data flow:** Read [data-flow.md](data-flow.md)
3. **Study architecture:** Read [../ARCHITECTURE.md](../ARCHITECTURE.md)
4. **Run your own pipeline:** Edit [feeds.json](../necls-backend/feeds.json) to add news sources
5. **Customize LLM prompts:** Edit files in [../necls-backend/necls_backend/prompts/](../necls-backend/necls_backend/prompts/)
6. **Deploy to cloud:** See [../DEPLOYMENT.md](../DEPLOYMENT.md)

---

## Getting Help

- Check logs: `docker-compose logs SERVICE_NAME`
- Review errors: Look for "ERROR" or "Exception" in logs
- Database debugging: Connect with psql and run queries
- API testing: Use curl or Postman
- Service health: `curl http://localhost:7090/health`

Happy developing! 🚀

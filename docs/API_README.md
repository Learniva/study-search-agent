# REST API Reference

Production-grade Multi-Agent Study & Grading System API.

## Quick Start

```bash
python -m api.app
```

**Docs:** http://localhost:8000/docs

## Endpoints

| Method | Endpoint | Auth | Description |
|--------|----------|------|-------------|
| **Health** ||||
| GET | `/` | - | API info |
| GET | `/health` | - | Health check |
| GET | `/metrics` | - | Prometheus metrics |
| **Query** ||||
| POST | `/query/` | Header | Main query endpoint |
| POST | `/query/stream` | Header | SSE streaming |
| GET | `/query/history/{thread_id}` | - | Conversation history |
| **Documents** ||||
| GET | `/documents/` | - | List documents |
| POST | `/documents/upload` | - | Upload PDF/DOCX/TXT/MD |
| DELETE | `/documents/{filename}` | - | Delete document |
| **Grading** ||||
| GET | `/grading/history/{professor_id}` | Teacher | Grading history |
| GET | `/grading/session/{session_id}` | Teacher | Session details |
| GET | `/grading/rubrics/{professor_id}` | Teacher | List rubrics |
| POST | `/grading/rubrics` | Teacher | Create rubric |
| POST | `/grading/feedback` | Teacher | Submit feedback |
| **ML Features** ||||
| POST | `/ml/feedback` | - | User feedback |
| GET | `/ml/profile/{user_id}` | - | User profile |
| GET | `/ml/stats` | - | ML statistics |
| **Admin** ||||
| POST | `/admin/reload` | Admin | Reload documents |
| GET | `/admin/cache/stats` | Admin | Cache stats |

## Authentication

**Headers:**
- `X-User-Role`: `student` / `teacher` / `admin`
- `X-User-ID`: User identifier (optional)
- `X-Correlation-ID`: Request tracking (optional)

**Access:**
- Student → Study Agent only
- Teacher → Study + Grading
- Admin → Full access

## Usage

### Basic Query

```bash
curl -X POST http://localhost:8000/query/ \
  -H "X-User-Role: student" \
  -H "Content-Type: application/json" \
  -d '{"question": "Explain neural networks", "thread_id": "session1"}'
```

### Grading Query

```bash
curl -X POST http://localhost:8000/query/ \
  -H "X-User-Role: teacher" \
  -H "X-User-ID: prof123" \
  -H "Content-Type: application/json" \
  -d '{
    "question": "Grade this essay: ...",
    "user_role": "teacher",
    "professor_id": "prof123",
    "student_id": "stu456"
  }'
```

### Python Client

```python
import requests

response = requests.post(
    "http://localhost:8000/query/",
    headers={"X-User-Role": "student"},
    json={"question": "Generate MCQs", "thread_id": "s1"}
)
print(response.json()["answer"])
```

## Architecture

```
Request → [CORS → Rate Limit → Tracing] 
       → Router → Supervisor 
       → [Study Agent | Grading Agent]
```

**Agents:**
- **Study:** document_qa, web_search, python_repl, manim_animation
- **Grading:** grade_essay, review_code, grade_mcq, evaluate_with_rubric

**Storage:**
- PostgreSQL (persistence, checkpointing)
- ChromaDB (document vectors, rubric RAG)
- Redis (distributed cache, scaling)

## Configuration

**Essential:**
```bash
GOOGLE_API_KEY=xxx              # Required
DATABASE_URL=postgresql+asyncpg://...
REDIS_URL=redis://localhost:6379
```

**API:**
```bash
API_HOST=0.0.0.0
API_PORT=8000
API_WORKERS=4
```

**Features:**
```bash
RATE_LIMIT_ENABLED=true
RATE_LIMIT_PER_MINUTE=60
ENABLE_ML_FEATURES=true
ENABLE_STREAMING=true
LOG_LEVEL=INFO
```

**See:** `config/settings.py` for all options

## Deployment

### Docker

```bash
docker build -t study-api .
docker run -p 8000:8000 -e GOOGLE_API_KEY=xxx study-api
```

### Docker Compose

```yaml
services:
  api:
    build: .
    ports: ["8000:8000"]
    environment:
      - GOOGLE_API_KEY=${GOOGLE_API_KEY}
      - DATABASE_URL=postgresql+asyncpg://postgres:postgres@db/grading
      - REDIS_URL=redis://redis:6379
    depends_on: [db, redis]
  
  db:
    image: postgres:15-alpine
    volumes: [postgres_data:/var/lib/postgresql/data]
  
  redis:
    image: redis:7-alpine
    volumes: [redis_data:/data]
```

### Production

```bash
# Multiple workers
uvicorn api.app:app --host 0.0.0.0 --port 8000 --workers 4

# With Gunicorn
gunicorn -w 4 -k uvicorn.workers.UvicornWorker api.app:app
```

## Performance

| Operation | Time | Notes |
|-----------|------|-------|
| Study query | 2-10s | Tool dependent |
| Grading | 10-20s | LLM analysis |
| Routing | <1s | Classification |
| DB save | <0.5s | Async |

**Optimizations:**
- Connection pool: 10 base, 20 overflow
- Cache: In-memory (1000 entries, 300s TTL) + Redis
- Async database ops
- Background document processing

## Monitoring

```bash
# Health
curl http://localhost:8000/health

# Metrics
curl http://localhost:8000/metrics

# Active instances (distributed)
curl http://localhost:8000/admin/instances
```

**Metrics:** Request count, latency (p50/p95/p99), pool stats, cache hit/miss

---

**Stack:** FastAPI + LangGraph + SQLAlchemy + ChromaDB + Redis

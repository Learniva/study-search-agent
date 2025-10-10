# PostgreSQL Database

Production-grade async persistence with RAG, conversation memory, and self-improvement.

## Overview

**Optional:** Works without database (no persistence)  
**Recommended:** Production with grading history, conversation memory, RAG learning

**Features:** Async operations • Connection pooling • LangGraph checkpointing • pgvector RAG • Self-learning • Audit logs

## Schema

### Tables

| Category | Table | Purpose |
|----------|-------|---------|
| **Grading** | `grading_sessions` | Complete history (score, feedback, AI metadata) |
| | `rubric_templates` | Reusable rubrics (criteria, weights) |
| | `professor_configurations` | User preferences and settings |
| | `grading_statistics` | Aggregated analytics |
| **RAG** | `document_vectors` | L2 Vector Store (pgvector embeddings) |
| | `grade_exceptions` | L3 Learning Store (self-correction) |
| | `rag_query_logs` | RAG performance tracking |
| **System** | `users` | Accounts (role, email, LMS) |
| | `audit_logs` | FERPA-compliant audit trail |
| | `langgraph_checkpoints` | Conversation state (multi-turn) |

## Installation

| Platform | Commands |
|----------|----------|
| **macOS** | `brew install postgresql@15 && brew services start postgresql@15 && createdb grading_system` |
| **Linux** | `sudo apt install postgresql && sudo systemctl start postgresql && sudo -u postgres createdb grading_system` |
| **Docker** | `docker run --name grading-db -e POSTGRES_DB=grading_system -p 5432:5432 -d postgres:15` |

### Enable pgvector (RAG)

```bash
psql grading_system -c "CREATE EXTENSION IF NOT EXISTS vector;"
```

## Configuration

```bash
# Async PostgreSQL (production)
DATABASE_URL=postgresql+asyncpg://user:pass@host/grading_system

# Connection pool
DB_POOL_SIZE=10
DB_MAX_OVERFLOW=20
DB_POOL_RECYCLE=3600

# Setup
alembic upgrade head
```

## Features

### Async Operations

```python
from database.core.async_engine import async_db_engine

async with async_db_engine.get_session() as session:
    result = await session.execute(query)
```

### Connection Pooling

```python
from database.monitoring import get_pool_monitor

monitor = get_pool_monitor()
stats = monitor.get_stats()
# → {"utilization_percent": 30, "is_healthy": True}
```

### Conversation Memory (LangGraph)

```python
from database.checkpointing import get_postgres_checkpointer

checkpointer = get_postgres_checkpointer()
# Multi-turn conversations persist across sessions
```

### Self-Improving RAG

**L2 Vector Store (pgvector):** Semantic embeddings for document search  
**L3 Learning Store:** Learn from professor corrections  
**Query Logs:** Track when retrieval helps

## Usage

### Via API

```bash
# Automatic persistence
curl -X POST http://localhost:8000/query/ \
  -H "X-User-Role: teacher" \
  -d '{"question": "Grade essay", "professor_id": "prof123"}'

# Get history
curl http://localhost:8000/grading/history/prof123
```

### Direct Access

```python
from database.operations import get_grading_history

sessions = await get_grading_history(db, professor_id="prof123")
```

## Performance

| Operation | Speed | Notes |
|-----------|-------|-------|
| Session save | <0.3s | Async write |
| History query | <0.5s | 1000 records |
| Vector search | <0.2s | pgvector |
| Checkpoint save | <0.1s | LangGraph |
| Pool: 10+20 | - | Base + overflow |

## Migrations

```bash
# Create
alembic revision --autogenerate -m "description"

# Apply
alembic upgrade head

# Rollback
alembic downgrade -1
```

## Monitoring

```python
from database.monitoring import get_pool_monitor

monitor = get_pool_monitor()

# Real-time metrics
stats = monitor.get_stats()
utilization = monitor.get_current_utilization()

# Health check
healthy = await monitor.health_check()
```

## Troubleshooting

| Problem | Solution |
|---------|----------|
| Connection refused | `brew services start postgresql@15` |
| Role does not exist | Use `postgresql+asyncpg://$(whoami)@localhost/grading_system` |
| pgvector not found | `psql grading_system -c "CREATE EXTENSION vector;"` |
| Pool exhausted | Increase `DB_POOL_SIZE` or `DB_MAX_OVERFLOW` |
| Slow queries | Add indexes, check `EXPLAIN ANALYZE` |

## Backup & Restore

```bash
# Backup
pg_dump grading_system | gzip > backup_$(date +%Y%m%d).sql.gz

# Restore
gunzip < backup.sql.gz | psql grading_system
```

## Security

**Data:** User isolation (foreign keys) • SQL injection protection (ORM) • Encrypted credentials  
**Compliance:** FERPA audit logs • Data retention policies • Export capabilities  
**Access:** Professors (own data) • Students (no access) • Admins (full + audit)

## Quick Commands

```bash
# Setup
alembic upgrade head                  # Apply migrations

# Access
psql grading_system                   # SQL shell

# Monitoring
python -c "from database.monitoring import get_pool_monitor; print(get_pool_monitor().get_stats())"

# Backup
pg_dump grading_system > backup.sql
```

## Architecture

**Stack:** Async SQLAlchemy + asyncpg + connection pooling  
**RAG:** pgvector (L2 semantic) + learning store (L3 corrections)  
**Memory:** LangGraph checkpointing for multi-turn conversations  
**Monitoring:** Real-time pool metrics + health checks

---

**Production-ready async database with RAG, conversation memory, and self-improvement.**

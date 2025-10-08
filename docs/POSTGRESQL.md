# PostgreSQL - Database Setup

Long-term persistence for grading sessions, rubrics, and analytics.

## Overview

**Optional:** Grading works without database (no persistence)  
**Recommended:** Production workflows with grading history

**Stores:**
- Grading sessions (score, feedback, rubric, time)
- Custom rubrics (criteria, weights)
- User preferences
- Audit logs

## Installation

### macOS
```bash
brew install postgresql@15
brew services start postgresql@15
createdb grading_system
```

### Linux
```bash
sudo apt install postgresql postgresql-contrib
sudo systemctl start postgresql
sudo -u postgres createdb grading_system
```

### Docker
```bash
docker run --name grading-postgres \
  -e POSTGRES_DB=grading_system \
  -p 5432:5432 -d postgres:15
```

### Verify
```bash
psql -d grading_system -c "SELECT version();"
```

## Configuration

### Environment
```bash
# .env - Use your Mac username, not "postgres"
DATABASE_URL=postgresql://$(whoami)@localhost:5432/grading_system

# Or with password
DATABASE_URL=postgresql://user:pass@host:5432/grading_system
```

### Dependencies
```bash
pip install sqlalchemy psycopg2-binary alembic asyncpg
```

Already in `requirements.txt`.

### Initialize
```bash
python setup_database.py        # Create tables
python setup_database.py --seed # Add sample data
python setup_database.py --test # Test connection
python setup_database.py --info # View stats
```

## Schema

### Tables

**users:** Accounts (role, email, LMS)  
**grading_sessions:** Complete history (score, feedback, rubric, time)  
**rubric_templates:** Custom rubrics (criteria, weights, public/private)  
**professor_configurations:** User preferences  
**audit_logs:** Audit trail

### Relationships
```
users (1) → (M) grading_sessions
users (1) → (M) rubric_templates
rubric_templates (1) → (M) grading_sessions
```

## Usage

### With Tracking
```bash
# Saves to database (requires --user-id)
python main.py --role professor --user-id prof123 \
  --question "Grade: $(cat test_submissions/essay.txt)"

# Look for:
# ✅ PostgreSQL connected - grading history will be persisted
# ✅ Grading session saved to database (12.5s)
```

### Without Tracking
```bash
# Works but doesn't save (no --user-id)
python main.py --role professor \
  --question "Grade essay..."

# Warning:
# ⚠️  PostgreSQL unavailable - grading history will not be persisted
```

### View History
```bash
# Stats
python setup_database.py --info

# Query sessions
python -c "
from database.database import get_db
from database.models import GradingSession

with get_db() as db:
    sessions = db.query(GradingSession).all()
    for s in sessions:
        print(f'{s.created_at}: {s.grading_type} - {s.score}')
"
```

### API
```bash
# Get history
curl localhost:8000/grading-history \
  -H "Authorization: Bearer $TOKEN"

# Create rubric
curl -X POST localhost:8000/rubrics \
  -H "Authorization: Bearer $TOKEN" \
  -d '{"name": "Essay Rubric", "criteria": {...}}'
```

## Troubleshooting

### Connection refused
```bash
# Check status
brew services list              # macOS
sudo systemctl status postgresql # Linux

# Start
brew services start postgresql@15
```

### Role does not exist
```bash
# Use your username, not "postgres"
DATABASE_URL=postgresql://$(whoami)@localhost:5432/grading_system
```

### Database does not exist
```bash
createdb grading_system
```

### Test connection
```bash
python -c "
from database.database import check_db_connection
print('✅ Connected' if check_db_connection() else '❌ Failed')
"
```

### Reset
```bash
python setup_database.py --reset  # WARNING: Deletes all data
```

## Production

### Environment
```bash
DATABASE_URL=postgresql://user:pass@host:5432/grading_system
DATABASE_POOL_SIZE=20
DATABASE_MAX_OVERFLOW=40
```

### Migration
```bash
alembic revision --autogenerate -m "description"
alembic upgrade head
alembic downgrade -1  # Rollback
```

### Backup
```bash
pg_dump grading_system > backup.sql
psql grading_system < backup.sql
```

## Performance

**Pool:** 10 connections, 20 overflow  
**Session save:** <0.5s  
**History query:** <1s (1000 records)  
**Rubric retrieval:** <0.2s

## Security

**Data:**
- User isolation (foreign keys)
- SQL injection protection (ORM)
- Encrypted credentials (.env)
- FERPA-compliant

**Access:**
- Professors see only their sessions
- Students cannot access database
- Admin has full access

## Commands

```bash
# Setup
python setup_database.py              # Initialize
python setup_database.py --seed       # Sample data
python setup_database.py --test       # Test
python setup_database.py --info       # Stats
python setup_database.py --reset      # Delete all

# Grade with tracking
python main.py --role professor --user-id prof123 --question "..."

# Direct access
psql -d grading_system
```

---

**Optional but recommended for production grading with persistent history.**

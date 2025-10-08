# REST API Reference

FastAPI server for Multi-Agent Study & Grading System with role-based access control.

## Quick Start

```bash
python api/main.py
```

**Server:** http://localhost:8000  
**Docs:** http://localhost:8000/docs (Swagger UI)

## Endpoints

### Study Features (All Users)

| Method | Endpoint | Description |
|--------|----------|-------------|
| GET | `/` | API info |
| GET | `/health` | Status check |
| POST | `/query` | Query agent (multi-agent routing) |
| GET | `/history/{thread_id}` | Conversation history |
| POST | `/documents/upload` | Upload PDF/DOCX |
| GET | `/documents` | List documents |
| DELETE | `/documents/{filename}` | Delete document |
| POST | `/reload` | Re-index documents |

### Grading Features (Teachers Only)

| Method | Endpoint | Auth | Description |
|--------|----------|------|-------------|
| POST | `/grade` | JWT | Direct grading |
| GET | `/grading-history` | JWT | Professor's sessions |
| GET | `/grading/session/{id}` | JWT | Session details |
| POST | `/rubrics` | JWT | Create rubric |
| GET | `/rubrics` | JWT | List rubrics |

## Authentication

**Study queries:** No auth required  
**Grading queries:** JWT token required

### Get Token
```bash
curl -X POST http://localhost:8000/token \
  -d "username=professor&password=secret"
```

**Response:**
```json
{
  "access_token": "eyJ...",
  "token_type": "bearer",
  "role": "teacher"
}
```

## Usage

### Study Query (No Auth)

```bash
curl -X POST http://localhost:8000/query \
  -H "Content-Type: application/json" \
  -d '{
    "question": "Generate 10 MCQs about neural networks",
    "thread_id": "user123"
  }'
```

**Response:**
```json
{
  "question": "Generate 10 MCQs...",
  "answer": "Question 1: ...",
  "agent_used": "Study Agent",
  "thread_id": "user123",
  "success": true
}
```

### Grading Query (Requires Auth)

```bash
curl -X POST http://localhost:8000/grade \
  -H "Authorization: Bearer $TOKEN" \
  -H "Content-Type: application/json" \
  -d '{
    "submission": "Essay text here...",
    "rubric_id": "essay_general",
    "user_id": "prof123",
    "student_id": "stu456"
  }'
```

**Response:**
```json
{
  "score": 85,
  "max_score": 100,
  "grade": "B",
  "feedback": {
    "thesis": {"score": 90, "feedback": "..."},
    "evidence": {"score": 85, "feedback": "..."}
  },
  "strengths": ["...", "..."],
  "improvements": ["...", "..."],
  "session_id": "uuid-here",
  "saved_to_database": true
}
```

### Multi-Agent Query (Auto-Routing)

```bash
# Student query → Study Agent
curl -X POST http://localhost:8000/query \
  -H "Content-Type: application/json" \
  -d '{
    "question": "Grade this essay...",
    "role": "student"
  }'
# Returns: Access denied (routed to deny_access node)

# Teacher query → Grading Agent
curl -X POST http://localhost:8000/query \
  -H "Authorization: Bearer $TOKEN" \
  -d '{
    "question": "Grade this essay...",
    "role": "teacher"
  }'
# Returns: Grading results
```

### View Grading History

```bash
curl http://localhost:8000/grading-history \
  -H "Authorization: Bearer $TOKEN"
```

**Response:**
```json
{
  "professor_id": "prof123",
  "total_sessions": 15,
  "sessions": [
    {
      "id": "uuid",
      "created_at": "2025-10-08T12:00:00",
      "grading_type": "essay",
      "score": 85,
      "student_id": "stu456"
    }
  ]
}
```

### Rubric Management

```bash
# Create rubric
curl -X POST http://localhost:8000/rubrics \
  -H "Authorization: Bearer $TOKEN" \
  -d '{
    "name": "Essay Rubric",
    "rubric_type": "essay",
    "criteria": {
      "thesis": {"weight": 0.25, "description": "..."},
      "evidence": {"weight": 0.30, "description": "..."}
    },
    "max_score": 100
  }'

# List rubrics
curl http://localhost:8000/rubrics \
  -H "Authorization: Bearer $TOKEN"
```

### Conversation Memory

```bash
# First message
curl -X POST http://localhost:8000/query \
  -d '{"question": "Explain photosynthesis", "thread_id": "session1"}'

# Follow-up (remembers context)
curl -X POST http://localhost:8000/query \
  -d '{"question": "Create a study guide", "thread_id": "session1"}'

# Get history
curl http://localhost:8000/history/session1
```

## Client Examples

### Python

```python
import requests

url = "http://localhost:8000"

# Study query (no auth)
response = requests.post(f"{url}/query", json={
    "question": "Generate MCQs about physics",
    "thread_id": "session1"
})
print(response.json()["answer"])

# Get token
token_response = requests.post(f"{url}/token", 
    data={"username": "professor", "password": "secret"})
token = token_response.json()["access_token"]

# Grading query (with auth)
headers = {"Authorization": f"Bearer {token}"}
response = requests.post(f"{url}/grade", 
    headers=headers,
    json={
        "submission": "Essay text...",
        "rubric_id": "essay_general",
        "user_id": "prof123"
    })
print(response.json())

# View history
history = requests.get(f"{url}/grading-history", headers=headers)
print(history.json())
```

### JavaScript

```javascript
const url = 'http://localhost:8000';

// Study query
const studyResponse = await fetch(`${url}/query`, {
  method: 'POST',
  headers: { 'Content-Type': 'application/json' },
  body: JSON.stringify({
    question: 'Generate 10 MCQs',
    thread_id: 'user456'
  })
});
console.log(await studyResponse.json());

// Get token
const tokenResponse = await fetch(`${url}/token`, {
  method: 'POST',
  body: new URLSearchParams({
    username: 'professor',
    password: 'secret'
  })
});
const { access_token } = await tokenResponse.json();

// Grading query
const gradeResponse = await fetch(`${url}/grade`, {
  method: 'POST',
  headers: {
    'Authorization': `Bearer ${access_token}`,
    'Content-Type': 'application/json'
  },
  body: JSON.stringify({
    submission: 'Essay text...',
    rubric_id: 'essay_general'
  })
});
console.log(await gradeResponse.json());
```

## Architecture

### Multi-Agent Routing

```
Request → Supervisor → [Study Agent | Grading Agent]
             ↓
       [Classify → Check Role → Route]
```

**Study Agent:** All users (research, Q&A, animations)  
**Grading Agent:** Teachers only (essay, code, MCQ grading)

### Access Control

| Role      | Study | Grading | Enforcement |
|-----------|-------|---------|-------------|
| Student   | ✅    | ❌      | Supervisor  |
| Teacher   | ✅    | ✅      | JWT + Supervisor |
| Admin     | ✅    | ✅      | JWT + Supervisor |

### Tools Available

**Study Agent:**
- document_qa (RAG + MCQs/summaries)
- web_search (Tavily → DuckDuckGo)
- python_repl (code execution)
- manim_animation (educational videos)

**Grading Agent:**
- grade_essay (rubric-based)
- review_code (correctness/style)
- grade_mcq (auto-scoring)
- evaluate_with_rubric (custom)
- generate_feedback (constructive)

## Features

**Multi-Agent Routing:** Automatic routing to Study or Grading agent  
**Role-Based Access:** JWT + supervisor enforcement  
**Conversation Memory:** Thread-based context across requests  
**Database Persistence:** Grading sessions saved to PostgreSQL  
**Rubric RAG:** Semantic rubric retrieval with ChromaDB  
**Fallback Logic:** document_qa → web_search if not found

## Configuration

```bash
# Environment (.env)
GOOGLE_API_KEY=xxx                    # Required (Gemini)
DATABASE_URL=postgresql://...         # Optional (persistence)
SECRET_KEY=xxx                        # Required (JWT)
TAVILY_API_KEY=xxx                    # Optional (web search)

# Custom host/port
HOST=0.0.0.0 PORT=8080 python api/main.py

# Custom documents
DOCUMENTS_DIR=/path/to/docs python api/main.py
```

## Deployment

### Production

```bash
# With Gunicorn
gunicorn -w 4 -k uvicorn.workers.UvicornWorker api.main:app

# With uvicorn
uvicorn api.main:app --host 0.0.0.0 --port 8000 --workers 4
```

### Docker

```dockerfile
FROM python:3.13-slim
WORKDIR /app
COPY requirements.txt .
RUN pip install -r requirements.txt
COPY . .
EXPOSE 8000
CMD ["uvicorn", "api.main:app", "--host", "0.0.0.0", "--port", "8000"]
```

### Docker Compose

```yaml
version: '3.8'
services:
  api:
    build: .
    ports:
      - "8000:8000"
    environment:
      - GOOGLE_API_KEY=${GOOGLE_API_KEY}
      - DATABASE_URL=postgresql://postgres:postgres@db:5432/grading_system
    depends_on:
      - db
  
  db:
    image: postgres:15
    environment:
      - POSTGRES_DB=grading_system
      - POSTGRES_PASSWORD=postgres
    volumes:
      - postgres_data:/var/lib/postgresql/data

volumes:
  postgres_data:
```

## Security

**Authentication:** JWT tokens for grading endpoints  
**Authorization:** Role-based access control (Supervisor)  
**Database:** User isolation via foreign keys  
**API Keys:** Stored in `.env` (not committed)  
**CORS:** Configure for production  
**Rate Limiting:** Add middleware for production

## Performance

**Study query:** 2-10s (depends on tool)  
**Grading query:** 10-20s (LLM analysis)  
**Intent classification:** <1s (routing)  
**Database save:** <0.5s  
**Connection pool:** 10 connections, 20 overflow

---

**Powered by LangGraph multi-agent routing with role-based access control.**

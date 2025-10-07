# REST API Reference

FastAPI server for the Study & Search Agent powered by LangChain & LangGraph with conversation memory and autonomous routing.

## Quick Start

```bash
python api/main.py       # Direct execution
# OR
python -m api.main       # Module execution (alternative)
```

**Server:** http://localhost:8000  
**Interactive docs:** http://localhost:8000/docs (Swagger UI)

## Endpoints

| Method | Endpoint | Description |
|--------|----------|-------------|
| GET | `/` | API info |
| GET | `/health` | Status check with features |
| POST | `/query` | Query agent (with thread_id) |
| GET | `/history/{thread_id}` | Get conversation history |
| POST | `/documents/upload` | Upload PDF/DOCX |
| GET | `/documents` | List documents |
| DELETE | `/documents/{filename}` | Delete document |
| POST | `/reload` | Re-index documents |

## Usage

### Query with Conversation Memory

```bash
# First message in thread
curl -X POST http://localhost:8000/query \
  -H "Content-Type: application/json" \
  -d '{
    "question": "Generate 10 MCQs about neural networks",
    "thread_id": "user123"
  }'

# Follow-up in same thread (remembers context)
curl -X POST http://localhost:8000/query \
  -H "Content-Type: application/json" \
  -d '{
    "question": "Create a study guide too",
    "thread_id": "user123"
  }'
```

**Response:**
```json
{
  "question": "Generate 10 MCQs about neural networks",
  "answer": "Question 1: ...",
  "thread_id": "user123",
  "success": true
}
```

### Get Conversation History

```bash
curl http://localhost:8000/history/user123
```

**Response:**
```json
{
  "thread_id": "user123",
  "message_count": 4,
  "messages": [
    {"role": "user", "content": "Generate 10 MCQs..."},
    {"role": "assistant", "content": "Question 1: ..."},
    {"role": "user", "content": "Create a study guide too"},
    {"role": "assistant", "content": "## Study Guide..."}
  ]
}
```

### Document Management

```bash
# Upload document
curl -X POST http://localhost:8000/documents/upload \
  -F "file=@notes.pdf"

# Re-index (required after upload)
curl -X POST http://localhost:8000/reload

# List documents
curl http://localhost:8000/documents

# Delete document
curl -X DELETE http://localhost:8000/documents/notes.pdf
```

### Health Check

```bash
curl http://localhost:8000/health
```

**Response:**
```json
{
  "status": "healthy",
  "llm_provider": "GEMINI",
  "documents_loaded": 2,
  "tools_available": ["Python_REPL", "Web_Search", "Document_QA", "render_manim_video"],
  "features": [
    "LangGraph: state management + routing + memory",
    "LangChain: RAG pipelines + tools + embeddings",
    "Thread-based conversation history",
    "Autonomous tool routing with fallback",
    "Context-aware follow-ups"
  ]
}
```

## Client Examples

### Python

```python
import requests

url = "http://localhost:8000"

# Query with conversation memory
response = requests.post(f"{url}/query", json={
    "question": "Generate 5 MCQs about physics",
    "thread_id": "session1"
})
print(response.json()["answer"])

# Follow-up question
response = requests.post(f"{url}/query", json={
    "question": "Now create a summary",
    "thread_id": "session1"  # Same thread = remembers context
})
print(response.json()["answer"])

# Get conversation history
history = requests.get(f"{url}/history/session1").json()
print(f"Messages: {history['message_count']}")

# Upload document
with open("notes.pdf", "rb") as f:
    requests.post(f"{url}/documents/upload", files={"file": f})
requests.post(f"{url}/reload")
```

### JavaScript

```javascript
const url = 'http://localhost:8000';

// Query with thread
const response = await fetch(`${url}/query`, {
  method: 'POST',
  headers: { 'Content-Type': 'application/json' },
  body: JSON.stringify({
    question: 'Generate 10 MCQs about quantum physics',
    thread_id: 'user456'
  })
});

const data = await response.json();
console.log(data.answer);

// Get history
const history = await fetch(`${url}/history/user456`).then(r => r.json());
console.log(`${history.message_count} messages`);
```

## Features

**Autonomous Routing:** Agent automatically selects from 4 tools:
- Document_QA (RAG + MCQs/summaries/study guides/flashcards)
- Web_Search (Hybrid: Tavily → Google → DuckDuckGo)
- Python_REPL (code execution)
- Manim_Animation (educational videos)

**Conversation Memory:** Use `thread_id` to maintain context across requests

**Fallback Logic:** Document_QA → Web_Search if content not found

**Context-Aware:** Vague follow-ups enriched with conversation history

## Configuration

```bash
# Custom host/port
HOST=0.0.0.0 PORT=8080 python api/main.py

# Custom documents directory
DOCUMENTS_DIR=/path/to/docs python api/main.py
```

See [README.md](../README.md) for API keys and LLM configuration.

## Deployment

**Production server:**
```bash
gunicorn -w 4 -k uvicorn.workers.UvicornWorker api.main:app
```

**Docker:**
```dockerfile
FROM python:3.13-slim
WORKDIR /app
COPY requirements.txt .
RUN pip install -r requirements.txt
COPY . .
CMD ["python", "api/main.py"]
```

⚠️ **For production:** Add authentication, rate limiting, and CORS configuration.

---

**Powered by LangChain & LangGraph with autonomous routing and conversation memory.**

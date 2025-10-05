# REST API Reference

FastAPI server for the Study & Search Agent.

## Quick Start

```bash
python api.py  # Starts at http://localhost:8000
```

**Interactive docs:** http://localhost:8000/docs

## Base URL

```
http://localhost:8000
```

## Endpoints

| Method | Endpoint | Description |
|--------|----------|-------------|
| POST | `/query` | Query the agent |
| POST | `/documents/upload` | Upload PDF/DOCX |
| GET | `/documents` | List uploaded files |
| DELETE | `/documents/{filename}` | Delete a file |
| POST | `/reload` | Re-index documents |
| GET | `/health` | Status check |

### POST /query

```bash
curl -X POST http://localhost:8000/query \
  -H "Content-Type: application/json" \
  -d '{"question": "Generate 10 MCQs about physics"}'
```

**Response:**
```json
{
  "question": "Generate 10 MCQs about physics",
  "answer": "Question 1: ...",
  "success": true
}
```

### POST /documents/upload

```bash
curl -X POST http://localhost:8000/documents/upload \
  -F "file=@notes.pdf"
```

### POST /reload

Required after uploading documents to index them.

```bash
curl -X POST http://localhost:8000/reload
```

## Client Examples

### Python

```python
import requests

url = "http://localhost:8000"

# Query
r = requests.post(f"{url}/query", json={"question": "Generate 5 MCQs about physics"})
print(r.json()["answer"])

# Upload & reload
with open("notes.pdf", "rb") as f:
    requests.post(f"{url}/documents/upload", files={"file": f})
requests.post(f"{url}/reload")
```

### JavaScript

```javascript
const url = 'http://localhost:8000';

const response = await fetch(`${url}/query`, {
  method: 'POST',
  headers: { 'Content-Type': 'application/json' },
  body: JSON.stringify({ question: 'Generate 10 MCQs about quantum physics' })
});

const data = await response.json();
console.log(data.answer);
```

## Testing

```bash
python api_examples.py  # Python examples
./test_api.sh           # cURL tests
```

## Configuration

**API-specific environment variables:**

```bash
HOST=127.0.0.1 PORT=8080 python api.py      # Custom host/port
DOCUMENTS_DIR=/path/to/docs python api.py   # Custom docs directory
```

See main [README.md](README.md) for API keys and LLM provider setup.

## Deployment

**Docker:**
```dockerfile
FROM python:3.13-slim
WORKDIR /app
COPY requirements.txt .
RUN pip install -r requirements.txt
COPY . .
CMD ["python", "api.py"]
```

**Production:**
```bash
gunicorn -w 4 -k uvicorn.workers.UvicornWorker api:app
```

**Note:** Add authentication, rate limiting, and CORS for public deployments.


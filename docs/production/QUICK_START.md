# Quick Start Guide

## Prerequisites

- Docker and Docker Compose
- Python 3.12+ (for local development)
- Google Gemini API key
- 8GB+ RAM recommended

## Environment Setup

1. **Clone the repository**
   ```bash
   git clone https://github.com/Learniva/study-search-agent.git
   cd study-search-agent
   ```

2. **Set up environment variables**
   ```bash
   cp env_example.txt .env
   # Edit .env with your API keys
   ```

3. **Required environment variables**
   ```env
   GOOGLE_API_KEY=your_google_gemini_api_key
   TAVILY_API_KEY=your_tavily_api_key_optional
   DATABASE_URL=postgresql://postgres:postgres@localhost:5432/study_search_agent
   REDIS_URL=redis://localhost:6379/0
   ```

## Docker Deployment (Recommended)

### Option 1: Full Production Setup

```bash
# Start all services
docker compose up -d

# View logs
docker compose logs -f app

# Access the application
curl http://localhost:8000/health
```

### Option 2: Development Setup

```bash
# Start only database services
docker compose -f docker-compose.dev.yml up -d postgres redis

# Run application locally
python -m uvicorn api.app:app --reload
```

### Option 3: Minimal Setup

```bash
# Use the minimal container for testing
docker build -f Dockerfile.minimal -t study-search-agent:minimal .
docker run -p 8000:8000 study-search-agent:minimal
```

## Local Development

### 1. Install Dependencies

```bash
# Create virtual environment
python -m venv venv
source venv/bin/activate  # On Windows: venv\Scripts\activate

# Install dependencies
pip install -r requirements.txt
```

### 2. Database Setup

```bash
# Start PostgreSQL with pgvector
docker run -d \
  --name postgres \
  -e POSTGRES_DB=study_search_agent \
  -e POSTGRES_USER=postgres \
  -e POSTGRES_PASSWORD=postgres \
  -p 5432:5432 \
  pgvector/pgvector:pg15

# Start Redis
docker run -d \
  --name redis \
  -p 6379:6379 \
  redis:7-alpine
```

### 3. Run the Application

```bash
# Run database migrations
python -m alembic upgrade head

# Start the API server
python -m uvicorn api.app:app --reload --host 0.0.0.0 --port 8000
```

## API Usage

### Health Check
```bash
curl http://localhost:8000/health
```

### API Documentation
Open http://localhost:8000/docs in your browser

### Basic Study Query
```bash
curl -X POST "http://localhost:8000/api/query" \
  -H "Content-Type: application/json" \
  -d '{
    "query": "Explain quantum computing",
    "user_id": "test_user"
  }'
```

### Grade Assignment
```bash
curl -X POST "http://localhost:8000/api/grading/grade" \
  -H "Content-Type: application/json" \
  -d '{
    "assignment": {
      "type": "essay",
      "content": "Student essay content here...",
      "rubric": "standard_essay"
    },
    "user_id": "teacher_user"
  }'
```

## Configuration

### Core Settings
- **LLM Provider**: Gemini (default), OpenAI, Anthropic
- **Database**: PostgreSQL with pgvector extension
- **Cache**: Redis for session and result caching
- **Rate Limiting**: 60 requests/minute, 1000/hour

### Performance Tuning
```env
# Database connection pool
DB_POOL_SIZE=20
DB_MAX_OVERFLOW=30

# Cache settings
CACHE_TTL=300
CACHE_MAX_SIZE=1000

# Rate limiting
RATE_LIMIT_PER_MINUTE=60
RATE_LIMIT_PER_HOUR=1000
```

## Testing

### Run Tests
```bash
# Run all tests
python -m pytest

# Run with coverage
python -m pytest --cov=. --cov-report=html
```

### Test Specific Components
```bash
# Test API endpoints
python -m pytest tests/api/

# Test agent workflows
python -m pytest tests/agents/

# Test database operations
python -m pytest tests/database/
```

## Monitoring

### Metrics Endpoint
```bash
curl http://localhost:8000/metrics
```

### Health Monitoring
```bash
# Detailed health check
curl http://localhost:8000/health/detailed

# Database health
curl http://localhost:8000/health/database

# Cache health
curl http://localhost:8000/health/cache
```

### Logs
```bash
# View application logs
docker compose logs -f app

# View database logs
docker compose logs -f postgres

# View cache logs
docker compose logs -f redis
```

## Troubleshooting

### Common Issues

1. **Database Connection Failed**
   ```bash
   # Check if PostgreSQL is running
   docker compose ps postgres
   
   # Check connection
   docker compose exec postgres pg_isready -U postgres
   ```

2. **API Key Invalid**
   - Verify GOOGLE_API_KEY in .env file
   - Check API key permissions and quotas

3. **Port Already in Use**
   ```bash
   # Find process using port 8000
   lsof -i :8000
   
   # Use different port
   docker compose -f docker-compose.yml -f docker-compose.override.yml up -d
   ```

4. **Memory Issues**
   - Increase Docker memory limit to 4GB+
   - Reduce concurrent workers in production

### Performance Issues

1. **Slow Response Times**
   - Check database query performance
   - Monitor cache hit rates
   - Verify external API latency

2. **High Memory Usage**
   - Monitor LLM context size
   - Check for memory leaks
   - Optimize query patterns

### Getting Help

1. Check the logs first
2. Review the API documentation at `/docs`
3. Verify environment variables
4. Test with minimal configuration
5. Check resource usage (memory, CPU, disk)

## Production Deployment

For production deployment, see:
- `DEPLOYMENT_CHECKLIST.md` - Complete production setup
- `PRODUCTION_ANALYSIS.md` - Architecture and scaling guide
- `.github/workflows/deploy.yml` - CI/CD pipeline

## Development Workflow

1. Make changes to source code
2. Run tests locally
3. Test with Docker containers
4. Push changes to repository
5. CI/CD pipeline handles deployment

## Additional Resources

- **API Reference**: http://localhost:8000/docs
- **Health Dashboard**: http://localhost:8000/health
- **Metrics**: http://localhost:8000/metrics
- **Repository**: https://github.com/Learniva/study-search-agent
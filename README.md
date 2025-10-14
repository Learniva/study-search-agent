# Multi-Agent Study & Grading System

> Autonomous AI system with **Agentic RAG**, intelligent routing, and self-improving capabilities.

**Stack:** LangGraph • LangChain • Gemini 2.5 • PostgreSQL + pgvector • FastAPI

[![Clean Architecture](https://img.shields.io/badge/architecture-clean-brightgreen)]() [![MIT License](https://img.shields.io/badge/license-MIT-blue)]()

---

## Features

### 📚 Study Agent (All Users)
Multi-step planning • Document Q&A • **Web search with source citations** • Python REPL • Manim animations • **Code generation** • Context-aware follow-ups • **Real-time streaming**

### 🎓 Grading Agent (Teachers)
19 rubrics • Essay/Code/MCQ grading • Self-reflection • Adaptive learning from corrections • **Google Classroom Integration**

### 🤖 Agentic RAG
- **Adaptive Retrieval** - Decides when RAG is needed
- **Self-Correction** - Grades context quality, refines if poor
- **L2 Vector Store** - Semantic search (pgvector)
- **L3 Learning Store** - Learns from errors

### 🔒 RBAC
Role-based access control: Students → Study only | Teachers → Study + Grading

---

## Quick Start

```bash
# 1. Install
pip install -r requirements.txt

# 2. Configure
cp env_example.txt .env
# Add GOOGLE_API_KEY (required)

# 3. Run
python main.py --role student              # CLI
python -m api.app                          # API: http://localhost:8000/docs
```

**API Keys:** [Gemini](https://aistudio.google.com/app/apikey) (required) • [Google Custom Search](https://console.cloud.google.com/apis/credentials) + [Search Engine ID](https://programmablesearchengine.google.com/) (optional - primary) • [Tavily](https://tavily.com/) (optional - fallback)

---

## Usage

### CLI Examples

```bash
# Study (all users)
python main.py --role student
> "Explain quantum entanglement with examples"        # Web search + sources
> "How to implement binary search in Python?"         # Code generation
> "Create a lesson plan on photosynthesis"            # Multi-step with streaming
> "What is 2+2?"                                       # Direct calculation

# Grading (teachers)
python main.py --role professor --user-id prof123
> "Grade: $(cat test_submissions/essay_good.txt)"
```

### API Examples

```bash
# Query
curl -X POST localhost:8000/query/ \
  -H "Content-Type: application/json" \
  -H "X-User-Role: student" \
  -d '{"question": "Explain RAG", "user_role": "student"}'

# Streaming (real-time token-by-token)
curl -X POST localhost:8000/query/stream \
  -H "Content-Type: application/json" \
  -d '{"question": "Explain quantum computing", "user_role": "student"}' \
  --no-buffer

# Get grading history
curl localhost:8000/grading/history/prof123 \
  -H "X-User-Role: teacher"
```

📖 **Full API docs:** http://localhost:8000/docs

---

## Architecture

```
USER → Supervisor (RBAC) → [Study Agent | Grading Agent]
              ↓                   ↓            ↓
        LangGraph Router     Tools + RAG   RAG + DB
                                  ↓            ↓
                         L2: Vector Store  L3: Learning
```

**Workflow:** Detect → Plan → Execute → Reflect → Improve

### Codebase Structure

```
study-search-agent/
├── agents/                   # Modular agent architecture
│   ├── study/               # Study agent (state, nodes, routing, workflow)
│   ├── grading/             # Grading agent (state, nodes, routing, workflow)
│   └── supervisor/          # Supervisor agent (routing, RBAC)
├── api/                     # FastAPI application
│   ├── routers/            # Modular route handlers
│   ├── app.py              # Main application
│   ├── models.py           # Pydantic schemas
│   └── dependencies.py     # Dependency injection
├── tools/                   # study/ + grading/ tools
├── utils/                   # core, api, rag, routing, ml
├── database/               # models, operations, checkpointing
└── docs/                   # Documentation
```

---

## Database Setup (Optional)

### PostgreSQL + pgvector (Recommended)

```bash
# Install
brew install postgresql@15        # macOS
sudo apt install postgresql       # Linux

# Setup
createdb grading_system
psql grading_system -c "CREATE EXTENSION vector;"
alembic upgrade head
```

**Enables:** Semantic search • Grading history • Self-correction • Conversation memory

See [PostgreSQL Guide](docs/POSTGRESQL.md) for details.

---

## Documentation

### 📖 Complete Guide
- **[COMPLETE USER GUIDE](COMPLETE_USER_GUIDE.md)** - **All documentation in one file** ⭐
  - Quick start & installation
  - Grading & Study agent features
  - Google Classroom integration
  - Command reference
  - Helper scripts & teaching tools
  - 19 available rubrics
  - Troubleshooting & examples

### Core Agents
- **[Study Agent](docs/STUDY_AGENT.md)** - Document Q&A, web search, code execution, animations
- **[Grading Agent](docs/GRADING_AGENT.md)** - Essay/code/MCQ grading with rubrics
- **[Supervisor Agent](docs/SUPERVISOR_AGENT.md)** - Routing, access control, learning

### Architecture & Implementation
- **[Agentic Workflow](docs/AGENTIC_WORKFLOW.md)** - Autonomous decision-making and routing
- **[Streaming Architecture](docs/STREAMING_ARCHITECTURE.md)** - Real-time streaming implementation
- **[API Guide](docs/API_README.md)** - REST API reference and endpoints
- **[PostgreSQL Guide](docs/POSTGRESQL.md)** - Database setup and RAG configuration
- **[Manim Guide](docs/MANIM.md)** - Educational animation generation

### Google Classroom
- **[Complete User Guide](COMPLETE_USER_GUIDE.md)** - Full Google Classroom integration documentation
- **[Interactive Tool](grade_classroom_assignment.py)** - Step-by-step grading script

### Testing
- **[Streaming Test Guide](STREAMING_TEST_GUIDE.md)** - Comprehensive streaming test suite
- `test_submissions/` - Sample essays, code, math problems (13+ files)
- `rubrics/` - 19 discipline-specific rubrics

### Helper Scripts
- **[Grade Classroom Assignment](grade_classroom_assignment.py)** - Interactive Google Classroom grading
- **[Grade File](grade_file.py)** - Quick file grading from `test_submissions/`

---

## Key Features

### 🚀 Performance
- **80-90% LLM reduction** via pattern-based routing
- **Token-by-token streaming** with real-time indicators
- **Result caching** with configurable TTL
- **40-50% token reduction** via smart context
- **Resilient database** with retry logic & exponential backoff

### 🧠 Intelligence
- **Adaptive rubrics** learn from professor corrections
- **Self-improving RAG** grades and refines context
- **Source citations** for all web search responses
- **Code generation** with working implementations
- **User profiling** for personalized feedback
- **Multi-step planning** for complex queries

### 🏗️ Architecture
- **Domain-driven design** with clean separation
- **Modular routers** for horizontal scaling
- **Async operations** throughout
- **Production-ready** monitoring, health checks, and logging

---

## ML & Optimization

| Feature | Benefit |
|---------|---------|
| Pattern routing | 80% requests skip LLM (2-3x faster) |
| Smart context | 40-50% token reduction |
| Streaming responses | Real-time progressive delivery |
| Source citations | Verifiable, authoritative information |
| Code generation | Working implementations, not descriptions |
| Adaptive rubrics | Learn from corrections |
| RAG self-correction | Improve retrieval quality |
| DB retry logic | Automatic recovery from transient failures |

---

## Project Status

✅ **Phase 1** - L2/L3 memory, RBAC, streaming  
✅ **Phase 2** - Self-correcting RAG, context-aware follow-ups  
✅ **Phase 3** - Adaptive grading, professor style matching  
✅ **Phase 4** - Source citations, code generation, resilient database  
✅ **Clean Architecture** - Domain-driven, modular design

**Latest:** v2.0 - Real-time streaming, source citations, code generation (Oct 2025)

---

## License

MIT © 2025 Anthony Maniko

**Built with** LangGraph, LangChain, and Gemini AI 🤖

# Multi-Agent Study & Grading System 🤖

Intelligent study assistant + AI grading agent with autonomous routing, memory, and role-based access control.

**CLI + REST API** • **LangChain & LangGraph** • **Gemini LLM** • **PostgreSQL**

## Features

### 📚 Study Agent (All Users)
- 🔄 **Smart Routing** - Auto-selects best tool, fallback to web if document fails
- 💾 **Memory** - Thread-based conversation history, context-aware follow-ups
- 📚 **Document Q&A** - RAG with ChromaDB (MCQs, summaries, flashcards)
- 🔍 **Web Search** - Hybrid: Tavily → Google → DuckDuckGo
- 🐍 **Python REPL** - Code execution and math
- 🎬 **Manim** - Educational animations with voice-over

### 🎓 Grading Agent (Teachers/Professors)
- ✅ **Essay Grading** - Thesis, evidence, organization, grammar analysis
- 💻 **Code Review** - Correctness, efficiency, style, bug detection
- 📝 **MCQ Auto-Grading** - Instant scoring with explanations
- 📊 **Rubric Evaluation** - Custom rubric-based assessment
- 🤖 **RAG Rubrics** - Semantic rubric retrieval from templates
- 💾 **PostgreSQL** - Persistent grading history and analytics
- 🔐 **Role-Based Access** - Students can't access grading tools

## Quick Start

```bash
# Install dependencies
pip install -r requirements.txt

# Configure
cp env_example.txt .env
# Add GOOGLE_API_KEY (required)
# Add DATABASE_URL (optional, for grading persistence)

# Run as student (study only)
python main.py --role student

# Run as professor (study + grading)
python main.py --role professor --user-id prof123

# API server
python api/main.py  # http://localhost:8000/docs
```

**Keys:** [Gemini](https://aistudio.google.com/app/apikey) (required) • [Tavily](https://tavily.com/), [ElevenLabs](https://elevenlabs.io/) (optional)

## Usage

### Study Features (All Users)

```bash
# Documents - Auto-generates MCQs, summaries, study guides, flashcards
"Generate 10 MCQs about neural networks from my notes"
"Create a study guide for machine learning"

# Web - Context-aware follow-ups
"Who founded Code Savanna?"
"What else did he create?"  # Remembers context

# Python
"Calculate 25 * 37"

# Animations
"Animate the Pythagorean theorem"
"Animate bubble sort with voice explanation"
```

### Grading Features (Teachers/Professors Only)

```bash
# Grade essays
python main.py --role professor --user-id prof123 \
  --question "Grade: $(cat test_submissions/essay_good.txt)"

# Review code
python main.py --role professor --user-id prof123 \
  --question "Review this code: def fibonacci(n): return n if n <= 1 else fibonacci(n-1) + fibonacci(n-2)"

# Grade MCQs
python main.py --role professor \
  --question "Grade: Q1: What is 2+2? Student: 4 (Correct: 4). Q2: Capital of France? Student: London (Correct: Paris)"

# Custom rubric
python main.py --role professor \
  --question "Evaluate using rubric: Content(40%), Style(30%), Grammar(30%). Essay: [TEXT]"

# View grading history
python setup_database.py --info
```

## Access Control

| Role      | Study Agent | Grading Agent | Database |
|-----------|-------------|---------------|----------|
| Student   | ✅          | ❌            | ❌       |
| Teacher   | ✅          | ✅            | ✅       |
| Professor | ✅          | ✅            | ✅       |
| Admin     | ✅          | ✅            | ✅       |

## API

```bash
# Study query
curl -X POST localhost:8000/query \
  -d '{"question": "Generate 5 MCQs about quantum physics"}'

# Grading (requires JWT + teacher role)
curl -X POST localhost:8000/grade \
  -H "Authorization: Bearer $TOKEN" \
  -d '{"submission": "essay text", "rubric": "essay_general"}'

# View grading history
curl localhost:8000/grading-history \
  -H "Authorization: Bearer $TOKEN"
```

**Endpoints:** `/query`, `/grade`, `/grading-history`, `/rubrics`, `/documents/upload`, `/health` • **Docs:** http://localhost:8000/docs

## Programmatic

```python
from agent.supervisor_agent import SupervisorAgent

# Initialize multi-agent system
supervisor = SupervisorAgent()

# Study query (any role)
answer = supervisor.query(
    question="Explain photosynthesis",
    user_role="student"
)

# Grading query (teacher only)
result = supervisor.query(
    question="Grade this essay: [TEXT]",
    user_role="professor",
    user_id="prof123"
)
```

## Database Setup (Optional)

Required for grading history persistence:

```bash
# Install PostgreSQL
brew install postgresql@15
brew services start postgresql@15

# Create database
createdb grading_system

# Configure
echo "DATABASE_URL=postgresql://$(whoami)@localhost:5432/grading_system" >> .env

# Initialize
python setup_database.py
python setup_database.py --seed  # Add sample data
```

## Testing

```bash
# Test grading agent
./test_grading_samples.sh

# Quick test
python test_grading_quick.py

# Test role access control
./test_role_access.sh
```

**Sample files:** `test_submissions/` (essay_good.txt, code_sample.py, lab_report.txt)

## Documentation

**Architecture:**  
[STUDY_SEARCH_ARCHITECTURE.md](docs/STUDY_SEARCH_ARCHITECTURE.md) - Study Agent  
[GRADING_AGENT_ARCHITECTURE.md](docs/GRADING_AGENT_ARCHITECTURE.md) - Grading Agent

**Guides:**  
[MANIM.md](docs/MANIM.md) - Animation system  
[GRADING_TESTING_GUIDE.md](GRADING_TESTING_GUIDE.md) - Grading usage examples  
[POSTGRESQL.md](docs/POSTGRESQL.md) - Database setup  
[API_README.md](docs/API_README.md) - API documentation

**Quick Reference:**  
[QUICK_GRADING_COMMANDS.txt](QUICK_GRADING_COMMANDS.txt) - Common grading commands

## Architecture

### Study Agent
```
User → CLI/API → LangGraph Agent → Tools → Gemini → Answer
                    ↓
          [Route → Execute → Check]
               ↓       ↓       ↓
          Document  Web   Python  Manim
            QA    Search   REPL  Animation
```

### Multi-Agent System (with Grading)
```
User → Supervisor (LangGraph) → [Study Agent | Grading Agent]
            ↓
      [Classify → Access → Route]
            ↓
    Grading Agent → Tools → LLM → PostgreSQL
            ↓
    [Essay | Code | MCQ | Rubric RAG]
```

**Study Agent:** LangGraph (routing + memory) + LangChain (RAG + tools)  
**Grading Agent:** LangGraph (tool routing) + RAG (rubrics) + PostgreSQL  
**Supervisor:** LangGraph (multi-agent routing) + RBAC  
**LLM:** Gemini 2.5 Flash  
**CLI:** `graph` • `history` • `arch` • `caps` • `quit`

## Tech Stack

**Frameworks:** [LangGraph](https://langchain-ai.github.io/langgraph/) • [LangChain](https://langchain.com/)  
**LLM:** [Gemini](https://ai.google.dev/)  
**Vectors:** [ChromaDB](https://trychroma.com/)  
**Database:** [PostgreSQL](https://www.postgresql.org/) + [SQLAlchemy](https://www.sqlalchemy.org/)  
**Animation:** [Manim](https://www.manim.community/)  
**API:** [FastAPI](https://fastapi.tiangolo.com/)

## License

MIT - See [LICENSE](LICENSE)

---

**Happy studying & grading! 🎓✅**

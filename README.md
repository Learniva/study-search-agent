# Multi-Agent Study & Grading System 🤖

Autonomous multi-agent system with intelligent routing, self-reflection, and role-based access control.

**CLI + REST API** • **LangGraph + LangChain** • **Gemini** • **PostgreSQL** • **ML Adaptation**

## Features

**📚 Study Agent** (All Users)  
Multi-step planning • Document Q&A • Web search • Python REPL • Manim animations • ML learning

**🎓 Grading Agent** (Teachers Only)  
15+ discipline rubrics • Essay/code/MCQ grading • Self-reflection • Adaptive learning • PostgreSQL persistence

**🔒 Access Control:** Students → Study only | Teachers → Study + Grading

## Quick Start

```bash
# Install
pip install -r requirements.txt

# Configure .env (copy from env_example.txt)
GOOGLE_API_KEY=your_key_here  # Required

# Run CLI
python main.py --role student                    # Study features
python main.py --role professor --user-id prof123  # Study + Grading

# Run API
python api/main.py  # http://localhost:8000/docs
```

**Get API Keys:** [Gemini](https://aistudio.google.com/app/apikey) (required) • [Tavily](https://tavily.com/), [ElevenLabs](https://elevenlabs.io/) (optional)

## Usage

**Study (All Users):**
```bash
python main.py --role student

"Generate 10 MCQs about neural networks from my notes"
"Who founded Code Savanna?"  # Web search with memory
"What else did he create?"   # Context-aware follow-up
"Animate the Pythagorean theorem"
```

**Grading (Teachers):**
```bash
python main.py --role professor --user-id prof123

# Grade essays, code, math problems
--question "Grade: $(cat test_submissions/essay_good.txt)"
--question "Review: $(cat test_submissions/intro_programming_assignment.py)"
--question "Grade: $(cat test_submissions/math_calculus_assignment.txt)"
```

## API

```bash
# Query endpoint (study or grading based on role)
curl -X POST localhost:8000/query \
  -H "Content-Type: application/json" \
  -d '{"question": "...", "user_role": "student"}'

# Streaming responses (SSE)
curl -N localhost:8000/query/stream -H "Content-Type: application/json" -d '{...}'

# ML endpoints: /ml/feedback, /ml/profile/{user_id}, /ml/performance
# Grading: /grading/history/{prof_id}, /rubrics/{prof_id}
```

**Full API docs:** http://localhost:8000/docs

## Architecture

```
USER → Supervisor Agent (RBAC) → [Study Agent | Grading Agent]
                ↓                      ↓              ↓
          LangGraph Router       Tools + RAG    RAG + PostgreSQL
```

**Agentic Workflow:** Detect complexity → Plan/Route → Execute → Self-reflect → Retry/Clarify/Finish

**Key Tech:** LangGraph • LangChain • Gemini 2.5 Flash • ChromaDB • PostgreSQL • FastAPI

## Rubrics & Testing

**15+ Rubrics:** CS (intro/algorithms/discrete/theory/projects) • Math (intro/calculus/proofs) • Social Sciences • Humanities • History

**Test Submissions:** `test_submissions/` contains sample essays, code, math problems, research papers

```bash
python main.py --role professor --question "Grade: $(cat test_submissions/essay_good.txt)"
```

## Database (Optional)

PostgreSQL enables grading history, analytics, and ML persistence:

```bash
brew install postgresql@15 && brew services start postgresql@15
createdb grading_system
echo "DATABASE_URL=postgresql://$(whoami)@localhost:5432/grading_system" >> .env
```

## Documentation

**Architecture:** [SYSTEM_ARCHITECTURE.md](docs/SYSTEM_ARCHITECTURE.md) • [AGENTIC_CAPABILITIES_SUMMARY.md](docs/AGENTIC_CAPABILITIES_SUMMARY.md) • [ML_ADAPTATION_ARCHITECTURE.md](docs/ML_ADAPTATION_ARCHITECTURE.md)

**Guides:** [MANIM.md](docs/MANIM.md) • [POSTGRESQL.md](docs/POSTGRESQL.md) • [API_README.md](docs/API_README.md)

**Rubrics:** [rubrics/README.md](rubrics/README.md) • **Tests:** [test_submissions/README.md](test_submissions/README.md)

## ML & Optimization

⚡ Pattern-based routing (80-90% LLM reduction) • 💾 Result caching • 🧠 Smart context (40-50% token reduction)  
📊 User profiling • 🎯 Performance learning • 🤖 Adaptive rubrics • 🧩 Multi-step planning • 🔍 Self-reflection

## License

MIT © 2025 Anthony Maniko

---

**Autonomous multi-agent system built with LangGraph, LangChain, and Gemini AI** 🤖🎓

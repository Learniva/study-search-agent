# Study & Search Agent 🤖

Intelligent study assistant that generates MCQs, summaries, study guides, and flashcards from **your documents** or **web sources**.

**CLI + REST API** • **LangGraph + LangChain + Gemini**

## Features

**Automatic tool selection:**
- 📚 **Your Documents** - Generate study materials from uploaded PDF/DOCX
- 🔍 **Web Search** - Generate from authoritative web sources (no upload needed)
- 🐍 **Python** - Math calculations and code execution

## Quick Start

```bash
# Setup
pip install -r requirements.txt
cp env_example.txt .env
# Add GOOGLE_API_KEY to .env (required for LLM)
# Add TAVILY_API_KEY (optional - for web search)

# Run CLI
python main.py

# Or API server
python api.py  # http://localhost:8000/docs
```

**Get keys:** [Gemini](https://aistudio.google.com/app/apikey) (required) • [Tavily](https://tavily.com/) (optional - uses DuckDuckGo fallback)

## Usage

**Example queries:**
```
"Generate 10 MCQs about neural networks"              → Web Search
"Summarize my notes about machine learning"            → Your Documents
"Create 5 questions and a study guide for physics"    → Multi-part
"Calculate 25 * 37"                                    → Python
```

**What you can generate:**
- Multiple choice questions with answers
- Summaries and study guides  
- Flashcards for memorization
- Multi-part combinations

**Tool selection:**
- Mention "my notes/documents" → uses your uploaded files
- General topic without reference → searches web
- Math/code → Python REPL

**Upload documents:**
```bash
cp notes.pdf documents/
# Or via API: curl -X POST http://localhost:8000/documents/upload -F "file=@notes.pdf"
```

## API

```bash
curl -X POST http://localhost:8000/query \
  -d '{"question": "Generate 5 MCQs about quantum physics"}'
```

Docs: http://localhost:8000/docs

## Programmatic

```python
from agent import StudySearchAgent

agent = StudySearchAgent()
answer = agent.query("Generate 10 MCQs about physics")
```

## Documentation

- **[API_README.md](API_README.md)** - API documentation
- **[ARCHITECTURE_INDEX.md](ARCHITECTURE_INDEX.md)** - 📚 Start here for architecture docs
- **[ARCHITECTURE.md](ARCHITECTURE.md)** - Comprehensive architecture guide
- **[ARCHITECTURE_QUICK_REF.md](ARCHITECTURE_QUICK_REF.md)** - Quick reference

## Architecture

```
User → CLI/API → LangGraph Agent → Tools (Document Q&A | Web Search | Python REPL) → LLM → Answer
```

**Built with LangGraph** for intelligent routing, automatic fallback logic, and conversation memory.

**Key Features:**
- 🔄 Automatic fallback: Document Q&A → Web Search
- 💾 Conversation memory with thread-based history
- 🔍 Hybrid web search: Tavily → Google → DuckDuckGo
- 🧠 Context-aware follow-up questions
- ⚡ 70% reduced token usage vs traditional ReAct

**Special Commands (CLI):**
- `graph` - View LangGraph architecture
- `history` - Show conversation history

See [LANGGRAPH_MIGRATION.md](LANGGRAPH_MIGRATION.md) for migration details and [ARCHITECTURE.md](ARCHITECTURE.md) for comprehensive documentation

## Stack

[LangGraph](https://langchain-ai.github.io/langgraph/) • [LangChain](https://langchain.com/) • [Gemini](https://ai.google.dev/) • [Tavily](https://tavily.com/) • [ChromaDB](https://trychroma.com/) • [FastAPI](https://fastapi.tiangolo.com/)

## License

MIT - See [LICENSE](LICENSE)

---

**Happy studying! 🎓**

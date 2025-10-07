# Study & Search Agent 🤖

Intelligent study assistant with autonomous routing, memory, and fallback logic. Generate MCQs, summaries, flashcards, and animations from documents or web.

**CLI + REST API** • **LangChain & LangGraph** • **Gemini LLM**

## Features

- 🔄 **Smart Routing** - Auto-selects best tool, fallback to web if document fails
- 💾 **Memory** - Thread-based conversation history, context-aware follow-ups
- 📚 **Document Q&A** - RAG with ChromaDB (MCQs, summaries, flashcards)
- 🔍 **Web Search** - Hybrid: Tavily → Google → DuckDuckGo
- 🐍 **Python REPL** - Code execution and math
- 🎬 **Manim** - Educational animations with voice-over

## Quick Start

```bash
pip install -r requirements.txt
cp env_example.txt .env  # Add GOOGLE_API_KEY (required)

python main.py           # CLI
python api/main.py       # API: http://localhost:8000/docs
```

**Keys:** [Gemini](https://aistudio.google.com/app/apikey) (required) • [Tavily](https://tavily.com/), [ElevenLabs](https://elevenlabs.io/) (optional)

## Usage

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

# Upload docs
cp notes.pdf documents/  # CLI
curl -X POST localhost:8000/documents/upload -F "file=@notes.pdf"  # API
```

## API

```bash
curl -X POST localhost:8000/query -d '{"question": "Generate 5 MCQs about quantum physics"}'
```

**Endpoints:** `/query`, `/documents/upload`, `/documents`, `/reload`, `/health` • **Docs:** http://localhost:8000/docs

## Programmatic

```python
from agent import StudySearchAgent

agent = StudySearchAgent()
answer = agent.query("Generate 10 MCQs", thread_id="session1")  # With memory
history = agent.get_conversation_history(thread_id="session1")
```

## Docs

[MANIM_GUIDE.md](docs/MANIM_GUIDE.md) • [ARCHITECTURE.md](docs/ARCHITECTURE.md) • [API_README.md](docs/API_README.md)

## Architecture

```
User → CLI/API → LangGraph Agent → Tools → Gemini → Answer
                    ↓
          [Route → Execute → Check]
               ↓       ↓       ↓
          Document  Web   Python  Manim
            QA    Search   REPL  Animation
```

**Agent:** LangGraph (routing + memory) + LangChain (RAG + tools)  
**LLM:** Gemini 2.5 Flash  
**CLI:** `graph` (visualize) • `history` (show memory) • `quit` (exit)

## Stack

[LangGraph](https://langchain-ai.github.io/langgraph/) • [LangChain](https://langchain.com/) • [Gemini](https://ai.google.dev/) • [ChromaDB](https://trychroma.com/) • [Manim](https://www.manim.community/) • [FastAPI](https://fastapi.tiangolo.com/)

## License

MIT - See [LICENSE](LICENSE)

---

**Happy studying! 🎓**

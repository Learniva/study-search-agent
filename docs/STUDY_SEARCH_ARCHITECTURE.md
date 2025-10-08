# Study & Search Agent - Architecture

Intelligent study assistant powered by LangChain & LangGraph with autonomous routing, memory, and fallback logic.

## System Architecture

```
User → CLI/API → LangGraph Agent → Tools → Gemini → Answer
                      ↓
            [Route → Execute → Check]
                 ↓       ↓       ↓
            Document  Web   Python  Manim
              QA    Search   REPL  Animation
```

## Components

### 1. Entry Points

**`main.py` (CLI):** Interactive chat, single query mode, conversation history  
**`api/main.py` (FastAPI):** REST endpoints (`/query`, `/documents/upload`, `/documents`, `/reload`, `/health`)

### 2. Agent (LangChain & LangGraph)

**LangGraph:** State management, routing logic, memory/checkpointing  
**LangChain:** RAG pipelines (LCEL), tools framework, embeddings, vector stores  
**State:** AgentState (messages, question, tool_used, tool_result, iteration, memory)  
**Nodes:** route_question, document_qa, web_search, python_repl, manim_animation, check_result, format_answer  
**Flow:** Smart routing → Tool execution → Fallback check (Doc→Web) → Memory storage  
**Memory:** Thread-based conversation history with MemorySaver checkpoint

### 3. Agent Flow

```
Question → Route (LLM decides tool) → Execute tool → Check result
                                           ↓
                                    If Doc fails → Web
                                           ↓
                                    Format + Save to memory → Answer
```

### 4. Tools

**Document_QA** (document_qa.py): RAG with ChromaDB, generates MCQs/summaries/study guides/flashcards  
**Web_Search** (web_search.py): Hybrid Tavily → Google → DuckDuckGo with context-aware query enrichment  
**Python_REPL** (python_repl.py): Code execution via PythonREPL  
**Manim_Animation** (manim_animation.py): 4-stage pipeline (RAG → Planning → Code Gen → Execution)

### 5. Document Q&A (RAG Pipeline)

```
Load: PDF/DOCX → PyPDFLoader/Docx2txtLoader
Split: RecursiveCharacterTextSplitter (chunk_size=1000, overlap=200)
Embed: GoogleGenerativeAIEmbeddings (text-embedding-004)
Store: ChromaDB (.chroma_db/)
Retrieve: Similarity search (k=3 chunks)
Generate: LCEL chain → retriever | format | prompt | LLM | parse → answer
```

**Features:**
- MCQ generation with answers/explanations
- Summaries with page citations
- Study guides (concepts/terms/examples)
- Flashcards (front/back format)
- Complex multi-part request parsing

### 6. Web Search (Hybrid)

```
Query enrichment (context-aware follow-ups) →
  Tavily (primary) → Google Custom Search → DuckDuckGo (fallback) →
  LLM synthesis → Answer with sources
```

**Context-aware:** Enriches vague questions ("Who else?") with conversation context

### 7. Manim Animation (Multi-Stage)

```
Stage 1: RAG Context - Retrieve source material from documents
Stage 2: Planning Agent - Create structured JSON plan
Stage 3: Code Generation - Convert plan to Manim Python code
Stage 4: Execution - Render video with optional voice-over (gTTS/ElevenLabs)
```

## Tech Stack

**Agent Framework:**  
- LangGraph: State management, routing, memory/checkpointing  
- LangChain: RAG (LCEL chains), tools, embeddings, vector stores  

**LLM:** Gemini 2.5 Flash (temperature=0)  
**Embeddings:** Gemini text-embedding-004  
**Vector DB:** ChromaDB (persistent)  
**API:** FastAPI  
**Search:** Tavily, Google Custom Search API, DuckDuckGo  
**Animation:** Manim, manim-voiceover, gTTS, ElevenLabs  
**Docs:** PyPDF, python-docx, docx2txt

## Configuration

```bash
# .env file
GOOGLE_API_KEY=xxx              # Required (Gemini LLM + embeddings)
TAVILY_API_KEY=xxx              # Optional (web search, has fallbacks)
ELEVEN_API_KEY=xxx              # Optional (high-quality voice-overs)
GOOGLE_SEARCH_API_KEY=xxx       # Optional (Google Custom Search)
GOOGLE_SEARCH_ENGINE_ID=xxx     # Optional (Google Custom Search)
```

**Runtime config:**
- Chunk size: 1000, overlap: 200
- Retrieval k: 3 (docs), 6 (MCQ), 9 (summary/study guide)
- LLM temperature: 0
- Max iterations: Controlled by LangGraph state

## File Structure

```
study-search-agent/
├── main.py                 # CLI
├── api/
│   ├── __init__.py         # Package init
│   └── main.py             # REST API
├── agent/
│   └── study_agent.py      # LangGraph agent
├── tools/
│   ├── base.py             # Tool aggregator
│   ├── document_qa.py      # RAG implementation
│   ├── web_search.py       # Hybrid search
│   ├── python_repl.py      # Code execution
│   └── manim_animation.py  # Animation pipeline
├── utils/
│   ├── llm.py              # Gemini initialization
│   └── prompts.py          # Prompt templates
├── documents/              # PDF/DOCX storage
└── .chroma_db/             # Vector database (auto-generated)
```

## Key Patterns

**LangGraph:** Stateful agent with nodes, conditional edges, checkpointing  
**LangChain:** LCEL chains for RAG, tools framework, embeddings  
**RAG:** Retrieval → Augment → Generate with LCEL chains  
**Fallback:** Document_QA fails → automatic retry with Web_Search  
**Memory:** Thread-based conversation history preserved across queries

## Extension Points

**Add tool:** Create in `tools/`, add to `tools/base.py get_all_tools()`  
**Add doc type:** Add loader in `DocumentQAManager.load_documents()`  
**Add endpoint:** Add route in `api/main.py` with Pydantic models  
**Customize RAG:** Adjust chunk size, k value, or prompt templates

## Security Notes

⚠️ **Python REPL:** Executes arbitrary code - not for untrusted users  
⚠️ **API:** No authentication/rate limiting - add for production  
⚠️ **File uploads:** No malware scanning - validate/scan in production  
✓ **API keys:** Stored in `.env` (not committed)

## Performance

**Document loading:** 5-20s per doc (one-time at startup)  
**Query processing:** 2-10s typical (LLM + retrieval)  
**Vector search:** <0.1s (very fast)  
**Animation:** 30s-5min (depends on complexity)

---

**Built with LangChain & LangGraph for intelligent routing, RAG pipelines, and conversation memory.**

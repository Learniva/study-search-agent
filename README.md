# Study and Search Agent 🤖

An intelligent agent that dynamically chooses the right tool to answer your questions.

**Available as CLI or REST API** • **Powered by LangChain & Gemini**

---

## ✨ Features

The agent automatically decides which tool to use:

- 📚 **Document Q&A** - Answers from your uploaded PDF/DOCX files (RAG with vector search)
- 🐍 **Python REPL** - Mathematical calculations and code execution  
- 🔍 **Web Search** - Real-time facts and current events (via Tavily)
- 💡 **Direct Answer** - General knowledge questions

## 🚀 Quick Start

### 1. Install

```bash
# Clone and setup
cd study-search-agent
python3 -m venv study_agent
source study_agent/bin/activate

# Install dependencies
pip install -r requirements.txt
```

### 2. Configure API Keys

```bash
cp env_example.txt .env
```

Edit `.env` and add your keys:

```env
LLM_PROVIDER=gemini
GOOGLE_API_KEY=your_key_here
TAVILY_API_KEY=your_key_here
```

**Get API keys:**
- [Google Gemini](https://aistudio.google.com/app/apikey) (Free tier available)
- [Tavily Search](https://tavily.com/) (Free tier available)
- [HuggingFace](https://huggingface.co/settings/tokens) (Optional)
- [OpenAI](https://platform.openai.com/api-keys) (Optional)

### 3. Run

**CLI Mode:**
```bash
python main.py
```

**API Mode:**
```bash
python api.py
# Visit http://localhost:8000/docs
```

---

## 💻 Usage

### Interactive Chat

```bash
$ python main.py

🤔 Your question: What is 25 * 37?
✅ Answer: 925  # Uses Python_REPL

🤔 Your question: Who won the 2024 Nobel Prize?
✅ Answer: ...  # Uses Web_Search

🤔 Your question: What is supervised learning?
✅ Answer: ...  # Uses Document_QA (if docs uploaded)
```

### REST API

Start the server:
```bash
python api.py
```

Query the agent:
```bash
curl -X POST http://localhost:8000/query \
  -H "Content-Type: application/json" \
  -d '{"question": "What is the capital of France?"}'
```

Upload documents:
```bash
curl -X POST http://localhost:8000/documents/upload \
  -F "file=@notes.pdf"

# Reload to index
curl -X POST http://localhost:8000/reload
```

**API Docs:** http://localhost:8000/docs

---

## 📚 Document Q&A (RAG)

Answer questions from your study materials using Retrieval Augmented Generation.

### Upload Documents

```bash
# Add files to documents/ folder
cp lecture_notes.pdf documents/
cp textbook.docx documents/

# Or use API
curl -X POST http://localhost:8000/documents/upload -F "file=@notes.pdf"
```

### How It Works

1. **Load** - Reads PDF/DOCX files  
2. **Split** - Chunks into 1000 char segments (200 overlap)  
3. **Embed** - Converts to vectors (Gemini `text-embedding-004`)  
4. **Store** - Saves to ChromaDB vector database  
5. **Retrieve** - Searches for top 3 relevant chunks  
6. **Generate** - Gemini 2.5 Flash creates answer with citations

**LCEL Chain:**
```
question → retriever | format | prompt | llm | parse → answer
```

### Example Questions

```
"What are the types of machine learning in my notes?"
"Explain neural networks from chapter 3"
"Compare supervised vs unsupervised learning"
```

---

## 🏗️ Architecture

```
User Question
    ↓
LLM Agent (Gemini 2.5 Flash)
    ↓
Decision: Which tool?
    ↓
┌───────────┬─────────────┬────────────┐
Document_QA  Python_REPL  Web_Search
(RAG+Vector)   (Math)      (Tavily)
```

**ReAct Framework:** Reasoning → Action → Observation → Answer

---

## 📁 Project Structure

```
study-search-agent/
├── agent/
│   └── study_agent.py      # Main agent logic
├── tools/
│   ├── base.py             # Tool registry
│   ├── document_qa.py      # RAG implementation
│   ├── python_repl.py      # Code execution
│   └── web_search.py       # Tavily search
├── utils/
│   ├── llm.py              # LLM initialization
│   └── prompts.py          # Agent prompts
├── main.py                 # CLI entry point
├── api.py                  # FastAPI server
├── requirements.txt        # Dependencies
└── .env                    # API keys (create this)
```

---

## 🛠️ Customization

### Use Different LLM Provider

```env
LLM_PROVIDER=gemini  # or huggingface, openai, anthropic
```

### Programmatic Usage

```python
from agent import StudySearchAgent

agent = StudySearchAgent(llm_provider="gemini")
answer = agent.query("What is 2 + 2?")
print(answer)
```

### Add New Tools

1. Create `tools/your_tool.py`
2. Add to `tools/base.py`
3. Update prompt in `utils/prompts.py`

---

## 📝 Example Questions

| Type | Question | Tool Used |
|------|----------|-----------|
| **Document** | "What is backpropagation in my notes?" | Document_QA |
| **Math** | "Calculate 15% of 850" | Python_REPL |
| **Current** | "Latest AI news" | Web_Search |
| **General** | "Capital of France?" | Direct Answer |

---

## 🔒 Security

- Never commit `.env` with real API keys
- Python REPL executes code - use with caution
- Consider API rate limits and costs

---

## 📄 License

MIT License - See LICENSE file

## 🙏 Built With

- [LangChain](https://langchain.com/) - Agent framework
- [Google Gemini](https://ai.google.dev/) - LLM & embeddings  
- [Tavily](https://tavily.com/) - Web search
- [ChromaDB](https://trychroma.com/) - Vector database
- [FastAPI](https://fastapi.tiangolo.com/) - REST API

---

**Happy studying! 🎓**

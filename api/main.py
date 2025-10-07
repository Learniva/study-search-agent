"""
FastAPI REST API for the Study and Search Agent.

Powered by LangChain & LangGraph:
- LangGraph: Thread-based conversation memory, autonomous routing, state management
- LangChain: RAG pipelines, tools framework, embeddings, vector stores
- 4 tools: Document Q&A, Web Search, Python REPL, Manim Animation
- Multi-part request handling (MCQs, summaries, study guides, flashcards)
"""

import os
import sys
from typing import Optional, List, Dict
from pathlib import Path
from contextlib import asynccontextmanager

# Add parent directory to path for imports
sys.path.insert(0, str(Path(__file__).parent.parent))

from fastapi import FastAPI, File, UploadFile, HTTPException, BackgroundTasks
from fastapi.responses import JSONResponse
from pydantic import BaseModel, Field
from dotenv import load_dotenv

from agent import StudySearchAgent
from tools.document_qa import initialize_document_qa

# Load environment variables
load_dotenv()

# Global agent instance
agent: Optional[StudySearchAgent] = None
documents_dir = os.getenv("DOCUMENTS_DIR", "documents")


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Lifespan event handler for startup and shutdown."""
    global agent
    
    # Startup
    print("🚀 Starting Study and Search Agent API...")
    
    # Get LLM provider
    llm_provider = os.getenv("LLM_PROVIDER", "gemini")
    print(f"📊 LLM Provider: {llm_provider.upper()}")
    
    # Load documents if available
    if os.path.exists(documents_dir) and os.listdir(documents_dir):
        print(f"📚 Loading documents from {documents_dir}...")
        initialize_document_qa(documents_dir)
    
    # Initialize agent
    try:
        agent = StudySearchAgent(llm_provider=llm_provider)
        print("✅ Agent initialized successfully!")
    except Exception as e:
        print(f"❌ Failed to initialize agent: {e}")
        raise
    
    yield
    
    # Shutdown (cleanup if needed)
    print("👋 Shutting down Study and Search Agent API...")


# Initialize FastAPI app with lifespan
app = FastAPI(
    title="Study and Search Agent API",
    description="Powered by LangChain & LangGraph: conversation memory, autonomous routing, RAG pipelines, 4 tools (Document Q&A, Web Search, Python REPL, Manim Animation)",
    version="2.0.0",
    lifespan=lifespan
)


# Request/Response Models
class QueryRequest(BaseModel):
    """Request model for querying the agent."""
    question: str = Field(..., description="The question to ask the agent")
    thread_id: Optional[str] = Field(default="default", description="Thread ID for conversation memory")
    
    class Config:
        json_schema_extra = {
            "example": {
                "question": "What are the types of machine learning in my notes?",
                "thread_id": "user123"
            }
        }


class QueryResponse(BaseModel):
    """Response model for agent queries."""
    question: str
    answer: str
    thread_id: str
    success: bool = True


class UploadResponse(BaseModel):
    """Response model for document uploads."""
    filename: str
    message: str
    size_bytes: int
    success: bool = True


class DocumentInfo(BaseModel):
    """Information about a document."""
    filename: str
    size_bytes: int
    size_readable: str


class DocumentsListResponse(BaseModel):
    """Response model for listing documents."""
    documents: List[DocumentInfo]
    total_count: int


class HealthResponse(BaseModel):
    """Health check response."""
    status: str
    llm_provider: str
    documents_loaded: int
    tools_available: List[str]
    features: List[str]


class ConversationHistoryResponse(BaseModel):
    """Response model for conversation history."""
    thread_id: str
    message_count: int
    messages: List[Dict[str, str]]


# API Endpoints

@app.get("/", tags=["General"])
async def root():
    """Root endpoint with API information."""
    return {
        "name": "Study and Search Agent API",
        "version": "2.0.0",
        "description": "Powered by LangChain & LangGraph",
        "features": [
            "LangGraph: state management, autonomous routing, conversation memory",
            "LangChain: RAG pipelines, tools framework, embeddings, vector stores",
            "4 tools: Document Q&A, Web Search, Python REPL, Manim Animation",
            "Multi-part requests (MCQs, summaries, study guides, flashcards)"
        ],
        "endpoints": {
            "health": "/health",
            "query": "/query",
            "history": "/history/{thread_id}",
            "documents": "/documents",
            "upload": "/documents/upload",
            "reload": "/reload"
        }
    }


@app.get("/health", response_model=HealthResponse, tags=["General"])
async def health_check():
    """Health check endpoint with system information."""
    if agent is None:
        raise HTTPException(status_code=503, detail="Agent not initialized")
    
    # Get tool names
    tool_names = [tool.name for tool in agent.tools]
    
    # Count documents
    doc_count = 0
    if os.path.exists(documents_dir):
        doc_count = len([f for f in os.listdir(documents_dir) 
                        if f.endswith(('.pdf', '.docx'))])
    
    return HealthResponse(
        status="healthy",
        llm_provider=agent.llm_provider.upper(),
        documents_loaded=doc_count,
        tools_available=tool_names,
        features=[
            "LangGraph: state management + routing + memory",
            "LangChain: RAG pipelines + tools + embeddings",
            "Thread-based conversation history",
            "Autonomous tool routing with fallback",
            "Context-aware follow-ups"
        ]
    )


@app.post("/query", response_model=QueryResponse, tags=["Agent"])
async def query_agent(request: QueryRequest):
    """
    Query the agent with a question. Supports conversation memory via thread_id.
    
    The agent autonomously chooses the appropriate tool:
    - Document_QA: Questions about documents, generate MCQs/summaries/study guides/flashcards
    - Web_Search: Real-time info, general knowledge (hybrid: Tavily→Google→DuckDuckGo)
    - Python_REPL: Math calculations and code execution
    - Manim_Animation: Create educational animations
    
    Features:
    - Conversation memory: Use same thread_id to maintain context
    - Context-aware follow-ups: Vague questions enriched with conversation history
    - Automatic fallback: Document_QA → Web_Search if document lacks content
    """
    if agent is None:
        raise HTTPException(status_code=503, detail="Agent not initialized")
    
    try:
        answer = agent.query(request.question, thread_id=request.thread_id)
        
        return QueryResponse(
            question=request.question,
            answer=answer,
            thread_id=request.thread_id,
            success=True
        )
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error processing query: {str(e)}")


@app.get("/history/{thread_id}", response_model=ConversationHistoryResponse, tags=["Agent"])
async def get_conversation_history(thread_id: str):
    """
    Get conversation history for a specific thread.
    
    Use this to retrieve past messages in a conversation thread.
    Thread IDs persist across API calls, allowing contextual conversations.
    """
    if agent is None:
        raise HTTPException(status_code=503, detail="Agent not initialized")
    
    try:
        from langchain_core.messages import HumanMessage, AIMessage
        
        history = agent.get_conversation_history(thread_id=thread_id)
        
        messages = []
        for msg in history:
            if isinstance(msg, HumanMessage):
                messages.append({"role": "user", "content": msg.content})
            elif isinstance(msg, AIMessage):
                messages.append({"role": "assistant", "content": msg.content})
        
        return ConversationHistoryResponse(
            thread_id=thread_id,
            message_count=len(messages),
            messages=messages
        )
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error retrieving history: {str(e)}")


@app.get("/documents", response_model=DocumentsListResponse, tags=["Documents"])
async def list_documents():
    """List all uploaded documents."""
    if not os.path.exists(documents_dir):
        return DocumentsListResponse(documents=[], total_count=0)
    
    docs = []
    for filename in os.listdir(documents_dir):
        if filename.endswith(('.pdf', '.docx')):
            filepath = Path(documents_dir) / filename
            size = filepath.stat().st_size
            
            # Human-readable size
            if size < 1024:
                size_readable = f"{size} B"
            elif size < 1024 * 1024:
                size_readable = f"{size / 1024:.1f} KB"
            else:
                size_readable = f"{size / (1024 * 1024):.1f} MB"
            
            docs.append(DocumentInfo(
                filename=filename,
                size_bytes=size,
                size_readable=size_readable
            ))
    
    return DocumentsListResponse(
        documents=sorted(docs, key=lambda x: x.filename),
        total_count=len(docs)
    )


@app.post("/documents/upload", response_model=UploadResponse, tags=["Documents"])
async def upload_document(
    file: UploadFile = File(..., description="PDF or DOCX file to upload"),
    background_tasks: BackgroundTasks = None
):
    """
    Upload a PDF or DOCX document for Q&A.
    
    After uploading, restart the agent to index the new document.
    """
    # Validate file type
    if not file.filename.endswith(('.pdf', '.docx')):
        raise HTTPException(
            status_code=400,
            detail="Only PDF and DOCX files are supported"
        )
    
    # Create documents directory if it doesn't exist
    Path(documents_dir).mkdir(exist_ok=True)
    
    # Save file
    file_path = Path(documents_dir) / file.filename
    try:
        content = await file.read()
        with open(file_path, "wb") as f:
            f.write(content)
        
        return UploadResponse(
            filename=file.filename,
            message=f"Document uploaded successfully. Restart required to index.",
            size_bytes=len(content),
            success=True
        )
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error uploading file: {str(e)}")


@app.delete("/documents/{filename}", tags=["Documents"])
async def delete_document(filename: str):
    """Delete a document by filename."""
    file_path = Path(documents_dir) / filename
    
    if not file_path.exists():
        raise HTTPException(status_code=404, detail=f"Document '{filename}' not found")
    
    try:
        file_path.unlink()
        return {
            "success": True,
            "message": f"Document '{filename}' deleted successfully"
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error deleting file: {str(e)}")


@app.post("/reload", tags=["Admin"])
async def reload_agent():
    """
    Reload the agent and re-index documents.
    
    Use this after uploading new documents to make them available for Q&A.
    """
    global agent
    
    try:
        # Reload documents
        if os.path.exists(documents_dir) and os.listdir(documents_dir):
            print(f"📚 Reloading documents from {documents_dir}...")
            initialize_document_qa(documents_dir)
        
        # Reinitialize agent
        llm_provider = os.getenv("LLM_PROVIDER", "gemini")
        agent = StudySearchAgent(llm_provider=llm_provider)
        
        # Count documents
        doc_count = len([f for f in os.listdir(documents_dir) 
                        if f.endswith(('.pdf', '.docx'))]) if os.path.exists(documents_dir) else 0
        
        return {
            "success": True,
            "message": "Agent reloaded successfully",
            "documents_indexed": doc_count
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error reloading agent: {str(e)}")


# Error handlers
@app.exception_handler(Exception)
async def global_exception_handler(request, exc):
    """Global exception handler."""
    return JSONResponse(
        status_code=500,
        content={
            "success": False,
            "error": str(exc)
        }
    )


if __name__ == "__main__":
    import uvicorn
    
    port = int(os.getenv("PORT", "8000"))
    host = os.getenv("HOST", "0.0.0.0")
    
    print(f"🚀 Starting API server on {host}:{port}")
    uvicorn.run(app, host=host, port=port, log_level="info")


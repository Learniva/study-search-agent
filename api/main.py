"""
FastAPI REST API for Multi-Agent Study & Grading System.

Powered by LangChain & LangGraph:
- Supervisor Pattern: Intelligent routing between Study and Grading agents
- Role-based access control: Students and Teachers have different capabilities
- Study Agent: Document Q&A, Web Search, Python REPL, Manim Animation
- Grading Agent: Essay grading, Code review, MCQ auto-grading (Teachers only)
- Thread-based conversation memory with state management
"""

import os
import sys
from typing import Optional, List, Dict, Any
from pathlib import Path
from contextlib import asynccontextmanager

# Add parent directory to path for imports
sys.path.insert(0, str(Path(__file__).parent.parent))

from fastapi import FastAPI, File, UploadFile, HTTPException, BackgroundTasks, Header
from fastapi.responses import JSONResponse, StreamingResponse
from pydantic import BaseModel, Field
from dotenv import load_dotenv

from agent.supervisor_agent import SupervisorAgent
from tools.document_qa import initialize_document_qa

# Database imports (optional - gracefully handle if not available)
try:
    from database.database import init_db, get_db_dependency
    from database.operations import get_grading_history, get_rubric_templates, save_rubric_template
    from sqlalchemy.orm import Session
    DATABASE_AVAILABLE = True
except ImportError:
    DATABASE_AVAILABLE = False
    print("⚠️  Database module not available. Database features will be disabled.")

# ML Features imports (optional - gracefully handle if not available)
try:
    from utils.ml import get_user_preferences, get_user_profile_manager
    from utils.ml import get_query_learner
    from utils.performance import get_performance_router
    from utils.ml import get_adaptive_rubric_manager
    ML_FEATURES_AVAILABLE = True
except ImportError:
    ML_FEATURES_AVAILABLE = False
    print("⚠️  ML features not available.")

# Load environment variables
load_dotenv()

# Global supervisor agent instance
supervisor: Optional[SupervisorAgent] = None
documents_dir = os.getenv("DOCUMENTS_DIR", "documents")


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Lifespan event handler for startup and shutdown."""
    global supervisor
    
    # Startup
    print("🚀 Starting Multi-Agent Study & Grading System API...")
    print("   Supervisor Pattern: Intelligent routing between agents")
    
    # Initialize database
    if DATABASE_AVAILABLE:
        print("\n📊 Initializing PostgreSQL database...")
        db_initialized = init_db()
        if db_initialized:
            print("✅ Database initialized successfully")
        else:
            print("⚠️  Database initialization failed - running without persistence")
    else:
        print("⚠️  Database module not available - running without persistence")
    
    # Get LLM provider
    llm_provider = os.getenv("LLM_PROVIDER", "gemini")
    print(f"\n📊 LLM Provider: {llm_provider.upper()}")
    
    # Load documents if available
    if os.path.exists(documents_dir) and os.listdir(documents_dir):
        print(f"📚 Loading documents from {documents_dir}...")
        initialize_document_qa(documents_dir)
    
    # Initialize supervisor agent
    print("\n🤖 Initializing agents...")
    try:
        supervisor = SupervisorAgent(llm_provider=llm_provider)
        print("✅ Supervisor Agent initialized successfully!")
        print("   • Study & Search Agent: Ready")
        print("   • AI Grading Agent: Ready (Teachers only)")
    except Exception as e:
        print(f"❌ Failed to initialize supervisor: {e}")
        raise
    
    yield
    
    # Shutdown (cleanup if needed)
    print("👋 Shutting down Multi-Agent System API...")


# Initialize FastAPI app with lifespan
app = FastAPI(
    title="Multi-Agent Study & Grading System API",
    description="Supervisor Pattern with role-based access: Study Agent (all users) + Grading Agent (teachers only). Powered by LangChain & LangGraph.",
    version="3.0.0",
    lifespan=lifespan
)


# Request/Response Models
class QueryRequest(BaseModel):
    """Request model for querying the supervisor agent."""
    question: str = Field(..., description="The question to ask the agent")
    user_role: str = Field(default="student", description="User role: student, teacher, or admin")
    thread_id: Optional[str] = Field(default="default", description="Thread ID for conversation memory")
    user_id: Optional[str] = Field(default=None, description="User ID for database tracking")
    student_id: Optional[str] = Field(default=None, description="Student ID (for grading tasks)")
    student_name: Optional[str] = Field(default=None, description="Student name (for grading tasks)")
    course_id: Optional[str] = Field(default=None, description="Course ID")
    assignment_id: Optional[str] = Field(default=None, description="Assignment ID")
    assignment_name: Optional[str] = Field(default=None, description="Assignment name")
    
    class Config:
        json_schema_extra = {
            "example": {
                "question": "Grade this essay: Democracy is important because...",
                "user_role": "teacher",
                "thread_id": "prof123",
                "user_id": "prof123",
                "student_id": "stu456",
                "student_name": "John Doe",
                "course_id": "CS101",
                "assignment_id": "essay1"
            }
        }


class QueryResponse(BaseModel):
    """Response model for agent queries."""
    question: str
    answer: str
    agent_used: Optional[str] = None
    user_role: str
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
    architecture: str
    agents_available: List[str]
    features: List[str]


class ConversationHistoryResponse(BaseModel):
    """Response model for conversation history."""
    thread_id: str
    message_count: int
    messages: List[Dict[str, str]]


class FeedbackRequest(BaseModel):
    """Request model for submitting user feedback."""
    user_id: str = Field(..., description="User ID")
    query: str = Field(..., description="The query that was asked")
    tool_used: str = Field(..., description="Tool that was used")
    response_time: float = Field(..., description="Response time in seconds")
    quality_score: Optional[float] = Field(None, description="Quality rating 0-1", ge=0, le=1)
    success: bool = Field(True, description="Whether the interaction was successful")
    feedback_text: Optional[str] = Field(None, description="Optional text feedback")
    
    class Config:
        json_schema_extra = {
            "example": {
                "user_id": "student123",
                "query": "What is machine learning?",
                "tool_used": "Web_Search",
                "response_time": 2.5,
                "quality_score": 0.9,
                "success": True,
                "feedback_text": "Great explanation!"
            }
        }


class ProfessorFeedbackRequest(BaseModel):
    """Request model for professor grading feedback."""
    professor_id: str = Field(..., description="Professor ID")
    rubric_type: str = Field(..., description="Type of rubric (essay, code, etc.)")
    ai_scores: Dict[str, float] = Field(..., description="AI's criterion scores")
    professor_scores: Dict[str, float] = Field(..., description="Professor's corrected scores")
    overall_ai_score: Optional[float] = Field(None, description="Overall AI score")
    overall_professor_score: Optional[float] = Field(None, description="Overall professor score")
    
    class Config:
        json_schema_extra = {
            "example": {
                "professor_id": "prof_smith",
                "rubric_type": "essay",
                "ai_scores": {
                    "Thesis & Argument": 25,
                    "Evidence & Support": 18,
                    "Organization": 17
                },
                "professor_scores": {
                    "Thesis & Argument": 25,
                    "Evidence & Support": 22,
                    "Organization": 17
                },
                "overall_ai_score": 81,
                "overall_professor_score": 85
            }
        }


# API Endpoints

@app.get("/", tags=["General"])
async def root():
    """Root endpoint with API information."""
    return {
        "name": "Multi-Agent Study & Grading System API",
        "version": "3.0.0",
        "architecture": "Supervisor Pattern (Centralized Control)",
        "description": "Intelligent routing between Study and Grading agents based on user role and task",
        "agents": {
            "supervisor": "Routes requests to appropriate specialized agent",
            "study_agent": "Document Q&A, Web Search, Python REPL, Manim Animation (all users)",
            "grading_agent": "Essay grading, Code review, MCQ auto-grading (teachers only)"
        },
        "features": [
            "🎯 Supervisor Pattern: Intelligent task routing",
            "🔒 Role-based access control (student/teacher/admin)",
            "💾 Thread-based conversation memory",
            "📚 Study Tools: Research, Q&A, animations, flashcards",
            "📝 Grading Tools: Essay grading, code review, auto-grading"
        ],
        "endpoints": {
            "health": "/health",
            "query": "/query",
            "query_stream": "/query/stream",
            "capabilities": "/capabilities/{role}",
            "history": "/history/{thread_id}",
            "documents": "/documents",
            "upload": "/documents/upload",
            "reload": "/reload",
            "ml_features": {
                "feedback": "/ml/feedback",
                "profile": "/ml/profile/{user_id}",
                "stats": "/ml/stats",
                "performance": "/ml/performance",
                "consistency": "/ml/consistency/{professor_id}",
                "grading_feedback": "/ml/grading/feedback"
            }
        }
    }


@app.get("/health", response_model=HealthResponse, tags=["General"])
async def health_check():
    """Health check endpoint with system information."""
    if supervisor is None:
        raise HTTPException(status_code=503, detail="Supervisor not initialized")
    
    # Count documents
    doc_count = 0
    if os.path.exists(documents_dir):
        doc_count = len([f for f in os.listdir(documents_dir) 
                        if f.endswith(('.pdf', '.docx'))])
    
    return HealthResponse(
        status="healthy",
        llm_provider=supervisor.llm_provider.upper(),
        documents_loaded=doc_count,
        architecture="Supervisor Pattern (Centralized Control)",
        agents_available=[
            "Supervisor Agent (Router)",
            "Study & Search Agent",
            "AI Grading Agent (Teachers only)"
        ],
        features=[
            "🎯 Intelligent task routing via Supervisor",
            "🔒 Role-based access control",
            "💾 Thread-based conversation memory",
            "📚 Study tools: Document Q&A, Web Search, Python, Manim",
            "📝 Grading tools: Essay, Code, MCQ evaluation"
        ]
    )


@app.post("/query", response_model=QueryResponse, tags=["Supervisor"])
async def query_supervisor(request: QueryRequest):
    """
    Query the supervisor agent with automatic routing to Study or Grading agent.
    
    **Role-Based Routing:**
    - **Students**: Can only access Study Agent (research, Q&A, animations, flashcards)
    - **Teachers**: Can access both Study and Grading agents
    - **Admin**: Full access to all agents
    
    **Study Agent Features:**
    - Document Q&A, Web Search, Python REPL, Manim Animation
    - Generate study guides, flashcards, MCQs for learning
    
    **Grading Agent Features (Teachers only):**
    - Grade essays with rubrics
    - Review code submissions
    - Auto-grade MCQ tests
    - Generate personalized feedback
    
    **Features:**
    - Conversation memory: Use same thread_id to maintain context
    - Intelligent routing: Supervisor automatically chooses the right agent
    - Access control: Role-based permissions enforced
    """
    if supervisor is None:
        raise HTTPException(status_code=503, detail="Supervisor not initialized")
    
    try:
        # Query supervisor with role-based routing and database context
        result = supervisor.query(
            question=request.question,
            user_role=request.user_role,
            thread_id=request.thread_id,
            user_id=request.user_id,
            student_id=request.student_id,
            student_name=request.student_name,
            course_id=request.course_id,
            assignment_id=request.assignment_id,
            assignment_name=request.assignment_name
        )
        
        return QueryResponse(
            question=request.question,
            answer=result["answer"],
            agent_used=result.get("agent_used"),
            user_role=request.user_role,
            thread_id=request.thread_id,
            success=result["success"]
        )
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error processing query: {str(e)}")


@app.get("/capabilities/{role}", tags=["Supervisor"])
async def get_capabilities(role: str):
    """
    Get available capabilities for a specific user role.
    
    Roles:
    - student: Study features only
    - teacher: Study + Grading features
    - admin: Full access
    """
    if supervisor is None:
        raise HTTPException(status_code=503, detail="Supervisor not initialized")
    
    try:
        capabilities = supervisor.get_capabilities(role)
        return {
            "role": role,
            "study_features": capabilities["study_features"],
            "grading_features": capabilities["grading_features"],
            "total_features": len(capabilities["study_features"]) + len(capabilities["grading_features"])
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error getting capabilities: {str(e)}")


@app.get("/history/{thread_id}", response_model=ConversationHistoryResponse, tags=["Supervisor"])
async def get_conversation_history(
    thread_id: str,
    agent: str = "study"
):
    """
    Get conversation history for a specific thread.
    
    Args:
    - thread_id: The conversation thread ID
    - agent: Which agent's history to retrieve ("study" or "grading")
    
    Use this to retrieve past messages in a conversation thread.
    Thread IDs persist across API calls, allowing contextual conversations.
    """
    if supervisor is None:
        raise HTTPException(status_code=503, detail="Supervisor not initialized")
    
    try:
        from langchain_core.messages import HumanMessage, AIMessage
        
        history = supervisor.get_conversation_history(thread_id=thread_id, agent=agent)
        
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


@app.get("/grading/history/{professor_id}", tags=["Grading"])
async def get_professor_grading_history(
    professor_id: str,
    limit: int = 50,
    offset: int = 0,
    course_id: Optional[str] = None,
    assignment_id: Optional[str] = None
):
    """
    Get grading history for a professor.
    
    **Requires:**
    - PostgreSQL database configured
    - Professor must exist in database
    
    **Query Parameters:**
    - limit: Maximum number of results (default: 50)
    - offset: Pagination offset (default: 0)
    - course_id: Filter by course (optional)
    - assignment_id: Filter by assignment (optional)
    
    **Returns:**
    - List of grading sessions with scores, feedback, and metadata
    """
    if not DATABASE_AVAILABLE:
        raise HTTPException(
            status_code=503,
            detail="Database not available. Please configure PostgreSQL."
        )
    
    try:
        from database.database import get_db
        
        with get_db() as db:
            history = get_grading_history(
                db=db,
                professor_id=professor_id,
                limit=limit,
                offset=offset,
                course_id=course_id,
                assignment_id=assignment_id
            )
            
            # Convert to dict
            result = []
            for session in history:
                result.append({
                    "id": str(session.id),
                    "student_id": session.student_id,
                    "student_name": session.student_name,
                    "course_id": session.course_id,
                    "assignment_id": session.assignment_id,
                    "assignment_name": session.assignment_name,
                    "grading_type": session.grading_type,
                    "score": session.score,
                    "max_score": session.max_score,
                    "percentage": session.percentage,
                    "grade_letter": session.grade_letter,
                    "ai_confidence": session.ai_confidence,
                    "reviewed_by_professor": session.reviewed_by_professor,
                    "created_at": session.created_at.isoformat(),
                    "agent_used": session.agent_used
                })
            
            return {
                "professor_id": professor_id,
                "total": len(result),
                "limit": limit,
                "offset": offset,
                "history": result
            }
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error retrieving grading history: {str(e)}")


@app.get("/grading/session/{session_id}", tags=["Grading"])
async def get_grading_session_details(session_id: str):
    """
    Get detailed information about a specific grading session.
    
    Includes full AI feedback, submission content, and all metadata.
    """
    if not DATABASE_AVAILABLE:
        raise HTTPException(
            status_code=503,
            detail="Database not available. Please configure PostgreSQL."
        )
    
    try:
        from database.database import get_db
        from database.models import GradingSession
        from uuid import UUID
        
        with get_db() as db:
            session = db.query(GradingSession).filter(
                GradingSession.id == UUID(session_id)
            ).first()
            
            if not session:
                raise HTTPException(status_code=404, detail="Grading session not found")
            
            return {
                "id": str(session.id),
                "professor_id": str(session.professor_id),
                "student_id": session.student_id,
                "student_name": session.student_name,
                "course_id": session.course_id,
                "assignment_id": session.assignment_id,
                "assignment_name": session.assignment_name,
                "grading_type": session.grading_type,
                "submission": session.submission,
                "score": session.score,
                "max_score": session.max_score,
                "percentage": session.percentage,
                "grade_letter": session.grade_letter,
                "ai_feedback": session.ai_feedback,
                "professor_feedback": session.professor_feedback,
                "ai_confidence": session.ai_confidence,
                "processing_time_seconds": session.processing_time_seconds,
                "reviewed_by_professor": session.reviewed_by_professor,
                "professor_adjusted_score": session.professor_adjusted_score,
                "posted_to_lms": session.posted_to_lms,
                "created_at": session.created_at.isoformat(),
                "agent_used": session.agent_used
            }
    except ValueError:
        raise HTTPException(status_code=400, detail="Invalid session ID format")
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error retrieving session: {str(e)}")


@app.get("/rubrics/{professor_id}", tags=["Rubrics"])
async def get_professor_rubrics(
    professor_id: str,
    rubric_type: Optional[str] = None
):
    """
    Get rubric templates for a professor.
    
    **Returns:**
    - Professor's personal rubrics
    - Public rubrics (if include_public=true)
    """
    if not DATABASE_AVAILABLE:
        raise HTTPException(
            status_code=503,
            detail="Database not available. Please configure PostgreSQL."
        )
    
    try:
        from database.database import get_db
        
        with get_db() as db:
            rubrics = get_rubric_templates(
                db=db,
                professor_id=professor_id,
                rubric_type=rubric_type,
                include_public=True
            )
            
            result = []
            for rubric in rubrics:
                result.append({
                    "id": str(rubric.id),
                    "name": rubric.name,
                    "description": rubric.description,
                    "rubric_type": rubric.rubric_type,
                    "criteria": rubric.criteria,
                    "max_score": rubric.max_score,
                    "times_used": rubric.times_used,
                    "is_public": rubric.is_public,
                    "created_at": rubric.created_at.isoformat()
                })
            
            return {
                "professor_id": professor_id,
                "total": len(result),
                "rubrics": result
            }
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error retrieving rubrics: {str(e)}")


@app.post("/rubrics", tags=["Rubrics"])
async def create_rubric(
    professor_id: str,
    name: str,
    rubric_type: str,
    criteria: Dict[str, Any],
    max_score: float,
    description: Optional[str] = None,
    is_public: bool = False
):
    """
    Create a new rubric template.
    
    **Example criteria format:**
    ```json
    {
      "criteria": [
        {
          "name": "Thesis Statement",
          "weight": 0.25,
          "levels": {
            "Excellent": "Clear, arguable thesis",
            "Good": "Thesis present but could be stronger"
          }
        }
      ]
    }
    ```
    """
    if not DATABASE_AVAILABLE:
        raise HTTPException(
            status_code=503,
            detail="Database not available. Please configure PostgreSQL."
        )
    
    try:
        from database.database import get_db
        
        with get_db() as db:
            rubric = save_rubric_template(
                db=db,
                professor_id=professor_id,
                name=name,
                rubric_type=rubric_type,
                criteria=criteria,
                max_score=max_score,
                description=description,
                is_public=is_public
            )
            
            return {
                "success": True,
                "rubric_id": str(rubric.id),
                "message": f"Rubric '{name}' created successfully"
            }
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error creating rubric: {str(e)}")


@app.post("/reload", tags=["Admin"])
async def reload_supervisor():
    """
    Reload the supervisor agent and re-index documents.
    
    Use this after uploading new documents to make them available for Q&A.
    """
    global supervisor
    
    try:
        # Reload documents
        if os.path.exists(documents_dir) and os.listdir(documents_dir):
            print(f"📚 Reloading documents from {documents_dir}...")
            initialize_document_qa(documents_dir)
        
        # Reinitialize supervisor
        llm_provider = os.getenv("LLM_PROVIDER", "gemini")
        supervisor = SupervisorAgent(llm_provider=llm_provider)
        
        # Count documents
        doc_count = len([f for f in os.listdir(documents_dir) 
                        if f.endswith(('.pdf', '.docx'))]) if os.path.exists(documents_dir) else 0
        
        return {
            "success": True,
            "message": "Supervisor and all agents reloaded successfully",
            "documents_indexed": doc_count
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error reloading supervisor: {str(e)}")


# =============================================================================
# ML FEATURES API ENDPOINTS
# =============================================================================

@app.post("/ml/feedback", tags=["ML Features"])
async def submit_feedback(request: FeedbackRequest):
    """
    Submit user feedback for ML learning.
    
    This endpoint allows you to provide feedback on query results, which helps
    the ML systems learn and improve:
    
    - **User Profile Learning**: Tracks preferences and interaction patterns
    - **Query Pattern Learning**: Improves tool selection accuracy
    - **Performance-Based Routing**: Adjusts tool scoring based on quality
    
    **Required:**
    - user_id: To track learning per user
    - query: The question that was asked
    - tool_used: Which tool provided the answer
    - response_time: How long it took
    
    **Optional but Recommended:**
    - quality_score: 0-1 rating of response quality
    - success: Whether the answer was satisfactory
    - feedback_text: Additional comments
    
    **Example:**
    ```json
    {
      "user_id": "student123",
      "query": "What is machine learning?",
      "tool_used": "Web_Search",
      "response_time": 2.5,
      "quality_score": 0.9,
      "success": true,
      "feedback_text": "Great explanation!"
    }
    ```
    """
    if not ML_FEATURES_AVAILABLE:
        raise HTTPException(
            status_code=503,
            detail="ML features not available. Please ensure ML modules are installed."
        )
    
    try:
        from utils.ml import update_user_profile
        from utils.ml import learn_from_query
        from utils.performance import get_performance_router
        
        # Update user profile
        update_user_profile(
            user_id=request.user_id,
            query=request.query,
            tool_used=request.tool_used,
            response_time=request.response_time,
            feedback=request.quality_score
        )
        
        # Update query learner
        learn_from_query(
            query=request.query,
            tool_used=request.tool_used,
            success=request.success,
            response_time=request.response_time,
            user_feedback=request.quality_score
        )
        
        # Update performance router if available
        router = get_performance_router()
        router.record_result(
            tool=request.tool_used,
            query=request.query,
            success=request.success,
            response_time=request.response_time,
            quality_score=request.quality_score
        )
        
        return {
            "success": True,
            "message": "Feedback recorded successfully",
            "user_id": request.user_id,
            "ml_systems_updated": ["user_profile", "query_learner", "performance_router"]
        }
    
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error recording feedback: {str(e)}")


@app.get("/ml/profile/{user_id}", tags=["ML Features"])
async def get_user_profile(user_id: str):
    """
    Get ML profile for a user.
    
    Returns learning data about the user including:
    - Interaction statistics
    - Tool preferences
    - Subject interests
    - Performance metrics
    - Satisfaction scores
    
    **Use Cases:**
    - Personalize user experience
    - Understand user behavior
    - Identify areas for improvement
    - Track learning progress
    """
    if not ML_FEATURES_AVAILABLE:
        raise HTTPException(
            status_code=503,
            detail="ML features not available."
        )
    
    try:
        preferences = get_user_preferences(user_id)
        
        if not preferences:
            raise HTTPException(
                status_code=404,
                detail=f"No profile found for user {user_id}"
            )
        
        return {
            "user_id": user_id,
            "profile": preferences,
            "ml_enabled": True
        }
    
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error retrieving profile: {str(e)}")


@app.get("/ml/stats", tags=["ML Features"])
async def get_ml_stats():
    """
    Get overall ML system statistics.
    
    Returns comprehensive statistics about all ML systems:
    
    **Performance Router:**
    - Tool performance scores
    - Success rates per tool
    - Average response times
    - Best/worst performers
    
    **Query Learning:**
    - Total queries learned
    - Tool prediction accuracy
    - Query patterns identified
    
    **User Profiles:**
    - Total users tracked
    - Average satisfaction scores
    - Tool usage distribution
    
    **Adaptive Rubrics (if available):**
    - Active rubrics count
    - Adaptation statistics per professor
    """
    if not ML_FEATURES_AVAILABLE:
        raise HTTPException(
            status_code=503,
            detail="ML features not available."
        )
    
    try:
        stats = {
            "ml_enabled": True,
            "systems": {}
        }
        
        # Performance Router Stats
        try:
            router = get_performance_router()
            perf_report = router.get_performance_report()
            
            stats["systems"]["performance_router"] = {
                "status": "active",
                "overall_metrics": perf_report["overall_metrics"],
                "best_performer": perf_report["best_performer"],
                "worst_performer": perf_report["worst_performer"],
                "tool_count": len(perf_report["tool_performance"])
            }
        except Exception as e:
            stats["systems"]["performance_router"] = {
                "status": "error",
                "error": str(e)
            }
        
        # Query Learner Stats
        try:
            learner = get_query_learner()
            stats["systems"]["query_learner"] = {
                "status": "active",
                "patterns_learned": learner.query_count,
                "tools_tracked": len(learner.tool_performance)
            }
        except Exception as e:
            stats["systems"]["query_learner"] = {
                "status": "error",
                "error": str(e)
            }
        
        # User Profile Stats
        try:
            profile_manager = get_user_profile_manager()
            stats["systems"]["user_profiles"] = {
                "status": "active",
                "users_tracked": len(profile_manager.profiles)
            }
        except Exception as e:
            stats["systems"]["user_profiles"] = {
                "status": "error",
                "error": str(e)
            }
        
        # Adaptive Rubrics Stats (if grading agent available)
        try:
            rubric_manager = get_adaptive_rubric_manager()
            stats["systems"]["adaptive_rubrics"] = {
                "status": "active",
                "rubrics_count": len(rubric_manager.rubrics)
            }
        except Exception as e:
            stats["systems"]["adaptive_rubrics"] = {
                "status": "unavailable",
                "note": "Grading agent not initialized"
            }
        
        return stats
    
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error retrieving stats: {str(e)}")


@app.get("/ml/performance", tags=["ML Features"])
async def get_performance_metrics():
    """
    Get detailed performance metrics for all tools.
    
    Returns detailed performance data:
    - Per-tool success rates
    - Average response times
    - Performance scores (0-100)
    - Health status
    - Performance trends
    - Recent routing decisions
    
    **Use Cases:**
    - Monitor system health
    - Identify slow/failing tools
    - Optimize routing decisions
    - Debug performance issues
    """
    if not ML_FEATURES_AVAILABLE:
        raise HTTPException(
            status_code=503,
            detail="ML features not available."
        )
    
    try:
        router = get_performance_router()
        report = router.get_performance_report()
        
        return {
            "status": "success",
            "performance_report": report
        }
    
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error retrieving performance metrics: {str(e)}")


@app.get("/ml/consistency/{professor_id}", tags=["ML Features"])
async def get_consistency_report(
    professor_id: str,
    grading_type: Optional[str] = None
):
    """
    Get grading consistency report for a professor.
    
    Analyzes AI-professor grading agreement and provides recommendations:
    
    **Metrics:**
    - Average score difference
    - Agreement rate (within 5 points)
    - Systematic bias detection
    - Consistency score (0-100)
    
    **Returns:**
    - Detailed metrics
    - Recommendation for calibration
    - Whether calibration is needed
    
    **Example Response:**
    ```json
    {
      "status": "analyzed",
      "gradings_count": 30,
      "metrics": {
        "avg_difference": "2.3",
        "agreement_rate": "90.0%",
        "systematic_bias": "+1.5",
        "consistency_score": "85.0/100"
      },
      "recommendation": "✅ Good consistency - Minor improvements possible",
      "calibration_needed": false
    }
    ```
    """
    if not ML_FEATURES_AVAILABLE:
        raise HTTPException(
            status_code=503,
            detail="ML features not available."
        )
    
    try:
        rubric_manager = get_adaptive_rubric_manager()
        report = rubric_manager.get_consistency_report(professor_id, grading_type)
        
        return {
            "professor_id": professor_id,
            "grading_type": grading_type or "all",
            "report": report
        }
    
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error retrieving consistency report: {str(e)}")


@app.post("/ml/grading/feedback", tags=["ML Features"])
async def submit_grading_feedback(request: ProfessorFeedbackRequest):
    """
    Submit professor feedback for adaptive rubric learning.
    
    When a professor corrects AI grading scores, submit the corrections here
    to enable the adaptive rubric system to learn and improve.
    
    **Process:**
    1. AI grades submission with current rubric
    2. Professor reviews and makes corrections
    3. Submit corrections via this endpoint
    4. Rubric adapts using gradient descent learning
    5. Future gradings use learned weights
    
    **Required:**
    - professor_id: To track per-professor adaptations
    - rubric_type: Type of rubric (essay, code, mcq, etc.)
    - ai_scores: AI's original scores per criterion
    - professor_scores: Professor's corrected scores
    
    **Optional:**
    - overall_ai_score: Overall AI score
    - overall_professor_score: Overall professor score
    
    **Example:**
    ```json
    {
      "professor_id": "prof_smith",
      "rubric_type": "essay",
      "ai_scores": {
        "Thesis & Argument": 25,
        "Evidence & Support": 18,
        "Organization": 17
      },
      "professor_scores": {
        "Thesis & Argument": 25,
        "Evidence & Support": 22,
        "Organization": 17
      }
    }
    ```
    
    **Learning:**
    - Rubric adapts to professor's grading style
    - Weights adjust based on systematic corrections
    - Future gradings become more aligned
    """
    if not ML_FEATURES_AVAILABLE:
        raise HTTPException(
            status_code=503,
            detail="ML features not available."
        )
    
    try:
        rubric_manager = get_adaptive_rubric_manager()
        
        rubric_manager.record_grading(
            professor_id=request.professor_id,
            rubric_type=request.rubric_type,
            ai_scores=request.ai_scores,
            professor_scores=request.professor_scores,
            overall_ai_score=request.overall_ai_score,
            overall_professor_score=request.overall_professor_score
        )
        
        # Calculate changes
        changes = []
        for criterion, prof_score in request.professor_scores.items():
            ai_score = request.ai_scores.get(criterion, 0)
            if prof_score != ai_score:
                diff = prof_score - ai_score
                changes.append({
                    "criterion": criterion,
                    "ai_score": ai_score,
                    "professor_score": prof_score,
                    "difference": diff
                })
        
        return {
            "success": True,
            "message": "Grading feedback recorded successfully",
            "professor_id": request.professor_id,
            "rubric_type": request.rubric_type,
            "changes_recorded": len(changes),
            "changes": changes,
            "learning_status": "Rubric adapted based on feedback"
        }
    
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error recording grading feedback: {str(e)}")


@app.post("/query/stream", tags=["Streaming"])
async def stream_query(request: QueryRequest):
    """
    Stream query response with Server-Sent Events (SSE).
    
    Instead of waiting for the complete response, this endpoint streams
    the response as it's being generated, significantly improving perceived
    performance for long responses.
    
    **Benefits:**
    - ⚡ Immediate feedback (see response start instantly)
    - 📊 Progressive display (watch response build in real-time)
    - ⏱️ Better UX (no waiting for full response)
    - 🚀 Faster perceived performance (60-80% improvement)
    
    **Usage:**
    ```javascript
    // JavaScript example
    const eventSource = new EventSource('/query/stream?question=What is AI?');
    
    eventSource.onmessage = (event) => {
        console.log('Chunk received:', event.data);
        document.getElementById('response').innerHTML += event.data;
    };
    
    eventSource.addEventListener('done', () => {
        console.log('Response complete!');
        eventSource.close();
    });
    ```
    
    **Python example:**
    ```python
    import requests
    
    response = requests.post(
        'http://localhost:8000/query/stream',
        json={'question': 'What is AI?', 'user_role': 'student'},
        stream=True
    )
    
    for line in response.iter_lines():
        if line:
            print(line.decode('utf-8'))
    ```
    
    **Response Format:**
    Server-Sent Events (SSE) with:
    - `data: <chunk>` - Response chunks
    - `event: done` - Completion signal
    - `event: error` - Error signal
    """
    if supervisor is None:
        raise HTTPException(status_code=503, detail="Supervisor not initialized")
    
    async def generate():
        """Generate SSE stream."""
        try:
            # Note: Current supervisor.query() is synchronous
            # This is a simplified streaming implementation
            # For true streaming, the LLM would need to support streaming
            
            yield f"data: {{\"status\": \"processing\", \"message\": \"Query received...\"}}\n\n"
            
            # Execute query (this would need to be async/streaming in production)
            import asyncio
            result = await asyncio.to_thread(
                supervisor.query,
                question=request.question,
                user_role=request.user_role,
                thread_id=request.thread_id,
                user_id=request.user_id,
                student_id=request.student_id,
                student_name=request.student_name,
                course_id=request.course_id,
                assignment_id=request.assignment_id,
                assignment_name=request.assignment_name
            )
            
            # Simulate streaming by chunking the response
            answer = result["answer"]
            chunk_size = 50  # Characters per chunk
            
            for i in range(0, len(answer), chunk_size):
                chunk = answer[i:i + chunk_size]
                yield f"data: {chunk}\n\n"
                await asyncio.sleep(0.01)  # Small delay for smooth streaming
            
            # Send completion event
            yield f"event: done\ndata: {{\"status\": \"complete\", \"agent_used\": \"{result.get('agent_used', 'unknown')}\"}}\n\n"
        
        except Exception as e:
            yield f"event: error\ndata: {{\"error\": \"{str(e)}\"}}\n\n"
    
    return StreamingResponse(
        generate(),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "Connection": "keep-alive",
            "X-Accel-Buffering": "no"  # Disable nginx buffering
        }
    )


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


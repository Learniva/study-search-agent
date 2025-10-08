# Supervisor Agent - Architecture

Multi-agent router using Supervisor Pattern for role-based access control between Study and Grading agents.

## System Architecture

```
User (role) → Supervisor (LangGraph) → [Study | Grading]
                    ↓
          [Classify → Check → Route]
                    ↓
              Agent Selection
                    ↓
          Study Agent (All)  |  Grading Agent (Teachers)
                    ↓                      ↓
              Tools                    Tools
              (QA, Search, REPL)      (Essay, Code, MCQ)
```

## Components

### 1. Supervisor Agent

**Pattern:** Centralized Control (single decision point)  
**Framework:** LangGraph with conditional routing  
**State:** SupervisorState (question, user_role, intent, access_denied, result)  
**Nodes:** classify_intent, check_access, route_to_agent  
**Flow:** Read request → Classify intent → Check role → Route

**Why Supervisor?**
- Single routing decision (low latency)
- Clear access control enforcement
- Easy to debug and maintain
- Cost-effective (Gemini routing)
- Scalable (add agents easily)

### 2. Intent Classification

```
Question → LLM Analysis → [STUDY | GRADE]

STUDY triggers:
- "Explain...", "Generate MCQs", "Create study guide"
- "Summarize...", "Make flashcards", "Animate..."

GRADE triggers:
- "Grade this...", "Evaluate...", "Provide feedback"
- "Review code...", "Score this...", "Compare answers"
```

### 3. Access Control

**Enforcement:** LangGraph conditional edges  
**Location:** Supervisor `check_access` node  
**Logic:** If intent=GRADE and role=STUDENT → deny

| Role      | Study | Grading | Enforcement |
|-----------|-------|---------|-------------|
| Student   | ✅    | ❌      | Supervisor  |
| Teacher   | ✅    | ✅      | Supervisor  |
| Professor | ✅    | ✅      | Supervisor  |
| Admin     | ✅    | ✅      | Supervisor  |

### 4. Routing Logic

```python
def route(state: SupervisorState) -> str:
    if state["access_denied"]:
        return "deny_access"
    
    if state["intent"] == "STUDY":
        return "study_agent"
    
    if state["intent"] == "GRADE":
        return "grading_agent"
```

**Conditional Edges:**
```
check_access → {
    "study": study_agent,
    "grade": grading_agent,
    "denied": deny_access
}
```

## Agent Comparison

### Study Agent

**Access:** All users  
**Tools:**
- document_qa (RAG with ChromaDB)
- web_search (Tavily/DuckDuckGo)
- python_repl (code execution)
- manim_animation (educational videos)

**Use Cases:**
- Research and Q&A
- MCQ/flashcard generation
- Study guide creation
- Math/coding help

### Grading Agent

**Access:** Teachers only  
**Tools:**
- grade_essay (rubric-based)
- review_code (correctness/efficiency)
- grade_mcq (auto-scoring)
- evaluate_with_rubric (custom)
- generate_feedback (constructive)
- answer_comparator (vs model answer)

**Use Cases:**
- Essay grading
- Code review
- MCQ auto-grading
- Rubric evaluation
- Feedback generation

## LMS Integration

### Canvas (LTI 1.3)

**Setup:**
```python
# 1. Register as LTI tool
# 2. Configure OAuth 2.0
# 3. Receive launch with user context

lti_launch → {
    "user_id": "12345",
    "role": "Instructor",  # or "Student"
    "course_id": "CS101",
    "assignment_id": "essay1"
}
```

**Integration Points:**
- Grade passback (LTI Advantage AGS)
- Deep linking (assignment selection)
- Names and Roles (roster sync)

### Google Classroom (OAuth 2.0)

**Setup:**
```python
# 1. Enable Classroom API
# 2. OAuth consent screen
# 3. Request scopes

scopes = [
    "classroom.courses.readonly",
    "classroom.rosters.readonly",
    "classroom.coursework.students"
]
```

**Integration Points:**
- Coursework retrieval
- Student submissions
- Grade posting (via API)

## Tech Stack

**Framework:**
- LangGraph: Multi-agent routing
- LangChain: Tools + RAG
- FastAPI: REST API

**LLM:** Gemini 2.5 Flash (routing + agents)  
**Auth:** PyJWT, python-jose, pylti1.3  
**LMS:** canvasapi, google-api-python-client  
**Database:** PostgreSQL (grading history)

## Configuration

```bash
# .env
GOOGLE_API_KEY=xxx              # Required (Gemini)
DATABASE_URL=postgresql://...   # Optional (persistence)

# LMS (optional)
CANVAS_API_URL=https://...
CANVAS_API_KEY=xxx
GOOGLE_CLIENT_ID=xxx
GOOGLE_CLIENT_SECRET=xxx
```

## API Flow

### 1. CLI Request
```bash
python main.py --role professor --question "Grade essay..."
    ↓
Supervisor classifies → Routes to Grading Agent → Returns result
```

### 2. API Request
```bash
POST /query
Headers: Authorization: Bearer <JWT>
Body: {"question": "Grade essay...", "role": "professor"}
    ↓
JWT → Extract role → Supervisor → Agent → Response
```

### 3. LMS Launch (Canvas)
```bash
Canvas → LTI Launch → Supervisor (with role from LMS) → Agent
    ↓
Result → Grade Passback → Canvas Gradebook
```

## Security

**Authentication:**
- CLI: `--role` flag (development)
- API: JWT tokens
- LMS: LTI 1.3 / OAuth 2.0

**Authorization:**
- Role enforcement in Supervisor
- LangGraph conditional routing
- Access denied for unauthorized requests

**Data Protection:**
- FERPA-compliant storage
- Encrypted credentials (.env)
- User isolation (professor_id foreign keys)
- No student data in logs

## Deployment

### Development
```bash
python main.py --role professor
python api/main.py  # localhost:8000
```

### Production
```bash
# With database
docker-compose up  # PostgreSQL + API
uvicorn api.main:app --host 0.0.0.0 --port 8000

# With LMS
# Configure LTI endpoints in Canvas/Classroom
# Set up OAuth callbacks
```

### Environment
```bash
# Required
GOOGLE_API_KEY=xxx

# Production
DATABASE_URL=postgresql://...
SECRET_KEY=xxx  # JWT signing
CANVAS_API_KEY=xxx  # If using Canvas
```

## Workflow Examples

### Study Workflow (Student)
```
1. Student asks: "Generate 10 MCQs about photosynthesis"
2. Supervisor classifies → STUDY intent
3. Routes to Study Agent
4. Study Agent uses document_qa tool
5. Returns MCQs
```

### Grading Workflow (Teacher)
```
1. Teacher asks: "Grade this essay: [text]"
2. Supervisor classifies → GRADE intent
3. Checks role → Teacher (authorized)
4. Routes to Grading Agent
5. Grading Agent uses grade_essay tool
6. Saves to database (if --user-id provided)
7. Returns score + feedback
```

### Blocked Workflow (Student)
```
1. Student asks: "Grade this essay: [text]"
2. Supervisor classifies → GRADE intent
3. Checks role → Student (unauthorized)
4. Returns access denied message
5. Student redirected to study features
```

## Extension Points

**Add agent:** Create agent class, add to Supervisor routing  
**Add role:** Update `check_access` logic in Supervisor  
**Add LMS:** Implement OAuth/LTI handler in `api/main.py`  
**Add tool:** Add to respective agent's tool list  
**Customize routing:** Modify `classify_intent` prompt

## Performance

**Intent classification:** <1s (Gemini routing)  
**Access check:** <0.1s (conditional logic)  
**Study query:** 2-10s (depends on tool)  
**Grading query:** 10-20s (LLM analysis)  
**LMS sync:** 1-3s (API calls)

## Monitoring

**Key Metrics:**
- Request count by role
- Intent classification accuracy
- Access denial rate
- Agent response times
- Error rates by agent

**Logging:**
```python
supervisor.query() logs:
- User role
- Classified intent
- Access decision
- Agent selected
- Response time
```

---

**Built with LangGraph supervisor pattern for scalable multi-agent routing with role-based access control.**

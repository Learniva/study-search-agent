# AI Grading Agent - Architecture

Intelligent grading assistant with multi-agent routing, RAG rubrics, and role-based access control.

## System Architecture

```
User → CLI/API → Supervisor (LangGraph) → [Study | Grading]
                       ↓
                [Classify → Access → Route]
                       ↓
              Grading Agent (LangGraph) → Tools → LLM
                       ↓
              [Route → Execute → Save → Result]
                       ↓           ↓        ↓
                   Essay      Rubric    PostgreSQL
                   Code       RAG       Persistence
                   MCQ
```

## Components

### 1. Entry Points

**`main.py` (CLI):** `--role`, `--user-id`, interactive/single-query  
**`api/main.py` (FastAPI):** REST endpoints, JWT auth, role validation

### 2. Supervisor Agent (Router)

**Pattern:** Supervisor (Centralized Control)  
**Framework:** LangGraph conditional routing  
**State:** SupervisorState (question, user_role, intent, access_denied, agent_result)  
**Nodes:** classify_intent, check_access, study_agent, grading_agent, deny_access  
**Flow:** Classify → Check access → Route → Execute

**Access Control:**
- Student: Study only
- Teacher/Professor/Admin: Study + Grading

### 3. Supervisor Flow

```
Question → Classify (STUDY/GRADE) → Check Role
              ↓                          ↓
         [Study Agent]            [Grading Agent]
                                  (if authorized)
```

### 4. Grading Agent

**Framework:** LangGraph tool routing  
**State:** GradingAgentState (question, tool_used, result, messages, db_context)  
**Nodes:** route_task, grade_essay, review_code, grade_mcq, evaluate_rubric, generate_feedback  
**Flow:** Route → Execute → Save DB → Structured feedback  
**Prompt:** Academic grader (fair, constructive, detailed)

### 5. Grading Tools

**grade_essay:** RAG rubric + thesis/evidence/organization/grammar  
**review_code:** Correctness/efficiency/style + bug detection  
**grade_mcq:** Auto-scoring + explanations  
**evaluate_with_rubric:** Custom rubric evaluation  
**generate_feedback:** Constructive improvement suggestions  
**answer_comparator:** Student vs model answer

### 6. RAG (Rubric Retrieval)

```
Load: JSON rubrics → rubrics/
Embed: GoogleGenerativeAIEmbeddings (text-embedding-004)
Store: ChromaDB (.chroma_rubrics/)
Retrieve: Semantic search (k=1)
Augment: Inject into context
Generate: LLM grades with rubric
```

**Features:**
- Auto-creates defaults (essay, code)
- Semantic matching ("programming" → code rubric)
- Rubric snapshots in sessions
- Custom professor rubrics

### 7. File Processing

```
Detect: PDF/DOCX/TXT/CSV/JSON/PY
Load: LangChain loaders
Extract: Content + metadata
Return: Structured data
```

**Loaders:** PyPDFLoader, Docx2txtLoader, TextLoader, CSVLoader, JSONLoader

### 8. Database (PostgreSQL)

```
Grading → SQLAlchemy → PostgreSQL
    ↓
[users | grading_sessions | rubric_templates]
    ↓
Persistence + query history
```

**Tables:**
- **users:** Accounts (role, email, LMS)
- **grading_sessions:** History (score, feedback, rubric, time)
- **rubric_templates:** Custom rubrics (criteria, weights)

**Features:** Auto-save with `--user-id`, history queries, audit logging

### 9. Grading Flow

```
Submit → Supervisor (role check) → Grading Agent
              ↓
    Route tool (essay/code/mcq)
              ↓
    Retrieve rubric + Process file
              ↓
    LLM generates feedback
              ↓
    Save PostgreSQL → Return result
```

## Tech Stack

**Framework:**  
- LangGraph: Multi-agent, state, RBAC  
- LangChain: Tools, RAG, embeddings

**LLM:** Gemini 2.5 Flash (temp=0.3)  
**Embeddings:** Gemini text-embedding-004  
**Vector DB:** ChromaDB (.chroma_rubrics/)  
**Database:** PostgreSQL + SQLAlchemy + Alembic  
**API:** FastAPI (JWT auth)  
**File Proc:** PyPDF, python-docx, docx2txt

## Configuration

```bash
# .env
GOOGLE_API_KEY=xxx            # Required (Gemini)
DATABASE_URL=postgresql://... # Required (persistence)
TAVILY_API_KEY=xxx            # Optional (study features)
ELEVEN_API_KEY=xxx            # Optional (animations)
```

**Runtime:**
- Grading temp: 0.3
- Rubric k: 1
- DB pool: 10 conn, 20 overflow
- Auto-save: with `--user-id`

## Key Patterns

**Supervisor Pattern:** Central router → specialized agents  
**RBAC:** LangGraph conditional edges  
**Multi-Agent:** State machines + routing  
**RAG Rubrics:** Semantic template search  
**DB Persistence:** Auto-save sessions  
**Tool Routing:** LLM-based selection  
**Structured Output:** JSON (score, criteria, suggestions)

## Extension Points

**Add tool:** `tools/grading_tools.py` → `get_all_grading_tools()`  
**Add rubric:** Create JSON in `rubrics/` (auto-indexed)  
**Add format:** Add loader in `submission_processor.py`  
**Add model:** `database/models.py` + Alembic migration  
**Add role:** Update `SupervisorAgent._check_access_node()`  
**Customize:** Modify `GRADING_AGENT_SYSTEM_PROMPT`

## Security

⚠️ **Role enforcement:** LangGraph routing blocks students  
⚠️ **API auth:** JWT required  
⚠️ **DB access:** User isolation via foreign keys  
⚠️ **File uploads:** Known formats only  
✓ **API keys:** In `.env` (gitignored)  
✓ **SQL injection:** SQLAlchemy ORM protection

## Access Control

| Role      | Study | Grading | DB Write |
|-----------|-------|---------|----------|
| Student   | ✅    | ❌      | ❌       |
| Teacher   | ✅    | ✅      | ✅       |
| Professor | ✅    | ✅      | ✅       |
| Admin     | ✅    | ✅      | ✅       |

## Performance

**Intent classification:** <1s  
**Rubric retrieval:** <0.2s  
**Essay grading:** 10-20s  
**Code review:** 8-15s  
**MCQ grading:** 3-8s  
**DB save:** <0.5s  
**File processing:** 1-5s

## Database Schema

```
users
├── id (UUID, PK)
├── user_id (String, unique)
├── role (student/teacher/admin)
└── email, name, timestamps

grading_sessions
├── id (UUID, PK)
├── professor_id (FK → users)
├── student_id, student_name
├── grading_type (essay/code/mcq)
├── submission (JSONB)
├── score, max_score, grade_letter
├── ai_feedback (JSONB)
├── rubric_id (FK → rubric_templates)
└── processing_time_seconds, timestamps

rubric_templates
├── id (UUID, PK)
├── professor_id (FK → users)
├── name, rubric_type
├── criteria (JSONB)
├── max_score, is_public
└── timestamps
```

## CLI Examples

```bash
# Student (study only)
python main.py --role student

# Professor (grading enabled)
python main.py --role professor --user-id prof123

# Grade with persistence
python main.py --role professor --user-id prof123 \
  --question "Grade: $(cat test_submissions/essay.txt)"

# View history
python setup_database.py --info
```

## API Endpoints

```
POST /query              # General (role-routed)
POST /grade              # Direct grading (JWT + teacher)
GET  /grading-history    # Professor sessions
POST /rubrics            # Create rubric
GET  /rubrics            # List rubrics
GET  /health             # System health
```

## Output Format

```json
{
  "score": 85,
  "max_score": 100,
  "grade": "B",
  "criteria_breakdown": {
    "thesis": {"score": 90, "feedback": "..."},
    "evidence": {"score": 85, "feedback": "..."}
  },
  "strengths": ["...", "..."],
  "improvements": ["...", "..."],
  "suggestions": ["...", "..."],
  "overall_feedback": "...",
  "ai_confidence": 95,
  "processing_time": 12.5,
  "rubric_used": "Essay General Rubric"
}
```

---

**Built with LangGraph multi-agent routing, LangChain RAG, and PostgreSQL persistence.**

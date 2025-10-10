"""
System-wide constants for the Multi-Agent Study & Grading System.

Centralizes all magic numbers, regex patterns, and configuration values
for easier maintenance and consistency across the codebase.
"""

# =============================================================================
# CACHE CONFIGURATION
# =============================================================================

# Default cache time-to-live in seconds (1 hour)
DEFAULT_CACHE_TTL = 3600

# Maximum cache history entries to keep
MAX_CACHE_HISTORY = 100

# =============================================================================
# CONTEXT MANAGEMENT
# =============================================================================

# Maximum tokens for smart context extraction
MAX_CONTEXT_TOKENS = 500

# Maximum number of messages to include in context
MAX_CONTEXT_MESSAGES = 2

# Rough token estimation ratio (characters per token)
CHARS_PER_TOKEN = 4

# =============================================================================
# ROUTING CONFIGURATION
# =============================================================================

# Similarity threshold for query matching
QUERY_SIMILARITY_THRESHOLD = 0.6

# Number of recent routing decisions to check for patterns
ROUTING_HISTORY_LOOKBACK = 20

# Confidence threshold for ML-based routing
ML_ROUTING_CONFIDENCE_THRESHOLD = 0.7

# Confidence threshold for performance-based routing
PERF_ROUTING_CONFIDENCE_THRESHOLD = 0.7

# =============================================================================
# AGENT CONFIGURATION
# =============================================================================

# Maximum iterations for agent workflows
MAX_AGENT_ITERATIONS = 5

# Maximum iterations for grading workflows
MAX_GRADING_ITERATIONS = 3

# =============================================================================
# WEB SEARCH PATTERNS
# =============================================================================

# Patterns for detecting real-time queries
REALTIME_QUERY_PATTERNS = [
    r'\b(current|now|right now|today)\b.*\b(time|date|weather|temperature|stock|price)\b',
    r'\b(what time is it|what\'s the time)\b',
    r'\b(time in|time at)\b.*\bnow\b',
    r'\b(current (date|time|weather|temperature))\b',
    r'\b(today\'s (date|weather|temperature))\b',
]

# Patterns for vague follow-up questions
VAGUE_QUESTION_PATTERNS = [
    'how does it work', 'tell me more', 'what about', 'how about',
    'explain that', 'how', 'why', 'when', 'where', 'can you', 'who else',
    'what else', 'anything else', 'more details', 'tell me about',
    'who is', 'what is', 'where is', 'when is', 'which is',
    'who are', 'what are', 'where are', 'who founded', 'who created',
    'who made', 'who built', 'who started', 'who owns'
]

# Pronouns that indicate follow-up questions
FOLLOW_UP_PRONOUNS = ['it', 'this', 'that', 'they', 'them', 'else', 'there']

# Generic subjects that need context
GENERIC_SUBJECTS = [
    'the founder', 'the creator', 'the ceo', 'the owner', 'the president',
    'the leader', 'the person', 'the company', 'the organization'
]

# Maximum words in short question
MAX_SHORT_QUESTION_WORDS = 6

# =============================================================================
# QUERY ENRICHMENT
# =============================================================================

# Query enrichment system prompt
QUERY_ENRICHMENT_SYSTEM_PROMPT = """You are a query expansion assistant. Given conversation history and a follow-up question, expand the question into a complete, standalone search query.

Rules:
1. Identify the main topic/subject from the most recent conversation
2. Replace pronouns (it, this, that, they, them) with the actual subject
3. Add the missing subject to generic questions (e.g., "Who is the founder" → "Who is the founder of [topic]")
4. Expand vague questions (who else?, what else?) to include the topic
5. Keep the query concise and specific
6. Provide ONLY the expanded search query (no explanations)

Examples:
- History: "User: What is Code Savanna all about?", Follow-up: "Who is the founder" → "Who is the founder of Code Savanna?"
- History: "User: Tell me about Tesla", Follow-up: "Who is the CEO" → "Who is the CEO of Tesla?"
- History: "User: Who is the founder of Code Savanna?", Follow-up: "Who else?" → "Who are the other founders of Code Savanna?"
- History: "User: What is LangChain?", Follow-up: "How does it work?" → "How does LangChain work?"
- History: "User: Tell me about Python", Follow-up: "What are the benefits" → "What are the benefits of Python?"
- History: "User: Explain quantum computing", Follow-up: "Where is it used" → "Where is quantum computing used?"""

# =============================================================================
# WEB SEARCH SYNTHESIS
# =============================================================================

# Web search synthesis prompt template
WEB_SEARCH_SYNTHESIS_PROMPT = """Based on the search results below, provide a clear, comprehensive answer to the question.

Original Question: {original_question}
Search Query Used: {search_query}

Search Results:
{raw_results}

INSTRUCTIONS:
1. Synthesize ALL relevant information from the search results into a coherent answer
2. Include ALL important names, dates, facts, and details mentioned in the sources
3. Answer the ORIGINAL question comprehensively using the search results
4. If multiple people, items, or facts are mentioned, list them all
5. Structure the answer clearly (use bullet points or sections if needed)
6. Be thorough and complete - don't omit important information
7. MUST end with a "Sources:" section listing ALL URLs referenced

FORMAT YOUR RESPONSE AS:
[Your comprehensive answer here]

Sources:
- [URL 1]
- [URL 2]
- [URL 3]"""

# =============================================================================
# DOCUMENT QA CONFIGURATION
# =============================================================================

# Number of documents to retrieve for RAG
DOCUMENT_RETRIEVAL_K = 40

# Number of candidate documents to consider before MMR selection
DOCUMENT_FETCH_K = 100

# MMR lambda parameter (0 = max diversity, 1 = max relevance)
DOCUMENT_MMR_LAMBDA = 0.7

# Minimum chunk size for document processing
MIN_CHUNK_SIZE = 100

# Default chunk size for text splitting
DEFAULT_CHUNK_SIZE = 800

# Chunk overlap for context preservation
DEFAULT_CHUNK_OVERLAP = 200

# =============================================================================
# GRADING CONFIGURATION
# =============================================================================

# Phrases indicating failed document retrieval
DOCUMENT_QA_FAILURE_PHRASES = [
    "no relevant content found",
    "no documents have been loaded",
    "no information",
    "not found in the documents"
]

# Grading quality issue patterns
GRADING_ERROR_INDICATORS = ["error", "failed", "not available", "could not", "no results"]
GRADING_UNCERTAINTY_INDICATORS = ["i don't know", "i'm not sure", "unclear", "cannot determine"]

# Minimum response length for quality check
MIN_RESPONSE_LENGTH = 50

# Minimum term overlap for response relevance check
MIN_TERM_OVERLAP_RATIO = 0.2

# Confidence thresholds for grading
GRADING_HIGH_CONFIDENCE = 0.8
GRADING_MEDIUM_CONFIDENCE = 0.5
GRADING_LOW_CONFIDENCE = 0.3

# =============================================================================
# PERFORMANCE MONITORING
# =============================================================================

# Maximum response time before warning (seconds)
MAX_RESPONSE_TIME_WARNING = 10.0

# Cache hit rate threshold for optimization alert
MIN_CACHE_HIT_RATE = 0.3

# =============================================================================
# DISPLAY FORMATTING
# =============================================================================

# Separator line length
SEPARATOR_LENGTH = 70

# Maximum preview length for text
MAX_PREVIEW_LENGTH = 60

# Maximum lines for history display
MAX_HISTORY_DISPLAY = 10

# =============================================================================
# FILE PROCESSING
# =============================================================================

# Supported file extensions
SUPPORTED_DOCUMENT_EXTENSIONS = ['.pdf', '.docx', '.txt']

# Minimum page text length to include
MIN_PAGE_TEXT_LENGTH = 50

# Chapter detection patterns
CHAPTER_PATTERNS = [
    r'Chapter\s+(\d+)',
    r'CHAPTER\s+(\d+)',
    r'^(\d+)\.\s+[A-Z]',  # "12. Generative Deep Learning"
]

# =============================================================================
# ERROR MESSAGES
# =============================================================================

# Common error messages
ERROR_NO_DOCUMENTS = "⚠️  No documents have been loaded. Please upload and index documents first."
ERROR_NO_API_KEY = "❌ API key not found. Please check your environment configuration."
ERROR_TOOL_NOT_AVAILABLE = "⚠️  Required tool not available. Please check installation."
ERROR_CACHE_FAILURE = "⚠️  Cache operation failed. Continuing without cache."
ERROR_ROUTING_FAILURE = "❌ Routing failed. Falling back to default behavior."

# =============================================================================
# SUCCESS MESSAGES
# =============================================================================

SUCCESS_CACHE_HIT = "⚡ Cache HIT! (saved API calls)"
SUCCESS_PATTERN_ROUTING = "⚡ Pattern-based routing"
SUCCESS_ML_ROUTING = "🎯 ML prediction"
SUCCESS_PERF_ROUTING = "🎯 Performance routing"

# =============================================================================
# LLM CONFIGURATION
# =============================================================================

# Default models
DEFAULT_LLM_MODEL = "gemini-2.5-flash"
FALLBACK_LLM_MODEL = "gemini-2.5-pro"
DEFAULT_EMBEDDING_MODEL = "models/embedding-001"

# Temperature settings by use case
TEMPERATURE_STUDY = 0.7      # Creative, conversational
TEMPERATURE_GRADING = 0.3    # Precise, consistent
TEMPERATURE_ROUTING = 0.0    # Deterministic
TEMPERATURE_CREATIVE = 0.9   # Maximum creativity
TEMPERATURE_PRECISE = 0.0    # Exact answers

# =============================================================================
# DATABASE CONFIGURATION
# =============================================================================

# ChromaDB collection names
CHROMA_COLLECTION_DOCS = "document_qa"
CHROMA_COLLECTION_RUBRICS = "rubrics"

# Vector database persist directories
CHROMA_PERSIST_DIR_DOCS = ".chroma_docs"
CHROMA_PERSIST_DIR_RUBRICS = ".chroma_rubrics"

# =============================================================================
# ROLE-BASED ACCESS CONTROL
# =============================================================================

# User roles
ROLE_STUDENT = "STUDENT"
ROLE_TEACHER = "TEACHER"
ROLE_PROFESSOR = "PROFESSOR"
ROLE_INSTRUCTOR = "INSTRUCTOR"
ROLE_ADMIN = "ADMIN"

# Roles with grading access
GRADING_ROLES = [ROLE_TEACHER, ROLE_PROFESSOR, ROLE_INSTRUCTOR, ROLE_ADMIN]

# Intent types
INTENT_STUDY = "STUDY"
INTENT_GRADE = "GRADE"

# =============================================================================
# VALIDATION CONSTANTS
# =============================================================================

# Maximum score validation
MAX_SCORE_LIMIT = 100
MIN_SCORE_LIMIT = 0

# Grade letters
GRADE_LETTERS = {
    90: "A",
    80: "B",
    70: "C",
    60: "D",
    0: "F"
}


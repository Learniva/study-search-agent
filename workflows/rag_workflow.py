"""
Phase 2.2: RAG Workflow with Self-Correction Loop

Implements the agentic RAG workflow as a LangGraph sub-graph:
  retrieve_context → grade_retrieval → conditional_edge → refine_query (loop back)

This workflow ensures retrieved context is high-quality before use.
"""

import time
from typing import TypedDict, Optional, List, Dict, Any, Literal, Annotated
from langgraph.graph import StateGraph, END
from langgraph.graph.message import add_messages
from langchain_core.messages import HumanMessage, AIMessage, SystemMessage

# Database imports for logging
try:
    from database.database import get_session
    from database.rag_operations import log_rag_query, create_grade_exception
    DATABASE_AVAILABLE = True
except ImportError:
    DATABASE_AVAILABLE = False


class RAGState(TypedDict):
    """
    State for the RAG sub-graph workflow.
    
    Tracks retrieval decision, context quality, and refinement loops.
    """
    # Input
    query: str
    user_id: Optional[str]
    messages: Annotated[List[Any], add_messages]
    
    # Retrieval decision (Step 2.1: should_retrieve)
    should_retrieve: bool
    retrieval_reason: str
    retrieval_confidence: float
    
    # Retrieved context (Step 2.1: retrieve_context)
    retrieved_context: Optional[str]
    retrieved_doc_ids: List[str]
    retrieval_time_ms: float
    
    # Context grading (Step 2.2: grade_retrieval)
    context_quality_score: float  # 0-1 score
    context_issues: List[str]  # Problems detected
    context_relevant: bool  # Is context relevant?
    
    # Query refinement (Step 2.2: refine_query)
    refinement_needed: bool
    refined_query: Optional[str]
    refinement_iteration: int
    max_refinement_iterations: int
    
    # Final output
    final_context: Optional[str]
    context_used: bool
    rag_decision_log_id: Optional[str]
    
    # Error tracking
    errors: List[str]


class RAGWorkflow:
    """
    Agentic RAG Workflow with self-correction loop.
    
    Phase 2.2 Implementation:
    1. Decide if retrieval is needed (adaptive)
    2. Retrieve context from L2 Vector Store
    3. Grade context quality (self-correction)
    4. Refine query if context is poor (loop back)
    5. Return high-quality context or None
    """
    
    def __init__(self, llm, vector_store_tool=None, learning_store_tool=None):
        """
        Initialize RAG workflow.
        
        Args:
            llm: Language model for decision-making and grading
            vector_store_tool: Tool for L2 Vector Store retrieval
            learning_store_tool: Tool for L3 Learning Store queries
        """
        self.llm = llm
        self.vector_store_tool = vector_store_tool
        self.learning_store_tool = learning_store_tool
        
        # Build the RAG sub-graph
        self.graph = self._build_rag_graph()
        self.app = self.graph.compile()
    
    def _build_rag_graph(self) -> StateGraph:
        """
        Build the RAG workflow as a LangGraph sub-graph.
        
        Workflow:
        START → should_retrieve_node → [retrieve | skip]
        retrieve → grade_retrieval_node → [accept | refine]
        refine → refine_query_node → retrieve (loop back)
        accept/skip → END
        """
        workflow = StateGraph(RAGState)
        
        # Add nodes
        workflow.add_node("should_retrieve", self._should_retrieve_node)
        workflow.add_node("retrieve_context", self._retrieve_context_node)
        workflow.add_node("grade_retrieval", self._grade_retrieval_node)
        workflow.add_node("refine_query", self._refine_query_node)
        workflow.add_node("accept_context", self._accept_context_node)
        workflow.add_node("skip_retrieval", self._skip_retrieval_node)
        
        # Set entry point
        workflow.set_entry_point("should_retrieve")
        
        # should_retrieve → [retrieve | skip]
        def route_retrieval_decision(state: RAGState) -> Literal["retrieve", "skip"]:
            return "retrieve" if state["should_retrieve"] else "skip"
        
        workflow.add_conditional_edges(
            "should_retrieve",
            route_retrieval_decision,
            {
                "retrieve": "retrieve_context",
                "skip": "skip_retrieval"
            }
        )
        
        # retrieve_context → grade_retrieval
        workflow.add_edge("retrieve_context", "grade_retrieval")
        
        # grade_retrieval → [accept | refine]
        def route_grading_decision(state: RAGState) -> Literal["accept", "refine", "skip"]:
            if not state.get("retrieved_context"):
                return "skip"  # No context retrieved
            elif state["context_relevant"] and state["context_quality_score"] >= 0.6:
                return "accept"  # Good quality
            elif state["refinement_iteration"] < state["max_refinement_iterations"]:
                return "refine"  # Try to improve
            else:
                return "accept"  # Max iterations reached, accept what we have
        
        workflow.add_conditional_edges(
            "grade_retrieval",
            route_grading_decision,
            {
                "accept": "accept_context",
                "refine": "refine_query",
                "skip": "skip_retrieval"
            }
        )
        
        # refine_query → retrieve_context (loop back)
        workflow.add_edge("refine_query", "retrieve_context")
        
        # Terminal nodes
        workflow.add_edge("accept_context", END)
        workflow.add_edge("skip_retrieval", END)
        
        return workflow
    
    def _should_retrieve_node(self, state: RAGState) -> RAGState:
        """
        Node: Decide if context retrieval is needed (Agentic RAG).
        
        Uses LLM to analyze query and determine if RAG would be beneficial.
        Avoids unnecessary retrieval for simple queries.
        """
        query = state["query"]
        query_lower = query.lower()
        
        print("\n🤔 Analyzing if retrieval is needed...")
        
        # Fast path: Skip for obvious cases
        greetings = ["hi", "hello", "hey", "thanks", "thank you", "bye", "goodbye"]
        if query_lower.strip() in greetings:
            print("   ⏭️  Skipping: Greeting detected")
            return {
                **state,
                "should_retrieve": False,
                "retrieval_reason": "Greeting - no context needed",
                "retrieval_confidence": 1.0
            }
        
        # Fast path: Simple calculations
        if len(query.split()) <= 4 and any(op in query for op in ['+', '-', '*', '/', '**']):
            print("   ⏭️  Skipping: Simple calculation")
            return {
                **state,
                "should_retrieve": False,
                "retrieval_reason": "Simple calculation - no retrieval needed",
                "retrieval_confidence": 1.0
            }
        
        # Check for document references
        doc_indicators = [
            "document", "notes", "file", "pdf", "chapter", "section",
            "page", "uploaded", "my notes", "the document", "my files"
        ]
        
        has_doc_reference = any(indicator in query_lower for indicator in doc_indicators)
        
        if has_doc_reference:
            print("   📚 Retrieving: Document reference detected")
            return {
                **state,
                "should_retrieve": True,
                "retrieval_reason": "Document reference detected",
                "retrieval_confidence": 0.9
            }
        
        # Use LLM for ambiguous cases
        decision_prompt = """Analyze if this query would benefit from document retrieval.

Query: {query}

Consider:
1. Does it reference specific documents, notes, or files?
2. Is it a factual question that might be in documents?
3. Or is it a greeting, calculation, or general question?

Respond with ONLY: RETRIEVE or SKIP
Then on a new line, give a one-sentence reason."""
        
        try:
            response = self.llm.invoke([
                HumanMessage(content=decision_prompt.format(query=query))
            ])
            
            decision_text = response.content.strip()
            lines = decision_text.split('\n', 1)
            decision = lines[0].strip().upper()
            reason = lines[1].strip() if len(lines) > 1 else "LLM decision"
            
            should_retrieve = "RETRIEVE" in decision
            
            if should_retrieve:
                print(f"   📚 Retrieving: {reason}")
            else:
                print(f"   ⏭️  Skipping: {reason}")
            
            return {
                **state,
                "should_retrieve": should_retrieve,
                "retrieval_reason": reason,
                "retrieval_confidence": 0.7  # Medium confidence for LLM decision
            }
            
        except Exception as e:
            print(f"   ⚠️  Error in decision: {e}, defaulting to SKIP")
            return {
                **state,
                "should_retrieve": False,
                "retrieval_reason": f"Error: {str(e)}",
                "retrieval_confidence": 0.5
            }
    
    def _retrieve_context_node(self, state: RAGState) -> RAGState:
        """
        Node: Retrieve context from L2 Vector Store.
        
        Performs semantic search using the query (or refined query).
        """
        query = state.get("refined_query") or state["query"]
        
        print(f"\n📚 Retrieving context for: '{query}'")
        
        start_time = time.time()
        
        try:
            if self.vector_store_tool:
                # Use the vector store tool
                result = self.vector_store_tool.func(
                    query=query,
                    limit=5,
                    user_id=state.get("user_id")
                )
                
                retrieval_time_ms = (time.time() - start_time) * 1000
                
                # Check if retrieval was successful
                if "No relevant documents found" in result or "not available" in result:
                    print("   ⚠️  No relevant documents found")
                    return {
                        **state,
                        "retrieved_context": None,
                        "retrieved_doc_ids": [],
                        "retrieval_time_ms": retrieval_time_ms,
                        "errors": state.get("errors", []) + ["No documents found"]
                    }
                
                print(f"   ✅ Retrieved context ({len(result)} chars) in {retrieval_time_ms:.1f}ms")
                
                return {
                    **state,
                    "retrieved_context": result,
                    "retrieved_doc_ids": [],  # Would extract IDs from result in production
                    "retrieval_time_ms": retrieval_time_ms
                }
            else:
                print("   ⚠️  Vector store tool not available")
                return {
                    **state,
                    "retrieved_context": None,
                    "retrieved_doc_ids": [],
                    "retrieval_time_ms": 0.0,
                    "errors": state.get("errors", []) + ["Vector store not available"]
                }
                
        except Exception as e:
            print(f"   ❌ Retrieval error: {e}")
            return {
                **state,
                "retrieved_context": None,
                "retrieved_doc_ids": [],
                "retrieval_time_ms": (time.time() - start_time) * 1000,
                "errors": state.get("errors", []) + [f"Retrieval error: {str(e)}"]
            }
    
    def _grade_retrieval_node(self, state: RAGState) -> RAGState:
        """
        Node: Grade the quality of retrieved context (Self-Correction).
        
        This is the core of the self-correction loop. Evaluates:
        - Relevance to query
        - Quality of content
        - Completeness
        
        If quality is low, triggers query refinement.
        """
        retrieved_context = state.get("retrieved_context")
        query = state.get("refined_query") or state["query"]
        
        print("\n🔍 Grading retrieved context quality...")
        
        if not retrieved_context:
            print("   ⚠️  No context to grade")
            return {
                **state,
                "context_quality_score": 0.0,
                "context_issues": ["No context retrieved"],
                "context_relevant": False,
                "refinement_needed": False
            }
        
        # Use LLM to grade context quality
        grading_prompt = """Grade the quality and relevance of this retrieved context for answering the query.

Query: {query}

Retrieved Context:
{context}

Evaluate:
1. Relevance: Does it relate to the query? (0-1 score)
2. Completeness: Does it provide enough information? (0-1 score)
3. Quality: Is it clear and useful? (0-1 score)

Respond in this format:
RELEVANCE: <score>
COMPLETENESS: <score>
QUALITY: <score>
ISSUES: <list any problems, or "none">
VERDICT: <ACCEPT or REFINE>"""
        
        try:
            response = self.llm.invoke([
                HumanMessage(content=grading_prompt.format(
                    query=query,
                    context=retrieved_context[:1000]  # Limit context length for grading
                ))
            ])
            
            grading_text = response.content.strip()
            
            # Parse scores
            relevance = 0.5
            completeness = 0.5
            quality_score = 0.5
            issues = []
            verdict = "ACCEPT"
            
            for line in grading_text.split('\n'):
                line = line.strip()
                if line.startswith("RELEVANCE:"):
                    try:
                        relevance = float(line.split(':')[1].strip())
                    except:
                        pass
                elif line.startswith("COMPLETENESS:"):
                    try:
                        completeness = float(line.split(':')[1].strip())
                    except:
                        pass
                elif line.startswith("QUALITY:"):
                    try:
                        quality_score = float(line.split(':')[1].strip())
                    except:
                        pass
                elif line.startswith("ISSUES:"):
                    issue_text = line.split(':', 1)[1].strip()
                    if issue_text.lower() != "none":
                        issues = [issue_text]
                elif line.startswith("VERDICT:"):
                    verdict = line.split(':')[1].strip().upper()
            
            # Overall quality score (average of components)
            overall_quality = (relevance + completeness + quality_score) / 3.0
            
            context_relevant = relevance >= 0.5
            refinement_needed = verdict == "REFINE" or overall_quality < 0.6
            
            print(f"   Quality Score: {overall_quality:.2f}")
            print(f"   Relevance: {relevance:.2f} | Completeness: {completeness:.2f} | Quality: {quality_score:.2f}")
            if issues:
                print(f"   Issues: {', '.join(issues)}")
            print(f"   Verdict: {'✅ Accept' if not refinement_needed else '🔄 Needs refinement'}")
            
            # Log to L3 if quality is poor
            if DATABASE_AVAILABLE and overall_quality < 0.5:
                try:
                    db = get_session()
                    try:
                        create_grade_exception(
                            db=db,
                            exception_type="rag_failure",
                            user_id=state.get("user_id", "unknown"),
                            query=query,
                            ai_decision={"quality_score": overall_quality},
                            correct_decision={"refinement_needed": True},
                            retrieved_context={"context": retrieved_context[:500]},
                            context_quality_score=overall_quality,
                            error_category="low_quality_retrieval",
                            error_description=f"Retrieved context quality below threshold: {overall_quality:.2f}"
                        )
                        print("   📝 Logged to L3 Learning Store")
                    finally:
                        db.close()
                except Exception as e:
                    print(f"   ⚠️  Failed to log to L3: {e}")
            
            return {
                **state,
                "context_quality_score": overall_quality,
                "context_issues": issues,
                "context_relevant": context_relevant,
                "refinement_needed": refinement_needed
            }
            
        except Exception as e:
            print(f"   ❌ Grading error: {e}")
            # Default to accepting context on error
            return {
                **state,
                "context_quality_score": 0.5,
                "context_issues": [f"Grading error: {str(e)}"],
                "context_relevant": True,
                "refinement_needed": False
            }
    
    def _refine_query_node(self, state: RAGState) -> RAGState:
        """
        Node: Refine the query to improve retrieval quality (Self-Correction Loop).
        
        Uses LLM to reformulate the query based on context quality issues.
        Loops back to retrieve_context with the refined query.
        """
        original_query = state["query"]
        current_query = state.get("refined_query") or original_query
        issues = state.get("context_issues", [])
        iteration = state.get("refinement_iteration", 0)
        
        print(f"\n🔄 Refining query (iteration {iteration + 1})...")
        
        refinement_prompt = """The retrieved context was not satisfactory. Refine the query to improve results.

Original Query: {original_query}
Current Query: {current_query}

Issues with Retrieved Context:
{issues}

Generate a refined search query that:
1. Is more specific and targeted
2. Uses different keywords or phrasing
3. Addresses the context quality issues
4. Stays true to the user's intent

Respond with ONLY the refined query (no explanations)."""
        
        try:
            response = self.llm.invoke([
                HumanMessage(content=refinement_prompt.format(
                    original_query=original_query,
                    current_query=current_query,
                    issues='\n'.join(issues) if issues else "Context quality too low"
                ))
            ])
            
            refined_query = response.content.strip()
            
            # Remove quotes if present
            refined_query = refined_query.strip('"\'')
            
            print(f"   Original: '{current_query}'")
            print(f"   Refined: '{refined_query}'")
            
            return {
                **state,
                "refined_query": refined_query,
                "refinement_iteration": iteration + 1
            }
            
        except Exception as e:
            print(f"   ❌ Refinement error: {e}")
            # Return original query on error
            return {
                **state,
                "refined_query": current_query,
                "refinement_iteration": iteration + 1
            }
    
    def _accept_context_node(self, state: RAGState) -> RAGState:
        """
        Node: Accept the retrieved context as final.
        
        Logs the successful retrieval to RAG query logs.
        """
        print("\n✅ Context accepted - high quality")
        
        # Log to database
        if DATABASE_AVAILABLE:
            try:
                db = get_session()
                try:
                    log_rag_query(
                        db=db,
                        user_id=state.get("user_id", "unknown"),
                        query=state["query"],
                        query_type="study",
                        should_retrieve=state["should_retrieve"],
                        retrieval_reason=state.get("retrieval_reason", ""),
                        retrieved_count=len(state.get("retrieved_doc_ids", [])),
                        context_quality_score=state.get("context_quality_score", 0.0),
                        retrieval_time_ms=state.get("retrieval_time_ms", 0.0),
                        context_used=True
                    )
                finally:
                    db.close()
            except Exception as e:
                print(f"   ⚠️  Failed to log: {e}")
        
        return {
            **state,
            "final_context": state.get("retrieved_context"),
            "context_used": True
        }
    
    def _skip_retrieval_node(self, state: RAGState) -> RAGState:
        """
        Node: Skip retrieval (query doesn't need context).
        
        Logs the decision to skip.
        """
        print("\n⏭️  Retrieval skipped - not needed for this query")
        
        # Log to database
        if DATABASE_AVAILABLE:
            try:
                db = get_session()
                try:
                    log_rag_query(
                        db=db,
                        user_id=state.get("user_id", "unknown"),
                        query=state["query"],
                        query_type="study",
                        should_retrieve=False,
                        retrieval_reason=state.get("retrieval_reason", "Not needed"),
                        retrieved_count=0,
                        context_used=False
                    )
                finally:
                    db.close()
            except Exception as e:
                print(f"   ⚠️  Failed to log: {e}")
        
        return {
            **state,
            "final_context": None,
            "context_used": False
        }
    
    def execute(
        self,
        query: str,
        user_id: Optional[str] = None,
        messages: Optional[List[Any]] = None
    ) -> Dict[str, Any]:
        """
        Execute the RAG workflow for a query.
        
        Args:
            query: The user's query
            user_id: Optional user ID for logging
            messages: Optional conversation history
        
        Returns:
            Dictionary with:
            - final_context: Retrieved and graded context (or None)
            - context_used: Whether context was retrieved
            - context_quality_score: Quality score (0-1)
            - should_retrieve: Whether retrieval was attempted
        """
        initial_state = {
            "query": query,
            "user_id": user_id,
            "messages": messages or [],
            "should_retrieve": False,
            "retrieval_reason": "",
            "retrieval_confidence": 0.0,
            "retrieved_context": None,
            "retrieved_doc_ids": [],
            "retrieval_time_ms": 0.0,
            "context_quality_score": 0.0,
            "context_issues": [],
            "context_relevant": False,
            "refinement_needed": False,
            "refined_query": None,
            "refinement_iteration": 0,
            "max_refinement_iterations": 2,  # Max 2 refinement loops
            "final_context": None,
            "context_used": False,
            "rag_decision_log_id": None,
            "errors": []
        }
        
        try:
            result = self.app.invoke(initial_state)
            return result
        except Exception as e:
            print(f"\n❌ RAG workflow error: {e}")
            return {
                **initial_state,
                "errors": [f"Workflow error: {str(e)}"]
            }


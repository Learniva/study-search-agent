"""
Study and Search Agent - LangGraph Implementation
A dynamic agent that uses LangGraph for:
- Intelligent tool routing with fallback logic
- Conversation memory and history tracking
- Multi-step workflows with state management
- Conditional branching and complex routing
"""

import os
import re
import time
from typing import Optional, TypedDict, Annotated, Literal, List, Dict, Any
from dotenv import load_dotenv

from langgraph.graph import StateGraph, END
from langgraph.graph.message import add_messages
from langgraph.checkpoint.memory import MemorySaver
from langchain_core.messages import HumanMessage, AIMessage, SystemMessage

from tools.base import get_all_tools
from utils.llm import initialize_llm
from utils.cache import ResultCache
from utils.context import get_smart_context
from utils.routing import fast_study_route, calculate_text_similarity
from utils.query_enrichment import (
    detect_realtime_query,
    needs_query_enrichment,
    enrich_query_with_context,
    format_realtime_warning
)
from utils.constants import (
    DEFAULT_CACHE_TTL,
    MAX_AGENT_ITERATIONS,
    MAX_CONTEXT_TOKENS,
    DOCUMENT_QA_FAILURE_PHRASES,
    WEB_SEARCH_SYNTHESIS_PROMPT
)

# ML/Adaptation features (optional - graceful fallback if not available)
try:
    from utils.ml import update_user_profile, get_user_preferences
    from utils.ml import learn_from_query, predict_best_tool
    ML_FEATURES_AVAILABLE = True
    print("✅ ML/Adaptation features loaded successfully")
except ImportError as e:
    ML_FEATURES_AVAILABLE = False
    print(f"⚠️  ML features not available: {e}")

# Performance-Based Routing (optional - graceful fallback if not available)
try:
    from utils.performance import get_performance_router, save_performance_router
    PERFORMANCE_ROUTING_AVAILABLE = True
    print("✅ Performance-Based Routing loaded successfully")
except ImportError as e:
    PERFORMANCE_ROUTING_AVAILABLE = False
    print(f"⚠️  Performance-Based Routing not available: {e}")

# Load environment variables
load_dotenv()


class AgentState(TypedDict):
    """
    Enhanced State for the LangGraph agent with full agentic capabilities.
    Matches AGENTIC_CAPABILITIES_SUMMARY.md specification exactly.
    """
    messages: Annotated[List[Any], add_messages]  # Conversation history
    question: str  # Current question
    tool_used: Optional[str]  # Last tool used
    tool_result: Optional[str]  # Last tool result
    final_answer: Optional[str]  # Final answer to return
    tried_document_qa: bool  # Track if we tried Document_QA
    document_qa_failed: bool  # Track if Document_QA failed
    iteration: int  # Track number of iterations
    
    # NEW: Planning and decomposition (from AGENTIC_CAPABILITIES_SUMMARY.md)
    original_question: str  # Stores the initial question
    is_complex_task: bool  # Flag for multi-step tasks
    task_plan: Optional[List[Dict]]  # Step-by-step execution plan
    current_step: int  # Track progress
    completed_steps: List[str]  # Steps already completed
    
    # NEW: Self-reflection (from AGENTIC_CAPABILITIES_SUMMARY.md)
    response_confidence: Optional[float]  # Confidence in answer (0-1)
    quality_issues: List[str]  # Detected problems in response
    
    # NEW: Clarification (from AGENTIC_CAPABILITIES_SUMMARY.md)
    needs_clarification: bool  # Flag to ask user
    clarification_question: Optional[str]  # Question to ask user
    
    # NEW: Tool usage tracking (from AGENTIC_CAPABILITIES_SUMMARY.md)
    tools_used_history: List[str]  # All tools used in request
    intermediate_answers: List[Dict]  # Results from each step
    
    # NEW: Error handling (from AGENTIC_CAPABILITIES_SUMMARY.md)
    fallback_attempts: int  # Retry counter
    max_iterations: int  # Iteration limit
    
    # NEW: Adaptive behavior (from AGENTIC_CAPABILITIES_SUMMARY.md)
    suggested_followups: List[str]  # Suggestions for user
    alternative_approaches: List[str]  # Other ways to solve
    error_context: Optional[Dict]  # Error information
    
    # Internal tracking (compatibility)
    needs_retry: bool  # Whether to retry with different approach


class StudySearchAgent:
    """
    An intelligent LangGraph-based agent that:
    - Routes questions to appropriate tools
    - Implements fallback logic (Document_QA → Web_Search)
    - Maintains conversation memory
    - Supports multi-step workflows
    - Reduces prompt overhead with explicit state management
    """
    
    def __init__(self, llm_provider: str = "gemini", model_name: Optional[str] = None):
        """
        Initialize the Study and Search Agent with LangGraph.
        
        Args:
            llm_provider: Either "openai", "anthropic", "gemini", or "huggingface"
            model_name: Optional model name override
        """
        self.llm_provider = llm_provider.lower()
        # Use study-optimized LLM (temperature=0.7 for creative, conversational responses)
        self.llm = initialize_llm(model_name=model_name, use_case="study")
        self.tools = get_all_tools()
        
        # Create tool lookup dictionary for fast access
        self.tool_map = {tool.name: tool for tool in self.tools}
        
        # Initialize memory for conversation history
        self.memory = MemorySaver()
        
        # OPTIMIZATION: Initialize result cache using shared utility
        self.cache = ResultCache(ttl_seconds=DEFAULT_CACHE_TTL)
        
        # Initialize performance-based router
        if PERFORMANCE_ROUTING_AVAILABLE:
            self.performance_router = get_performance_router()
            print("✅ Study Agent: Performance-Based Routing enabled - learning from tool performance")
        else:
            self.performance_router = None
        
        # Build the LangGraph
        self.graph = self._build_graph()
        
        # Compile graph with checkpointing for memory
        self.app = self.graph.compile(checkpointer=self.memory)
    
    def _build_graph(self) -> StateGraph:
        """
        Build the AGENTIC LangGraph with full decision-making capabilities.
        Per AGENTIC_CAPABILITIES_SUMMARY.md specification.
        
        NEW AGENTIC FLOW:
        START → detect_complexity → [simple or complex/clarification]
        
        SIMPLE path:
          → route_question → [tool] → self_reflect → [good/retry/clarify] → END
          
        COMPLEX path:
          → plan_complex_task → execute_plan (loop) → synthesize → self_reflect → END
        """
        workflow = StateGraph(AgentState)
        
        # ===== AGENTIC NODES (per AGENTIC_CAPABILITIES_SUMMARY.md) =====
        workflow.add_node("detect_complexity", self._detect_complexity)
        workflow.add_node("plan_complex_task", self._plan_complex_task)
        workflow.add_node("execute_plan", self._execute_plan)  # Renamed per spec
        workflow.add_node("synthesize_results", self._synthesize_plan_results)
        workflow.add_node("self_reflect", self._self_reflect)
        workflow.add_node("ask_clarification", self._ask_clarification)
        workflow.add_node("retry_improved", self._retry_improved)
        
        # ===== EXISTING NODES =====
        workflow.add_node("route_question", self._route_question)
        workflow.add_node("document_qa", self._execute_document_qa)
        workflow.add_node("web_search", self._execute_web_search)
        workflow.add_node("python_repl", self._execute_python_repl)
        workflow.add_node("manim_animation", self._execute_manim_animation)
        workflow.add_node("check_result", self._check_result)
        workflow.add_node("format_answer", self._format_answer)
        
        # ===== ENTRY POINT: Detect Complexity =====
        workflow.set_entry_point("detect_complexity")
        
        # ===== COMPLEXITY ROUTING (per spec) =====
        def route_by_complexity(state: AgentState) -> str:
            if state.get("is_complex_task", False):  # Updated field name
                return "plan_complex"
            return "route_simple"
        
        workflow.add_conditional_edges(
            "detect_complexity",
            route_by_complexity,
            {
                "plan_complex": "plan_complex_task",
                "route_simple": "route_question"
            }
        )
        
        # ===== COMPLEX PATH: Multi-Step Planning (per spec) =====
        def check_plan_steps(state: AgentState) -> str:
            plan = state.get("task_plan", [])  # Updated field name
            current_step = state.get("current_step", 0)
            
            if plan is None or not state.get("is_complex_task", False):  # Updated field name
                # Planning failed, fall back to simple route
                return "fallback_to_simple"
            elif current_step < len(plan):
                return "execute_step"
            else:
                return "synthesize"
        
        workflow.add_conditional_edges(
            "plan_complex_task",
            check_plan_steps,
            {
                "execute_step": "execute_plan",  # Updated node name
                "synthesize": "synthesize_results",
                "fallback_to_simple": "route_question"
            }
        )
        
        # Loop for multi-step execution (per spec)
        workflow.add_conditional_edges(
            "execute_plan",  # Updated node name
            check_plan_steps,
            {
                "execute_step": "execute_plan",  # Updated node name
                "synthesize": "synthesize_results"
            }
        )
        
        # After synthesis, self-reflect
        workflow.add_edge("synthesize_results", "self_reflect")
        
        # ===== SIMPLE PATH: Single Tool Routing =====
        workflow.add_conditional_edges(
            "route_question",
            self._route_to_tool,
            {
                "document_qa": "document_qa",
                "web_search": "web_search",
                "python_repl": "python_repl",
                "manim_animation": "manim_animation"
            }
        )
        
        # All simple tools → check_result → format_answer → self_reflect
        workflow.add_edge("document_qa", "check_result")
        workflow.add_edge("web_search", "check_result")
        workflow.add_edge("python_repl", "check_result")
        workflow.add_edge("manim_animation", "check_result")
        
        workflow.add_conditional_edges(
            "check_result",
            self._should_retry,
            {
                "retry": "web_search",
                "finish": "format_answer"
            }
        )
        
        workflow.add_edge("format_answer", "self_reflect")
        
        # ===== SELF-REFLECTION ROUTING =====
        def route_after_reflection(state: AgentState) -> str:
            if state.get("needs_retry", False):
                return "retry"
            elif state.get("needs_clarification", False):
                return "clarify"
            else:
                return "finish"
        
        workflow.add_conditional_edges(
            "self_reflect",
            route_after_reflection,
            {
                "retry": "retry_improved",
                "clarify": "ask_clarification",
                "finish": END
            }
        )
        
        # Retry loops back to routing
        workflow.add_edge("retry_improved", "route_question")
        
        # Clarification ends the flow
        workflow.add_edge("ask_clarification", END)
        
        return workflow
    
    def _route_question(self, state: AgentState) -> AgentState:
        """
        Analyze the question and prepare for routing.
        Uses LLM to understand intent with conversation context.
        """
        question = state["question"]
        previous_messages = state.get("messages", [])
        
        # Build routing prompt with conversation context
        routing_prompt = """Analyze this question and determine which tool to use:

Available tools:
1. Document_QA - Use ONLY if user mentions "my notes", "my documents", "uploaded files", "the PDF", "the document"
2. Python_REPL - Use for math calculations, code execution, computational problems
3. render_manim_video - Use if user asks to "animate", "visualize", "create animation", or wants visual explanation of concepts
4. Web_Search - Use for general knowledge, current events, academic topics without document reference

Respond with ONLY the tool name: Document_QA, Python_REPL, render_manim_video, or Web_Search"""
        
        # Include conversation history for context
        messages = [SystemMessage(content=routing_prompt)]
        
        # Add recent conversation history (last 4 messages for context)
        if previous_messages:
            messages.extend(previous_messages[-4:])
        
        # Add current question
        messages.append(HumanMessage(content=question))
        
        response = self.llm.invoke(messages)
        tool_choice = response.content.strip()
        
        # Ensure valid tool name
        if "Document_QA" in tool_choice or "document" in tool_choice.lower():
            tool_choice = "Document_QA"
        elif "Python_REPL" in tool_choice or "python" in tool_choice.lower() or "repl" in tool_choice.lower():
            tool_choice = "Python_REPL"
        elif "render_manim_video" in tool_choice or "manim" in tool_choice.lower() or "animation" in tool_choice.lower() or "render" in tool_choice.lower():
            tool_choice = "render_manim_video"
        else:
            tool_choice = "Web_Search"
        
        print(f"\n🤔 Routing decision: {tool_choice}")
        
        # Update messages with current question
        updated_messages = previous_messages + [HumanMessage(content=question)]
        
        return {
            **state,
            "tool_used": tool_choice,
            "messages": updated_messages
        }
    
    def _route_to_tool(self, state: AgentState) -> Literal["document_qa", "web_search", "python_repl", "manim_animation"]:
        """Conditional edge function to route to the appropriate tool."""
        tool = state["tool_used"]
        
        if tool == "Document_QA":
            return "document_qa"
        elif tool == "Python_REPL":
            return "python_repl"
        elif tool == "render_manim_video":
            return "manim_animation"
        else:
            return "web_search"
    
    def _execute_document_qa(self, state: AgentState) -> AgentState:
        """Execute Document_QA tool."""
        print("📚 Executing Document_QA...")
        
        tool = self.tool_map.get("Document_QA")
        if not tool:
            return {
                **state,
                "tool_result": "Document_QA tool not available. No documents loaded.",
                "tried_document_qa": True,
                "document_qa_failed": True
            }
        
        try:
            result = tool.func(state["question"])
            
            # Check if Document_QA failed to find content
            failed_phrases = [
                "no relevant content found",
                "no documents have been loaded",
                "no information",
                "not found in the documents"
            ]
            
            failed = any(phrase in result.lower() for phrase in failed_phrases)
            
            return {
                **state,
                "tool_result": result,
                "tried_document_qa": True,
                "document_qa_failed": failed
            }
        except Exception as e:
            return {
                **state,
                "tool_result": f"Error in Document_QA: {str(e)}",
                "tried_document_qa": True,
                "document_qa_failed": True
            }
    
    def _execute_web_search(self, state: AgentState) -> AgentState:
        """Execute Web_Search tool and synthesize results."""
        print("🔍 Executing Web_Search...")
        
        tool = self.tool_map.get("Web_Search")
        if not tool:
            return {
                **state,
                "tool_result": "Web search tool not available. TAVILY_API_KEY may be missing.",
                "document_qa_failed": False
            }
        
        try:
            # Get conversation context
            previous_messages = state.get("messages", [])
            context_messages = previous_messages[-6:] if previous_messages else []
            
            original_question = state["question"]
            search_query = original_question
            
            # Debug: Show conversation memory status
            if context_messages:
                print(f"💾 Found {len(previous_messages)} messages in conversation history")
            
            # Check if this is a vague follow-up question that needs context enrichment
            vague_patterns = [
                'how does it work', 'tell me more', 'what about', 'how about', 
                'explain that', 'how', 'why', 'when', 'where', 'can you', 'who else',
                'what else', 'anything else', 'more details', 'tell me about',
                'who is', 'what is', 'where is', 'when is', 'which is',
                'who are', 'what are', 'where are', 'who founded', 'who created',
                'who made', 'who built', 'who started', 'who owns'
            ]
            
            is_vague = any(original_question.lower().startswith(pattern) for pattern in vague_patterns)
            is_short = len(original_question.split()) <= 6  # Increased from 5 to 6
            has_pronoun = any(word in original_question.lower() for word in ['it', 'this', 'that', 'they', 'them', 'else', 'there'])
            
            # Check if question lacks a clear topic (very generic)
            # Questions like "Who is the founder" without mentioning what organization
            generic_subjects = ['the founder', 'the creator', 'the ceo', 'the owner', 'the president',
                              'the leader', 'the person', 'the company', 'the organization']
            has_generic_subject = any(subject in original_question.lower() for subject in generic_subjects)
            
            # If question seems like a follow-up, enrich it with context
            needs_enrichment = (is_vague or has_pronoun or has_generic_subject) and context_messages and is_short
            
            # Debug: Show why enrichment is/isn't happening
            if context_messages and is_short:
                if needs_enrichment:
                    reasons = []
                    if is_vague: reasons.append("vague pattern")
                    if has_pronoun: reasons.append("has pronoun")
                    if has_generic_subject: reasons.append("generic subject")
                    print(f"🔗 Enriching follow-up question ({', '.join(reasons)}) with conversation context...")
            
            if needs_enrichment:
                
                # Use LLM to expand the question with context
                context_text = "\n".join([
                    f"{'User' if isinstance(msg, HumanMessage) else 'Assistant'}: {msg.content[:200]}"
                    for msg in context_messages
                ])
                
                enrichment_system = """You are a query expansion assistant. Given conversation history and a follow-up question, expand the question into a complete, standalone search query.

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
                
                enrichment_user = f"""Conversation History:
{context_text}

Follow-up Question: {original_question}

Expanded search query:"""
                
                enrichment_response = self.llm.invoke([
                    SystemMessage(content=enrichment_system),
                    HumanMessage(content=enrichment_user)
                ])
                
                search_query = enrichment_response.content.strip()
                print(f"💡 Enriched query: '{search_query}'")
            
            # Get raw search results with the enriched query
            raw_results = tool.func(search_query)
            
            # Synthesize results into coherent answer using LLM
            synthesis_prompt = f"""Based on the search results below, provide a clear, comprehensive answer to the question.

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
            
            messages = [SystemMessage(content=synthesis_prompt)]
            
            # Add conversation context if available
            if context_messages:
                messages.extend(context_messages[-4:])  # Last 4 for context
            
            messages.append(HumanMessage(content="Please provide the synthesized answer."))
            
            print("🧠 Synthesizing search results into coherent answer...")
            synthesized_answer = self.llm.invoke(messages)
            
            return {
                **state,
                "tool_result": synthesized_answer.content,
                "document_qa_failed": False
            }
        except Exception as e:
            return {
                **state,
                "tool_result": f"Error in Web_Search: {str(e)}",
                "document_qa_failed": False
            }
    
    def _execute_python_repl(self, state: AgentState) -> AgentState:
        """Execute Python_REPL tool."""
        print("🐍 Executing Python_REPL...")
        
        tool = self.tool_map.get("Python_REPL")
        if not tool:
            return {
                **state,
                "tool_result": "Python REPL tool not available.",
                "document_qa_failed": False
            }
        
        try:
            # For Python REPL, we need to construct executable code
            question = state["question"]
            
            # Use LLM to generate Python code if needed
            if "print" not in question.lower() and any(op in question for op in ['+', '-', '*', '/', '**']):
                code = f"print({question})"
            else:
                code = question
            
            result = tool.func(code)
            return {
                **state,
                "tool_result": str(result),
                "document_qa_failed": False
            }
        except Exception as e:
            return {
                **state,
                "tool_result": f"Error in Python_REPL: {str(e)}",
                "document_qa_failed": False
            }
    
    def _execute_manim_animation(self, state: AgentState) -> AgentState:
        """Execute render_manim_video tool."""
        print("🎬 Executing render_manim_video...")
        
        tool = self.tool_map.get("render_manim_video")
        if not tool:
            return {
                **state,
                "tool_result": "Manim Animation tool not available. Please ensure Manim is installed.",
                "document_qa_failed": False
            }
        
        try:
            question = state["question"]
            result = tool.func(question)
            
            # Parse the Tool Artifact JSON response
            try:
                import json
                artifact_response = json.loads(result)
                content = artifact_response.get("content", result)
                artifact = artifact_response.get("artifact")
                
                # If we have an artifact (video file), display it
                if artifact:
                    print(f"🎥 Video artifact available: {artifact}")
                    formatted_result = f"{content}\n\n📹 Video file: {artifact}"
                else:
                    formatted_result = content
                
                return {
                    **state,
                    "tool_result": formatted_result,
                    "document_qa_failed": False
                }
            except json.JSONDecodeError:
                # Fallback if result is not JSON
                return {
                    **state,
                    "tool_result": result,
                    "document_qa_failed": False
                }
                
        except Exception as e:
            return {
                **state,
                "tool_result": f"Error in render_manim_video: {str(e)}",
                "document_qa_failed": False
            }
    
    def _check_result(self, state: AgentState) -> AgentState:
        """Check if the result is satisfactory or needs fallback."""
        iteration = state.get("iteration", 0) + 1
        
        return {
            **state,
            "iteration": iteration
        }
    
    def _should_retry(self, state: AgentState) -> Literal["retry", "finish"]:
        """
        Decide if we should retry with a different tool (fallback logic).
        
        Fallback strategy:
        - If Document_QA failed and we haven't tried Web_Search yet → retry with Web_Search
        - Otherwise → finish
        """
        # If Document_QA failed and we used it first, try Web_Search as fallback
        if state.get("document_qa_failed", False) and state.get("tried_document_qa", False):
            if state.get("iteration", 0) < 2:  # Prevent infinite loops
                print("⚠️  Document_QA failed. Falling back to Web_Search...")
                return "retry"
        
        return "finish"
    
    def _format_answer(self, state: AgentState) -> AgentState:
        """Format the final answer from tool results."""
        tool_result = state.get("tool_result", "No result generated")
        tool_used = state.get("tool_used", "Unknown")
        
        # If we had a fallback, mention it
        if state.get("document_qa_failed", False) and state.get("tried_document_qa", False):
            prefix = "ℹ️  Note: Document not found, searched the web instead.\n\n"
            final_answer = prefix + tool_result
        else:
            final_answer = tool_result
        
        return {
            **state,
            "final_answer": final_answer,
            "messages": state["messages"] + [AIMessage(content=final_answer)]
        }
    
    # =============================================================================
    # NEW: AGENTIC NODES - Complexity Detection, Planning, Self-Reflection
    # =============================================================================
    
    def _detect_complexity(self, state: AgentState) -> AgentState:
        """
        NEW AGENTIC NODE: Detect question complexity and decide if planning is needed.
        Per AGENTIC_CAPABILITIES_SUMMARY.md specification.
        
        Analyzes if the question is:
        - Multi-part (multiple questions or tasks)
        - Vague/ambiguous (needs clarification)
        - Complex (requires multiple tools)
        """
        question = state["question"]
        question_lower = question.lower()
        
        print("\n🔍 Analyzing Question Complexity...")
        
        # Store original question if not set
        original_question = state.get("original_question", question)
        
        # Check for multi-part questions
        multi_part_indicators = [
            " and ", " also ", " then ", " after that", " followed by"
        ]
        is_multi_part = any(indicator in question_lower for indicator in multi_part_indicators)
        question_marks = question.count("?")
        has_multiple_questions = question_marks > 1
        
        # Check for vague language (triggers clarification)
        vague_indicators = [
            "it", "this", "that", "stuff", "thing", "something", "somehow"
        ]
        is_vague = any(word in question_lower.split() for word in vague_indicators)
        
        # Check for explicit multi-tool requests
        tool_keywords = {
            "document": ["document", "notes", "file", "pdf"],
            "web": ["search", "internet", "online", "web"],
            "code": ["code", "program", "python", "execute", "run"],
            "animate": ["animate", "animation", "video", "visual"]
        }
        
        tools_mentioned = 0
        for tool_words in tool_keywords.values():
            if any(word in question_lower for word in tool_words):
                tools_mentioned += 1
        
        needs_multiple_tools = tools_mentioned > 1
        
        # Determine complexity level
        complexity_factors = [
            is_multi_part,
            has_multiple_questions,
            needs_multiple_tools
        ]
        
        is_complex_task = any(complexity_factors)
        
        print(f"   Complexity: {'COMPLEX' if is_complex_task else 'SIMPLE'}")
        if is_multi_part:
            print(f"   ├─ Multi-part question detected")
        if has_multiple_questions:
            print(f"   ├─ Multiple questions detected ({question_marks} question marks)")
        if needs_multiple_tools:
            print(f"   ├─ Multiple tools needed ({tools_mentioned} tool types mentioned)")
        if is_vague:
            print(f"   ├─ Vague language detected")
        
        # Set needs_clarification if vague
        needs_clarification = is_vague and not is_complex_task
        
        return {
            **state,
            "original_question": original_question,
            "is_complex_task": is_complex_task,
            "needs_clarification": needs_clarification,
            "tools_used_history": state.get("tools_used_history", [])
        }
    
    def _plan_complex_task(self, state: AgentState) -> AgentState:
        """
        NEW AGENTIC NODE: Create multi-step execution plan for complex questions.
        Per AGENTIC_CAPABILITIES_SUMMARY.md specification.
        
        Uses LLM to break down complex questions into executable steps.
        """
        question = state["question"]
        
        print("\n📋 Creating Multi-Step Execution Plan...")
        
        planning_prompt = f"""You are a task planner. Break this complex question into clear, executable steps.

Question: {question}

Available tools:
- Document_QA: Search uploaded documents and PDFs
- Web_Search: Search the internet for information
- Python_REPL: Execute Python code
- Manim_Animation: Create educational animations

Create a step-by-step plan. Return ONLY a JSON array like this:
[
  {{"step_number": 1, "description": "Find information about X", "tool": "web_search"}},
  {{"step_number": 2, "description": "Calculate Y", "tool": "python_repl"}},
  {{"step_number": 3, "description": "Create animation", "tool": "manim"}}
]

Keep it simple - typically 2-4 steps maximum."""
        
        try:
            import json
            response = self.llm.invoke([HumanMessage(content=planning_prompt)])
            
            # Extract JSON from response
            content = response.content.strip()
            # Remove markdown code blocks if present
            if "```json" in content:
                content = content.split("```json")[1].split("```")[0].strip()
            elif "```" in content:
                content = content.split("```")[1].split("```")[0].strip()
            
            plan = json.loads(content)
            
            print(f"   Created {len(plan)}-step plan:")
            for step in plan:
                print(f"   Step {step['step_number']}: {step['tool']} - {step['description']}")
            
            return {
                **state,
                "task_plan": plan,
                "current_step": 0,
                "completed_steps": [],
                "intermediate_answers": []
            }
        
        except Exception as e:
            print(f"   ⚠️  Planning failed: {e}")
            print(f"   Falling back to simple execution")
            # Fall back to simple execution
            return {
                **state,
                "task_plan": None,
                "is_complex_task": False  # Disable complex path, use simple route
            }
    
    def _execute_plan(self, state: AgentState) -> AgentState:
        """
        NEW AGENTIC NODE: Execute one step from the task plan.
        Per AGENTIC_CAPABILITIES_SUMMARY.md specification.
        
        Sequential execution with context accumulation.
        """
        plan = state.get("task_plan", [])
        current_step = state.get("current_step", 0)
        
        if not plan or current_step >= len(plan):
            return state
        
        step = plan[current_step]
        step_number = step.get("step_number", current_step + 1)
        description = step.get("description", "Execute step")
        tool_name = step.get("tool", "")
        
        print(f"\n▶️  Executing Step {step_number}: {description}")
        
        # Map tool names to execution methods
        tool_map = {
            "web_search": self._execute_web_search,
            "Web_Search": self._execute_web_search,
            "document_qa": self._execute_document_qa,
            "Document_QA": self._execute_document_qa,
            "python_repl": self._execute_python_repl,
            "Python_REPL": self._execute_python_repl,
            "manim": self._execute_manim_animation,
            "Manim_Animation": self._execute_manim_animation
        }
        
        if tool_name in tool_map:
            # Execute the tool
            result_state = tool_map[tool_name](state)
            
            # Store intermediate answer (per spec)
            intermediate_answers = state.get("intermediate_answers", [])
            intermediate_answers.append({
                "step_number": step_number,
                "description": description,
                "tool": tool_name,
                "result": result_state.get("tool_result", "")
            })
            
            # Track tools used
            tools_used = state.get("tools_used_history", [])
            tools_used.append(tool_name)
            
            # Track completed steps (per spec: List[str])
            completed_steps = state.get("completed_steps", [])
            completed_steps.append(f"step_{step_number}")
            
            return {
                **result_state,
                "current_step": current_step + 1,
                "completed_steps": completed_steps,
                "intermediate_answers": intermediate_answers,
                "tools_used_history": tools_used
            }
        else:
            print(f"   ⚠️  Unknown tool: {tool_name}")
            return {
                **state,
                "current_step": current_step + 1
            }
    
    def _synthesize_plan_results(self, state: AgentState) -> AgentState:
        """
        NEW AGENTIC NODE: Synthesize results from all plan steps into final answer.
        Per AGENTIC_CAPABILITIES_SUMMARY.md - synthesizes final answer from all steps.
        """
        intermediate_answers = state.get("intermediate_answers", [])
        question = state["question"]
        
        print("\n🧩 Synthesizing Multi-Step Results...")
        
        # Build context from all steps (per spec)
        steps_context = "\n\n".join([
            f"Step {r['step_number']} ({r['tool']} - {r['description']}):\n{r['result']}"
            for r in intermediate_answers
        ])
        
        synthesis_prompt = f"""Synthesize these step-by-step results into a comprehensive answer.

Original Question: {question}

Step Results:
{steps_context}

Provide a complete, coherent answer that addresses the original question using ALL the information from the steps above."""
        
        try:
            response = self.llm.invoke([HumanMessage(content=synthesis_prompt)])
            final_answer = response.content
            
            # Add metadata about the multi-step process
            metadata = f"\n\n---\n📊 Multi-Step Process: {len(intermediate_answers)} steps completed"
            final_answer = final_answer + metadata
            
            return {
                **state,
                "final_answer": final_answer,
                "tool_result": final_answer,
                "messages": state["messages"] + [AIMessage(content=final_answer)]
            }
            
        except Exception as e:
            print(f"   ⚠️  Synthesis failed: {e}")
            # Fall back to last result
            last_result = intermediate_answers[-1]["result"] if intermediate_answers else "No results generated"
            return {
                **state,
                "final_answer": last_result,
                "tool_result": last_result
            }
    
    def _self_reflect(self, state: AgentState) -> AgentState:
        """
        NEW AGENTIC NODE: Self-reflect on answer quality and confidence.
        
        Evaluates:
        - Answer completeness
        - Confidence level
        - Quality issues
        - Need for retry or clarification
        """
        answer = state.get("final_answer") or state.get("tool_result", "")
        question = state["question"]
        iteration = state.get("iteration", 0)
        
        print("\n🤔 Self-Reflecting on Answer Quality...")
        
        quality_issues = []
        confidence = 1.0
        
        # Check answer length
        if len(answer) < 50:
            quality_issues.append("Response is too short")
            confidence -= 0.3
        
        # Check for error indicators
        error_indicators = ["error", "failed", "not found", "not available", "could not"]
        if any(indicator in answer.lower() for indicator in error_indicators):
            quality_issues.append("Contains error messages")
            confidence -= 0.4
        
        # Check for uncertainty indicators
        uncertainty_indicators = ["i don't know", "i'm not sure", "unclear", "cannot determine"]
        if any(indicator in answer.lower() for indicator in uncertainty_indicators):
            quality_issues.append("Expresses uncertainty")
            confidence -= 0.2
        
        # Check if answer addresses the question
        question_words = set(question.lower().split())
        answer_words = set(answer.lower().split())
        overlap = len(question_words & answer_words)
        overlap_ratio = overlap / len(question_words) if question_words else 0
        
        if overlap_ratio < 0.2:
            quality_issues.append("May not address the question")
            confidence -= 0.3
        
        # Check completeness for multi-part questions
        if state.get("is_multi_part", False):
            question_marks = question.count("?")
            if question_marks > 1:
                # Simple heuristic: should have multiple answer sections
                sections = len([p for p in answer.split("\n\n") if len(p) > 20])
                if sections < question_marks:
                    quality_issues.append("May not answer all parts of multi-part question")
                    confidence -= 0.2
        
        confidence = max(0.0, min(1.0, confidence))
        
        # Decide on actions
        needs_retry = confidence < 0.5 and iteration < MAX_AGENT_ITERATIONS
        needs_clarification = confidence < 0.6 and state.get("is_vague", False)
        
        print(f"   Confidence: {confidence:.2f}")
        if quality_issues:
            print(f"   Issues detected:")
            for issue in quality_issues:
                print(f"   ├─ {issue}")
        
        if needs_retry:
            print(f"   ⚠️  Quality too low - will retry with alternative approach")
        elif needs_clarification:
            print(f"   ⚠️  Question vague - may need clarification")
        else:
            print(f"   ✅ Quality acceptable")
        
        return {
            **state,
            "response_confidence": confidence,
            "quality_issues": quality_issues,
            "needs_retry": needs_retry,
            "needs_clarification": needs_clarification
        }
    
    def _ask_clarification(self, state: AgentState) -> AgentState:
        """
        NEW AGENTIC NODE: Generate clarification question for ambiguous requests.
        """
        question = state["question"]
        quality_issues = state.get("quality_issues", [])
        
        print("\n❓ Generating Clarification Question...")
        
        clarification_prompt = f"""The user's question is ambiguous or unclear. Generate a helpful clarification question.

Original Question: {question}

Quality Issues: {', '.join(quality_issues)}

Generate ONE specific clarification question to help understand what the user needs. Be concise and helpful."""
        
        try:
            response = self.llm.invoke([HumanMessage(content=clarification_prompt)])
            clarification = response.content.strip()
            
            final_answer = f"{state.get('final_answer', '')}\n\n🤔 **Clarification needed**: {clarification}"
            
            print(f"   Generated: {clarification}")
            
            return {
                **state,
                "clarification_question": clarification,
                "final_answer": final_answer
            }
            
        except Exception as e:
            print(f"   ⚠️  Failed to generate clarification: {e}")
            return state
    
    def _retry_improved(self, state: AgentState) -> AgentState:
        """
        NEW AGENTIC NODE: Retry with improved strategy after quality issues detected.
        Per AGENTIC_CAPABILITIES_SUMMARY.md - tries different tool combinations.
        """
        alternative_approaches = state.get("alternative_approaches", [])
        current_tool = state.get("tool_used")
        fallback_attempts = state.get("fallback_attempts", 0)
        
        print("\n🔄 Retrying with Alternative Approach...")
        
        # Try alternative tool
        available_tools = ["Document_QA", "Web_Search", "Python_REPL"]
        alternative_tools = [t for t in available_tools if t != current_tool and t not in alternative_approaches]
        
        if alternative_tools and fallback_attempts < state.get("max_iterations", MAX_AGENT_ITERATIONS):
            alternative = alternative_tools[0]
            print(f"   Trying alternative: {alternative}")
            
            # Track this approach (per spec)
            alternative_approaches.append(current_tool)
            
            return {
                **state,
                "tool_used": alternative,
                "alternative_approaches": alternative_approaches,
                "fallback_attempts": fallback_attempts + 1,
                "iteration": state.get("iteration", 0) + 1
            }
        else:
            print(f"   No more alternatives available")
            return state
    
    def query(self, question: str, thread_id: str = "default", user_id: Optional[str] = None) -> str:
        """
        Process a question and return the answer.
        
        Args:
            question: The question to answer
            thread_id: Thread ID for conversation memory (default: "default")
            user_id: Optional user ID for ML tracking and personalization
            
        Returns:
            The answer string
        """
        try:
            # Configure with thread ID for memory
            config = {"configurable": {"thread_id": thread_id}}
            
            # Get existing conversation history from memory
            existing_messages = []
            try:
                state = self.app.get_state(config)
                if state and state.values:
                    existing_messages = state.values.get("messages", [])
            except Exception:
                pass  # No previous state, start fresh
            
            # Initial state with conversation history
            initial_state = {
                "messages": existing_messages,  # Load previous messages
                "question": question,
                "tool_used": None,
                "tool_result": None,
                "final_answer": None,
                "tried_document_qa": False,
                "document_qa_failed": False,
                "iteration": 0,
                # NEW: Agentic state fields (per AGENTIC_CAPABILITIES_SUMMARY.md)
                "original_question": question,
                "is_complex_task": False,
                "task_plan": None,
                "current_step": 0,
                "completed_steps": [],
                "intermediate_answers": [],
                "response_confidence": None,
                "quality_issues": [],
                "needs_clarification": False,
                "clarification_question": None,
                "tools_used_history": [],
                "fallback_attempts": 0,
                "max_iterations": MAX_AGENT_ITERATIONS,
                "suggested_followups": [],
                "alternative_approaches": [],
                "error_context": None,
                "needs_retry": False
            }
            
            # Run the graph
            result = self.app.invoke(initial_state, config)
            
            return result.get("final_answer", "No answer generated")
                    
        except Exception as e:
            return f"Error processing query: {str(e)}"
    
    def get_conversation_history(self, thread_id: str = "default") -> List[Any]:
        """
        Get conversation history for a specific thread.
        
        Args:
            thread_id: Thread ID to retrieve history for
            
        Returns:
            List of messages in the conversation
        """
        try:
            config = {"configurable": {"thread_id": thread_id}}
            state = self.app.get_state(config)
            return state.values.get("messages", []) if state else []
        except Exception as e:
            print(f"Error retrieving history: {e}")
            return []
    
    def visualize_graph(self) -> str:
        """
        Return a text visualization of the LangGraph structure.
        
        Returns:
            Simple graph representation
        """
        return """
LangGraph Flow: START → route_question → [document_qa|web_search|python_repl|manim_animation] 
                  → check_result → [retry: web_search | finish: format_answer] → END
                  
Features: Intelligent routing, fallback logic, conversation memory, Manim animations, reduced overhead
See LANGGRAPH_MIGRATION.md for detailed architecture diagram.
        """
    
    def chat(self):
        """Interactive chat mode with LangGraph features."""
        print("=" * 60)
        print("Study and Search Agent - LangGraph Mode 🚀")
        print("=" * 60)
        print("\n✨ New Features:")
        print("  🔄 Automatic fallback logic (Document → Web)")
        print("  💾 Conversation memory across questions")
        print("  🎯 Smart routing with reduced overhead")
        print("\nI can help you with:")
        print("  📊 Math and code execution (using Python)")
        print("  🔍 Real-time web searches")
        print("  💡 General knowledge questions")
        
        # Check if Document_QA is available
        doc_qa_available = any(tool.name == "Document_QA" for tool in self.tools)
        if doc_qa_available:
            print("  📚 Questions about uploaded documents (PDF/DOCX)")
            print("  ✨ Generate MCQs, summaries, study guides, and flashcards")
            print("  ✨ Handle complex requests (e.g., 'Generate 10 MCQs and summarize chapter 1')")
        
        # Check if Manim is available
        manim_available = any(tool.name == "render_manim_video" for tool in self.tools)
        if manim_available:
            print("  🎬 Create educational animations (e.g., 'animate the Pythagorean theorem')")
            print("  🎨 Visualize mathematical and conceptual topics with Manim")
        
        print("\nSpecial commands:")
        print("  'graph' - Show LangGraph architecture visualization")
        print("  'history' - Show conversation history")
        print("  'quit', 'exit', 'q' - End conversation\n")
        
        while True:
            try:
                question = input("\n🤔 Your question: ").strip()
                
                if question.lower() in ['quit', 'exit', 'q']:
                    print("\n👋 Goodbye! Happy studying!")
                    break
                
                if question.lower() == 'graph':
                    print(self.visualize_graph())
                    continue
                
                if question.lower() == 'history':
                    history = self.get_conversation_history()
                    if history:
                        print("\n📝 Conversation History:")
                        for i, msg in enumerate(history, 1):
                            msg_type = "You" if isinstance(msg, HumanMessage) else "Agent"
                            content = msg.content[:100] + "..." if len(msg.content) > 100 else msg.content
                            print(f"  {i}. [{msg_type}]: {content}")
                    else:
                        print("\n📝 No conversation history yet.")
                    continue
                
                if not question:
                    continue
                
                print("\n" + "=" * 60)
                answer = self.query(question)
                print("=" * 60)
                print(f"\n✅ Final Answer: {answer}\n")
                
            except KeyboardInterrupt:
                print("\n\n👋 Goodbye! Happy studying!")
                break
            except Exception as e:
                print(f"\n❌ Error: {str(e)}\n")


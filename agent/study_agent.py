"""
Study and Search Agent - LangGraph Implementation
A dynamic agent that uses LangGraph for:
- Intelligent tool routing with fallback logic
- Conversation memory and history tracking
- Multi-step workflows with state management
- Conditional branching and complex routing
"""

import os
from typing import Optional, TypedDict, Annotated, Literal, List, Dict, Any
from dotenv import load_dotenv

from langgraph.graph import StateGraph, END
from langgraph.graph.message import add_messages
from langgraph.checkpoint.memory import MemorySaver
from langchain_core.messages import HumanMessage, AIMessage, SystemMessage

from tools.base import get_all_tools
from utils.llm import initialize_llm

# Load environment variables
load_dotenv()


class AgentState(TypedDict):
    """
    State for the LangGraph agent.
    Tracks conversation history and execution context.
    """
    messages: Annotated[List[Any], add_messages]  # Conversation history
    question: str  # Current question
    tool_used: Optional[str]  # Last tool used
    tool_result: Optional[str]  # Last tool result
    final_answer: Optional[str]  # Final answer to return
    tried_document_qa: bool  # Track if we tried Document_QA
    document_qa_failed: bool  # Track if Document_QA failed
    iteration: int  # Track number of iterations


class StudySearchAgent:
    """
    An intelligent LangGraph-based agent that:
    - Routes questions to appropriate tools
    - Implements fallback logic (Document_QA → Web_Search)
    - Maintains conversation memory
    - Supports multi-step workflows
    - Reduces prompt overhead with explicit state management
    """
    
    def __init__(self, llm_provider: str = "openai", model_name: Optional[str] = None):
        """
        Initialize the Study and Search Agent with LangGraph.
        
        Args:
            llm_provider: Either "openai", "anthropic", "gemini", or "huggingface"
            model_name: Optional model name override
        """
        self.llm_provider = llm_provider.lower()
        self.llm = initialize_llm(llm_provider, model_name)
        self.tools = get_all_tools()
        
        # Create tool lookup dictionary for fast access
        self.tool_map = {tool.name: tool for tool in self.tools}
        
        # Initialize memory for conversation history
        self.memory = MemorySaver()
        
        # Build the LangGraph
        self.graph = self._build_graph()
        
        # Compile graph with checkpointing for memory
        self.app = self.graph.compile(checkpointer=self.memory)
    
    def _build_graph(self) -> StateGraph:
        """
        Build the LangGraph with nodes and edges.
        
        Graph structure:
        START → route_question → [document_qa | web_search | python_repl | manim_animation]
                                       ↓              ↓            ↓            ↓
                                  check_result → [retry_web_search | format_answer]
                                                         ↓              ↓
                                                   format_answer → END
        """
        # Create the state graph
        workflow = StateGraph(AgentState)
        
        # Add nodes
        workflow.add_node("route_question", self._route_question)
        workflow.add_node("document_qa", self._execute_document_qa)
        workflow.add_node("web_search", self._execute_web_search)
        workflow.add_node("python_repl", self._execute_python_repl)
        workflow.add_node("manim_animation", self._execute_manim_animation)
        workflow.add_node("check_result", self._check_result)
        workflow.add_node("format_answer", self._format_answer)
        
        # Set entry point
        workflow.set_entry_point("route_question")
        
        # Add conditional edges from router
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
        
        # All tool nodes go to result checker
        workflow.add_edge("document_qa", "check_result")
        workflow.add_edge("web_search", "check_result")
        workflow.add_edge("python_repl", "check_result")
        workflow.add_edge("manim_animation", "check_result")
        
        # Conditional edge from result checker
        workflow.add_conditional_edges(
            "check_result",
            self._should_retry,
            {
                "retry": "web_search",  # Fallback to web search
                "finish": "format_answer"
            }
        )
        
        # Format answer goes to END
        workflow.add_edge("format_answer", END)
        
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
    
    def query(self, question: str, thread_id: str = "default") -> str:
        """
        Process a question and return the answer.
        
        Args:
            question: The question to answer
            thread_id: Thread ID for conversation memory (default: "default")
            
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
                "iteration": 0
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


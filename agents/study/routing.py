"""Routing logic for Study Agent."""

from typing import Literal
from langchain_core.messages import HumanMessage, SystemMessage

from .state import StudyAgentState
from utils import fast_study_route


class StudyAgentRouter:
    """Tool routing for Study Agent."""
    
    def __init__(self, llm):
        self.llm = llm
    
    def route_question(self, state: StudyAgentState) -> StudyAgentState:
        """Analyze question and determine tool to use."""
        question = state["question"]
        previous_messages = state.get("messages", [])
        
        # Try pattern-based routing first (fast, no LLM call)
        quick_route = fast_study_route(question)
        print(f"🔍 [ROUTING DEBUG] Initial route for '{question[:60]}...': {quick_route}")
        
        # If Document_QA was suggested, verify documents exist first
        if quick_route == "Document_QA":
            print("📚 [ROUTING DEBUG] Document_QA selected - checking database...")
            
            # Check if user explicitly references uploaded document
            question_lower = question.lower()
            explicit_doc_reference = any(indicator in question_lower for indicator in [
                "attached", "uploaded", "attachment", "the document", "the pdf", 
                "the file", "my document", "my file", "this document", "this pdf"
            ])
            
            try:
                from database.core import get_db
                from sqlalchemy import text
                import os
                
                with get_db() as db:
                    count_result = db.execute(text("SELECT COUNT(*) as count FROM document_vectors"))
                    total_docs = count_result.fetchone().count
                    print(f"📊 [ROUTING DEBUG] Found {total_docs} document vectors in DB")
                    
                    if total_docs == 0:
                        # Check if documents exist on disk but not yet indexed
                        documents_dir = os.getenv("DOCUMENTS_DIR", "documents")
                        files_on_disk = []
                        if os.path.exists(documents_dir):
                            files_on_disk = [f for f in os.listdir(documents_dir) 
                                           if f.endswith(('.pdf', '.docx', '.txt', '.md'))]
                        
                        if files_on_disk:
                            print(f"⚠️  Found {len(files_on_disk)} file(s) on disk but not indexed yet")
                            print(f"📄 Files: {', '.join(files_on_disk)}")
                            # Don't change route - let Document_QA handle the "indexing in progress" message
                        elif explicit_doc_reference:
                            print("⚠️  User explicitly referenced a document but none found")
                            # Don't change route - let Document_QA explain that no document was found
                        else:
                            print("⚠️  No documents in vector store and no explicit document reference")
                            # Only in this case, route to Web Search
                            quick_route = "Web_Search"
                    else:
                        print(f"✅ [ROUTING DEBUG] Documents available - proceeding with Document_QA")
            except Exception as e:
                print(f"⚠️  Database check error: {e} - continuing with Document_QA route (will fallback if needed)")
                # Continue with original route - fallback mechanism will handle it
        
        if quick_route:
            updated_messages = previous_messages + [HumanMessage(content=question)]
            return {**state, "tool_used": quick_route, "messages": updated_messages}
        
        # Fall back to LLM for ambiguous cases
        routing_prompt = """Determine which tool to use:

Available tools:
1. Document_QA - Search uploaded documents
2. Python_REPL - Execute code/calculations
3. render_manim_video - Create animations
4. Web_Search - Internet search

Respond with ONLY the tool name."""
        
        messages = [
            SystemMessage(content=routing_prompt),
            *previous_messages[-4:],  # Recent context
            HumanMessage(content=question)
        ]
        
        response = self.llm.invoke(messages)
        tool_choice = response.content.strip()
        
        # Normalize tool name
        if "Document_QA" in tool_choice or "document" in tool_choice.lower():
            tool_choice = "Document_QA"
        elif "Python_REPL" in tool_choice or "python" in tool_choice.lower():
            tool_choice = "Python_REPL"
        elif "manim" in tool_choice.lower() or "animation" in tool_choice.lower():
            tool_choice = "render_manim_video"
        else:
            tool_choice = "Web_Search"
        
        updated_messages = previous_messages + [HumanMessage(content=question)]
        return {**state, "tool_used": tool_choice, "messages": updated_messages}
    
    def route_to_tool(self, state: StudyAgentState) -> Literal[
        "document_qa", "web_search", "python_repl", "manim_animation"
    ]:
        """Conditional edge function for tool routing."""
        tool = state["tool_used"]
        
        if tool == "Document_QA":
            return "document_qa"
        elif tool == "Python_REPL":
            return "python_repl"
        elif tool == "render_manim_video":
            return "manim_animation"
        else:
            return "web_search"
    
    def should_retry(self, state: StudyAgentState) -> Literal["retry", "finish"]:
        """Decide if retry with different tool is needed."""
        # Check if we asked user for clarification and they haven't responded yet
        if state.get("awaiting_user_choice"):
            # Don't auto-retry - wait for user's explicit choice
            return "finish"
        
        # If user explicitly chose web search, we're done after executing it
        # Don't retry again
        if state.get("user_choice_web_search") or state.get("user_choice_upload"):
            return "finish"
        
        # Legacy auto-retry (shouldn't happen now but keep as fallback)
        if state.get("document_qa_failed") and state.get("tried_document_qa"):
            if state.get("iteration", 0) < 2 and not state.get("needs_clarification"):
                return "retry"
        
        return "finish"
    
    def route_by_complexity(self, state: StudyAgentState) -> Literal["plan_complex", "route_simple"]:
        """Route based on task complexity."""
        if state.get("is_complex_task", False):
            return "plan_complex"
        return "route_simple"
    
    def check_plan_steps(self, state: StudyAgentState) -> Literal["execute_step", "synthesize", "fallback_to_simple"]:
        """Check plan execution progress."""
        plan = state.get("task_plan", [])
        current_step = state.get("current_step", 0)
        
        if plan is None or not state.get("is_complex_task", False):
            return "fallback_to_simple"
        elif current_step < len(plan):
            return "execute_step"
        else:
            return "synthesize"
    
    def route_after_reflection(self, state: StudyAgentState) -> Literal["retry", "clarify", "finish"]:
        """Route based on self-reflection results."""
        if state.get("needs_retry", False):
            return "retry"
        elif state.get("needs_clarification", False):
            return "clarify"
        else:
            return "finish"


"""
Streaming-enabled node implementations for the Study Agent.

This module provides streaming versions of all study agent nodes,
allowing token-by-token streaming throughout the entire workflow.
"""

import re
import json
import asyncio
from typing import Dict, Any, List, Optional, AsyncGenerator

from langchain_core.messages import HumanMessage, AIMessage, SystemMessage
from langchain.callbacks.streaming_stdout import StreamingStdOutCallbackHandler

from utils.patterns.streaming import (
    StreamingState, 
    StreamingIndicator,
    StreamingCallbackHandler
)


class StreamingStudyNodes:
    """Streaming-enabled node implementations for Study Agent."""
    
    def __init__(self, llm, streaming_llm, tool_map: Dict[str, Any]):
        """
        Initialize streaming study nodes.
        
        Args:
            llm: Regular LLM for non-streaming operations
            streaming_llm: Streaming-enabled LLM
            tool_map: Map of tool names to tool objects
        """
        self.llm = llm
        self.streaming_llm = streaming_llm
        self.tool_map = tool_map
    
    async def detect_complexity(self, state: StreamingState) -> StreamingState:
        """
        Detect if question requires multi-step planning.
        
        Args:
            state: Streaming state
            
        Returns:
            Updated state with complexity detection
        """
        # Signal processing
        await state.add_indicator(StreamingIndicator.THINKING, "Analyzing question complexity...")
        
        question = state.get("question", "").lower()
        
        # Check for multi-part indicators
        is_multi_part = any(ind in question for ind in [" and ", " also ", " then "])
        has_multiple_questions = question.count("?") > 1
        
        # Check for multi-tool requirements
        tools_mentioned = sum(1 for keywords in [
            ["document", "notes", "file"],
            ["search", "internet", "web"],
            ["code", "python", "execute"],
            ["animate", "animation", "video"]
        ] if any(k in question for k in keywords))
        
        is_complex = is_multi_part or has_multiple_questions or tools_mentioned > 1
        
        # Update state
        await state.update("original_question", state.get("original_question", state.get("question")), stream=False)
        await state.update("is_complex_task", is_complex, stream=False)
        await state.update("tools_used_history", state.get("tools_used_history", []), stream=False)
        
        # Signal completion with result
        complexity_type = "complex" if is_complex else "simple"
        await state.add_indicator(
            StreamingIndicator.COMPLETE, 
            f"Question analyzed as {complexity_type}"
        )
        
        return state
    
    async def plan_complex_task(self, state: StreamingState) -> StreamingState:
        """
        Create execution plan for complex tasks with streaming.
        
        Args:
            state: Streaming state
            
        Returns:
            Updated state with task plan
        """
        # Signal planning
        await state.add_indicator(StreamingIndicator.THINKING, "Planning task execution...")
        
        question = state.get("question", "")
        
        planning_prompt = f"""Break this complex question into executable steps:

Question: {question}

Available tools:
- Document_QA: Search documents
- Web_Search: Internet search
- Python_REPL: Execute code
- Manim_Animation: Create animations

Return JSON array:
[{{"step": 1, "description": "...", "tool": "..."}}, ...]

Keep it 2-4 steps maximum."""
        
        try:
            # Create streaming handler
            handler = StreamingCallbackHandler(state)
            
            # Stream thinking process
            await state.add_indicator(
                StreamingIndicator.PROCESSING, 
                "Creating execution plan..."
            )
            
            # Generate plan with streaming
            response = await self.streaming_llm.agenerate(
                [[HumanMessage(content=planning_prompt)]],
                callbacks=[handler]
            )
            
            content = response.generations[0][0].text.strip()
            
            # Extract JSON
            if "```json" in content:
                content = content.split("```json")[1].split("```")[0].strip()
            elif "```" in content:
                content = content.split("```")[1].split("```")[0].strip()
            
            # Parse plan
            plan = json.loads(content)
            
            # Update state
            await state.update("task_plan", plan, stream=False)
            await state.update("current_step", 0, stream=False)
            await state.update("completed_steps", [], stream=False)
            await state.update("intermediate_answers", [], stream=False)
            
            # Stream plan summary
            plan_summary = "\n".join([
                f"Step {step['step']}: {step['description']} (using {step['tool']})"
                for step in plan
            ])
            
            await state.add_indicator(
                StreamingIndicator.COMPLETE,
                f"Task plan created with {len(plan)} steps:\n{plan_summary}"
            )
            
            return state
            
        except Exception as e:
            # Handle planning failure
            await state.add_indicator(
                StreamingIndicator.ERROR,
                f"Planning failed: {str(e)}"
            )
            
            # Fallback to simple mode
            await state.update("task_plan", None, stream=False)
            await state.update("is_complex_task", False, stream=False)
            
            return state
    
    async def execute_plan(self, state: StreamingState) -> StreamingState:
        """
        Execute one step from the task plan with streaming.
        
        Args:
            state: Streaming state
            
        Returns:
            Updated state after executing step
        """
        plan = state.get("task_plan", [])
        current_step = state.get("current_step", 0)
        
        if not plan or current_step >= len(plan):
            return state
        
        step = plan[current_step]
        tool_name = step.get("tool", "")
        
        # Signal step execution
        await state.add_indicator(
            StreamingIndicator.TOOL_START,
            f"Executing step {current_step + 1}: {step.get('description', '')}"
        )
        
        # Map tool names to execution methods
        tool_executors = {
            "web_search": self._execute_web_search,
            "Web_Search": self._execute_web_search,
            "document_qa": self._execute_document_qa,
            "Document_QA": self._execute_document_qa,
            "python_repl": self._execute_python_repl,
            "Python_REPL": self._execute_python_repl,
            "manim_animation": self._execute_manim_animation,
            "Manim_Animation": self._execute_manim_animation,
        }
        
        if tool_name in tool_executors:
            # Execute tool with streaming
            await state.add_indicator(
                StreamingIndicator.PROCESSING,
                f"Using {tool_name} tool..."
            )
            
            # Call tool executor
            await tool_executors[tool_name](state)
            
            # Update intermediate results
            intermediate = state.get("intermediate_answers", [])
            intermediate.append({
                "step": current_step + 1,
                "description": step.get("description", ""),
                "tool": tool_name,
                "result": state.get("tool_result", "")
            })
            
            # Update history
            tools_used = state.get("tools_used_history", [])
            tools_used.append(tool_name)
            
            completed = state.get("completed_steps", [])
            completed.append(f"step_{current_step + 1}")
            
            # Update state
            await state.update("intermediate_answers", intermediate, stream=False)
            await state.update("tools_used_history", tools_used, stream=False)
            await state.update("completed_steps", completed, stream=False)
            await state.update("current_step", current_step + 1, stream=False)
            
            # Signal step completion
            await state.add_indicator(
                StreamingIndicator.TOOL_END,
                f"Completed step {current_step + 1}"
            )
        else:
            # Unknown tool
            await state.add_indicator(
                StreamingIndicator.ERROR,
                f"Unknown tool: {tool_name}"
            )
            await state.update("current_step", current_step + 1, stream=False)
        
        return state
    
    async def synthesize_results(self, state: StreamingState) -> StreamingState:
        """
        Synthesize multi-step results into final answer with streaming.
        
        Args:
            state: Streaming state
            
        Returns:
            Updated state with synthesized results
        """
        # Signal synthesis
        await state.add_indicator(
            StreamingIndicator.THINKING,
            "Synthesizing results from all steps..."
        )
        
        intermediate = state.get("intermediate_answers", [])
        question = state.get("question", "")
        
        if not intermediate:
            return state
        
        steps_context = "\n\n".join([
            f"Step {r['step']} ({r['tool']}): {r['result']}"
            for r in intermediate
        ])
        
        synthesis_prompt = f"""Synthesize these step-by-step results:

Question: {question}

Results:
{steps_context}

Provide a complete answer."""
        
        try:
            # Create streaming handler
            handler = StreamingCallbackHandler(state)
            
            # Stream synthesis
            await state.add_indicator(
                StreamingIndicator.PROCESSING,
                "Creating final answer..."
            )
            
            # Generate synthesis with streaming
            await self.streaming_llm.agenerate(
                [[HumanMessage(content=synthesis_prompt)]],
                callbacks=[handler]
            )
            
            # Get accumulated response
            final_answer = state.get("partial_response", "")
            
            # Update state
            await state.update("final_answer", final_answer, stream=False)
            await state.update("tool_result", final_answer, stream=False)
            
            # Add to messages
            messages = state.get("messages", [])
            await state.update("messages", messages + [AIMessage(content=final_answer)], stream=False)
            
            # Signal completion
            await state.add_indicator(
                StreamingIndicator.COMPLETE,
                "Synthesis complete"
            )
            
            return state
            
        except Exception as e:
            # Handle synthesis failure
            await state.add_indicator(
                StreamingIndicator.ERROR,
                f"Synthesis failed: {str(e)}"
            )
            
            # Use last result as fallback
            last_result = intermediate[-1]["result"] if intermediate else "No results"
            await state.update("final_answer", last_result, stream=False)
            await state.update("tool_result", last_result, stream=False)
            
            return state
    
    async def self_reflect(self, state: StreamingState) -> StreamingState:
        """
        Self-reflect on answer quality with streaming.
        
        Args:
            state: Streaming state
            
        Returns:
            Updated state with reflection results
        """
        # Signal reflection
        await state.add_indicator(
            StreamingIndicator.THINKING,
            "Evaluating answer quality..."
        )
        
        answer = state.get("final_answer") or state.get("tool_result", "")
        question = state.get("question", "")
        
        quality_issues = []
        confidence = 1.0
        
        if len(answer) < 50:
            quality_issues.append("Response too short")
            confidence -= 0.3
        
        error_indicators = ["error", "failed", "not found"]
        if any(ind in answer.lower() for ind in error_indicators):
            quality_issues.append("Contains errors")
            confidence -= 0.4
        
        confidence = max(0.0, min(1.0, confidence))
        needs_retry = confidence < 0.5 and state.get("iteration", 0) < state.get("max_iterations", 5)
        
        # Update state
        await state.update("response_confidence", confidence, stream=False)
        await state.update("quality_issues", quality_issues, stream=False)
        await state.update("needs_retry", needs_retry, stream=False)
        
        # Signal reflection result
        if needs_retry:
            await state.add_indicator(
                StreamingIndicator.RECOVERY,
                f"Quality issues detected: {', '.join(quality_issues)}. Retrying..."
            )
        else:
            quality_level = "high" if confidence > 0.8 else "acceptable" if confidence > 0.5 else "low"
            await state.add_indicator(
                StreamingIndicator.COMPLETE,
                f"Answer quality: {quality_level} ({confidence:.0%})"
            )
        
        return state
    
    async def _execute_document_qa(self, state: StreamingState) -> StreamingState:
        """
        Execute Document QA tool with streaming.
        
        Args:
            state: Streaming state
            
        Returns:
            Updated state with document QA results
        """
        tool = self.tool_map.get("Document_QA")
        if not tool:
            await state.update("tool_result", "Document QA not available", stream=True)
            await state.update("tried_document_qa", True, stream=False)
            await state.update("document_qa_failed", True, stream=False)
            return state
        
        try:
            # Signal document search
            await state.add_indicator(
                StreamingIndicator.PROCESSING,
                "Searching documents..."
            )
            
            # Retrieve relevant document chunks
            raw_results = tool.func(state.get("question", ""))
            
            # Check if retrieval failed
            failed = any(p in raw_results.lower() for p in [
                "no relevant content", "no documents found", "not found", "❌",
                "no documents", "please upload", "vector store"
            ])
            
            if failed:
                # Check if this is a "no documents available" situation
                if "no documents found" in raw_results.lower() or "please upload" in raw_results.lower():
                    clarification_message = (
                        "📚 No documents found in your library.\n\n"
                        "Would you like me to:\n"
                        "1. 🌐 Search the web for this information\n"
                        "2. ⏸️  Wait while you upload a document first\n\n"
                        "Please reply with 'search web' or 'upload document' (or just '1' or '2'):"
                    )
                    await state.update("tool_result", clarification_message, stream=True)
                    await state.update("tried_document_qa", True, stream=False)
                    await state.update("document_qa_failed", True, stream=False)
                    await state.update("needs_clarification", True, stream=False)
                    await state.update("awaiting_user_choice", True, stream=False)
                    return state
                
                await state.update("tool_result", raw_results, stream=True)
                await state.update("tried_document_qa", True, stream=False)
                await state.update("document_qa_failed", True, stream=False)
                return state
            
            # Detect if this is a study material generation request
            question_lower = state.get("question", "").lower()
            is_study_material = any(keyword in question_lower for keyword in [
                'flashcard', 'study guide', 'summary', 'summarize', 'mcq', 
                'multiple choice', 'quiz', 'practice questions'
            ])
            
            # Signal synthesis
            await state.add_indicator(
                StreamingIndicator.PROCESSING,
                "Synthesizing information from documents..."
            )
            
            # Prepare prompt based on request type
            if is_study_material:
                synthesis_prompt = f"""You are a study assistant creating educational materials from retrieved content.

Question: {state.get("question", "")}

Retrieved Content:
{raw_results}

Instructions:
1. Create the requested study material (flashcards, study guide, MCQ, etc.) based on the retrieved content
2. Use ONLY information from the retrieved content above
3. If the content is insufficient, clearly state what's missing
4. Cite page numbers when available: "(p. 42)"
5. Make the material comprehensive and well-organized
6. For flashcards: Format as "**Front:**" and "**Back:**" pairs
7. For study guides: Use clear headings and bullet points
8. For MCQs: Include question, options, and correct answer

Answer:"""
            else:
                synthesis_prompt = f"""You are a helpful study assistant. Answer the question concisely and clearly.

Question: {state.get("question", "")}

Retrieved Content:
{raw_results}

Instructions:
1. Provide a direct, focused answer to the question
2. Use ONLY information from the retrieved content above
3. Do NOT include chunk references like "[Chunk X]" - cite page numbers instead when available
4. If page numbers appear in the content (e.g., "[Page 42]"), cite them naturally: "(p. 42)"
5. Keep it concise - answer the question without extra elaboration
6. If the user wants more details, they can ask follow-up questions
7. Use clear, simple language and good formatting

Answer:"""
            
            # Create streaming handler
            handler = StreamingCallbackHandler(state)
            
            # Generate response with streaming
            await self.streaming_llm.agenerate(
                [[HumanMessage(content=synthesis_prompt)]],
                callbacks=[handler]
            )
            
            # Get accumulated response
            response_content = state.get("partial_response", "")
            
            # Check if LLM indicated content was insufficient/irrelevant
            response_lower = response_content.lower()
            insufficient = any(phrase in response_lower for phrase in [
                "does not contain", "do not contain", "no information about",
                "no information available", "there is no information",
                "provided content does not", "cannot answer",
                "not available about", "nothing about"
            ])
            
            # Also check for negative statements at the start of response
            if response_lower.strip().startswith(("based on the retrieved content, there is no", 
                                               "the retrieved content", "i cannot find")):
                insufficient = True
            
            if insufficient:
                # Ask user what they want to do instead of auto-searching
                clarification_message = (
                    "I couldn't find relevant information about this topic in your uploaded documents.\n\n"
                    "Would you like me to:\n"
                    "1. 🌐 Search the web for this information\n"
                    "2. ⏸️  Wait while you upload a document with this information\n\n"
                    "Please reply with 'search web' or 'upload document' (or just '1' or '2'):"
                )
                await state.update("tool_result", clarification_message, stream=True)
                await state.update("tried_document_qa", True, stream=False)
                await state.update("document_qa_failed", True, stream=False)
                await state.update("needs_clarification", True, stream=False)
                await state.update("awaiting_user_choice", True, stream=False)
                return state
            
            # Success - update state with result
            await state.update("tool_result", response_content, stream=False)
            await state.update("tried_document_qa", True, stream=False)
            await state.update("document_qa_failed", False, stream=False)
            
            return state
            
        except Exception as e:
            # Handle errors
            error_message = f"Error: {str(e)}"
            await state.update("tool_result", error_message, stream=True)
            await state.update("tried_document_qa", True, stream=False)
            await state.update("document_qa_failed", True, stream=False)
            
            return state
    
    async def _execute_web_search(self, state: StreamingState) -> StreamingState:
        """
        Execute Web Search tool with streaming.
        
        Args:
            state: Streaming state
            
        Returns:
            Updated state with web search results
        """
        tool = self.tool_map.get("Web_Search")
        if not tool:
            await state.update("tool_result", "Web search not available", stream=True)
            return state
        
        try:
            # Signal web search
            await state.add_indicator(
                StreamingIndicator.PROCESSING,
                "Searching the web..."
            )
            
            # Build conversation context for better understanding of follow-up questions
            messages = state.get("messages", [])
            context = ""
            
            # Include last 2-3 Q&A pairs for context
            if messages:
                recent_messages = []
                for msg in messages[-6:]:  # Last 6 messages = ~3 Q&A pairs
                    if hasattr(msg, 'content'):
                        role = "User" if hasattr(msg, 'type') and msg.type == 'human' else "Assistant"
                        recent_messages.append(f"{role}: {msg.content[:200]}")  # Limit to 200 chars
                
                if recent_messages:
                    context = f"\n\nConversation History:\n" + "\n".join(recent_messages)
            
            # Build search query with context if needed
            search_query = state.get("question", "")
            question_lower = search_query.lower()
            
            # For ambiguous follow-up questions (pronouns, "it", "that", etc.), 
            # enhance query with context from conversation
            has_pronoun = any(word in question_lower for word in [' it ', ' this ', ' that ', ' them ', ' these ', ' those '])
            has_ambiguous_phrase = any(phrase in question_lower for phrase in ['where is', 'how is', 'how does', 'who discovered', 'who invented', 'who created'])
            
            if has_pronoun or has_ambiguous_phrase:
                # Extract topic from recent messages
                if messages:
                    import re
                    for msg in reversed(messages[-4:]):
                        if hasattr(msg, 'type') and msg.type == 'human' and hasattr(msg, 'content'):
                            prev_question = msg.content.lower()
                            # Look for "what is X" pattern to extract topic
                            topic_match = re.search(r'what\s+(?:is|are)\s+([^?]+)', prev_question)
                            if topic_match:
                                topic = topic_match.group(1).strip()
                                
                                # For specific question types, replace pronoun with topic directly
                                if any(q in question_lower for q in ['who discovered', 'who invented', 'who created', 'who found', 
                                                                     'how does', 'how is', 'where is', 'when was']):
                                    # Replace "it" with the actual topic
                                    search_query = re.sub(r'\bit\b', topic, search_query, flags=re.IGNORECASE)
                                elif has_pronoun:
                                    # For questions with pronouns but not specific patterns
                                    search_query = re.sub(r'\bit\b', topic, search_query, flags=re.IGNORECASE)
                                else:
                                    # For other questions, add as context
                                    search_query = f"{search_query} {topic}"
                                break
            
            # Execute search
            await state.add_indicator(
                StreamingIndicator.PROCESSING,
                f"Searching for: {search_query}"
            )
            
            raw_results = tool.func(search_query)
            
            # Detect time-sensitive queries that need disclaimers
            is_time_sensitive = any(phrase in question_lower for phrase in [
                'current time', 'what time', 'time now', 'time in',
                'current date', 'what date', 'date today', 'today date',
                'current weather', 'weather now', 'weather today',
                'latest', 'breaking news', 'just happened'
            ])
            
            time_disclaimer = ""
            if is_time_sensitive:
                time_disclaimer = "\n\nIMPORTANT: Add a disclaimer that for real-time information (time, date, weather), the search results may be outdated or cached. Recommend checking a reliable real-time source directly (e.g., time.is, weather.com)."
            
            # Signal synthesis
            await state.add_indicator(
                StreamingIndicator.PROCESSING,
                "Synthesizing search results..."
            )
            
            synthesis_prompt = f"""Answer the question concisely and directly using the search results.

Question: {state.get("question", "")}{context}

Search Results:
{raw_results}{time_disclaimer}

Instructions:
1. Use conversation history to understand follow-up questions and pronouns (it, this, that)
2. Answer ONLY what was asked - no extra sections or elaboration
3. Be direct and concise (2-4 sentences max for definitions)
4. Use simple, clear language - avoid complex formatting
5. Cite ONLY high-quality, authoritative sources:
   - Prioritize: Wikipedia, .edu (universities), .gov (government), .org (established organizations)
   - Avoid: blogs, forums, random websites
   - Include MAXIMUM 4-6 sources
6. Format sources EXACTLY as: Sources: [1] Title - https://full-url.com, [2] Title - https://full-url.com
   - ALWAYS include the complete URL for each source
   - DO NOT write just titles without URLs
7. DO NOT include HTML tags or markdown links (use plain text URLs)
8. If the user wants more details, they will ask a follow-up question

Answer:"""
            
            # Create streaming handler
            handler = StreamingCallbackHandler(state)
            
            # Generate response with streaming
            await self.streaming_llm.agenerate(
                [[HumanMessage(content=synthesis_prompt)]],
                callbacks=[handler]
            )
            
            # Get accumulated response
            response_content = state.get("partial_response", "")
            
            # Update state with result
            await state.update("tool_result", response_content, stream=False)
            
            return state
            
        except Exception as e:
            # Handle errors
            error_message = f"Search error: {str(e)}"
            await state.update("tool_result", error_message, stream=True)
            
            return state
    
    async def _execute_python_repl(self, state: StreamingState) -> StreamingState:
        """
        Execute Python REPL tool with streaming.
        
        Args:
            state: Streaming state
            
        Returns:
            Updated state with Python REPL results
        """
        tool = self.tool_map.get("Python_REPL")
        if not tool:
            await state.update("tool_result", "Python REPL not available", stream=True)
            return state
        
        try:
            # Signal code execution
            await state.add_indicator(
                StreamingIndicator.PROCESSING,
                "Executing Python code..."
            )
            
            question = state.get("question", "")
            
            if "print" not in question.lower() and any(op in question for op in ['+', '-', '*', '/']):
                code = f"print({question})"
            else:
                code = question
            
            # Show code being executed
            await state.update("executing_code", code, stream=True)
            
            # Execute code
            result = tool.func(code)
            
            # Update state with result
            await state.update("tool_result", str(result), stream=True)
            
            return state
            
        except Exception as e:
            # Handle errors
            error_message = f"Execution error: {str(e)}"
            await state.update("tool_result", error_message, stream=True)
            
            return state
    
    async def _execute_manim_animation(self, state: StreamingState) -> StreamingState:
        """
        Execute Manim Animation tool with streaming.
        
        Args:
            state: Streaming state
            
        Returns:
            Updated state with animation results
        """
        tool = self.tool_map.get("render_manim_video")
        if not tool:
            await state.update(
                "tool_result", 
                "Manim animation tool not available. Please ensure Manim is installed.", 
                stream=True
            )
            return state
        
        try:
            # Signal animation generation
            await state.add_indicator(
                StreamingIndicator.PROCESSING,
                "Generating animation..."
            )
            
            question = state.get("question", "")
            
            # Extract topic from question
            import re
            topic = re.sub(r'\b(please|animate|animation|visualize|create|generate|show|me|an?|the|video|of)\b', '', question, flags=re.IGNORECASE)
            topic = topic.strip()
            
            if not topic:
                topic = question
            
            # Show animation topic
            await state.update("animation_topic", topic, stream=True)
            
            # Generate animation (this can take time)
            await state.add_indicator(
                StreamingIndicator.PROCESSING,
                f"Creating animation for: {topic} (this may take 30-60 seconds)..."
            )
            
            result = tool.func(topic)
            
            # Parse JSON result
            try:
                import json
                result_data = json.loads(result)
                content = result_data.get("content", "")
                artifact = result_data.get("artifact")
                
                if artifact:
                    final_result = f"{content}\n\n📹 Video saved to: {artifact}"
                    # Show video path
                    await state.update("video_path", artifact, stream=True)
                else:
                    final_result = content
                
                # Update state with result
                await state.update("tool_result", final_result, stream=True)
                
            except json.JSONDecodeError:
                # Fallback if result is not JSON
                await state.update("tool_result", str(result), stream=True)
            
            return state
            
        except Exception as e:
            # Handle errors
            error_message = f"Animation error: {str(e)}"
            await state.update("tool_result", error_message, stream=True)
            
            return state

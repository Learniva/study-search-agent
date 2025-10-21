"""
Streaming-enabled node implementations for the Study Agent.

This module provides streaming versions of all study agent nodes,
allowing token-by-token streaming throughout the entire workflow.

PERFORMANCE OPTIMIZATIONS:
- Fast-path routing with pattern matching (no LLM calls)
- Smart query caching with TTL
- Progressive result streaming
- Instant user feedback
"""

import re
import json
import asyncio
import time
from typing import Dict, Any, List, Optional, AsyncGenerator

from langchain_core.messages import HumanMessage, AIMessage, SystemMessage
from langchain.callbacks.streaming_stdout import StreamingStdOutCallbackHandler

from utils.patterns.streaming import (
    StreamingState, 
    StreamingIndicator,
    StreamingCallbackHandler
)
from utils.monitoring import get_logger

logger = get_logger(__name__)


class StreamingStudyNodes:
    """
    Streaming-enabled node implementations for Study Agent.
    
    Features:
    - Token-by-token streaming
    - Fast pattern-based routing
    - Smart caching for repeated queries
    - Progressive result disclosure
    """
    
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
        
        # Performance optimizations
        self._query_cache = {}  # In-memory cache for frequent queries
        self._max_cache_size = 100
        self._cache_ttl = 300  # 5 minutes
    
    def _fast_classify(self, question_lower: str) -> str:
        """
        Fast pattern-based classification - NO LLM calls.
        
        Returns tool name in 10-20ms instead of 1-2s.
        
        Args:
            question_lower: Lowercase question string
            
        Returns:
            Tool name to use
        """
        # Document QA patterns (most specific - check first)
        if any(word in question_lower for word in [
            'document', 'uploaded', 'notes', 'my notes', 'file', 'pdf',
            'chapter', 'section', 'page', 'book', 'textbook'
        ]):
            return "document_qa"
        
        # Code/Python patterns
        if any(word in question_lower for word in [
            'code', 'calculate', 'compute', 'python', 'execute',
            'run', 'program', '+', '-', '*', '/', '='
        ]):
            return "python_repl"
        
        # Animation patterns
        if any(phrase in question_lower for phrase in [
            'animate ', 'animation', 'visualize', 'create video',
            'generate video', 'make video', 'show animation'
        ]):
            return "manim_animation"
        
        # Default to web search
        return "web_search"
    
    def _get_from_cache(self, key: str) -> Optional[str]:
        """Get result from cache if available and not expired."""
        if key in self._query_cache:
            cached_data = self._query_cache[key]
            timestamp = cached_data.get("timestamp", 0)
            
            # Check if expired
            if time.time() - timestamp < self._cache_ttl:
                return cached_data.get("result")
            else:
                # Expired - remove
                del self._query_cache[key]
        
        return None
    
    def _add_to_cache(self, key: str, result: str):
        """Add result to cache with TTL."""
        # Simple cache size management
        if len(self._query_cache) >= self._max_cache_size:
            # Remove oldest entry
            oldest_key = min(self._query_cache.keys(), 
                           key=lambda k: self._query_cache[k].get("timestamp", 0))
            del self._query_cache[oldest_key]
        
        self._query_cache[key] = {
            "result": result,
            "timestamp": time.time()
        }
        
        logger.info(f"📦 Cached result for key: {key[:50]}...")
    
    async def _progressive_synthesis(
        self, 
        state: StreamingState, 
        content_chunks: List[str], 
        question: str,
        min_chunks: int = 5
    ) -> str:
        """
        Progressive synthesis - start generating answer as soon as we have enough chunks.
        
        OPTIMIZATION: Don't wait for ALL chunks - start synthesis with first N chunks.
        
        Args:
            state: Streaming state
            content_chunks: List of content chunks
            question: User's question
            min_chunks: Minimum chunks needed to start synthesis
            
        Returns:
            Synthesized response
        """
        if len(content_chunks) < min_chunks:
            # Not enough chunks yet, wait for more
            logger.info(f"⏳ Waiting for more chunks ({len(content_chunks)}/{min_chunks})")
            return None
        
        # We have enough chunks to start synthesis
        logger.info(f"⚡ Progressive synthesis starting with {len(content_chunks)} chunks")
        
        partial_content = "\n\n".join(content_chunks[:min_chunks])
        
        synthesis_prompt = f"""Provide a comprehensive answer based on available information:

Question: {question}

Available Content:
{partial_content}

Note: More information may be available, but provide the best answer you can with this content.

Answer:"""
        
        # Stream synthesis
        handler = StreamingCallbackHandler(state)
        await self.streaming_llm.agenerate(
            [[HumanMessage(content=synthesis_prompt)]],
            callbacks=[handler]
        )
        
        return state.get("partial_response", "")
    
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
        Execute Document QA tool with streaming and caching.
        
        OPTIMIZATIONS:
        - Cache check for instant response on repeated queries
        - Progressive streaming of results
        
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
            question = state.get("question", "")
            
            # Check cache first (instant if cached)
            cache_key = f"doc_qa:{question}"
            cached_result = self._get_from_cache(cache_key)
            
            if cached_result:
                logger.info("⚡ Cache hit - instant document QA response!")
                await state.add_indicator(
                    StreamingIndicator.PROCESSING,
                    "📦 Retrieved from cache (instant)"
                )
                await state.update("tool_result", cached_result, stream=True)
                await state.update("tried_document_qa", True, stream=False)
                await state.update("document_qa_failed", False, stream=False)
                return state
            
            # Not cached - proceed with search
            # Signal document search
            await state.add_indicator(
                StreamingIndicator.PROCESSING,
                "Searching documents..."
            )
            
            # Build conversation history in parallel with other operations
            messages = state.get("messages", [])
            question_lower = state.get("question", "").lower()
            
            # Create parallel tasks for conversation history and chunk limit determination
            async def build_conversation_history():
                """Build conversation history for context."""
                if not messages:
                    return ""
                
                user_messages = []
                for msg in reversed(messages[-8:]):
                    if hasattr(msg, 'type') and msg.type == 'human' and hasattr(msg, 'content'):
                        user_messages.append(msg.content)
                        if len(user_messages) >= 4:
                            break
                
                conversation_history = " ".join(reversed(user_messages))
                print(f"📝 [DOC QA CONTEXT] Conversation history: {conversation_history[:150]}...")
                return conversation_history
            
            async def determine_chunk_limit():
                """Determine optimal chunk limit based on query type."""
                if any(keyword in question_lower for keyword in [
                    'chapter', 'section', 'structured notes', 'generate notes', 
                    'all about', 'overview', 'entire', 'whole', 'complete'
                ]):
                    chunk_limit = 60
                    print(f"📚 [COMPREHENSIVE RETRIEVAL] Chapter/overview request - retrieving {chunk_limit} chunks")
                else:
                    chunk_limit = 15
                    print(f"📄 [STANDARD RETRIEVAL] Specific question - retrieving {chunk_limit} chunks")
                return chunk_limit
            
            # Execute in parallel
            start_parallel = time.time()
            conversation_history, chunk_limit = await asyncio.gather(
                build_conversation_history(),
                determine_chunk_limit()
            )
            parallel_time = (time.time() - start_parallel) * 1000
            logger.info(f"⚡ Parallel prep: {parallel_time:.1f}ms")
            
            # Retrieve relevant document chunks with context awareness and appropriate limit
            # OPTIMIZATION: Use asyncio.to_thread for blocking I/O operation
            retrieval_start = time.time()
            raw_results = await asyncio.to_thread(
                tool.func,
                state.get("question", ""),
                limit=chunk_limit,
                conversation_history=conversation_history
            )
            retrieval_time = (time.time() - retrieval_start) * 1000
            logger.info(f"📊 Document retrieval: {retrieval_time:.1f}ms")
            
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
            
            # Detect request type
            question_lower = state.get("question", "").lower()
            
            # Check if this is a STRUCTURED NOTES generation request
            is_structured_notes = any(keyword in question_lower for keyword in [
                'structured notes', 'generate notes', 'create notes', 'make notes',
                'note-taking', 'organize notes', 'format notes'
            ])
            
            # Check if this is a chapter/section overview request
            is_chapter_overview = any(keyword in question_lower for keyword in [
                'chapter', 'section', 'all about', 'overview', 'covers', 'discusses'
            ]) and not is_structured_notes  # Don't overlap with structured notes
            
            # Check if this is a study material generation request
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
            if is_structured_notes:
                synthesis_prompt = f"""You are an expert note-taker creating HIGHLY STRUCTURED, PROFESSIONAL study notes from retrieved content.

Question: {state.get("question", "")}

Retrieved Content:
{raw_results}

MANDATORY STRUCTURE - Follow this EXACT order:

# [Chapter/Topic Title]

## 📋 BRIEF SUMMARY
[MUST BE FIRST - 2-3 sentences explaining what this chapter/document is about overall]

## 🎯 KEY TOPICS AND CONCEPTS
[List the main topics covered, using bullet points with **bold** formatting]
• **Topic 1**: Brief description (p. XX)
• **Topic 2**: Brief description (p. XX)
• **Topic 3**: Brief description (p. XX)

## 💻 CODE & ALGORITHMS
[ONLY include if code or algorithms are present in the content]
### Algorithm/Code Name (p. XX)
• **Purpose**: What it does
• **Key Steps**: 
  1. Step 1
  2. Step 2
• **Code Example** (if available):
  ```language
  code here
  ```

## 📚 DETAILED CONTENT

### Section 1: [Name] (p. XX)
[Detailed explanation with **bold key concepts**]

**Key Points:**
• Point 1 (p. XX)
• Point 2 (p. XX)

**Important Definitions:**
• **Term**: Definition (p. XX)

### Section 2: [Name] (p. XX)
[Continue with clear subsections...]

## 🔧 CONCEPTS AND USE CASES

### Concept: [Name]
• **What it is**: Definition/explanation (p. XX)
• **Why it matters**: Practical significance
• **Use Cases**:
  - Use case 1 (p. XX)
  - Use case 2 (p. XX)
• **Real-world Applications**: [If mentioned]

## 💡 KEY TAKEAWAYS
[3-5 bullet points summarizing the most important lessons]
• Key takeaway 1
• Key takeaway 2
• Key takeaway 3

## 📖 PAGE REFERENCES
[List all page numbers covered: pp. XX-XX]

---

FORMATTING RULES:
1. Use markdown hierarchy: # ## ### for headings
2. **Bold** all key terms and concepts
3. Include page citations after every major point: (p. XX)
4. Use bullet points (•) for lists
5. Use numbered lists (1. 2. 3.) for sequential steps
6. Format code in ```language``` blocks
7. Use clear spacing between sections
8. Make it visually scannable
9. Use ONLY information from the retrieved content
10. Be comprehensive but organized

Answer:"""
            elif is_study_material:
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
            elif is_chapter_overview:
                synthesis_prompt = f"""You are a helpful study assistant providing comprehensive chapter/section summaries.

Question: {state.get("question", "")}

Retrieved Content:
{raw_results}

Instructions:
1. Provide a COMPREHENSIVE summary (1-2 paragraphs minimum, 4-8 sentences)
2. Include the main topic/theme of the chapter/section
3. List the key concepts, subtopics, or techniques covered
4. Mention specific examples, algorithms, or applications if present in the content
5. Use ONLY information from the retrieved content above
6. Cite page numbers naturally when available: "(p. 42)" or "(pp. 42-45)"
7. Use clear paragraph structure with good flow
8. Do NOT say "the retrieved content" or "according to the document" - just present the information directly
9. Make it comprehensive enough that the reader gets a solid understanding of what the chapter/section covers

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
5. Provide a comprehensive answer with at least 2-3 sentences. Explain concepts thoroughly with relevant context
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
            
            # Success - update state with result and cache it
            await state.update("tool_result", response_content, stream=False)
            await state.update("tried_document_qa", True, stream=False)
            await state.update("document_qa_failed", False, stream=False)
            
            # Cache the result for future queries
            self._add_to_cache(cache_key, response_content)
            
            return state
            
        except Exception as e:
            # Handle errors
            error_message = f"Error: {str(e)}"
            await state.update("tool_result", error_message, stream=True)
            await state.update("tried_document_qa", True, stream=False)
            await state.update("document_qa_failed", True, stream=False)
            
            return state
    
    def _extract_main_topic_from_conversation(self, messages: list) -> str:
        """
        Advanced topic extraction from conversation history.
        Uses multiple strategies to identify the main subject being discussed.
        """
        import re
        
        # Strategy 1: Look for explicit topic declarations in recent messages
        for msg in reversed(messages[-8:]):  # Look at last 8 messages (4 Q&A pairs)
            # Handle both dict format {'role': 'user'} and object format (msg.type)
            if isinstance(msg, dict):
                msg_role = msg.get('role', '')
                msg_content = msg.get('content', '')
            elif hasattr(msg, 'type') and hasattr(msg, 'content'):
                msg_role = 'user' if msg.type == 'human' else msg.type
                msg_content = msg.content
            else:
                continue
                
            if msg_role in ['user', 'human']:
                content = msg_content.lower()
                
                # Pattern 1: "What is/are [TOPIC]?"
                match = re.search(r'what\s+(?:is|are)\s+(?:a|an|the)?\s*([^?,.!]+?)(?:\?|$)', content)
                if match:
                    topic = match.group(1).strip()
                    # Filter out too-short or generic topics
                    if len(topic.split()) >= 2 or len(topic) > 5:
                        return self._clean_topic(topic)
                
                # Pattern 2: "Tell me about [TOPIC]"
                match = re.search(r'tell\s+me\s+(?:about|more about)\s+([^?,.!]+)', content)
                if match:
                    return self._clean_topic(match.group(1))
                
                # Pattern 3: "Explain [TOPIC]"
                match = re.search(r'explain\s+(?:the\s+)?([^?,.!]+)', content)
                if match:
                    topic = match.group(1).strip()
                    if len(topic.split()) >= 2:
                        return self._clean_topic(topic)
                
                # Pattern 4: "How do/does [TOPIC] work?"
                match = re.search(r'how\s+(?:do|does)\s+([^?,.!]+?)\s+work', content)
                if match:
                    return self._clean_topic(match.group(1))
                
                # Pattern 5: Extract capitalized terms (might be proper nouns)
                capitalized = re.findall(r'\b[A-Z][a-z]+(?:\s+[A-Z][a-z]+)*\b', msg.content)
                if capitalized and len(capitalized[0].split()) >= 2:
                    return self._clean_topic(capitalized[0].lower())
        
        # Strategy 2: Look for recurring keywords (mentioned multiple times)
        word_freq = {}
        stop_words = {'what', 'is', 'are', 'the', 'a', 'an', 'how', 'why', 'when', 'where', 'who',
                      'do', 'does', 'did', 'can', 'could', 'should', 'would', 'will', 'about',
                      'tell', 'me', 'explain', 'please', 'help', 'thanks', 'thank', 'you'}
        
        for msg in reversed(messages[-8:]):
            if hasattr(msg, 'type') and msg.type == 'human' and hasattr(msg, 'content'):
                words = msg.content.lower().split()
                for word in words:
                    cleaned = re.sub(r'[^a-z\s]', '', word)
                    if cleaned and len(cleaned) > 3 and cleaned not in stop_words:
                        word_freq[cleaned] = word_freq.get(cleaned, 0) + 1
        
        # Get most frequent non-stop word
        if word_freq:
            most_common = max(word_freq.items(), key=lambda x: x[1])
            if most_common[1] >= 2:  # Mentioned at least twice
                return most_common[0]
        
        return ""
    
    def _clean_topic(self, topic: str) -> str:
        """Clean and normalize extracted topic."""
        import re
        # Remove leading/trailing punctuation
        topic = topic.strip(' ,.!?:;-')
        # Remove filler phrases
        topic = re.sub(r'\b(to be|to do|to have|to make)\b', '', topic)
        topic = re.sub(r'\s+', ' ', topic)  # Normalize spaces
        return topic.strip()
    
    def _reformulate_query_intelligently(self, question: str, topic: str) -> str:
        """
        Intelligently reformulate query based on question type and context.
        """
        import re
        question_lower = question.lower()
        
        # Question type detection and reformulation
        reformulation_patterns = [
            # Possessive pronoun patterns (more specific, check first)
            (r'(?:what|which)\s+(?:are|is)\s+(?:some\s+of\s+)?its\s+branches', f"branches of {topic}"),
            (r'(?:what|which)\s+(?:are|is)\s+(?:some\s+of\s+)?its\s+types', f"types of {topic}"),
            (r'(?:what|which)\s+(?:are|is)\s+(?:some\s+of\s+)?its\s+applications', f"applications of {topic}"),
            (r'(?:what|which)\s+(?:are|is)\s+(?:some\s+of\s+)?its\s+uses', f"uses of {topic}"),
            (r'(?:what|which)\s+(?:are|is)\s+(?:some\s+of\s+)?its\s+benefits', f"benefits of {topic}"),
            (r'(?:what|which)\s+(?:are|is)\s+(?:some\s+of\s+)?its\s+features', f"features of {topic}"),
            (r'(?:what|which)\s+(?:are|is)\s+(?:some\s+of\s+)?its\s+advantages', f"advantages of {topic}"),
            (r'(?:what|which)\s+(?:are|is)\s+its\s+', f"aspects of {topic}"),
            
            # Company/Organization queries
            (r'what\s+companies\s+(?:have|use|make|build|develop|own)', f"companies with {topic}"),
            (r'which\s+companies\s+(?:have|use|make|build|develop|own)', f"companies with {topic}"),
            (r'who\s+(?:makes|builds|develops|manufactures|produces)\s+(?:it|them|these|those)', f"companies that make {topic}"),
            (r'who\s+has\s+(?:it|them|these|those)', f"companies and organizations with {topic}"),
            (r'which\s+organizations\s+(?:have|use)', f"organizations using {topic}"),
            
            # Inventor/Creator queries
            (r'who\s+(?:invented|created|discovered|founded)\s+(?:it|them|this|that)', f"who invented {topic}"),
            (r'who\s+is\s+the\s+inventor\s+of\s+(?:it|them)', f"inventor of {topic}"),
            
            # How/Why/When queries with pronouns
            (r'how\s+(?:does|do|did)\s+(?:it|they|this|that)\s+work', f"how {topic} works"),
            (r'why\s+(?:is|are|was|were)\s+(?:it|they|this|that)\s+important', f"why {topic} is important"),
            (r'when\s+(?:was|were)\s+(?:it|they|this|that)\s+(?:invented|created|discovered)', f"when was {topic} invented"),
            (r'where\s+(?:is|are|was|were)\s+(?:it|they|this|that)', f"where is {topic}"),
            
            # Benefits/Advantages queries
            (r'what\s+(?:are|is)\s+the\s+(?:benefits|advantages|pros)\s+of\s+(?:it|them)', f"benefits of {topic}"),
            (r'why\s+(?:should|would)\s+(?:we|i|people)\s+use\s+(?:it|them)', f"advantages of using {topic}"),
            
            # Applications/Use cases
            (r'what\s+(?:can|could)\s+(?:it|they)\s+(?:be used for|do)', f"applications of {topic}"),
            (r'where\s+(?:is|are)\s+(?:it|they)\s+used', f"applications and uses of {topic}"),
        ]
        
        # Try each pattern
        for pattern, replacement in reformulation_patterns:
            if re.search(pattern, question_lower):
                return replacement
        
        # Generic pronoun replacement if no specific pattern matches
        pronouns = ['it', 'them', 'this', 'that', 'these', 'those']
        for pronoun in pronouns:
            if f' {pronoun} ' in f' {question_lower} ':
                question = re.sub(rf'\b{pronoun}\b', topic, question, flags=re.IGNORECASE)
                return question
        
        # If no reformulation, append topic as context
        return f"{question} {topic}"
    
    async def _execute_web_search(self, state: StreamingState) -> StreamingState:
        """
        Execute Web Search tool with streaming and caching.
        
        OPTIMIZATIONS:
        - Cache check for instant response on repeated queries
        - Progressive streaming of results
        
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
            question = state.get("question", "")
            
            # Check cache first (instant if cached)
            cache_key = f"web_search:{question}"
            cached_result = self._get_from_cache(cache_key)
            
            if cached_result:
                logger.info("⚡ Cache hit - instant web search response!")
                await state.add_indicator(
                    StreamingIndicator.PROCESSING,
                    "📦 Retrieved from cache (instant)"
                )
                await state.update("tool_result", cached_result, stream=True)
                return state
            
            # Not cached - proceed with search
            # Signal web search
            await state.add_indicator(
                StreamingIndicator.PROCESSING,
                "Searching the web..."
            )
            
            # Parallel query analysis and reformulation
            messages = state.get("messages", [])
            search_query = state.get("question", "")
            question_lower = search_query.lower()
            
            print(f"\n{'='*70}")
            print(f"🔍 INTELLIGENT WEB SEARCH (OPTIMIZED)")
            print(f"{'='*70}")
            print(f"📝 Original question: '{search_query}'")
            
            async def analyze_and_reformulate():
                """Analyze query and reformulate if needed (parallel execution)."""
                # Advanced context detection
                has_pronoun = any(f' {word} ' in f' {question_lower} ' for word in 
                                ['it', 'its', 'this', 'that', 'them', 'these', 'those', 'they', 'their'])
                
                has_contextual_query = any(phrase in question_lower for phrase in [
                    'what companies', 'which companies', 'who makes', 'who has', 'who discovered',
                    'who invented', 'who created', 'how does', 'how did', 'why is', 'why are',
                    'when was', 'when were', 'where is', 'where are', 'what are the benefits',
                    'what are the advantages', 'what can', 'where is it used'
                ])
                
                is_short_followup = len(search_query.split()) <= 6 and (has_pronoun or has_contextual_query)
                
                print(f"🎯 Context needed: {has_pronoun or has_contextual_query or is_short_followup}")
                
                final_query = search_query
                if (has_pronoun or has_contextual_query or is_short_followup) and messages:
                    extracted_topic = self._extract_main_topic_from_conversation(messages)
                    
                    if extracted_topic:
                        print(f"💡 Extracted topic: '{extracted_topic}'")
                        final_query = self._reformulate_query_intelligently(search_query, extracted_topic)
                        print(f"✨ Reformulated query: '{final_query}'")
                    else:
                        print(f"⚠️  Could not extract topic from conversation")
                else:
                    print(f"✅ Direct question - no reformulation needed")
                
                return final_query
            
            async def detect_time_sensitivity():
                """Detect if query is time-sensitive (parallel execution)."""
                return any(phrase in question_lower for phrase in [
                    'current time', 'what time', 'time now', 'time in',
                    'current date', 'what date', 'date today', 'today date',
                    'current weather', 'weather now', 'weather today',
                    'latest', 'breaking news', 'just happened'
                ])
            
            # Execute analysis in parallel
            start_analysis = time.time()
            final_search_query, is_time_sensitive = await asyncio.gather(
                analyze_and_reformulate(),
                detect_time_sensitivity()
            )
            analysis_time = (time.time() - start_analysis) * 1000
            logger.info(f"⚡ Query analysis (parallel): {analysis_time:.1f}ms")
            
            if final_search_query != search_query:
                await state.add_indicator(
                    StreamingIndicator.PROCESSING,
                    f"Reformulated: {final_search_query}"
                )
            
            print(f"{'='*70}\n")
            
            # Execute search with reformulated query (non-blocking)
            await state.add_indicator(
                StreamingIndicator.PROCESSING,
                f"Searching for: {final_search_query}"
            )
            
            search_start = time.time()
            raw_results = await asyncio.to_thread(tool.func, final_search_query)
            search_time = (time.time() - search_start) * 1000
            logger.info(f"🔍 Web search execution: {search_time:.1f}ms")
            
            # Debug: Print raw search results to verify URLs are present
            print(f"\n{'='*70}")
            print(f"📋 RAW SEARCH RESULTS (for debugging URL extraction):")
            print(f"{'='*70}")
            print(raw_results[:1000] if len(raw_results) > 1000 else raw_results)
            print(f"{'='*70}\n")
            
            # Use the is_time_sensitive flag from parallel analysis
            time_disclaimer = ""
            if is_time_sensitive:
                time_disclaimer = "\n\nIMPORTANT: Add a disclaimer that for real-time information (time, date, weather), the search results may be outdated or cached. Recommend checking a reliable real-time source directly (e.g., time.is, weather.com)."
            
            # Signal synthesis
            await state.add_indicator(
                StreamingIndicator.PROCESSING,
                "Synthesizing search results..."
            )
            
            synthesis_prompt = f"""Answer the question comprehensively and informatively using the search results.

Question: {state.get("question", "")}

Search Results:
{raw_results}{time_disclaimer}

Instructions:
1. Use conversation history to understand follow-up questions and pronouns (it, this, that)
2. Provide a DETAILED, comprehensive answer (minimum 4-6 sentences, ideally 6-10 sentences for complex topics)
3. Cover multiple aspects of the topic and include relevant context, examples, and explanations
4. Make the response educational and informative - help the user truly understand the subject
5. Use clear, engaging language with good paragraph structure - write naturally without inline citation numbers
6. **CRITICAL - NO INLINE CITATION NUMBERS:**
   - DO NOT use inline citations like [1], [2], [1, 3] anywhere in your answer text
   - Write naturally and continuously without interrupting the flow with numbers
   - Present information as a cohesive, well-structured explanation
   - Prioritize: Wikipedia, .edu (universities), .gov (government), .org (established organizations)
   - Avoid: blogs, forums, random websites
   - Include MAXIMUM 4-6 sources
7. **SOURCES SECTION (REQUIRED AT THE END):**
   
   After your answer, add a "**Sources**" section with clean, readable citations.
   
   The search results above are formatted like this:
   ```
   1. Computer Science - Wikipedia
      Computer science is the study of...
      Source: https://en.wikipedia.org/wiki/Computer_science
   ```
   
   **Format your sources cleanly without showing URLs:**
   
   Example citations:
   ```
   **Sources**
   
   * Computer Science – Wikipedia
   * Fundamentals of Algorithms – GeeksforGeeks
   * Machine Learning Explained – MIT Sloan
   ```
   
   - Use asterisk (*) before each source
   - Include source title and website name ONLY (no URLs)
   - Use an en-dash (–) to separate title from website
   - One source per line (no blank lines between sources)
   - Include ONLY high-quality sources (Wikipedia, .edu, .gov, .org - avoid blogs/forums)
   - Maximum 4-6 sources
   - Keep it clean and readable
   
8. DO NOT include URLs, HTML tags, or markdown links in the sources section
9. If relevant, mention related concepts, applications, or recent developments to enrich understanding

Format:
[Your comprehensive answer here - no citation numbers in the text]

**Sources**

* [Source 1 title] – [Website]
* [Source 2 title] – [Website]

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
            
            # Update state with result and cache it
            await state.update("tool_result", response_content, stream=False)
            
            # Cache the result for future queries
            self._add_to_cache(cache_key, response_content)
            
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

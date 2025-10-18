"""LangGraph nodes for Study Agent."""

from typing import Dict, Any
from langchain_core.messages import HumanMessage, AIMessage, SystemMessage

from .state import StudyAgentState
from utils import MAX_AGENT_ITERATIONS


class StudyAgentNodes:
    """LangGraph node implementations for Study Agent."""
    
    def __init__(self, llm, tool_map: Dict[str, Any]):
        self.llm = llm
        self.tool_map = tool_map
    
    def check_user_choice(self, state: StudyAgentState) -> StudyAgentState:
        """Check if user is responding to a choice prompt (web search vs upload)."""
        question = state["question"].lower().strip()
        messages = state.get("messages", [])
        
        # Check if the last AI message was a clarification prompt
        last_ai_message = None
        for msg in reversed(messages):
            if hasattr(msg, 'type') and msg.type == 'ai':
                last_ai_message = msg.content.lower() if hasattr(msg, 'content') else ""
                break
        
        # Only treat as choice if last message was our clarification prompt
        is_clarification_context = (
            last_ai_message and 
            ("would you like me to" in last_ai_message or 
             "search the web" in last_ai_message and "upload" in last_ai_message)
        )
        
        if not is_clarification_context:
            # Not responding to our prompt - treat as normal question
            return state
        
        # Now check if this is a response to our clarification question
        # Detect: "1", "2", "search web", "web search", "upload", "upload document"
        is_web_search = any(phrase in question for phrase in [
            "search web", "web search", "search the web", "1", "yes", "sure", "ok", "search"
        ]) and len(question) < 50  # Short responses only
        
        is_upload = any(phrase in question for phrase in [
            "upload", "upload document", "2", "wait", "no", "later"
        ]) and len(question) < 50
        
        if is_web_search:
            print("✅ User chose: Search the web")
            return {
                **state,
                "user_choice_web_search": True,
                "awaiting_user_choice": False,
                "tool_used": "Web_Search"
            }
        elif is_upload:
            print("✅ User chose: Upload document")
            return {
                **state,
                "user_choice_upload": True,
                "awaiting_user_choice": False,
                "tool_result": "Please upload your document using the API endpoint: POST /documents/upload\n\nOnce uploaded, feel free to ask your question again!"
            }
        
        # Not a clear choice - treat as new question
        return state
    
    def detect_complexity(self, state: StudyAgentState) -> StudyAgentState:
        """Detect if question requires multi-step planning."""
        question = state["question"].lower()
        
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
        
        return {
            **state,
            "original_question": state.get("original_question", state["question"]),
            "is_complex_task": is_complex,
            "tools_used_history": state.get("tools_used_history", [])
        }
    
    def plan_complex_task(self, state: StudyAgentState) -> StudyAgentState:
        """Create execution plan for complex tasks."""
        question = state["question"]
        
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
            import json
            response = self.llm.invoke([HumanMessage(content=planning_prompt)])
            content = response.content.strip()
            
            if "```json" in content:
                content = content.split("```json")[1].split("```")[0].strip()
            elif "```" in content:
                content = content.split("```")[1].split("```")[0].strip()
            
            plan = json.loads(content)
            
            return {
                **state,
                "task_plan": plan,
                "current_step": 0,
                "completed_steps": [],
                "intermediate_answers": []
            }
        except Exception:
            return {**state, "task_plan": None, "is_complex_task": False}
    
    def execute_plan(self, state: StudyAgentState) -> StudyAgentState:
        """Execute one step from the task plan."""
        plan = state.get("task_plan", [])
        current_step = state.get("current_step", 0)
        
        if not plan or current_step >= len(plan):
            return state
        
        step = plan[current_step]
        tool_name = step.get("tool", "")
        
        # Map tool names to execution methods
        tool_executors = {
            "web_search": self._execute_web_search,
            "Web_Search": self._execute_web_search,
            "document_qa": self._execute_document_qa,
            "Document_QA": self._execute_document_qa,
            "python_repl": self._execute_python_repl,
            "Python_REPL": self._execute_python_repl,
        }
        
        if tool_name in tool_executors:
            result_state = tool_executors[tool_name](state)
            
            intermediate = state.get("intermediate_answers", [])
            intermediate.append({
                "step": current_step + 1,
                "description": step.get("description", ""),
                "tool": tool_name,
                "result": result_state.get("tool_result", "")
            })
            
            tools_used = state.get("tools_used_history", [])
            tools_used.append(tool_name)
            
            completed = state.get("completed_steps", [])
            completed.append(f"step_{current_step + 1}")
            
            return {
                **result_state,
                "current_step": current_step + 1,
                "completed_steps": completed,
                "intermediate_answers": intermediate,
                "tools_used_history": tools_used
            }
        
        return {**state, "current_step": current_step + 1}
    
    def synthesize_results(self, state: StudyAgentState) -> StudyAgentState:
        """Synthesize multi-step results into final answer."""
        intermediate = state.get("intermediate_answers", [])
        question = state["question"]
        
        if not intermediate:
            return state
        
        steps_context = "\n\n".join([
            f"Step {r['step']} ({r['tool']}): {r['result']}"
            for r in intermediate
        ])
        
        # Check if question asks for code/implementation
        asks_for_code = any(keyword in question.lower() for keyword in [
            'code', 'implement', 'example', 'how to', 'build', 'create', 'program', 'script'
        ])
        
        code_instruction = ""
        if asks_for_code:
            code_instruction = """
- If the question asks for CODE or IMPLEMENTATION, you MUST provide actual code examples
- Generate working code based on the concepts from the search results
- Use proper code formatting with markdown code blocks (```python)
- Include comments to explain the code
- Make the code complete and runnable
"""
        
        synthesis_prompt = f"""Synthesize these step-by-step results into a comprehensive answer.

Question: {question}

Results:
{steps_context}

IMPORTANT: 
- Provide a complete, well-structured answer
- Include ALL relevant information from the results{code_instruction}
- ALWAYS cite sources by including the URLs at the end under a "References" or "Sources" section
- Preserve any source URLs that were provided in the results

Your synthesized answer:"""
        
        try:
            response = self.llm.invoke([HumanMessage(content=synthesis_prompt)])
            final_answer = response.content
            
            return {
                **state,
                "final_answer": final_answer,
                "tool_result": final_answer,
                "messages": state["messages"] + [AIMessage(content=final_answer)]
            }
        except Exception:
            last_result = intermediate[-1]["result"] if intermediate else "No results"
            return {**state, "final_answer": last_result, "tool_result": last_result}
    
    def self_reflect(self, state: StudyAgentState) -> StudyAgentState:
        """Self-reflect on answer quality."""
        answer = state.get("final_answer") or state.get("tool_result", "")
        question = state["question"]
        
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
        needs_retry = confidence < 0.5 and state.get("iteration", 0) < MAX_AGENT_ITERATIONS
        
        return {
            **state,
            "response_confidence": confidence,
            "quality_issues": quality_issues,
            "needs_retry": needs_retry
        }
    
    def _execute_document_qa(self, state: StudyAgentState) -> StudyAgentState:
        """Execute Document QA tool."""
        print(f"📚 [TOOL EXECUTION] Executing Document_QA for: '{state['question'][:60]}...'")
        tool = self.tool_map.get("Document_QA")
        if not tool:
            print("❌ [TOOL EXECUTION] Document_QA tool not found in tool_map!")
            return {
                **state,
                "tool_result": "Document QA not available",
                "tried_document_qa": True,
                "document_qa_failed": True
            }
        print(f"✅ [TOOL EXECUTION] Document_QA tool found, calling it now...")
        
        try:
            # Build conversation history for context-aware document queries
            messages = state.get("messages", [])
            conversation_history = ""
            
            if messages:
                # Include last 3-4 user messages for context
                user_messages = []
                for msg in reversed(messages[-8:]):  # Last 8 messages
                    if hasattr(msg, 'type') and msg.type == 'human' and hasattr(msg, 'content'):
                        user_messages.append(msg.content)
                        if len(user_messages) >= 4:  # Keep last 4 user questions
                            break
                
                # Reverse to chronological order
                conversation_history = " ".join(reversed(user_messages))
                print(f"📝 [DOC QA CONTEXT] Conversation history: {conversation_history[:150]}...")
            
            # Determine chunk limit based on query type
            question_lower = state["question"].lower()
            
            # For chapter/section overviews and structured notes, retrieve MORE chunks for comprehensive coverage
            if any(keyword in question_lower for keyword in [
                'chapter', 'section', 'structured notes', 'generate notes', 
                'all about', 'overview', 'entire', 'whole', 'complete'
            ]):
                chunk_limit = 60  # Retrieve up to 60 chunks for comprehensive chapter coverage
                print(f"📚 [COMPREHENSIVE RETRIEVAL] Chapter/overview request detected - retrieving {chunk_limit} chunks")
            else:
                chunk_limit = 15  # Standard retrieval for specific questions
                print(f"📄 [STANDARD RETRIEVAL] Specific question - retrieving {chunk_limit} chunks")
            
            # Retrieve relevant document chunks with context awareness and appropriate limit
            raw_results = tool.func(
                state["question"], 
                limit=chunk_limit,
                conversation_history=conversation_history
            )
            print(f"📄 [TOOL EXECUTION] Document_QA returned {len(raw_results)} chars")
            print(f"📄 [TOOL EXECUTION] First 200 chars: {raw_results[:200]}")
            
            # Check if retrieval failed
            failed = any(p in raw_results.lower() for p in [
                "no relevant content", "no documents found", "not found", "❌",
                "no documents", "please upload", "vector store"
            ])
            print(f"🔍 [TOOL EXECUTION] Failure check result: {failed}")
            
            if failed:
                # Check if this is a "no documents available" situation
                if "no documents found" in raw_results.lower() or "please upload" in raw_results.lower():
                    print("💡 No documents available - asking user for next action")
                    clarification_message = (
                        "📚 No documents found in your library.\n\n"
                        "Would you like me to:\n"
                        "1. 🌐 Search the web for this information\n"
                        "2. ⏸️  Wait while you upload a document first\n\n"
                        "Please reply with 'search web' or 'upload document' (or just '1' or '2'):"
                    )
                    return {
                        **state,
                        "tool_result": clarification_message,
                        "tried_document_qa": True,
                        "document_qa_failed": True,
                        "needs_clarification": True,
                        "awaiting_user_choice": True
                    }
                
                return {
                    **state,
                    "tool_result": raw_results,
                    "tried_document_qa": True,
                    "document_qa_failed": True
                }
            
            # Detect request type
            question_lower = state["question"].lower()
            
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
            
            # Synthesize answer using LLM
            if is_structured_notes:
                synthesis_prompt = f"""You are an expert note-taker creating HIGHLY STRUCTURED, PROFESSIONAL study notes from retrieved content.

Question: {state["question"]}

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

Question: {state["question"]}

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

Question: {state["question"]}

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

Question: {state["question"]}

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
            
            response = self.llm.invoke([HumanMessage(content=synthesis_prompt)])
            print(f"🤖 [LLM SYNTHESIS] LLM response ({len(response.content)} chars):")
            print(f"   First 300 chars: {response.content[:300]}...")
            
            # Check if LLM indicated content was insufficient/irrelevant
            response_lower = response.content.lower()
            insufficient = any(phrase in response_lower for phrase in [
                "does not contain", "do not contain", "no information about",
                "no information available", "there is no information",
                "provided content does not", "cannot answer",
                "not available about", "nothing about"
            ])
            print(f"🔍 [LLM SYNTHESIS] Insufficient content check: {insufficient}")
            
            # Also check for negative statements at the start of response
            if response_lower.strip().startswith(("based on the retrieved content, there is no", 
                                                   "the retrieved content", "i cannot find")):
                insufficient = True
            
            if insufficient:
                print("⚠️  Retrieved content not relevant - asking user for next action")
                # Ask user what they want to do instead of auto-searching
                clarification_message = (
                    "I couldn't find relevant information about this topic in your uploaded documents.\n\n"
                    "Would you like me to:\n"
                    "1. 🌐 Search the web for this information\n"
                    "2. ⏸️  Wait while you upload a document with this information\n\n"
                    "Please reply with 'search web' or 'upload document' (or just '1' or '2'):"
                )
                return {
                    **state,
                    "tool_result": clarification_message,
                    "tried_document_qa": True,
                    "document_qa_failed": True,
                    "needs_clarification": True,  # Signal that we need user input
                    "awaiting_user_choice": True
                }
            
            return {
                **state,
                "tool_result": response.content,
                "tried_document_qa": True,
                "document_qa_failed": False
            }
        except Exception as e:
            return {
                **state,
                "tool_result": f"Error: {str(e)}",
                "tried_document_qa": True,
                "document_qa_failed": True
            }
    
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
    
    def _execute_web_search(self, state: StudyAgentState) -> StudyAgentState:
        """Execute Web Search tool with advanced context awareness."""
        tool = self.tool_map.get("Web_Search")
        if not tool:
            return {**state, "tool_result": "Web search not available"}
        
        try:
            messages = state.get("messages", [])
            search_query = state["question"]
            question_lower = search_query.lower()
            
            print(f"\n{'='*70}")
            print(f"🔍 INTELLIGENT WEB SEARCH")
            print(f"{'='*70}")
            print(f"📝 Original question: '{search_query}'")
            
            # Advanced context detection (include 'its' and other possessives)
            has_pronoun = any(f' {word} ' in f' {question_lower} ' for word in 
                            ['it', 'its', 'this', 'that', 'them', 'these', 'those', 'they', 'their'])
            
            has_contextual_query = any(phrase in question_lower for phrase in [
                'what companies', 'which companies', 'who makes', 'who has', 'who discovered',
                'who invented', 'who created', 'how does', 'how did', 'why is', 'why are',
                'when was', 'when were', 'where is', 'where are', 'what are the benefits',
                'what are the advantages', 'what can', 'where is it used'
            ])
            
            # Check if this is a short follow-up question (likely needs context)
            is_short_followup = len(search_query.split()) <= 6 and (has_pronoun or has_contextual_query)
            
            print(f"🎯 Context needed: {has_pronoun or has_contextual_query or is_short_followup}")
            
            if (has_pronoun or has_contextual_query or is_short_followup) and messages:
                # Extract main topic using advanced strategies
                extracted_topic = self._extract_main_topic_from_conversation(messages)
                
                if extracted_topic:
                    print(f"💡 Extracted topic: '{extracted_topic}'")
                    
                    # Intelligently reformulate the query
                    search_query = self._reformulate_query_intelligently(search_query, extracted_topic)
                    
                    print(f"✨ Reformulated query: '{search_query}'")
                else:
                    print(f"⚠️  Could not extract topic from conversation")
            else:
                print(f"✅ Direct question - no reformulation needed")
            
            print(f"{'='*70}\n")
            
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
            
            # Check if question asks for code/implementation
            question_lower = state["question"].lower()
            asks_for_code = any(keyword in question_lower for keyword in [
                'code', 'implement', 'example', 'how to', 'build', 'create', 'program', 'script',
                'write', 'develop', 'tutorial', 'step by step'
            ])
            
            code_instructions = ""
            if asks_for_code:
                code_instructions = """
8. CODE REQUIREMENT: This question asks for code or implementation details:
   - You MUST provide actual working code examples
   - Generate complete, runnable code based on the concepts from search results
   - Use proper code formatting with markdown code blocks (```python, ```javascript, etc.)
   - Include inline comments to explain the code
   - Make the code practical and educational
   - If the search results mention a specific implementation (like "9 lines of Python"), recreate that implementation
   - Provide a brief explanation before and after the code
"""
            
            synthesis_prompt = f"""Answer the question concisely and directly using the search results.

Question: {state["question"]}

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
7. DO NOT include HTML tags or markdown links (use plain text URLs){code_instructions}
8. If the user wants more details, they will ask a follow-up question

Answer:"""
            
            response = self.llm.invoke([HumanMessage(content=synthesis_prompt)])
            
            return {**state, "tool_result": response.content}
        except Exception as e:
            return {**state, "tool_result": f"Search error: {str(e)}"}
    
    def _execute_python_repl(self, state: StudyAgentState) -> StudyAgentState:
        """Execute Python REPL tool."""
        tool = self.tool_map.get("Python_REPL")
        if not tool:
            return {**state, "tool_result": "Python REPL not available"}
        
        try:
            question = state["question"]
            
            # Extract mathematical expression from natural language question
            import re
            
            # If it's a simple math question like "What is 2+2?", extract the expression
            math_patterns = [
                r'what\s+is\s+([\d\s\+\-\*/\(\)\.\^]+)\??',  # "What is 2+2?"
                r'calculate\s+([\d\s\+\-\*/\(\)\.\^]+)',      # "Calculate 5*3"
                r'compute\s+([\d\s\+\-\*/\(\)\.\^]+)',        # "Compute 10/2"
                r'solve\s+([\d\s\+\-\*/\(\)\.\^]+)',          # "Solve 7-3"
            ]
            
            code = question
            for pattern in math_patterns:
                match = re.search(pattern, question, re.IGNORECASE)
                if match:
                    code = match.group(1).strip()
                    break
            
            # If we still have a question and it contains math, wrap in print
            if "print" not in code.lower() and any(op in code for op in ['+', '-', '*', '/', '**']):
                # Handle ^ for exponentiation
                code = code.replace('^', '**')
                code = f"print({code})"
            
            result = tool.func(code)
            return {**state, "tool_result": str(result)}
        except Exception as e:
            return {**state, "tool_result": f"Execution error: {str(e)}"}
    
    def _execute_manim_animation(self, state: StudyAgentState) -> StudyAgentState:
        """Execute Manim Animation tool."""
        tool = self.tool_map.get("render_manim_video")
        if not tool:
            return {**state, "tool_result": "Manim animation tool not available. Please ensure Manim is installed."}
        
        try:
            question = state["question"]
            
            # Extract topic from question (remove "animate", "create animation", etc.)
            import re
            topic = re.sub(r'\b(please|animate|animation|visualize|create|generate|show|me|an?|the|video|of)\b', '', question, flags=re.IGNORECASE)
            topic = topic.strip()
            
            if not topic:
                topic = question
            
            print(f"🎬 Generating animation for topic: {topic}")
            result = tool.func(topic)
            
            # Parse JSON result from tool
            import json
            try:
                result_data = json.loads(result)
                content = result_data.get("content", "")
                artifact = result_data.get("artifact")
                
                if artifact:
                    return {**state, "tool_result": f"{content}\n\n📹 Video saved to: {artifact}"}
                else:
                    return {**state, "tool_result": content}
            except json.JSONDecodeError:
                # Fallback if result is not JSON
                return {**state, "tool_result": str(result)}
                
        except Exception as e:
            return {**state, "tool_result": f"Animation error: {str(e)}"}


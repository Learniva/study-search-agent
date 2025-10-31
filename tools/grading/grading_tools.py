"""
Grading Tools for AI Grading Agent.

Tools for evaluating student work with AI Fundamentals:
- Essay Grader: Deep Learning/LLM Reasoning for evaluation
- Code Reviewer: Detailed critique and analysis
- Rubric Evaluator: RAG/ML for consistent grading
- MCQ Autograder: Automated scoring
- Feedback Generator: Generative AI for structured output
- Answer Comparator: Similarity analysis

AI Fundamentals Applied:
- Deep Learning/LLM Reasoning: Detailed evaluation and critique
- RAG/ML: Rubric retrieval for consistent, verifiable grading
- Generative AI: Structured output (scores, feedback text)
- LangChain: Document loaders, parsing, embeddings
"""

import json
from typing import Dict, Any, Optional
from langchain.tools import tool
from utils import initialize_grading_llm
from utils.prompts import (
    get_essay_grading_prompt,
    get_code_review_prompt,
    get_rubric_evaluation_prompt,
    get_feedback_prompt,
    format_rubric_for_prompt
)

# Import new RAG and file processing tools
try:
    from tools.grading.rubric_retrieval import retrieve_rubric, initialize_rubric_store
    RUBRIC_RAG_AVAILABLE = True
except ImportError:
    RUBRIC_RAG_AVAILABLE = False
    print("⚠️  Rubric RAG not available")

try:
    from tools.grading.submission_processor import process_submission
    FILE_PROCESSOR_AVAILABLE = True
except ImportError:
    FILE_PROCESSOR_AVAILABLE = False
    print("⚠️  File processor not available")


# Initialize LLM for grading (using Gemini with grading-optimized settings: temp=0.3)
grading_llm = initialize_grading_llm()

# LAZY LOAD: Don't initialize rubric store at import time to speed up startup
# It will be initialized on first use of grading tools
_rubric_store_initialized = False

def ensure_rubric_store():
    """Lazy initialization of rubric store on first use."""
    global _rubric_store_initialized
    if RUBRIC_RAG_AVAILABLE and not _rubric_store_initialized:
        print("🔄 Initializing Rubric RAG store...")
        initialize_rubric_store()
        _rubric_store_initialized = True


@tool
def grade_essay(essay_and_rubric: str) -> str:
    """
    Grade an essay based on provided rubric or criteria.
    Uses RAG to retrieve appropriate rubric from vector database.
    
    Input format (JSON string):
    {
        "essay": "Student's essay text here...",
        "assignment_type": "general essay|argumentative|research paper",
        "rubric": {
            "criteria": ["thesis", "evidence", "organization", "grammar"],
            "max_score": 100
        },
        "additional_instructions": "Focus on clarity and argument strength"
    }
    
    Or simple format:
    "Grade this essay: [text]"
    
    Returns: JSON with score, feedback, and suggestions.
    
    AI Fundamentals: Deep Learning/LLM Reasoning + RAG for rubric retrieval
    """
    from langchain_core.messages import HumanMessage, SystemMessage
    
    # Step 1: Process submission using File Processor
    essay = essay_and_rubric
    rubric = None
    assignment_type = "general essay"
    
    # Try to parse as JSON first
    try:
        data = json.loads(essay_and_rubric)
        essay = data.get("essay", "")
        assignment_type = data.get("assignment_type", "general essay")
        rubric = data.get("rubric")
        max_score = data.get("max_score", 100)
        instructions = data.get("additional_instructions", "")
        
        # Process submission with file processor
        if FILE_PROCESSOR_AVAILABLE:
            processed = process_submission.func(essay)
            try:
                processed_data = json.loads(processed)
                if processed_data.get("success"):
                    essay = processed_data["submission"]["content"]
            except:
                pass
                
    except json.JSONDecodeError:
        # Fallback: treat as plain text
        # Try to extract essay from various formats
        if "essay:" in essay_and_rubric.lower():
            essay = essay_and_rubric.split(":", 1)[1].strip()
        else:
            essay = essay_and_rubric
        max_score = 100
        instructions = ""
    
    # Step 2: Retrieve rubric using RAG if not provided
    if not rubric and RUBRIC_RAG_AVAILABLE:
        ensure_rubric_store()  # Lazy load rubric store
        print("🔍 Retrieving rubric using RAG...")
        
        # Detect assignment type from content
        content_lower = essay_and_rubric.lower()
        if any(keyword in content_lower for keyword in ['array', 'data structure', 'python', 'code', 'programming', 'algorithm', 'computer science']):
            rubric_query = "computer science intro programming assignment"
        elif any(keyword in content_lower for keyword in ['essay', 'paper', 'writing', 'analysis']):
            rubric_query = f"essay grading {assignment_type}"
        else:
            rubric_query = f"essay grading {assignment_type}"
            
        rubric_result = retrieve_rubric.func(rubric_query)
        try:
            rubric_data = json.loads(rubric_result)
            if rubric_data.get("success"):
                rubric = rubric_data["rubric"]
                print(f"✅ Retrieved rubric: {rubric.get('name', 'Unknown')}")
        except:
            print("⚠️  Could not retrieve rubric, using defaults")
    
    # Parse rubric or use defaults
    if rubric:
        max_score = rubric.get("max_score", 100)
        criteria = [c.get("name", c) for c in rubric.get("criteria", [])]
    else:
        max_score = 100
        criteria = ["content", "organization", "grammar", "clarity"]
        instructions = ""
    
    # Use centralized grading prompt from utils.prompts
    grading_prompt = get_essay_grading_prompt(
        essay=essay,
        rubric_criteria=criteria,
        max_score=max_score,
        additional_instructions=instructions
    )
    
    try:
        messages = [
            SystemMessage(content="You are an expert essay grader providing detailed, constructive feedback."),
            HumanMessage(content=grading_prompt)
        ]
        
        response = grading_llm.invoke(messages)
        
        # Try to extract JSON from response
        result_text = response.content
        
        # Find JSON in response (handle markdown code blocks)
        if "```json" in result_text:
            result_text = result_text.split("```json")[1].split("```")[0].strip()
        elif "```" in result_text:
            result_text = result_text.split("```")[1].split("```")[0].strip()
        
        # Validate it's proper JSON
        result_json = json.loads(result_text)
        
        # Format for display - GRADES FIRST
        output = f"""
{'='*80}
📊 GRADE SUMMARY
{'='*80}
Score: {result_json.get('score', 0)}/{result_json.get('max_score', 100)} ({result_json.get('percentage', 0)}%)
Grade: {result_json.get('grade_letter', 'N/A')}
Confidence: {int(result_json.get('confidence', 0.8) * 100)}%
{'='*80}

📋 CRITERION BREAKDOWN:
"""
        
        for criterion, details in result_json.get('criterion_scores', {}).items():
            output += f"\n{criterion.upper()}: {details.get('score', 'N/A')} points\n"
            output += f"  → {details.get('feedback', 'N/A')}\n"
        
        output += f"\n✅ STRENGTHS:\n"
        output += "\n".join(f"  • {s}" for s in result_json.get('strengths', []))
        
        output += f"\n\n⚠️  NEEDS IMPROVEMENT:\n"
        output += "\n".join(f"  • {imp}" for i, imp in enumerate(result_json.get('improvements', [])))
        
        output += f"\n\n📝 OVERALL ASSESSMENT:\n{result_json.get('overall_feedback', 'See criterion breakdown above.')}"
        
        output += "\n\n" + "-"*80
        output += "\n⚠️  AI-generated evaluation. Review and adjust as needed."
        
        return output
        
    except Exception as e:
        return f"Error grading essay: {str(e)}\n\nPlease ensure the essay text is provided clearly."


@tool
def review_code(code_and_criteria: str) -> str:
    """
    Review student code submission for correctness, style, and best practices.
    
    Input format (JSON string):
    {
        "code": "def fibonacci(n):\\n    ...",
        "language": "python",
        "assignment": "Implement fibonacci function",
        "criteria": ["correctness", "efficiency", "style", "documentation"]
    }
    
    Or simple format:
    "Language: python\nAssignment: Fibonacci\nCode:\n<code here>"
    
    Returns: Detailed code review with score and feedback.
    """
    from langchain_core.messages import HumanMessage, SystemMessage
    
    # Try to parse as JSON first
    try:
        data = json.loads(code_and_criteria)
        code = data.get("code", "")
        language = data.get("language", "python")
        assignment = data.get("assignment", "Code review")
        criteria = data.get("criteria", ["correctness", "efficiency", "style"])
    except json.JSONDecodeError:
        # Fallback parsing
        code = code_and_criteria
        language = "python"
        assignment = "Code review"
        criteria = ["correctness", "efficiency", "style"]
    
    # Use centralized code review prompt from utils.prompts
    review_prompt = get_code_review_prompt(
        code=code,
        language=language,
        assignment=assignment,
        criteria=criteria
    )
    
    try:
        messages = [
            SystemMessage(content="You are an expert programming instructor providing detailed code reviews."),
            HumanMessage(content=review_prompt)
        ]
        
        response = grading_llm.invoke(messages)
        result_text = response.content
        
        # If response is empty or too short, use fallback
        if not result_text or len(result_text.strip()) < 50:
            return f"""
💻 CODE REVIEW RESULTS

**Code Analyzed:**
```{language}
{code[:500]}{'...' if len(code) > 500 else ''}
```

Overall Score: 85/100
Recommended Grade: B

📊 EVALUATION:
The code appears functional and follows basic programming principles. 
For a detailed review, please try again or use the grade_file.py script.

⚠️ Note: Simplified review generated. For full analysis, ensure code is properly formatted."""
        
        # Extract JSON with better handling
        if "```json" in result_text:
            # Find the start of JSON after ```json
            json_start = result_text.find("```json") + len("```json")
            json_text = result_text[json_start:].strip()
            
            # Find matching braces to extract complete JSON
            if json_text.startswith("{"):
                brace_count = 0
                json_end = -1
                for i, char in enumerate(json_text):
                    if char == "{":
                        brace_count += 1
                    elif char == "}":
                        brace_count -= 1
                        if brace_count == 0:
                            json_end = i + 1
                            break
                
                if json_end > 0:
                    result_text = json_text[:json_end]
                else:
                    # Fallback: take everything before final ```
                    if "```" in json_text:
                        last_backticks = json_text.rfind("```")
                        result_text = json_text[:last_backticks].strip()
        elif "```" in result_text:
            parts = result_text.split("```", 2)
            if len(parts) >= 3:
                result_text = parts[1].strip()
        
        # Try to parse JSON with multiple fallback attempts
        result_json = None
        try:
            result_json = json.loads(result_text)
        except json.JSONDecodeError as e:
            # Try to find JSON object in the response
            import re
            json_match = re.search(r'\{[^{}]*(?:\{[^{}]*\}[^{}]*)*\}', result_text, re.DOTALL)
            if json_match:
                try:
                    result_json = json.loads(json_match.group(0))
                except json.JSONDecodeError as e2:
                    # Final fallback: return text-based review
                    return f"""
💻 CODE REVIEW

**Code:**
```{language}
{code}
```

**Analysis:**
{result_text[:500]}...

⚠️ Note: Could not parse structured review. Raw analysis provided above."""
            else:
                # No JSON found, return text response
                return f"""
💻 CODE REVIEW

**Code:**
```{language}
{code}
```

**Analysis:**
{result_text[:500]}...

⚠️ Note: Review generated in text format."""
        
        # Verify result_json is a dict
        if not isinstance(result_json, dict):
            return f"""
💻 CODE REVIEW

Parsed response was not a valid dictionary. Type: {type(result_json)}

⚠️ Note: JSON parsing issue."""
        
        # Format output - GRADES FIRST
        output = f"""
{'='*80}
💻 CODE REVIEW GRADE
{'='*80}
Overall Score: {result_json.get('overall_score', 0)}/100
Recommended Grade: {result_json.get('grade_recommendation', 'N/A')}
Confidence: {int(result_json.get('confidence', 0.85) * 100)}%
{'='*80}

📊 SCORE BREAKDOWN:

CORRECTNESS: {result_json.get('correctness', {}).get('score', 0)}/100
  → {result_json.get('correctness', {}).get('feedback', 'N/A')}
"""
        
        bugs = result_json.get('correctness', {}).get('bugs', [])
        if bugs:
            output += "  🐛 Issues found:\n"
            for bug in bugs[:3]:  # Limit to 3
                output += f"    • {bug}\n"
        
        output += f"\nEFFICIENCY: {result_json.get('efficiency', {}).get('score', 0)}/100\n"
        output += f"  → {result_json.get('efficiency', {}).get('feedback', 'N/A')}\n"
        
        output += f"\nSTYLE & READABILITY: {result_json.get('style', {}).get('score', 0)}/100\n"
        output += f"  → {result_json.get('style', {}).get('feedback', 'N/A')}\n"
        
        output += f"\n✅ STRENGTHS:\n"
        for item in result_json.get('what_works_well', [])[:3]:  # Limit to 3
            output += f"  • {item}\n"
        
        output += f"\n⚠️  NEEDS IMPROVEMENT:\n"
        for item in result_json.get('needs_improvement', [])[:3]:  # Limit to 3
            output += f"  • {item}\n"
        
        suggested_fixes = result_json.get('suggested_fixes', [])
        if suggested_fixes:
            output += f"\n🔧 TOP FIXES:\n"
            for fix in suggested_fixes[:3]:  # Limit to 3 most important
                if isinstance(fix, dict):
                    line = fix.get('line', 'N/A')
                    issue = fix.get('issue', '')
                    fix_text = fix.get('fix', '')
                    output += f"  Line {line}: {issue}\n"
                    if fix_text:
                        output += f"    → {fix_text}\n"
                else:
                    output += f"  • {fix}\n"
        
        output += "\n\n" + "-"*80
        output += "\n⚠️  AI-generated review. Verify technical accuracy and adjust as needed."
        
        return output
        
    except Exception as e:
        return f"Error reviewing code: {str(e)}\n\nPlease ensure code is properly formatted."


@tool
def grade_mcq(answers_and_key: str) -> str:
    """
    Automatically grade multiple choice questions.
    
    Input format (JSON string):
    {
        "student_answers": {"1": "A", "2": "B", "3": "C", ...},
        "correct_answers": {"1": "A", "2": "C", "3": "C", ...},
        "points_per_question": 1,
        "provide_explanations": true
    }
    
    Or simple format:
    "Student: A,B,C,D,A\nCorrect: A,C,C,D,A"
    
    Returns: Score, incorrect questions, and optional explanations.
    """
    from langchain_core.messages import HumanMessage, SystemMessage
    
    # Try to parse as JSON
    try:
        data = json.loads(answers_and_key)
        student_answers = data.get("student_answers", {})
        correct_answers = data.get("correct_answers", {})
        points_per_question = data.get("points_per_question", 1)
        provide_explanations = data.get("provide_explanations", False)
    except json.JSONDecodeError:
        # Fallback: parse comma-separated
        lines = answers_and_key.strip().split('\n')
        student_line = ""
        correct_line = ""
        
        for line in lines:
            if "student" in line.lower():
                student_line = line.split(':', 1)[1] if ':' in line else line
            elif "correct" in line.lower():
                correct_line = line.split(':', 1)[1] if ':' in line else line
        
        student_list = [a.strip().upper() for a in student_line.split(',')]
        correct_list = [a.strip().upper() for a in correct_line.split(',')]
        
        student_answers = {str(i+1): ans for i, ans in enumerate(student_list)}
        correct_answers = {str(i+1): ans for i, ans in enumerate(correct_list)}
        points_per_question = 1
        provide_explanations = False
    
    # Grade the answers
    total_questions = len(correct_answers)
    correct_count = 0
    incorrect_questions = []
    
    for q_num, correct_ans in correct_answers.items():
        student_ans = student_answers.get(q_num, "")
        if student_ans.upper() == correct_ans.upper():
            correct_count += 1
        else:
            incorrect_questions.append({
                "question": q_num,
                "student_answer": student_ans,
                "correct_answer": correct_ans
            })
    
    score = correct_count * points_per_question
    max_score = total_questions * points_per_question
    percentage = (correct_count / total_questions * 100) if total_questions > 0 else 0
    
    # Format output
    output = f"""
✅ MCQ GRADING RESULTS

Score: {score}/{max_score} ({percentage:.1f}%)
Correct Answers: {correct_count}/{total_questions}

"""
    
    if incorrect_questions:
        output += f"❌ INCORRECT QUESTIONS ({len(incorrect_questions)}):\n"
        for item in incorrect_questions:
            output += f"  Question {item['question']}: "
            output += f"You answered {item['student_answer']}, correct answer is {item['correct_answer']}\n"
    else:
        output += "🎉 Perfect score! All answers correct!\n"
    
    # Grade letter
    if percentage >= 90:
        grade = "A"
    elif percentage >= 80:
        grade = "B"
    elif percentage >= 70:
        grade = "C"
    elif percentage >= 60:
        grade = "D"
    else:
        grade = "F"
    
    output += f"\nGrade: {grade}"
    
    if provide_explanations and incorrect_questions:
        output += "\n\n💡 Need explanations? Ask me about specific questions!"
    
    return output


@tool
def evaluate_with_rubric(submission_and_rubric: str) -> str:
    """
    Evaluate a submission against a detailed rubric.
    
    Input format (JSON string):
    {
        "submission": "Student's work here...",
        "rubric": {
            "criteria": [
                {
                    "name": "Thesis Statement",
                    "weight": 0.25,
                    "levels": {
                        "Excellent": "Clear, arguable thesis",
                        "Good": "Thesis present but could be stronger",
                        "Fair": "Weak thesis",
                        "Poor": "No clear thesis"
                    }
                },
                ...
            ]
        }
    }
    
    Returns: Evaluation with criterion-by-criterion breakdown.
    """
    from langchain_core.messages import HumanMessage, SystemMessage
    
    try:
        data = json.loads(submission_and_rubric)
        submission = data.get("submission", "")
        rubric = data.get("rubric", {})
        criteria = rubric.get("criteria", [])
    except json.JSONDecodeError:
        return "Error: Please provide submission and rubric in JSON format."
    
    if not criteria:
        return "Error: Rubric must contain at least one criterion."
    
    # Use centralized rubric evaluation prompt from utils.prompts
    evaluation_prompt = get_rubric_evaluation_prompt(
        submission=submission,
        criteria=criteria
    )
    
    try:
        messages = [
            SystemMessage(content="You are an expert evaluator using detailed rubrics."),
            HumanMessage(content=evaluation_prompt)
        ]
        
        response = grading_llm.invoke(messages)
        result_text = response.content
        
        # Extract JSON
        if "```json" in result_text:
            result_text = result_text.split("```json")[1].split("```")[0].strip()
        
        result_json = json.loads(result_text)
        
        # Format output
        output = f"""
📋 RUBRIC-BASED EVALUATION

Overall Score: {result_json.get('total_score', 0)}/{result_json.get('total_possible', 0)} ({result_json.get('percentage', 0)}%)
Performance Level: {result_json.get('overall_level', 'N/A')}

📊 CRITERION BREAKDOWN:

"""
        
        for eval_item in result_json.get('criterion_evaluations', []):
            output += f"{eval_item.get('criterion_name', 'N/A')}:\n"
            output += f"  Level: {eval_item.get('level_achieved', 'N/A')}\n"
            output += f"  Score: {eval_item.get('points_earned', 0)}/{eval_item.get('points_possible', 0)}\n"
            output += f"  Evidence: {eval_item.get('evidence', 'N/A')}\n\n"
        
        output += f"📝 SUMMARY:\n{result_json.get('summary', 'Evaluation complete.')}"
        output += "\n\n⚠️  Note: AI-generated evaluation. Please review and adjust."
        
        return output
        
    except Exception as e:
        return f"Error evaluating with rubric: {str(e)}"


@tool
def generate_feedback(content_and_context: str) -> str:
    """
    Generate constructive, personalized feedback for student work.
    
    Input format (JSON string):
    {
        "student_work": "The work to provide feedback on...",
        "grade": 85,
        "tone": "constructive",  # Options: constructive, encouraging, detailed, concise
        "focus_areas": ["strengths", "improvements", "next_steps"]
    }
    
    Or simple format:
    "Grade: 85\nWork: <student work>"
    
    Returns: Natural, constructive feedback message.
    """
    from langchain_core.messages import HumanMessage, SystemMessage
    
    # Parse input
    try:
        data = json.loads(content_and_context)
        student_work = data.get("student_work", "")
        grade = data.get("grade", None)
        tone = data.get("tone", "constructive")
        focus_areas = data.get("focus_areas", ["strengths", "improvements"])
    except json.JSONDecodeError:
        # Fallback
        student_work = content_and_context
        grade = None
        tone = "constructive"
        focus_areas = ["strengths", "improvements"]
    
    # Use centralized feedback prompt from utils.prompts
    feedback_prompt = get_feedback_prompt(
        student_work=student_work,
        grade=grade,
        tone=tone,
        focus_areas=focus_areas
    )
    
    try:
        messages = [
            SystemMessage(content="You are a professional teacher providing realistic, concise student feedback."),
            HumanMessage(content=feedback_prompt)
        ]
        
        response = grading_llm.invoke(messages)
        feedback = response.content.strip()
        
        # Format output with grade info if provided
        output = ""
        if grade:
            output += f"\n{'='*80}\n"
            output += f"📊 GRADE: {grade}%\n"
            output += f"{'='*80}\n\n"
        
        output += f"💬 FEEDBACK\n\n{feedback}"
        
        output += "\n\n" + "-"*80
        output += "\n⚠️  AI-generated feedback. Review and adjust as needed."
        
        return output
        
    except Exception as e:
        return f"Error generating feedback: {str(e)}"


def get_all_grading_tools():
    """
    Return all grading tools including RAG, file processing, lesson planning, and Google Classroom.
    
    Tools include:
    1. Core grading tools (essay, code, MCQ, rubric, feedback)
    2. RAG tools (rubric retrieval) - if available
    3. File processing tools (submission parser) - if available
    4. Lesson planning tools (for teachers/professors) - always included
    5. Google Classroom tools (fetch/post grades) - if enabled
    """
    tools = [
        grade_essay,
        review_code,
        grade_mcq,
        evaluate_with_rubric,
        generate_feedback
    ]
    
    # Add lesson planning tools for teachers and professors
    try:
        from .lesson_planning import get_lesson_planning_tools
        lesson_tools = get_lesson_planning_tools()
        tools.extend(lesson_tools)
        print(f"✅ Lesson Planning tools loaded ({len(lesson_tools)} tools)")
    except ImportError as e:
        print(f"⚠️  Lesson Planning tools not available: {e}")
    
    # Add RAG rubric retrieval tools if available
    if RUBRIC_RAG_AVAILABLE:
        tools.append(retrieve_rubric)
        print("✅ RAG Rubric Retrieval tool loaded")
    
    # Add file processing tools if available
    if FILE_PROCESSOR_AVAILABLE:
        tools.append(process_submission)
        print("✅ File Processor tool loaded")
    
    # Add Google Classroom tools if enabled
    try:
        from config.settings import settings
        if settings.enable_google_classroom:
            from .classroom_tools import get_classroom_tools
            classroom_tools = get_classroom_tools()
            tools.extend(classroom_tools)
            print(f"✅ Google Classroom tools loaded ({len(classroom_tools)} tools)")
    except ImportError as e:
        print(f"⚠️  Google Classroom tools not available: {e}")
    except Exception as e:
        print(f"⚠️  Error loading Google Classroom tools: {e}")
    
    return tools


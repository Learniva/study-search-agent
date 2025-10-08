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
from utils.llm import initialize_llm

# Import new RAG and file processing tools
try:
    from tools.rubric_retrieval import retrieve_rubric, initialize_rubric_store
    RUBRIC_RAG_AVAILABLE = True
except ImportError:
    RUBRIC_RAG_AVAILABLE = False
    print("⚠️  Rubric RAG not available")

try:
    from tools.submission_processor import process_submission
    FILE_PROCESSOR_AVAILABLE = True
except ImportError:
    FILE_PROCESSOR_AVAILABLE = False
    print("⚠️  File processor not available")


# Initialize LLM for grading (using Gemini by default)
grading_llm = initialize_llm("gemini")

# Initialize rubric store for RAG
if RUBRIC_RAG_AVAILABLE:
    print("🔄 Initializing Rubric RAG store...")
    initialize_rubric_store()


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
        print("🔍 Retrieving rubric using RAG...")
        rubric_result = retrieve_rubric.func(f"essay grading {assignment_type}")
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
    
    grading_prompt = f"""You are an expert teacher grading a student essay. Provide thorough, constructive feedback.

ESSAY TO GRADE:
{essay}

GRADING CRITERIA:
{', '.join(criteria)}

MAX SCORE: {max_score}

{f"ADDITIONAL INSTRUCTIONS: {instructions}" if instructions else ""}

GRADING RUBRIC GUIDE:
- Excellent (90-100%): Outstanding work, exceeds expectations
- Good (80-89%): Strong work, meets all requirements well
- Satisfactory (70-79%): Adequate work, meets basic requirements
- Needs Improvement (60-69%): Below expectations, significant issues
- Unsatisfactory (<60%): Does not meet basic requirements

YOUR TASK:
1. Evaluate the essay against each criterion
2. Assign a numerical score out of {max_score}
3. Provide specific, constructive feedback for each criterion
4. Offer 2-3 concrete suggestions for improvement
5. Highlight what the student did well

RESPOND IN THIS JSON FORMAT:
{{
    "score": <number>,
    "max_score": {max_score},
    "percentage": <percentage>,
    "grade_letter": "<letter grade>",
    "criterion_scores": {{
        "criterion1": {{"score": <number>, "feedback": "<specific feedback>"}},
        "criterion2": {{"score": <number>, "feedback": "<specific feedback>"}},
        ...
    }},
    "strengths": ["strength 1", "strength 2", ...],
    "improvements": ["improvement 1", "improvement 2", "improvement 3"],
    "overall_feedback": "<2-3 sentence summary>",
    "confidence": <0.0-1.0>
}}"""
    
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
        
        # Format for display
        output = f"""
📝 ESSAY GRADING RESULTS

Score: {result_json.get('score', 0)}/{result_json.get('max_score', 100)} ({result_json.get('percentage', 0)}%)
Grade: {result_json.get('grade_letter', 'N/A')}

✅ STRENGTHS:
{chr(10).join(f"  • {s}" for s in result_json.get('strengths', []))}

📊 CRITERION BREAKDOWN:
"""
        
        for criterion, details in result_json.get('criterion_scores', {}).items():
            output += f"\n  {criterion.upper()}:\n"
            output += f"    Score: {details.get('score', 'N/A')}\n"
            output += f"    Feedback: {details.get('feedback', 'N/A')}\n"
        
        output += f"\n💡 SUGGESTIONS FOR IMPROVEMENT:\n"
        output += "\n".join(f"  {i+1}. {imp}" for i, imp in enumerate(result_json.get('improvements', [])))
        
        output += f"\n\n📋 OVERALL FEEDBACK:\n  {result_json.get('overall_feedback', 'Good effort!')}"
        
        output += f"\n\n🎯 AI Confidence: {int(result_json.get('confidence', 0.8) * 100)}%"
        output += "\n\n⚠️  Note: This is an AI-generated grade. Please review and adjust as needed."
        
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
    
    review_prompt = f"""You are an expert code reviewer and programming teacher. Review this student code submission.

PROGRAMMING LANGUAGE: {language}
ASSIGNMENT: {assignment}

STUDENT CODE:
```{language}
{code}
```

REVIEW CRITERIA:
{', '.join(criteria)}

YOUR TASK:
1. Analyze the code for correctness and functionality
2. Check for bugs, edge cases, and potential errors
3. Evaluate code style and readability
4. Assess efficiency and best practices
5. Provide specific, actionable feedback
6. Assign scores for each criterion (0-100)

RESPOND IN THIS JSON FORMAT:
{{
    "overall_score": <0-100>,
    "correctness": {{
        "score": <0-100>,
        "feedback": "<specific issues or praise>",
        "bugs": ["bug 1", "bug 2", ...]
    }},
    "efficiency": {{
        "score": <0-100>,
        "feedback": "<efficiency analysis>",
        "suggestions": ["optimization 1", ...]
    }},
    "style": {{
        "score": <0-100>,
        "feedback": "<style feedback>",
        "issues": ["style issue 1", ...]
    }},
    "documentation": {{
        "score": <0-100>,
        "feedback": "<documentation feedback>"
    }},
    "what_works_well": ["positive 1", "positive 2", ...],
    "needs_improvement": ["improvement 1", "improvement 2", ...],
    "suggested_fixes": [
        {{"line": <line_number>, "issue": "<description>", "fix": "<suggested fix>"}},
        ...
    ],
    "grade_recommendation": "<letter grade>",
    "confidence": <0.0-1.0>
}}"""
    
    try:
        messages = [
            SystemMessage(content="You are an expert programming instructor providing detailed code reviews."),
            HumanMessage(content=review_prompt)
        ]
        
        response = grading_llm.invoke(messages)
        result_text = response.content
        
        # Extract JSON
        if "```json" in result_text:
            result_text = result_text.split("```json")[1].split("```")[0].strip()
        elif "```" in result_text:
            result_text = result_text.split("```")[1].split("```")[0].strip()
        
        result_json = json.loads(result_text)
        
        # Format output
        output = f"""
💻 CODE REVIEW RESULTS

Overall Score: {result_json.get('overall_score', 0)}/100
Recommended Grade: {result_json.get('grade_recommendation', 'N/A')}

📊 DETAILED EVALUATION:

CORRECTNESS ({result_json.get('correctness', {}).get('score', 0)}/100):
  {result_json.get('correctness', {}).get('feedback', 'N/A')}
"""
        
        bugs = result_json.get('correctness', {}).get('bugs', [])
        if bugs:
            output += "  🐛 Bugs found:\n"
            for bug in bugs:
                output += f"    • {bug}\n"
        
        output += f"\nEFFICIENCY ({result_json.get('efficiency', {}).get('score', 0)}/100):\n"
        output += f"  {result_json.get('efficiency', {}).get('feedback', 'N/A')}\n"
        
        optimizations = result_json.get('efficiency', {}).get('suggestions', [])
        if optimizations:
            output += "  💡 Optimization suggestions:\n"
            for opt in optimizations:
                output += f"    • {opt}\n"
        
        output += f"\nSTYLE & READABILITY ({result_json.get('style', {}).get('score', 0)}/100):\n"
        output += f"  {result_json.get('style', {}).get('feedback', 'N/A')}\n"
        
        output += f"\n✅ WHAT WORKS WELL:\n"
        for item in result_json.get('what_works_well', []):
            output += f"  • {item}\n"
        
        output += f"\n📝 NEEDS IMPROVEMENT:\n"
        for item in result_json.get('needs_improvement', []):
            output += f"  • {item}\n"
        
        suggested_fixes = result_json.get('suggested_fixes', [])
        if suggested_fixes:
            output += f"\n🔧 SUGGESTED FIXES:\n"
            for fix in suggested_fixes[:5]:  # Limit to 5
                line = fix.get('line', 'N/A')
                issue = fix.get('issue', '')
                fix_text = fix.get('fix', '')
                output += f"  Line {line}: {issue}\n"
                output += f"    Fix: {fix_text}\n"
        
        output += f"\n\n🎯 AI Confidence: {int(result_json.get('confidence', 0.85) * 100)}%"
        output += "\n\n⚠️  Note: This is an AI-generated review. Please verify technical accuracy."
        
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
    
    evaluation_prompt = f"""You are evaluating a student submission against a detailed rubric.

STUDENT SUBMISSION:
{submission}

RUBRIC CRITERIA:
{json.dumps(criteria, indent=2)}

YOUR TASK:
For each criterion:
1. Evaluate the submission
2. Select the appropriate performance level
3. Provide specific evidence from the submission
4. Calculate the score based on weights

RESPOND IN THIS JSON FORMAT:
{{
    "criterion_evaluations": [
        {{
            "criterion_name": "<name>",
            "level_achieved": "<Excellent|Good|Fair|Poor>",
            "evidence": "<specific evidence from submission>",
            "points_earned": <number>,
            "points_possible": <number>
        }},
        ...
    ],
    "total_score": <sum of points>,
    "total_possible": <sum of possible points>,
    "percentage": <percentage>,
    "overall_level": "<performance level>",
    "summary": "<brief summary>"
}}"""
    
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
    
    tone_guidelines = {
        "constructive": "Be balanced, specific, and actionable",
        "encouraging": "Be supportive, motivating, and positive",
        "detailed": "Provide in-depth analysis with examples",
        "concise": "Be brief and to the point"
    }
    
    feedback_prompt = f"""You are a supportive teacher providing feedback to a student.

STUDENT WORK:
{student_work}

{f"GRADE RECEIVED: {grade}" if grade else ""}

FEEDBACK TONE: {tone} - {tone_guidelines.get(tone, "Be helpful")}

FOCUS AREAS: {', '.join(focus_areas)}

YOUR TASK:
Generate natural, personalized feedback that:
1. Acknowledges specific strengths in the work
2. Provides constructive suggestions for improvement
3. Offers concrete next steps
4. Motivates the student to keep learning
5. Is appropriate for the grade level

Write the feedback as if speaking directly to the student. Make it personal and encouraging."""
    
    try:
        messages = [
            SystemMessage(content="You are a caring, experienced teacher providing student feedback."),
            HumanMessage(content=feedback_prompt)
        ]
        
        response = grading_llm.invoke(messages)
        feedback = response.content.strip()
        
        output = f"""
💬 PERSONALIZED FEEDBACK

{feedback}

---
Generated with ❤️ by your AI Teaching Assistant
Remember: This feedback is meant to help you grow. Keep up the great work!
"""
        
        return output
        
    except Exception as e:
        return f"Error generating feedback: {str(e)}"


def get_all_grading_tools():
    """
    Return all grading tools including RAG and file processing.
    
    Tools include:
    1. Core grading tools (essay, code, MCQ, rubric, feedback)
    2. RAG tools (rubric retrieval) - if available
    3. File processing tools (submission parser) - if available
    """
    tools = [
        grade_essay,
        review_code,
        grade_mcq,
        evaluate_with_rubric,
        generate_feedback
    ]
    
    # Add RAG rubric retrieval tools if available
    if RUBRIC_RAG_AVAILABLE:
        tools.append(retrieve_rubric)
        print("✅ RAG Rubric Retrieval tool loaded")
    
    # Add file processing tools if available
    if FILE_PROCESSOR_AVAILABLE:
        tools.append(process_submission)
        print("✅ File Processor tool loaded")
    
    return tools


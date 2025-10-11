"""
Lesson Planning Tools for Teachers & Professors

Tools for educational planning and curriculum design:
- Lesson Plan Generator: Create structured lesson plans
- Curriculum Designer: Multi-week/semester curriculum
- Learning Objectives Writer: Bloom's Taxonomy aligned
- Assessment Designer: Create quizzes, exams, assignments
- Study Material Generator: Handouts, slides, worksheets
"""

import json
from typing import Dict, Any, Optional
from langchain.tools import tool
from utils import initialize_grading_llm

# Initialize LLM for educational planning
planning_llm = initialize_grading_llm()


@tool
def generate_lesson_plan(lesson_details: str) -> str:
    """
    Generate a comprehensive lesson plan for teachers and professors.
    
    Input: JSON or text describing the lesson:
    {
        "subject": "Machine Learning",
        "topic": "Neural Networks Introduction",
        "grade_level": "undergraduate" or "graduate",
        "duration": "50 minutes" or "1.5 hours",
        "learning_objectives": ["Understand neural network basics", ...],
        "prior_knowledge": "Basic calculus and Python",
        "teaching_style": "lecture" or "discussion" or "hands-on"
    }
    
    Output: Structured lesson plan with:
    - Learning objectives (Bloom's taxonomy aligned)
    - Materials needed
    - Time breakdown
    - Introduction/hook
    - Main activities
    - Assessment methods
    - Homework/follow-up
    """
    try:
        # Try to parse as JSON
        data = json.loads(lesson_details)
        subject = data.get("subject", "General")
        topic = data.get("topic", "")
        grade_level = data.get("grade_level", "undergraduate")
        duration = data.get("duration", "50 minutes")
        objectives = data.get("learning_objectives", [])
        prior_knowledge = data.get("prior_knowledge", "")
        teaching_style = data.get("teaching_style", "lecture")
    except json.JSONDecodeError:
        # Fallback: extract from plain text
        subject = "General"
        topic = lesson_details
        grade_level = "undergraduate"
        duration = "50 minutes"
        objectives = []
        prior_knowledge = ""
        teaching_style = "lecture"
    
    prompt = f"""Create a comprehensive lesson plan for educators.

**Course Details:**
- Subject: {subject}
- Topic: {topic}
- Grade Level: {grade_level}
- Duration: {duration}
- Teaching Style: {teaching_style}
- Prior Knowledge: {prior_knowledge}

**Requested Learning Objectives:**
{json.dumps(objectives, indent=2) if objectives else "Generate appropriate objectives"}

**Instructions:**
Create a detailed, practical lesson plan with the following sections:

1. **Learning Objectives** (Use Bloom's Taxonomy - Remember, Understand, Apply, Analyze, Evaluate, Create)
   - 3-5 specific, measurable objectives
   - Clearly state what students will be able to do

2. **Materials & Resources**
   - Textbooks, handouts, technology needs
   - Links to resources (if applicable)

3. **Lesson Timeline** (Break down the {duration} into segments)
   - Introduction/Hook (5-10 min)
   - Main Content/Activities (30-40 min)
   - Assessment/Practice (10-15 min)
   - Closure/Homework (5 min)

4. **Detailed Activities**
   For each segment, provide:
   - Teacher actions (what you'll do)
   - Student activities (what they'll do)
   - Discussion questions
   - Examples to use

5. **Assessment Methods**
   - Formative assessment (during class)
   - Summative assessment (end of lesson/unit)
   - Rubric criteria

6. **Differentiation Strategies**
   - For advanced students
   - For struggling students
   - For different learning styles

7. **Homework/Follow-up**
   - Assignment description
   - Expected time commitment
   - Connection to next lesson

8. **Reflection Questions** (for teacher)
   - What worked well?
   - What to adjust for next time?

**Output Format:** Clear, structured markdown with headers and bullet points.
**Tone:** Professional, practical, actionable."""

    response = planning_llm.invoke(prompt)
    
    return response.content


@tool
def design_curriculum(curriculum_details: str) -> str:
    """
    Design a multi-week or semester curriculum for a course.
    
    Input: JSON or text describing the course:
    {
        "course_name": "Introduction to Machine Learning",
        "duration": "15 weeks" or "8 weeks",
        "grade_level": "undergraduate",
        "credits": 3,
        "prerequisites": ["Calculus", "Python Programming"],
        "course_goals": ["Master ML fundamentals", ...],
        "constraints": ["2 lectures + 1 lab per week"]
    }
    
    Output: Complete curriculum with:
    - Course overview
    - Weekly breakdown
    - Learning objectives per unit
    - Assessment schedule
    - Reading list
    - Project ideas
    """
    try:
        data = json.loads(curriculum_details)
        course_name = data.get("course_name", "")
        duration = data.get("duration", "15 weeks")
        grade_level = data.get("grade_level", "undergraduate")
        credits = data.get("credits", 3)
        prerequisites = data.get("prerequisites", [])
        goals = data.get("course_goals", [])
        constraints = data.get("constraints", [])
    except json.JSONDecodeError:
        course_name = curriculum_details
        duration = "15 weeks"
        grade_level = "undergraduate"
        credits = 3
        prerequisites = []
        goals = []
        constraints = []
    
    prompt = f"""Design a comprehensive curriculum for a {duration} course.

**Course Information:**
- Name: {course_name}
- Duration: {duration}
- Level: {grade_level}
- Credits: {credits}
- Prerequisites: {', '.join(prerequisites) if prerequisites else 'None'}

**Course Goals:**
{json.dumps(goals, indent=2) if goals else "Define comprehensive learning goals"}

**Constraints:**
{json.dumps(constraints, indent=2) if constraints else "Standard academic constraints"}

**Instructions:**
Create a detailed curriculum with:

1. **Course Overview**
   - Description (2-3 paragraphs)
   - Learning outcomes (5-8 major outcomes)
   - Assessment breakdown (exams, projects, participation %)

2. **Weekly Schedule**
   For each week, provide:
   - Week number and theme
   - Topics covered
   - Learning objectives
   - Readings/materials
   - Assignments due
   - Key activities

3. **Assessment Schedule**
   - Quizzes (dates, topics, weight)
   - Exams (midterm, final, weight)
   - Projects (description, milestones, weight)
   - Participation (criteria, weight)

4. **Reading List**
   - Textbooks (required)
   - Supplementary readings
   - Online resources
   - Research papers (if applicable)

5. **Project Ideas**
   - 3-5 potential projects
   - Learning objectives addressed
   - Evaluation criteria

6. **Grading Policy**
   - Scale (A, B, C, etc. or numeric)
   - Late submission policy
   - Extra credit opportunities

7. **Course Policies**
   - Attendance
   - Academic integrity
   - Accommodations

**Output Format:** Structured, professional curriculum document."""

    response = planning_llm.invoke(prompt)
    
    return response.content


@tool
def create_learning_objectives(objectives_request: str) -> str:
    """
    Write clear, measurable learning objectives using Bloom's Taxonomy.
    
    Input: Topic and context
    "Create learning objectives for: Neural Networks (undergraduate level, 3-week unit)"
    
    Output: Bloom's Taxonomy aligned objectives:
    - Remember (recall facts)
    - Understand (explain concepts)
    - Apply (use in new situations)
    - Analyze (break down, compare)
    - Evaluate (judge, critique)
    - Create (design, construct)
    """
    prompt = f"""Write clear, measurable learning objectives using Bloom's Taxonomy.

**Topic/Context:**
{objectives_request}

**Instructions:**
Create 8-12 learning objectives across Bloom's Taxonomy levels:

**REMEMBER** (Recall, identify, list)
- Objective 1: Students will be able to [recall/list/identify] ...
- Objective 2: ...

**UNDERSTAND** (Explain, describe, summarize)
- Objective 3: Students will be able to [explain/describe/interpret] ...
- Objective 4: ...

**APPLY** (Use, demonstrate, implement)
- Objective 5: Students will be able to [apply/implement/use] ...
- Objective 6: ...

**ANALYZE** (Compare, differentiate, examine)
- Objective 7: Students will be able to [analyze/compare/differentiate] ...
- Objective 8: ...

**EVALUATE** (Assess, critique, judge)
- Objective 9: Students will be able to [evaluate/critique/justify] ...

**CREATE** (Design, construct, develop)
- Objective 10: Students will be able to [design/create/develop] ...

**Requirements:**
✓ Use action verbs (avoid "know", "learn", "understand" without specifics)
✓ Make them measurable (observable outcomes)
✓ Align with assessment methods
✓ Progress from lower to higher cognitive levels

**Output Format:** Clean list of objectives organized by Bloom's level."""

    response = planning_llm.invoke(prompt)
    
    return response.content


@tool
def design_assessment(assessment_request: str) -> str:
    """
    Design quizzes, exams, or assignments with answer keys.
    
    Input: JSON or text:
    {
        "type": "quiz" or "exam" or "assignment",
        "topic": "Neural Networks",
        "num_questions": 10,
        "difficulty": "medium",
        "question_types": ["multiple_choice", "short_answer", "problem_solving"],
        "learning_objectives": ["Explain backpropagation", ...]
    }
    
    Output: Complete assessment with:
    - Questions
    - Answer key
    - Rubric (for open-ended questions)
    - Estimated time
    """
    try:
        data = json.loads(assessment_request)
        assessment_type = data.get("type", "quiz")
        topic = data.get("topic", "")
        num_questions = data.get("num_questions", 10)
        difficulty = data.get("difficulty", "medium")
        question_types = data.get("question_types", ["multiple_choice"])
        objectives = data.get("learning_objectives", [])
    except json.JSONDecodeError:
        assessment_type = "quiz"
        topic = assessment_request
        num_questions = 10
        difficulty = "medium"
        question_types = ["multiple_choice"]
        objectives = []
    
    prompt = f"""Design a comprehensive {assessment_type} for students.

**Assessment Details:**
- Type: {assessment_type}
- Topic: {topic}
- Number of Questions: {num_questions}
- Difficulty: {difficulty}
- Question Types: {', '.join(question_types)}

**Learning Objectives to Assess:**
{json.dumps(objectives, indent=2) if objectives else "Cover key concepts"}

**Instructions:**
Create a complete assessment with:

1. **Header Information**
   - Title
   - Time limit
   - Total points
   - Instructions for students

2. **Questions** (Create {num_questions} questions)
   For each question:
   - Question number and text
   - Type (MC, short answer, essay, problem-solving)
   - Points value
   - Bloom's level it assesses
   
   Question Types:
   - Multiple Choice: 4 options (A, B, C, D), clear distractors
   - Short Answer: Clear prompt, expected length
   - Essay: Detailed prompt with sub-questions
   - Problem-Solving: Step-by-step problems

3. **Answer Key**
   - Correct answers for all questions
   - Partial credit criteria (if applicable)
   - Common mistakes to watch for

4. **Rubrics** (for open-ended questions)
   - Criteria breakdown
   - Point allocation
   - Example responses (excellent, good, poor)

5. **Metadata**
   - Estimated completion time
   - Difficulty distribution
   - Bloom's taxonomy coverage

**Output Format:** Professional assessment document ready to use."""

    response = planning_llm.invoke(prompt)
    
    return response.content


@tool
def generate_study_materials(materials_request: str) -> str:
    """
    Generate study materials: handouts, slides outlines, worksheets.
    
    Input: Description of needed materials
    "Create a 2-page handout for undergraduate students on neural network architectures"
    
    Output: Ready-to-use study material with:
    - Clear explanations
    - Diagrams descriptions
    - Practice problems
    - Key takeaways
    """
    prompt = f"""Generate educational study materials.

**Request:**
{materials_request}

**Instructions:**
Create comprehensive study materials with:

1. **Title & Overview**
   - Clear, engaging title
   - Brief overview (what students will learn)

2. **Main Content** (organized in logical sections)
   - Clear headings and subheadings
   - Concise explanations
   - Key terms highlighted
   - Examples worked out
   - Diagrams/visuals described
   - Real-world applications

3. **Practice Section**
   - 5-8 practice problems
   - Range of difficulties
   - Solutions/hints included

4. **Summary Section**
   - Key takeaways (bullet points)
   - Common misconceptions addressed
   - Tips for success

5. **Additional Resources**
   - Further reading suggestions
   - Online tools/simulations
   - Video links (if applicable)

**Formatting Guidelines:**
✓ Use clear, student-friendly language
✓ Include visual descriptions [e.g., "Diagram: Neural network with 3 layers"]
✓ Add callout boxes for important concepts
✓ Provide space for student notes
✓ Make it printer-friendly (if handout)

**Output Format:** Complete study material in markdown, ready for distribution."""

    response = planning_llm.invoke(prompt)
    
    return response.content


def get_lesson_planning_tools():
    """Get all lesson planning tools for teachers/professors."""
    return [
        generate_lesson_plan,
        design_curriculum,
        create_learning_objectives,
        design_assessment,
        generate_study_materials
    ]


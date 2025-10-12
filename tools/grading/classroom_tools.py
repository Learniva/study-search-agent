"""
Google Classroom Tools for Grading Agent.

Integrates Google Classroom API with the AI Grading Agent.
Provides tools to fetch assignments, submissions, and post grades.
"""

import json
from typing import Dict, Any, Optional
from langchain.tools import tool
from utils.classroom import get_classroom_service


@tool
def fetch_classroom_courses(teacher_id: str = "me") -> str:
    """
    Fetch all Google Classroom courses for the authenticated teacher.
    
    Input: teacher_id (default: 'me' for current user) or JSON with:
    {
        "teacher_id": "me"
    }
    
    Returns: JSON string with list of courses
    """
    try:
        classroom_service = get_classroom_service()
        
        if not classroom_service.is_available():
            return json.dumps({
                "success": False,
                "error": "Google Classroom integration is not enabled or configured",
                "hint": "Set ENABLE_GOOGLE_CLASSROOM=true in your .env file"
            })
        
        # Parse input - handle both JSON and plain text
        try:
            if teacher_id.startswith("{"):
                data = json.loads(teacher_id)
                teacher_id = data.get("teacher_id", "me")
            else:
                # If it's a full question/sentence, just use 'me'
                if len(teacher_id.split()) > 2:
                    teacher_id = "me"
        except json.JSONDecodeError:
            teacher_id = "me"
        
        courses = classroom_service.list_courses(teacher_id=teacher_id)
    except Exception as e:
        return json.dumps({
            "success": False,
            "error": f"Error fetching courses: {str(e)}",
            "hint": "Check your Google Classroom credentials and authentication"
        })
    
    if not courses:
        return json.dumps({
            "success": True,
            "courses": [],
            "message": "No courses found"
        })
    
    # Format course information
    formatted_courses = []
    for course in courses:
        formatted_courses.append({
            "id": course.get("id"),
            "name": course.get("name"),
            "section": course.get("section", ""),
            "description": course.get("description", ""),
            "enrollment_code": course.get("enrollmentCode", ""),
            "state": course.get("courseState")
        })
    
    return json.dumps({
        "success": True,
        "courses": formatted_courses,
        "count": len(formatted_courses)
    }, indent=2)


@tool
def fetch_classroom_assignments(course_assignments_info: str) -> str:
    """
    Fetch all assignments (coursework) for a Google Classroom course.
    
    Input (JSON string):
    {
        "course_id": "123456789"
    }
    
    Or simple format:
    "course_id" or "Show me assignments from course 123456789"
    
    Returns: JSON string with list of assignments
    """
    try:
        classroom_service = get_classroom_service()
        
        if not classroom_service.is_available():
            return json.dumps({
                "success": False,
                "error": "Google Classroom integration is not enabled or configured",
                "hint": "Set ENABLE_GOOGLE_CLASSROOM=true in your .env file"
            })
        
        # Parse input - handle JSON, plain course ID, or natural language
        course_id = None
        try:
            data = json.loads(course_assignments_info)
            course_id = data.get("course_id")
        except json.JSONDecodeError:
            # Try to extract course ID from natural language
            import re
            # Look for numeric course ID
            match = re.search(r'\b(\d{10,})\b', course_assignments_info)
            if match:
                course_id = match.group(1)
            else:
                course_id = course_assignments_info.strip()
        
        if not course_id:
            return json.dumps({
                "success": False,
                "error": "course_id is required",
                "hint": "Provide a course ID (e.g., '717842350721')"
            })
        
        # Fetch both coursework (graded assignments) and materials (non-graded)
        coursework = classroom_service.list_course_work(course_id)
        materials = classroom_service.list_course_work_materials(course_id)
    except Exception as e:
        return json.dumps({
            "success": False,
            "error": f"Error fetching assignments: {str(e)}",
            "hint": "Check if the course ID is valid and you have access to this course"
        })
    
    # Format assignment information
    formatted_assignments = []
    
    # Add coursework (graded assignments)
    for work in coursework:
        formatted_assignments.append({
            "id": work.get("id"),
            "title": work.get("title"),
            "description": work.get("description", ""),
            "state": work.get("state"),
            "type": "assignment",
            "work_type": work.get("workType"),
            "max_points": work.get("maxPoints"),
            "due_date": work.get("dueDate"),
            "due_time": work.get("dueTime"),
            "creation_time": work.get("creationTime"),
            "update_time": work.get("updateTime")
        })
    
    # Add materials (non-graded)
    for material in materials:
        formatted_assignments.append({
            "id": material.get("id"),
            "title": material.get("title"),
            "description": material.get("description", ""),
            "state": material.get("state"),
            "type": "material",
            "work_type": "MATERIAL",
            "max_points": None,
            "due_date": None,
            "due_time": None,
            "creation_time": material.get("creationTime"),
            "update_time": material.get("updateTime")
        })
    
    if not formatted_assignments:
        return json.dumps({
            "success": True,
            "assignments": [],
            "message": f"No assignments or materials found for course {course_id}"
        })
    
    return json.dumps({
        "success": True,
        "course_id": course_id,
        "assignments": formatted_assignments,
        "count": len(formatted_assignments),
        "coursework_count": len(coursework),
        "materials_count": len(materials)
    }, indent=2)


@tool
def fetch_classroom_submissions(submission_request: str) -> str:
    """
    Fetch student submissions for a specific assignment in Google Classroom.
    
    Input (JSON string):
    {
        "course_id": "123456789",
        "assignment_id": "987654321"
    }
    
    Or natural language: "Get submissions for course 123 assignment 456"
    
    Returns: JSON string with list of student submissions
    """
    classroom_service = get_classroom_service()
    
    if not classroom_service.is_available():
        return json.dumps({
            "success": False,
            "error": "Google Classroom integration is not enabled or configured"
        })
    
    # Parse input - handle JSON or natural language
    course_id = None
    assignment_id = None
    
    try:
        data = json.loads(submission_request)
        course_id = data.get("course_id")
        assignment_id = data.get("assignment_id")
    except json.JSONDecodeError:
        # Try to extract IDs from natural language
        import re
        numbers = re.findall(r'\b(\d{10,})\b', submission_request)
        if len(numbers) >= 2:
            course_id = numbers[0]
            assignment_id = numbers[1]
        elif len(numbers) == 1:
            return json.dumps({
                "success": False,
                "error": "Both course_id and assignment_id are required. Found only one ID."
            })
        else:
            return json.dumps({
                "success": False,
                "error": "Invalid format. Required: course_id and assignment_id"
            })
    
    if not course_id or not assignment_id:
        return json.dumps({
            "success": False,
            "error": "Both course_id and assignment_id are required"
        })
    
    submissions = classroom_service.list_student_submissions(course_id, assignment_id)
    
    if not submissions:
        return json.dumps({
            "success": True,
            "submissions": [],
            "message": "No submissions found"
        })
    
    # Format submission information
    formatted_submissions = []
    for submission in submissions:
        formatted_submissions.append({
            "id": submission.get("id"),
            "user_id": submission.get("userId"),
            "course_id": submission.get("courseId"),
            "coursework_id": submission.get("courseWorkId"),
            "state": submission.get("state"),
            "assigned_grade": submission.get("assignedGrade"),
            "draft_grade": submission.get("draftGrade"),
            "creation_time": submission.get("creationTime"),
            "update_time": submission.get("updateTime"),
            "submission_history": len(submission.get("submissionHistory", [])),
            "late": submission.get("late", False)
        })
    
    return json.dumps({
        "success": True,
        "course_id": course_id,
        "assignment_id": assignment_id,
        "submissions": formatted_submissions,
        "count": len(formatted_submissions)
    }, indent=2)


@tool
def get_classroom_submission_details(submission_request: str) -> str:
    """
    Get detailed information about a specific student submission.
    
    Input (JSON string):
    {
        "course_id": "123456789",
        "assignment_id": "987654321",
        "submission_id": "Cg4I..."
    }
    
    Returns: JSON string with detailed submission information
    """
    classroom_service = get_classroom_service()
    
    if not classroom_service.is_available():
        return json.dumps({
            "success": False,
            "error": "Google Classroom integration is not enabled or configured"
        })
    
    # Parse input - handle JSON or natural language
    course_id = None
    assignment_id = None
    submission_id = None
    
    try:
        data = json.loads(submission_request)
        course_id = data.get("course_id")
        assignment_id = data.get("assignment_id")
        submission_id = data.get("submission_id")
    except json.JSONDecodeError:
        # Try to extract IDs from natural language
        import re
        numbers = re.findall(r'\b(\d{10,})\b', submission_request)
        submission_ids = re.findall(r'\b(Cg[A-Za-z0-9_-]+)\b', submission_request)
        
        if len(numbers) >= 2 and len(submission_ids) >= 1:
            course_id = numbers[0]
            assignment_id = numbers[1]
            submission_id = submission_ids[0]
        elif len(numbers) >= 2:
            course_id = numbers[0]
            assignment_id = numbers[1]
            # Try to find submission ID in the text
            submission_match = re.search(r'\bsubmission\s+([A-Za-z0-9_-]+)', submission_request)
            if submission_match:
                submission_id = submission_match.group(1)
            else:
                return json.dumps({
                    "success": False,
                    "error": "Could not find submission ID in the request. Please include the submission ID."
                })
        else:
            return json.dumps({
                "success": False,
                "error": "Could not extract course_id, assignment_id, and submission_id from the request."
            })
    
    if not all([course_id, assignment_id, submission_id]):
        return json.dumps({
            "success": False,
            "error": "course_id, assignment_id, and submission_id are all required"
        })
    
    submission = classroom_service.get_student_submission(
        course_id, assignment_id, submission_id
    )
    
    if not submission:
        return json.dumps({
            "success": False,
            "error": "Submission not found"
        })
    
    return json.dumps({
        "success": True,
        "submission": submission
    }, indent=2)


@tool
def fetch_submission_content(submission_request: str) -> str:
    """
    Fetch the actual content of student submission files from Google Drive.
    
    Input (JSON string):
    {
        "course_id": "123456789",
        "assignment_id": "987654321",
        "submission_id": "Cg4I..."
    }
    
    Or natural language: "Get content for course 123 assignment 456 submission Cg4I..."
    
    Returns: JSON string with submission content from all attached files
    """
    classroom_service = get_classroom_service()
    
    if not classroom_service.is_available():
        return json.dumps({
            "success": False,
            "error": "Google Classroom integration is not enabled or configured"
        })
    
    # Parse input - handle JSON or natural language
    course_id = None
    assignment_id = None
    submission_id = None
    
    try:
        data = json.loads(submission_request)
        course_id = data.get("course_id")
        assignment_id = data.get("assignment_id")
        submission_id = data.get("submission_id")
    except json.JSONDecodeError:
        # Try to extract IDs from natural language
        import re
        numbers = re.findall(r'\b(\d{10,})\b', submission_request)
        submission_ids = re.findall(r'\b(Cg[A-Za-z0-9_-]+)\b', submission_request)
        
        if len(numbers) >= 2 and len(submission_ids) >= 1:
            course_id = numbers[0]
            assignment_id = numbers[1]
            submission_id = submission_ids[0]
        elif len(numbers) >= 2:
            course_id = numbers[0]
            assignment_id = numbers[1]
            # Try to find submission ID in the text
            submission_match = re.search(r'\bsubmission\s+([A-Za-z0-9_-]+)', submission_request)
            if submission_match:
                submission_id = submission_match.group(1)
            else:
                return json.dumps({
                    "success": False,
                    "error": "Could not find submission ID in the request. Please include the submission ID."
                })
        else:
            return json.dumps({
                "success": False,
                "error": "Could not extract course_id, assignment_id, and submission_id from the request."
            })
    
    if not all([course_id, assignment_id, submission_id]):
        return json.dumps({
            "success": False,
            "error": "course_id, assignment_id, and submission_id are all required"
        })
    
    # Get submission details first
    submission = classroom_service.get_student_submission(
        course_id, assignment_id, submission_id
    )
    
    if not submission:
        return json.dumps({
            "success": False,
            "error": "Submission not found"
        })
    
    # Extract file attachments
    attachments = []
    if 'assignmentSubmission' in submission and 'attachments' in submission['assignmentSubmission']:
        attachments = submission['assignmentSubmission']['attachments']
    
    if not attachments:
        return json.dumps({
            "success": False,
            "error": "No file attachments found in submission"
        })
    
    # Fetch content from each attachment
    submission_content = {
        "submission_id": submission_id,
        "student_id": submission.get('userId'),
        "course_id": course_id,
        "assignment_id": assignment_id,
        "files": []
    }
    
    for attachment in attachments:
        if 'driveFile' in attachment:
            drive_file = attachment['driveFile']
            file_id = drive_file['id']
            file_title = drive_file['title']
            
            # Fetch the document content
            content = classroom_service.get_drive_document_content(file_id)
            
            if content:
                submission_content['files'].append({
                    "file_id": file_id,
                    "title": file_title,
                    "content": content,
                    "alternate_link": drive_file.get('alternateLink')
                })
            else:
                submission_content['files'].append({
                    "file_id": file_id,
                    "title": file_title,
                    "content": None,
                    "error": "Could not fetch content",
                    "alternate_link": drive_file.get('alternateLink')
                })
    
    return json.dumps({
        "success": True,
        "submission_content": submission_content
    }, indent=2)


@tool
def post_grade_to_classroom(grading_request: str) -> str:
    """
    Post a grade to Google Classroom for a student submission.
    
    Input (JSON string):
    {
        "course_id": "123456789",
        "assignment_id": "987654321",
        "submission_id": "Cg4I...",
        "grade": 85.5,
        "feedback": "Excellent work! Clear arguments and good evidence."
    }
    
    Returns: JSON string with success/failure status
    """
    classroom_service = get_classroom_service()
    
    if not classroom_service.is_available():
        return json.dumps({
            "success": False,
            "error": "Google Classroom integration is not enabled or configured"
        })
    
    # Parse input
    try:
        data = json.loads(grading_request)
        course_id = data.get("course_id")
        assignment_id = data.get("assignment_id")
        submission_id = data.get("submission_id")
        grade = data.get("grade")
        feedback = data.get("feedback", "")
    except json.JSONDecodeError:
        return json.dumps({
            "success": False,
            "error": "Invalid JSON format"
        })
    
    if not all([course_id, assignment_id, submission_id]) or grade is None:
        return json.dumps({
            "success": False,
            "error": "course_id, assignment_id, submission_id, and grade are all required"
        })
    
    # Validate grade
    try:
        grade = float(grade)
    except (TypeError, ValueError):
        return json.dumps({
            "success": False,
            "error": "Grade must be a number"
        })
    
    success = classroom_service.grade_submission(
        course_id=course_id,
        coursework_id=assignment_id,
        submission_id=submission_id,
        grade=grade,
        feedback=feedback
    )
    
    if success:
        return json.dumps({
            "success": True,
            "message": f"Successfully posted grade {grade} to Google Classroom",
            "grade": grade,
            "course_id": course_id,
            "assignment_id": assignment_id,
            "submission_id": submission_id
        }, indent=2)
    else:
        return json.dumps({
            "success": False,
            "error": "Failed to post grade to Google Classroom"
        })


@tool
def fetch_classroom_rubrics(rubric_request: str) -> str:
    """
    Fetch rubrics for a Google Classroom assignment.
    
    Input (JSON string):
    {
        "course_id": "123456789",
        "assignment_id": "987654321"
    }
    
    Returns: JSON string with rubric information
    """
    classroom_service = get_classroom_service()
    
    if not classroom_service.is_available():
        return json.dumps({
            "success": False,
            "error": "Google Classroom integration is not enabled or configured"
        })
    
    # Parse input
    try:
        data = json.loads(rubric_request)
        course_id = data.get("course_id")
        assignment_id = data.get("assignment_id")
    except json.JSONDecodeError:
        return json.dumps({
            "success": False,
            "error": "Invalid JSON format. Required: course_id and assignment_id"
        })
    
    if not course_id or not assignment_id:
        return json.dumps({
            "success": False,
            "error": "Both course_id and assignment_id are required"
        })
    
    rubrics = classroom_service.list_rubrics(course_id, assignment_id)
    
    if not rubrics:
        return json.dumps({
            "success": True,
            "rubrics": [],
            "message": "No rubrics found for this assignment"
        })
    
    return json.dumps({
        "success": True,
        "course_id": course_id,
        "assignment_id": assignment_id,
        "rubrics": rubrics,
        "count": len(rubrics)
    }, indent=2)


def get_classroom_tools():
    """
    Get all Google Classroom tools for the grading agent.
    
    Returns:
        List of Google Classroom tools
    """
    return [
        fetch_classroom_courses,
        fetch_classroom_assignments,
        fetch_classroom_submissions,
        get_classroom_submission_details,
        fetch_submission_content,
        post_grade_to_classroom,
        fetch_classroom_rubrics
    ]


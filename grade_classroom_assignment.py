#!/usr/bin/env python3
"""
Grade Google Classroom Assignment

Interactive script to fetch, grade, and post results back to Google Classroom.
"""

import sys
import os
import json

# Add parent directory to path
sys.path.insert(0, os.path.abspath(os.path.dirname(__file__)))

from agents.grading import GradingAgent


def print_banner(text):
    """Print a formatted banner."""
    print("\n" + "=" * 80)
    print(f"  {text}")
    print("=" * 80)


def print_section(text):
    """Print a section header."""
    print("\n" + "-" * 80)
    print(f"  {text}")
    print("-" * 80)


def main():
    """Main interactive grading workflow."""
    print_banner(" Google Classroom Assignment Grading Tool")
    print("\nThis tool will help you:")
    print("  1. List your Google Classroom courses")
    print("  2. Fetch assignments from a course")
    print("  3. Get student submissions")
    print("  4. Fetch submission content (Google Docs, etc.)")
    print("  5. Grade the submission with AI")
    print("  6. Post the grade back to Google Classroom")
    
    print("\n Initializing Grading Agent...")
    try:
        agent = GradingAgent()
        print(" Grading Agent initialized successfully!")
    except Exception as e:
        print(f" Error initializing agent: {e}")
        return
    
    # Step 1: List courses
    print_banner("Step 1: List Your Google Classroom Courses")
    print("\nFetching courses...")
    
    try:
        result = agent.query("Show me all my Google Classroom courses")
        print("\n" + result)
        
        # Try to parse the result to show courses nicely
        if "courses" in result.lower():
            print("\n Copy the course ID for the next step")
    except Exception as e:
        print(f" Error: {e}")
        return
    
    # Get course ID from user
    print_section("Enter Course Information")
    course_id = input("\nPaste the course ID you want to grade: ").strip()
    
    if not course_id:
        print(" No course ID provided. Exiting.")
        return
    
    # Step 2: List assignments
    print_banner("Step 2: Fetch Assignments from Course")
    print(f"\nFetching assignments for course {course_id}...")
    
    try:
        result = agent.query(f"Fetch assignments from course {course_id}")
        print("\n" + result)
        
        print("\n Copy the assignment ID for the next step")
    except Exception as e:
        print(f" Error: {e}")
        return
    
    # Get assignment ID from user
    print_section("Enter Assignment Information")
    assignment_id = input("\nPaste the assignment ID you want to grade: ").strip()
    
    if not assignment_id:
        print(" No assignment ID provided. Exiting.")
        return
    
    # Step 3: List submissions
    print_banner("Step 3: Fetch Student Submissions")
    print(f"\nFetching submissions for assignment {assignment_id}...")
    
    try:
        query = json.dumps({
            "course_id": course_id,
            "assignment_id": assignment_id
        })
        result = agent.query(f"Fetch student submissions: {query}")
        print("\n" + result)
        
        print("\n Copy the submission ID for the next step")
    except Exception as e:
        print(f" Error: {e}")
        return
    
    # Get submission ID from user
    print_section("Enter Submission Information")
    submission_id = input("\nPaste the submission ID you want to grade: ").strip()
    
    if not submission_id:
        print(" No submission ID provided. Exiting.")
        return
    
    # Step 4: Fetch submission content
    print_banner("Step 4: Fetch Submission Content (Google Docs)")
    print(f"\nFetching content from submission {submission_id}...")
    
    try:
        query = json.dumps({
            "course_id": course_id,
            "assignment_id": assignment_id,
            "submission_id": submission_id
        })
        result = agent.query(f"Fetch submission content: {query}")
        print("\n" + result)
        
        # Try to extract the actual content
        submission_content = None
        if "content" in result.lower():
            print("\n Successfully fetched submission content!")
            # Save for grading
            submission_content = result
    except Exception as e:
        print(f" Error: {e}")
        return
    
    # Step 5: Grade the submission
    print_banner("Step 5: Grade the Submission")
    
    # Ask for grading options
    print("\nGrading Options:")
    print("  1. Grade with default rubric (essay)")
    print("  2. Grade as code review")
    print("  3. Grade with specific rubric")
    print("  4. Just provide feedback (no score)")
    
    choice = input("\nSelect grading option (1-4): ").strip()
    
    print("\nGrading submission...")
    try:
        if choice == "1":
            result = agent.query(f"Grade this submission as an essay:\n\n{submission_content}")
        elif choice == "2":
            result = agent.query(f"Review this code submission:\n\n{submission_content}")
        elif choice == "3":
            rubric_name = input("Enter rubric name (e.g., 'essay_general', 'code_review_general'): ").strip()
            result = agent.query(f"Grade this submission using {rubric_name} rubric:\n\n{submission_content}")
        elif choice == "4":
            result = agent.query(f"Provide feedback on this submission:\n\n{submission_content}")
        else:
            result = agent.query(f"Grade this submission:\n\n{submission_content}")
        
        print("\n" + "=" * 80)
        print("GRADING RESULT:")
        print("=" * 80)
        print(result)
        print("=" * 80)
        
    except Exception as e:
        print(f" Error: {e}")
        return
    
    # Step 6: Post grade to Google Classroom
    print_banner("Step 6: Post Grade to Google Classroom")
    
    post_grade = input("\nDo you want to post this grade to Google Classroom? (y/n): ").strip().lower()
    
    if post_grade == 'y':
        grade_value = input("Enter the numerical grade (e.g., 85): ").strip()
        
        try:
            grade_value = float(grade_value)
        except ValueError:
            print(" Invalid grade value. Must be a number.")
            return
        
        # Extract feedback from result (simplified - in practice would parse more carefully)
        feedback = input("\nEnter feedback to post (or press Enter to use AI feedback):\n").strip()
        if not feedback:
            feedback = "Please see detailed feedback from the grading system."
        
        print("\n Posting grade to Google Classroom...")
        
        try:
            query = json.dumps({
                "course_id": course_id,
                "assignment_id": assignment_id,
                "submission_id": submission_id,
                "grade": grade_value,
                "feedback": feedback
            })
            result = agent.query(f"Post this grade to Google Classroom: {query}")
            print("\n" + result)
            
            if "success" in result.lower():
                print("\n Grade successfully posted to Google Classroom!")
            else:
                print("\n  There may have been an issue posting the grade.")
        except Exception as e:
            print(f" Error posting grade: {e}")
            return
    else:
        print("\n Grade not posted. You can review it and post manually.")
    
    print_banner(" Grading Complete!")
    print("\nSummary:")
    print(f"  • Course ID: {course_id}")
    print(f"  • Assignment ID: {assignment_id}")
    print(f"  • Submission ID: {submission_id}")
    if post_grade == 'y':
        print(f"  • Grade: {grade_value}")
        print(f"  • Status: Posted to Google Classroom")
    else:
        print(f"  • Status: Graded locally (not posted)")


def quick_grade():
    """Quick grade if you already have the IDs."""
    print_banner(" Quick Grade Mode")
    print("\nYou'll need:")
    print("  • Course ID")
    print("  • Assignment ID")
    print("  • Submission ID")
    
    course_id = input("\nCourse ID: ").strip()
    assignment_id = input("Assignment ID: ").strip()
    submission_id = input("Submission ID: ").strip()
    
    if not all([course_id, assignment_id, submission_id]):
        print(" All IDs are required!")
        return
    
    print("\n Initializing Grading Agent...")
    agent = GradingAgent()
    
    # Fetch and grade
    print("\n Fetching submission content...")
    query = json.dumps({
        "course_id": course_id,
        "assignment_id": assignment_id,
        "submission_id": submission_id
    })
    
    content_result = agent.query(f"Fetch submission content: {query}")
    print("\n Content fetched!")
    
    print("\n Grading submission...")
    grade_result = agent.query(f"Grade this submission:\n\n{content_result}")
    
    print("\n" + "=" * 80)
    print("GRADING RESULT:")
    print("=" * 80)
    print(grade_result)
    print("=" * 80)
    
    # Ask to post
    post = input("\nPost grade to Google Classroom? (y/n): ").strip().lower()
    if post == 'y':
        grade = float(input("Grade (numerical): "))
        feedback = input("Feedback: ").strip()
        
        post_query = json.dumps({
            "course_id": course_id,
            "assignment_id": assignment_id,
            "submission_id": submission_id,
            "grade": grade,
            "feedback": feedback
        })
        
        result = agent.query(f"Post this grade to Google Classroom: {post_query}")
        print("\n" + result)


if __name__ == "__main__":
    import sys
    
    print("\n Welcome to the Google Classroom Grading Tool!")
    print("\nSelect mode:")
    print("  1. Interactive mode (step-by-step)")
    print("  2. Quick mode (if you have IDs ready)")
    print("  3. Exit")
    
    choice = input("\nYour choice (1-3): ").strip()
    
    if choice == "1":
        main()
    elif choice == "2":
        quick_grade()
    else:
        print("\n Goodbye!")
        sys.exit(0)


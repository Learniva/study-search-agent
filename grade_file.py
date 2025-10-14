#!/usr/bin/env python3
"""
Helper script to grade submissions from test_submissions/ directory.

Usage:
    python grade_file.py <filename>
    python grade_file.py intro_programming_assignment.py
    python grade_file.py essay_good.txt
    python grade_file.py --list  # Show all available files

Examples:
    # Grade a Python assignment
    python grade_file.py intro_programming_assignment.py
    
    # Grade an essay
    python grade_file.py essay_good.txt
    
    # Grade with custom student info
    python grade_file.py intro_programming_assignment.py --student "John Doe" --student-id "stu123"
"""

import sys
import os
from pathlib import Path
from agents.supervisor import SupervisorAgent


def list_available_files():
    """List all available files in test_submissions/"""
    test_dir = Path("test_submissions")
    
    if not test_dir.exists():
        print("❌ test_submissions/ directory not found")
        return
    
    files = sorted(test_dir.glob("*"))
    files = [f for f in files if f.is_file() and f.name != "README.md"]
    
    if not files:
        print("📁 No files found in test_submissions/")
        return
    
    print("\n" + "="*80)
    print("📁 AVAILABLE FILES IN test_submissions/")
    print("="*80)
    
    # Group by type
    python_files = [f for f in files if f.suffix == ".py"]
    text_files = [f for f in files if f.suffix == ".txt"]
    other_files = [f for f in files if f not in python_files and f not in text_files]
    
    if python_files:
        print("\n💻 Python Code:")
        for f in python_files:
            size = f.stat().st_size
            print(f"   • {f.name} ({size} bytes)")
    
    if text_files:
        print("\n📝 Text Submissions:")
        for f in text_files:
            size = f.stat().st_size
            print(f"   • {f.name} ({size} bytes)")
    
    if other_files:
        print("\n📄 Other Files:")
        for f in other_files:
            size = f.stat().st_size
            print(f"   • {f.name} ({size} bytes)")
    
    print("\n" + "="*80)
    print("Usage: python grade_file.py <filename>")
    print("="*80 + "\n")


def grade_file(filename, student_name=None, student_id=None, professor_id="teacher_001"):
    """Grade a file from test_submissions/"""
    
    # Construct file path
    filepath = Path("test_submissions") / filename
    
    # Check if file exists
    if not filepath.exists():
        print(f"❌ File not found: {filepath}")
        print("\n💡 Available files:")
        list_available_files()
        return False
    
    # Read file content
    try:
        with open(filepath, 'r', encoding='utf-8') as f:
            content = f.read()
    except Exception as e:
        print(f"❌ Error reading file: {e}")
        return False
    
    # Determine submission type
    file_ext = filepath.suffix.lower()
    
    if file_ext == ".py":
        question = f"Review code:\n\n```python\n{content}\n```"
    elif file_ext == ".txt":
        # Check content to determine type
        content_lower = content.lower()
        if any(word in content_lower for word in ["essay", "paragraph", "introduction", "conclusion"]):
            question = f"Grade this essay:\n\n{content}"
        else:
            question = f"Grade this submission:\n\n{content}"
    else:
        question = f"Grade this submission ({file_ext}):\n\n{content}"
    
    # Display info
    print("\n" + "="*80)
    print("📝 GRADING SUBMISSION")
    print("="*80)
    print(f"File: {filename}")
    print(f"Size: {len(content)} characters")
    print(f"Type: {file_ext}")
    if student_name:
        print(f"Student: {student_name}")
    if student_id:
        print(f"Student ID: {student_id}")
    print("="*80)
    print("\n🔄 Processing with AI Grading Agent...\n")
    
    # Initialize supervisor and grade
    try:
        supervisor = SupervisorAgent()
        
        result = supervisor.query(
            question=question,
            user_role="teacher",
            user_id=professor_id,
            student_id=student_id or "unknown_student",
            student_name=student_name or "Unknown Student"
        )
        
        # Display results
        if result.get("answer"):
            print(result["answer"])
        elif result.get("final_answer"):
            print(result["final_answer"])
        else:
            print("❌ No grading result returned")
            print(f"Debug - Result keys: {list(result.keys())}")
            if result.get("error"):
                print(f"Error: {result['error']}")
            return False
        
        return True
        
    except Exception as e:
        print(f"❌ Error during grading: {e}")
        import traceback
        traceback.print_exc()
        return False


def main():
    """Main entry point"""
    
    # Parse arguments
    if len(sys.argv) < 2:
        print("""
╔════════════════════════════════════════════════════════════════════════════╗
║                    GRADING HELPER SCRIPT                                   ║
╚════════════════════════════════════════════════════════════════════════════╝

Usage:
    python grade_file.py <filename>                    # Grade a file
    python grade_file.py --list                        # List available files
    python grade_file.py <filename> --student "Name"   # With student name
    python grade_file.py --help                        # Show this help

Examples:
    python grade_file.py intro_programming_assignment.py
    python grade_file.py essay_good.txt
    python grade_file.py cs_algorithm_sorting.py --student "Alice" --student-id "stu123"

Available Flags:
    --list              List all files in test_submissions/
    --student NAME      Specify student name
    --student-id ID     Specify student ID
    --professor-id ID   Specify professor ID (default: teacher_001)
    --help, -h          Show this help message
""")
        list_available_files()
        sys.exit(0)
    
    # Check for flags
    if sys.argv[1] in ["--list", "-l"]:
        list_available_files()
        sys.exit(0)
    
    if sys.argv[1] in ["--help", "-h"]:
        print(__doc__)
        sys.exit(0)
    
    # Parse arguments
    filename = sys.argv[1]
    student_name = None
    student_id = None
    professor_id = "teacher_001"
    
    # Parse additional flags
    i = 2
    while i < len(sys.argv):
        if sys.argv[i] == "--student" and i + 1 < len(sys.argv):
            student_name = sys.argv[i + 1]
            i += 2
        elif sys.argv[i] == "--student-id" and i + 1 < len(sys.argv):
            student_id = sys.argv[i + 1]
            i += 2
        elif sys.argv[i] == "--professor-id" and i + 1 < len(sys.argv):
            professor_id = sys.argv[i + 1]
            i += 2
        else:
            print(f"⚠️  Unknown flag: {sys.argv[i]}")
            i += 1
    
    # Grade the file
    success = grade_file(
        filename,
        student_name=student_name,
        student_id=student_id,
        professor_id=professor_id
    )
    
    sys.exit(0 if success else 1)


if __name__ == "__main__":
    main()


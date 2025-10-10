"""
Main entry point for the Multi-Agent Study & Grading System.

Supports role-based access control:
- Students: Can access study features only
- Teachers: Can access study + grading features

Usage:
    python main.py --role professor        # Start as professor
    python main.py --role student          # Start as student
    python main.py                         # Will prompt for role
"""

import os
import sys
import argparse
from dotenv import load_dotenv

# Updated imports for refactored agent structure
from agents.supervisor.core import SupervisorAgent

# Load environment variables
load_dotenv()


def get_user_role(args):
    """
    Get user role from command line flag or interactive prompt.
    
    Args:
        args: Parsed command line arguments
        
    Returns:
        str: User role (student, teacher, professor, instructor, admin)
    """
    # Method 1: Using Flag (Recommended)
    if args.role:
        role = args.role.lower()
        print(f"🎓 Role set via flag: {role.upper()}")
        return role
    
    # Method 2: Using Prompt
    print("\n" + "="*70)
    print("  🎓 Multi-Agent Study & Grading System")
    print("="*70)
    print("\nPlease select your role:")
    print("  1. Student   - Access study features (research, Q&A, animations)")
    print("  2. Teacher   - Access study + grading features")
    print("  3. Professor - Same as teacher")
    print("  4. Admin     - Full access")
    
    while True:
        choice = input("\nEnter your choice (1-4) or role name: ").strip().lower()
        
        # Map choices to roles
        role_map = {
            "1": "student",
            "2": "teacher",
            "3": "professor",
            "4": "admin",
            "student": "student",
            "teacher": "teacher",
            "professor": "teacher",  # Treat professor as teacher
            "instructor": "teacher",
            "admin": "admin"
        }
        
        if choice in role_map:
            role = role_map[choice]
            print(f"\n✅ Role selected: {role.upper()}")
            return role
        else:
            print("❌ Invalid choice. Please enter 1-4 or a valid role name.")


def main():
    """Main entry point for the multi-agent system."""
    
    # Parse command line arguments
    parser = argparse.ArgumentParser(
        description="Multi-Agent Study & Grading System with role-based access",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  python main.py --role professor       Start as professor
  python main.py --role student         Start as student
  python main.py                        Will prompt for role
  python main.py --role teacher --question "Grade this essay..."
        """
    )
    
    parser.add_argument(
        "--role",
        type=str,
        choices=["student", "teacher", "professor", "instructor", "admin"],
        help="User role (student, teacher, professor, instructor, or admin)"
    )
    
    parser.add_argument(
        "--question",
        type=str,
        help="Single question to process (non-interactive mode)"
    )
    
    parser.add_argument(
        "--user-id",
        type=str,
        help="User ID for database tracking (optional)"
    )
    
    args = parser.parse_args()
    
    # Get user role
    user_role = get_user_role(args)
    
    # Normalize professor/instructor to teacher
    if user_role in ["professor", "instructor"]:
        user_role = "teacher"
    
    # Get LLM provider from environment
    llm_provider = os.getenv("LLM_PROVIDER", "gemini")
    
    print(f"\n🚀 Initializing Multi-Agent System with {llm_provider.upper()}...")
    print(f"👤 Your Role: {user_role.upper()}\n")
    
    # Auto-index documents from documents/ folder into L2 Vector Store
    documents_dir = os.getenv("DOCUMENTS_DIR", "documents")
    if os.path.exists(documents_dir) and os.listdir(documents_dir):
        print(f"📚 Documents directory found: {documents_dir}")
        try:
            from database.operations.document_loader import initialize_document_store
            print("🔄 Indexing documents into vector store...")
            success = initialize_document_store(documents_dir)
            if success:
                print("✅ Documents indexed and ready for Q&A\n")
            else:
                print("⚠️  Some documents failed to index (see logs)\n")
        except Exception as e:
            print(f"⚠️  Document indexing skipped: {str(e)}")
            print("💡 Documents will be available after manual upload via API\n")
    
    try:
        # Initialize supervisor agent
        supervisor = SupervisorAgent(llm_provider=llm_provider)
        
        # Get user ID (for database tracking)
        user_id = args.user_id or user_role + "_cli_user"
        
        # Check if a question was provided as command line argument
        if args.question:
            question = args.question
            print(f"Question: {question}\n")
            print("=" * 70)
            
            result = supervisor.query(
                question=question,
                user_role=user_role,
                user_id=user_id
            )
            
            print("=" * 70)
            print(f"\n✅ Agent Used: {result.get('agent_used', 'N/A')}")
            print(f"\n{result['answer']}\n")
        else:
            # Start interactive chat mode
            print("\n" + "="*70)
            print(f"  Interactive Mode - Role: {user_role.upper()}")
            print("="*70)
            
            # Show capabilities for this role
            capabilities = supervisor.get_capabilities(user_role)
            
            print("\n📚 Your Available Features:")
            for feature in capabilities["study_features"]:
                print(f"   {feature}")
            
            if capabilities["grading_features"]:
                print("\n📝 Your Grading Features:")
                for feature in capabilities["grading_features"]:
                    print(f"   {feature}")
            
            print("\n💡 Special Commands:")
            print("   'arch' - Show system architecture")
            print("   'caps' - Show your capabilities")
            print("   'help' - Show help message")
            print("   'quit', 'exit', 'q' - Exit program")
            print()
            
            # Interactive loop
            while True:
                try:
                    question = input(f"\n[{user_role.upper()}] Your request: ").strip()
                    
                    if question.lower() in ['quit', 'exit', 'q']:
                        print("\n👋 Goodbye! Happy learning and teaching!")
                        break
                    
                    if question.lower() == 'arch':
                        print(supervisor.visualize_architecture())
                        continue
                    
                    if question.lower() == 'caps':
                        caps = supervisor.get_capabilities(user_role)
                        print(f"\n📋 Capabilities for {user_role.upper()}:")
                        print("\n📚 Study Features:")
                        for f in caps["study_features"]:
                            print(f"  {f}")
                        if caps["grading_features"]:
                            print("\n📝 Grading Features:")
                            for f in caps["grading_features"]:
                                print(f"  {f}")
                        continue
                    
                    if question.lower() == 'help':
                        print("\n" + "="*70)
                        print("  HELP - Multi-Agent System")
                        print("="*70)
                        print(f"\nYour Role: {user_role.upper()}")
                        print("\nHow to use:")
                        print("  • Type your question naturally")
                        print("  • System automatically routes to the right agent")
                        print("  • Students: Get study help")
                        print("  • Teachers: Get study help + grading assistance")
                        print("\nExamples:")
                        if user_role == "student":
                            print("  'Explain quantum physics'")
                            print("  'Generate 10 MCQs about biology'")
                            print("  'Animate the Pythagorean theorem'")
                        else:
                            print("  'Grade this essay: [paste essay]'")
                            print("  'Review this Python code: [paste code]'")
                            print("  'Generate study guide for calculus'")
                        print("="*70)
                        continue
                    
                    if not question:
                        continue
                    
                    # Process request through supervisor
                    print("\n" + "="*70)
                    
                    result = supervisor.query(
                        question=question,
                        user_role=user_role,
                        user_id=user_id
                    )
                    
                    print("="*70)
                    
                    if result["success"]:
                        if result.get("agent_used"):
                            print(f"\n✅ Processed by: {result['agent_used']}")
                        print(f"\n{result['answer']}\n")
                    else:
                        print(f"\n❌ Error: {result['answer']}\n")
                    
                except KeyboardInterrupt:
                    print("\n\n👋 Goodbye! Happy learning and teaching!")
                    break
                except Exception as e:
                    print(f"\n❌ Error: {str(e)}\n")
            
    except Exception as e:
        print(f"❌ Failed to initialize system: {str(e)}")
        print("\nPlease ensure you have:")
        print("1. Created a .env file with your API keys (see env_example.txt)")
        print("2. Installed required packages: pip install -r requirements.txt")
        print("3. Set up database (optional): See docs/POSTGRESQL.md")
        print("\nFor API mode, run: uvicorn api.app:app --host 0.0.0.0 --port 8000")
        sys.exit(1)


if __name__ == "__main__":
    main()


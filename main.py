"""
Main entry point for the Study and Search Agent.
"""

import os
import sys
from dotenv import load_dotenv

from agent import StudySearchAgent

# Load environment variables
load_dotenv()


def main():
    """Main entry point for the agent."""
    
    # Get LLM provider from environment or default to gemini
    llm_provider = os.getenv("LLM_PROVIDER", "gemini")
    
    print(f"\n🚀 Initializing Study and Search Agent with {llm_provider.upper()}...\n")
    
    try:
        agent = StudySearchAgent(llm_provider=llm_provider)
        
        # Check if a question was provided as command line argument
        if len(sys.argv) > 1:
            question = " ".join(sys.argv[1:])
            print(f"Question: {question}\n")
            print("=" * 60)
            answer = agent.query(question)
            print("=" * 60)
            print(f"\n✅ Final Answer: {answer}\n")
        else:
            # Start interactive chat mode
            agent.chat()
            
    except Exception as e:
        print(f"❌ Failed to initialize agent: {str(e)}")
        print("\nPlease ensure you have:")
        print("1. Created a .env file with your API keys (see env_example.txt)")
        print("2. Installed required packages: pip install -r requirements.txt")
        sys.exit(1)


if __name__ == "__main__":
    main()


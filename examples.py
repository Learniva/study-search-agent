"""
Example usage of the Study and Search Agent
Demonstrates different types of questions and tool selection
"""

import os
from dotenv import load_dotenv

from agent import StudySearchAgent

load_dotenv()


def run_examples():
    """Run example queries demonstrating different tool selections."""
    
    print("=" * 70)
    print("Study and Search Agent - Example Demonstrations")
    print("=" * 70)
    
    # Initialize agent
    llm_provider = os.getenv("LLM_PROVIDER", "gemini")
    agent = StudySearchAgent(llm_provider=llm_provider)
    
    # Example queries
    examples = [
        {
            "category": "MATH/CODE (should use Python_REPL)",
            "questions": [
                "What is the square root of 12345?",
                "Calculate the factorial of 20",
                "What is 15% of 850?",
                "Write Python code to generate the first 10 Fibonacci numbers",
            ]
        },
        {
            "category": "REAL-TIME INFO (should use Web_Search)",
            "questions": [
                "What is the current weather in Tokyo?",
                "Who won the latest Nobel Prize in Physics?",
                "What are the latest developments in AI in 2024?",
                "What is the current stock price of Tesla?",
            ]
        },
        {
            "category": "GENERAL KNOWLEDGE (should answer directly)",
            "questions": [
                "What is the capital of France?",
                "Who wrote Romeo and Juliet?",
                "What is photosynthesis?",
                "How many continents are there?",
            ]
        }
    ]
    
    for example_group in examples:
        print(f"\n\n{'=' * 70}")
        print(f"📚 CATEGORY: {example_group['category']}")
        print(f"{'=' * 70}\n")
        
        for i, question in enumerate(example_group['questions'], 1):
            print(f"\n{'─' * 70}")
            print(f"Example {i}: {question}")
            print(f"{'─' * 70}")
            
            try:
                answer = agent.query(question)
                print(f"\n✅ Answer: {answer}\n")
            except Exception as e:
                print(f"\n❌ Error: {str(e)}\n")
            
            # Optional: uncomment to pause between questions
            # input("Press Enter to continue...")
    
    print(f"\n{'=' * 70}")
    print("Examples completed!")
    print(f"{'=' * 70}\n")


if __name__ == "__main__":
    run_examples()

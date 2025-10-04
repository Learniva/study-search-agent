"""
Study and Search Agent
A dynamic agent that chooses between web search, Python REPL, or direct answers.
"""

import os
from typing import Optional
from dotenv import load_dotenv

from langchain.agents import AgentExecutor, create_react_agent

from tools.base import get_all_tools
from utils.llm import initialize_llm
from utils.prompts import get_agent_prompt

# Load environment variables
load_dotenv()


class StudySearchAgent:
    """
    An intelligent agent that dynamically decides which tool to use:
    - Python REPL for math/code execution
    - Web Search for real-time facts/recent events
    - Direct answer for general knowledge
    """
    
    def __init__(self, llm_provider: str = "openai", model_name: Optional[str] = None):
        """
        Initialize the Study and Search Agent.
        
        Args:
            llm_provider: Either "openai" or "anthropic"
            model_name: Optional model name override
        """
        self.llm_provider = llm_provider.lower()
        self.llm = initialize_llm(llm_provider, model_name)
        self.tools = get_all_tools()
        self.agent_executor = self._create_agent()
    
    def _create_agent(self) -> AgentExecutor:
        """Create the ReAct agent with custom prompt."""
        
        prompt = get_agent_prompt(self.tools)
        
        agent = create_react_agent(
            llm=self.llm,
            tools=self.tools,
            prompt=prompt
        )
        
        return AgentExecutor(
            agent=agent,
            tools=self.tools,
            verbose=True,
            handle_parsing_errors=True,
            max_iterations=5
        )
    
    def query(self, question: str) -> str:
        """
        Process a question and return the answer.
        
        Args:
            question: The question to answer
            
        Returns:
            The answer string
        """
        try:
            result = self.agent_executor.invoke({"input": question})
            return result.get("output", "No answer generated")
        except Exception as e:
            return f"Error processing query: {str(e)}"
    
    def chat(self):
        """Interactive chat mode."""
        print("=" * 60)
        print("Study and Search Agent - Interactive Mode")
        print("=" * 60)
        print("\nI can help you with:")
        print("  📊 Math and code execution (using Python)")
        print("  🔍 Real-time web searches")
        print("  💡 General knowledge questions")
        print("\nType 'quit', 'exit', or 'q' to end the conversation.\n")
        
        while True:
            try:
                question = input("\n🤔 Your question: ").strip()
                
                if question.lower() in ['quit', 'exit', 'q']:
                    print("\n👋 Goodbye! Happy studying!")
                    break
                
                if not question:
                    continue
                
                print("\n" + "=" * 60)
                answer = self.query(question)
                print("=" * 60)
                print(f"\n✅ Final Answer: {answer}\n")
                
            except KeyboardInterrupt:
                print("\n\n👋 Goodbye! Happy studying!")
                break
            except Exception as e:
                print(f"\n❌ Error: {str(e)}\n")


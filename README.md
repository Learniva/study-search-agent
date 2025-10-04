# Study and Search Agent 🤖

An intelligent agent that dynamically decides between different tools to answer your questions:
- 🐍 **Python REPL** for math and code execution
- 🔍 **Web Search** for real-time facts and recent events
- 💡 **Direct answers** for general knowledge

## 🌟 Key Features

The **dynamic decision-making** is the core of this project. The LLM intelligently chooses:

1. **Python_REPL Tool** → For mathematical calculations or code execution
2. **Web_Search Tool** → For real-time facts, current events, or recent information
3. **Direct Answer** → For trivial or general knowledge questions (no tool needed)

## 🏗️ Architecture

```
User Question → LLM Agent → Decision Making
                              ↓
                    ┌─────────┴─────────┐
                    ↓         ↓         ↓
              Python_REPL  Web_Search  Direct Answer
```

The agent uses a **ReAct (Reasoning + Acting)** framework to:
1. Reason about which tool to use
2. Execute the appropriate action
3. Observe the result
4. Provide a final answer

## 📦 Installation

### 1. Clone or navigate to the repository

```bash
cd study-search-agent
```

### 2. Create a virtual environment (recommended)

```bash
python3 -m venv study_agent
source study_agent/bin/activate  # On Windows: study_agent\Scripts\activate
```

### 3. Install dependencies

```bash
pip install -r requirements.txt
```

### 4. Set up environment variables

Copy the example environment file and add your API keys:

```bash
cp env_example.txt .env
```

Edit `.env` and add your API keys:

```env
# Choose your LLM provider
LLM_PROVIDER=gemini  # Options: "huggingface", "gemini", "openai", "anthropic"

# Add your API keys (only need the ones you're using)
HUGGINGFACE_API_KEY=your_huggingface_api_key_here
GOOGLE_API_KEY=your_google_api_key_here
OPENAI_API_KEY=your_openai_api_key_here
ANTHROPIC_API_KEY=your_anthropic_api_key_here
TAVILY_API_KEY=your_tavily_api_key_here
```

**Where to get API keys:**
- HuggingFace: https://huggingface.co/settings/tokens
- Google Gemini: https://aistudio.google.com/app/apikey
- OpenAI: https://platform.openai.com/api-keys
- Anthropic: https://console.anthropic.com/
- Tavily: https://tavily.com/

## 🚀 Usage

### Interactive Mode

Run the agent in interactive chat mode:

```bash
python main.py
```

This starts a conversation where you can ask any question:

```
🤔 Your question: What is 25 * 37 + 128?
# Agent will use Python_REPL

🤔 Your question: Who is the current president of the United States?
# Agent will use Web_Search

🤔 Your question: What is the capital of France?
# Agent will answer directly
```

### Single Question Mode

Ask a single question from the command line:

```bash
python main.py "What is the square root of 2?"
```

### Examples

Run the examples to see the agent in action:

```bash
python examples.py
```

## 📝 Example Questions

### Math/Code (Uses Python_REPL)
- "What is the square root of 12345?"
- "Calculate the factorial of 20"
- "Generate the first 10 Fibonacci numbers"
- "What is 15% of 850?"

### Real-Time Info (Uses Web_Search)
- "What is the current weather in Tokyo?"
- "Who won the latest Nobel Prize?"
- "What are the latest developments in AI?"
- "What is Tesla's current stock price?"

### General Knowledge (Direct Answer)
- "What is the capital of France?"
- "Who wrote Romeo and Juliet?"
- "What is photosynthesis?"
- "How many planets are in our solar system?"

## 🧠 How It Works

### Decision Logic

The agent uses a carefully crafted prompt that instructs the LLM to:

1. **Analyze the question** - Understand what type of information is needed
2. **Choose the right tool** - Based on these criteria:
   - Mathematical or computational? → `Python_REPL`
   - Current/recent information? → `Web_Search`
   - Established general knowledge? → Direct answer
3. **Execute and respond** - Use the chosen tool or answer directly

### Tools

#### Python_REPL
- Executes Python code in a safe REPL environment
- Perfect for calculations, data processing, and code examples
- Returns the output of the executed code

#### Web_Search (Tavily)
- Performs real-time web searches
- Returns up-to-date information from the internet
- Useful for current events, statistics, and recent data

## 🛠️ Customization

### Using Different LLM Providers

The agent supports multiple LLM providers. Set your preference in `.env`:

```env
LLM_PROVIDER=gemini  # Options: "huggingface", "gemini", "openai", "anthropic"
```

**Provider-specific notes:**

- **HuggingFace**: Uses the Inference API. Default model: `mistralai/Mistral-7B-Instruct-v0.2`
  - You can specify any HuggingFace model that supports text generation
  - Free tier available with rate limits
  
- **Gemini**: Google's Gemini models. Default: `gemini-1.5-flash`
  - Fast and efficient
  - Good free tier quota
  
- **OpenAI**: GPT models. Default: `gpt-4-turbo-preview`
  - Requires paid API access
  
- **Anthropic**: Claude models. Default: `claude-3-sonnet-20240229`
  - Requires paid API access

### Programmatic Usage

You can also use the agent in your own Python code:

```python
from agent import StudySearchAgent

# Initialize the agent with your preferred provider
agent = StudySearchAgent(llm_provider="gemini")  # or "huggingface", "openai", "anthropic"

# Optionally specify a custom model
agent = StudySearchAgent(llm_provider="huggingface", model_name="meta-llama/Llama-2-7b-chat-hf")
agent = StudySearchAgent(llm_provider="gemini", model_name="gemini-1.5-pro")

# Ask questions
answer = agent.query("What is 2 + 2?")
print(answer)

# Start interactive chat
agent.chat()
```

### Modular Architecture

The project is organized into modules for easy extension:

- **`agent/`** - Core agent logic
- **`tools/`** - Individual tool implementations (easy to add new tools)
- **`utils/`** - Shared utilities (LLM initialization, prompts)

To add a new tool:
1. Create a new file in `tools/` (e.g., `calculator.py`)
2. Implement a `get_your_tool()` function
3. Add it to `tools/base.py`'s `get_all_tools()` function

## 📊 Project Structure

```
study-search-agent/
├── agent/                    # Agent module
│   ├── __init__.py          # Agent exports
│   └── study_agent.py       # Main agent implementation
├── tools/                    # Tools module
│   ├── __init__.py          # Tool exports
│   ├── base.py              # Tool collection
│   ├── python_repl.py       # Python REPL tool
│   └── web_search.py        # Web search tool
├── utils/                    # Utilities module
│   ├── __init__.py          # Utility exports
│   ├── llm.py               # LLM initialization
│   └── prompts.py           # Prompt templates
├── main.py                  # Entry point
├── examples.py              # Example usage demonstrations
├── requirements.txt         # Python dependencies
├── env_example.txt          # Example environment variables
├── .gitignore               # Git ignore rules
└── README.md                # This file
```

## 🔒 Security Notes

- Never commit your `.env` file with real API keys
- The Python REPL tool executes code - use with caution
- Consider rate limits and costs of API calls

## 🤝 Contributing

Feel free to enhance this agent by:
- Adding more tools (e.g., calculator, image generation)
- Improving the decision-making prompt
- Adding error handling and edge cases
- Creating more examples

## 📄 License

See LICENSE file for details.

## 🙏 Acknowledgments

Built with:
- [LangChain](https://www.langchain.com/) - Agent framework
- [HuggingFace](https://huggingface.co/) - Open-source models
- [Google Gemini](https://ai.google.dev/) - Gemini models
- [OpenAI](https://openai.com/) - GPT models (optional)
- [Anthropic](https://www.anthropic.com/) - Claude models (optional)
- [Tavily](https://tavily.com/) - Web search API

---

**Happy studying and searching! 🎓🔍**
# Welcome to LangChain Docker Chat

This is an interactive chat interface powered by multiple LLM providers through LangChain.

## Features

- **Multiple Providers**: Choose between OpenAI, Anthropic (Claude), and Google (Gemini)
- **Real-time Streaming**: See responses as they're generated
- **Conversation History**: Your conversations are automatically saved with session management
- **Customizable Settings**: Adjust temperature and switch providers on the fly

## Getting Started

1. **Select Your Provider**: Use the settings panel to choose your preferred LLM provider
2. **Adjust Temperature**: Control the randomness of responses (0.0 = deterministic, 2.0 = very creative)
3. **Start Chatting**: Type your message and press Enter

## Settings

- **Provider**: Choose between OpenAI (GPT), Anthropic (Claude), or Google (Gemini)
- **Temperature**: Controls response creativity (default: 0.7)

## Tips

- Your conversation history persists automatically through sessions
- Try different providers to compare their responses
- Lower temperatures (0.0-0.3) for factual/analytical tasks
- Higher temperatures (0.7-1.5) for creative tasks

## Requirements

Make sure the FastAPI backend is running:
```bash
uv run langchain-docker serve
```

The backend should be accessible at `http://localhost:8000`

---

**Powered by**: LangChain, FastAPI, and Chainlit

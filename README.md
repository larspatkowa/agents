# Agents Project

Welcome to my "agents" project! I wanted to learn more about LLM-on-LLM interactions, especially the MoP (mixture of prompts) approach. I do not have a lot of experience with Python and Copilot has, thus far, helped me actually understand what I'm writing!

## Project Structure

- **main.py**: The main entry point of the application - it initializes the FastAPI server and defines endpoints for text processing and listing chat names.
- **utils.py**: Houses utility functions and classes for database operations, tool call processing, and AI model interactions.
- **request.py**: A sample script designed to send requests to the FastAPI server and interact with the AI.

## Key Components

### FastAPI Server

The FastAPI server is initialized in `main.py` and provides endpoints for AI agent interactions:
- `/v1/text`: Handles user input and generates responses from the AI agent.
- `/v1/list`: Retrieves all unique chat names stored in the database.

### Database

SQLite is used for storing conversations and chat messages. The database is set up in the `startup` function in `utils.py`, which creates the necessary tables and fields if they don't already exist.

### AI Models

The project supports various AI models, including OpenAI and Ollama's offerings. Currently, I'm using gpt-4o-mini and llama3.2.

### Tool Calls

AI agents can invoke various tools to perform specific tasks. These tool calls are managed in the `tools.py` file, accessed by the `process_tool_calls` function in `utils.py`.
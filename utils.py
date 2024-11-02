import string
import random
import sqlite3
from pydantic import BaseModel
from openai import AsyncOpenAI
from tools import available_functions, openapi_schemas
from dotenv import load_dotenv
import os
import json
import logging

PROVIDER = "openai"  # Set to "openai" or "ollama"

# llama3.2 3b is not a good model if using functions

OPENAI_MODEL = "gpt-4o-mini"  # Set the OpenAI model to use

OLLAMA_MODEL = "llama3.2"  # Set the Ollama model to use

SYSTEM_MESSAGE = """You are a helpful assistant.
                    Keep responses concise - 1-2 sentences unless a longer response is requested.
                    Only call functions if needed.
                    Do not use markdown formatting."""

# Configure logging
logging.basicConfig(level=logging.DEBUG)

# Load environment variables from a .env file
load_dotenv()

# Retrieve the OpenAI API key from environment variables
OPENAI_API_KEY = os.getenv("OPENAI_API_KEY")

# Path to the SQLite database
DATABASE_PATH = "./conversations.db"

# Initialize the OpenAI client with the API key
client = AsyncOpenAI(api_key=OPENAI_API_KEY) if PROVIDER == "openai" else AsyncOpenAI(base_url="http://localhost:11434/v1", api_key="ollama")

# Set model
MODEL = OPENAI_MODEL if PROVIDER == "openai" else OLLAMA_MODEL

# Define a Pydantic model for messages
class Message(BaseModel):
    conversation_name: str = ""
    content: str

# Function to initialize the database and create the conversations and chats tables if they don't exist
async def startup():
    logging.debug("Initializing database...")
    with sqlite3.connect(DATABASE_PATH) as conn:
        cursor = conn.cursor()
        
        # Create the conversations table
        cursor.execute("""
        CREATE TABLE IF NOT EXISTS conversations (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            conversation_name TEXT
        )
        """)
        
        # Create the chats table with a timestamp field
        cursor.execute("""
        CREATE TABLE IF NOT EXISTS chats (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            conversation_name TEXT,
            role TEXT,
            content TEXT,
            tool_call_id TEXT,
            name TEXT,
            tool_calls TEXT,
            timestamp DATETIME DEFAULT CURRENT_TIMESTAMP
        )
        """)
        
        conn.commit()
    logging.debug("Database initialized.")

# Function to list all unique chat names
async def list_conversation_names():
    logging.debug("Listing conversation names...")
    with sqlite3.connect(DATABASE_PATH) as conn:
        cursor = conn.cursor()
        cursor.execute("SELECT DISTINCT conversation_name FROM conversations WHERE conversation_name IS NOT NULL AND conversation_name != ''")
        conversation_names = [row[0] for row in cursor.fetchall()]
    logging.debug(f"Conversation names: {conversation_names}")
    return {"conversation_names": conversation_names}

# Function to parse tool calls from the assistant's response
async def parse_tool_calls(tool_call_msg):
    logging.debug(f"Parsing tool calls: {tool_call_msg}")
    if not tool_call_msg:
        return None
    tool_calls_list = []
    for tool_call in tool_call_msg:
        tool_calls_list.append({
            "id": tool_call.id,
            "type": tool_call.type,
            "function": {
                "arguments": tool_call.function.arguments,
                "name": tool_call.function.name,
            }
        })
    logging.debug(f"Parsed tool calls: {tool_calls_list}")
    return tool_calls_list

# Function to process tool calls in the response message
async def process_tool_calls(messages):
    logging.debug(f"Processing tool calls for messages: {messages}")
    assistant_message = messages[-1]
    msgs = []
    for tool_call in assistant_message["tool_calls"]:
        function_name = tool_call["function"]["name"]
        function_to_call = available_functions[function_name]
        function_args = json.loads(tool_call["function"]["arguments"])
        function_response = function_to_call(
            **function_args  # Unpack arguments for the called function
        )
        tc = {
            "tool_call_id": tool_call["id"],
            "role": "tool",
            "name": function_name,
            "content": function_response,
        }
        # Add the tool call response to the temporary messages list
        msgs.append(tc)
        messages.extend(msgs)
    # Generate a second response from the assistant after processing tool calls
    second_response = await client.chat.completions.create(
        model=MODEL,
        messages=messages,
        tools=openapi_schemas
    )
    second_message = second_response.choices[0].message
    if second_message.content:
        # Add the assistant's response to the messages list
        msgs.append({
            "role": "assistant",
            "content": second_message.content,
            "tool_calls": await parse_tool_calls(second_message.tool_calls)
        })
    messages.append(msgs[-1])
    logging.debug(f"Processed tool calls messages: {msgs}")
    return msgs

# Function to process user input and generate a response
async def process_user_input(message):
    logging.debug(f"Processing user input: {message}")
    user_message = {"role": "user", "content": message.content}
    with sqlite3.connect(DATABASE_PATH) as conn:
        cursor = conn.cursor()
        cursor.execute("SELECT id, conversation_name FROM conversations WHERE conversation_name IS NOT NULL AND conversation_name != '' AND conversation_name = ?", (message.conversation_name,))
        result = cursor.fetchone()

        if not result:
            if message.conversation_name:
                raise HTTPException(status_code=400, detail="invalid conversation name")
            
            # Generate a unique conversation name based on the user's initial message
            conversation_name_response = await client.chat.completions.create(
                model=MODEL,
                messages=[{"role": "system", "content": "You are an expert summarizer. Provided is the first message from a user to an assistant. Create a few-word name for this conversation based on the user's first message."}, user_message]
            )
            base_conversation_name = conversation_name_response.choices[0].message.content.strip().strip('"')
            
            # Check if the base chat name is available
            cursor.execute("SELECT 1 FROM conversations WHERE conversation_name = ?", (base_conversation_name,))
            if not cursor.fetchone():
                conversation_name = base_conversation_name
            else:
                # Append a number if the base chat name is already taken
                suffix = 1
                while True:
                    conversation_name = f"{base_conversation_name} ({suffix})"
                    cursor.execute("SELECT 1 FROM conversations WHERE conversation_name = ?", (conversation_name,))
                    if not cursor.fetchone():
                        break
                    suffix += 1
            message.conversation_name = conversation_name

            # Insert the new conversation into the database
            cursor.execute("INSERT INTO conversations (conversation_name) VALUES (?)", (message.conversation_name,))

            # Insert the system message into the database
            system_message = {"role": "system", "content": SYSTEM_MESSAGE}
            cursor.execute("INSERT INTO chats (conversation_name, role, content, tool_call_id, name, tool_calls, timestamp) VALUES (?, ?, ?, ?, ?, ?, CURRENT_TIMESTAMP)", 
                           (message.conversation_name, system_message["role"], system_message["content"], None, None, None))

        # Insert the user's message into the database
        cursor.execute("INSERT INTO chats (conversation_name, role, content, tool_call_id, name, tool_calls, timestamp) VALUES (?, ?, ?, ?, ?, ?, CURRENT_TIMESTAMP)", 
                           (message.conversation_name, user_message["role"], user_message["content"], None, None, None))
        conn.commit()

        # Retrieve all messages for the conversation and add the user's message
        cursor.execute("SELECT role, content, tool_call_id, name, tool_calls FROM chats WHERE conversation_name = ?", (message.conversation_name,))
        result = cursor.fetchall()
        messages = []
        for row in result:
            role, content, tool_call_id, name, tool_calls = row
            if role == "tool":
                messages.append({
                    "tool_call_id": tool_call_id,
                    "role": "tool",
                    "name": name,
                    "content": content,
                })
            elif role == "assistant":
                try:
                    tool_calls = json.loads(tool_calls)
                except:
                    tool_calls = None
                if tool_calls:
                    messages.append({
                        "role": "assistant",
                        "content": content,
                        "tool_calls": tool_calls,
                    })
                else:
                    messages.append({
                        "role": role,
                        "content": content
                    })
            else:
                messages.append({
                    "role": role,
                    "content": content
                })

        # Generate a response from the assistant
        response = await client.chat.completions.create(
            model=MODEL,
            messages=messages,
            tools=openapi_schemas
        )

        # Insert the assistant's response into the database and add it to the messages list
        tcs = await parse_tool_calls(response.choices[0].message.tool_calls)
        content = response.choices[0].message.content
        assistant_message = {
            "role": "assistant",
        }
        if tcs and content:
            assistant_message["content"] = content
            assistant_message["tool_calls"] = tcs
        elif content:
            assistant_message["content"] = content
        elif tcs:
            assistant_message["tool_calls"] = tcs

        # Else, no valid response from the assistant

        messages.append(assistant_message)

        cursor.execute(
            "INSERT INTO chats (conversation_name, role, content, tool_call_id, name, tool_calls, timestamp) VALUES (?, ?, ?, ?, ?, ?, CURRENT_TIMESTAMP)",
            (message.conversation_name, assistant_message["role"], assistant_message["content"] if "content" in assistant_message else None, None, None, json.dumps(assistant_message["tool_calls"] if "tool_calls" in assistant_message else None, default=str))
        )
        conn.commit()

        # Process tool calls if any
        while "tool_calls" in messages[-1] and messages[-1]["tool_calls"]:
            msgs = await process_tool_calls(messages)
            for msg in msgs:
                cursor.execute(
                    "INSERT INTO chats (conversation_name, role, content, tool_call_id, name, tool_calls, timestamp) VALUES (?, ?, ?, ?, ?, ?, CURRENT_TIMESTAMP)",
                    (message.conversation_name, msg["role"], msg["content"] if "content" in msg else None, msg["tool_call_id"] if "tool_call_id" in msg else None, msg["name"] if "name" in msg else None, None)
                )
                conn.commit()          

    logging.debug(f"Final response: {messages[-1]}")
    return {"conversation_name": message.conversation_name, "content": messages[-1]["content"]}
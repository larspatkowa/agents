from fastapi import FastAPI
from pydantic import BaseModel
import utils
import asyncio

app = FastAPI()

# Define a Pydantic model for messages
class Message(BaseModel):
    conversation_name: str = ""
    content: str

@app.on_event("startup")
async def startup():
    await utils.startup()

@app.post("/v1/text")
async def process_text(message: Message):
    return await utils.process_user_input(message)

@app.get("/v1/list")
async def list_chat_names():
    return await utils.list_conversation_names()

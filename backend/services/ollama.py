import asyncio

from ollama import chat
from config import SYSTEM_PROMPT, OLLAMA_MODEL, MAX_TURNS

def make_conversation():
    return [{"role": "system", "content": SYSTEM_PROMPT}]

def get_streaming_response(conversation: list, user_message: str):
    conversation.append({"role": "user", "content": user_message})
    return chat(model=OLLAMA_MODEL, messages=conversation, stream=True, options={
        'temperature': 1.0,
    })

def commit_reply(conversation: list, reply: str):
    conversation.append({"role": "assistant", "content": reply})
    _trim(conversation)

def _trim(conversation: list):
    system_msg = conversation[0]
    conversation[:] = [system_msg] + conversation[-(MAX_TURNS * 2):]

async def warmup():
    print("Warming up Ollama model...")
    loop = asyncio.get_event_loop()
    await loop.run_in_executor(None, lambda: chat(
        model=OLLAMA_MODEL,
        messages=[{"role": "user", "content": "Helllo"}]
    ))
    print("Model ready.")
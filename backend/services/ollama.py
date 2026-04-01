import asyncio, httpx, time
from typing import Any
from config import SYSTEM_PROMPT, MAX_TURNS, LLAMA_SERVER_URL
from services.tools import TOOLS

async def _is_ollama_running() -> bool:
    try:
        async with httpx.AsyncClient() as client:
            r = await client.get(f"{LLAMA_SERVER_URL}/api/tags", timeout=2.0)
            return r.status_code == 200
    except Exception:
        return False
 
async def _wait_for_ollama(timeout: float = 30.0):
    deadline = asyncio.get_event_loop().time() + timeout
    while asyncio.get_event_loop().time() < deadline:
        if await _is_ollama_running():
            return
        await asyncio.sleep(0.5)
    raise RuntimeError("Ollama did not start within the timeout period.")

def make_conversation():
    return [{"role": "system", "content": SYSTEM_PROMPT}]

def commit_reply(conversation: list, reply: dict[str, Any]):
    conversation.append(reply)
    _trim(conversation)

def _trim(conversation: list):
    system_msg = conversation[0]
    conversation[:] = [system_msg] + conversation[-(MAX_TURNS * 2):]
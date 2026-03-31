import asyncio, httpx, time
from typing import Any

from ollama import AsyncClient, chat
from config import SYSTEM_PROMPT, OLLAMA_MODEL, MAX_TURNS, OLLAMA_URL
from services.tools import TOOLS

async def _is_ollama_running() -> bool:
    try:
        async with httpx.AsyncClient() as client:
            r = await client.get(f"{OLLAMA_URL}/api/tags", timeout=2.0)
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

async def get_streaming_response(conversation: list, client: AsyncClient):
    # last = time.perf_counter()
    async for chunk in await client.chat(
        model=OLLAMA_MODEL, 
        messages=conversation, 
        stream=True, 
        options={
            'temperature': 0.6,
            "num_ctx": 1024,
            "num_predict": 150
        },
        tools=TOOLS.values(),
        # think=True,
        keep_alive=-1
    ):
        # new = time.perf_counter()
        # print(f"Time per Chunk: {new - last:.3}s")
        # last = new
        yield chunk

def commit_reply(conversation: list, reply: dict[str, Any]):
    conversation.append(reply)
    _trim(conversation)

def _trim(conversation: list):
    system_msg = conversation[0]
    conversation[:] = [system_msg] + conversation[-(MAX_TURNS * 2):]

async def warmup(client: AsyncClient):
    print("Warming up model...")
    start = time.perf_counter()
    
    print("Warm Up Output:")
    async for chunk in await client.chat(
        model=OLLAMA_MODEL,
        messages=make_conversation() + [{"role": "user", "content": "what time is it?"}],
        tools=TOOLS.values(),
        options={
            "num_predict": 10,
            "num_ctx": 1024,
        },
        stream=True,
        keep_alive=-1,
        # think=True,
    ): 
        out = chunk.message.content
        if not out:
            out = chunk.message.thinking
        print(out, end="", flush=True)
    
    elapsed = time.perf_counter() - start
    print(f"\nModel ready ({elapsed:.3} s)")
 
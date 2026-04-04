import asyncio
from contextlib import asynccontextmanager
from fastapi import FastAPI
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles
from fastapi.middleware.cors import CORSMiddleware
from openai import AsyncOpenAI
from piper import PiperVoice

from services.stt import WhisperSTT
from services.llm import LlamaServerRouter, LlamaServerResponder
from config import PIPER_MODEL_PATH, LLAMA_SERVER_URL, build_router_system_prompt, RESPONDER_SYSTEM_PROMPT
from ws.chat import chat_ws

@asynccontextmanager
async def lifespan(app: FastAPI):
    loop = asyncio.get_running_loop()
    
    print("[STARTUP] Initializing: Loading Router LLM...")
    app.state.router_llm = await loop.run_in_executor(
        None, lambda: LlamaServerRouter(LLAMA_SERVER_URL, build_router_system_prompt())
    )
    
    max_retry = 5
    is_healthy = False
    for _ in range(max_retry):
        is_healthy = await app.state.router_llm.health_check()
        if is_healthy:
            break
        await asyncio.sleep(2)
        
    if not is_healthy:
        exit(0)
        
    print("[STARTUP] Initializing: Loading Responder LLM...")
    app.state.responder_llm = await loop.run_in_executor(
        None, lambda: LlamaServerResponder(LLAMA_SERVER_URL, RESPONDER_SYSTEM_PROMPT)
    )
    
    is_healthy=False
    for _ in range(max_retry):
        is_healthy = await app.state.router_llm.health_check()
        if is_healthy:
            break
        await asyncio.sleep(2)
        
    if not is_healthy:
        exit(0)
    
    print("[STARTUP] Initializing: Loading Text-to-Speech Model - Piper...")
    app.state.voice = await loop.run_in_executor(None, PiperVoice.load, PIPER_MODEL_PATH)
    print("[STARTUP] Initializing: Loading Speech-to-Text Model - Whisper...")
    app.state.stt = WhisperSTT()
    yield
    # optional cleanup

app = FastAPI(lifespan=lifespan)
app.add_middleware(CORSMiddleware, allow_origins=["*"], allow_credentials=False, allow_methods=["*"],
    allow_headers=["*"])

app.mount("/static", StaticFiles(directory="../frontend"), name="static")

# Serve index.html at root
@app.get("/")
async def root():
    return FileResponse("../frontend/index.html")

app.add_api_websocket_route("/ws", chat_ws)
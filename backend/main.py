import asyncio
from contextlib import asynccontextmanager
from fastapi import FastAPI
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles
from fastapi.middleware.cors import CORSMiddleware
from piper import PiperVoice

from services.stt import WhisperSTT
from services.llm import LlamaServerResponder
from config import PIPER_MODEL_PATH, LLAMA_SERVER_URL, SYSTEM_PROMPT
from ws.chat import chat_ws

@asynccontextmanager
async def lifespan(app: FastAPI):
    loop = asyncio.get_running_loop()
    
    print("[STARTUP] Initializing: Loading LLM...")
    app.state.llm = await loop.run_in_executor(
        None, lambda: LlamaServerResponder(LLAMA_SERVER_URL, SYSTEM_PROMPT)
    )
    
    max_retry = 5
    is_healthy = False
    for _ in range(max_retry):
        is_healthy = await app.state.llm.health_check()
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
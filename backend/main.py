import asyncio
from contextlib import asynccontextmanager
from fastapi import FastAPI
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles
from fastapi.middleware.cors import CORSMiddleware
from llama_cpp import Llama
from piper import PiperVoice

from config import ROUTER_MODEL_PATH, RESPONDER_MODEL_PATH, PIPER_MODEL_PATH
from ws.chat import chat_ws

@asynccontextmanager
async def lifespan(app: FastAPI):
    # Load Piper TTS
    loop = asyncio.get_running_loop()
    app.state.voice = await loop.run_in_executor(None, PiperVoice.load, PIPER_MODEL_PATH)
    # Load llama.cpp models
    app.state.router_model = await loop.run_in_executor(
        None, lambda: Llama(model_path=ROUTER_MODEL_PATH, verbose=False, n_ctx=2048)
    )
    # app.state.responder_model = Llama(model_path=RESPONDER_MODEL_PATH, verbose=False, n_ctx=2048)
    app.state.responder_model = app.state.router_model
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
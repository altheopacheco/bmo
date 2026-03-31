import asyncio
from collections.abc import AsyncIterable
from contextlib import asynccontextmanager
from fastapi import FastAPI, Request
from fastapi.sse import EventSourceResponse
from fastapi.staticfiles import StaticFiles
from fastapi.middleware.cors import CORSMiddleware
from ollama import AsyncClient
from pydantic import BaseModel

from routes.static import router as static_router
from services.ollama import warmup
from ws.chat import chat_ws

from piper import PiperVoice

from config import PIPER_MODEL_PATH

async def _startup(app: FastAPI):
    print("starting up")
    loop = asyncio.get_running_loop()
 
    app.state.system_init_message = "Loading Piper..."

    app.state.voice = await loop.run_in_executor(None, PiperVoice.load, PIPER_MODEL_PATH)
 
    app.state.system_init_message = "Loading Ollama Client..."
    
    client = AsyncClient()
    app.state.ollama_client = client
    
    app.state.system_init_message = "Warming Up Ollama..."

    await warmup(client)
 
    app.state.system_init_message = "Initialized"
 

@asynccontextmanager
async def lifespan(app: FastAPI):
    app.state.system_init_message = "Starting..."
    app.state.voice = None
    asyncio.create_task(_startup(app))
    yield
    
origins = [
    "http://localhost",
    "http://localhost:8000",
    'http://127.0.0.1:8000'
]

    
app = FastAPI(lifespan=lifespan)

app.add_middleware(
    CORSMiddleware,
    allow_origins=origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

class SystemInitMessage(BaseModel):
    system_init_message: str

@app.get("/llm-ready", response_class=EventSourceResponse)
async def llm_ready(request: Request) -> AsyncIterable[SystemInitMessage]:
    last_message = ""
    while True:
        if await request.is_disconnected(): break
 
        yield {"system_init_message": app.state.system_init_message}
 
        if app.state.system_init_message == "Initialized": break
        
        if app.state.system_init_message != last_message:
            print(app.state.system_init_message)
            last_message = app.state.system_init_message
 
        await asyncio.sleep(0.05)
 
app.mount("/static", StaticFiles(directory="../frontend"), name="static")
app.include_router(static_router)
app.add_api_websocket_route("/ws", chat_ws)
import asyncio
from contextlib import asynccontextmanager
from fastapi import FastAPI, Request
from fastapi.sse import EventSourceResponse
from fastapi.staticfiles import StaticFiles
from fastapi.middleware.cors import CORSMiddleware

from routes.static import router as static_router
from services.ollama import warmup
from ws.chat import chat_ws

from piper import PiperVoice

from config import PIPER_MODEL_PATH

system_init_message = "Initializing..."

@asynccontextmanager
async def lifespan(app: FastAPI):
    global system_init_message
    
    system_init_message = "Loading Piper..."
    app.state.voice = PiperVoice.load(PIPER_MODEL_PATH)
    system_init_message = "Warming Up Ollama..."
    asyncio.create_task(warmup())
    system_init_message = "Initialized"
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

@app.get("/llm-ready", response_class=EventSourceResponse)
async def llm_ready(request: Request):
    global system_init_message
    while True:
        if await request.is_disconnected():
            yield {
                "message": "Disconnected"
            }
            break
        
        yield {
            "system_init_message": system_init_message
        }
        
        await asyncio.sleep(0.5)

app.mount("/static", StaticFiles(directory="../frontend"), name="static")
app.include_router(static_router)
app.add_api_websocket_route("/ws", chat_ws)
import asyncio, httpx
from collections.abc import AsyncIterable
from contextlib import asynccontextmanager
from fastapi import FastAPI, Request
from fastapi.sse import EventSourceResponse
from fastapi.staticfiles import StaticFiles
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel

from services.state import BMOState, StateManager
from routes.static import router as static_router
from ws.chat import chat_ws

from piper import PiperVoice

from config import LLAMA_SERVER_URL, PIPER_MODEL_PATH

async def _startup(app: FastAPI):
    print("Starting up...")
    state: StateManager = app.state.bmo_state
    loop = asyncio.get_running_loop()
 
    await state.set(BMOState.STARTING, "Loading Piper...")
    app.state.voice = await loop.run_in_executor(None, PiperVoice.load, PIPER_MODEL_PATH)
 
    await state.set(BMOState.STARTING, "Connecting to llama-server...")
    client = httpx.AsyncClient(base_url=LLAMA_SERVER_URL, timeout=None)
    app.state.llama_client = client

    try:
        resp = await client.get("/health")
        resp.raise_for_status()
        print(f"llama-server healthy: {resp.json()}")
    except Exception as e:
        print(f"Warning: llama-server not reachable: {e}")
 
    await state.set(BMOState.IDLE, "BMO is online!")
 

@asynccontextmanager
async def lifespan(app: FastAPI):
    app.state.bmo_state = StateManager()
    app.state.voice = None
    app.state.llama_client = None
    asyncio.create_task(_startup(app))
    yield
    if app.state.llama_client:
        await app.state.llama_client.aclose()
    
app = FastAPI(lifespan=lifespan)

app.add_middleware(
    CORSMiddleware,
    allow_origins=[
        "http://localhost:8000",
        'http://127.0.0.1:8000'
    ],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

class StateResponse(BaseModel):
    state: BMOState
    message: str

@app.get("/state", response_class=EventSourceResponse)
async def state(request: Request) -> AsyncIterable[StateResponse]:
    state_manager: StateManager = app.state.bmo_state
    
    try:
        last_state = {"state": state_manager.state, "message": state_manager.message}
        q = state_manager.subscribe()
        
        await q.put(last_state)
        
        while True:
            if await request.is_disconnected(): break
            await asyncio.sleep(0.05)
            
            try:
                event = await asyncio.wait_for(q.get(), timeout=15.0)
                yield event
            except asyncio.TimeoutError:
                yield {"state": BMOState.IDLE, "message": ""}
            
    finally:
        state_manager.unsubscribe(q) 
        
app.mount("/static", StaticFiles(directory="../frontend"), name="static")
app.include_router(static_router)
app.add_api_websocket_route("/ws", chat_ws)
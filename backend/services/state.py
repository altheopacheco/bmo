from enum import Enum
import asyncio


class BMOState(str, Enum):
    STARTING     = "starting"
    IDLE         = "idle"
    LISTENING    = "listening"
    TRANSCRIBING = "transcribing"
    THINKING     = "thinking"
    SPEAKING     = "speaking"
    TOOL         = "using tool"
    ERROR        = "error"
    
class StateManager:
    def __init__(self):
        self._state = BMOState.STARTING
        self._message = ""
        self._subscribers: list[asyncio.Queue] = []

    @property
    def state(self) -> BMOState:
        return self._state

    @property
    def message(self) -> str:
        return self._message

    async def set(self, state: BMOState, message: str = ""):
        self._state = state
        self._message = message
        print(f"[BMO] {state} — {message}" if message else f"[BMO] {state}")
        await self._broadcast()

    async def _broadcast(self):
        dead = []
        for q in self._subscribers:
            try:
                await q.put({"state": self._state, "message": self._message})
            except Exception:
                dead.append(q)
        for q in dead:
            self._subscribers.remove(q)

    def subscribe(self) -> asyncio.Queue:
        q: asyncio.Queue = asyncio.Queue()
        self._subscribers.append(q)
        return q

    def unsubscribe(self, q: asyncio.Queue):
        self._subscribers.remove(q) if q in self._subscribers else None
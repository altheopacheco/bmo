from pydantic import BaseModel
from typing import Optional, Any, Literal

# Frontend → Backend
class ClientMessage(BaseModel):
    type: Literal["audio_chunk", "audio_stop", "interrupt"]
    data: Optional[bytes] = None

# Backend → Frontend
class ServerMessage(BaseModel):
    type: Literal[
        "status", "transcript", "llm_token", "reasoning",
        "tool_call", "tool_result", "final_answer_start", 
        "audio_chunk", "viseme_timeline", "metric", "done", "error"
    ]
    payload: Optional[Any] = None
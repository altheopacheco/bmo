from pydantic import BaseModel
from typing import Optional, Any, Literal

# Backend → Frontend
class ServerMessage(BaseModel):
    type: Literal[
        "status", "transcript", "llm_token", "reasoning",
        "tool_call", "tool_result", "final_answer_start", 
        "audio_chunk", "viseme_timeline", "metric", "done", "error"
    ]
    payload: Optional[Any] = None
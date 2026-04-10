from pydantic import BaseModel
from typing import Optional, Any, Literal

# Backend → Frontend
class ServerMessage(BaseModel):
    type: Literal[
        "status", "user_message",
        "tool_call", "tool_result", 
        "viseme_timeline", 
        "response_token", "response_finish", 
        "reasoning_token", "reasoning_finish", 
        "metric", "done", "error"
    ]
    payload: Optional[Any] = None
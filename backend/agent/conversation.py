import json
from typing import List, Dict, Any, Optional

class ConversationHistory:
    def __init__(self, max_turns: int = 10):
        self.max_turns = max_turns
        self.messages: List[Dict[str, Any]] = []
    
    def add_user(self, content: str) -> None:
        self.messages.append({"role": "user", "content": content})
        self._trim()
    
    def add_assistant(self, content: str = "", reasoning: str = "", tool_calls: Optional[List[Dict]] = None) -> None:
        msg = {"role": "assistant"}
        if content:
            msg["content"] = content
        if reasoning:
            msg["reasoning_content"] = reasoning
        if tool_calls:
            msg["tool_calls"] = tool_calls
        self.messages.append(msg)
        self._trim()
    
    def add_tool_result(self, tool_name: str, result: str) -> None:
        # Return the result in the user slot — widely understood by all model families
        self.messages.append({
            "role": "user",
            "content": json.dumps({
                "tool_result": tool_name,
                "result": result
            })
        })
        self._trim()
        
    def add_tool_call(self, tool_name: str, args: dict = {}) -> None:
        self.messages.append({
            "role": "assistant",
            "content": json.dumps({
                "action": "tool",
                "name": tool_name,
                "args": args
            })
        })
        self._trim()
        
    def get_messages(self) -> List[Dict[str, Any]]:
        return self.messages.copy()
    
    def _trim(self) -> None:
        """Keep system + last max_turns exchanges (each exchange = user + assistant/tool pair)."""
        # Count non-system messages
        # non_system = self.messages[1:]
        # We want to keep at most 2*max_turns non-system messages (alternating user/assistant)
        # if len(non_system) > 2 * self.max_turns:
            # remove oldest pairs
            # self.messages = [self.messages[0]] + non_system[-(2 * self.max_turns):]
        self.messages = self.messages[-(2 * self.max_turns):]
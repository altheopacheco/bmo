from typing import List, Dict, Any, Optional

from config import SYSTEM_PROMPT

class ConversationHistory:
    def __init__(self, max_turns: int = 10):
        self.max_turns = max_turns
        self.messages: List[Dict[str, Any]] = [
            {"role": "system", "content": SYSTEM_PROMPT}
        ]
    
    def add_user(self, content: str) -> None:
        self.messages.append({"role": "user", "content": content})
        self._trim()
    
    def add_assistant(self, content: str = "", reasoning: str = "", tool_calls: Optional[List[Dict]] = None) -> None:
        self.messages.append({
            "role": "assistant",
            "content": content,
            "reasoning_content": reasoning, # Some servers support saving this
            "tool_calls": tool_calls
        })
        self._trim()
        
    def add_tool_result(self, id, name, result) -> None:
        self.messages.append({
            "role": "tool", 
            "tool_call_id": id, 
            "name": name, 
            "content": result})
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
import json
import time
from typing import AsyncGenerator
from agent.events import ServerMessage
from services.llm import ResponderLLM
from services.tools import dispatch_tool
from agent.conversation import ConversationHistory
from config import MAX_CONVERSATION_TURNS, TOOLS

class AgentLoop:
    def __init__(
        self,
        llm: ResponderLLM,
        max_steps: int = 10,
    ):
        self.llm = llm
        self.conversation = ConversationHistory(max_turns=MAX_CONVERSATION_TURNS)
        self.max_steps = max_steps
        self.stopped = False
    
    def stop(self):
        self.stopped = True
    
    async def run(self, user_input: str) -> AsyncGenerator[ServerMessage, None]:
        print("[SYSTEM] Running agent loop...")
        self.stopped = False
        
        self.conversation.add_user(user_input)
        
        for step in range(self.max_steps):
            print(f"---------- Step {step + 1} ------------")
            start = time.perf_counter()
            if self.stopped:
                print("[SYSTEM] Stopped agent loop")
                yield ServerMessage(type="done")
                return
            
            print("[AGENT] BMO: Processing user prompt...")
            
            stream = self.llm.generate(
                conversation=self.conversation.get_messages(),
                tools=TOOLS,
            )

            reasoning_text = ""
            content_text = ""
            tool_calls_raw = {}

            async for chunk in stream:
                delta = chunk.choices[0].delta
                
                # A. Stream the Reasoning (Thought)
                reasoning = getattr(delta, "reasoning_content", None)
                if reasoning:
                    reasoning_text += reasoning
                    yield ServerMessage(type="reasoning_token", payload=reasoning)
                    print(f"\033[90m{reasoning}\033[0m", end="", flush=True)

                # B. Accumulate Tool Calls (Action)
                if delta.tool_calls:
                    if reasoning_text and not tool_calls_raw:
                        yield ServerMessage(type="reasoning_finish")
                    for tc in delta.tool_calls:
                        if tc.index not in tool_calls_raw:
                            tool_calls_raw[tc.index] = {"id": tc.id, "name": tc.function.name, "arguments": ""}
                        if tc.function.arguments:
                            tool_calls_raw[tc.index]["arguments"] += tc.function.arguments

                # C. Stream the Final Content (if any)
                if delta.content:
                    if reasoning_text and not content_text:
                        yield ServerMessage(type="reasoning_finish")
                    content_text += delta.content
                    yield ServerMessage(type="response_token", payload=delta.content)
                    print(delta.content, end="", flush=True)
            
            yield ServerMessage(type="response_finish")
            if tool_calls_raw:
                formatted_calls = [
                    {"id": v["id"], "type": "function", "function": {"name": v["name"], "arguments": v["arguments"]}}
                    for v in tool_calls_raw.values()
                ]
                
                self.conversation.add_assistant(content=content_text, reasoning=reasoning_text, tool_calls=formatted_calls or None)
                
                for tc in formatted_calls:
                    id = tc["id"]
                    name = tc['function']['name']
                    arguments = json.loads(tc['function']['arguments'])
                    
                    yield ServerMessage(type="tool_call", payload={"name": name, "args": arguments})
                    result = dispatch_tool(name, arguments or {})
                    yield ServerMessage(type="tool_result", payload=result)
                    
                    self.conversation.add_tool_result(id, name, result)
            else:
                self.conversation.add_assistant(content=content_text, reasoning=reasoning_text)
                yield ServerMessage(type="done")
                return

        # Exceeded max steps
        yield ServerMessage(type="error", payload="Max steps reached")
        yield ServerMessage(type="done")
        print("[SYSTEM] Stopped agent loop")
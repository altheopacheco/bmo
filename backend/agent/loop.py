import json
import time
from typing import AsyncGenerator
from agent.events import ServerMessage
from services.llm import RouterDecision, RouterLLM, ResponderLLM
from services.tools import dispatch_tool
from agent.conversation import ConversationHistory
from config import MAX_CONVERSATION_TURNS

class AgentLoop:
    def __init__(
        self,
        router: RouterLLM,
        responder: ResponderLLM,
        max_steps: int = 10
    ):
        self.router = router
        self.responder = responder
        self.conversation = ConversationHistory(max_turns=MAX_CONVERSATION_TURNS)
        self.max_steps = max_steps
        self.stopped = False
    
    def stop(self):
        self.stopped = True
    
    async def run(self, user_input: str) -> AsyncGenerator[ServerMessage, None]:
        # Add user message to history
        print("[SYSTEM] Running agent loop...")
        self.conversation.add_user(user_input)
        
        for step in range(self.max_steps):
            print(f"---------- Step {step + 1} ------------")
            start = time.perf_counter()
            if self.stopped:
                print("[SYSTEM] Stopped agent loop")
                yield ServerMessage(type="done")
                return
            
            print("[AGENT] BMO: Processing user prompt...")
            # decision = await self.router.decide(self.conversation.get_messages())
            
            stream = self.router._decide_stream(self.conversation.get_messages())
            
            decision_buffer = ""
            async for chunk in stream:
                if self.stopped:
                    break
                if not decision_buffer:
                    ttft = time.perf_counter() - start
                    print(f"[METRIC] TTFT: {ttft:.4}s")
                    print("[AGENT] Decision: ", end="", flush=True)
                    yield ServerMessage(type="metric", payload={"name": "ttft", "content": ttft})
                # new_token = chunk["choices"][0].get("delta", {}).get('content', "")
                if chunk:
                    print(chunk, end="", flush=True)
                    decision_buffer += chunk
                    
            print()
            
            try:
                decision = RouterDecision.model_validate(json.loads(decision_buffer))
            except (json.JSONDecodeError, ValueError) as e:
                # TODO: Add error to history and allow agent to retry
                yield ServerMessage(type="error", payload=f"Invalid router response: {e}")
                yield ServerMessage(type="done")
                return
            
            yield ServerMessage(type="status", payload=f"Step {step+1}: {decision.action}")
            
            if decision.action == "tool":
                if not decision.name:
                    continue
                # Execute tool
                result = dispatch_tool(decision.name, decision.args or {})
                # Log tool call and result in conversation (as plain text, compatible with any model)
                self.conversation.add_tool_call(tool_name=decision.name, args=decision.args)
                self.conversation.add_tool_result(tool_name=decision.name, result=result)
                # Notify frontend
                yield ServerMessage(type="tool_call", payload={"name": decision.name, "args": decision.args})
                yield ServerMessage(type="tool_result", payload=result)
                # Continue loop – router will see the result

            elif decision.action == "speak":
                # Generate intermediate message
                print("[AGENT] BMO: Generating reply...")
                stream = self.responder.generate(self.conversation.get_messages(), is_final=False)
                # Stream tokens (split into words for smoother UI)
                full_output = ""
                async for token in stream:
                    if self.stopped:
                        break
                    full_output += token
                    yield ServerMessage(type="llm_token", payload=token)
                # Append to conversation
                self.conversation.add_assistant(content=full_output)
                # Optionally yield an event to indicate intermediate speech is done (for TTS)
                yield ServerMessage(type="done")

            elif decision.action == "finish":
                # Generate final answer
                print("[AGENT] BMO: Generating reply...")
                stream = self.responder.generate(self.conversation.get_messages(), is_final=True)
                # Stream tokens
                full_output = ""
                yield ServerMessage(type="final_answer_start")
                async for token in stream:
                    if self.stopped:
                        break
                    full_output += token
                    yield ServerMessage(type="llm_token", payload=token)
                    
                self.conversation.add_assistant(content=full_output)
                yield ServerMessage(type="done")
                return

        # Exceeded max steps
        yield ServerMessage(type="error", payload="Max steps reached")
        yield ServerMessage(type="done")
        print("[SYSTEM] Stopped agent loop")
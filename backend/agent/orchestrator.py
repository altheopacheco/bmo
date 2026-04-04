from services.stt import STTService
from services.tts import TTSService
from services.llm import RouterLLM, ResponderLLM
from agent.loop import AgentLoop
from agent.events import ServerMessage

class AgentOrchestrator:
    def __init__(
        self,
        stt: STTService,
        router: RouterLLM,
        responder: ResponderLLM,
        tts: TTSService,
        max_steps: int = 10
    ):
        self.stt = stt
        self.router = router
        self.responder = responder
        self.tts = tts
        self.max_steps = max_steps
        self.agent_loop = None

    async def process_audio(self, audio_bytes: bytes, websocket) -> str:
        # 1. Transcribe
        print("[AGENT] Transcribing...")
        transcript = await self.stt.transcribe(audio_bytes)
        print("[AGENT] Transcript Complete:", transcript)
        return transcript

    async def run_loop(self, input: str, websocket):
        await websocket.send_json(ServerMessage(type="transcript", payload=input).model_dump())
        # 2. Run the two‑stage agent loop
        self.agent_loop = AgentLoop(self.router, self.responder, max_steps=self.max_steps)

        token_buffer: str = ""
        final_mode = False
        
        async def flush_sentence(sentence: str):
            nonlocal token_buffer
            audio_bytes, timeline = await self.tts.synthesize(sentence)
            await websocket.send_json(ServerMessage(type="viseme_timeline", payload=timeline).model_dump())
            await websocket.send_bytes(audio_bytes)
            token_buffer = ""

        async for event in self.agent_loop.run(input):
            # Forward all events to frontend
            if event.type == "status":
                print(f"[AGENT] Status: {event.payload}")
                await websocket.send_json(event.model_dump())
                
            elif event.type == "llm_token":
                # Forward token to frontend
                await websocket.send_json(event.model_dump())
                # Accumulate only if we are in final answer mode
                # if final_mode:
                token_buffer += event.payload
                if any(token_buffer.endswith(p) for p in [".", "!", "?", "\n", "—"]):
                    await flush_sentence(token_buffer)
            elif event.type == "reasoning":
                await websocket.send_json(event.model_dump())

            elif event.type == "tool_call":
                print(f"Calling {event.payload['name']}")
                await websocket.send_json(event.model_dump())

            elif event.type == "tool_result":
                await websocket.send_json(event.model_dump())

            elif event.type == "final_answer_start":
                final_mode = True
                await websocket.send_json(event.model_dump())

            elif event.type == "viseme_timeline":
                # This is usually sent by the orchestrator itself (not the loop)
                # but if the loop yields it, forward
                await websocket.send_json(event.model_dump())

            elif event.type == "metric":
                await websocket.send_json(event.model_dump())

            elif event.type == "error":
                await websocket.send_json(event.model_dump())
                # Optionally break or reset

            elif event.type == "done":
                # Final TTS using accumulated final answer tokens
                print(token_buffer)
                if token_buffer.strip():
                    await flush_sentence(token_buffer)
                # Forward the done event
                await websocket.send_json(event.model_dump())
                break   # end of turn

            else:
                # Unknown event type – log and ignore
                print(f"Unknown event type: {event.type}")

        print("[BMO] Idle")
        
    def cancel(self):
        if self.agent_loop:
            self.agent_loop.stop()
        else: 
            print("[WARN] Orchestrator.py: Called cancel when agent loop is None.")
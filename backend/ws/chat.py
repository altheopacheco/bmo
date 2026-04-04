import json
from fastapi import WebSocket, WebSocketDisconnect
from agent.orchestrator import AgentOrchestrator
from services.stt import WhisperSTT
from services.tts import PiperTTS
from services.llm import RouterLLM, ResponderLLM
from config import MAX_AGENT_STEPS, build_router_system_prompt, RESPONDER_SYSTEM_PROMPT

async def chat_ws(websocket: WebSocket):
    await websocket.accept()
    app = websocket.app

    # Models loaded during lifespan
    router_llm = RouterLLM(app.state.router_model, build_router_system_prompt())
    responder_llm = ResponderLLM(app.state.responder_model, RESPONDER_SYSTEM_PROMPT)
    stt = app.state.stt
    tts = PiperTTS(app.state.voice)

    orchestrator = AgentOrchestrator(
        stt=stt, router=router_llm, responder=responder_llm, tts=tts,
        max_steps=MAX_AGENT_STEPS
    )

    audio_buffer = bytearray()
    try:
        while True:
            msg = await websocket.receive()
            print(msg["type"])
            if msg["type"] == "websocket.disconnect":
                break
            
            if "text" in msg:
                print(msg)
                try:
                    data = json.loads(msg["text"])
                except json.JSONDecodeError:
                    continue
                if data.get("type") == "stop":
                    await orchestrator.process_audio(bytes(audio_buffer), websocket)
                    audio_buffer.clear()
                elif data.get("type") == "cancel":
                    orchestrator.cancel()
            elif "bytes" in msg:
                audio_buffer.extend(msg["bytes"])
    except WebSocketDisconnect:
        orchestrator.cancel()
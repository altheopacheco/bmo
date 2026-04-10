import json
from fastapi import WebSocket, WebSocketDisconnect
from agent.orchestrator import AgentOrchestrator
from services.tts import PiperTTS
from config import MAX_AGENT_STEPS

async def chat_ws(websocket: WebSocket):
    await websocket.accept()
    app = websocket.app

    # Models loaded during lifespan
    llm = app.state.llm
    stt = app.state.stt
    tts = PiperTTS(app.state.voice)

    orchestrator = AgentOrchestrator(
        stt=stt, llm=llm, tts=tts,
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
                    transcript = await orchestrator.process_audio(bytes(audio_buffer))
                    await orchestrator.run_loop(transcript, websocket=websocket)
                    audio_buffer.clear()
                elif data.get("type") == "cancel":
                    orchestrator.cancel()
                elif data.get("type") == "user_message":
                    user_input = data.get('content', None)
                    if user_input:
                        await orchestrator.run_loop(user_input, websocket=websocket)
            elif "bytes" in msg:
                audio_buffer.extend(msg["bytes"])
    except WebSocketDisconnect:
        orchestrator.cancel()
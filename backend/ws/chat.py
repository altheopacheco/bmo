import asyncio, json, time
from fastapi import WebSocket, WebSocketDisconnect
from services.tts import synthesize
from services.ollama import make_conversation, get_streaming_response, commit_reply
from services.transcribe import transcribe_audio

async def chat_ws(websocket: WebSocket):
    await websocket.accept()
    conversation = make_conversation()

    try:
        while True:
            message = await websocket.receive()

            if message["type"] == "websocket.disconnect":
                break

            audio_bytes = message.get("bytes")
            if not audio_bytes:
                continue

            transcript = await _transcribe(websocket, audio_bytes)
            if transcript:
                await _stream_reply(websocket, conversation, transcript)
            else: 
                print("No transcript received")        
            await websocket.send_text(json.dumps({"type": "end_reply"}))
            

    except WebSocketDisconnect:
        print("Client disconnected")

async def _transcribe(websocket: WebSocket, audio_bytes: bytes) -> str:
    if audio_bytes is None: 
        return
    print("Transcribing...")
    start_time = time.perf_counter()
    
    loop = asyncio.get_running_loop()
    (segments, _) = await loop.run_in_executor(None, transcribe_audio, audio_bytes)


    if not segments:
        await websocket.send_text(json.dumps({"type": "error", "message": "Could not transcribe audio"}))
        return ""

    
    transcript = ""

    for segment in segments:
        time_elapsed = time.perf_counter() - start_time
        transcript += segment.text
        await websocket.send_text(json.dumps({"type": "user", "text": segment.text}))
        await websocket.send_text(json.dumps({"type": "transcription_metric", "time_elapsed": time_elapsed}))
        
    return transcript

async def _stream_reply(websocket: WebSocket, conversation: list, user_input: str):
    loop = asyncio.get_event_loop()
    response = await loop.run_in_executor(
        None, get_streaming_response, conversation, user_input
    )

    reply = ""
    buffer = ""
    llm_start = time.perf_counter()
    
    await websocket.send_text(json.dumps({"type": "start"}))
    
    voice = websocket.app.state.voice
    
    async def flush_sentence(sentence: str):
        if not sentence:
            return
        tts_start = time.perf_counter()
        
        audio, timeline = await loop.run_in_executor(None, synthesize, sentence, voice)
        
        await websocket.send_text(json.dumps({"type": "viseme_timeline", "timeline": timeline}))
        await websocket.send_bytes(audio)
        
        tts_elapsed = time.perf_counter() - tts_start
        await websocket.send_text(json.dumps({"type": "audio_metric", "time_elapsed": tts_elapsed}))

    for chunk in response:
        content = chunk["message"]["content"]
        reply += content
        buffer += content
        await websocket.send_text(json.dumps({"type": "chunk", 
                                              "text": content}))
        
        if any(buffer.endswith(p) for p in [".", "!", "?", "\n"]):
            llm_elapsed = time.perf_counter() - llm_start
            await websocket.send_text(json.dumps({"type": "llm_metric", "time_elapsed": llm_elapsed}))

            sentence = buffer.strip()
            buffer = ""
            await flush_sentence(sentence)
                    
    if buffer.strip():
        await flush_sentence(buffer.strip())

    commit_reply(conversation, reply)
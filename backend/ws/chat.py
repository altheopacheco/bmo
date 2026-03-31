import asyncio, json, time
from fastapi import WebSocket, WebSocketDisconnect
from config import MAX_TOOL_CALLS, OLLAMA_MODEL
from services.tools import TOOLS
from services.tts import synthesize
from services.ollama import make_conversation, get_streaming_response, commit_reply
from services.transcribe import transcribe_audio

async def chat_ws(websocket: WebSocket):
    await websocket.accept()
    
    if websocket.app.state.voice is None:
        await websocket.send_text(json.dumps({
            "type": "error",
            "message": "BMO is still waking up. Please wait a moment."
        }))
        await websocket.close()
        return
    
    conversation = make_conversation()

    try:
        while True:
            message = await websocket.receive()
            
            if websocket.app.state.system_init_message != "Initialized":
                print("BMO not ready")
                continue

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
        transcript += segment.text
        time_elapsed = time.perf_counter() - start_time
        await websocket.send_text(json.dumps({"type": "user", "text": segment.text}))
        await websocket.send_text(json.dumps({"type": "transcription_metric", "time_elapsed": time_elapsed}))

    print("User: " + transcript)    
    return transcript


async def _stream_reply(websocket: WebSocket, conversation: list, user_input: str):
    conversation.append({"role": "user", "content": user_input})
    
    loop = asyncio.get_running_loop()
    
    await websocket.send_text(json.dumps({"type": "start"}))
    
    voice = websocket.app.state.voice
    
    # For sending audio to client - TEXT TO SPEECH BLOCK
    async def flush_sentence(sentence: str): 
        if not sentence:
            return
        tts_start = time.perf_counter()
        
        audio, timeline = await loop.run_in_executor(None, synthesize, sentence, voice)
        
        tts_elapsed = time.perf_counter() - tts_start
        
        await websocket.send_text(json.dumps({"type": "viseme_timeline", "timeline": timeline}))
        await websocket.send_bytes(audio)
        
        await websocket.send_text(json.dumps({"type": "audio_metric", "time_elapsed": tts_elapsed}))

    for i in range(MAX_TOOL_CALLS): 
        print(f"AGENT LOOP - {i}")
        reply = ""
        buffer = ""
        first_chunk = True
        thinking = ""
        tool_calls = []
 
        llm_start = time.perf_counter()

        print("Generating response...")
        async for chunk in get_streaming_response(conversation, websocket.app.state.ollama_client):
            if chunk is None: break
            ttft = time.perf_counter() - llm_start
            
            if chunk.message.thinking:
                thinking += chunk.message.thinking
                print(chunk.message.thinking, end='', flush=True)
                
            if chunk.message.tool_calls:
                tool_calls.extend(chunk.message.tool_calls)
                print(chunk.message.tool_calls)
            
            content = chunk["message"]["content"]
            if content:
                if first_chunk:
                    first_chunk = False
                    await websocket.send_text(json.dumps({"type": "llm_metric", "time_elapsed": ttft}))

                reply += content
                buffer += content
                print(content, end="", flush=True)
                await websocket.send_text(json.dumps({"type": "chunk", 
                                                    "text": content}))
            
                if any(buffer.endswith(p) for p in [".", "!", "?", "\n", "—", ","]):
                    sentence = buffer.strip()   
                    buffer = ""
                    await flush_sentence(sentence)
                    
        if buffer.strip():
            await flush_sentence(buffer.strip())

        assistant_turn = {"role": "assistant", "content": reply}
        if thinking: assistant_turn["thinking"] = thinking
        if tool_calls: assistant_turn["tool_calls"] = tool_calls
        
        commit_reply(conversation, assistant_turn)
        
        if not tool_calls:
            break
        
        print("Calling tools")
        for tc in tool_calls:
            if tc.function.name in TOOLS:
                print(f"Calling {tc.function.name} with arguments {tc.function.arguments}")
                result = TOOLS[tc.function.name](**tc.function.arguments)
                print(f"Result: {result}")
                conversation.append({'role': 'tool', 'tool_name': tc.function.name, 'content': str(result)})
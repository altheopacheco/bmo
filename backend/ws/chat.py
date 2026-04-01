import asyncio, json, time
from fastapi import WebSocket, WebSocketDisconnect
from httpx import AsyncClient
from services.state import BMOState, StateManager
from config import LLAMA_MODEL, MAX_AGENT_LOOPS
from services.tools import TOOL_SCHEMAS, TOOLS
from services.tts import synthesize
from services.ollama import make_conversation, commit_reply
from services.transcribe import transcribe_audio

async def chat_ws(websocket: WebSocket):
    await websocket.accept()
    
    state: StateManager = websocket.app.state.bmo_state
    
    if state.state != BMOState.IDLE:
        await websocket.send_json({"type": "error", "message": f"BMO not ready: {state.state}"})
        await websocket.close()
        return
    
    conversation = make_conversation()
    client = websocket.app.state.llama_client

    try:
        while True:
            message = await websocket.receive()

            if message["type"] == "websocket.disconnect":
                break

            audio_bytes = message.get("bytes")
            if not audio_bytes:
                continue

            transcript = await _transcribe(websocket, state, audio_bytes)
            if transcript:
                await _stream_reply(websocket, client, state, conversation, transcript)
            else: 
                print("No transcript received")   
                     
            await websocket.send_text(json.dumps({"type": "end_reply"}))
            await state.set(BMOState.IDLE)
            

    except WebSocketDisconnect:
        print("Client disconnected")
        await state.set(BMOState.IDLE)
    except Exception as e:
        print(f"WebSocket error: {e}")
        await state.set(BMOState.ERROR, str(e))

async def _transcribe(websocket: WebSocket, state: StateManager, audio_bytes: bytes) -> str:
    if audio_bytes is None: 
        return
    print("Transcribing...")
    await state.set(BMOState.TRANSCRIBING)
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


async def _stream_reply(websocket: WebSocket, client: AsyncClient, state: StateManager, conversation: list, user_input: str):
    conversation.append({"role": "user", "content": user_input})
    
    loop = asyncio.get_running_loop()
    
    await websocket.send_text(json.dumps({"type": "start"}))
    
    voice = websocket.app.state.voice
    
    # For sending audio to client - TEXT TO SPEECH BLOCK
    async def flush_sentence(sentence: str): 
        if not sentence:
            return
        
        await state.set(BMOState.SPEAKING)
        
        tts_start = time.perf_counter()
        
        audio, timeline = await loop.run_in_executor(None, synthesize, sentence, voice)
        
        tts_elapsed = time.perf_counter() - tts_start
        
        await websocket.send_text(json.dumps({"type": "viseme_timeline", "timeline": timeline}))
        await websocket.send_bytes(audio)
        
        await websocket.send_text(json.dumps({"type": "audio_metric", "time_elapsed": tts_elapsed}))
    
    agent_loop_idx = 0
    while True: 
        if agent_loop_idx == MAX_AGENT_LOOPS: 
            warning = "hit MAX_AGENT_LOOPS limit"
            print("Warning:", warning)
            await websocket.send_json({"type": "error", "message": warning})
            break
        
        agent_loop_idx+=1
        print(f"AGENT LOOP - {agent_loop_idx}")
        await state.set(BMOState.THINKING)
        reply = ""
        buffer = ""
        reasoning = ""
        tool_calls: dict[int, dict] = {}

        llm_start = time.perf_counter()
        ttft = None

        print("Generating response...")
        async with client.stream("POST", "/v1/chat/completions", json={
            "model": LLAMA_MODEL,
            "messages": conversation,
            "tools": TOOL_SCHEMAS,  
            "tool_choice": "auto",
            "stream": True,
        }) as resp:
            async for line in resp.aiter_lines():
                if not line or not line.startswith("data: "): continue
                
                data = line[len("data: "):]
                if data.strip() == "[DONE]": break
                
                chunk = json.loads(data)
                choice = chunk["choices"][0]
                delta = choice["delta"]
                finish_reason = choice.get("finish_reason", None)
                
                if chunk is None: break
                
                if ttft is None:
                    ttft = time.perf_counter() - llm_start
                    await websocket.send_text(json.dumps({"type": "llm_metric", "time_elapsed": ttft}))
                    
                
                if delta.get("reasoning_content"):
                    reasoning = delta["reasoning_content"]
                    await websocket.send_text(json.dumps({"type": "reasoning", 
                                                        "text": reasoning}))
                    print(reasoning or "", end="", flush=True)
                    reasoning += reasoning
                    
                for tc in delta.get("tool_calls") or []:
                    idx = tc["index"]
                    if idx not in tool_calls:
                        tool_calls[idx] = {
                            "id": tc.get("id", ""),
                            "type": "function",
                            "function": {"name": "", "arguments": ""}
                        }
                    fn = tc.get("function", {})
                    tool_calls[idx]["function"]["name"] += fn.get("name") or ""
                    tool_calls[idx]["function"]["arguments"] += fn.get("arguments") or ""
                
                content = delta.get("content") or ""
                if content:
                    reply += content
                    buffer += content
                    print(content, end="", flush=True)
                    await websocket.send_text(json.dumps({"type": "chunk", 
                                                        "text": content}))
                
                    if any(buffer.endswith(p) for p in [".", "!", "?", "\n", "—", ","]):
                        await flush_sentence(buffer.strip())
                        buffer = ""
                        
            if buffer.strip():
                await flush_sentence(buffer.strip())

            assistant_turn: dict = {"role": "assistant"}
            if reply: assistant_turn["content"] = reply
            if reasoning: assistant_turn["reasoning_content"] = reasoning
            if tool_calls: assistant_turn["tool_calls"] = list(tool_calls.values())
            
            commit_reply(conversation, assistant_turn)
            
            if finish_reason == "tool_calls":
                print(f"Executing {len(tool_calls)} tool call(s)...")
                await state.set(BMOState.TOOL, f"Executing {len(tool_calls)} tool call(s)...")
                for tc in tool_calls.values():
                    fn_name = tc["function"]["name"]
                    fn_args = json.loads(tc["function"]["arguments"])
                    print(f"  → {fn_name}({fn_args})")
                    await state.set(BMOState.TOOL, f"Calling {fn_name}({fn_args})...")

                    result = TOOLS[fn_name](**fn_args) if fn_name in TOOLS else {"error": f"Unknown tool: {fn_name}"}
                    print(f"  ← {result}")
                    await state.set(BMOState.TOOL, f"{fn_name}({fn_args}) returned {result}")

                    conversation.append({
                        "role": "tool",
                        "tool_call_id": tc["id"],
                        "content": json.dumps(result) if not isinstance(result, str) else result
                    })
                continue;

            if finish_reason: 
                print(f"Finish reason: {finish_reason} → ending agent loop")
                break
import json

import httpx

LLAMA_SERVER = "http://localhost:8080"
PROMPT = "What is the weather in Istanbul and tokyo?"

MODEL = "qwen3-1.7b-q4_k_m"
payload = {
                "model": MODEL,
                "messages": 
                        [
                            {"role": "system", "content": "You are a chatbot that uses tools/functions. Dont overthink things."},
                            {"role": "user", "content": PROMPT}
                        ],
                "tools": [
                    {
                    "type":"function",
                    "function":{
                            "name":"get_weather",
                            "description":"Gets the current weather conditions of a city",
                            "parameters":{
                            "type":"object",
                            "properties":{
                                "city":{
                                "type":"string",
                                "description":"The name of the city"
                                }
                            },
                            "required":["city"]
                            }
                        }
                    }
                ],
                "tool_choice": "auto",
                "stream": True,
            }

def stream():
    print(f"User: {PROMPT}")
    collected_tool_calls = {}
    with httpx.stream("POST", "http://localhost:8080/v1/chat/completions", json=payload, timeout=None) as resp:
        for line in resp.iter_lines():
            if not line:
                continue
            if line.startswith("data: "):
                data = line[len("data: "):]

                if data.strip() == "[DONE]":
                    break
                
                chunk = json.loads(data)
                delta = chunk["choices"][0]["delta"]
                finish_reason = chunk["choices"][0].get("finish_reason")

                if "content" in delta:
                    print(delta["content"] or "", end="", flush=True)
                elif "reasoning_content" in delta:
                    print(delta["reasoning_content"], end="", flush=True)
                elif delta.get("tool_calls"):
                    for tc in delta["tool_calls"]:
                        idx = tc["index"]
                        if idx not in collected_tool_calls:
                            collected_tool_calls[idx] = {
                                "id": tc.get("id", ""),
                                "type": "function",
                                "function": {"name": "", "arguments": ""}
                            }
                        fn = tc.get("function", {})
                        if fn.get("name"):
                            collected_tool_calls[idx]["function"]["name"] += fn["name"]
                        if fn.get("arguments"):
                            collected_tool_calls[idx]["function"]["arguments"] += fn["arguments"]

                if finish_reason == "tool_calls":
                    print(f"\n[Executing {len(collected_tool_calls)} tool call(s)]")
                    for tc in collected_tool_calls.values():
                        name = tc["function"]["name"]
                        args = json.loads(tc["function"]["arguments"])
                        print(f"  → {name}({args})")
stream()
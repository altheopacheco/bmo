import time, json, httpx
from config import SYSTEM_PROMPT

PROMPT = "Explain how a neural network works."
MODEL_PATH = "C:/Users/althe/Downloads/qwen3-1.7b-q4_k_m.gguf"
TOOL_PROMPT = "What's the weather like in tokyo?"

client = httpx.Client(base_url="http://localhost:8080", timeout=None)
MODEL = "qwen3-1.7b-q4_k_m"

TOOLS = [
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
        ]

def benchmark_llama_cpp_chat():
    print("Benchmarking Llama-cpp Chat...")
    tokens = 0
    tps = 0
    ttft = None
    start = time.perf_counter()

    with client.stream("POST", "/v1/chat/completions", json={
        "model": MODEL,
        "messages": [
            {"role": "system", "content": SYSTEM_PROMPT},
            {"role": "user", "content": PROMPT}
        ],
        "stream": True,
    }) as resp:
    
        print("Output:")
        for line in resp.iter_lines():
            if not line:
                continue
            if line.startswith("data: "):
                data = line[len("data: "):]

                if data.strip() == "[DONE]":
                    break
                
                chunk = json.loads(data)
                delta = chunk["choices"][0]["delta"]
            
                if ttft is None:
                    ttft = time.perf_counter() - start
                    
                delta = chunk["choices"][0]["delta"]
                
                if "content" in delta:
                    print(delta["content"] or "", end="", flush=True)

                if "reasoning_content" in delta:
                    print(delta["reasoning_content"], end="", flush=True)
                    
                if "timings" in chunk:
                    timings = chunk.get("timings", {})
                    tokens = timings["predicted_n"]
                    tps = timings["predicted_per_second"]
    
    end = time.perf_counter()
    
    print("\n--- LLAMA-CPP CHAT ---")
    print(f"TTFT: {ttft:.4}s")
    print(f"Total Time Elapsed: {end - start:.4}s")
    print(f"Tokens: {tokens}")
    print(f"Tokens per second: {tps:.4}")

def benchmark_llama_cpp_tools():
    print("Benchmarking Llama-cpp Chat...")
    messages=[
            {"role": "system", "content": SYSTEM_PROMPT},
            {"role": "user", "content": TOOL_PROMPT}
        ]
    tokens = 0
    ttft = None
    start = time.perf_counter()
    
    stream = llm.create_chat_completion(
        messages=messages,
        stream=True,
        tools=TOOLS,
        tool_choice="auto"
    )
    
    print("Output:")
    collected_content = ""
    collected_tool_calls = {}  # keyed by index

    for chunk in stream:
        if ttft is None:
            ttft = time.perf_counter() - start
        tokens += 1
        
        delta = chunk["choices"][0]["delta"]

        # Regular text content
        if delta.get("content"):
            print(delta["content"], end="", flush=True)
            collected_content += delta["content"]

        # Tool call fragments
        if delta.get("tool_calls"):
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

        finish_reason = chunk["choices"][0].get("finish_reason")
        if finish_reason == "tool_calls":
            print("\n[Model wants to call tools]")
    
    if collected_tool_calls:
        tool_call_list = list(collected_tool_calls.values())

        # Append assistant tool call turn
        messages.append({
            "role": "assistant",
            "content": collected_content or None,
            "tool_calls": tool_call_list
        })

        # Execute each tool and append results
        for tc in tool_call_list:
            fn_name = tc["function"]["name"]
            fn_args = json.loads(tc["function"]["arguments"])
            print(f"\n[Calling {fn_name}({fn_args})]")
            result = TOOL_MAP[fn_name](**fn_args)
            messages.append({
                "role": "tool",
                "tool_call_id": tc["id"],
                "content": result
            })

        # Stream the final response
        print("\n[Final Response]")
        final_stream = llm.create_chat_completion(
            messages=messages,
            tools=TOOLS,
            stream=True,
        )
        for chunk in final_stream:
            tokens += 1
            delta = chunk["choices"][0]["delta"]
            if delta.get("content"):
                print(delta["content"], end="", flush=True)
                
    end = time.perf_counter()
    
    print("\n--- LLAMA-CPP TOOLING ---")
    print(f"TTFT: {ttft:.4}s")
    print(f"Total Time Elapsed: {end - start:.4}s")
    print(f"Tokens: {tokens}")
    print(f"Tokens per second: {tokens/(end-start):.4}")
    
for i in range(1):
    print("Iteration:", i)
    print("Starting Cold Run...")
    benchmark_llama_cpp_chat()

    print("Starting Warm Run...")
    benchmark_llama_cpp_chat()
    
    # benchmark_llama_cpp_tools(model)

    print("\nShutting down Llama-cpp...")
    print("Shut Down Complete")
    


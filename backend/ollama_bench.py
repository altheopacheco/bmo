import time, os
from ollama import chat
from config import OLLAMA_MODEL, SYSTEM_PROMPT

PROMPT = "Explain how a neural network works."
TOOL_PROMPT = "What is 7 + 8"

def add(x: int, y: int):
    return x + y

def stop_ollama():
    time.sleep(1)  # small delay to ensure all output is done
    os.system("taskkill /IM ollama.exe /F")

def benchmark_ollama_chat():
    print("Benchmarking Ollama Chat...")
    start = time.perf_counter()
    ftt = None
    token_count = 0

    stream = chat(
        model=OLLAMA_MODEL,
        messages=[
            {"role": "system", "content": SYSTEM_PROMPT},
            {"role": "user", "content": PROMPT}
        ],
        stream=True,
        keep_alive=-1
    )
    
    for chunk in stream:
        if ftt is None:
            ftt = time.perf_counter()
            
        # content = chunk["message"]["content"]
        
        if chunk.get("done"):
            token_count = chunk.get("eval_count", 0)
        
    end = time.perf_counter()
    
    print("\n--- OLLAMA CHAT ---")
    print("TTFT:", ftt - start, "s")
    print("Total Time Taken:", end - start, "s")
    print("Tokens:", token_count, " tokens")
    print("Tokens/sec:", token_count / (end - ftt), " tokens")

def benchmark_ollama_tools():
    print("Benchmarking Ollama Tooling...")
    start = time.perf_counter()
    ftt = None
    token_count = 0

    stream = chat(
        model=OLLAMA_MODEL,
        messages=[
            {"role": "system", "content": SYSTEM_PROMPT},
            {"role": "user", "content": PROMPT}
        ],
        stream=True,
        tools=[add],
        keep_alive=0
    )
    
    for chunk in stream:
        if ftt is None:
            ftt = time.perf_counter()
            
        # content = chunk["message"]["content"]
        if chunk.get("done"):
            token_count = chunk.get("eval_count", 0)
        
    end = time.perf_counter()
    
    print("\n--- OLLAMA TOOLING ---")
    print("TTFT:", ftt - start, "s")
    print("Total Time Taken:", end - start, "s")
    print("Tokens:", token_count, " tokens")
    print("Tokens/sec:", token_count / (end - ftt), " tokens")
    
print("Benchmarking", OLLAMA_MODEL)
for i in range(3):
    print("Iteration:", i)
    print("Starting Cold Run...")
    benchmark_ollama_chat()

    print("Starting Warm Run...")
    benchmark_ollama_chat()

    benchmark_ollama_tools()

    print("\nShutting down Ollama...")
    stop_ollama()
    print("Shut Down Complete")
    
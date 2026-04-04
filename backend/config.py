from pathlib import Path

# Paths
BASE_DIR = Path(__file__).resolve().parent
MODEL_DIR = BASE_DIR / "models"

# LLM models (llama-cpp-python)
ROUTER_MODEL_PATH = str(MODEL_DIR / "Llama-3.2-1B-Instruct-Q5_K_M.gguf")
RESPONDER_MODEL_PATH = str(MODEL_DIR / "Llama-3.2-1B-Instruct-Q5_K_M.gguf")

# STT & TTS
WHISPER_MODEL_SIZE = "base.en"
PIPER_MODEL_PATH = str(MODEL_DIR / "bmo.onnx")

# Agent settings
MAX_CONVERSATION_TURNS = 5
MAX_AGENT_STEPS = 10
RESPONDER_SYSTEM_PROMPT = "You are BMO, a helpful AI assistant."  # base system prompt

TOOLS: dict[str, dict] = {
    "get_weather": {
        "description": "Get current weather for a city.",
        "args": {"city": "string"},
    },
    "calculate": {
        "description": "Evaluate an arithmetic expression.",
        "args": {"expression": "string  e.g. '12 * (3 + 7)'"},
    },
    "search_web": {
        "description": "Search the web and return a brief summary.",
        "args": {"query": "string"},
    },
}

# Router system prompt (built dynamically from tools)
def build_router_system_prompt() -> str:
    tool_list = "\n".join(
       f"  {name}: {meta['description']}  args={meta['args']}\n"
        for name, meta in TOOLS.items()
    )
    return f"""
Decide next action: tool, speak, or finish.

Available Tools:
{tool_list}

RULES (strict order):
1. **finish** – Use when:
   - User request is fully satisfied.
   - After a successful tool call that answers the question.
   - User says hi/thanks/goodbye.

2. **tool** – Use when you need external data.
   - For multiple items (e.g., weather in two cities), call the tool **once per item**.
   - After each tool result, decide again (call next tool or finish).
   - Never put two cities in one `args`.

3. **speak** – Brief acknowledgment before a tool. Never two speaks in a row.

If a tool returns an error, fix the arguments or finish if impossible.

Output JSON only. Examples:

User: "Weather in New York and Chicago"
Step1: {{"action": "tool", "name": "get_weather", "args": {{"city": "New York"}}}}
(After result)
Step2: {{"action": "tool", "name": "get_weather", "args": {{"city": "Chicago"}}}}
(After result)
Step3: {{"action": "finish"}}

User: "Hi"
{{"action": "finish"}}

User: "What's 5+7?"
{{"action": "tool", "name": "calculate", "args": {{"expression": "5+7"}}}}
Then: {{"action": "finish"}}

Never output: {{"action": "tool", "name": "get_weather", "args": {{"city": "New York", "city2": "Chicago"}}}}"""
"""
Two-stage router + responder agentic loop.

Architecture per turn:
  ┌─────────────────────────────────────────────────────┐
  │  User message                                        │
  │        │                                            │
  │        ▼                                            │
  │  ┌──────────┐  JSON decision   ┌───────────────┐   │
  │  │  Router  │ ──────────────▶  │ Python dispatch│  │
  │  │ (small,  │                  │ - run tool     │  │
  │  │  fast)   │ ──────────────▶  │ - call         │  │
  │  └──────────┘  speak/finish    │   Responder    │  │
  │        ▲                       └───────┬───────┘   │
  │        │        context grows          │           │
  │        └──────────────────────◀────────┘           │
  │  (loop until router says "finish")                  │
  └─────────────────────────────────────────────────────┘

Router outputs one of:
  {"action": "tool",   "name": "...", "args": {...}}
  {"action": "speak"}          ← triggers Responder for an intermediate message
  {"action": "finish"}         ← triggers Responder for the final reply, ends turn

This means the model CAN speak mid-turn (e.g. "Let me look that up...")
before calling tools and then finishing.

Requirements:
    pip install openai

Start llama.cpp (two windows if using separate models, or same port):
    ./llama-server -m router-model.gguf  --port 8080
    ./llama-server -m respond-model.gguf --port 8081
"""

import json
import re
from typing import Literal, Optional, Union
from llama_cpp import Llama
from llama_cpp.llama_grammar import json_schema_to_gbnf, LlamaGrammar
from pydantic import BaseModel, Field, TypeAdapter

from config import LLAMA_MODEL, LLAMA_SERVER_URL

# ── Clients ───────────────────────────────────────────────────────────────────
# Point both at the same server if you only have one model loaded,
# or use different ports/models for a proper small-router / large-responder split.

# router_model = Llama(
#     model_path="C:/Users/althe/Downloads/qwen3-1.7b-q4_k_m.gguf",
#     verbose=False, n_ctx=2048
# )

worker_model = Llama(
    model_path="C:/Users/althe/Downloads/nemotron-mini-4b-instruct-q4_k_m.gguf",
    verbose=False, n_ctx=2048
)

router_model = worker_model

# ── Tool registry ─────────────────────────────────────────────────────────────
# Add new tools here — router learns about them via the system prompt.
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


# ── Tool implementations ──────────────────────────────────────────────────────
def get_weather(city: str) -> str:
    # Replace with a real HTTP call to your weather API of choice
    return f"Weather in {city}: 26 °C, partly cloudy."


def calculate(expression: str) -> str:
    try:
        return str(eval(expression, {"__builtins__": {}}))
    except Exception as e:
        return f"Error evaluating '{expression}': {e}"


def search_web(query: str) -> str:
    # Replace with a real search API (SerpAPI, Brave, etc.)
    return f"(Stub) Top result for '{query}': No live search wired up yet."


def dispatch(name: str, args: dict) -> str:
    handlers = {
        "get_weather": get_weather,
        "calculate":   calculate,
        "search_web":  search_web,
    }
    fn = handlers.get(name)
    if fn is None:
        return f"[error] Unknown tool '{name}'"
    try:
        return fn(**args)
    except TypeError as e:
        return f"Error: {e}. This tool expects only: {fn.__annotations__}"


# ── Prompts ───────────────────────────────────────────────────────────────────
def build_router_system() -> str:
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

ROUTER_SYSTEM = build_router_system()

RESPONDER_SYSTEM = """\
You are a helpful, concise assistant. Generate a natural language message based \
on the conversation so far.

If the instruction says INTERMEDIATE, keep it brief — one or two sentences \
acknowledging what you are about to do.
If the instruction says FINAL, give a complete, accurate answer using all \
available context."""


class RouterOutput(BaseModel):
    action: Literal["tool", "speak", "finish"]
    name: Optional[Literal["get_weather", "calculate", "search_web"]] = None
    args: Optional[dict] = None

json_schema = json.dumps(RouterOutput.model_json_schema())
grammar = LlamaGrammar.from_json_schema(json_schema)

# ── Router call ───────────────────────────────────────────────────────────────
def call_router(conversation: list[dict]) -> RouterOutput:
    """Ask the router model what to do next. Returns a parsed decision dict."""

    decision = router_model.create_chat_completion(
                    messages=[
                            {"role": "system", "content": ROUTER_SYSTEM},
                            *conversation,
                        ],
                    grammar=grammar
                )
    
    response_text = decision['choices'][0]['message']['content']
    parsed = json.loads(response_text)

    result = RouterOutput.model_validate(parsed)
    
    if result.action != "tool":
        result.name = None
        result.args = None
    print(f"  [router raw] {result!r}") 
    return result


# ── Responder call ────────────────────────────────────────────────────────────
def call_responder(conversation: list[dict], *, is_final: bool) -> str:
    """Generate a natural-language message via the responder model."""
    mode = "FINAL" if is_final else "INTERMEDIATE"
    response = worker_model.create_chat_completion(
        messages=[
            {"role": "system", "content": f"{RESPONDER_SYSTEM}\n\nMode: {mode}"},
            *conversation,
        ],
    )
    return (response['choices'][0]['message']['content'] or "").strip()


# ── Shared context helpers ────────────────────────────────────────────────────
# We store everything in one flat conversation list.
# Tool interactions are represented as assistant + user pairs so any model
# architecture (with or without native tool roles) can follow along.

def ctx_assistant(conv: list, text: str) -> None:
    conv.append({"role": "assistant", "content": text})

def ctx_tool_result(conv: list, name: str, args: dict, result: str) -> None:
    # Log the call as an assistant action so the router sees it in history
    conv.append({
        "role": "assistant",
        "content": json.dumps({
            "action": "tool",
            "name": name,
            "args": args
        })
    })
    # Return the result in the user slot — widely understood by all model families
    conv.append({
        "role": "user",
        "content": json.dumps({
            "tool_result": name,
            "result": result
        })
    })


# ── Main loop ─────────────────────────────────────────────────────────────────
def run_agent() -> None:
    print("Agent ready. Type 'quit' to stop.\n")

    conversation: list[dict] = []

    while True:
        # ── Outer: get user input ─────────────────────────────────────────────
        try:
            user_input = input("You: ").strip()
        except (EOFError, KeyboardInterrupt):
            print("\nBye!")
            break

        if not user_input:
            continue
        if user_input.lower() in {"quit", "exit"}:
            print("Bye!")
            break

        conversation.append({"role": "user", "content": user_input})

        # ── Inner: agentic planning loop ──────────────────────────────────────
        step = 0
        while True:
            step += 1
            decision = call_router(conversation)

            print(f"  [step {step}] router → {decision}", end="", flush=True)

            # ── Tool call ─────────────────────────────────────────────────────
            if decision.action == "tool":
                name = decision.name
                args = decision.args
                if name is None or args is None:
                    result = f"[error] Router returned tool action but missing name or args"
                    ctx_tool_result(conversation, name or "unknown", args or {}, result)
                    continue
                print(f": {name}({json.dumps(args)})", flush=True)

                result = dispatch(name, args)
                print(f"  [result] {result}", flush=True)

                ctx_tool_result(conversation, name, args, result)
                # Router will see the result on the next iteration

            # ── Intermediate speech ───────────────────────────────────────────
            elif decision.action == "speak":
                print(flush=True)
                text = call_responder(conversation, is_final=False)
                print(f"\nAssistant: {text}\n", flush=True)
                ctx_assistant(conversation, text)
                # Router keeps going

            # ── Final reply ───────────────────────────────────────────────────
            elif decision.action == "finish":
                print(flush=True)
                text = call_responder(conversation, is_final=True)
                print(f"\nAssistant: {text}\n", flush=True)
                ctx_assistant(conversation, text)
                break  # End this turn, return to outer loop for next user message

            else:
                print(f" (unrecognised — finishing)", flush=True)
                break

if __name__ == "__main__":
    run_agent()
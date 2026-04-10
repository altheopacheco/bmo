from pathlib import Path
from openai.types.chat import ChatCompletionToolUnionParam

# Paths
BASE_DIR = Path(__file__).resolve().parent
MODEL_DIR = BASE_DIR / "models"

# LLM models 
LLAMA_SERVER_URL="http://localhost:8080/v1"
LLM_MODEL_PATH = str(MODEL_DIR / "gemma-4-E2B-it-Q4_K_M.gguf")

# STT & TTS
WHISPER_MODEL_SIZE = "base.en"
PIPER_MODEL_PATH = str(MODEL_DIR / "bmo.onnx")

# Agent settings
MAX_CONVERSATION_TURNS = 5
MAX_AGENT_STEPS = 10
SYSTEM_PROMPT = "You are BMO, a helpful AI assistant." 

TOOLS: list[ChatCompletionToolUnionParam] = [
    {
        "type": "function", 
        "function": {
            "name": "get_weather",
            "description": "Get current weather for a city.",
            "parameters": {
                "type": "object",
                "properties": {
                    "city": {
                        "type": "string",
                        "description": "The city to query",
                    },
                },
                "required": ["city"],
            }
        }
    }
]


# {
#     "get_weather": {
#         "description": "Get current weather for a city.",
#         "args": {"city": "string"},
#     },
#     "calculate": {
#         "description": "Evaluate an arithmetic expression.",
#         "args": {"expression": "string  e.g. '12 * (3 + 7)'"},
#     },
#     "search_web": {
#         "description": "Search the web and return a brief summary.",
#         "args": {"query": "string"},
#     },
# }
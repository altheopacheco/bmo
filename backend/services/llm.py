from abc import ABC, abstractmethod
import asyncio
import json, concurrent.futures

from typing import AsyncGenerator, Dict, List, Literal, Optional
from openai import AsyncOpenAI
from openai.types.chat.chat_completion_chunk import ChatCompletionChunk
from openai.types.chat import ChatCompletionToolUnionParam
from llama_cpp import Llama, LlamaGrammar
from pydantic import BaseModel

class RouterDecision(BaseModel):
    action: Literal["tool", "speak", "finish"]
    name: Optional[Literal["get_weather", "calculate", "search_web"]] = None
    args: Optional[dict] = None
    
class RouterLLM(ABC):
    @abstractmethod
    async def decide_stream(self, conversation: List[Dict]) -> AsyncGenerator[str, None]:
        pass
    
    @abstractmethod
    async def health_check(self) -> bool:
        pass
    
class ResponderLLM(ABC):
    @abstractmethod
    async def generate(self, conversation: List[Dict], tools: list[ChatCompletionToolUnionParam]) -> AsyncGenerator[ChatCompletionChunk, None]:
        pass
    
    @abstractmethod
    async def health_check(self) -> bool:
        pass
    
class LlamaCPPResponder(ResponderLLM):
    def __init__(self, model: Llama, system_prompt: str):
        self.model = model
        self.system_prompt = system_prompt

    async def generate(self, conversation: List[Dict], is_final: bool) -> AsyncGenerator[str, None]:
        """Streams tokens of the generated message."""
        mode = "FINAL" if is_final else "INTERMEDIATE"
        messages = [
            {"role": "system", "content": f"{self.system_prompt}\n\nMode: {mode}"},
            *conversation
        ]
        # Run the synchronous streaming generator in a thread pool
        loop = asyncio.get_running_loop()
        # We'll use a queue to pass tokens from the sync thread to async generator
        queue: asyncio.Queue = asyncio.Queue()
        
        def stream_sync():
            try:
                for chunk in self.model.create_chat_completion(
                    messages=messages,
                    stream=True,
                    temperature=0.7,
                    max_tokens=512
                ):
                    token = chunk["choices"][0]["delta"].get("content", "")
                    if token:
                        # Put token into queue (this is called from another thread)
                        asyncio.run_coroutine_threadsafe(queue.put(token), loop)
                asyncio.run_coroutine_threadsafe(queue.put(None), loop)  # sentinel
            except Exception as e:
                asyncio.run_coroutine_threadsafe(queue.put(f"Error: {e}"), loop)
                asyncio.run_coroutine_threadsafe(queue.put(None), loop)
        
        # Start the sync streaming in a thread
        executor = concurrent.futures.ThreadPoolExecutor()
        executor.submit(stream_sync)
        try:   
            while True:
                token = await queue.get()
                if token is None:
                    break
                yield token
        finally:
            executor.shutdown(wait=False)
        
class LlamaServerResponder(ResponderLLM):
    def __init__(self, base_url: str, system_prompt: str):
        self.client = AsyncOpenAI(base_url=base_url, api_key="sk-no-key-required")
        self.system_prompt = system_prompt
        
    async def health_check(self) -> bool:
        print("[SYSTEM] Health Check: Checking LlamaCPP Server...")
        try:
            # Run the blocking call in a separate thread
            result = await asyncio.to_thread(self.client.models.list)
            print("[SYSTEM] Health Check: Server Healthy")
            return True
        except Exception as e:
            print(f"[ERROR] Responder LLM Health check failed: {e}")
            return False

    async def generate(self, conversation: List[Dict], tools: list[ChatCompletionToolUnionParam]) -> AsyncGenerator[ChatCompletionChunk, None]:
        """Streams tokens directly from the remote server."""
        stream = await self.client.chat.completions.create(
            model="local-model",
            messages=conversation,
            stream=True,
            tools=tools,
            temperature=0.7,
            max_tokens=512,
            extra_body={"reasoning_budget": 1024} 
        )

        async for chunk in stream:
            yield chunk
from abc import ABC, abstractmethod
import asyncio
import json, concurrent.futures

from typing import AsyncGenerator, Dict, Iterator, List, Literal, Optional
from openai import AsyncOpenAI
from llama_cpp import CreateChatCompletionResponse, Llama, LlamaGrammar
from pydantic import BaseModel

from config import LLAMA_SERVER_URL, ROUTER_MODEL_PATH

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
    async def generate(self, conversation: List[Dict], is_final: bool) -> AsyncGenerator[str, None]:
        pass
    
    @abstractmethod
    async def health_check(self) -> bool:
        pass

class LlamaCPPRouter(RouterLLM):
    def __init__(self, model: Llama, system_prompt: str):
        self.model = model
        self.system_prompt = system_prompt
        # Build grammar from the RouterDecision JSON schema
        schema_json = json.dumps(RouterDecision.model_json_schema())
        self.grammar = LlamaGrammar.from_json_schema(schema_json)

    async def decide(self, conversation: List[Dict]) -> RouterDecision:
        """Non‑streaming call; returns a structured decision."""
        # Run the synchronous model in a thread pool
        loop = asyncio.get_running_loop()
        
        decision_dict = await loop.run_in_executor(
            None,
            self._decide_sync,
            conversation
        )
        
        return RouterDecision.model_validate(decision_dict)

    def _decide_sync(self, conversation: List[Dict]) -> dict:
        messages = [
            {"role": "system", "content": self.system_prompt},
            *conversation
        ]
        response = self.model.create_chat_completion(
            messages=messages,
            grammar=self.grammar,
            temperature=0.0,
            max_tokens=150
        )
        
        queue: asyncio.Queue = asyncio.Queue()
        
        content = response["choices"][0]["message"]["content"]
        # Parse JSON; fallback if model adds extra text
        try:
            return json.loads(content)
        except json.JSONDecodeError:
            # Attempt to extract first JSON object
            import re
            match = re.search(r'\{.*\}', content, re.DOTALL)
            if match:
                return json.loads(match.group())
            return {"action": "finish"}   # safe fallback
    
    async def decide_stream(self, conversation: List[Dict]) -> AsyncGenerator[str, None]:
        
        loop = asyncio.get_running_loop()
        queue = asyncio.Queue()
        
        messages = [
            {"role": "system", "content": self.system_prompt},
            *conversation
        ]
        
        def decide_sync():
            try:
                for chunk in self.model.create_chat_completion(
                    messages=messages,
                    grammar=self.grammar,
                    temperature=0.0,
                    max_tokens=150,
                    stream=True
                ):
                    token = chunk["choices"][0]["delta"].get("content", "")
                    if token:
                        # Put token into queue (this is called from another thread)
                        asyncio.run_coroutine_threadsafe(queue.put(token), loop)
                asyncio.run_coroutine_threadsafe(queue.put(None), loop)  # sentinel
            except Exception as e:
                asyncio.run_coroutine_threadsafe(queue.put(e), loop)
                asyncio.run_coroutine_threadsafe(queue.put(None), loop)
        
        executor = concurrent.futures.ThreadPoolExecutor()
        executor.submit(decide_sync)
        
        try: 
            while True:
                token = await queue.get()
                if token is None:
                    break
                if isinstance(token, Exception):
                    raise token
                yield token
        finally:        
            executor.shutdown(wait=False)
                
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
        
class LlamaServerRouter(RouterLLM):
    def __init__(self, base_url: str, system_prompt: str):
        self.client = AsyncOpenAI(base_url=base_url, api_key="sk-no-key-required")
        self.system_prompt = system_prompt
        schema_json = json.dumps(RouterDecision.model_json_schema())
        self.grammar = LlamaGrammar.from_json_schema(schema_json)
        
    async def health_check(self) -> bool:
        print("[SYSTEM] Health Check: Checking LlamaCPP Server...")
        try:
            await self.client.models.list()
            print("[SYSTEM] Health Check: Server Healthy")
            return True
        except Exception as e:
            print(f"[ERROR] Router LLM Health check failed: {e}")
            return False
            
    async def decide(self, conversation: List[Dict]) -> RouterDecision:
        """Non-blocking call using native async SDK."""
        messages = [
            {"role": "system", "content": self.system_prompt},
            *conversation
        ]

        response = await self.client.chat.completions.create(
            model="local-model",
            messages=messages,
            temperature=0.0,
            max_tokens=150,
            extra_body={
                "grammar": self.grammar._grammar
            }
        )

        content = response.choices[0].message.content
        
        try:
            decision_dict = json.loads(content)
        except json.JSONDecodeError:
            import re
            match = re.search(r'\{.*\}', content, re.DOTALL)
            decision_dict = json.loads(match.group()) if match else {"action": "finish"}

        return RouterDecision.model_validate(decision_dict)

    async def decide_stream(self, conversation: List[Dict]) -> AsyncGenerator[str, None]:
        """Streams tokens directly using the SDK's async iterator."""
        messages = [
            {"role": "system", "content": self.system_prompt},
            *conversation
        ]

        stream = await self.client.chat.completions.create(
            model="local-model",
            messages=messages,
            temperature=0.0,
            max_tokens=4096,
            stream=True,
            extra_body={
                "grammar": self.grammar._grammar,
                "cache_prompt": True
            },
        )

        async for chunk in stream:
            if chunk.choices[0].finish_reason:
                print(f"\nFINISH REASON: {chunk.choices[0].finish_reason}")
            token = chunk.choices[0].delta.content
            if token:
                yield token
                
class LlamaServerResponder(ResponderLLM):
    def __init__(self, base_url: str, system_prompt: str):
        self.client = AsyncOpenAI(base_url=base_url, api_key="sk-no-key-required")
        self.system_prompt = system_prompt
        
    async def health_check(self) -> bool:
        print("[SYSTEM] Health Check: Checking LlamaCPP Server...")
        try:
            # Run the blocking call in a separate thread
            result = await asyncio.to_thread(self.client.models.list())
            print("[SYSTEM] Health Check: Server Healthy")
            return True
        except Exception as e:
            print(f"[ERROR] Responder LLM Health check failed: {e}")
            return False

    async def generate(self, conversation: List[Dict], is_final: bool) -> AsyncGenerator[str, None]:
        """Streams tokens directly from the remote server."""
        mode = "FINAL" if is_final else "INTERMEDIATE"
        
        messages = [
            {"role": "system", "content": f"{self.system_prompt}\n\nMode: {mode}"},
            *conversation
        ]

        stream = await self.client.chat.completions.create(
            model="local-model",
            messages=messages,
            stream=True,
            temperature=0.7,
            max_tokens=512
        )

        async for chunk in stream:
            # Safely extract the content delta
            if chunk.choices[0].delta.content:
                yield chunk.choices[0].delta.content
import time
from typing import Dict, Any, AsyncGenerator, Type
from openai import AsyncOpenAI
from pydantic import BaseModel
from app.orchestrator.base_provider import BaseAIProvider
from app.config import settings

class OpenAIProvider(BaseAIProvider):
    def __init__(self):
        # Initialized cleanly using credentials supplied via BaseSettings
        self.client = AsyncOpenAI(api_key=settings.OPENAI_API_KEY)

    def _map_model(self, model_tier: str) -> str:
        """
        Maps logical complexity tiers directly to explicit OpenAI models.
        """
        if model_tier == "high-tier":
            # Reserved strictly for high-stakes evaluations and readiness models
            return "gpt-4o"
        # Balanced or mid-tier uses highly efficient, low-cost options
        return "gpt-4o-mini"

    async def generate_text(
        self, 
        prompt_layers: list, 
        model_tier: str, 
        temperature: float,
        max_tokens: int
    ) -> Dict[str, Any]:
        model = self._map_model(model_tier)
        start_time = time.time()
        
        # In a real payload, prompts are concatenated down the 8-layer design pipeline
        messages = [{"role": "user", "content": "\n".join(prompt_layers)}]
        
        response = await self.client.chat.completions.create(
            model=model,
            messages=messages,
            temperature=temperature,
            max_tokens=max_tokens
        )
        
        latency_ms = int((time.time() - start_time) * 1000)
        
        # Enforce exact structural trace elements for AIModelRun compatibility
        return {
            "text": response.choices[0].message.content,
            "metadata": {
                "model_name": response.model,
                "model_version": response.system_fingerprint or "stable",
                "input_tokens": response.usage.prompt_tokens,
                "output_tokens": response.usage.completion_tokens,
                "latency_ms": latency_ms
            }
        }

    async def stream_text(
        self, 
        prompt_layers: list, 
        model_tier: str, 
        temperature: float,
        max_tokens: int
    ) -> AsyncGenerator[str, None]:
        model = self._map_model(model_tier)
        messages = [{"role": "user", "content": "\n".join(prompt_layers)}]
        
        stream = await self.client.chat.completions.create(
            model=model,
            messages=messages,
            temperature=temperature,
            max_tokens=max_tokens,
            stream=True
        )
        
        async for chunk in stream:
            if chunk.choices and chunk.choices[0].delta.content:
                yield chunk.choices[0].delta.content

    
    async def generate_structured(
        self, 
        prompt_layers: list, 
        response_model: Type[BaseModel],
        model_tier: str, 
        temperature: float
    ) -> BaseModel:
        """
        Leverages OpenAI Beta Parsing SDK to inject JSON schemas natively 
        into the V8 inference sequence.
        """
        model = self._map_model(model_tier)
        messages = [
            {
                "role": "system", 
                "content": "You are an expert CEFR language assessment generator. You must return perfectly formatted testing assets."
            },
            {"role": "user", "content": "\n".join(prompt_layers)}
        ]

        # Use beta client parse method to guarantee structure matching
        completion = await self.client.beta.chat.completions.parse(
            model=model,
            messages=messages,
            response_format=response_model,
            temperature=temperature
        )
        
        # Returns the cleanly inflated Pydantic model instance directly
        return completion.choices[0].message.parsed
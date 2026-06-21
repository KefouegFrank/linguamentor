from abc import ABC, abstractmethod
from typing import Dict, Any, AsyncGenerator, Type
from pydantic import BaseModel

class BaseAIProvider(ABC):
    """
    Mandated AI Provider Interface Layer.
    Enforces version traceability, standardized formatting schema parameters,
    and decoupling of vendor dependencies from core engine logic.
    """
    
    @abstractmethod
    async def generate_text(
        self, 
        prompt_layers: list, 
        model_tier: str, 
        temperature: float,
        max_tokens: int
    ) -> Dict[str, Any]:
        """Executes a synchronous block completion, enforcing token and metadata schemas."""
        pass

    @abstractmethod
    async def stream_text(
        self, 
        prompt_layers: list, 
        model_tier: str, 
        temperature: float,
        max_tokens: int
    ) -> AsyncGenerator[str, None]:
        """Provides raw token streaming pipelines for real-time interfaces."""
        pass

    @abstractmethod
    async def generate_structured(
        self, 
        prompt_layers: list, 
        response_model: Type[BaseModel],
        model_tier: str, 
        temperature: float
    ) -> Any:
        """
        Enforces native LLM structured parsing.
        Returns an instantiated instance of the provided response_model.
        """
        pass
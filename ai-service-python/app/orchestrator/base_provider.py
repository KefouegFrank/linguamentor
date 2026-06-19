from abc import ABC, abstractmethod
from typing import Dict, Any, AsyncGenerator

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
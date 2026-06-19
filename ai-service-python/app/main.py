import os
from fastapi import FastAPI, Depends
from fastapi.middleware.cors import CORSMiddleware
from dotenv import load_dotenv

# Preserve your exact environment bootstrap sequence
load_dotenv(dotenv_path="../../.env")

from app.config import settings
from app.orchestrator.openai_provider import OpenAIProvider

app = FastAPI(
    title=settings.PROJECT_NAME,
    description="Isolated Python engine for LLM and Audio evaluation",
    version=settings.VERSION
)

# Your standard security wrapper for cross-origin development
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Dependency Injection lifecycle provider
def get_ai_provider():
    return OpenAIProvider()

@app.get("/health")
async def health_check():
    """Unified health check preserving your database name lookup debug variable."""
    return {
        "status": "UP",
        "service": "ai-service-python",
        "environment": os.getenv("DB_NAME", "unknown"),
        "version": settings.VERSION
    }

@app.post("/api/v1/orchestrator/test-inference")
async def test_inference(prompt: str, tier: str = "mid-tier", provider: OpenAIProvider = Depends(get_ai_provider)):
    """Internal orchestration verification endpoint."""
    if settings.OPENAI_API_KEY == "mock-key-for-dev":
        return {
            "text": f"[MOCK RUN] Processed input via {tier}: {prompt}",
            "metadata": {"model_name": "mock-engine", "latency_ms": 1}
        }
        
    result = await provider.generate_text(
        prompt_layers=[prompt],
        model_tier=tier,
        temperature=0.3,
        max_tokens=100
    )
    return result

if __name__ == "__main__":
    import uvicorn
    # Respects your custom system environment variables 
    port = int(os.getenv("AI_SERVICE_PORT", 8000))
    uvicorn.run("app.main:app", host="0.0.0.0", port=port, reload=True)
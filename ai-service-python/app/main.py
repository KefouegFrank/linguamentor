import os
from fastapi import FastAPI, Depends, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from dotenv import load_dotenv

# Preserve your exact environment bootstrap sequence
load_dotenv(dotenv_path="../../.env")

from app.config import settings
from app.orchestrator.openai_provider import OpenAIProvider
from app.orchestrator.schemas import DiagnosticTemplate, InferenceRequest

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
    return {
        "status": "UP",
        "service": "ai-service-python",
        "environment": os.getenv("DB_NAME", "unknown"),
        "version": settings.VERSION
    }

@app.post("/api/v1/orchestrator/test-inference")
async def test_inference(request: InferenceRequest, provider: OpenAIProvider = Depends(get_ai_provider)):
    """Internal orchestration verification endpoint."""

    # 1. Detect if we need to run structured placement assessment templates
    if "adaptive baseline diagnostic evaluation" in request.prompt.lower():
        target_lang = "ENGLISH" if "ENGLISH" in request.prompt else "FRENCH"
        
        # Handle Local Dev Bypasses if API Key is not set up yet
        if settings.OPENAI_API_KEY == "mock-key-for-dev":
            return {
                "target_language": target_lang,
                "assumed_level": "A1",
                "grammar_test": {
                    "question": "Choose the correct verb: She ____ to school every day.",
                    "options": [{"key": "A", "text": "go"}, {"key": "B", "text": "goes"}, {"key": "C", "text": "going"}, {"key": "D", "text": "gone"}],
                    "correct_key": "B",
                    "explanation": "Third person singular subject takes a singular verb form."
                },
                "vocabulary_test": {
                    "context_sentence": "His massive vocabulary was an immense asset.",
                    "question": "What does 'immense' mean in this context?",
                    "options": [{"key": "A", "text": "Small"}, {"key": "B", "text": "Extremely large"}, {"key": "C", "text": "Weak"}, {"key": "D", "text": "Vague"}],
                    "correct_key": "B",
                    "explanation": "Immense corresponds to grand scale or huge size constraints."
                },
                "writing_test": {
                    "prompt_text": "Describe your journey learning a new language. Write at least three sentences.",
                    "evaluation_focus": ["Subject-Verb Agreement", "Vocabulary Variety", "Coherence"]
                }
            }

        # Real Live Structured Generation Call
        try:
            structured_data = await provider.generate_structured(
                prompt_layers=[request.prompt],
                response_model=DiagnosticTemplate,
                model_tier="mid-tier",
                temperature=0.5
            )
            return structured_data
        except Exception as e:
            raise HTTPException(status_code=500, detail=f"Structured generation layout failed: {str(e)}")

    # Standard fallback path for un-targeted prompts
    if settings.OPENAI_API_KEY == "mock-key-for-dev":
        return {"text": f"[MOCK RUN] Processed: {request.prompt}", "metadata": {"model_name": "mock-engine", "latency_ms": 1}}
        
    return await provider.generate_text(prompt_layers=[request.prompt], model_tier=request.tier, temperature=0.3, max_tokens=100)

if __name__ == "__main__":
    import uvicorn
    # Respects your custom system environment variables 
    port = int(os.getenv("AI_SERVICE_PORT", 8000))
    uvicorn.run("app.main:app", host="0.0.0.0", port=port, reload=True)
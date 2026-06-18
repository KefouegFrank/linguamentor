import os
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from dotenv import load_dotenv

# Load root .env file (stepping up two directories from app/main.py)
load_dotenv(dotenv_path="../../.env")

app = FastAPI(
    title="LinguaMentor AI Service",
    description="Isolated Python engine for LLM and Audio evaluation",
    version="1.0.0"
)

# Standard security wrapper for local cross-origin development
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # Restrict this in production
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

@app.get("/health")
async def health_check():
    return {
        "status": "UP",
        "service": "ai-service-python",
        "environment": os.getenv("DB_NAME", "unknown")
    }

if __name__ == "__main__":
    import uvicorn
    port = int(os.getenv("AI_SERVICE_PORT", 8000))
    uvicorn.run("app.main:app", host="0.0.0.0", port=port, reload=True)
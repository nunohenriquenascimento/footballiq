from fastapi import FastAPI

from app.api.competitions import router as competitions_router

app = FastAPI(
    title="ScoutMetrics AI",
    version="1.0.0",
)

app.include_router(competitions_router)

@app.get("/")
def root():
    return {
        "message": "ScoutMetrics AI API is running"
    }

@app.get("/health")
def health():
    return {
        "status": "healthy"
    }
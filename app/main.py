from fastapi import FastAPI

app = FastAPI(
    title="Banking Platform",
    version="0.1.0",
    docs_url="/docs",
    redoc_url="/redoc"
)

@app.get("/health")
def health_check():
    return {
        "success": True,
        "service": "banking-platform",
        "status": "healthy"
    }

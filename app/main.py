from fastapi import FastAPI, Depends
from sqlalchemy.orm import Session

from app.common.db.session import get_db
from app.config.logging import setup_logging

# Initialize logging
setup_logging()

app = FastAPI(
    title="Banking Platform",
    version="0.1.0",
    docs_url="/docs",
    redoc_url="/redoc"
)


@app.on_event("startup")
async def startup_event():
    """Initialize application on startup."""
    # Logging is already initialized via setup_logging() import
    pass


@app.on_event("shutdown")
async def shutdown_event():
    """Cleanup on application shutdown."""
    pass


# DB session dependency placeholder
# Use in route handlers like: def my_route(db: Session = Depends(get_db))
# Example:
# @app.get("/example")
# def example_route(db: Session = Depends(get_db)):
#     # Use db session here
#     pass


@app.get("/health")
def health_check():
    return {
        "success": True,
        "service": "banking-platform",
        "status": "healthy"
    }

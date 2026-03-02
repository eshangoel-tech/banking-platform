from fastapi import FastAPI, Depends, Request
from fastapi.responses import JSONResponse
from sqlalchemy.orm import Session
import asyncio
import logging
import traceback
import uuid

from app.common.logging import setup_logging
from app.repository.session import get_db, SessionLocal
from app.repository.models.error_log import ErrorLog
from app.api.middleware import HttpLoggingMiddleware

# Initialize logging
setup_logging()

app = FastAPI(
    title="ADX Bank",
    version="0.1.0",
    docs_url="/docs",
    redoc_url="/redoc",
)

# HTTP logging middleware
app.add_middleware(HttpLoggingMiddleware)


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


@app.exception_handler(Exception)
async def global_exception_handler(request: Request, exc: Exception) -> JSONResponse:
    """
    Catch-all exception handler that:
    - Captures request_id, session_id, user_id from request.state (if present)
    - Persists an ErrorLog row asynchronously
    - Returns a generic 500 error without leaking stack traces
    """
    logger = logging.getLogger("errors")

    request_id = getattr(request.state, "request_id", uuid.uuid4())
    session_id = getattr(request.state, "session_id", None)
    user_id = getattr(request.state, "user_id", None)

    async def _persist_error_log() -> None:
        def _sync_persist() -> None:
            db = SessionLocal()
            try:
                log_row = ErrorLog(
                    id=uuid.uuid4(),
                    request_id=request_id,
                    session_id=session_id,
                    user_id=user_id,
                    path=str(request.url.path),
                    method=request.method,
                    error_message=str(exc),
                    stack_trace=traceback.format_exc(),
                )
                db.add(log_row)
                db.commit()
            except Exception:
                logger.exception("Failed to persist error log")
            finally:
                db.close()

        await asyncio.to_thread(_sync_persist)

    # Fire-and-forget persistence
    asyncio.create_task(_persist_error_log())

    # Log full stack trace to application logs
    logger.exception(
        "Unhandled exception",
        extra={
            "request_id": str(request_id),
            "session_id": str(session_id) if session_id else None,
            "user_id": str(user_id) if user_id else None,
            "path": request.url.path,
            "method": request.method,
        },
    )

    return JSONResponse(
        status_code=500,
        content={
            "success": False,
            "message": "Internal server error",
            "request_id": str(request_id),
        },
    )

from fastapi import FastAPI, Depends, Request
from fastapi.responses import JSONResponse
import asyncio
import logging
import traceback
import uuid

from app.common.logging import setup_logging
from app.repository.session import get_db, AsyncSessionLocal
from app.repository.models.error_log import ErrorLog
from app.api.middleware import HttpLoggingMiddleware
from app.api.v1.core.auth.routes import router as auth_v1_router
from app.api.v1.core.user.routes import router as user_v1_router
from app.api.v1.core.transfer.routes import router as transfer_v1_router
from app.api.v1.core.wallet.routes import router as wallet_v1_router
from app.api.v1.core.loan.routes import router as loan_v1_router
from app.common.utils.exceptions import AppException

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

# API routers
app.include_router(auth_v1_router, prefix="/api/v1/auth", tags=["auth"])
app.include_router(user_v1_router, prefix="/api/v1", tags=["user"])
app.include_router(transfer_v1_router, prefix="/api/v1/transfer", tags=["transfer"])
app.include_router(wallet_v1_router, prefix="/api/v1/wallet", tags=["wallet"])
app.include_router(loan_v1_router, prefix="/api/v1/loan", tags=["loan"])


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


@app.exception_handler(AppException)
async def app_exception_handler(request: Request, exc: AppException) -> JSONResponse:
    request_id = getattr(request.state, "request_id", uuid.uuid4())
    return JSONResponse(
        status_code=exc.http_status,
        content={
            "success": False,
            "message": exc.message,
            "data": {"code": exc.code},
            "request_id": str(request_id),
        },
    )


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
        try:
            async with AsyncSessionLocal() as db:
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
                await db.commit()
        except Exception:
            logger.exception("Failed to persist error log")

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
            "data": None,
            "request_id": str(request_id),
        },
    )

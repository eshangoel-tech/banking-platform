from fastapi import FastAPI, Depends, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from fastapi.exceptions import RequestValidationError
import asyncio
import logging
import os
import traceback
import uuid

from app.common.logging import setup_logging
from app.repository.session import get_db, AsyncSessionLocal
from app.repository.models.error_log import ErrorLog
from app.api.middleware import HttpLoggingMiddleware
from app.api.v1.core.auth_routes import router as auth_v1_router
from app.api.v1.core.user_routes import router as user_v1_router
from app.api.v1.core.transfer_routes import router as transfer_v1_router
from app.api.v1.core.wallet_routes import router as wallet_v1_router
from app.api.v1.core.loan_routes import router as loan_v1_router
from app.api.v1.ai.assistant_routes import router as ai_assistant_router
from app.common.utils.exceptions import AppException
from app.services.ai.rag.vector_store import initialize_vector_store

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

# CORS — must be added after other middleware so it runs outermost
_FRONTEND_URL = os.getenv("FRONTEND_URL", "http://localhost:3000")
app.add_middleware(
    CORSMiddleware,
    allow_origins=[_FRONTEND_URL, "http://localhost:3000"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# API routers
app.include_router(auth_v1_router, prefix="/api/v1/auth", tags=["auth"])
app.include_router(user_v1_router, prefix="/api/v1", tags=["user"])
app.include_router(transfer_v1_router, prefix="/api/v1/transfer", tags=["transfer"])
app.include_router(wallet_v1_router, prefix="/api/v1/wallet", tags=["wallet"])
app.include_router(loan_v1_router, prefix="/api/v1/loan", tags=["loan"])
app.include_router(ai_assistant_router, prefix="/api/v1/ai/assistant", tags=["ai-assistant"])


logger = logging.getLogger(__name__)
_rag_ready = False


@app.on_event("startup")
async def startup_event():
    """Initialize application on startup — RAG runs in background so healthcheck passes immediately."""
    asyncio.create_task(_init_rag_background())


async def _init_rag_background():
    global _rag_ready
    try:
        loop = asyncio.get_event_loop()
        await loop.run_in_executor(None, initialize_vector_store)
        _rag_ready = True
        logger.info("RAG vector store ready.")
    except Exception:
        logger.exception("RAG initialization failed — AI assistant may not work.")


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
def health_check(request: Request):
    return {
        "success": True,
        "message": "Service is healthy.",
        "data": {
            "service": "banking-platform",
            "status": "healthy",
            "rag_ready": _rag_ready,
        },
        "request_id": str(getattr(request.state, "request_id", "")),
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


@app.exception_handler(RequestValidationError)
async def validation_exception_handler(request: Request, exc: RequestValidationError) -> JSONResponse:
    request_id = getattr(request.state, "request_id", uuid.uuid4())
    errors = exc.errors()
    # Build a readable message from the first validation error
    first = errors[0]
    field = ".".join(str(p) for p in first["loc"] if p != "body")
    message = f"{field}: {first['msg']}" if field else first["msg"]
    return JSONResponse(
        status_code=422,
        content={
            "success": False,
            "message": message,
            "data": {"code": "VALIDATION_ERROR"},
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

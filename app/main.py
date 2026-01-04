"""
Text Moderation Service - FastAPI Application

Production-ready API for text moderation with ML-powered toxicity detection.
"""

import logging
import sys
import time
from contextlib import asynccontextmanager
from typing import Dict

from fastapi import FastAPI, HTTPException, Request, Depends
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from prometheus_fastapi_instrumentator import Instrumentator

from app.config import settings
from app.models import ModerationRequest, ModerationResponse
from app.worker import start_worker, stop_worker, moderation_queue
from app.engine import engine
from app.metrics import (
    SERVICE_INFO,
    REQUESTS_TOTAL,
    QUEUE_SIZE,
    MODEL_LOADED,
)


# =============================================================================
# Logging Configuration
# =============================================================================
def setup_logging():
    """Configure logging based on settings."""
    log_level = getattr(logging, settings.LOG_LEVEL.upper(), logging.INFO)
    
    if settings.LOG_FORMAT == "json":
        # JSON format for production (better for log aggregation)
        log_format = '{"time": "%(asctime)s", "level": "%(levelname)s", "logger": "%(name)s", "message": "%(message)s"}'
    else:
        # Human-readable format for development
        log_format = "%(asctime)s - %(name)s - %(levelname)s - %(message)s"
    
    logging.basicConfig(
        level=log_level,
        format=log_format,
        handlers=[logging.StreamHandler(sys.stdout)]
    )
    
    # Reduce noise from third-party libraries
    logging.getLogger("uvicorn.access").setLevel(logging.WARNING)
    logging.getLogger("httpx").setLevel(logging.WARNING)

setup_logging()
logger = logging.getLogger(__name__)


# =============================================================================
# Rate Limiting (Simple in-memory implementation)
# =============================================================================
class RateLimiter:
    """Simple in-memory rate limiter."""
    
    def __init__(self, requests_per_minute: int = 100):
        self.requests_per_minute = requests_per_minute
        self.requests: Dict[str, list] = {}
    
    def is_allowed(self, client_ip: str) -> bool:
        """Check if request is allowed for the given IP."""
        if not settings.RATE_LIMIT_ENABLED:
            return True
            
        current_time = time.time()
        minute_ago = current_time - 60
        
        # Clean old requests
        if client_ip in self.requests:
            self.requests[client_ip] = [
                t for t in self.requests[client_ip] if t > minute_ago
            ]
        else:
            self.requests[client_ip] = []
        
        # Check limit
        if len(self.requests[client_ip]) >= self.requests_per_minute:
            return False
        
        # Record request
        self.requests[client_ip].append(current_time)
        return True

rate_limiter = RateLimiter(settings.RATE_LIMIT_PER_MINUTE)


# =============================================================================
# Security Dependencies
# =============================================================================
def get_client_ip(request: Request) -> str:
    """Extract client IP from request, considering proxies."""
    forwarded = request.headers.get("X-Forwarded-For")
    if forwarded:
        return forwarded.split(",")[0].strip()
    return request.client.host if request.client else "unknown"


async def verify_api_token(request: Request):
    """Verify API token if configured."""
    if settings.API_TOKEN:
        auth_header = request.headers.get("Authorization")
        if not auth_header:
            raise HTTPException(status_code=401, detail="Authorization header required")
        
        # Support both "Bearer <token>" and plain "<token>"
        token = auth_header.replace("Bearer ", "").strip()
        if token != settings.API_TOKEN:
            raise HTTPException(status_code=401, detail="Invalid API token")


async def check_rate_limit(request: Request):
    """Check rate limit for request."""
    if settings.RATE_LIMIT_ENABLED:
        client_ip = get_client_ip(request)
        if not rate_limiter.is_allowed(client_ip):
            raise HTTPException(
                status_code=429,
                detail="Rate limit exceeded. Please try again later."
            )


# =============================================================================
# Application Lifecycle
# =============================================================================
@asynccontextmanager
async def lifespan(app: FastAPI):
    """Application startup and shutdown lifecycle."""
    # Startup
    logger.info(f"Starting {settings.SERVICE_NAME} v{settings.SERVICE_VERSION}")
    logger.info(f"Environment: {'Development' if settings.DEBUG else 'Production'}")
    
    try:
        # Set service info metrics
        SERVICE_INFO.info({
            'version': settings.SERVICE_VERSION,
            'model_name': settings.MODEL_NAME,
            'model_backend': settings.MODEL_BACKEND,
        })
        
        # Initialize engine (loads model and wordlists)
        engine.initialize()
        MODEL_LOADED.set(1)
        
        # Start background worker
        start_worker()
        
        logger.info("Service started successfully")
        
    except Exception as e:
        logger.error(f"Startup failed: {e}")
        MODEL_LOADED.set(0)
        raise e
    
    yield
    
    # Shutdown
    logger.info("Shutting down...")
    MODEL_LOADED.set(0)
    stop_worker()
    logger.info("Service stopped")


# =============================================================================
# FastAPI Application
# =============================================================================
app = FastAPI(
    title=settings.SERVICE_NAME,
    version=settings.SERVICE_VERSION,
    description="ML-powered text moderation service with toxicity detection",
    docs_url="/docs" if settings.DEBUG else None,  # Disable in production
    redoc_url="/redoc" if settings.DEBUG else None,
    openapi_url="/openapi.json" if settings.DEBUG else None,
    lifespan=lifespan,
)


# =============================================================================
# Middleware
# =============================================================================
# CORS
app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_origins_list,
    allow_credentials=True,
    allow_methods=["GET", "POST"],
    allow_headers=["*"],
)


# Custom exception handler for better error responses
@app.exception_handler(Exception)
async def global_exception_handler(request: Request, exc: Exception):
    """Global exception handler for unhandled errors."""
    logger.error(f"Unhandled exception: {exc}", exc_info=True)
    return JSONResponse(
        status_code=500,
        content={"detail": "Internal server error"}
    )


# =============================================================================
# Prometheus Instrumentation
# =============================================================================
instrumentator = Instrumentator(
    should_group_status_codes=True,
    should_ignore_untemplated=True,
    should_respect_env_var=False,
    should_instrument_requests_inprogress=True,
    excluded_handlers=["/metrics", "/healthz", "/readyz"],
    inprogress_name="http_requests_inprogress",
    inprogress_labels=True,
)

instrumentator.instrument(app).expose(app, include_in_schema=True, tags=["monitoring"])


# =============================================================================
# API Endpoints
# =============================================================================
@app.post(
    "/moderate",
    response_model=ModerationResponse,
    tags=["moderation"],
    summary="Submit text for moderation",
    dependencies=[Depends(verify_api_token), Depends(check_rate_limit)]
)
async def moderate(request: ModerationRequest):
    """
    Submit text for asynchronous moderation.
    
    The result will be sent to the specified callback_url.
    """
    moderation_queue.put(request)
    REQUESTS_TOTAL.labels(status="queued").inc()
    QUEUE_SIZE.set(moderation_queue.qsize())
    
    logger.info(f"Request {request.id} queued for moderation")
    return ModerationResponse(status="queued", id=request.id)


@app.get("/healthz", tags=["health"], summary="Liveness probe")
async def healthz():
    """Kubernetes liveness probe - checks if process is running."""
    return {"status": "ok"}


@app.get("/readyz", tags=["health"], summary="Readiness probe")
async def readyz():
    """Kubernetes readiness probe - checks if service is ready to handle requests."""
    if engine.adapter is None:
        raise HTTPException(status_code=503, detail="Model not loaded")
    return {
        "status": "ready",
        "model_loaded": True,
        "queue_size": moderation_queue.qsize()
    }


@app.get("/metrics/queue", tags=["monitoring"], summary="Queue status")
async def queue_metrics():
    """Returns current queue status for debugging."""
    return {
        "queue_size": moderation_queue.qsize(),
        "model_loaded": engine.adapter is not None,
        "version": settings.SERVICE_VERSION
    }


# =============================================================================
# Root endpoint (for quick health check)
# =============================================================================
@app.get("/", include_in_schema=False)
async def root():
    """Root endpoint - basic service info."""
    return {
        "service": settings.SERVICE_NAME,
        "version": settings.SERVICE_VERSION,
        "status": "running"
    }

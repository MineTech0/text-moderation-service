from fastapi import FastAPI, HTTPException, BackgroundTasks
from contextlib import asynccontextmanager
import logging
from app.config import settings
from app.models import ModerationRequest, ModerationResponse
from app.worker import start_worker, stop_worker, moderation_queue
from app.engine import engine

# Setup logging
logging.basicConfig(level=logging.INFO if not settings.DEBUG else logging.DEBUG)
logger = logging.getLogger(__name__)

@asynccontextmanager
async def lifespan(app: FastAPI):
    # Startup
    logger.info("Starting up...")
    try:
        engine.initialize()
        start_worker()
    except Exception as e:
        logger.error(f"Startup failed: {e}")
        raise e
    
    yield
    
    # Shutdown
    logger.info("Shutting down...")
    stop_worker()

app = FastAPI(
    title=settings.SERVICE_NAME,
    lifespan=lifespan
)

@app.post("/moderate", response_model=ModerationResponse)
async def moderate(request: ModerationRequest):
    moderation_queue.put(request)
    return ModerationResponse(status="queued", id=request.id)

@app.get("/healthz")
async def healthz():
    return {"status": "ok"}

@app.get("/readyz")
async def readyz():
    if engine.adapter is None:
        raise HTTPException(status_code=503, detail="Model not loaded")
    return {"status": "ready"}


import queue
import threading
import time
import requests
import logging
from app.config import settings
from app.models import ModerationRequest, CallbackPayload
from app.engine import engine
from app.metrics import (
    REQUESTS_TOTAL,
    QUEUE_SIZE,
    PROCESSING_TIME,
    DECISIONS_TOTAL,
    BADWORD_DETECTIONS,
    TOXICITY_SCORE,
    CALLBACKS_TOTAL,
    CALLBACK_RETRIES,
    CALLBACK_LATENCY,
)

logger = logging.getLogger(__name__)

# Global queue
moderation_queue = queue.Queue()

def process_queue():
    """Worker loop."""
    logger.info("Worker thread started.")
    while True:
        try:
            # Blocking get
            item = moderation_queue.get()
            if item is None:
                # Sentinel to stop
                break
            
            # Update queue size metric
            QUEUE_SIZE.set(moderation_queue.qsize())
            
            process_request(item)
            moderation_queue.task_done()
            
            # Update queue size after processing
            QUEUE_SIZE.set(moderation_queue.qsize())
        except Exception as e:
            logger.error(f"Error in worker loop: {e}")
            REQUESTS_TOTAL.labels(status="failed").inc()

def process_request(request: ModerationRequest):
    start_time = time.perf_counter()
    try:
        logger.info(f"Processing request {request.id}")
        result = engine.moderate(request)
        
        # Record processing time
        processing_duration = time.perf_counter() - start_time
        PROCESSING_TIME.observe(processing_duration)
        
        # Record decision metrics
        DECISIONS_TOTAL.labels(decision=result.decision).inc()
        TOXICITY_SCORE.observe(result.reason.toxicity_score)
        
        if result.reason.badword:
            BADWORD_DETECTIONS.inc()
        
        REQUESTS_TOTAL.labels(status="processed").inc()
        
        send_callback(request.callback_url, result)
    except Exception as e:
        logger.error(f"Failed to process request {request.id}: {e}")
        REQUESTS_TOTAL.labels(status="failed").inc()

def send_callback(url: str, payload: CallbackPayload):
    payload_dict = payload.model_dump(mode="json")
    
    for attempt in range(settings.MAX_RETRIES):
        callback_start = time.perf_counter()
        try:
            response = requests.post(str(url), json=payload_dict, timeout=10)
            callback_duration = time.perf_counter() - callback_start
            CALLBACK_LATENCY.observe(callback_duration)
            
            if 200 <= response.status_code < 300:
                logger.info(f"Callback successful for {payload.id}")
                CALLBACKS_TOTAL.labels(status="success").inc()
                return
            else:
                logger.warning(f"Callback failed for {payload.id} (status {response.status_code}). Attempt {attempt + 1}/{settings.MAX_RETRIES}")
                if attempt < settings.MAX_RETRIES - 1:
                    CALLBACK_RETRIES.inc()
        except Exception as e:
            callback_duration = time.perf_counter() - callback_start
            CALLBACK_LATENCY.observe(callback_duration)
            logger.warning(f"Callback exception for {payload.id}: {e}. Attempt {attempt + 1}/{settings.MAX_RETRIES}")
            if attempt < settings.MAX_RETRIES - 1:
                CALLBACK_RETRIES.inc()
        
        # Backoff
        time.sleep(settings.RETRY_BACKOFF_FACTOR ** attempt)
    
    logger.error(f"All callback attempts failed for {payload.id}")
    CALLBACKS_TOTAL.labels(status="failed").inc()

def start_worker():
    t = threading.Thread(target=process_queue, daemon=True)
    t.start()
    return t

def stop_worker():
    moderation_queue.put(None)

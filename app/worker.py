import queue
import threading
import time
import requests
import logging
from app.config import settings
from app.models import ModerationRequest, CallbackPayload
from app.engine import engine

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
            
            process_request(item)
            moderation_queue.task_done()
        except Exception as e:
            logger.error(f"Error in worker loop: {e}")

def process_request(request: ModerationRequest):
    try:
        logger.info(f"Processing request {request.id}")
        result = engine.moderate(request)
        send_callback(request.callback_url, result)
    except Exception as e:
        logger.error(f"Failed to process request {request.id}: {e}")

def send_callback(url: str, payload: CallbackPayload):
    payload_dict = payload.model_dump(mode="json")
    
    for attempt in range(settings.MAX_RETRIES):
        try:
            response = requests.post(str(url), json=payload_dict, timeout=10)
            if 200 <= response.status_code < 300:
                logger.info(f"Callback successful for {payload.id}")
                return
            else:
                logger.warning(f"Callback failed for {payload.id} (status {response.status_code}). Attempt {attempt + 1}/{settings.MAX_RETRIES}")
        except Exception as e:
            logger.warning(f"Callback exception for {payload.id}: {e}. Attempt {attempt + 1}/{settings.MAX_RETRIES}")
        
        # Backoff
        time.sleep(settings.RETRY_BACKOFF_FACTOR ** attempt)
    
    logger.error(f"All callback attempts failed for {payload.id}")

def start_worker():
    t = threading.Thread(target=process_queue, daemon=True)
    t.start()
    return t

def stop_worker():
    moderation_queue.put(None)


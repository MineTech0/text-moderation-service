"""
Prometheus metrics for the Text Moderation Service.

Custom metrics for monitoring inference performance, queue status,
and moderation decisions.
"""

from prometheus_client import Counter, Histogram, Gauge, Info

# Service info
SERVICE_INFO = Info(
    'moderation_service',
    'Information about the moderation service'
)

# Request metrics
REQUESTS_TOTAL = Counter(
    'moderation_requests_total',
    'Total number of moderation requests received',
    ['status']  # queued, processed, failed
)

# Queue metrics
QUEUE_SIZE = Gauge(
    'moderation_queue_size',
    'Current number of items in the moderation queue'
)

# Processing metrics
PROCESSING_TIME = Histogram(
    'moderation_processing_seconds',
    'Time spent processing a moderation request',
    buckets=[0.01, 0.05, 0.1, 0.25, 0.5, 1.0, 2.5, 5.0, 10.0]
)

INFERENCE_TIME = Histogram(
    'moderation_inference_seconds',
    'Time spent on ML model inference only',
    buckets=[0.01, 0.05, 0.1, 0.25, 0.5, 1.0, 2.5, 5.0]
)

WORDLIST_CHECK_TIME = Histogram(
    'moderation_wordlist_check_seconds',
    'Time spent checking wordlists',
    buckets=[0.0001, 0.0005, 0.001, 0.005, 0.01, 0.05]
)

# Decision metrics
DECISIONS_TOTAL = Counter(
    'moderation_decisions_total',
    'Total moderation decisions by type',
    ['decision']  # allow, flag, block
)

BADWORD_DETECTIONS = Counter(
    'moderation_badword_detections_total',
    'Total number of badword detections'
)

# Toxicity score distribution
TOXICITY_SCORE = Histogram(
    'moderation_toxicity_score',
    'Distribution of toxicity scores',
    buckets=[0.0, 0.1, 0.2, 0.3, 0.4, 0.5, 0.6, 0.7, 0.8, 0.9, 1.0]
)

# Callback metrics
CALLBACKS_TOTAL = Counter(
    'moderation_callbacks_total',
    'Total callback attempts',
    ['status']  # success, failed
)

CALLBACK_RETRIES = Counter(
    'moderation_callback_retries_total',
    'Total number of callback retries'
)

CALLBACK_LATENCY = Histogram(
    'moderation_callback_latency_seconds',
    'Time spent sending callbacks',
    buckets=[0.01, 0.05, 0.1, 0.25, 0.5, 1.0, 2.5, 5.0, 10.0]
)

# Model metrics
MODEL_LOADED = Gauge(
    'moderation_model_loaded',
    'Whether the ML model is loaded (1) or not (0)'
)

WORDLISTS_LOADED = Gauge(
    'moderation_wordlists_loaded',
    'Number of wordlists loaded'
)

WORDLIST_ENTRIES = Gauge(
    'moderation_wordlist_entries_total',
    'Total number of entries across all wordlists'
)


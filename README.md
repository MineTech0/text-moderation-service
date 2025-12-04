# Text Moderation Service

A lightweight, production-ready text moderation service designed to run on CPU-only environments. It combines high-performance wordlist filtering (Finnish & English) with a pluggable machine learning toxicity model.

## Features

*   **Dual-layer Filtering**:
    *   **Wordlist Filter**: Fast, rule-based filtering with normalization (leet speak handling, repetition removal). Automatically downloads/updates lists.
    *   **ML Model**: Toxicity classification using Hugging Face transformers (default: `TurkuNLP/bert-large-finnish-cased-toxicity`).
*   **Asynchronous Processing**: Immediate API response; heavy lifting happens in a background worker queue.
*   **Callback Architecture**: Results are delivered via HTTP POST to a specified callback URL.
*   **Production Ready**: Dockerized, non-root user, healthchecks, retry logic, and structured logging.
*   **Configurable**: Easy to swap models or adjust sensitivity thresholds via environment variables.

## Quick Start with Docker

1.  **Build the image:**

    ```bash
    docker build -t moderation-service .
    ```

2.  **Run the container:**

    ```bash
    mkdir -p data && chmod 777 data
    docker run -d \
      -p 8000:8000 \
      --name moderation-service \
      -v $(pwd)/data:/app/data \
      -v moderation_model_cache:/app/model_cache \
      moderation-service
    ```

    *   Port 8000 is exposed.
    *   `./data` volume persists downloaded wordlists.
    *   `model_cache` volume prevents re-downloading the ML model on every restart.

## API Documentation

### 1. Submit Text for Moderation

**Endpoint:** `POST /moderate`

Queues a text for moderation. Returns immediately.

**Request:**

```json
{
  "id": "msg_12345",
  "text": "This is a test message to check moderation.",
  "callback_url": "https://your-api.com/moderation-callback"
}
```

**Response (200 OK):**

```json
{
  "status": "queued",
  "id": "msg_12345"
}
```

### 2. Receive Moderation Result (Callback)

The service will send a `POST` request to your `callback_url`.

**Payload:**

```json
{
  "id": "msg_12345",
  "text": "This is a test message to check moderation.",
  "decision": "allow",
  "reason": {
    "badword": false,
    "toxicity_score": 0.05,
    "model_label": "neutral"
  }
}
```

*   **decision**: `allow`, `flag`, or `block`.
*   **reason.badword**: `true` if it hit the hardcoded blocklist.
*   **reason.toxicity_score**: 0.0 - 1.0 (higher is more toxic).

### 3. Health Checks

*   `GET /healthz`: Liveness probe (returns 200 if process is running).
*   `GET /readyz`: Readiness probe (returns 200 if model and wordlists are loaded).

## Configuration

You can configure the service using environment variables.

| Variable | Default | Description |
| :--- | :--- | :--- |
| `SERVICE_NAME` | Text Moderation Service | Name of the service. |
| `DEBUG` | False | Enable debug logging. |
| `MODEL_BACKEND` | huggingface_pipeline | Backend to use. |
| `MODEL_NAME` | TurkuNLP/bert-large-finnish-cased-toxicity | Hugging Face model ID. |
| `MODEL_DEVICE` | -1 | `-1` for CPU, `0` for GPU. |
| `WORDLIST_REFRESH_DAYS` | 7 | How often to re-download wordlists (days). |
| `TRIVIAL_LENGTH_THRESHOLD`| 2 | Texts shorter than this are automatically allowed. |
| `BLOCK_THRESHOLD` | 0.9 | Score > 0.9 = block. |
| `FLAG_THRESHOLD` | 0.7 | Score > 0.7 = flag. |
| `MAX_RETRIES` | 3 | Number of callback retries. |
| `RETRY_BACKOFF_FACTOR` | 1.5 | Multiplier for backoff delay. |

## Local Development

1.  **Install dependencies:**

    ```bash
    pip install -r requirements.txt
    ```

2.  **Run the application:**

    ```bash
    uvicorn app.main:app --reload --port 8000
    ```

## Architecture

1.  **FastAPI** receives the request and pushes it to an internal `queue.Queue`.
2.  **Background Worker** thread pulls requests from the queue.
3.  **Moderation Engine**:
    *   Checks for triviality (length).
    *   Checks normalized text against `badwords_fi.txt` and `badwords_en.txt` (loaded into memory).
    *   Runs the text through the Hugging Face Pipeline.
4.  **Callback**: The result is posted back to the client's URL.

## Security

*   The Docker image runs as a non-root user (`appuser`).
*   Dependencies are pinned and minimal.
*   No input text is logged by default in production mode.


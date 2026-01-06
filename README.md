# Text Moderation Service

A production-ready, ML-powered text moderation service designed for CPU-only environments. It combines high-performance wordlist filtering (Finnish & English) with a transformer-based toxicity model.

## Features

- **Dual-layer Filtering**:
  - **Wordlist Filter**: Fast, rule-based filtering with normalization (leet speak handling, repetition removal)
  - **ML Model**: Toxicity classification using Hugging Face transformers (default: `TurkuNLP/bert-large-finnish-cased-toxicity`)
- **Asynchronous Processing**: Immediate API response; heavy lifting happens in a background worker queue
- **Callback Architecture**: Results are delivered via HTTP POST to a specified callback URL
- **Production Ready**: Multi-stage Docker build, non-root user, health checks, rate limiting, CORS
- **Monitoring**: Built-in Prometheus metrics and Grafana dashboards
- **Configurable**: All settings via environment variables

## Quick Start

### Local Development

```bash
# Install dependencies
pip install -r requirements.txt

# Run the application
uvicorn app.main:app --reload --port 8000
```

### Docker (Development)

```bash
# Build and run with monitoring stack
docker compose up -d

# Access points:
# - API:        http://localhost:8000
# - Prometheus: http://localhost:9090
# - Grafana:    http://localhost:3000 (admin/moderation123)
```

---

## 🚀 Coolify Deployment

### Deploy via Docker Compose

1. **In Coolify**, create a new service:
   - Select **"Docker Compose"**
   - Connect your Git repository

2. **Set the compose file** to `docker-compose.prod.yml`

3. **Coolify Magic Variables** (auto-generated):

   | Variable | Description |
   |----------|-------------|
   | `SERVICE_FQDN_GRAFANA_3000` | Grafana dashboard URL (only external service) |
   | `SERVICE_PASSWORD_GRAFANA` | Grafana admin password |

4. **Optional overrides** (set in Coolify UI if needed):

   | Variable | Default | Description |
   |----------|---------|-------------|
   | `API_TOKEN` | _(empty)_ | API authentication token |
   | `CORS_ORIGINS` | `*` | Allowed origins |
   | `MODEL_NAME` | TurkuNLP/bert-large-finnish-cased-toxicity | HuggingFace model |

5. **Deploy** and wait for the model to download (~2-3 min on first start)

### Service Architecture

```
Internet
    │
    ▼
┌─────────────────────────────────────────────────┐
│  Coolify (Reverse Proxy)                        │
└─────────────────────────────────────────────────┘
    │
    ▼ Only Grafana exposed
┌─────────────────────────────────────────────────┐
│  grafana:3000  ◄── SERVICE_FQDN_GRAFANA_3000   │
│       │                                         │
│       ▼                                         │
│  prometheus:9090  (internal)                    │
│       │                                         │
│       ▼                                         │
│  moderation-service:8000  (internal)            │
│  node-exporter:9100  (internal)                 │
└─────────────────────────────────────────────────┘
```

**Grafana password** is shown in Coolify UI → Environment Variables.

### Option 2: Deploy Service Only

If you only need the moderation API (without monitoring):

```bash
docker build -t moderation-service .
docker run -d \
  -p 8000:8000 \
  -e API_TOKEN=your-secret-token \
  -e CORS_ORIGINS=https://your-app.com \
  -v moderation_data:/app/data \
  -v moderation_model_cache:/app/model_cache \
  moderation-service
```

### Coolify Network & Ports

Coolify automatically manages:
- ✅ **Reverse proxy** with SSL/TLS for Grafana
- ✅ **Internal networking** between all services
- ✅ **No manual port exposure needed**

| Service | Internal Address | External |
|---------|------------------|----------|
| `moderation-service` | `moderation-service:8000` | ❌ Internal only |
| `prometheus` | `prometheus:9090` | ❌ Internal only |
| `grafana` | `grafana:3000` | ✅ Via SERVICE_FQDN |
| `node-exporter` | `node-exporter:9100` | ❌ Internal only |

---

## API Documentation

### 1. Submit Text for Moderation

**Endpoint:** `POST /moderate`

**Headers:**
```
Authorization: Bearer <your-api-token>  # If API_TOKEN is set
Content-Type: application/json
```

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

### 2. Callback Payload

The service sends a `POST` request to your `callback_url`:

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

**Decisions:**
- `allow` - Content is safe
- `flag` - Content needs review (score > FLAG_THRESHOLD)
- `block` - Content should be blocked (score > BLOCK_THRESHOLD or badword detected)

### 3. Health Checks

| Endpoint | Purpose |
|----------|---------|
| `GET /healthz` | Liveness probe (process running) |
| `GET /readyz` | Readiness probe (model loaded) |
| `GET /metrics` | Prometheus metrics |

---

## Configuration

All settings can be configured via environment variables:

### Application Settings

| Variable | Default | Description |
|----------|---------|-------------|
| `SERVICE_NAME` | Text Moderation Service | Service name |
| `DEBUG` | `false` | Enable debug mode |
| `LOG_LEVEL` | `INFO` | Log level (DEBUG, INFO, WARNING, ERROR) |
| `LOG_FORMAT` | `json` | Log format (`json` or `text`) |

### Model Settings

| Variable | Default | Description |
|----------|---------|-------------|
| `MODEL_NAME` | `TurkuNLP/bert-large-finnish-cased-toxicity` | HuggingFace model |
| `MODEL_DEVICE` | `-1` | Device (`-1` for CPU, `0`+ for GPU) |

### Moderation Thresholds

| Variable | Default | Description |
|----------|---------|-------------|
| `BLOCK_THRESHOLD` | `0.9` | Score above this = block |
| `FLAG_THRESHOLD` | `0.7` | Score above this = flag |
| `TRIVIAL_LENGTH_THRESHOLD` | `2` | Texts shorter = auto-allow |

### Security

| Variable | Default | Description |
|----------|---------|-------------|
| `API_TOKEN` | _(empty)_ | Required token for API access |
| `CORS_ORIGINS` | `*` | Comma-separated allowed origins |
| `RATE_LIMIT_ENABLED` | `true` | Enable rate limiting |
| `RATE_LIMIT_PER_MINUTE` | `100` | Max requests per IP per minute |

---

## Monitoring

### Available Metrics

| Metric | Type | Description |
|--------|------|-------------|
| `moderation_requests_total` | Counter | Total requests by status |
| `moderation_queue_size` | Gauge | Current queue size |
| `moderation_processing_seconds` | Histogram | Processing time |
| `moderation_inference_seconds` | Histogram | ML inference time |
| `moderation_decisions_total` | Counter | Decisions by type |
| `moderation_toxicity_score` | Histogram | Score distribution |
| `moderation_callbacks_total` | Counter | Callback attempts |

### Pre-configured Alerts

- Service down
- High queue size (>100 items)
- High error rate (>10%)
- Slow inference (p95 > 2s)
- High callback failure rate (>20%)
- High CPU/Memory usage (>80%)

### Grafana Dashboard

The included dashboard provides:
- **Overview**: Status, queue size, latency, request rate
- **Inference Performance**: ML latency percentiles
- **Decisions**: Allow/flag/block distribution
- **System Resources**: CPU, memory, disk, network

---

## Architecture

```
┌─────────────┐    ┌─────────────┐    ┌─────────────┐
│   Client    │───▶│   FastAPI   │───▶│    Queue    │
└─────────────┘    └─────────────┘    └─────────────┘
                          │                   │
                          ▼                   ▼
                   ┌─────────────┐    ┌─────────────┐
                   │  /metrics   │    │   Worker    │
                   └─────────────┘    └─────────────┘
                          │                   │
                          ▼                   ▼
                   ┌─────────────┐    ┌─────────────┐
                   │ Prometheus  │    │   Engine    │
                   └─────────────┘    └─────────────┘
                          │                   │
                          ▼                   ├──▶ Wordlist Filter
                   ┌─────────────┐           │
                   │   Grafana   │           └──▶ ML Model (BERT)
                   └─────────────┘                    │
                                                      ▼
                                              ┌─────────────┐
                                              │  Callback   │
                                              └─────────────┘
```

---

## Security

- **Non-root user**: Docker image runs as `appuser` (UID 1000)
- **API Authentication**: Optional Bearer token
- **Rate Limiting**: Configurable per-IP limits
- **CORS**: Configurable allowed origins
- **No sensitive logging**: Text content not logged in production
- **Health checks**: Kubernetes-compatible probes

---

## Development

### Project Structure

```
text-moderation-service/
├── app/
│   ├── main.py          # FastAPI application
│   ├── config.py        # Settings
│   ├── models.py        # Pydantic models
│   ├── engine.py        # Moderation logic
│   ├── worker.py        # Background worker
│   ├── wordlist.py      # Wordlist handling
│   ├── adapters.py      # ML model adapters
│   └── metrics.py       # Prometheus metrics
├── monitoring/
│   ├── prometheus/
│   │   ├── Dockerfile       # Custom image with config
│   │   ├── prometheus.yml
│   │   └── alerts.yml
│   └── grafana/
│       ├── Dockerfile       # Custom image with dashboards
│       ├── dashboards/
│       └── provisioning/
├── docker-compose.yml       # Development (with mounts)
├── docker-compose.prod.yml  # Production/Coolify (no mounts)
├── Dockerfile
├── requirements.txt
└── env.example
```

### Running Tests

```bash
python test_script.py
```

---

## License

MIT

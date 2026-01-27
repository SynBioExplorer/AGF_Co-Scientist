# Phase 5F: Observability & Monitoring

## Overview

Implement observability infrastructure including metrics, logging, tracing, and alerting for production monitoring.

**Branch:** `phase5/observability`
**Worktree:** `worktree-5f-observability`
**Dependencies:** None (standalone)
**Estimated Duration:** 0.5 weeks

## Stack

| Component | Technology |
|-----------|------------|
| Metrics | Prometheus |
| Visualization | Grafana |
| Logging | Structured JSON (structlog) |
| Tracing | OpenTelemetry (optional) |
| Alerting | Grafana Alerts / CloudWatch |

## Deliverables

### Files to Create

```
src/
├── observability/
│   ├── __init__.py
│   ├── metrics.py             # Prometheus metrics
│   ├── logging.py             # Enhanced logging
│   └── tracing.py             # OpenTelemetry setup

monitoring/
├── prometheus/
│   └── prometheus.yml         # Prometheus config
├── grafana/
│   ├── provisioning/
│   │   └── dashboards/
│   │       └── coscientist.json
│   └── grafana.ini
└── docker-compose.monitoring.yml

tests/
└── test_metrics.py
```

### 1. Prometheus Metrics (`src/observability/metrics.py`)

```python
from prometheus_client import Counter, Histogram, Gauge, Info
from prometheus_client import generate_latest, CONTENT_TYPE_LATEST
from fastapi import Response
import time
from functools import wraps

# Application info
app_info = Info('coscientist', 'AI Co-Scientist application info')
app_info.info({
    'version': '1.0.0',
    'phase': '5'
})

# Request metrics
http_requests_total = Counter(
    'http_requests_total',
    'Total HTTP requests',
    ['method', 'endpoint', 'status']
)

http_request_duration_seconds = Histogram(
    'http_request_duration_seconds',
    'HTTP request duration in seconds',
    ['method', 'endpoint'],
    buckets=[0.01, 0.05, 0.1, 0.25, 0.5, 1.0, 2.5, 5.0, 10.0]
)

# Agent metrics
agent_executions_total = Counter(
    'agent_executions_total',
    'Total agent executions',
    ['agent_type', 'status']
)

agent_execution_duration_seconds = Histogram(
    'agent_execution_duration_seconds',
    'Agent execution duration in seconds',
    ['agent_type'],
    buckets=[1.0, 5.0, 10.0, 30.0, 60.0, 120.0, 300.0]
)

# Hypothesis metrics
hypotheses_generated_total = Counter(
    'hypotheses_generated_total',
    'Total hypotheses generated',
    ['research_goal_id']
)

hypotheses_active = Gauge(
    'hypotheses_active',
    'Number of active hypotheses',
    ['research_goal_id', 'status']
)

hypothesis_elo_rating = Gauge(
    'hypothesis_elo_rating',
    'Current Elo rating of hypothesis',
    ['hypothesis_id']
)

# Tournament metrics
tournament_matches_total = Counter(
    'tournament_matches_total',
    'Total tournament matches',
    ['research_goal_id']
)

tournament_convergence_score = Gauge(
    'tournament_convergence_score',
    'Tournament convergence score',
    ['research_goal_id']
)

# LLM metrics
llm_requests_total = Counter(
    'llm_requests_total',
    'Total LLM API requests',
    ['provider', 'model', 'status']
)

llm_tokens_total = Counter(
    'llm_tokens_total',
    'Total LLM tokens used',
    ['provider', 'model', 'direction']  # direction: input/output
)

llm_cost_aud_total = Counter(
    'llm_cost_aud_total',
    'Total LLM cost in AUD',
    ['provider', 'model']
)

llm_request_duration_seconds = Histogram(
    'llm_request_duration_seconds',
    'LLM request duration in seconds',
    ['provider', 'model'],
    buckets=[0.5, 1.0, 2.0, 5.0, 10.0, 30.0, 60.0]
)

# Budget metrics
budget_remaining_aud = Gauge(
    'budget_remaining_aud',
    'Remaining budget in AUD'
)

budget_used_aud = Gauge(
    'budget_used_aud',
    'Used budget in AUD'
)

# Queue metrics
task_queue_size = Gauge(
    'task_queue_size',
    'Number of tasks in queue',
    ['status']  # pending, running, completed, failed
)

# Decorators for automatic metric collection
def track_request(endpoint: str):
    """Decorator to track HTTP request metrics."""
    def decorator(func):
        @wraps(func)
        async def wrapper(*args, **kwargs):
            start_time = time.time()
            status = "success"
            try:
                result = await func(*args, **kwargs)
                return result
            except Exception as e:
                status = "error"
                raise
            finally:
                duration = time.time() - start_time
                http_requests_total.labels(
                    method="POST",
                    endpoint=endpoint,
                    status=status
                ).inc()
                http_request_duration_seconds.labels(
                    method="POST",
                    endpoint=endpoint
                ).observe(duration)
        return wrapper
    return decorator

def track_agent_execution(agent_type: str):
    """Decorator to track agent execution metrics."""
    def decorator(func):
        @wraps(func)
        async def wrapper(*args, **kwargs):
            start_time = time.time()
            status = "success"
            try:
                result = await func(*args, **kwargs)
                return result
            except Exception as e:
                status = "error"
                raise
            finally:
                duration = time.time() - start_time
                agent_executions_total.labels(
                    agent_type=agent_type,
                    status=status
                ).inc()
                agent_execution_duration_seconds.labels(
                    agent_type=agent_type
                ).observe(duration)
        return wrapper
    return decorator

def track_llm_request(provider: str, model: str):
    """Decorator to track LLM request metrics."""
    def decorator(func):
        @wraps(func)
        async def wrapper(*args, **kwargs):
            start_time = time.time()
            status = "success"
            try:
                result = await func(*args, **kwargs)
                return result
            except Exception as e:
                status = "error"
                raise
            finally:
                duration = time.time() - start_time
                llm_requests_total.labels(
                    provider=provider,
                    model=model,
                    status=status
                ).inc()
                llm_request_duration_seconds.labels(
                    provider=provider,
                    model=model
                ).observe(duration)
        return wrapper
    return decorator

# FastAPI endpoint for Prometheus scraping
async def metrics_endpoint():
    """Prometheus metrics endpoint."""
    return Response(
        content=generate_latest(),
        media_type=CONTENT_TYPE_LATEST
    )
```

### 2. Enhanced Logging (`src/observability/logging.py`)

```python
import structlog
import logging
import sys
from typing import Any
from datetime import datetime

def setup_logging(
    level: str = "INFO",
    json_format: bool = True,
    include_timestamp: bool = True
):
    """Configure structured logging."""

    # Processors for structlog
    processors = [
        structlog.stdlib.filter_by_level,
        structlog.stdlib.add_logger_name,
        structlog.stdlib.add_log_level,
        structlog.stdlib.PositionalArgumentsFormatter(),
        structlog.processors.TimeStamper(fmt="iso"),
        structlog.processors.StackInfoRenderer(),
        structlog.processors.format_exc_info,
        structlog.processors.UnicodeDecoder(),
    ]

    if json_format:
        processors.append(structlog.processors.JSONRenderer())
    else:
        processors.append(structlog.dev.ConsoleRenderer())

    structlog.configure(
        processors=processors,
        wrapper_class=structlog.stdlib.BoundLogger,
        context_class=dict,
        logger_factory=structlog.stdlib.LoggerFactory(),
        cache_logger_on_first_use=True,
    )

    # Configure stdlib logging
    logging.basicConfig(
        format="%(message)s",
        stream=sys.stdout,
        level=getattr(logging, level.upper()),
    )

def get_logger(name: str) -> structlog.stdlib.BoundLogger:
    """Get a structured logger."""
    return structlog.get_logger(name)

# Context managers for request tracking
class LogContext:
    """Context manager for adding context to logs."""

    def __init__(self, **kwargs):
        self.context = kwargs
        self.logger = get_logger(__name__)

    def __enter__(self):
        structlog.contextvars.bind_contextvars(**self.context)
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        structlog.contextvars.unbind_contextvars(*self.context.keys())

# Logging utilities
def log_agent_execution(
    agent_type: str,
    research_goal_id: str,
    duration_seconds: float,
    success: bool,
    **extra
):
    """Log agent execution with structured data."""
    logger = get_logger("agent")
    log_method = logger.info if success else logger.error

    log_method(
        "agent_execution",
        agent_type=agent_type,
        research_goal_id=research_goal_id,
        duration_seconds=duration_seconds,
        success=success,
        **extra
    )

def log_llm_request(
    provider: str,
    model: str,
    input_tokens: int,
    output_tokens: int,
    cost_aud: float,
    duration_seconds: float,
    **extra
):
    """Log LLM request with structured data."""
    logger = get_logger("llm")
    logger.info(
        "llm_request",
        provider=provider,
        model=model,
        input_tokens=input_tokens,
        output_tokens=output_tokens,
        cost_aud=cost_aud,
        duration_seconds=duration_seconds,
        **extra
    )

def log_hypothesis_created(
    hypothesis_id: str,
    research_goal_id: str,
    title: str,
    method: str
):
    """Log hypothesis creation."""
    logger = get_logger("hypothesis")
    logger.info(
        "hypothesis_created",
        hypothesis_id=hypothesis_id,
        research_goal_id=research_goal_id,
        title=title,
        generation_method=method
    )

def log_tournament_match(
    match_id: str,
    hypothesis_a_id: str,
    hypothesis_b_id: str,
    winner_id: str,
    elo_change: float
):
    """Log tournament match result."""
    logger = get_logger("tournament")
    logger.info(
        "tournament_match",
        match_id=match_id,
        hypothesis_a_id=hypothesis_a_id,
        hypothesis_b_id=hypothesis_b_id,
        winner_id=winner_id,
        elo_change=elo_change
    )
```

### 3. Prometheus Configuration (`monitoring/prometheus/prometheus.yml`)

```yaml
global:
  scrape_interval: 15s
  evaluation_interval: 15s

alerting:
  alertmanagers:
    - static_configs:
        - targets: []

rule_files:
  - "alerts.yml"

scrape_configs:
  - job_name: 'coscientist'
    static_configs:
      - targets: ['host.docker.internal:8000']
    metrics_path: '/metrics'

  - job_name: 'prometheus'
    static_configs:
      - targets: ['localhost:9090']
```

### 4. Alert Rules (`monitoring/prometheus/alerts.yml`)

```yaml
groups:
  - name: coscientist_alerts
    rules:
      # High error rate
      - alert: HighErrorRate
        expr: rate(http_requests_total{status="error"}[5m]) > 0.1
        for: 2m
        labels:
          severity: warning
        annotations:
          summary: High error rate detected
          description: Error rate is {{ $value | printf "%.2f" }} requests/sec

      # Budget running low
      - alert: BudgetLow
        expr: budget_remaining_aud < 5
        for: 1m
        labels:
          severity: warning
        annotations:
          summary: Budget running low
          description: Only ${{ $value | printf "%.2f" }} AUD remaining

      # Budget exhausted
      - alert: BudgetExhausted
        expr: budget_remaining_aud <= 0
        for: 1m
        labels:
          severity: critical
        annotations:
          summary: Budget exhausted
          description: No budget remaining

      # Agent taking too long
      - alert: SlowAgentExecution
        expr: histogram_quantile(0.95, rate(agent_execution_duration_seconds_bucket[5m])) > 300
        for: 5m
        labels:
          severity: warning
        annotations:
          summary: Agent executions are slow
          description: 95th percentile agent execution time is {{ $value | printf "%.0f" }} seconds

      # LLM API errors
      - alert: LLMAPIErrors
        expr: rate(llm_requests_total{status="error"}[5m]) > 0.05
        for: 2m
        labels:
          severity: warning
        annotations:
          summary: LLM API errors detected
          description: LLM error rate is {{ $value | printf "%.3f" }} requests/sec

      # Queue buildup
      - alert: TaskQueueBacklog
        expr: task_queue_size{status="pending"} > 50
        for: 5m
        labels:
          severity: warning
        annotations:
          summary: Task queue backlog
          description: {{ $value }} pending tasks in queue
```

### 5. Grafana Dashboard (`monitoring/grafana/provisioning/dashboards/coscientist.json`)

```json
{
  "dashboard": {
    "id": null,
    "title": "AI Co-Scientist Dashboard",
    "tags": ["coscientist"],
    "timezone": "browser",
    "panels": [
      {
        "title": "Request Rate",
        "type": "graph",
        "gridPos": {"h": 8, "w": 12, "x": 0, "y": 0},
        "targets": [
          {
            "expr": "rate(http_requests_total[5m])",
            "legendFormat": "{{method}} {{endpoint}}"
          }
        ]
      },
      {
        "title": "Request Duration (p95)",
        "type": "graph",
        "gridPos": {"h": 8, "w": 12, "x": 12, "y": 0},
        "targets": [
          {
            "expr": "histogram_quantile(0.95, rate(http_request_duration_seconds_bucket[5m]))",
            "legendFormat": "{{endpoint}}"
          }
        ]
      },
      {
        "title": "Budget Status",
        "type": "gauge",
        "gridPos": {"h": 8, "w": 6, "x": 0, "y": 8},
        "targets": [
          {
            "expr": "budget_remaining_aud",
            "legendFormat": "Remaining"
          }
        ],
        "fieldConfig": {
          "defaults": {
            "max": 50,
            "min": 0,
            "unit": "currencyAUD",
            "thresholds": {
              "steps": [
                {"color": "red", "value": 0},
                {"color": "yellow", "value": 10},
                {"color": "green", "value": 25}
              ]
            }
          }
        }
      },
      {
        "title": "LLM Cost Over Time",
        "type": "graph",
        "gridPos": {"h": 8, "w": 18, "x": 6, "y": 8},
        "targets": [
          {
            "expr": "increase(llm_cost_aud_total[1h])",
            "legendFormat": "{{provider}} {{model}}"
          }
        ]
      },
      {
        "title": "Agent Executions",
        "type": "graph",
        "gridPos": {"h": 8, "w": 12, "x": 0, "y": 16},
        "targets": [
          {
            "expr": "rate(agent_executions_total[5m])",
            "legendFormat": "{{agent_type}}"
          }
        ]
      },
      {
        "title": "Tournament Convergence",
        "type": "graph",
        "gridPos": {"h": 8, "w": 12, "x": 12, "y": 16},
        "targets": [
          {
            "expr": "tournament_convergence_score",
            "legendFormat": "{{research_goal_id}}"
          }
        ]
      },
      {
        "title": "Hypothesis Count by Status",
        "type": "piechart",
        "gridPos": {"h": 8, "w": 8, "x": 0, "y": 24},
        "targets": [
          {
            "expr": "sum(hypotheses_active) by (status)",
            "legendFormat": "{{status}}"
          }
        ]
      },
      {
        "title": "Task Queue",
        "type": "graph",
        "gridPos": {"h": 8, "w": 16, "x": 8, "y": 24},
        "targets": [
          {
            "expr": "task_queue_size",
            "legendFormat": "{{status}}"
          }
        ]
      }
    ],
    "refresh": "30s",
    "time": {"from": "now-6h", "to": "now"}
  }
}
```

### 6. Docker Compose for Monitoring (`monitoring/docker-compose.monitoring.yml`)

```yaml
version: '3.8'

services:
  prometheus:
    image: prom/prometheus:latest
    container_name: coscientist-prometheus
    ports:
      - "9090:9090"
    volumes:
      - ./prometheus/prometheus.yml:/etc/prometheus/prometheus.yml
      - ./prometheus/alerts.yml:/etc/prometheus/alerts.yml
      - prometheus_data:/prometheus
    command:
      - '--config.file=/etc/prometheus/prometheus.yml'
      - '--storage.tsdb.path=/prometheus'
      - '--web.enable-lifecycle'
    extra_hosts:
      - "host.docker.internal:host-gateway"

  grafana:
    image: grafana/grafana:latest
    container_name: coscientist-grafana
    ports:
      - "3001:3000"
    environment:
      - GF_SECURITY_ADMIN_PASSWORD=admin
      - GF_USERS_ALLOW_SIGN_UP=false
    volumes:
      - ./grafana/provisioning:/etc/grafana/provisioning
      - grafana_data:/var/lib/grafana
    depends_on:
      - prometheus

volumes:
  prometheus_data:
  grafana_data:
```

### 7. FastAPI Integration

Update `src/api/main.py`:

```python
from fastapi import FastAPI
from src.observability.metrics import metrics_endpoint
from src.observability.logging import setup_logging

# Initialize logging
setup_logging(level="INFO", json_format=True)

app = FastAPI(title="AI Co-Scientist API")

# Metrics endpoint
@app.get("/metrics")
async def metrics():
    return await metrics_endpoint()
```

### 8. Agent Integration Example

```python
# In src/agents/generation.py
from src.observability.metrics import (
    track_agent_execution,
    hypotheses_generated_total,
    hypothesis_elo_rating
)
from src.observability.logging import log_hypothesis_created

class GenerationAgent(BaseAgent):

    @track_agent_execution("generation")
    async def execute(self, research_goal: ResearchGoal, **kwargs) -> Hypothesis:
        # ... existing code ...

        hypothesis = await self._generate_hypothesis(...)

        # Update metrics
        hypotheses_generated_total.labels(
            research_goal_id=research_goal.id
        ).inc()

        hypothesis_elo_rating.labels(
            hypothesis_id=hypothesis.id
        ).set(hypothesis.elo_rating)

        # Log
        log_hypothesis_created(
            hypothesis_id=hypothesis.id,
            research_goal_id=research_goal.id,
            title=hypothesis.title,
            method=kwargs.get("method", "literature")
        )

        return hypothesis
```

## Running Monitoring Stack

```bash
# Start monitoring stack
cd monitoring
docker-compose -f docker-compose.monitoring.yml up -d

# Access
# Prometheus: http://localhost:9090
# Grafana: http://localhost:3001 (admin/admin)
```

## Test Cases (`tests/test_metrics.py`)

```python
import pytest
from src.observability.metrics import (
    http_requests_total,
    agent_executions_total,
    track_request
)

def test_request_counter():
    """Test HTTP request counter."""
    initial = http_requests_total.labels(
        method="GET",
        endpoint="/test",
        status="success"
    )._value.get()

    http_requests_total.labels(
        method="GET",
        endpoint="/test",
        status="success"
    ).inc()

    new_value = http_requests_total.labels(
        method="GET",
        endpoint="/test",
        status="success"
    )._value.get()

    assert new_value == initial + 1

@pytest.mark.asyncio
async def test_track_request_decorator():
    """Test request tracking decorator."""

    @track_request("/test")
    async def test_endpoint():
        return {"status": "ok"}

    result = await test_endpoint()
    assert result == {"status": "ok"}
```

## Success Criteria

- [ ] Prometheus metrics endpoint `/metrics` working
- [ ] Key metrics being collected (requests, agents, LLM, budget)
- [ ] Grafana dashboard showing real-time data
- [ ] Alert rules configured
- [ ] Structured JSON logging working
- [ ] Docker Compose stack running
- [ ] All tests passing

## AWS CloudWatch Integration (Optional)

For AWS deployment, metrics can be pushed to CloudWatch:

```python
import boto3

cloudwatch = boto3.client('cloudwatch')

def push_to_cloudwatch(metric_name: str, value: float, unit: str = 'Count'):
    cloudwatch.put_metric_data(
        Namespace='CoScientist',
        MetricData=[{
            'MetricName': metric_name,
            'Value': value,
            'Unit': unit
        }]
    )
```

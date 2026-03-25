"""Lightweight Prometheus-compatible metrics for Strype Cloud.

Exposes counters and gauges at GET /api/metrics in Prometheus text exposition format.
No external library needed — the format is plain text.

Metrics collected:
- strype_http_requests_total{method, path, status} — request counter
- strype_http_request_duration_seconds{method, path} — latency histogram buckets
- strype_circuit_breaker_state{service} — 0=closed, 1=open, 2=half_open
- strype_scheduler_last_tick_epoch — last scheduler tick timestamp
"""

import time
from collections import defaultdict
from typing import Optional

# --- In-memory counters (per-process) ---

_request_counts: dict[str, int] = defaultdict(int)
_request_durations: dict[str, list[float]] = defaultdict(list)

# Keep at most 1000 recent durations per path to bound memory
_MAX_DURATION_SAMPLES = 1000


def record_request(method: str, path: str, status_code: int, duration_s: float) -> None:
    """Record a completed HTTP request."""
    # Normalize path: strip query params, collapse IDs to :id
    normalized = _normalize_path(path)
    key = f'{method} {normalized} {status_code}'
    _request_counts[key] += 1

    dur_key = f'{method} {normalized}'
    durations = _request_durations[dur_key]
    durations.append(duration_s)
    if len(durations) > _MAX_DURATION_SAMPLES:
        _request_durations[dur_key] = durations[-_MAX_DURATION_SAMPLES:]


def _normalize_path(path: str) -> str:
    """Collapse UUID-like path segments to :id for aggregation."""
    parts = path.split("?")[0].split("/")
    normalized = []
    for part in parts:
        # Collapse UUIDs and long hex strings to :id
        if len(part) > 20 and ("-" in part or all(c in "0123456789abcdef-" for c in part.lower())):
            normalized.append(":id")
        elif part.startswith("claim_"):
            normalized.append(":code")
        else:
            normalized.append(part)
    return "/".join(normalized)


def format_prometheus() -> str:
    """Render all metrics in Prometheus text exposition format."""
    lines = []

    # Request counts
    lines.append("# HELP strype_http_requests_total Total HTTP requests")
    lines.append("# TYPE strype_http_requests_total counter")
    for key, count in sorted(_request_counts.items()):
        parts = key.split(" ", 2)
        if len(parts) == 3:
            method, path, status = parts
            lines.append(f'strype_http_requests_total{{method="{method}",path="{path}",status="{status}"}} {count}')

    # Request durations (simple avg + p95)
    lines.append("# HELP strype_http_request_duration_seconds Request duration")
    lines.append("# TYPE strype_http_request_duration_seconds summary")
    for key, durations in sorted(_request_durations.items()):
        if not durations:
            continue
        parts = key.split(" ", 1)
        if len(parts) == 2:
            method, path = parts
            avg = sum(durations) / len(durations)
            sorted_d = sorted(durations)
            p95 = sorted_d[int(len(sorted_d) * 0.95)] if len(sorted_d) >= 2 else avg
            lines.append(f'strype_http_request_duration_seconds{{method="{method}",path="{path}",quantile="0.5"}} {sorted_d[len(sorted_d)//2]:.4f}')
            lines.append(f'strype_http_request_duration_seconds{{method="{method}",path="{path}",quantile="0.95"}} {p95:.4f}')
            lines.append(f'strype_http_request_duration_seconds_count{{method="{method}",path="{path}"}} {len(durations)}')
            lines.append(f'strype_http_request_duration_seconds_sum{{method="{method}",path="{path}"}} {sum(durations):.4f}')

    # Circuit breaker states
    try:
        from .services.shipping_service import easypost_breaker
        breakers = [easypost_breaker]
    except ImportError:
        breakers = []

    if breakers:
        lines.append("# HELP strype_circuit_breaker_state Circuit breaker state (0=closed, 1=open, 2=half_open)")
        lines.append("# TYPE strype_circuit_breaker_state gauge")
        state_map = {"closed": 0, "open": 1, "half_open": 2}
        for b in breakers:
            state_val = state_map.get(b.state, 0)
            lines.append(f'strype_circuit_breaker_state{{service="{b.service_name}"}} {state_val}')
            lines.append(f'strype_circuit_breaker_failures{{service="{b.service_name}"}} {b.failure_count}')

    # Scheduler health
    try:
        from .services.scheduler import get_scheduler_health
        health = get_scheduler_health()
        lines.append("# HELP strype_scheduler_running Whether scheduler loop is running")
        lines.append("# TYPE strype_scheduler_running gauge")
        lines.append(f'strype_scheduler_running {1 if health.get("running") else 0}')
    except ImportError:
        pass

    lines.append("")
    return "\n".join(lines)

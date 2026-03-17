"""StatsD metrics client for CloudWatch custom metrics.

Emits:
  - Count: number of times each API endpoint is called
  - Timer: duration of each API call (ms)
  - Timer: duration of each database query (ms)
  - Timer: duration of each S3 operation (ms)
"""

import time
import logging
import statsd

logger = logging.getLogger(__name__)

# StatsD client — connects to localhost:8125 where CloudWatch agent listens
_client = statsd.StatsClient(host="localhost", port=8125, prefix="csye6225")


def increment(metric_name: str, count: int = 1):
    """Increment a counter metric."""
    try:
        _client.incr(metric_name, count)
    except Exception as e:
        logger.warning(f"Failed to emit counter metric {metric_name}: {e}")


def timing(metric_name: str, duration_ms: float):
    """Record a timing metric in milliseconds."""
    try:
        _client.timing(metric_name, duration_ms)
    except Exception as e:
        logger.warning(f"Failed to emit timing metric {metric_name}: {e}")


class Timer:
    """Context manager to measure and emit timing metrics."""

    def __init__(self, metric_name: str):
        self.metric_name = metric_name
        self.start_time = None
        self.duration_ms = 0

    def __enter__(self):
        self.start_time = time.time()
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        self.duration_ms = (time.time() - self.start_time) * 1000
        timing(self.metric_name, self.duration_ms)
        return False

"""
LangWatch tracing/evaluation initialization.

Reads LANGWATCH_API_KEY (and optional LANGWATCH_ENDPOINT) from the environment.
If no API key is set, LangWatch runs in local/no-op mode — traces are still
created in-process but nothing is sent over the wire, so the rest of the app
behaves identically.

Usage:
    from app.observability.langwatch_setup import init_langwatch
    init_langwatch()
"""
from __future__ import annotations

import logging
import os
from typing import Optional

logger = logging.getLogger(__name__)

_INITIALIZED = False
_ENABLED = False


def init_langwatch() -> bool:
    """
    Initialize LangWatch once. Returns True if remote sending is enabled.

    Without LANGWATCH_API_KEY the SDK refuses to set up its tracer provider,
    so we treat that as 'disabled' and let the agent code use no-op spans.
    """
    global _INITIALIZED, _ENABLED
    if _INITIALIZED:
        return _ENABLED

    _INITIALIZED = True

    try:
        import langwatch
    except ImportError:
        logger.warning("langwatch package not installed; tracing disabled")
        return False

    api_key = os.getenv("LANGWATCH_API_KEY", "").strip()
    endpoint = os.getenv("LANGWATCH_ENDPOINT", "").strip() or None

    if not api_key:
        logger.info(
            "LangWatch disabled — no LANGWATCH_API_KEY set. "
            "Export LANGWATCH_API_KEY=<your key> (and optionally LANGWATCH_ENDPOINT) "
            "to ship traces & evaluations to the dashboard."
        )
        return False

    kwargs = {
        "api_key": api_key,
        "base_attributes": {
            "service.name": os.getenv("LANGWATCH_SERVICE", "enterprise-agent-sor"),
            "service.version": "2.0.0",
            "deployment.environment": os.getenv("ENVIRONMENT", "development"),
        },
    }
    if endpoint:
        kwargs["endpoint_url"] = endpoint

    try:
        langwatch.setup(**kwargs)
    except Exception as e:
        logger.warning(f"LangWatch setup failed: {e}")
        return False

    _ENABLED = True
    logger.info(
        f"LangWatch enabled — sending to {endpoint or 'https://app.langwatch.ai'}"
    )
    return _ENABLED


def is_enabled() -> bool:
    return _ENABLED


def get_langwatch() -> Optional[object]:
    """
    Return the langwatch module ONLY if init_langwatch() succeeded
    (so calling code can use it directly without re-checking).
    """
    if not _ENABLED:
        return None
    try:
        import langwatch
        return langwatch
    except ImportError:
        return None

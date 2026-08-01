"""Socket.IO server — Redis-backed for multi-instance broadcast when Redis is up."""

from __future__ import annotations

import logging
import socket
from urllib.parse import urlparse

import socketio

from app.core.config import settings

logger = logging.getLogger(__name__)


def _redis_reachable(url: str, timeout: float = 0.75) -> bool:
    parsed = urlparse(url)
    host = parsed.hostname or "localhost"
    port = parsed.port or 6379
    try:
        with socket.create_connection((host, port), timeout=timeout):
            return True
    except OSError:
        return False


def _build_client_manager():
    if _redis_reachable(settings.REDIS_URL):
        logger.info("Socket.IO using AsyncRedisManager at %s", settings.REDIS_URL)
        return socketio.AsyncRedisManager(settings.REDIS_URL)
    logger.warning(
        "Redis unreachable at %s — Socket.IO falling back to in-memory manager "
        "(fine for single-instance local; required for horizontal scale).",
        settings.REDIS_URL,
    )
    return None


# Built-in heartbeat: ping_interval / ping_timeout detect dead sockets.
sio = socketio.AsyncServer(
    async_mode="asgi",
    client_manager=_build_client_manager(),
    cors_allowed_origins="*",
    logger=settings.DEBUG,
    engineio_logger=settings.DEBUG,
    ping_interval=25,
    ping_timeout=60,
)


def user_room(user_id) -> str:
    return f"user:{user_id}"


def conversation_room(conversation_id) -> str:
    return f"conversation:{conversation_id}"

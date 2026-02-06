"""
Network utility functions.
"""

import socket
from functools import lru_cache
import time


_last_check_time: float = 0
_last_check_result: bool = False
_check_interval: float = 30.0  # Check every 30 seconds


def is_online(force_check: bool = False) -> bool:
    """
    Check if the system has internet connectivity.

    Uses caching to avoid frequent checks.
    """
    global _last_check_time, _last_check_result

    current_time = time.time()

    if not force_check and (current_time - _last_check_time) < _check_interval:
        return _last_check_result

    _last_check_time = current_time
    _last_check_result = _check_connectivity()

    return _last_check_result


def _check_connectivity() -> bool:
    """Actually check internet connectivity."""
    try:
        # Try to connect to Google's DNS
        socket.create_connection(("8.8.8.8", 53), timeout=3)
        return True
    except OSError:
        pass

    try:
        # Fallback: try to connect to Cloudflare's DNS
        socket.create_connection(("1.1.1.1", 53), timeout=3)
        return True
    except OSError:
        pass

    return False

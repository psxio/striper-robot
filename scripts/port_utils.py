"""Utilities for selecting non-conflicting local TCP ports."""

from __future__ import annotations

import socket


def is_port_available(port: int, host: str = "127.0.0.1") -> bool:
    """Return True when a TCP port can be bound on the given host."""
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as sock:
        try:
            sock.bind((host, port))
        except OSError:
            return False
    return True


def find_free_port(start_port: int = 8111, host: str = "127.0.0.1", max_port: int = 65535) -> int:
    """Find the first available TCP port starting from start_port."""
    if start_port < 1 or start_port > 65535:
        raise ValueError(f"start_port must be between 1 and 65535, got {start_port}")
    if max_port < 1 or max_port > 65535:
        raise ValueError(f"max_port must be between 1 and 65535, got {max_port}")
    if start_port > max_port:
        raise ValueError(f"start_port ({start_port}) must be <= max_port ({max_port})")

    for port in range(start_port, max_port + 1):
        if is_port_available(port, host=host):
            return port

    raise RuntimeError(f"No available TCP port found in range {start_port}-{max_port}")

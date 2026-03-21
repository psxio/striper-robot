"""Start the backend on a non-conflicting local port."""

from __future__ import annotations

import argparse
import os
import subprocess
import sys

from port_utils import find_free_port, is_port_available


def main() -> int:
    parser = argparse.ArgumentParser(description="Run FastAPI backend on a free port")
    parser.add_argument("--host", default="0.0.0.0", help="Host interface to bind")
    parser.add_argument("--start-port", type=int, default=None, help="Preferred starting port")
    parser.add_argument("--strict-port", action="store_true", help="Fail if preferred port is busy")
    parser.add_argument("--reload", action="store_true", help="Enable uvicorn reload mode")
    args = parser.parse_args()

    preferred = args.start_port
    if preferred is None:
        try:
            preferred = int(os.environ.get("PORT", "8111"))
        except ValueError:
            print(f"Invalid PORT environment variable: {os.environ.get('PORT')}", file=sys.stderr)
            return 1

    if args.strict_port:
        if not is_port_available(preferred):
            print(f"Port {preferred} is already in use", file=sys.stderr)
            return 2
        selected_port = preferred
    else:
        selected_port = find_free_port(start_port=preferred)
        if selected_port != preferred:
            print(f"Preferred port {preferred} is busy, using {selected_port}")

    env = dict(os.environ)
    env["PORT"] = str(selected_port)

    url_host = "127.0.0.1" if args.host == "0.0.0.0" else args.host
    print(f"Starting backend on http://{url_host}:{selected_port}")

    command = [
        sys.executable,
        "-m",
        "uvicorn",
        "backend.main:app",
        "--host",
        args.host,
        "--port",
        str(selected_port),
    ]
    if args.reload:
        command.append("--reload")

    completed = subprocess.run(command, env=env)
    return completed.returncode


if __name__ == "__main__":
    raise SystemExit(main())

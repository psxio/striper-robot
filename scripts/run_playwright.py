"""Run Playwright tests on a non-conflicting backend port."""

from __future__ import annotations

import os
import shutil
import subprocess
import sys

from port_utils import find_free_port


def main() -> int:
    raw_port = os.environ.get("PLAYWRIGHT_PORT", os.environ.get("PORT", "8111"))
    try:
        start_port = int(raw_port)
    except ValueError:
        print(f"Invalid PLAYWRIGHT_PORT/PORT environment value: {raw_port}", file=sys.stderr)
        return 1

    selected_port = find_free_port(start_port=start_port)

    env = dict(os.environ)
    env["PLAYWRIGHT_PORT"] = str(selected_port)

    npx_cmd = shutil.which("npx")
    if not npx_cmd:
        print("npx was not found in PATH. Install Node.js to run Playwright.", file=sys.stderr)
        return 1

    print(f"Running Playwright with backend on http://127.0.0.1:{selected_port}")

    command = [npx_cmd, "playwright", "test", *sys.argv[1:]]
    completed = subprocess.run(command, env=env)
    return completed.returncode


if __name__ == "__main__":
    raise SystemExit(main())

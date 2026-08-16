"""Wait for local development infrastructure without adding extra dependencies."""

import argparse
import socket
import time
import urllib.error
import urllib.request
from dataclasses import dataclass
from urllib.parse import urlparse

from app.core.config import Settings


@dataclass(frozen=True, slots=True)
class Check:
    name: str
    kind: str
    target: str


def _tcp_ready(url: str, timeout: float) -> bool:
    parsed = urlparse(url)
    host = parsed.hostname or "127.0.0.1"
    if parsed.port is not None:
        port = parsed.port
    elif parsed.scheme.startswith("postgres"):
        port = 5432
    elif parsed.scheme.startswith("redis"):
        port = 6379
    else:
        raise ValueError(f"Could not infer port from {url!r}")

    try:
        with socket.create_connection((host, port), timeout=timeout):
            return True
    except OSError:
        return False


def _http_ready(url: str, timeout: float) -> bool:
    try:
        with urllib.request.urlopen(url, timeout=timeout) as response:
            return 200 <= response.status < 500
    except (OSError, urllib.error.URLError):
        return False


def _ready(check: Check, timeout: float) -> bool:
    if check.kind == "tcp":
        return _tcp_ready(check.target, timeout)
    return _http_ready(check.target, timeout)


def wait(checks: list[Check], timeout_s: float) -> None:
    deadline = time.monotonic() + timeout_s
    pending = {check.name: check for check in checks}
    announced: set[str] = set()

    while pending and time.monotonic() < deadline:
        for name, check in list(pending.items()):
            if _ready(check, timeout=1.5):
                print(f"[ok] {name}")
                pending.pop(name)
            elif name not in announced:
                print(f"[...] aguardando {name}")
                announced.add(name)
        if pending:
            time.sleep(1.0)

    if pending:
        missing = ", ".join(sorted(pending))
        raise SystemExit(f"ERRO: timeout aguardando infraestrutura: {missing}")


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--timeout", type=float, default=120.0)
    parser.add_argument("--gateway", action="store_true")
    args = parser.parse_args()

    settings = Settings()
    checks = [
        Check("PostgreSQL", "tcp", settings.database_url),
        Check("Redis", "tcp", settings.redis_url),
        Check("Ollama", "http", f"{settings.ollama_base_url.rstrip('/')}/api/tags"),
        Check("Qdrant", "http", f"{settings.qdrant_base_url.rstrip('/')}/readyz"),
    ]
    if args.gateway:
        checks.append(Check("Gateway", "http", f"http://127.0.0.1:{settings.port}/health"))

    wait(checks, args.timeout)


if __name__ == "__main__":
    main()

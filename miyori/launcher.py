from __future__ import annotations

import argparse
import json
import os
import platform
import socket
import sys
import threading
import time
import traceback
import urllib.error
import urllib.request
import webbrowser
from pathlib import Path
from typing import TextIO

import uvicorn

from .config import settings


MIN_PYTHON = (3, 10)
ROOT = Path(__file__).resolve().parent.parent
LOG_DIR = ROOT / "logs"
STARTUP_LOG = LOG_DIR / "last-startup.log"


class _Tee:
    def __init__(self, *streams: TextIO):
        self.streams = streams

    def write(self, value: str) -> int:
        written = 0
        for stream in self.streams:
            try:
                stream.write(value)
                stream.flush()
                written = len(value)
            except UnicodeEncodeError:
                encoding = getattr(stream, "encoding", None) or "utf-8"
                safe_value = value.encode(
                    encoding,
                    errors="replace",
                ).decode(
                    encoding,
                    errors="replace",
                )
                try:
                    stream.write(safe_value)
                    stream.flush()
                    written = len(value)
                except OSError:
                    continue
            except OSError:
                continue
        return written

    def flush(self) -> None:
        for stream in self.streams:
            try:
                stream.flush()
            except OSError:
                continue


def python_supported(version_info=None) -> bool:
    version = version_info or sys.version_info
    return tuple(version[:2]) >= MIN_PYTHON


def browser_host(host: str) -> str:
    clean = (host or "").strip()
    if clean in {"", "0.0.0.0", "::", "[::]"}:
        return "127.0.0.1"
    return clean


def service_url(host: str | None = None, port: int | None = None) -> str:
    resolved_host = browser_host(host or settings.host)
    resolved_port = int(port or settings.port)
    return f"http://{resolved_host}:{resolved_port}"


def _health_url(host: str, port: int) -> str:
    return service_url(host, port) + "/api/status"


def _read_health(host: str, port: int, *, timeout: float = 1.0) -> dict | None:
    request = urllib.request.Request(
        _health_url(host, port),
        headers={"Accept": "application/json", "User-Agent": "Miyori-Launcher"},
    )
    try:
        with urllib.request.urlopen(request, timeout=timeout) as response:
            if response.status != 200:
                return None
            payload = json.loads(response.read().decode("utf-8"))
    except (
        urllib.error.URLError,
        TimeoutError,
        ValueError,
        OSError,
        json.JSONDecodeError,
    ):
        return None
    if not isinstance(payload, dict):
        return None
    if payload.get("name") != "Miyori Kitsune AI":
        return None
    return payload


def port_is_open(host: str, port: int, *, timeout: float = 0.35) -> bool:
    target = browser_host(host)
    family = socket.AF_INET6 if ":" in target else socket.AF_INET
    try:
        with socket.socket(family, socket.SOCK_STREAM) as sock:
            sock.settimeout(timeout)
            return sock.connect_ex((target, port)) == 0
    except OSError:
        return False


def ensure_runtime_files() -> list[str]:
    required = [
        ROOT / "app.py",
        ROOT / "templates" / "index.html",
        ROOT / "static",
        ROOT / "miyori",
    ]
    return [str(path.relative_to(ROOT)) for path in required if not path.exists()]


def run_preflight(host: str, port: int) -> tuple[bool, str]:
    if not python_supported():
        minimum = ".".join(str(item) for item in MIN_PYTHON)
        return False, (
            f"Python {sys.version.split()[0]} слишком старый. "
            f"Требуется Python {minimum} или новее."
        )

    missing = ensure_runtime_files()
    if missing:
        return False, "В папке Miyori отсутствуют файлы: " + ", ".join(missing)

    health = _read_health(host, port)
    if health:
        return True, (
            f"Miyori уже запущена: {service_url(host, port)} "
            f"(версия {health.get('version') or 'unknown'})."
        )

    if port_is_open(host, port):
        return False, (
            f"Порт {port} уже занят другим приложением. "
            "Закройте его или измените MIYORI_PORT в .env."
        )

    try:
        __import__("app")
    except Exception as exc:
        return False, f"Не удалось импортировать приложение: {exc}"

    return True, "Проверка запуска успешно завершена."


def _wait_and_open_browser(host: str, port: int, log: TextIO) -> None:
    deadline = time.monotonic() + 30.0
    while time.monotonic() < deadline:
        health = _read_health(host, port, timeout=0.75)
        if health:
            url = service_url(host, port)
            try:
                opened = webbrowser.open(url, new=2)
                print(
                    f"[browser] {'opened' if opened else 'requested'} {url}",
                    file=log,
                    flush=True,
                )
            except Exception as exc:
                print(f"[browser] could not open: {exc}", file=log, flush=True)
            return
        time.sleep(0.25)
    print("[browser] server readiness timeout; browser was not opened.", file=log, flush=True)


def _force_utf8_stdio() -> None:
    for stream in (sys.stdout, sys.stderr):
        reconfigure = getattr(stream, "reconfigure", None)
        if not callable(reconfigure):
            continue
        try:
            reconfigure(encoding="utf-8", errors="replace")
        except (OSError, ValueError):
            continue


def _prepare_log() -> TextIO:
    LOG_DIR.mkdir(parents=True, exist_ok=True)
    return STARTUP_LOG.open("w", encoding="utf-8", buffering=1)


def _print_environment() -> None:
    print("Miyori Kitsune AI startup")
    print(f"Root: {ROOT}")
    print(f"Python: {sys.version.split()[0]} ({sys.executable})")
    print(f"Platform: {platform.platform()}")
    print(f"URL: {service_url()}")
    print()


def _build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Miyori local launcher")
    parser.add_argument("--check", action="store_true", help="Validate startup without running the server.")
    parser.add_argument("--no-browser", action="store_true", help="Do not open the browser automatically.")
    parser.add_argument("--host", default=None, help="Override MIYORI_HOST.")
    parser.add_argument("--port", type=int, default=None, help="Override MIYORI_PORT.")
    return parser


def main(argv: list[str] | None = None) -> int:
    _force_utf8_stdio()
    args = _build_parser().parse_args(argv)
    host = str(args.host or settings.host)
    port = int(args.port or settings.port)

    log = _prepare_log()
    original_stdout = sys.stdout
    original_stderr = sys.stderr
    sys.stdout = _Tee(original_stdout, log)  # type: ignore[assignment]
    sys.stderr = _Tee(original_stderr, log)  # type: ignore[assignment]
    try:
        _print_environment()

        ok, message = run_preflight(host, port)
        if args.check:
            print(("[OK] " if ok else "[ERROR] ") + message)
            return 0 if ok else 2

        health = _read_health(host, port)
        if health:
            print(message)
            if not args.no_browser and settings.open_browser:
                webbrowser.open(service_url(host, port), new=2)
            return 0

        if not ok:
            print("[ERROR] " + message)
            return 2

        print("[startup] " + message)
        print("[startup] Starting Uvicorn...")
        print("Press Ctrl+C to stop Miyori.")
        print()

        if not args.no_browser and settings.open_browser:
            thread = threading.Thread(
                target=_wait_and_open_browser,
                args=(host, port, log),
                daemon=True,
                name="miyori-browser-opener",
            )
            thread.start()

        config = uvicorn.Config(
            "app:app",
            host=host,
            port=port,
            log_level="info",
            access_log=False,
            reload=False,
        )
        server = uvicorn.Server(config)
        server.run()
        if not server.started:
            print("[ERROR] Uvicorn did not start.")
            return 3
        return 0
    except KeyboardInterrupt:
        print("\n[startup] Miyori stopped by user.")
        return 0
    except BaseException:
        traceback.print_exc()
        return 4
    finally:
        sys.stdout = original_stdout
        sys.stderr = original_stderr
        log.close()


if __name__ == "__main__":
    raise SystemExit(main())

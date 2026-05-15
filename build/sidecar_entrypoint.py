"""
PyInstaller entrypoint for the AGF Co-Scientist Python sidecar.

Responsibilities:
  1. Read bind host/port from environment (`AGF_BIND_HOST` / `AGF_BIND_PORT`),
     defaulting to `127.0.0.1:0` (ephemeral port).
  2. Start uvicorn programmatically against `src.api.main:app`.
  3. After the socket is bound, write the actual port to
     `<AGF_DATA_DIR>/port.txt` so the Electron main process can read it.
  4. Tear the file down on shutdown.

The Electron main process polls `<userData>/port.txt`; this entrypoint
exists so the bundled binary writes that file even when started outside
of `uvicorn` CLI.
"""

from __future__ import annotations

import asyncio
import os
import signal
import sys
from pathlib import Path


def _data_dir() -> Path:
    raw = os.environ.get("AGF_DATA_DIR")
    if raw:
        p = Path(raw)
    else:
        p = Path.home() / ".agf-coscientist"
    p.mkdir(parents=True, exist_ok=True)
    return p


def _write_port_file(port: int) -> Path:
    path = _data_dir() / "port.txt"
    path.write_text(str(port), encoding="utf-8")
    return path


def _remove_port_file(path: Path) -> None:
    try:
        if path.exists():
            path.unlink()
    except Exception:
        pass


async def _serve() -> None:
    # Lazy import so PyInstaller's analysis pulls these into the bundle.
    import uvicorn

    from src.api.main import app  # type: ignore

    host = os.environ.get("AGF_BIND_HOST", "127.0.0.1")
    port = int(os.environ.get("AGF_BIND_PORT", "0"))

    config = uvicorn.Config(
        app,
        host=host,
        port=port,
        log_level=os.environ.get("AGF_LOG_LEVEL", "info"),
        loop="asyncio",
        lifespan="on",
    )
    server = uvicorn.Server(config)

    # Start the server in the background so we can probe the bound port.
    serve_task = asyncio.create_task(server.serve())

    # Wait until uvicorn has bound a socket and recorded `.servers`.
    while not server.started:
        await asyncio.sleep(0.05)

    bound_port = port
    try:
        # uvicorn exposes the bound sockets via `server.servers[*].sockets`.
        for srv in server.servers:
            for sock in srv.sockets:
                addr = sock.getsockname()
                if isinstance(addr, tuple) and len(addr) >= 2:
                    bound_port = int(addr[1])
                    break
            if bound_port:
                break
    except Exception as exc:  # pragma: no cover - defensive
        print(f"[sidecar] could not introspect port: {exc}", file=sys.stderr)

    port_file = _write_port_file(bound_port)
    print(f"[sidecar] listening on http://{host}:{bound_port}", flush=True)
    print(f"[sidecar] port file: {port_file}", flush=True)

    # Forward SIGTERM/SIGINT to uvicorn for graceful shutdown.
    loop = asyncio.get_running_loop()

    def _request_shutdown() -> None:
        server.should_exit = True

    for sig_name in ("SIGTERM", "SIGINT"):
        sig = getattr(signal, sig_name, None)
        if sig is None:
            continue
        try:
            loop.add_signal_handler(sig, _request_shutdown)
        except NotImplementedError:
            # Windows: signal handlers via add_signal_handler are unsupported.
            signal.signal(sig, lambda *_: _request_shutdown())

    try:
        await serve_task
    finally:
        _remove_port_file(port_file)


def main() -> None:
    try:
        asyncio.run(_serve())
    except KeyboardInterrupt:
        pass


if __name__ == "__main__":
    main()

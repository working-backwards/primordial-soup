#!/usr/bin/env python
"""Serve the run designer page with local validate-and-run support.

Usage
-----
    python scripts/design_studio.py            # serve on http://127.0.0.1:8765
    python scripts/design_studio.py --port 9000
    python scripts/design_studio.py --no-browser

What this is
------------
A thin standard-library HTTP wrapper around tools/run_designer.html. The
page works standalone (double-click it, download the YAML, run it with
scripts/run_design.py). Served through this script, the page additionally
detects the local API and offers two buttons:

    Validate on server — resolves the posted YAML through the workbench
        (RunDesignSpec.from_dict → resolve_run_design) and returns the
        resolved-design summary, without running anything.
    Save & run — writes the YAML under results/designs/ and executes it
        via scripts/run_design.py --no-confirm, exactly as if the user had
        run it from the command line. The page polls for output.

This script deliberately owns NO simulation or config-assembly logic:
run_design.py remains the single execution path, and the workbench remains
the single schema authority. Everything here is HTTP plumbing.

Endpoints (all bound to 127.0.0.1 only)
---------------------------------------
    GET  /                → tools/run_designer.html
    GET  /api/ping        → {"ok": true} (the page's server-mode probe)
    POST /api/validate    → {"ok": true, "summary": ...} or {"ok": false, "error": ...}
    POST /api/run         → {"ok": true, "run_id": ..., "yaml_path": ...}
    GET  /api/status?id=N → {"output": ..., "done": ..., "exit_code": ...}
"""

from __future__ import annotations

import argparse
import json
import logging
import subprocess
import sys
import threading
import webbrowser
from datetime import UTC, datetime
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from urllib.parse import parse_qs, urlparse

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s  %(levelname)-8s  %(name)s  %(message)s",
    datefmt="%H:%M:%S",
)
logger = logging.getLogger("design_studio")

# Repo layout: this file lives in scripts/, the page in tools/, and saved
# designs go under results/ (already gitignored — per CLAUDE.md script
# output conventions).
REPO_ROOT = Path(__file__).resolve().parent.parent
PAGE_PATH = REPO_ROOT / "tools" / "run_designer.html"
RUN_DESIGN_SCRIPT = REPO_ROOT / "scripts" / "run_design.py"
DESIGNS_DIR = REPO_ROOT / "results" / "designs"

# Cap on retained subprocess output lines per run, to bound memory if a
# long campaign is launched from the page.
MAX_OUTPUT_LINES = 2000


# ---------------------------------------------------------------------------
# Workbench plumbing (testable without a socket — see tests/test_design_studio.py)
# ---------------------------------------------------------------------------


def validate_design_yaml(yaml_text: str) -> dict:
    """Resolve a run-design YAML string through the workbench without running.

    Args:
        yaml_text: Contents of a run-design YAML file.

    Returns:
        {"ok": True, "summary": <resolved-design summary str>} on success,
        {"ok": False, "error": <message>} when parsing, validation, or
        resolution fails. All failure modes are reported as data rather
        than raised, because the caller forwards them to the browser.
    """
    import yaml

    from primordial_soup.workbench import RunDesignSpec, resolve_run_design

    try:
        data = yaml.safe_load(yaml_text)
        if not isinstance(data, dict):
            return {"ok": False, "error": "YAML did not produce a mapping at the top level."}
        spec = RunDesignSpec.from_dict(data)
        resolved = resolve_run_design(spec)  # validates, then resolves
    except (ValueError, KeyError, TypeError, yaml.YAMLError) as exc:
        return {"ok": False, "error": str(exc)}
    return {"ok": True, "summary": resolved.summary()}


def save_design_yaml(yaml_text: str, designs_dir: Path) -> Path:
    """Write a design YAML under designs_dir with a timestamped filename.

    The filename is "<design name>_<UTC timestamp>.yaml" so repeated runs
    of the same design never collide. The design name is read from the
    YAML itself (falling back to "design" if absent) — by the time this is
    called the YAML has already passed validate_design_yaml().

    Args:
        yaml_text: Validated run-design YAML contents.
        designs_dir: Directory to write into (created if missing).

    Returns:
        Path of the written file.
    """
    import yaml

    data = yaml.safe_load(yaml_text)
    design_name = str(data.get("name", "design")).strip() or "design"
    timestamp = datetime.now(UTC).strftime("%Y%m%d_%H%M%S")
    designs_dir.mkdir(parents=True, exist_ok=True)
    yaml_path = designs_dir / f"{design_name}_{timestamp}.yaml"
    # Two saves of the same design within one second must not overwrite
    # each other — add a numeric suffix until the name is free.
    suffix = 2
    while yaml_path.exists():
        yaml_path = designs_dir / f"{design_name}_{timestamp}_{suffix}.yaml"
        suffix += 1
    yaml_path.write_text(yaml_text, encoding="utf-8")
    return yaml_path


# ---------------------------------------------------------------------------
# Run registry: one entry per launched run_design.py subprocess
# ---------------------------------------------------------------------------


class RunHandle:
    """Mutable record of one launched run_design.py subprocess.

    Deliberately a plain class, not a frozen dataclass: it accumulates
    subprocess output as it streams in. Access is guarded by `lock`.
    """

    def __init__(self, yaml_path: Path) -> None:
        self.yaml_path = yaml_path
        self.lock = threading.Lock()
        self.output_lines: list[str] = []
        self.done = False
        self.exit_code: int | None = None

    def append_line(self, line: str) -> None:
        with self.lock:
            self.output_lines.append(line)
            # Keep only the tail — the browser shows a scrollback, not a log.
            if len(self.output_lines) > MAX_OUTPUT_LINES:
                del self.output_lines[:-MAX_OUTPUT_LINES]

    def finish(self, exit_code: int) -> None:
        with self.lock:
            self.done = True
            self.exit_code = exit_code

    def snapshot(self) -> dict:
        with self.lock:
            return {
                "output": "\n".join(self.output_lines),
                "done": self.done,
                "exit_code": self.exit_code,
            }


_runs: dict[int, RunHandle] = {}
_runs_lock = threading.Lock()
_next_run_id = 0


def start_run(yaml_path: Path) -> int:
    """Launch run_design.py on a saved design and stream its output.

    Runs `<python> scripts/run_design.py <yaml_path> --no-confirm` with the
    repo root as working directory (so output lands under results/ exactly
    as a manual invocation would). A daemon thread drains stdout+stderr
    into the run's handle.

    Args:
        yaml_path: A design file previously written by save_design_yaml().

    Returns:
        Integer run id for /api/status polling.
    """
    global _next_run_id
    handle = RunHandle(yaml_path)
    with _runs_lock:
        run_id = _next_run_id
        _next_run_id += 1
        _runs[run_id] = handle

    process = subprocess.Popen(
        [sys.executable, str(RUN_DESIGN_SCRIPT), str(yaml_path), "--no-confirm"],
        cwd=str(REPO_ROOT),
        stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT,  # interleave, as a terminal would show it
        text=True,
        encoding="utf-8",
        errors="replace",
    )
    logger.info("run %d started: %s (pid %d)", run_id, yaml_path.name, process.pid)

    def drain() -> None:
        assert process.stdout is not None  # guaranteed by stdout=PIPE
        for line in process.stdout:
            handle.append_line(line.rstrip("\n"))
        handle.finish(process.wait())
        logger.info("run %d finished with exit code %s", run_id, handle.exit_code)

    threading.Thread(target=drain, daemon=True, name=f"run-{run_id}-drain").start()
    return run_id


def get_run(run_id: int) -> RunHandle | None:
    with _runs_lock:
        return _runs.get(run_id)


# ---------------------------------------------------------------------------
# HTTP handler
# ---------------------------------------------------------------------------


class DesignStudioHandler(BaseHTTPRequestHandler):
    """Routes the five endpoints. All responses are JSON except the page."""

    # Quieter than the default BaseHTTPRequestHandler stderr logging.
    def log_message(self, format: str, *args) -> None:  # noqa: A002 (stdlib signature)
        logger.debug("%s — %s", self.address_string(), format % args)

    def _send_json(self, payload: dict, status: int = 200) -> None:
        body = json.dumps(payload).encode("utf-8")
        self.send_response(status)
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def _read_body(self) -> str:
        length = int(self.headers.get("Content-Length", "0"))
        return self.rfile.read(length).decode("utf-8")

    def do_GET(self) -> None:  # noqa: N802 (stdlib naming)
        parsed = urlparse(self.path)
        if parsed.path in ("/", "/index.html"):
            body = PAGE_PATH.read_bytes()
            self.send_response(200)
            self.send_header("Content-Type", "text/html; charset=utf-8")
            self.send_header("Content-Length", str(len(body)))
            self.end_headers()
            self.wfile.write(body)
        elif parsed.path == "/api/ping":
            self._send_json({"ok": True})
        elif parsed.path == "/api/status":
            query = parse_qs(parsed.query)
            try:
                run_id = int(query.get("id", ["-1"])[0])
            except ValueError:
                run_id = -1
            handle = get_run(run_id)
            if handle is None:
                self._send_json({"ok": False, "error": f"Unknown run id {run_id}."}, status=404)
            else:
                self._send_json(handle.snapshot())
        else:
            self._send_json({"ok": False, "error": "Not found."}, status=404)

    def do_POST(self) -> None:  # noqa: N802 (stdlib naming)
        parsed = urlparse(self.path)
        if parsed.path == "/api/validate":
            self._send_json(validate_design_yaml(self._read_body()))
        elif parsed.path == "/api/run":
            yaml_text = self._read_body()
            # Validate before launching anything: a run that would fail
            # run_design.py's own validation is refused with the reason.
            verdict = validate_design_yaml(yaml_text)
            if not verdict["ok"]:
                self._send_json(verdict)
                return
            yaml_path = save_design_yaml(yaml_text, DESIGNS_DIR)
            run_id = start_run(yaml_path)
            self._send_json(
                {
                    "ok": True,
                    "run_id": run_id,
                    # Repo-relative path is friendlier in the browser console.
                    "yaml_path": str(yaml_path.relative_to(REPO_ROOT)),
                }
            )
        else:
            self._send_json({"ok": False, "error": "Not found."}, status=404)


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------


def main() -> None:
    parser = argparse.ArgumentParser(description="Serve the run designer page locally.")
    parser.add_argument("--port", type=int, default=8765, help="Port to listen on (default 8765).")
    parser.add_argument(
        "--no-browser", action="store_true", help="Do not open the page in a browser on start."
    )
    args = parser.parse_args()

    if not PAGE_PATH.exists():
        logger.error("Designer page not found: %s", PAGE_PATH)
        sys.exit(1)

    # Loopback only: this server executes simulations on request, so it must
    # never be reachable from other machines.
    address = ("127.0.0.1", args.port)
    server = ThreadingHTTPServer(address, DesignStudioHandler)
    url = f"http://{address[0]}:{args.port}/"
    logger.info("Design studio serving %s at %s (Ctrl+C to stop)", PAGE_PATH.name, url)
    if not args.no_browser:
        webbrowser.open(url)
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        logger.info("Shutting down.")
        server.shutdown()


if __name__ == "__main__":
    main()

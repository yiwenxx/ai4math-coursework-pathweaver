"""Persistent warm Lean 4 LSP server pool for fast incremental kernel verification."""
import atexit
from collections import deque
import json
import os
from pathlib import Path
import queue
import shutil
import subprocess
import tempfile
import threading
import time
from typing import Any

from pathweaver.research.formal_verifier import resolve_lean_executable

try:
    from pathweaver.execution.process import WindowsJob
except Exception:  # pragma: no cover - optional fallback outside full runtime
    WindowsJob = None  # type: ignore[assignment]

_LSP_SEVERITY_MAP = {
    1: "error",
    2: "warning",
    3: "information",
    4: "hint",
}


def _read_exact(stream: Any, size: int) -> bytes:
    """Read exactly `size` bytes from an unbuffered binary stream, or fewer on EOF."""
    chunks: list[bytes] = []
    remaining = size
    while remaining > 0:
        chunk = stream.read(remaining)
        if not chunk:
            break
        chunks.append(chunk)
        remaining -= len(chunk)
    return b"".join(chunks)


def _format_lsp_diagnostics(raw_diags: list[dict[str, Any]]) -> tuple[list[dict[str, Any]], str, int, int]:
    """Convert LSP `publishDiagnostics` items to PathWeaver diagnostic dicts and summary text."""
    diagnostics: list[dict[str, Any]] = []
    text_lines: list[str] = []
    for item in raw_diags:
        if not isinstance(item, dict):
            continue
        rng = item.get("range") or {}
        pos = rng.get("start") if isinstance(rng, dict) else {}
        line_val = pos.get("line") if isinstance(pos, dict) else None
        col_val = pos.get("character") if isinstance(pos, dict) else None
        line_no = line_val + 1 if isinstance(line_val, int) else None
        col_no = col_val if isinstance(col_val, int) else None
        sev_raw = item.get("severity", 3)
        severity = _LSP_SEVERITY_MAP.get(sev_raw, str(sev_raw)) if isinstance(sev_raw, int) else str(sev_raw)
        message = str(item.get("message", "")).strip()
        diagnostics.append({
            "severity": severity,
            "line": line_no,
            "column": col_no,
            "message": message,
        })
        loc = f"{line_no}:{col_no}: " if line_no is not None else ""
        text_lines.append(f"{severity}: {loc}{message}")
    error_count = sum(1 for item in diagnostics if item["severity"] == "error")
    sorry_count = sum(
        1 for item in diagnostics
        if item["severity"] == "warning" and "sorry" in item["message"].lower()
    )
    return diagnostics, "\n".join(text_lines).strip(), error_count, sorry_count


class LeanServerSession:
    """Single warm `lake env lean --server` or `lean --server` JSON-RPC 2.0 LSP worker."""

    def __init__(self, project_dir: str | Path | None = None, *, startup_timeout: float = 15.0) -> None:
        lean_bin = resolve_lean_executable("lean")
        lake_bin = resolve_lean_executable("lake")
        if lean_bin is None:
            raise RuntimeError("Lean 4 executable not found")

        self._owned_tmpdir: Path | None = None
        if project_dir is not None:
            self.cwd = Path(project_dir).resolve()
            has_lakefile = (self.cwd / "lakefile.toml").is_file() or (self.cwd / "lakefile.lean").is_file()
            if lake_bin is not None and has_lakefile:
                cmd = [lake_bin, "env", lean_bin, "--server"]
            else:
                cmd = [lean_bin, "--server"]
        else:
            self._owned_tmpdir = Path(tempfile.mkdtemp(prefix="pathweaver-lean-lsp-"))
            self.cwd = self._owned_tmpdir
            cmd = [lean_bin, "--server"]

        opts: dict[str, Any] = {
            "stdin": subprocess.PIPE,
            "stdout": subprocess.PIPE,
            "stderr": subprocess.PIPE,
            "bufsize": 0,
            "cwd": str(self.cwd),
        }
        if os.name == "nt":
            opts["creationflags"] = subprocess.CREATE_NO_WINDOW

        self._proc = subprocess.Popen(cmd, **opts)
        self._job = None
        if os.name == "nt" and WindowsJob is not None:
            try:
                self._job = WindowsJob(self._proc)
            except OSError:
                self._job = None

        self._write_lock = threading.Lock()
        self._closed = False
        self._next_id = 1
        self._doc_counter = 0
        self._version = 0
        self._uri: str | None = None
        self._opened = False
        self._msg_queue: queue.Queue[dict[str, Any] | None] = queue.Queue()
        self._stderr_tail: deque[str] = deque(maxlen=64)

        self._reader_thread = threading.Thread(target=self._reader_loop, daemon=True)
        self._stderr_thread = threading.Thread(target=self._stderr_loop, daemon=True)
        self._reader_thread.start()
        self._stderr_thread.start()

        try:
            self._initialize(startup_timeout)
        except Exception:
            self.close()
            raise

    def is_alive(self) -> bool:
        return not self._closed and self._proc.poll() is None

    def _next_request_id(self) -> int:
        req_id = self._next_id
        self._next_id += 1
        return req_id

    def _send_raw(self, payload: dict[str, Any]) -> None:
        if self._closed or self._proc.stdin is None:
            raise BrokenPipeError("Lean LSP session is closed")
        body = json.dumps(payload, separators=(",", ":")).encode("utf-8")
        frame = f"Content-Length: {len(body)}\r\n\r\n".encode("ascii") + body
        with self._write_lock:
            self._proc.stdin.write(frame)
            self._proc.stdin.flush()

    def _send_response(self, req_id: Any, result: Any) -> None:
        try:
            self._send_raw({"jsonrpc": "2.0", "id": req_id, "result": result})
        except OSError:
            pass

    def _reader_loop(self) -> None:
        stdout = self._proc.stdout
        if stdout is None:
            self._msg_queue.put(None)
            return
        try:
            while not self._closed:
                headers: dict[str, str] = {}
                while True:
                    line = stdout.readline()
                    if not line:
                        self._msg_queue.put(None)
                        return
                    text = line.decode("ascii", errors="replace").strip()
                    if not text:
                        break
                    if ":" in text:
                        key, value = text.split(":", 1)
                        headers[key.strip().lower()] = value.strip()
                length = int(headers.get("content-length", "0"))
                if length <= 0:
                    continue
                raw_body = _read_exact(stdout, length)
                if len(raw_body) < length:
                    self._msg_queue.put(None)
                    return
                try:
                    message = json.loads(raw_body.decode("utf-8", errors="replace"))
                except ValueError:
                    continue
                if isinstance(message, dict):
                    self._msg_queue.put(message)
        except OSError:
            self._msg_queue.put(None)

    def _stderr_loop(self) -> None:
        stderr = self._proc.stderr
        if stderr is None:
            return
        try:
            while not self._closed:
                line = stderr.readline()
                if not line:
                    break
                self._stderr_tail.append(line.decode("utf-8", errors="replace").rstrip())
        except OSError:
            pass

    def _initialize(self, timeout_seconds: float) -> None:
        init_id = self._next_request_id()
        self._send_raw({
            "jsonrpc": "2.0",
            "id": init_id,
            "method": "initialize",
            "params": {
                "processId": os.getpid(),
                "rootUri": self.cwd.as_uri(),
                "capabilities": {},
            },
        })
        deadline = time.monotonic() + max(1.0, timeout_seconds)
        while True:
            remaining = deadline - time.monotonic()
            if remaining <= 0:
                raise TimeoutError("Lean LSP initialize timed out")
            try:
                msg = self._msg_queue.get(timeout=remaining)
            except queue.Empty as exc:
                raise TimeoutError("Lean LSP initialize timed out") from exc
            if msg is None:
                raise RuntimeError("Lean LSP exited during initialize")
            if msg.get("id") == init_id and ("result" in msg or "error" in msg):
                if "error" in msg:
                    raise RuntimeError(f"Lean LSP initialize failed: {msg['error']}")
                break
            if "id" in msg and "method" in msg:
                self._send_response(msg["id"], None)
        self._send_raw({"jsonrpc": "2.0", "method": "initialized", "params": {}})

    def _drain_pending(self) -> None:
        while True:
            try:
                msg = self._msg_queue.get_nowait()
            except queue.Empty:
                break
            if msg is not None and "id" in msg and "method" in msg:
                self._send_response(msg["id"], None)

    def check_source(self, source: str, *, timeout_seconds: float = 60.0) -> dict[str, Any] | None:
        """Elaborate `source` on this warm LSP worker; return None on timeout/crash."""
        if not self.is_alive():
            return None
        self._drain_pending()
        try:
            if not self._opened:
                self._doc_counter += 1
                self._uri = (self.cwd / f"__pw_check_{self._doc_counter}.lean").as_uri()
                self._version = 1
                self._send_raw({
                    "jsonrpc": "2.0",
                    "method": "textDocument/didOpen",
                    "params": {
                        "textDocument": {
                            "uri": self._uri,
                            "languageId": "lean4",
                            "version": self._version,
                            "text": source,
                        }
                    },
                })
                self._opened = True
            else:
                self._version += 1
                self._send_raw({
                    "jsonrpc": "2.0",
                    "method": "textDocument/didChange",
                    "params": {
                        "textDocument": {"uri": self._uri, "version": self._version},
                        "contentChanges": [{"text": source}],
                    },
                })
        except OSError:
            return None

        target_version = self._version
        deadline = time.monotonic() + max(0.5, timeout_seconds)
        settle_deadline: float | None = None
        saw_done = False
        saw_diag = False
        latest_diags: list[dict[str, Any]] | None = None

        while True:
            now = time.monotonic()
            if now >= deadline:
                return None
            if settle_deadline is not None and now >= settle_deadline:
                break
            wait_for = deadline - now
            if settle_deadline is not None:
                wait_for = min(wait_for, max(0.005, settle_deadline - now))
            try:
                msg = self._msg_queue.get(timeout=wait_for)
            except queue.Empty:
                if saw_done:
                    break
                return None
            if msg is None:
                return None
            if "id" in msg and "method" in msg:
                self._send_response(msg["id"], None)
                continue
            method = msg.get("method")
            params = msg.get("params") or {}
            if method == "textDocument/publishDiagnostics":
                if params.get("uri") == self._uri and params.get("version") in (None, target_version):
                    raw = params.get("diagnostics")
                    latest_diags = list(raw) if isinstance(raw, list) else []
                    saw_diag = True
                    if saw_done:
                        settle_deadline = min(settle_deadline or deadline, time.monotonic() + 0.03)
            elif method == "$/lean/fileProgress":
                doc = params.get("textDocument") or {}
                if doc.get("uri") == self._uri and doc.get("version") in (None, target_version):
                    if params.get("processing") == []:
                        saw_done = True
                        grace = 0.05 if saw_diag else 0.30
                        settle_deadline = min(deadline, time.monotonic() + grace)

        if not saw_done or latest_diags is None:
            return None

        diagnostics, combined_out, error_count, sorry_count = _format_lsp_diagnostics(latest_diags)
        if not combined_out and self._stderr_tail:
            combined_out = "\n".join(self._stderr_tail).strip()
        return {
            "diagnostics": diagnostics,
            "combined_output": combined_out,
            "error_count": error_count,
            "sorry_count": sorry_count,
            "returncode": 1 if error_count > 0 else 0,
        }

    def close(self) -> None:
        if self._closed:
            return
        self._closed = True
        try:
            if self._proc.poll() is None and self._proc.stdin is not None:
                try:
                    self._send_raw({"jsonrpc": "2.0", "id": self._next_request_id(), "method": "shutdown", "params": None})
                    self._send_raw({"jsonrpc": "2.0", "method": "exit", "params": None})
                except OSError:
                    pass
                try:
                    self._proc.stdin.close()
                except OSError:
                    pass
        finally:
            if self._proc.poll() is None:
                try:
                    self._proc.terminate()
                    self._proc.wait(timeout=1.5)
                except (OSError, subprocess.TimeoutExpired):
                    try:
                        self._proc.kill()
                        self._proc.wait(timeout=1.5)
                    except (OSError, subprocess.TimeoutExpired):
                        pass
            if self._job is not None:
                try:
                    self._job.close()
                except Exception:
                    pass
                self._job = None
            for pipe in (self._proc.stdout, self._proc.stderr):
                if pipe is not None:
                    try:
                        pipe.close()
                    except OSError:
                        pass
            if self._owned_tmpdir is not None:
                shutil.rmtree(self._owned_tmpdir, ignore_errors=True)
                self._owned_tmpdir = None


class LeanServerPool:
    """Thread-safe bounded pool of warm Lean 4 LSP sessions keyed by Lake project directory."""

    def __init__(self, *, max_sessions_per_key: int = 2, max_total_sessions: int = 4) -> None:
        self._max_per_key = max(1, max_sessions_per_key)
        self._max_total = max(1, max_total_sessions)
        self._lock = threading.Lock()
        self._idle: dict[str, deque[LeanServerSession]] = {}
        self._active: set[LeanServerSession] = set()
        self._lru_keys: deque[str] = deque()

    @staticmethod
    def _project_key(project_dir: str | Path | None) -> tuple[str, Path | None]:
        if project_dir is None:
            return "", None
        resolved = Path(project_dir).resolve()
        return str(resolved), resolved

    def _total_idle_locked(self) -> int:
        return sum(len(bucket) for bucket in self._idle.values())

    def _evict_oldest_locked(self) -> list[LeanServerSession]:
        evicted: list[LeanServerSession] = []
        while self._total_idle_locked() > self._max_total and self._lru_keys:
            key = self._lru_keys.popleft()
            bucket = self._idle.get(key)
            if bucket:
                evicted.append(bucket.popleft())
                if not bucket:
                    self._idle.pop(key, None)
        return evicted

    def _acquire(self, project_dir: str | Path | None, startup_timeout: float) -> LeanServerSession | None:
        key, resolved = self._project_key(project_dir)
        stale: list[LeanServerSession] = []
        session: LeanServerSession | None = None
        with self._lock:
            bucket = self._idle.get(key)
            while bucket:
                cand = bucket.pop()
                if cand.is_alive():
                    session = cand
                    break
                stale.append(cand)
            if bucket is not None and not bucket:
                self._idle.pop(key, None)
        for dead in stale:
            dead.close()
        if session is None:
            try:
                session = LeanServerSession(resolved, startup_timeout=startup_timeout)
            except Exception:
                return None
        with self._lock:
            self._active.add(session)
        return session

    def _release(self, project_dir: str | Path | None, session: LeanServerSession, *, reusable: bool) -> None:
        key, _ = self._project_key(project_dir)
        to_close: list[LeanServerSession] = []
        with self._lock:
            self._active.discard(session)
            if not reusable or not session.is_alive():
                to_close.append(session)
            else:
                bucket = self._idle.setdefault(key, deque())
                if len(bucket) >= self._max_per_key:
                    to_close.append(bucket.popleft())
                bucket.append(session)
                self._lru_keys.append(key)
                to_close.extend(self._evict_oldest_locked())
        for item in to_close:
            item.close()

    def check_source(
        self,
        source: str,
        *,
        project_dir: str | Path | None = None,
        timeout_seconds: float = 60.0,
    ) -> dict[str, Any] | None:
        """Check `source` on a warm session; return None so caller can fall back cleanly."""
        session = self._acquire(project_dir, startup_timeout=min(15.0, max(5.0, timeout_seconds)))
        if session is None:
            return None
        result: dict[str, Any] | None = None
        try:
            result = session.check_source(source, timeout_seconds=timeout_seconds)
        except Exception:
            result = None
        finally:
            self._release(project_dir, session, reusable=(result is not None))
        return result

    def close_all(self) -> None:
        to_close: list[LeanServerSession] = []
        with self._lock:
            for bucket in self._idle.values():
                to_close.extend(bucket)
            self._idle.clear()
            self._lru_keys.clear()
            to_close.extend(self._active)
            self._active.clear()
        for session in to_close:
            session.close()


_POOL_LOCK = threading.Lock()
_DEFAULT_POOL: LeanServerPool | None = None


def get_default_lean_server_pool() -> LeanServerPool:
    """Return the process-wide warm Lean 4 LSP server pool singleton."""
    global _DEFAULT_POOL
    with _POOL_LOCK:
        if _DEFAULT_POOL is None:
            _DEFAULT_POOL = LeanServerPool()
        return _DEFAULT_POOL


def shutdown_default_lean_server_pool() -> None:
    """Terminate all warm Lean 4 LSP sessions cleanly (registered with `atexit`)."""
    global _DEFAULT_POOL
    with _POOL_LOCK:
        pool = _DEFAULT_POOL
        _DEFAULT_POOL = None
    if pool is not None:
        pool.close_all()


atexit.register(shutdown_default_lean_server_pool)

from __future__ import annotations

import inspect
import json
import runpy
import sys
import threading
import time
import traceback
from datetime import datetime, timezone
from pathlib import Path
from types import FrameType
from typing import Any


class RuntimeTracer:
    """
    sys.setprofile based tracer for factual CodeModel enrichment.

    Captures call, return and exception events inside a project root. It records
    concrete runtime types, but does not infer architecture.
    """

    def __init__(
        self,
        project_root: str | Path,
        output_path: str | Path,
        include_returns: bool = True,
        include_exceptions: bool = True,
        max_events: int = 20000,
        scenario_name: str | None = None,
        mode: str = "desktop",
    ):
        self.project_root = Path(project_root).resolve()
        self.output_path = Path(output_path).resolve()
        self.include_returns = include_returns
        self.include_exceptions = include_exceptions
        self.max_events = max_events
        self.scenario_name = scenario_name
        self.mode = mode
        self.events: list[dict[str, Any]] = []
        self.stack_by_thread: dict[int, list[str]] = {}
        self.started_at: str | None = None
        self.finished_at: str | None = None

    def run_script(self, script_path: str | Path, argv: list[str] | None = None) -> dict[str, Any]:
        script_path = Path(script_path)
        if not script_path.is_absolute():
            script_path = (self.project_root / script_path).resolve()
        if not script_path.exists():
            raise FileNotFoundError(f"Runtime scenario script not found: {script_path}")

        old_argv = sys.argv[:]
        old_path = sys.path[:]

        sys.argv = [str(script_path)] + list(argv or [])

        # runpy.run_path does not reliably add the scenario folder to sys.path.
        # Add both the scenario directory and project root so local helpers such
        # as _scenario_common.py can be imported.
        for candidate in [script_path.parent, self.project_root]:
            candidate_str = str(candidate)
            if candidate_str not in sys.path:
                sys.path.insert(0, candidate_str)

        error = None
        try:
            self.start()
            runpy.run_path(str(script_path), run_name="__main__")
            status = "completed"
        except SystemExit as exc:
            status = "system_exit"
            error = {"type": "SystemExit", "message": str(exc), "code": exc.code}
        except Exception as exc:
            status = "failed"
            error = {"type": type(exc).__name__, "message": str(exc), "traceback": traceback.format_exc()}
        finally:
            self.stop()
            sys.argv = old_argv
            sys.path = old_path

        trace = self.build_trace(status, error, str(script_path), argv or [])
        self.write_trace(trace)
        return trace

    def start(self) -> None:
        self.started_at = datetime.now(timezone.utc).isoformat()
        sys.setprofile(self._profile)
        threading.setprofile(self._profile)

    def stop(self) -> None:
        sys.setprofile(None)
        threading.setprofile(None)
        self.finished_at = datetime.now(timezone.utc).isoformat()

    def _profile(self, frame: FrameType, event: str, arg: Any) -> None:
        if len(self.events) >= self.max_events:
            return
        if event not in {"call", "return", "exception"}:
            return
        if event == "return" and not self.include_returns:
            return
        if event == "exception" and not self.include_exceptions:
            return

        file_path = Path(frame.f_code.co_filename).resolve()
        if not self._is_project_file(file_path):
            return

        thread_id = threading.get_ident()
        qname = self._qualified_name(frame, file_path)

        if event == "call":
            stack = self.stack_by_thread.setdefault(thread_id, [])
            caller = stack[-1] if stack else None
            stack.append(qname)
            self.events.append({
                "type": "call",
                "timestamp": time.time(),
                "thread_id": thread_id,
                "scenario": self.scenario_name,
                "mode": self.mode,
                "source": caller,
                "target": qname,
                "function": frame.f_code.co_name,
                "qualified_name": qname,
                "file": self._relative_file(file_path),
                "line": frame.f_lineno,
                "arg_types": self._argument_types(frame),
                "receiver_type": self._receiver_type(frame),
            })
            return

        if event == "return":
            self.events.append({
                "type": "return",
                "timestamp": time.time(),
                "thread_id": thread_id,
                "scenario": self.scenario_name,
                "mode": self.mode,
                "source": qname,
                "function": frame.f_code.co_name,
                "qualified_name": qname,
                "file": self._relative_file(file_path),
                "line": frame.f_lineno,
                "return_type": self._safe_type_name(arg),
            })
            stack = self.stack_by_thread.setdefault(thread_id, [])
            if stack and stack[-1] == qname:
                stack.pop()
            elif qname in stack:
                stack.remove(qname)
            return

        if event == "exception":
            exc_type, exc_value, _ = arg
            self.events.append({
                "type": "exception",
                "timestamp": time.time(),
                "thread_id": thread_id,
                "scenario": self.scenario_name,
                "mode": self.mode,
                "source": qname,
                "function": frame.f_code.co_name,
                "qualified_name": qname,
                "file": self._relative_file(file_path),
                "line": frame.f_lineno,
                "exception_type": self._safe_type_name(exc_type),
                "exception_message": str(exc_value),
            })

    def build_trace(self, status: str, error: dict[str, Any] | None, entrypoint: str, argv: list[str]) -> dict[str, Any]:
        return {
            "version": "1.0",
            "type": "runtime_trace",
            "generated_by": "kdm_dynamic_analysis.RuntimeTracer",
            "metadata": {
                "project_root": str(self.project_root),
                "entrypoint": entrypoint,
                "argv": argv,
                "scenario": self.scenario_name,
                "mode": self.mode,
                "started_at": self.started_at,
                "finished_at": self.finished_at,
                "execution_status": status,
                "execution_error": error,
                "trace_quality": "call_level",
                "event_count": len(self.events),
                "max_events": self.max_events,
                "web_ready": True,
            },
            "events": self.events,
        }

    def write_trace(self, trace: dict[str, Any]) -> None:
        self.output_path.parent.mkdir(parents=True, exist_ok=True)
        with self.output_path.open("w", encoding="utf-8") as handle:
            json.dump(trace, handle, indent=2, ensure_ascii=False)

    def _is_project_file(self, file_path: Path) -> bool:
        try:
            file_path.relative_to(self.project_root)
            return True
        except ValueError:
            return False

    def _relative_file(self, file_path: Path) -> str:
        try:
            return str(file_path.relative_to(self.project_root))
        except ValueError:
            return str(file_path)

    def _qualified_name(self, frame: FrameType, file_path: Path) -> str:
        module_name = self._module_name(file_path)
        function_name = frame.f_code.co_name
        receiver = frame.f_locals.get("self") or frame.f_locals.get("cls")
        if receiver is not None:
            receiver_type = receiver if inspect.isclass(receiver) else type(receiver)
            return f"{module_name}.{receiver_type.__name__}.{function_name}"
        return f"{module_name}.{function_name}"

    def _module_name(self, file_path: Path) -> str:
        try:
            relative = file_path.relative_to(self.project_root)
        except ValueError:
            return file_path.stem
        if relative.suffix == ".py":
            relative = relative.with_suffix("")
        return ".".join(part for part in relative.parts if part != "__init__")

    def _argument_types(self, frame: FrameType) -> dict[str, str]:
        info = inspect.getargvalues(frame)
        result = {}
        for name in info.args:
            if name in frame.f_locals:
                result[name] = self._safe_type_name(frame.f_locals[name])
        if info.varargs and info.varargs in frame.f_locals:
            result[info.varargs] = self._safe_type_name(frame.f_locals[info.varargs])
        if info.keywords and info.keywords in frame.f_locals:
            result[info.keywords] = self._safe_type_name(frame.f_locals[info.keywords])
        return result

    def _receiver_type(self, frame: FrameType) -> str | None:
        receiver = frame.f_locals.get("self") or frame.f_locals.get("cls")
        if receiver is None:
            return None
        return self._safe_type_name(receiver if not inspect.isclass(receiver) else receiver)

    def _safe_type_name(self, value: Any) -> str:
        cls = value if inspect.isclass(value) else type(value)
        module = getattr(cls, "__module__", "")
        name = getattr(cls, "__qualname__", getattr(cls, "__name__", str(cls)))
        return f"{module}.{name}" if module and module != "builtins" else name

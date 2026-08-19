"""Python-owned lifecycle and tool mediation for the governed Cline Node worker."""
from __future__ import annotations

import subprocess
import threading
from pathlib import Path
from typing import Callable, TextIO

from .cline_stdio_protocol import (
    PROTOCOL_VERSION,
    BridgeFrame,
    ProtocolError,
    parse_frame,
)
from .tool_orchestration import (
    GovernedToolOrchestrator,
    ToolExecutionContext,
    ToolRequest,
)


class BridgeProcessError(RuntimeError):
    """Raised when the bounded worker lifecycle fails closed."""


class GovernedClineWorker:
    """Own one bounded long-lived Node child and fail closed on protocol defects."""

    def __init__(
        self,
        *,
        node_executable: str = "node",
        worker_path: str | Path | None = None,
        startup_timeout_seconds: float = 10.0,
    ) -> None:
        default_worker = Path(__file__).with_name("cline_worker") / "worker.mjs"
        self.node_executable = node_executable
        self.worker_path = (
            Path(worker_path) if worker_path is not None else default_worker
        )
        self.startup_timeout_seconds = startup_timeout_seconds
        self._process: subprocess.Popen[str] | None = None
        self._seen_message_ids: set[str] = set()
        self._stderr_lines: list[str] = []
        self._stderr_thread: threading.Thread | None = None
        self._outbound_sequence = 0

    @property
    def is_running(self) -> bool:
        return self._process is not None and self._process.poll() is None

    @property
    def stderr_text(self) -> str:
        return "".join(self._stderr_lines)

    def start(self, frame: BridgeFrame) -> BridgeFrame:
        if self.is_running:
            raise BridgeProcessError("worker already running")
        if frame.message_type != "runtime.start":
            raise ValueError("start requires runtime.start frame")
        if not self.worker_path.is_file():
            raise FileNotFoundError(f"worker not found: {self.worker_path}")

        self._process = subprocess.Popen(
            [self.node_executable, str(self.worker_path)],
            cwd=self.worker_path.parent,
            shell=False,
            stdin=subprocess.PIPE,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True,
            encoding="utf-8",
            bufsize=1,
        )
        assert self._process.stdin is not None
        assert self._process.stdout is not None
        assert self._process.stderr is not None
        self._stderr_thread = threading.Thread(
            target=self._drain_stderr,
            args=(self._process.stderr,),
            daemon=True,
        )
        self._stderr_thread.start()
        self.send(frame)
        ready = self.read(timeout_seconds=self.startup_timeout_seconds)
        if ready.message_type != "runtime.ready":
            self.terminate()
            raise BridgeProcessError(
                f"expected runtime.ready, got {ready.message_type}"
            )
        return ready

    def send(self, frame: BridgeFrame) -> None:
        if (
            not self.is_running
            or self._process is None
            or self._process.stdin is None
        ):
            raise BridgeProcessError("worker is not running")
        self._process.stdin.write(frame.to_json_line())
        self._process.stdin.flush()

    def read(self, *, timeout_seconds: float = 10.0) -> BridgeFrame:
        if (
            not self.is_running
            or self._process is None
            or self._process.stdout is None
        ):
            raise BridgeProcessError("worker is not running")

        holder: list[str] = []
        done = threading.Event()

        def _reader() -> None:
            assert self._process is not None
            assert self._process.stdout is not None
            holder.append(self._process.stdout.readline())
            done.set()

        threading.Thread(target=_reader, daemon=True).start()
        if not done.wait(timeout_seconds):
            self.terminate()
            raise BridgeProcessError("worker response timeout")
        raw = holder[0]
        if raw == "":
            code = self._process.poll()
            raise BridgeProcessError(
                f"worker exited before protocol response: {code}"
            )

        try:
            frame = parse_frame(raw, expected_direction="node_to_python")
        except ProtocolError:
            self.terminate()
            raise

        if frame.message_id in self._seen_message_ids:
            self.terminate()
            raise ProtocolError(f"duplicate message_id: {frame.message_id}")
        self._seen_message_ids.add(frame.message_id)
        return frame

    def execute_turn(
        self,
        frame: BridgeFrame,
        *,
        orchestrator: GovernedToolOrchestrator,
        context: ToolExecutionContext,
        timeout_seconds: float = 60.0,
        on_provider_event: Callable[[BridgeFrame], None] | None = None,
    ) -> BridgeFrame:
        """Run one Cline turn while LBE remains the only executable-tool owner."""
        if frame.message_type != "turn.execute":
            raise ValueError("execute_turn requires turn.execute frame")
        if not isinstance(orchestrator, GovernedToolOrchestrator):
            raise TypeError("orchestrator must be GovernedToolOrchestrator")
        if not isinstance(context, ToolExecutionContext):
            raise TypeError("context must be ToolExecutionContext")

        self.send(frame)
        while True:
            response = self.read(timeout_seconds=timeout_seconds)
            if response.session_id != frame.session_id:
                self.terminate()
                raise ProtocolError("worker response session_id mismatch")
            if response.turn_id != frame.turn_id:
                self.terminate()
                raise ProtocolError("worker response turn_id mismatch")

            if response.message_type == "provider.event":
                if on_provider_event is not None:
                    on_provider_event(response)
                continue

            if response.message_type == "tool.proposed":
                self._mediate_tool_proposal(
                    response,
                    orchestrator=orchestrator,
                    context=context,
                )
                continue

            if response.message_type in {"turn.completed", "turn.failed"}:
                return response

            if response.message_type == "runtime.error":
                self.terminate()
                raise BridgeProcessError(
                    f"worker runtime error: {response.payload.get('code')}: "
                    f"{response.payload.get('message')}"
                )

            self.terminate()
            raise ProtocolError(
                f"unexpected worker frame during turn: {response.message_type}"
            )

    def cancel(self, frame: BridgeFrame) -> None:
        if frame.message_type != "control.cancel":
            raise ValueError("cancel requires control.cancel frame")
        self.send(frame)

    def shutdown(
        self, frame: BridgeFrame, *, timeout_seconds: float = 5.0
    ) -> BridgeFrame:
        if frame.message_type != "runtime.shutdown":
            raise ValueError("shutdown requires runtime.shutdown frame")
        self.send(frame)
        result = self.read(timeout_seconds=timeout_seconds)
        process = self._process
        if process is not None:
            if process.stdin is not None and not process.stdin.closed:
                process.stdin.close()
            try:
                process.wait(timeout=timeout_seconds)
            except subprocess.TimeoutExpired as exc:
                self.terminate()
                raise BridgeProcessError(
                    "worker did not exit after shutdown"
                ) from exc
        return result

    def terminate(self) -> None:
        process = self._process
        if process is None:
            return
        if process.poll() is None:
            process.terminate()
            try:
                process.wait(timeout=2.0)
            except subprocess.TimeoutExpired:
                process.kill()
                process.wait(timeout=2.0)

    def _mediate_tool_proposal(
        self,
        proposal: BridgeFrame,
        *,
        orchestrator: GovernedToolOrchestrator,
        context: ToolExecutionContext,
    ) -> None:
        tool_id = proposal.payload.get("tool_id")
        arguments = proposal.payload.get("arguments", {})
        if not isinstance(tool_id, str) or not tool_id.strip():
            self.terminate()
            raise ProtocolError("tool.proposed requires payload.tool_id")
        if not isinstance(arguments, dict):
            self.terminate()
            raise ProtocolError("tool.proposed payload.arguments must be an object")
        if not proposal.cline_tool_call_id:
            self.terminate()
            raise ProtocolError("tool.proposed requires cline_tool_call_id")
        if not proposal.lbe_call_id:
            self.terminate()
            raise ProtocolError("tool.proposed requires lbe_call_id")
        if not proposal.operation_id:
            self.terminate()
            raise ProtocolError("tool.proposed requires operation_id")

        receipt = orchestrator.invoke(
            ToolRequest(
                operation_id=proposal.operation_id,
                tool_id=tool_id,
                arguments=arguments,
                context=context,
            )
        )
        result = BridgeFrame(
            protocol_version=PROTOCOL_VERSION,
            message_id=self._next_message_id("tool-result"),
            message_type="tool.result",
            session_id=proposal.session_id,
            turn_id=proposal.turn_id,
            payload={
                "status": receipt.status.value,
                "output": dict(receipt.output or {}),
                "evidence": [dict(item) for item in receipt.evidence],
                "error_code": receipt.error_code,
                "error_message": receipt.error_message,
            },
            cline_tool_call_id=proposal.cline_tool_call_id,
            lbe_call_id=proposal.lbe_call_id,
            operation_id=proposal.operation_id,
            receipt_id=receipt.receipt_id,
        )
        self.send(result)

    def _next_message_id(self, prefix: str) -> str:
        self._outbound_sequence += 1
        return f"py-{prefix}-{self._outbound_sequence}"

    def _drain_stderr(self, stream: TextIO) -> None:
        for line in stream:
            self._stderr_lines.append(line)

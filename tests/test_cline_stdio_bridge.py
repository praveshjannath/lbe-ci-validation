from __future__ import annotations

import contextlib
import json
import threading
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path

import pytest

from lbe_guard_inspector.runtime.cline_stdio_bridge import GovernedClineWorker
from lbe_guard_inspector.runtime.cline_stdio_protocol import (
    PROTOCOL_VERSION,
    BridgeFrame,
    ProtocolError,
    parse_frame,
)
from lbe_guard_inspector.runtime.mode_controller import ModeDecision
from lbe_guard_inspector.runtime.tool_orchestration import (
    GovernedToolOrchestrator,
    ToolExecutionContext,
    ToolExecutionResult,
    ToolRegistry,
    workspace_read_spec,
)


def _frame(
    message_type: str,
    message_id: str = "py-1",
    payload: dict | None = None,
) -> BridgeFrame:
    return BridgeFrame(
        protocol_version=PROTOCOL_VERSION,
        message_id=message_id,
        message_type=message_type,
        session_id="session-1",
        turn_id="turn-1",
        payload=payload or {},
    )


def _context(tmp_path: Path, *capabilities: str) -> ToolExecutionContext:
    return ToolExecutionContext(
        mode_decision=ModeDecision(
            mode="coding",
            allowed_behaviors=("development_mode_capabilities",),
            capabilities=tuple(capabilities),
            rationale="test",
        ),
        workspace_id="workspace-1",
        workspace_root=tmp_path,
        configured_root_id="dev",
    )


class _OpenAIStubHandler(BaseHTTPRequestHandler):
    protocol_version = "HTTP/1.1"

    def log_message(self, format, *args):  # noqa: A003
        return

    def do_POST(self) -> None:  # noqa: N802
        length = int(self.headers.get("content-length", "0"))
        raw = self.rfile.read(length)
        request = json.loads(raw.decode("utf-8")) if raw else {}
        self.server.requests.append({"path": self.path, "body": request})
        if not self.server.responses:
            self.send_error(500, "no scripted response")
            return
        chunks = self.server.responses.pop(0)
        lines = [f"data: {json.dumps(chunk)}\n\n" for chunk in chunks]
        lines.append("data: [DONE]\n\n")
        body = "".join(lines).encode("utf-8")
        self.send_response(200)
        self.send_header("Content-Type", "text/event-stream")
        self.send_header("Content-Length", str(len(body)))
        self.send_header("Connection", "close")
        self.end_headers()
        self.wfile.write(body)
        self.wfile.flush()


class _OpenAIStubServer(ThreadingHTTPServer):
    def __init__(self, responses):
        super().__init__(("127.0.0.1", 0), _OpenAIStubHandler)
        self.responses = list(responses)
        self.requests = []


@contextlib.contextmanager
def _openai_stub(responses):
    server = _OpenAIStubServer(responses)
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    try:
        yield server, f"http://127.0.0.1:{server.server_port}/v1"
    finally:
        server.shutdown()
        server.server_close()
        thread.join(timeout=2)


def _text_response(text: str):
    return [
        {
            "id": "chatcmpl-test",
            "object": "chat.completion.chunk",
            "created": 1,
            "model": "gpt-4o",
            "choices": [
                {
                    "index": 0,
                    "delta": {"role": "assistant", "content": text},
                    "finish_reason": None,
                }
            ],
        },
        {
            "id": "chatcmpl-test",
            "object": "chat.completion.chunk",
            "created": 1,
            "model": "gpt-4o",
            "choices": [
                {"index": 0, "delta": {}, "finish_reason": "stop"}
            ],
            "usage": {
                "prompt_tokens": 1,
                "completion_tokens": 1,
                "total_tokens": 2,
            },
        },
    ]


def _tool_call_response():
    return [
        {
            "id": "chatcmpl-tool",
            "object": "chat.completion.chunk",
            "created": 1,
            "model": "gpt-4o",
            "choices": [
                {
                    "index": 0,
                    "delta": {
                        "role": "assistant",
                        "tool_calls": [
                            {
                                "index": 0,
                                "id": "call_workspace_read_1",
                                "type": "function",
                                "function": {
                                    "name": "lbe_0_workspace_read",
                                    "arguments": '{"path":"README.md"}',
                                },
                            }
                        ],
                    },
                    "finish_reason": None,
                }
            ],
        },
        {
            "id": "chatcmpl-tool",
            "object": "chat.completion.chunk",
            "created": 1,
            "model": "gpt-4o",
            "choices": [
                {"index": 0, "delta": {}, "finish_reason": "tool_calls"}
            ],
            "usage": {
                "prompt_tokens": 1,
                "completion_tokens": 1,
                "total_tokens": 2,
            },
        },
    ]


def _provider_payload(base_url: str, *, allowed_tools=None) -> dict:
    return {
        "provider": {
            "provider_id": "openai-compatible",
            "model_id": "gpt-4o",
            "api_key": "super-secret-never-echo",
            "base_url": base_url,
        },
        "allowed_tools": allowed_tools or [],
        "system_prompt": "Return concise test output.",
        "max_iterations": 4,
    }


def test_valid_protocol_frame_round_trips() -> None:
    frame = _frame("runtime.start", payload={"allowed_tools": []})
    parsed = parse_frame(
        frame.to_json_line(), expected_direction="python_to_node"
    )
    assert parsed == frame


@pytest.mark.parametrize(
    "raw, message",
    [
        ("not-json", "malformed JSON frame"),
        (
            json.dumps(
                {
                    "protocol_version": "wrong",
                    "message_id": "1",
                    "message_type": "runtime.ready",
                    "session_id": "s",
                    "turn_id": "t",
                }
            ),
            "unsupported protocol_version",
        ),
        (
            json.dumps(
                {
                    "protocol_version": PROTOCOL_VERSION,
                    "message_id": "1",
                    "message_type": "unknown",
                    "session_id": "s",
                    "turn_id": "t",
                }
            ),
            "unknown message_type",
        ),
    ],
)
def test_protocol_rejects_malformed_or_unknown_frames(
    raw: str, message: str
) -> None:
    with pytest.raises(ProtocolError, match=message):
        parse_frame(raw)


def test_protocol_preserves_tool_identity_chain() -> None:
    frame = BridgeFrame(
        protocol_version=PROTOCOL_VERSION,
        message_id="node-1",
        message_type="tool.proposed",
        session_id="session-1",
        turn_id="turn-1",
        payload={"tool_id": "workspace.read", "arguments": {"path": "README.md"}},
        cline_tool_call_id="cline-call-1",
        lbe_call_id="lbe-call-1",
        operation_id="operation-1",
    )
    parsed = parse_frame(
        frame.to_json_line(), expected_direction="node_to_python"
    )
    assert parsed.cline_tool_call_id == "cline-call-1"
    assert parsed.lbe_call_id == "lbe-call-1"
    assert parsed.operation_id == "operation-1"


def test_real_worker_startup_and_shutdown_reports_pinned_cline_runtime() -> None:
    worker = GovernedClineWorker()
    ready = worker.start(
        _frame(
            "runtime.start",
            payload={"allowed_tools": [{"tool_id": "workspace.read"}]},
        )
    )
    assert ready.message_type == "runtime.ready"
    assert ready.payload["cline_agents_version"] == "0.0.75"
    assert ready.payload["agent_runtime_export"] is True
    assert ready.payload["create_agent_runtime_export"] is True
    assert ready.payload["provider_configured"] is False
    assert ready.payload["allowed_tool_ids"] == ["workspace.read"]
    assert ready.payload["native_mutation_tools_registered"] is False

    completed = worker.shutdown(
        _frame("runtime.shutdown", message_id="py-2")
    )
    assert completed.message_type == "turn.completed"
    assert completed.payload == {"shutdown": True}
    assert not worker.is_running


def test_worker_exposes_only_explicit_allowlist() -> None:
    worker = GovernedClineWorker()
    ready = worker.start(
        _frame("runtime.start", payload={"allowed_tools": []})
    )
    assert ready.payload["allowed_tool_ids"] == []
    assert ready.payload["native_mutation_tools_registered"] is False
    worker.shutdown(_frame("runtime.shutdown", message_id="py-2"))


def test_turn_execution_without_provider_fails_truthfully() -> None:
    worker = GovernedClineWorker()
    worker.start(_frame("runtime.start", payload={"allowed_tools": []}))
    worker.send(
        _frame(
            "turn.execute",
            message_id="py-2",
            payload={"text": "hello"},
        )
    )
    result = worker.read()
    assert result.message_type == "turn.failed"
    assert result.payload["code"] == "PROVIDER_RUNTIME_NOT_CONFIGURED"
    worker.shutdown(_frame("runtime.shutdown", message_id="py-3"))


def test_provider_configured_startup_does_not_echo_api_key() -> None:
    with _openai_stub([_text_response("hello")]) as (_, base_url):
        worker = GovernedClineWorker()
        ready = worker.start(_frame("runtime.start", payload=_provider_payload(base_url)))
        assert ready.payload["provider_configured"] is True
        assert ready.payload["provider"] == {
            "provider_id": "openai-compatible",
            "model_id": "gpt-4o",
        }
        assert "super-secret-never-echo" not in ready.to_json_line()
        worker.shutdown(_frame("runtime.shutdown", message_id="py-2"))


def test_invalid_cline_provider_maps_failed_run_to_turn_failed(tmp_path: Path) -> None:
    worker = GovernedClineWorker()
    worker.start(
        _frame(
            "runtime.start",
            payload={
                "provider": {
                    "provider_id": "definitely-not-a-provider",
                    "model_id": "gpt-4o",
                },
                "allowed_tools": [],
            },
        )
    )
    result = worker.execute_turn(
        _frame("turn.execute", message_id="py-2", payload={"text": "hello"}),
        orchestrator=GovernedToolOrchestrator(registry=ToolRegistry()),
        context=_context(tmp_path, "inspect"),
        timeout_seconds=15,
    )
    assert result.message_type == "turn.failed"
    assert result.payload["code"] == "CLINE_AGENTRUNTIME_FAILED"
    assert "Unknown or disabled provider" in result.payload["message"]
    assert result.payload["status"] == "failed"
    worker.shutdown(_frame("runtime.shutdown", message_id="py-3"))


def test_local_provider_turn_completes_through_real_cline_runtime(tmp_path: Path) -> None:
    with _openai_stub([_text_response("hello from cline")]) as (server, base_url):
        worker = GovernedClineWorker()
        worker.start(_frame("runtime.start", payload=_provider_payload(base_url)))
        result = worker.execute_turn(
            _frame("turn.execute", message_id="py-2", payload={"text": "hello"}),
            orchestrator=GovernedToolOrchestrator(registry=ToolRegistry()),
            context=_context(tmp_path, "inspect"),
            timeout_seconds=15,
        )
        assert result.message_type == "turn.completed"
        assert result.payload["status"] == "completed"
        assert result.payload["output_text"] == "hello from cline"
        assert result.payload["lbe_completion_truth"] is False
        assert len(server.requests) == 1
        assert server.requests[0]["path"] == "/v1/chat/completions"
        worker.shutdown(_frame("runtime.shutdown", message_id="py-3"))


def test_cline_tool_call_routes_through_governed_orchestrator_and_continues(
    tmp_path: Path,
) -> None:
    calls = []

    def handler(request):
        calls.append(request)
        return ToolExecutionResult(
            output={"path": "README.md", "content": "governed-result"},
            evidence=({"ref": "workspace:README.md", "verified": True},),
        )

    registry = ToolRegistry()
    registry.register(workspace_read_spec(), handler)
    orchestrator = GovernedToolOrchestrator(registry=registry)
    allowed_tools = [
        {
            "tool_id": "workspace.read",
            "description": "Read one file through the LBE governed workspace owner.",
            "input_schema": {
                "type": "object",
                "properties": {"path": {"type": "string"}},
                "required": ["path"],
                "additionalProperties": False,
            },
            "timeout_ms": 10_000,
        }
    ]
    with _openai_stub([_tool_call_response(), _text_response("tool complete")]) as (
        server,
        base_url,
    ):
        worker = GovernedClineWorker()
        worker.start(
            _frame(
                "runtime.start",
                payload=_provider_payload(base_url, allowed_tools=allowed_tools),
            )
        )
        result = worker.execute_turn(
            _frame(
                "turn.execute",
                message_id="py-2",
                payload={"text": "Read README.md then finish."},
            ),
            orchestrator=orchestrator,
            context=_context(tmp_path, "inspect"),
            timeout_seconds=15,
        )
        assert result.message_type == "turn.completed"
        assert result.payload["output_text"] == "tool complete"
        assert len(calls) == 1
        assert calls[0].tool_id == "workspace.read"
        assert calls[0].arguments == {"path": "README.md"}
        assert calls[0].operation_id.startswith("turn-1:tool:")
        assert orchestrator.receipt(calls[0].operation_id) is not None
        assert len(server.requests) == 2
        worker.shutdown(_frame("runtime.shutdown", message_id="py-3"))
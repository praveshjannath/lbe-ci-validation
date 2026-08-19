from __future__ import annotations

import json
from dataclasses import asdict
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from typing import Any, Mapping, Protocol
from urllib.parse import urlparse

from agent import (
    CONFIG_PATH, Context, GovernanceError, database_status,
    inspect_file, load_json, search_workspace
)
from lbe_guard_inspector.callback_vertical_slice import CallbackVerticalSlice
from lbe_guard_inspector.module_registry_vertical_slice import ModuleRegistryVerticalSlice
from lbe_guard_inspector.reasoning_config import load_provider_config
from lbe_guard_inspector.reasoning_contracts import LBERequest, LBEResponse
from lbe_guard_inspector.reasoning_runtime import build_openai_compatible_controller

_INSPECTION_FIELDS = frozenset({"workspace_root", "workspace_id", "reason", "max_results"})
_MAX_INSPECTION_RESULTS = 50
_REASONING_FIELDS = frozenset({
    "problem", "workspace_root", "reference_context", "task_id", "max_results"
})


class _ReasoningController(Protocol):
    def run(self, request: LBERequest) -> LBEResponse: ...


def _inspection_kwargs(payload: Mapping[str, Any], *, label: str) -> dict[str, Any]:
    unknown = sorted(set(payload) - _INSPECTION_FIELDS)
    if unknown:
        raise GovernanceError(f"Unsupported {label} inspection fields: {unknown}")

    workspace_root = payload.get("workspace_root")
    if not isinstance(workspace_root, str) or not workspace_root.strip():
        raise GovernanceError("'workspace_root' must be a non-empty string")

    workspace_id = payload.get("workspace_id")
    if workspace_id is not None and (
        not isinstance(workspace_id, str) or not workspace_id.strip()
    ):
        raise GovernanceError("'workspace_id' must be a non-empty string when provided")

    reason = payload.get("reason")
    if reason is not None and (not isinstance(reason, str) or not reason.strip()):
        raise GovernanceError("'reason' must be a non-empty string when provided")

    max_results = payload.get("max_results", 10)
    if isinstance(max_results, bool) or not isinstance(max_results, int):
        raise GovernanceError("'max_results' must be an integer")
    if max_results < 1 or max_results > _MAX_INSPECTION_RESULTS:
        raise GovernanceError(
            f"'max_results' must be between 1 and {_MAX_INSPECTION_RESULTS}"
        )

    kwargs: dict[str, Any] = {
        "workspace_root": workspace_root,
        "max_results": max_results,
    }
    if workspace_id is not None:
        kwargs["workspace_id"] = workspace_id
    if reason is not None:
        kwargs["reason"] = reason
    return kwargs


def _reasoning_request(payload: Mapping[str, Any]) -> LBERequest:
    unknown = sorted(set(payload) - _REASONING_FIELDS)
    if unknown:
        raise GovernanceError(f"Unsupported reasoning fields: {unknown}")

    problem = payload.get("problem")
    if not isinstance(problem, str) or not problem.strip():
        raise GovernanceError("'problem' must be a non-empty string")

    workspace_root = payload.get("workspace_root")
    if not isinstance(workspace_root, str) or not workspace_root.strip():
        raise GovernanceError("'workspace_root' must be a non-empty string")

    reference_context = payload.get("reference_context", [])
    if not isinstance(reference_context, list) or not all(
        isinstance(item, Mapping) for item in reference_context
    ):
        raise GovernanceError("'reference_context' must be an array of objects")

    task_id = payload.get("task_id")
    if task_id is not None and (not isinstance(task_id, str) or not task_id.strip()):
        raise GovernanceError("'task_id' must be a non-empty string when provided")

    max_results = payload.get("max_results", 10)
    if isinstance(max_results, bool) or not isinstance(max_results, int):
        raise GovernanceError("'max_results' must be an integer")
    if max_results < 1 or max_results > _MAX_INSPECTION_RESULTS:
        raise GovernanceError(
            f"'max_results' must be between 1 and {_MAX_INSPECTION_RESULTS}"
        )

    return LBERequest(
        problem=problem.strip(),
        workspace_root=workspace_root.strip(),
        reference_context=tuple(dict(item) for item in reference_context),
        task_id=task_id.strip() if isinstance(task_id, str) else None,
        max_results=max_results,
    )


def run_callback_inspection(payload: Mapping[str, Any]) -> dict[str, Any]:
    """Validate and invoke the fixed read-only callback Guard Inspector slice."""
    return CallbackVerticalSlice().run(**_inspection_kwargs(payload, label="callback"))


def run_module_registry_inspection(payload: Mapping[str, Any]) -> dict[str, Any]:
    """Validate and invoke the fixed read-only module-registry Guard Inspector slice."""
    return ModuleRegistryVerticalSlice().run(
        **_inspection_kwargs(payload, label="module registry")
    )


class Handler(BaseHTTPRequestHandler):
    server_version = "CEPKnowledgeAgent/0.8-guard-inspector"
    reasoning_controller: _ReasoningController | None = None

    def send_json(self, status: int, payload: dict) -> None:
        body = json.dumps(payload, ensure_ascii=False, indent=2).encode("utf-8")
        self.send_response(status)
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.send_header("Content-Length", str(len(body)))
        self.send_header("Cache-Control", "no-store")
        self.end_headers()
        self.wfile.write(body)

    def read_json(self) -> dict:
        try:
            length = int(self.headers.get("Content-Length", "0"))
        except ValueError as exc:
            raise GovernanceError("Invalid Content-Length") from exc
        if length <= 0:
            return {}
        if length > 2_000_000:
            raise GovernanceError("Request body exceeds 2 MB")
        try:
            payload = json.loads(self.rfile.read(length).decode("utf-8"))
        except (UnicodeDecodeError, json.JSONDecodeError) as exc:
            raise GovernanceError("Request must contain valid UTF-8 JSON") from exc
        if not isinstance(payload, dict):
            raise GovernanceError("Request JSON must be an object")
        return payload

    def do_GET(self) -> None:
        try:
            path = urlparse(self.path).path
            if path == "/health":
                ctx = Context.load()
                self.send_json(200, {
                    "status": "ok",
                    "mode": "read-only-sqlite",
                    "roots": [root.name for root in ctx.roots],
                })
                return
            if path == "/roots":
                ctx = Context.load()
                self.send_json(200, {
                    "knowledge_roots": [
                        {"name": root.name, "path": str(root.path)}
                        for root in ctx.roots
                    ]
                })
                return
            if path == "/status":
                self.send_json(200, database_status())
                return
            self.send_json(404, {"error": "not_found", "path": path})
        except (GovernanceError, FileNotFoundError, RuntimeError) as exc:
            self.send_json(400, {"error": type(exc).__name__, "message": str(exc)})
        except Exception as exc:
            self.send_json(500, {"error": type(exc).__name__, "message": str(exc)})

    def do_POST(self) -> None:
        try:
            path = urlparse(self.path).path
            payload = self.read_json()

            if path == "/reasoning/run":
                controller = self.reasoning_controller
                if controller is None:
                    raise GovernanceError("Reasoning controller is not configured")
                result = asdict(controller.run(_reasoning_request(payload)))
            elif path == "/guard-inspector/callback":
                result = run_callback_inspection(payload)
            elif path == "/guard-inspector/module-registry":
                result = run_module_registry_inspection(payload)
            elif path == "/inspect":
                ctx = Context.load()
                value = payload.get("path")
                if not isinstance(value, str):
                    raise GovernanceError("'path' must be a string")
                result = inspect_file(ctx, value)
            elif path == "/search":
                ctx = Context.load()
                query = payload.get("query")
                if not isinstance(query, str):
                    raise GovernanceError("'query' must be a string")
                extensions = payload.get("extensions")
                roots = payload.get("roots")
                if extensions is not None and not isinstance(extensions, list):
                    raise GovernanceError("'extensions' must be an array")
                if roots is not None and not isinstance(roots, list):
                    raise GovernanceError("'roots' must be an array")
                result = search_workspace(
                    ctx,
                    query,
                    max_results=int(payload.get("max_results", 50)),
                    extensions=extensions,
                    roots=roots,
                )
            elif path in {"/trace", "/apply", "/validate", "/propose"}:
                raise GovernanceError(
                    "This HTTP server is read-only. Run traces directly in PowerShell."
                )
            else:
                self.send_json(404, {"error": "not_found", "path": path})
                return

            self.send_json(200, result)
        except (GovernanceError, FileNotFoundError, ValueError, RuntimeError) as exc:
            self.send_json(400, {"error": type(exc).__name__, "message": str(exc)})
        except Exception as exc:
            self.send_json(500, {"error": type(exc).__name__, "message": str(exc)})

    def log_message(self, format: str, *args) -> None:
        return


def make_handler(reasoning_controller: _ReasoningController) -> type[Handler]:
    """Bind one explicit reasoning controller without global runtime mutation."""
    if reasoning_controller is None:
        raise TypeError("reasoning_controller is required")

    class BoundHandler(Handler):
        pass

    BoundHandler.reasoning_controller = reasoning_controller
    return BoundHandler


def _startup_handler(
    config: Mapping[str, Any],
    *,
    config_path=CONFIG_PATH,
) -> type[Handler]:
    """Build the root handler with reasoning disabled unless explicitly configured."""
    provider_config_value = config.get("reasoning_provider_config")
    if provider_config_value is None:
        return Handler
    if not isinstance(provider_config_value, str) or not provider_config_value.strip():
        raise GovernanceError(
            "'reasoning_provider_config' must be a non-empty string when supplied"
        )

    provider_config_path = config_path.parent / provider_config_value.strip()
    provider_config = load_provider_config(provider_config_path)
    controller = build_openai_compatible_controller(
        provider_config=provider_config
    )
    return make_handler(controller)


def main() -> None:
    config = load_json(CONFIG_PATH)
    host = str(config.get("server_host", "127.0.0.1"))
    if host not in {"127.0.0.1", "localhost"}:
        raise GovernanceError("Server host must remain local-only")
    port = int(config.get("server_port", 8765))
    handler = _startup_handler(config)
    server = ThreadingHTTPServer((host, port), handler)
    print(f"CEP/LBE SQLite agent listening on http://{host}:{port}")
    print("Mode: read-only local retrieval and fixed guard inspection")
    print(
        "Endpoints: GET /health, GET /roots, GET /status, POST /search, "
        "POST /inspect, POST /guard-inspector/callback, "
        "POST /guard-inspector/module-registry"
    )
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        print("\nServer stopped.")
    finally:
        server.server_close()


if __name__ == "__main__":
    main()

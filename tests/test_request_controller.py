from __future__ import annotations

from pathlib import Path

import pytest

from agent import Context, KnowledgeRoot
from lbe_guard_inspector.proposal_planner import ProposalOutcome
from lbe_guard_inspector.request_controller import LBERequestController
from lbe_guard_inspector.reasoning_contracts import LBERequest


class FakeBackend:
    def __init__(self, plan, explanation={"explanation": "Deterministic result explained."}):
        self.plan_value = plan
        self.explanation_value = explanation
        self.plan_requests = []
        self.explanation_requests = []

    def plan(self, request):
        self.plan_requests.append(request)
        if isinstance(self.plan_value, Exception):
            raise self.plan_value
        return self.plan_value

    def explain(self, request):
        self.explanation_requests.append(request)
        if isinstance(self.explanation_value, Exception):
            raise self.explanation_value
        return self.explanation_value


class FakeRunner:
    def __init__(self, verdict="PASS", contradictions=()):
        self.calls = []
        self.verdict = verdict
        self.contradictions = tuple(contradictions)

    def run(self, **kwargs):
        self.calls.append(kwargs)
        workspace_id = kwargs["workspace_id"]
        evidence = [] if self.verdict == "INSUFFICIENT_EVIDENCE" else [_evidence(workspace_id, kwargs["workspace_root"])]
        validation = [] if self.verdict == "INSUFFICIENT_EVIDENCE" else [_validation(workspace_id, kwargs["workspace_root"])]
        return {
            "guard_result": {
                "result_id": "gr-1", "guard_id": kwargs["guard_id"], "guard_version": None,
                "workspace_id": workspace_id, "verdict": self.verdict, "summary": "deterministic",
                "findings": [], "evidence_refs": [item["ref"] for item in evidence], "validation_refs": [item["ref"] for item in validation],
                "governance_state": "READ_ONLY", "executed_at": "2026-07-30T00:00:00+00:00",
            },
            "evidence_package": {
                "package_id": "ep-1", "task_id": "task-1", "query": "CSXS/manifest.xml", "workspace_id": workspace_id,
                "indexed_reference_evidence": [], "current_workspace_evidence": evidence,
                "validation_evidence": validation, "contradictions": list(self.contradictions), "missing_evidence": [],
                "generated_at": "2026-07-30T00:00:00+00:00",
            },
        }


class FakeEvidenceService:
    def __init__(self, package):
        self.package = package
        self.calls = []

    def build_evidence_package(self, **kwargs):
        self.calls.append(kwargs)
        if kwargs.get("retrieval_mode") == "guard":
            return {
                **self.package,
                "current_workspace_evidence": [
                    {
                        "ref": "workspace:test:CSXS/manifest.xml",
                        "path": "CSXS/manifest.xml",
                        "source_type": "workspace",
                        "authority": 9,
                        "verified": True,
                        "classification": "source",
                    }
                ],
            }
        return self.package


def _evidence(workspace_id: str, root: str):
    return {
        "ref": f"workspace:{workspace_id}:CSXS/manifest.xml", "source_type": "workspace", "record_id": None,
        "workspace_id": workspace_id, "path": str(Path(root) / "CSXS" / "manifest.xml"), "hash": "a" * 64,
        "line_start": 1, "line_end": 1, "snippet": "manifest", "score": None, "matched_terms": [],
        "exact_phrase": None, "authority": 9, "verified": True, "classification": "source", "metadata": {},
    }


def _validation(workspace_id: str, root: str):
    value = _evidence(workspace_id, root)
    return {**value, "ref": f"validation:{workspace_id}:CSXS/manifest.xml", "source_type": "validation"}


def _plan(**overrides):
    value = {
        "interpreted_problem": "Inspect the canonical CEP manifest.", "ambiguities": [],
        "candidate_guard_ids": ["cep.manifest_exists"],
        "evidence_requests": [{"tool_id": "workspace.read", "path": "CSXS/manifest.xml", "reason": "canonical manifest"}],
        "validation_requests": [], "explanation_focus": ["state current evidence"],
    }
    value.update(overrides)
    return value


def _proposal_candidate(**overrides):
    value = {
        "target_profile_path": "profile.json",
        "trigger": "missing protection",
        "rationale": "verify evidence",
        "scope": ["CSXS/manifest.xml"],
        "required_action": "Define a deterministic guard.",
        "severity": "error",
        "exceptions": [],
        "validation_plan": ["run focused validation"],
        "rollback_plan": ["do not apply"],
    }
    value.update(overrides)
    return value


class FakeProposalPlanner:
    def __init__(self, outcome=None, proposal=None):
        self.calls = []
        self.outcome = outcome
        self.proposal = proposal

    def build(self, **kwargs):
        self.calls.append(kwargs)
        if self.outcome is not None:
            return self.outcome
        return ProposalOutcome(self.proposal, None, read_only=True)


def _evidence_package(indexed=None, current=None, validation=None):
    return {
        "package_id": "ep-reasoning",
        "task_id": "task-1",
        "query": "Why did this fail?",
        "workspace_id": "workspace-test",
        "indexed_reference_evidence": indexed or [],
        "current_workspace_evidence": current or [],
        "validation_evidence": validation or [],
        "contradictions": [],
        "missing_evidence": [],
        "generated_at": "2026-07-30T00:00:00+00:00",
    }


def _controller(
    tmp_path: Path,
    backend: FakeBackend,
    runner: FakeRunner | None = None,
    evidence_service: FakeEvidenceService | None = None,
    proposal_planner: FakeProposalPlanner | None = None,
):
    configured = tmp_path / "configured"; configured.mkdir()
    workspace = configured / "project"; (workspace / "CSXS").mkdir(parents=True)
    (workspace / "CSXS" / "manifest.xml").write_text("<ExtensionManifest/>", encoding="utf-8")
    context = Context(config={}, governance={}, roots=(KnowledgeRoot("dev", configured),))
    resolved_runner = runner or FakeRunner()
    resolved_evidence = evidence_service or FakeEvidenceService(_evidence_package())
    controller = LBERequestController(
        backend=backend, context=context, runner=resolved_runner,
        evidence_service=resolved_evidence, proposal_planner=proposal_planner,
        rule_resolver=lambda pack, rule: object() if (pack, rule) == ("cep", "cep.manifest_exists") else (_ for _ in ()).throw(ValueError("unregistered")),
    )
    return controller, resolved_runner, workspace


def _run(controller, workspace):
    return controller.run(LBERequest(problem="Why did this fail?", workspace_root=workspace, task_id="task-1"))


def test_valid_typed_plan_runs_registered_guard_and_preserves_verdict(tmp_path):
    backend = FakeBackend(_plan())
    controller, runner, workspace = _controller(tmp_path, backend)
    response = _run(controller, workspace)
    assert response.outcome == "COMPLETED"
    assert runner.calls[0]["guard_id"] == "cep.manifest_exists"
    assert runner.calls[0]["extensions"] == (".xml",)
    assert runner.calls[0]["path_patterns"] == ["CSXS/manifest.xml"]
    assert runner.calls[0]["evidence_requirements"] == ["canonical CEP manifest"]
    assert runner.calls[0]["reason"] == "controller-selected guard inspection: cep.manifest_exists"
    assert response.deterministic_result["verdict"] == "PASS"
    assert response.explanation.explanation == "Deterministic result explained."
    assert backend.plan_requests[0].workspace_identity["target_project_root"] == str(workspace.resolve())


def test_planning_receives_only_indexed_evidence_from_task_retrieval(tmp_path):
    indexed = [_evidence("index-workspace", "index/path.py")]
    current = [_evidence("current-workspace", "current/path.py")]
    validation = [_evidence("validation-workspace", "validation/path.py")]
    evidence_service = FakeEvidenceService(_evidence_package(indexed, current, validation))
    backend = FakeBackend(_plan())
    controller, _, workspace = _controller(tmp_path, backend, evidence_service=evidence_service)

    response = _run(controller, workspace)

    assert response.outcome == "COMPLETED"
    assert backend.plan_requests[0].reference_context == tuple(indexed)
    assert evidence_service.calls[0]["query"] == "Why did this fail?"
    assert evidence_service.calls[0]["workspace_root"] == str(workspace.resolve())
    assert evidence_service.calls[0]["max_results"] == 10


@pytest.mark.parametrize("plan,code", [
    (_plan(candidate_guard_ids=["unknown.guard"]), "UNKNOWN_GUARD"),
    (_plan(candidate_guard_ids=["cep.manifest_exists", "unknown.guard"]), "UNKNOWN_GUARD"),
    (_plan(validation_requests=["guard_runner.independent_reread"]), "MODEL_VALIDATION_REQUEST_FORBIDDEN"),
    (_plan(evidence_requests=[{"tool_id": "shell.execute", "path": "CSXS/manifest.xml", "reason": "bad"}]), "UNKNOWN_TOOL"),
    (_plan(evidence_requests=[{"tool_id": "workspace.read", "path": "../outside.txt", "reason": "bad"}]), "OUT_OF_WORKSPACE_PATH"),
])
def test_plan_rejects_unknown_or_unbounded_requests(tmp_path, plan, code):
    controller, runner, workspace = _controller(tmp_path, FakeBackend(plan))
    response = _run(controller, workspace)
    assert response.outcome == "ORCHESTRATION_ERROR"
    assert response.error.code == code
    assert runner.calls == []


def test_guard_planner_stops_on_ambiguous_approved_guards(tmp_path):
    backend = FakeBackend(_plan(candidate_guard_ids=["cep.manifest_exists", "cep.host_version"]))
    controller, runner, workspace = _controller(tmp_path, backend)
    response = _run(controller, workspace)
    assert response.outcome == "INSUFFICIENT_EVIDENCE"
    assert response.error.code == "AMBIGUOUS_GUARD_SELECTION"
    assert runner.calls == []


class FakeInsufficientEvidenceService:
    def __init__(self, package):
        self.package = package
        self.calls = []

    def build_evidence_package(self, **kwargs):
        self.calls.append(kwargs)
        return self.package


def test_guard_planner_stops_on_insufficient_evidence(tmp_path):
    backend = FakeBackend(_plan(candidate_guard_ids=["cep.manifest_exists"]))
    evidence_service = FakeInsufficientEvidenceService(_evidence_package(
        current=[{"ref": "workspace:test:src/app.py", "path": "src/app.py", "source_type": "workspace", "authority": 9, "verified": True, "classification": "source"}]
    ))
    controller, runner, workspace = _controller(tmp_path, backend, evidence_service=evidence_service)
    response = _run(controller, workspace)
    assert response.outcome == "INSUFFICIENT_EVIDENCE"
    assert response.error.code == "INSUFFICIENT_EVIDENCE"
    assert runner.calls == []


@pytest.mark.parametrize("field", ["verdict", "write", "apply", "memory_promotion", "authorization"])
def test_plan_rejects_forbidden_authority_fields(tmp_path, field):
    plan = _plan(); plan[field] = "forbidden"
    controller, runner, workspace = _controller(tmp_path, FakeBackend(plan))
    response = _run(controller, workspace)
    assert response.outcome == "ORCHESTRATION_ERROR"
    assert field in response.error.message
    assert runner.calls == []


def test_missing_evidence_verdict_remains_deterministic(tmp_path):
    controller, _, workspace = _controller(tmp_path, FakeBackend(_plan()), FakeRunner("INSUFFICIENT_EVIDENCE"))
    response = _run(controller, workspace)
    assert response.outcome == "COMPLETED"
    assert response.deterministic_result["verdict"] == "INSUFFICIENT_EVIDENCE"


def test_explanation_cannot_alter_verdict(tmp_path):
    controller, _, workspace = _controller(tmp_path, FakeBackend(_plan(), {"explanation": "override", "verdict": "FAIL"}))
    response = _run(controller, workspace)
    assert response.outcome == "ORCHESTRATION_ERROR"
    assert response.deterministic_result["verdict"] == "PASS"
    assert response.error.code == "EXPLANATION_FAILED"


def test_backend_failure_returns_structured_error(tmp_path):
    controller, _, workspace = _controller(tmp_path, FakeBackend(RuntimeError("provider unavailable")))
    response = _run(controller, workspace)
    assert response.outcome == "ORCHESTRATION_ERROR"
    assert "provider unavailable" in response.error.message


def test_controller_performs_no_workspace_write(tmp_path):
    backend = FakeBackend(_plan())
    controller, _, workspace = _controller(tmp_path, backend)
    before = {path.relative_to(workspace).as_posix(): path.read_bytes() for path in workspace.rglob("*") if path.is_file()}
    response = _run(controller, workspace)
    after = {path.relative_to(workspace).as_posix(): path.read_bytes() for path in workspace.rglob("*") if path.is_file()}
    assert response.read_only is True
    assert before == after

def test_disguised_absolute_workspace_root_is_rejected(tmp_path):
    from lbe_guard_inspector.request_controller import _ControllerFailure, _bounded_path

    root = tmp_path.resolve()
    disguised_root = "/".join(
        part.strip(chr(92) + "/").rstrip(":")
        for part in root.parts
        if part.strip(chr(92) + "/").rstrip(":")
    )

    with pytest.raises(_ControllerFailure) as error:
        _bounded_path(root, disguised_root + "/pyproject.toml")

    assert error.value.code == "OUT_OF_WORKSPACE_PATH"


def test_optional_proposal_included_when_plan_has_candidate(tmp_path):
    proposal = {"proposal_id": "prop-test", "approval_required": True, "workspace_id": "workspace-1"}
    planner = FakeProposalPlanner(proposal=proposal)
    controller, _, workspace = _controller(
        tmp_path, FakeBackend(_plan(proposal_candidate=_proposal_candidate())),
        proposal_planner=planner,
    )
    response = _run(controller, workspace)
    assert response.outcome == "COMPLETED"
    assert response.proposal == proposal
    assert response.read_only is True
    assert len(planner.calls) == 1
    assert planner.calls[0]["candidate"] == _proposal_candidate()


def test_optional_proposal_absent_when_no_candidate(tmp_path):
    planner = FakeProposalPlanner(proposal={"proposal_id": "prop"})
    controller, _, workspace = _controller(tmp_path, FakeBackend(_plan()), proposal_planner=planner)
    response = _run(controller, workspace)
    assert response.outcome == "COMPLETED"
    assert response.proposal is None
    assert planner.calls == []


def test_optional_proposal_insufficient_still_completes(tmp_path):
    planner = FakeProposalPlanner(outcome=ProposalOutcome(None, "INSUFFICIENT_EVIDENCE", read_only=True))
    controller, _, workspace = _controller(
        tmp_path, FakeBackend(_plan(proposal_candidate=_proposal_candidate())),
        proposal_planner=planner,
    )
    response = _run(controller, workspace)
    assert response.outcome == "COMPLETED"
    assert response.proposal is None


def test_optional_proposal_skipped_on_unresolved_contradictions(tmp_path):
    planner = FakeProposalPlanner(proposal={"proposal_id": "prop"})
    controller, _, workspace = _controller(
        tmp_path,
        FakeBackend(_plan(proposal_candidate=_proposal_candidate())),
        runner=FakeRunner(contradictions=["conflict-1"]),
        proposal_planner=planner,
    )
    response = _run(controller, workspace)
    assert response.outcome == "COMPLETED"
    assert response.proposal is None
    assert planner.calls == []

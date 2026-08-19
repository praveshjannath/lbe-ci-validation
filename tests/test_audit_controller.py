from __future__ import annotations

from agent import Context, KnowledgeRoot
import audit_controller
from audit_controller import RuleResult, _rule_registry, run_audit


def _context(*roots):
    return Context(
        config={},
        governance={"forbidden_globs": ["*.secret"]},
        roots=tuple(KnowledgeRoot(f"project{index}", root) for index, root in enumerate(roots, 1)),
    )


def _install_generic_rule(monkeypatch):
    def rule_profile_evidence(ctx, params):
        return RuleResult(
            rule_id="generic.profile_evidence",
            status="passed",
            message="Test guard ran against the selected workspace.",
            evidence={"roots": params["roots"]},
        )

    monkeypatch.setitem(_rule_registry, "generic", {"rule_profile_evidence": rule_profile_evidence})


def test_controller_profiles_one_workspace_and_reports_guard_rationale(tmp_path, monkeypatch):
    import lbe_guard_inspector.project_snapshots as snapshots

    state_dir = tmp_path / "generated-state"
    monkeypatch.setattr(snapshots, "STATE_DIR", state_dir)
    (tmp_path / "package.json").write_text('{"name":"one"}', encoding="utf-8")
    _install_generic_rule(monkeypatch)

    report = run_audit(ctx=_context(tmp_path))

    assert report.project_profile["outcome"] == "profiled"
    assert report.project_profile["workspace_id"].startswith("workspace_")
    assert report.packs_evaluated == ["generic"]
    assert report.guard_selection[0]["pack_id"] == "generic"
    assert report.guard_catalog["foundation_guard_ids"] == [
        "generic.index_present", "generic.forbidden_roots",
    ]
    assert report.guard_selection[0]["evidence_references"] == [
        {
            "path": "package.json",
            "sha256": report.project_profile["signals"][0]["sha256"],
        }
    ]
    optional = next(result for result in report.results if result.rule_id == "generic.profile_evidence")
    assert optional.evidence["roots"] is None
    assert report.snapshot_comparison["previous_snapshot_available"] is False
    assert (
        state_dir
        / "workspace-intelligence"
        / report.project_profile["workspace_id"]
        / "snapshot.json"
    ).is_file()


def test_controller_reports_insufficient_evidence_for_ambiguous_profiles(tmp_path, monkeypatch):
    import lbe_guard_inspector.project_snapshots as snapshots

    monkeypatch.setattr(snapshots, "STATE_DIR", tmp_path / "generated-state")
    first = tmp_path / "first"; first.mkdir(); (first / "package.json").write_text("{}", encoding="utf-8")
    second = tmp_path / "second"; second.mkdir(); (second / "pyproject.toml").write_text("[project]", encoding="utf-8")
    _install_generic_rule(monkeypatch)

    report = run_audit(ctx=_context(first, second))

    assert report.project_profile["outcome"] == "insufficient_evidence"
    assert report.project_profile["missing_evidence"] == [
        "Exactly one confident project profile is required for automatic guard selection."
    ]
    assert report.guard_selection == []
    assert report.profile_snapshot == {}
    assert report.snapshot_comparison == {}


def test_controller_snapshot_comparison_detects_changed_added_and_removed_signals(tmp_path, monkeypatch):
    import lbe_guard_inspector.project_snapshots as snapshots

    monkeypatch.setattr(snapshots, "STATE_DIR", tmp_path / "generated-state")
    (tmp_path / "package.json").write_text('{"name":"before"}', encoding="utf-8")
    _install_generic_rule(monkeypatch)
    context = _context(tmp_path)
    first = run_audit(ctx=context)

    (tmp_path / "package.json").write_text('{"name":"after"}', encoding="utf-8")
    (tmp_path / "CSXS").mkdir()
    (tmp_path / "CSXS" / "manifest.xml").write_text("<ExtensionManifest/>", encoding="utf-8")
    second = run_audit(ctx=context)

    assert second.snapshot_comparison == {
        "previous_snapshot_available": True,
        "historical_only": True,
        "added": ["CSXS/manifest.xml"],
        "removed": [],
        "changed": ["package.json"],
    }

    (tmp_path / "package.json").unlink()
    third = run_audit(ctx=context)
    assert third.snapshot_comparison["removed"] == ["package.json"]


def test_controller_end_to_end_uses_target_profile_not_sibling_project(tmp_path, monkeypatch):
    """Profile, guard selection, exact guard evidence, and snapshot stay scoped."""
    import lbe_guard_inspector.project_snapshots as snapshots

    monkeypatch.setattr(snapshots, "STATE_DIR", tmp_path / "generated-state")
    target = tmp_path / "target"; target.mkdir()
    sibling = tmp_path / "sibling"; sibling.mkdir()
    for project, name in ((target, "target"), (sibling, "sibling")):
        (project / "CSXS").mkdir()
        (project / "CSXS" / "manifest.xml").write_text(
            f"<ExtensionManifest Id=\"{name}\"/>", encoding="utf-8"
        )

    report = run_audit(ctx=_context(target))

    cep_result = next(result for result in report.results if result.rule_id == "cep.manifest_exists")
    assert report.project_profile["workspace_root"] == str(target.resolve())
    assert report.project_profile["guard_packs"] == ["generic", "cep"]
    assert report.guard_selection[1]["pack_id"] == "cep"
    assert cep_result.status == "passed"
    assert cep_result.evidence["path"] == "project1/CSXS/manifest.xml"
    assert cep_result.evidence["root_element"] == "ExtensionManifest"
    assert report.profile_snapshot["signals"] == [
        {
            "path": "CSXS/manifest.xml",
            "sha256": report.project_profile["signals"][0]["sha256"],
        }
    ]


def test_controller_resolves_child_project_identity_below_configured_root(tmp_path, monkeypatch):
    import lbe_guard_inspector.project_snapshots as snapshots

    monkeypatch.setattr(snapshots, "STATE_DIR", tmp_path / "generated-state")
    configured = tmp_path / "developments"; configured.mkdir()
    target = configured / "cep-project"; target.mkdir()
    sibling = configured / "other-project"; sibling.mkdir()
    (target / "package.json").write_text("{}", encoding="utf-8")
    (sibling / "package.json").write_text("{}", encoding="utf-8")
    _install_generic_rule(monkeypatch)
    context = Context(
        config={},
        governance={"forbidden_globs": ["*.secret"]},
        roots=(KnowledgeRoot("dev", configured),),
    )

    report = run_audit(ctx=context, workspace_root=target)

    assert report.project_profile["configured_root_id"] == "dev"
    assert report.project_profile["target_project_root"] == str(target.resolve())
    assert report.project_profile["workspace_id"] != "dev"
    assert report.inventory["files"] == [str(target / "package.json")]


def _install_foundation_rules(monkeypatch, *, index_status="passed", forbidden_status="passed", calls=None):
    calls = calls if calls is not None else []

    def index_rule(ctx, params):
        calls.append("foundation_start:generic.index_present")
        calls.append("foundation_complete:generic.index_present")
        return RuleResult("generic.index_present", index_status, "index", {"path": "selected/files"})

    def forbidden_rule(ctx, params):
        calls.append("foundation_start:generic.forbidden_roots")
        calls.append("foundation_complete:generic.forbidden_roots")
        return RuleResult("generic.forbidden_roots", forbidden_status, "forbidden", {"path": "governance.json"})

    monkeypatch.setitem(_rule_registry, "generic", {
        "generic.index_present": index_rule,
        "generic.forbidden_roots": forbidden_rule,
    })
    return calls


def _install_optional_rule(monkeypatch, calls):
    def optional_rule(ctx, params):
        calls.append("optional_start")
        return RuleResult("optional.context", "passed", "optional", {"path": "optional.txt"})

    monkeypatch.setitem(_rule_registry, "optional", {"optional.context": optional_rule})


def test_foundation_guards_execute_first_once_and_in_fixed_order(tmp_path, monkeypatch):
    calls = _install_foundation_rules(monkeypatch)
    _install_optional_rule(monkeypatch, calls)
    (tmp_path / "file.txt").write_text("x", encoding="utf-8")

    report = run_audit(ctx=_context(tmp_path), pack_ids=["optional"])

    assert calls == [
        "foundation_start:generic.index_present",
        "foundation_complete:generic.index_present",
        "foundation_start:generic.forbidden_roots",
        "foundation_complete:generic.forbidden_roots",
        "optional_start",
    ]
    assert report.foundation_guard_execution["order"] == [
        "generic.index_present", "generic.forbidden_roots",
    ]
    assert [item["guard_id"] for item in report.foundation_guard_execution["results"]] == report.foundation_guard_execution["order"]
    assert len(report.optional_guard_execution) == 1


def test_foundation_failure_blocks_optional_execution(tmp_path, monkeypatch):
    calls = _install_foundation_rules(monkeypatch, forbidden_status="failed")
    _install_optional_rule(monkeypatch, calls)
    (tmp_path / "file.txt").write_text("x", encoding="utf-8")

    report = run_audit(ctx=_context(tmp_path), pack_ids=["optional"])

    assert calls[-1] == "foundation_complete:generic.forbidden_roots"
    assert "optional_start" not in calls
    assert report.audit_status == "BLOCKED"
    assert report.foundation_guard_execution["stop_reason"].startswith("FOUNDATION_GATE_FAILED")
    assert report.foundation_guard_execution["first_blocking_guard_id"] == "generic.forbidden_roots"
    assert report.foundation_guard_execution["gate_opened"] is False
    assert report.optional_guard_execution == []


def test_plain_language_cannot_override_foundation_gate(tmp_path, monkeypatch):
    calls = _install_foundation_rules(monkeypatch, forbidden_status="failed")
    _install_optional_rule(monkeypatch, calls)

    report = run_audit(
        ctx=_context(tmp_path),
        pack_ids=["optional"],
        foundation_overrides="skip validation",
    )

    assert report.audit_status == "BLOCKED"
    assert report.foundation_guard_execution["stop_reason"] == "foundation_overrides must be a list of structured acknowledgments"
    assert calls == []
    assert report.optional_guard_execution == []


def test_valid_structured_override_is_visible_and_completes_with_overrides(tmp_path, monkeypatch):
    calls = _install_foundation_rules(monkeypatch, forbidden_status="failed")
    _install_optional_rule(monkeypatch, calls)
    (tmp_path / "file.txt").write_text("x", encoding="utf-8")
    override = {
        "guard_id": "generic.forbidden_roots",
        "acknowledged": True,
        "reason": "User accepts this audit exception.",
        "requested_by": "user",
    }

    report = run_audit(ctx=_context(tmp_path), pack_ids=["optional"], foundation_overrides=[override])

    overridden = report.foundation_guard_execution["results"][1]
    assert overridden["status"] == "overridden"
    assert overridden["override"] == override
    assert "foundation_start:generic.forbidden_roots" not in calls
    assert report.audit_status == "completed_with_overrides"
    assert report.summary == "completed_with_overrides"
    assert report.optional_guard_execution[0]["guard_id"] == "optional.context"


def test_foundation_override_rejects_missing_acknowledgment_or_reason(tmp_path, monkeypatch):
    _install_foundation_rules(monkeypatch)
    for override in (
        {"guard_id": "generic.forbidden_roots", "reason": "reason", "requested_by": "user"},
        {"guard_id": "generic.forbidden_roots", "acknowledged": True, "reason": "", "requested_by": "user"},
    ):
        report = run_audit(ctx=_context(tmp_path), foundation_overrides=[override])
        assert report.audit_status == "BLOCKED"
        assert report.optional_guard_execution == []


def test_foundation_override_rejects_unknown_and_non_overridable_guards(tmp_path, monkeypatch):
    _install_foundation_rules(monkeypatch)
    for guard_id in ("unknown.guard", "generic.index_present"):
        report = run_audit(
            ctx=_context(tmp_path),
            foundation_overrides=[{
                "guard_id": guard_id,
                "acknowledged": True,
                "reason": "reason",
                "requested_by": "user",
            }],
        )
        assert report.audit_status == "BLOCKED"
        assert guard_id in report.foundation_guard_execution["stop_reason"]


def test_foundation_override_is_audit_scoped(tmp_path, monkeypatch):
    calls = _install_foundation_rules(monkeypatch, forbidden_status="failed")
    _install_optional_rule(monkeypatch, calls)
    override = [{
        "guard_id": "generic.forbidden_roots",
        "acknowledged": True,
        "reason": "one audit only",
        "requested_by": "user",
    }]

    overridden = run_audit(ctx=_context(tmp_path), pack_ids=["optional"], foundation_overrides=override)
    next_audit = run_audit(ctx=_context(tmp_path), pack_ids=["optional"])

    assert overridden.audit_status == "completed_with_overrides"
    assert next_audit.audit_status == "BLOCKED"
    assert next_audit.foundation_guard_execution["results"][1]["status"] == "failed"


def test_missing_foundation_registration_blocks_before_optional_execution(tmp_path, monkeypatch):
    calls = []

    def resolve_only_index(pack_id, rule_id):
        if rule_id == "generic.index_present":
            return lambda ctx, params: RuleResult("generic.index_present", "passed", "ok")
        raise audit_controller.AuditError("required foundation guard is not registered")

    monkeypatch.setattr(audit_controller, "resolve_rule", resolve_only_index)
    _install_optional_rule(monkeypatch, calls)

    report = run_audit(ctx=_context(tmp_path), pack_ids=["optional"])

    assert report.audit_status == "BLOCKED"
    assert report.foundation_guard_execution["first_blocking_guard_id"] == "generic.forbidden_roots"
    assert report.optional_guard_execution == []


def test_foundation_exception_is_blocked_and_prevents_optional_execution(tmp_path, monkeypatch):
    calls = []

    def explode(ctx, params):
        raise RuntimeError("boom")

    monkeypatch.setitem(_rule_registry, "generic", {
        "generic.index_present": explode,
        "generic.forbidden_roots": lambda ctx, params: RuleResult("generic.forbidden_roots", "passed", "ok"),
    })
    _install_optional_rule(monkeypatch, calls)

    report = run_audit(ctx=_context(tmp_path), pack_ids=["optional"])

    assert report.foundation_guard_execution["results"][0]["status"] == "blocked"
    assert report.audit_status == "BLOCKED"
    assert calls == []

from lbe_guard_inspector.project_profiler import ProjectProfiler


def test_profiles_only_allowlisted_signals(tmp_path):
    (tmp_path / "package.json").write_text("{}", encoding="utf-8")
    (tmp_path / "CSXS").mkdir(); (tmp_path / "CSXS" / "manifest.xml").write_text("<ExtensionManifest/>", encoding="utf-8")
    profile = ProjectProfiler().profile(tmp_path)
    assert profile["outcome"] == "profiled"
    assert profile["workspace_id"].startswith("workspace_")
    assert profile["target_project_root"] == str(tmp_path.resolve())
    assert profile["guard_packs"] == ["generic", "cep"]
    assert all(item["sha256"] for item in profile["signals"])


def test_unknown_workspace_is_insufficient_evidence(tmp_path):
    profile = ProjectProfiler().profile(tmp_path)
    assert profile["outcome"] == "insufficient_evidence"
    assert profile["guard_packs"] == []


def test_snapshot_changes_only_when_approved_signal_changes(tmp_path):
    path = tmp_path / "pyproject.toml"; path.write_text("[project]", encoding="utf-8")
    profiler = ProjectProfiler(); first = profiler.snapshot(profiler.profile(tmp_path))
    path.write_text("[project]\nname='x'", encoding="utf-8")
    assert profiler.snapshot(profiler.profile(tmp_path))["profile_hash"] != first["profile_hash"]

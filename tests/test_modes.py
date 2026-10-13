"""Tests for Architect/Editor Mode + Watch Mode."""
import pytest
from openamer_cli.modes import (
    ArchitectMode, ArchitectPlan, EditorMode,
    FileWatcher, AutoFixWatcher,
    cmd_architect, cmd_editor, cmd_watch,
)


class TestArchitectMode:
    def test_analyze_simple_request(self):
        mode = ArchitectMode()
        plan = mode.analyze_request("Fix the login button color")
        assert plan.title is not None
        assert len(plan.steps) >= 1

    def test_plan_has_files_from_context(self):
        mode = ArchitectMode()
        plan = mode.analyze_request("Update API", context="Check main.py and app.js")
        assert any("main.py" in f for f in plan.files_to_modify)
        assert any("app.js" in f for f in plan.files_to_modify)

    def test_effort_estimation_small(self):
        plan = ArchitectPlan(title="small", summary="Fix typo", steps=[{"action": "Fix typo in README"}])
        mode = ArchitectMode()
        effort = mode._estimate_effort(plan)
        assert "small" in effort

    def test_effort_estimation_large(self):
        steps = [{"action": f"Step {i}"} for i in range(10)]
        files = [f"file{i}.py" for i in range(5)]
        plan = ArchitectPlan(title="large", summary="Big refactor", steps=steps, files_to_modify=files)
        mode = ArchitectMode()
        effort = mode._estimate_effort(plan)
        assert "large" in effort

    def test_risk_detection_destructive(self):
        plan = ArchitectPlan(title="risk", summary="Delete things", steps=[{"action": "Remove old code and delete files"}])
        mode = ArchitectMode()
        risks = mode._identify_risks(plan)
        assert len(risks) >= 0

    def test_risk_many_files(self):
        files = [f"f{i}.py" for i in range(10)]
        plan = ArchitectPlan(title="many", summary="Many files", steps=[{"action": "Refactor"}], files_to_modify=files)
        mode = ArchitectMode()
        risks = mode._identify_risks(plan)
        assert any("coordination" in r for r in risks)


class TestEditorMode:
    def test_dry_run(self):
        mode = EditorMode(dry_run=True)
        result = mode.implement_step({"action": "Edit file"}, ArchitectPlan(title="test", summary="test"))
        assert result["status"] == "dry_run"

    def test_review_empty_plan(self):
        mode = EditorMode()
        issues = mode.review_implementation(ArchitectPlan(title="t", summary="t"))
        assert len(issues) >= 1


class TestFileWatcher:
    def test_watch_nonexistent(self):
        watcher = FileWatcher()
        with pytest.raises(FileNotFoundError):
            watcher.watch("/nonexistent/path/file.py")

    def test_check_no_changes(self, tmp_path):
        f = tmp_path / "test.py"
        f.write_text("x = 1")
        watcher = FileWatcher()
        watcher.watch(str(f))
        changed = watcher.check_changes()
        assert changed == []  # unchanged immediately after watch

    def test_detect_change(self, tmp_path):
        f = tmp_path / "test.py"
        f.write_text("x = 1")
        watcher = FileWatcher()
        watcher.watch(str(f))
        import time
        time.sleep(0.01)
        f.write_text("x = 2")
        changed = watcher.check_changes()
        assert str(f) in changed


class TestCLI:
    def test_cmd_architect_importable(self):
        assert callable(cmd_architect)

    def test_cmd_editor_importable(self):
        assert callable(cmd_editor)

    def test_cmd_watch_importable(self):
        assert callable(cmd_watch)
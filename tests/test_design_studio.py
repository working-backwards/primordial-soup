"""Tests for the design studio's workbench plumbing (scripts/design_studio.py).

Only the socket-free functions are tested: validate_design_yaml() and
save_design_yaml(). The HTTP routing is thin dispatch over these, and the
run-launching path is exercised end-to-end manually (it shells out to
run_design.py, which has its own validation and is too slow for unit tests).
"""

from __future__ import annotations

import importlib.util
from pathlib import Path

# scripts/ is not a package, so load the module straight from its file.
_REPO_ROOT = Path(__file__).resolve().parent.parent
_MODULE_PATH = _REPO_ROOT / "scripts" / "design_studio.py"
_spec = importlib.util.spec_from_file_location("design_studio", _MODULE_PATH)
design_studio = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(design_studio)

FIXTURES_DIR = Path(__file__).resolve().parent / "fixtures"


def _fixture_text(name: str) -> str:
    return (FIXTURES_DIR / name).read_text(encoding="utf-8")


class TestValidateDesignYaml:
    def test_valid_design_returns_summary(self) -> None:
        result = design_studio.validate_design_yaml(_fixture_text("run_designer_default.yaml"))
        assert result["ok"] is True
        # The summary is the workbench's resolved-design printout.
        assert 'Run Design: "my_run_v1"' in result["summary"]
        assert "balanced_incumbent" in result["summary"]

    def test_invalid_design_returns_error_not_exception(self) -> None:
        # Name with a space violates validate_run_design(); the studio must
        # report it as data so the browser can display it.
        broken = _fixture_text("run_designer_default.yaml").replace(
            "name: my_run_v1", "name: my run v1"
        )
        result = design_studio.validate_design_yaml(broken)
        assert result["ok"] is False
        assert "spaces" in result["error"]

    def test_non_mapping_yaml_is_rejected(self) -> None:
        result = design_studio.validate_design_yaml("- just\n- a\n- list\n")
        assert result["ok"] is False
        assert "mapping" in result["error"]

    def test_unparseable_yaml_is_rejected(self) -> None:
        result = design_studio.validate_design_yaml("name: [unclosed\n")
        assert result["ok"] is False


class TestSaveDesignYaml:
    def test_writes_timestamped_file_named_after_design(self, tmp_path: Path) -> None:
        yaml_text = _fixture_text("run_designer_default.yaml")
        written = design_studio.save_design_yaml(yaml_text, tmp_path)
        assert written.parent == tmp_path
        assert written.name.startswith("my_run_v1_")
        assert written.suffix == ".yaml"
        assert written.read_text(encoding="utf-8") == yaml_text

    def test_repeated_saves_do_not_overwrite(self, tmp_path: Path) -> None:
        # Saves within the same second get a numeric suffix instead of
        # clobbering the earlier file.
        yaml_text = _fixture_text("run_designer_default.yaml")
        first = design_studio.save_design_yaml(yaml_text, tmp_path)
        second = design_studio.save_design_yaml(yaml_text, tmp_path)
        assert first != second
        assert first.exists() and second.exists()

"""
Tests for semver-dredd CLI.
"""

import json
import logging
import os
from datetime import date
from unittest.mock import patch

import yaml

from cli import main
from semverdredd.plugin_base import LanguagePlugin, SnapshotResult


class InventoryPlugin(LanguagePlugin):
    @property
    def name(self) -> str:
        return "inventory-test"

    @property
    def version(self) -> str:
        return "9.9.9"

    @property
    def metadata(self) -> dict:
        return {
            "scope": {"syntax": "demo-syntax"},
            "plugin_options": ["demo_option"],
            "features": ["metadata", "machine_readable_inventory"],
        }

    def generate_snapshot(self, path: str, version: str, options=None) -> SnapshotResult:
        return SnapshotResult(True, "inventory")


class TestCLIBump:
    """Tests for bump command."""

    def test_bump_major(self, capsys):
        """Test bumping major version."""
        result = main(["bump", "-c", "1.2.20260213001", "-t", "major"])
        assert result == 0
        output = capsys.readouterr().out
        assert "2.0." in output  # Major bump resets minor

    def test_bump_minor(self, capsys):
        """Test bumping minor version."""
        result = main(["bump", "-c", "1.2.20260213001", "-t", "minor"])
        assert result == 0
        output = capsys.readouterr().out
        assert "1.3." in output

    def test_bump_patch(self, capsys):
        """Test bumping patch version."""
        result = main(["bump", "-c", "1.2.20260213001", "-t", "patch"])
        assert result == 0
        output = capsys.readouterr().out
        assert "1.2." in output

    def test_bump_quiet(self, capsys):
        """Test quiet mode only outputs version."""
        result = main(["bump", "-c", "1.2.3", "-t", "minor", "-q"])
        assert result == 0
        output = capsys.readouterr().out
        # Quiet mode should only have the version number
        lines = [l for l in output.strip().split("\n") if l]
        assert len(lines) == 1
        assert lines[0].startswith("1.3.")

    def test_bump_invalid_version(self, capsys):
        """Test error for invalid version."""
        result = main(["bump", "-c", "invalid", "-t", "minor"])
        assert result == 1
        err = capsys.readouterr().err
        assert "Error" in err

    def test_bump_none(self, capsys):
        """Test bump with none change type."""
        result = main(["bump", "-c", "1.2.3", "-t", "none"])
        assert result == 0
        output = capsys.readouterr().out
        assert "1.2.3" in output


class TestCLIPatch:
    """Tests for patch command."""

    def test_patch_new(self, capsys):
        """Test generating new patch version."""
        result = main(["patch"])
        assert result == 0
        output = capsys.readouterr().out.strip()
        # Should be in YYYYMMDDZZZ format
        assert len(output) == 11
        assert output.isdigit()

    def test_patch_increment(self, capsys):
        """Test incrementing existing patch version."""
        today = date.today()
        current = int(f"{today.year:04d}{today.month:02d}{today.day:02d}001")
        result = main(["patch", "-c", str(current)])
        assert result == 0
        output = capsys.readouterr().out.strip()
        expected = str(current + 1)
        assert output == expected


class TestCLICompare:
    """Tests for compare command."""

    def test_compare_pygeometry(self, capsys):
        """Test comparing pygeometry1 and pygeometry2."""
        result = main(["compare", "example.py.pygeometry1", "example.py.pygeometry2"])
        assert result == 0
        captured = capsys.readouterr()
        assert "MINOR" in captured.out
        # MINOR emits a WARN line on stderr
        assert "[WARN]" in captured.err

    def test_compare_pygeometry_details_lists_added(self, capsys):
        result = main(
            ["compare", "example.py.pygeometry1", "example.py.pygeometry2", "--details"]
        )
        assert result == 0
        captured = capsys.readouterr()
        # Should list at least one added item (volume, translate)
        assert "Added changes:" in captured.out
        assert "function added: volume" in captured.out
        assert "method added: translate" in captured.out

    def test_compare_pygeometry_breaking_details(self, capsys):
        # v2 -> v1 is breaking (removes volume/translate and changes signatures)
        result = main(
            [
                "compare",
                "example.py.pygeometry2",
                "example.py.pygeometry1",
                "--details",
                "--allow-breaking",
            ]
        )
        assert result == 0
        captured = capsys.readouterr()
        assert "Breaking changes:" in captured.out
        assert "function removed: volume" in captured.out
        assert "method removed: translate" in captured.out

    def test_compare_verbose_explains_inspected_api(self, capsys):
        result = main(
            ["compare", "example.py.pygeometry1", "example.py.pygeometry2", "--verbose"]
        )
        assert result == 0
        captured = capsys.readouterr()
        # Unified plugin-based approach shows "Using plugin" message
        assert "Using plugin" in captured.err or "Using plugin" in captured.out

    def test_compare_same_module(self, capsys):
        """Test comparing same module."""
        result = main(["compare", "example.py.pygeometry1", "example.py.pygeometry1"])
        assert result == 0
        captured = capsys.readouterr()
        assert "NONE" in captured.out
        assert "[INFO]" in captured.err or "[INFO]" in captured.out

    def test_compare_with_current_version(self, capsys):
        """Test compare with current version suggestion."""
        result = main(
            [
                "compare",
                "example.py.pygeometry1",
                "example.py.pygeometry2",
                "--current",
                "1.0.20260213001",
            ]
        )
        assert result == 0
        output = capsys.readouterr().out
        assert "1.1." in output  # Minor bump

    def test_compare_invalid_module(self, capsys):
        """Test error for invalid module."""
        result = main(["compare", "nonexistent.module", "example.py.pygeometry1"])
        assert result == 1
        err = capsys.readouterr().err
        assert "[ERROR]" in err or "error" in err.lower()

    def test_compare_mutually_exclusive_breaking_flags(self, capsys):
        result = main(
            [
                "compare",
                "example.py.pygeometry1",
                "example.py.pygeometry1",
                "--allow-breaking",
                "--disallow-breaking",
            ]
        )
        assert result == 1
        err = capsys.readouterr().err
        assert "mutually exclusive" in err


class TestCLIBreakingPolicy:
    """Policy tests for breaking change gating."""

    def test_breaking_changes_disallowed_by_default(self, capsys):
        # v2 removes things compared to v1 => MAJOR
        result = main(["compare", "example.py.pygeometry2", "example.py.pygeometry1"])
        assert result == 10
        captured = capsys.readouterr()
        assert "BREAKING" in captured.out
        assert "[ERROR]" in captured.err  # Severity should be ERROR when not allowed
        assert "Breaking changes are not allowed" in captured.err

    def test_breaking_changes_allowed_with_flag(self, capsys):
        result = main(
            [
                "compare",
                "example.py.pygeometry2",
                "example.py.pygeometry1",
                "--allow-breaking",
            ]
        )
        assert result == 0
        captured = capsys.readouterr()
        assert "BREAKING" in captured.out
        assert "[WARN]" in captured.err  # Severity should be WARN when allowed
        assert (
            "Breaking changes are not allowed" not in captured.err
        )  # No error message


class TestCLIHelpSurface:
    """Help and command-group behavior should be informative and stable."""

    def test_top_level_help_is_verbose(self, capsys):
        with patch("sys.argv", ["semver-dredd", "--help"]):
            try:
                main(["--help"])
            except SystemExit as e:
                assert e.code == 0

        captured = capsys.readouterr()
        assert "Typical workflow:" in captured.out
        assert "Configuration precedence" in captured.out
        assert "semver-dredd plugin list" in captured.out

    def test_plugin_command_without_subcommand_prints_help(self, capsys):
        result = main(["plugin"])
        assert result == 0

        captured = capsys.readouterr()
        assert "usage: semver-dredd plugin" in captured.out
        assert "list,install,remove,info" in captured.out
        assert captured.err == ""

    def test_snapshot_help_mentions_config_driven_behavior(self, capsys):
        with patch("sys.argv", ["semver-dredd", "snapshot", "--help"]):
            try:
                main(["snapshot", "--help"])
            except SystemExit as e:
                assert e.code == 0

        captured = capsys.readouterr()
        assert "Config-driven behavior:" in captured.out
        assert "reads the resolved VERSION file" in captured.out
        assert "unless --override is used" in captured.out


class TestConfigPriority:
    """Tests for configuration priority system."""

    def test_yaml_config_sets_allow_breaking(self, capsys, tmp_path, monkeypatch):
        """Test .semver.yaml sets allow_breaking_changes."""
        monkeypatch.chdir(tmp_path)

        # Create .semver.yaml with allow_breaking_changes: true
        config_file = tmp_path / ".semver.yaml"
        config_file.write_text("""
schema_version: 1
policies:
  allow_breaking_changes: true
""")

        # v2 removes things compared to v1 => MAJOR
        # Without config, this would fail (exit 10)
        # With config allowing breaking, should exit 0
        result = main(["compare", "example.py.pygeometry2", "example.py.pygeometry1"])
        assert result == 0
        captured = capsys.readouterr()
        assert "BREAKING" in captured.out
        assert "[WARN]" in captured.err  # Should be WARN when allowed

    def test_env_file_overrides_yaml(self, capsys, tmp_path, monkeypatch):
        """Test .env file overrides .semver.yaml."""
        monkeypatch.chdir(tmp_path)

        # Create .semver.yaml with allow_breaking: true
        config_file = tmp_path / ".semver.yaml"
        config_file.write_text("""
schema_version: 1
policies:
  allow_breaking_changes: true
""")

        # Create .env that sets allow_breaking: false
        env_file = tmp_path / ".env"
        env_file.write_text("SEMVER_DREDD_ALLOW_BREAKING=false\n")

        # .env should override yaml, so breaking changes disallowed
        result = main(["compare", "example.py.pygeometry2", "example.py.pygeometry1"])
        assert result == 10  # Should fail because .env overrides yaml
        captured = capsys.readouterr()
        assert "Breaking changes are not allowed" in captured.err

    def test_real_env_overrides_env_file(self, capsys, tmp_path, monkeypatch):
        """Test real environment variables override .env file."""
        monkeypatch.chdir(tmp_path)

        # Create .env that sets allow_breaking: false
        env_file = tmp_path / ".env"
        env_file.write_text("SEMVER_DREDD_ALLOW_BREAKING=false\n")

        # Real env var overrides .env
        with patch.dict(os.environ, {"SEMVER_DREDD_ALLOW_BREAKING": "true"}):
            result = main(
                ["compare", "example.py.pygeometry2", "example.py.pygeometry1"]
            )
            assert result == 0  # Should pass because real env overrides .env
            captured = capsys.readouterr()
            assert "BREAKING" in captured.out
            assert "[WARN]" in captured.err

    def test_cli_arg_overrides_all(self, capsys, tmp_path, monkeypatch):
        """Test CLI arguments override all config sources."""
        monkeypatch.chdir(tmp_path)

        # Create .semver.yaml with allow_breaking: true
        config_file = tmp_path / ".semver.yaml"
        config_file.write_text("""
schema_version: 1
policies:
  allow_breaking_changes: true
""")

        # Create .env that also sets allow_breaking: true
        env_file = tmp_path / ".env"
        env_file.write_text("SEMVER_DREDD_ALLOW_BREAKING=true\n")

        # Real env var also sets allow_breaking: true
        with patch.dict(os.environ, {"SEMVER_DREDD_ALLOW_BREAKING": "true"}):
            # But CLI --disallow-breaking should override everything
            result = main(
                [
                    "compare",
                    "example.py.pygeometry2",
                    "example.py.pygeometry1",
                    "--disallow-breaking",
                ]
            )
            assert result == 10  # Should fail because CLI overrides all
            captured = capsys.readouterr()
            assert "Breaking changes are not allowed" in captured.err


class TestRun1ConfigWorkflow:
    def test_explicit_config_missing_fails_for_non_init(
        self, tmp_path, monkeypatch, capsys
    ):
        monkeypatch.chdir(tmp_path)
        result = main(
            [
                "--config",
                ".semver.dev.yaml",
                "status",
                "example.py.pygeometry1",
            ]
        )
        assert result == 1
        err = capsys.readouterr().err
        assert "Config file not found" in err

    def test_init_allows_missing_explicit_config_and_creates_it(
        self, tmp_path, monkeypatch
    ):
        monkeypatch.chdir(tmp_path)
        result = main(
            [
                "--config",
                ".semver.dev.yaml",
                "init",
                "example.py.pygeometry1",
                "--plugin",
                "python",
                "--version",
                "1.0.0",
            ]
        )
        assert result == 0
        assert (tmp_path / ".semver.dev.yaml").exists()
        assert not (tmp_path / ".semver.yaml").exists()

    def test_custom_config_selection_over_default(self, tmp_path, monkeypatch, capsys):
        monkeypatch.chdir(tmp_path)
        (tmp_path / ".semver.yaml").write_text("""
schema_version: 1
policies:
  allow_breaking_changes: false
""")
        (tmp_path / ".semver.dev.yaml").write_text("""
schema_version: 1
policies:
  allow_breaking_changes: true
""")

        result = main(
            [
                "--config",
                ".semver.dev.yaml",
                "compare",
                "example.py.pygeometry2",
                "example.py.pygeometry1",
            ]
        )
        assert result == 0
        captured = capsys.readouterr()
        assert "BREAKING" in captured.out
        assert "[WARN]" in captured.err

    def test_status_and_bake_are_pathless_after_init(self, tmp_path, monkeypatch):
        monkeypatch.chdir(tmp_path)
        init_result = main(
            [
                "init",
                "example.py.pygeometry1",
                "--plugin",
                "python",
                "--version",
                "1.0.0",
            ]
        )
        assert init_result == 0

        status_result = main(["status", "--details"])
        assert status_result == 0

        bake_result = main(["bake"])
        assert bake_result == 0

    def test_snapshot_defaults_from_config_and_version_file(
        self, tmp_path, monkeypatch
    ):
        monkeypatch.chdir(tmp_path)
        init_result = main(
            [
                "init",
                "example.py.pygeometry1",
                "--plugin",
                "python",
                "--version",
                "1.2.3",
            ]
        )
        assert init_result == 0

        out = tmp_path / "snapshot.yaml"
        snap_result = main(["snapshot", "--out", str(out)])
        assert snap_result == 0
        assert out.exists()
        assert "version: 1.2.3" in out.read_text()

    def test_multi_document_candidate_fallback_works_in_real_cli_main(
        self, tmp_path, monkeypatch
    ):
        monkeypatch.chdir(tmp_path)
        cfg = tmp_path / ".semver.yaml"
        cfg.write_text(
            """
schema_version: 1
source:
  path: .
---
plugin: does-not-exist
---
plugin: go
"""
        )
        (tmp_path / "dummy.go").write_text("package dummy\n")
        (tmp_path / "VERSION").write_text("1.0.0\n")

        out = tmp_path / "snap.yaml"
        result = main(["snapshot", "--version", "1.0.0", "--out", str(out)])
        assert result == 0
        assert out.exists()


class TestRun2Verbosity:
    """Tests for global counted verbosity flag (-v/-vv/-vvv)."""

    def test_no_verbosity_produces_no_selection_output_on_stderr(
        self, tmp_path, monkeypatch, capsys
    ):
        """Default verbosity (0) should not emit config/plugin selection events to stderr."""
        monkeypatch.chdir(tmp_path)
        main(["bump", "-c", "1.0.0", "-t", "none"])
        err = capsys.readouterr().err
        # config.selected and plugin.selected events must not appear in stderr at default verbosity
        assert "config.selected" not in err
        assert "plugin.selected" not in err

    def test_single_v_emits_config_and_plugin_selection(
        self, tmp_path, monkeypatch, caplog
    ):
        """Single -v should log config.selected and plugin.selected at INFO."""
        monkeypatch.chdir(tmp_path)
        with caplog.at_level(logging.INFO, logger="cli"):
            main(["-v", "compare", "example.py.pygeometry1", "example.py.pygeometry1"])
        messages = [r.getMessage() for r in caplog.records if r.name.startswith("cli")]
        assert any(
            "config.selected" in m for m in messages
        ), f"No config.selected in {messages}"
        assert any(
            "plugin.selected" in m for m in messages
        ), f"No plugin.selected in {messages}"

    def test_double_v_emits_candidate_attempt(self, tmp_path, monkeypatch, caplog):
        """Double -vv should log candidate.attempt events at DEBUG."""
        monkeypatch.chdir(tmp_path)
        with caplog.at_level(logging.DEBUG, logger="cli"):
            main(
                [
                    "-v",
                    "-v",
                    "compare",
                    "example.py.pygeometry1",
                    "example.py.pygeometry1",
                ]
            )
        messages = [r.getMessage() for r in caplog.records if r.name.startswith("cli")]
        assert any(
            "candidate.attempt" in m for m in messages
        ), f"No candidate.attempt in {messages}"

    def test_triple_v_emits_args_dump(self, tmp_path, monkeypatch, caplog):
        """Triple -vvv should log args.dump with command context."""
        monkeypatch.chdir(tmp_path)
        with caplog.at_level(logging.DEBUG, logger="cli"):
            main(
                [
                    "-v",
                    "-v",
                    "-v",
                    "compare",
                    "example.py.pygeometry1",
                    "example.py.pygeometry1",
                ]
            )
        messages = [r.getMessage() for r in caplog.records if r.name.startswith("cli")]
        assert any(
            "args.dump" in m and "command=" in m for m in messages
        ), f"No args.dump in {messages}"

    def test_init_version_flag_is_long_form_only(self, tmp_path, monkeypatch):
        """init --version should work; -v on top-level is now verbosity."""
        monkeypatch.chdir(tmp_path)
        # init --version 1.0.0 should still work
        result = main(
            [
                "init",
                "example.py.pygeometry1",
                "--plugin",
                "python",
                "--version",
                "1.0.0",
            ]
        )
        assert result == 0
        assert (tmp_path / "VERSION").read_text().strip() == "1.0.0"

    def test_config_selected_shows_explicit_for_explicit_config(
        self, tmp_path, monkeypatch, caplog
    ):
        """When --config is used, config.selected should report 'explicit'."""
        monkeypatch.chdir(tmp_path)
        cfg = tmp_path / ".semver.custom.yaml"
        cfg.write_text("schema_version: 1\n")
        with caplog.at_level(logging.INFO, logger="cli"):
            main(["-v", "--config", str(cfg), "bump", "-c", "1.0.0", "-t", "none"])
        messages = [r.getMessage() for r in caplog.records if r.name.startswith("cli")]
        assert any(
            "config.selected" in m and "explicit" in m for m in messages
        ), f"Expected explicit in config.selected, got: {messages}"

    def test_config_selected_shows_absent_when_no_config(
        self, tmp_path, monkeypatch, caplog
    ):
        """When no config file exists, config.selected should report 'absent'."""
        monkeypatch.chdir(tmp_path)
        with caplog.at_level(logging.INFO, logger="cli"):
            main(["-v", "bump", "-c", "1.0.0", "-t", "none"])
        messages = [r.getMessage() for r in caplog.records if r.name.startswith("cli")]
        assert any(
            "config.selected" in m and "absent" in m for m in messages
        ), f"Expected absent in config.selected, got: {messages}"


class TestPluginInventoryOutput:
    def test_plugin_list_json_emits_stable_shape(self, capsys):
        from semverdredd.plugin_manager import get_plugin_manager

        mgr = get_plugin_manager()
        mgr.register(InventoryPlugin())
        try:
            result = main(["plugin", "list", "--json"])
            assert result == 0
            output = capsys.readouterr().out
            payload = json.loads(output)
            plugin = next(item for item in payload if item["name"] == "inventory-test")
            assert plugin["version"] == "9.9.9"
            assert plugin["origin"] == "manual"
            assert plugin["scope"] == {"syntax": "demo-syntax"}
            assert plugin["features"] == ["machine_readable_inventory", "metadata"]
            assert set(plugin["snapshot_format"].keys()) == {
                "class",
                "snapshot_type_id",
            }
        finally:
            mgr.unregister("inventory-test")

    def test_plugin_info_yaml_emits_stable_shape(self, capsys):
        from semverdredd.plugin_manager import get_plugin_manager

        mgr = get_plugin_manager()
        mgr.register(InventoryPlugin())
        try:
            result = main(["plugin", "info", "inventory-test", "--yaml"])
            assert result == 0
            output = capsys.readouterr().out
            payload = yaml.safe_load(output)
            assert payload["name"] == "inventory-test"
            assert payload["display_name"] == "Inventory-test"
            assert payload["plugin_options"] == ["demo_option"]
            assert payload["snapshot_format"] == {
                "class": None,
                "snapshot_type_id": None,
            }
        finally:
            mgr.unregister("inventory-test")

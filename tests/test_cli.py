"""
Tests for semver-dredd CLI.
"""

import os
from datetime import date
from unittest.mock import patch

from cli import main


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
        lines = [l for l in output.strip().split('\n') if l]
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
        result = main(["compare", "example.pygeometry1", "example.pygeometry2"])
        assert result == 0
        captured = capsys.readouterr()
        assert "MINOR" in captured.out
        # MINOR emits a WARN line on stderr
        assert "[WARN]" in captured.err

    def test_compare_pygeometry_details_lists_added(self, capsys):
        result = main(["compare", "example.pygeometry1", "example.pygeometry2", "--details"])
        assert result == 0
        captured = capsys.readouterr()
        # Should list at least one added item (volume, translate)
        assert "Added changes:" in captured.out
        assert "function added: volume" in captured.out
        assert "method added: translate" in captured.out

    def test_compare_pygeometry_breaking_details(self, capsys):
        # v2 -> v1 is breaking (removes volume/translate and changes signatures)
        result = main([
            "compare",
            "example.pygeometry2",
            "example.pygeometry1",
            "--details",
            "--allow-breaking",
        ])
        assert result == 0
        captured = capsys.readouterr()
        assert "Breaking changes:" in captured.out
        assert "function removed: volume" in captured.out
        assert "method removed: translate" in captured.out

    def test_compare_verbose_explains_inspected_api(self, capsys):
        result = main(["compare", "example.pygeometry1", "example.pygeometry2", "--verbose"])
        assert result == 0
        captured = capsys.readouterr()
        assert "Inspecting public module API" in captured.err or "Inspecting public module API" in captured.out

    def test_compare_same_module(self, capsys):
        """Test comparing same module."""
        result = main(["compare", "example.pygeometry1", "example.pygeometry1"])
        assert result == 0
        captured = capsys.readouterr()
        assert "NONE" in captured.out
        assert "[INFO]" in captured.err or "[INFO]" in captured.out

    def test_compare_with_current_version(self, capsys):
        """Test compare with current version suggestion."""
        result = main([
            "compare",
            "example.pygeometry1",
            "example.pygeometry2",
            "--current", "1.0.20260213001"
        ])
        assert result == 0
        output = capsys.readouterr().out
        assert "1.1." in output  # Minor bump

    def test_compare_invalid_module(self, capsys):
        """Test error for invalid module."""
        result = main(["compare", "nonexistent.module", "example.pygeometry1"])
        assert result == 1
        err = capsys.readouterr().err
        assert "Error" in err

    def test_compare_mutually_exclusive_breaking_flags(self, capsys):
        result = main([
            "compare",
            "example.pygeometry1",
            "example.pygeometry1",
            "--allow-breaking",
            "--disallow-breaking",
        ])
        assert result == 1
        err = capsys.readouterr().err
        assert "mutually exclusive" in err


class TestCLIBreakingPolicy:
    """Policy tests for breaking change gating."""

    def test_breaking_changes_disallowed_by_default(self, capsys):
        # v2 removes things compared to v1 => MAJOR
        result = main(["compare", "example.pygeometry2", "example.pygeometry1"])
        assert result == 10
        captured = capsys.readouterr()
        assert "MAJOR" in captured.out
        assert "[ERROR]" in captured.err  # Severity should be ERROR when not allowed
        assert "Breaking changes are not allowed" in captured.err

    def test_breaking_changes_allowed_with_flag(self, capsys):
        result = main([
            "compare",
            "example.pygeometry2",
            "example.pygeometry1",
            "--allow-breaking",
        ])
        assert result == 0
        captured = capsys.readouterr()
        assert "MAJOR" in captured.out
        assert "[WARN]" in captured.err  # Severity should be WARN when allowed
        assert "Breaking changes are not allowed" not in captured.err  # No error message


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
        result = main(["compare", "example.pygeometry2", "example.pygeometry1"])
        assert result == 0
        captured = capsys.readouterr()
        assert "MAJOR" in captured.out
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
        result = main(["compare", "example.pygeometry2", "example.pygeometry1"])
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
            result = main(["compare", "example.pygeometry2", "example.pygeometry1"])
            assert result == 0  # Should pass because real env overrides .env
            captured = capsys.readouterr()
            assert "MAJOR" in captured.out
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
            result = main([
                "compare",
                "example.pygeometry2",
                "example.pygeometry1",
                "--disallow-breaking",
            ])
            assert result == 10  # Should fail because CLI overrides all
            captured = capsys.readouterr()
            assert "Breaking changes are not allowed" in captured.err

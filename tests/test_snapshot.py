"""Tests for semver-dredd snapshot and new CLI commands."""

import tempfile
from pathlib import Path

from cli import main
from semverdredd.version import save_version_file, load_version_file
from example.py import pygeometry2
from example.py import pygeometry1


class TestVersionFile:
    """Tests for VERSION file utilities."""

    def test_save_and_load_version(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            path = Path(tmpdir) / "VERSION"
            save_version_file("1.2.3", path)
            loaded = load_version_file(path)
            assert loaded == "1.2.3"


class TestCLIInit:
    """Tests for init command."""

    def test_init_creates_files(self, capsys, tmp_path, monkeypatch):
        monkeypatch.chdir(tmp_path)
        result = main(["init", "example.py.pygeometry1", "--version", "1.0.0"])
        assert result == 0
        assert (tmp_path / ".semver.yaml").exists()
        assert (tmp_path / "baked.yaml").exists()
        assert (tmp_path / "VERSION").exists()
        assert (tmp_path / "VERSION").read_text().strip() == "1.0.0"


class TestCLIStatus:
    """Tests for status command."""

    def test_status_detects_changes(self, capsys, tmp_path, monkeypatch):
        monkeypatch.chdir(tmp_path)
        # Init with pygeometry1
        main(["init", "example.py.pygeometry1", "--version", "1.0.0"])
        # Check status with pygeometry2 (has additions)
        result = main(["status", "example.py.pygeometry2", "--details"])
        assert result == 0
        captured = capsys.readouterr()
        assert "MINOR" in captured.err  # Severity goes to stderr
        assert "Suggested version: 1.1." in captured.out
        assert (tmp_path / "current.yaml").exists()


class TestCLIBake:
    """Tests for bake command."""

    def test_bake_updates_version(self, capsys, tmp_path, monkeypatch):
        monkeypatch.chdir(tmp_path)
        # Init with pygeometry1
        main(["init", "example.py.pygeometry1", "--version", "1.0.0"])
        # Bake pygeometry2
        result = main(["bake", "example.py.pygeometry2"])
        assert result == 0
        # VERSION should be updated
        version = (tmp_path / "VERSION").read_text().strip()
        assert version.startswith("1.1.")

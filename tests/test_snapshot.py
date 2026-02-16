"""Tests for semver-dredd snapshot and new CLI commands."""

import tempfile
from pathlib import Path

from cli import main
from semverdredd.snapshot import APISnapshot, save_version_file, load_version_file
from semverdredd.python_api import ModuleAPI
from example.py import pygeometry2
from example.py import pygeometry1


class TestAPISnapshot:
    """Tests for APISnapshot serialization."""

    def test_from_module_and_to_yaml(self):
        snapshot = APISnapshot.from_module(pygeometry1, "1.0.0")
        yaml_str = snapshot.to_yaml()
        assert "version: 1.0.0" in yaml_str
        assert "area:" in yaml_str
        assert "Point:" in yaml_str

    def test_roundtrip(self):
        original = APISnapshot.from_module(pygeometry1, "1.0.0")
        yaml_str = original.to_yaml()
        loaded = APISnapshot.from_yaml(yaml_str)
        assert loaded.version == original.version
        assert loaded.functions.keys() == original.functions.keys()
        assert loaded.classes.keys() == original.classes.keys()

    def test_to_module_api(self):
        snapshot = APISnapshot.from_module(pygeometry1, "1.0.0")
        api = snapshot.to_module_api()
        assert isinstance(api, ModuleAPI)
        assert "area" in api.functions
        assert "Point" in api.classes

    def test_save_and_load(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            path = Path(tmpdir) / "test.yaml"
            original = APISnapshot.from_module(pygeometry1, "1.0.0")
            original.save(path)
            loaded = APISnapshot.load(path)
            assert loaded.version == original.version


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

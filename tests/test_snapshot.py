"""Tests for semver-dredd snapshot and new CLI commands."""

import tempfile
from pathlib import Path

import yaml

from cli import main
from example.py import pygeometry1, pygeometry2
from semverdredd.version import load_version_file, save_version_file
from snapshot.models import GeneratorInfo, NormalizedSnapshot


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
        assert (tmp_path / ".semver.yaml").exists()
        assert (tmp_path / "baked.yaml").exists()
        assert (tmp_path / "VERSION").exists()
        assert (tmp_path / "VERSION").read_text().strip() == "1.0.0"


class TestCLIStatus:
    """Tests for status command."""

    def test_status_detects_changes(self, capsys, tmp_path, monkeypatch):
        monkeypatch.chdir(tmp_path)
        # Init with pygeometry1
        main(
            [
                "init",
                "example.py.pygeometry1",
                "--plugin",
                "python",
                "--version",
                "1.0.0",
            ]
        )
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
        main(
            [
                "init",
                "example.py.pygeometry1",
                "--plugin",
                "python",
                "--version",
                "1.0.0",
            ]
        )
        # Bake pygeometry2
        result = main(["bake", "example.py.pygeometry2"])
        assert result == 0
        # VERSION should be updated
        version = (tmp_path / "VERSION").read_text().strip()
        assert version.startswith("1.1.")


class TestBundleCLIWorkflow:
    def _write_version(self, path: Path, version: str) -> None:
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(version + "\n")

    def _write_bundle_config(self, tmp_path: Path) -> None:
        (tmp_path / ".semver.yaml").write_text(
            """schema_version: 1
plugin: bundle

source:
  path: .

files:
  version: VERSION

include:
  - backend/VERSION
  - sdk-python/VERSION
"""
        )

    def test_snapshot_uses_bundle_config(self, tmp_path, monkeypatch):
        monkeypatch.chdir(tmp_path)
        self._write_version(tmp_path / "backend" / "VERSION", "1.2.3")
        self._write_version(tmp_path / "sdk-python" / "VERSION", "2.0.0")
        (tmp_path / "VERSION").write_text("5.0.0\n")
        self._write_bundle_config(tmp_path)

        out = tmp_path / "bundle-snapshot.yaml"
        result = main(["snapshot", "--out", str(out)])

        assert result == 0
        data = yaml.safe_load(out.read_text())
        assert data["language"] == "bundle"
        assert data["version"] == "5.0.0"
        assert sorted(data["api"]["dependencies"].keys()) == ["backend", "sdk-python"]

    def test_status_and_bake_work_for_bundle(self, tmp_path, monkeypatch, capsys):
        monkeypatch.chdir(tmp_path)
        self._write_version(tmp_path / "backend" / "VERSION", "1.2.3")
        self._write_version(tmp_path / "sdk-python" / "VERSION", "2.0.0")
        (tmp_path / "VERSION").write_text("5.0.0\n")
        self._write_bundle_config(tmp_path)

        snapshot_result = main(["snapshot", "--out", "baked.yaml"])
        assert snapshot_result == 0

        self._write_version(tmp_path / "backend" / "VERSION", "1.3.0")

        status_result = main(["status", "--details"])
        assert status_result == 0
        captured = capsys.readouterr()
        assert "MINOR" in captured.err
        assert "Suggested version: 5.1." in captured.out
        assert (tmp_path / "current.yaml").exists()

        bake_result = main(["bake"])
        assert bake_result == 0
        assert (tmp_path / "VERSION").read_text().strip().startswith("5.1.")
        baked = yaml.safe_load((tmp_path / "baked.yaml").read_text())
        assert baked["version"].startswith("5.1.")


class TestRun2GeneratorMetadata:
    """Tests for stable snapshot generator provenance (plan 03, step 3)."""

    def test_generator_info_round_trips_yaml(self):
        """GeneratorInfo serializes and deserializes through to_dict/from_dict."""
        gi = GeneratorInfo(
            plugin_name="python",
            plugin_version="1.0.0",
            plugin_source="entry_point",
            config_path=".semver.yaml",
            candidate_index=0,
        )
        data = gi.to_dict()
        gi2 = GeneratorInfo.from_dict(data)
        assert gi2.plugin_name == "python"
        assert gi2.plugin_version == "1.0.0"
        assert gi2.plugin_source == "entry_point"
        assert gi2.config_path == ".semver.yaml"
        assert gi2.candidate_index == 0

    def test_old_snapshot_without_generator_still_loads(self):
        """Old snapshots without a generator block deserialize without error."""
        old_yaml = """\
snapshot_type_id: d4e5f6a7-1234-5678-9abc-def012345678
schema_version: 2
version: 1.0.0
language: python
source:
  kind: module
  path: example.py.pygeometry1
api:
  functions: {}
  types: {}
"""
        snap = NormalizedSnapshot.from_yaml_str(old_yaml)
        assert snap.generator is None
        assert snap.version == "1.0.0"

    def test_new_snapshot_includes_generator_block(self):
        """Snapshots with a generator block deserialize and preserve all fields."""
        snap_with_gen = NormalizedSnapshot(
            version="2.0.0",
            language="python",
            generator=GeneratorInfo(
                plugin_name="python",
                plugin_version="3.10.0",
                plugin_source="builtin",
                config_path=".semver.yaml",
                candidate_index=-1,
            ),
        )
        yaml_str = snap_with_gen.to_yaml()
        assert "generator:" in yaml_str
        assert "plugin_name: python" in yaml_str

        loaded = NormalizedSnapshot.from_yaml_str(yaml_str)
        assert loaded.generator is not None
        assert loaded.generator.plugin_name == "python"
        assert loaded.generator.plugin_source == "builtin"

    def test_init_baked_snapshot_carries_generator(self, tmp_path, monkeypatch):
        """After init, baked.yaml contains a generator block with plugin provenance."""
        monkeypatch.chdir(tmp_path)
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

        baked_text = (tmp_path / "baked.yaml").read_text()
        baked_data = yaml.safe_load(baked_text)
        assert (
            "generator" in baked_data
        ), f"No generator block in baked.yaml: {baked_text}"
        assert baked_data["generator"]["plugin_name"] == "python"

    def test_snapshot_command_output_carries_generator(self, tmp_path, monkeypatch):
        """semver-dredd snapshot --out FILE should embed generator provenance."""
        monkeypatch.chdir(tmp_path)
        # Init first to get a config
        main(
            [
                "init",
                "example.py.pygeometry1",
                "--plugin",
                "python",
                "--version",
                "1.0.0",
            ]
        )

        out = tmp_path / "snap.yaml"
        result = main(["snapshot", "--out", str(out)])
        assert result == 0

        data = yaml.safe_load(out.read_text())
        assert "generator" in data, f"No generator block in snapshot: {out.read_text()}"
        assert data["generator"]["plugin_name"] == "python"


class TestRun2PluginMismatchWarning:
    """Tests for plugin mismatch assumptions surfacing (plan 03, step 4)."""

    def test_same_plugin_produces_no_mismatch_warning(
        self, tmp_path, monkeypatch, capsys
    ):
        """Same plugin for init and status: no mismatch warning emitted."""
        monkeypatch.chdir(tmp_path)
        main(
            [
                "init",
                "example.py.pygeometry1",
                "--plugin",
                "python",
                "--version",
                "1.0.0",
            ]
        )
        main(["status", "example.py.pygeometry1"])
        err = capsys.readouterr().err
        assert "plugin mismatch" not in err.lower()

    def test_mismatch_warning_when_baked_has_different_plugin(
        self, tmp_path, monkeypatch, capsys
    ):
        """When baked snapshot generator.plugin_name differs from current plugin, warn."""
        monkeypatch.chdir(tmp_path)
        main(
            [
                "init",
                "example.py.pygeometry1",
                "--plugin",
                "python",
                "--version",
                "1.0.0",
            ]
        )

        # Manually patch baked.yaml generator to claim it was made by 'go'
        baked_path = tmp_path / "baked.yaml"
        data = yaml.safe_load(baked_path.read_text())
        data["generator"] = {
            "plugin_name": "go",
            "plugin_version": "",
            "plugin_source": "entry_point",
            "config_path": "",
            "candidate_index": -1,
        }
        baked_path.write_text(
            yaml.dump(data, default_flow_style=False, sort_keys=False)
        )

        # Now run status with python plugin
        result = main(["status", "example.py.pygeometry1"])
        assert result == 0
        err = capsys.readouterr().err
        assert (
            "plugin mismatch" in err.lower()
        ), f"Expected mismatch warning in stderr: {err}"
        assert "go" in err
        assert "python" in err

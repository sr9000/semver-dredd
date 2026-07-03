from pathlib import Path

import yaml

from semverdredd.bundle_plugin import BundlePlugin, BundleSnapshot


def _write_version(path: Path, version: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(version + "\n")


class TestBundlePluginGeneration:
    def test_generate_snapshot_from_includes(self, tmp_path):
        _write_version(tmp_path / "backend" / "VERSION", "1.2.3")
        _write_version(tmp_path / "sdk-python" / "VERSION", "2.0.0")

        plugin = BundlePlugin()
        result = plugin.generate_snapshot(
            str(tmp_path),
            "9.9.9",
            options={
                "include": ["backend/VERSION", "sdk-python/VERSION"],
            },
        )

        assert result.success is True
        snap = BundleSnapshot.from_yaml_str(result.yaml_content)
        assert snap.version == "9.9.9"
        assert snap.source_kind == "bundle"
        assert snap.dependencies["backend"].path == "backend/VERSION"
        assert snap.dependencies["backend"].version == "1.2.3"
        assert snap.dependencies["sdk-python"].path == "sdk-python/VERSION"
        assert snap.dependencies["sdk-python"].version == "2.0.0"

    def test_generate_snapshot_rejects_missing_files(self, tmp_path):
        plugin = BundlePlugin()
        result = plugin.generate_snapshot(
            str(tmp_path),
            "1.0.0",
            options={"include": ["missing/VERSION"]},
        )

        assert result.success is False
        assert "not found" in (result.error_message or "").lower()

    def test_generate_snapshot_rejects_globs(self, tmp_path):
        plugin = BundlePlugin()
        result = plugin.generate_snapshot(
            str(tmp_path),
            "1.0.0",
            options={"include": ["services/*/VERSION"]},
        )

        assert result.success is False
        assert "does not support globs" in (result.error_message or "")

    def test_bundle_snapshot_yaml_is_stable(self, tmp_path):
        _write_version(tmp_path / "cli" / "VERSION", "3.4.5")
        plugin = BundlePlugin()
        result = plugin.generate_snapshot(
            str(tmp_path),
            "7.0.0",
            options={"include": ["cli/VERSION"]},
        )

        assert result.success is True
        payload = yaml.safe_load(result.yaml_content)
        assert payload["snapshot_type_id"] == BundleSnapshot.SNAPSHOT_TYPE_ID
        assert payload["language"] == "bundle"
        assert payload["api"]["dependencies"] == {
            "cli": {"path": "cli/VERSION", "version": "3.4.5"}
        }
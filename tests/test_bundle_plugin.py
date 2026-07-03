from pathlib import Path

import yaml

from semverdredd.bundle_plugin import BundleDependency, BundlePlugin, BundleSnapshot
from snapshot.change_kind import ChangeKind


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


def _bundle_snapshot_from_versions(dependencies: dict[str, str]) -> BundleSnapshot:
    return BundleSnapshot(
        version="1.0.0",
        dependencies={
            name: BundleDependency(
                name=name,
                path=f"{name}/VERSION",
                version=version,
            )
            for name, version in dependencies.items()
        },
    )


class TestBundleSnapshotDiff:
    def test_added_dependency_is_minor(self):
        old = _bundle_snapshot_from_versions({"backend": "1.0.0"})
        new = _bundle_snapshot_from_versions({"backend": "1.0.0", "cli": "1.0.0"})

        diff = old.diff_against(new)

        assert diff.change_kind == ChangeKind.MINOR
        assert "dependency added: cli (1.0.0)" in diff.added

    def test_removed_dependency_is_breaking(self):
        old = _bundle_snapshot_from_versions({"backend": "1.0.0", "cli": "1.0.0"})
        new = _bundle_snapshot_from_versions({"backend": "1.0.0"})

        diff = old.diff_against(new)

        assert diff.change_kind == ChangeKind.BREAKING
        assert "dependency removed: cli (1.0.0)" in diff.breaking

    def test_patch_increase_is_patch(self):
        old = _bundle_snapshot_from_versions({"backend": "1.0.0"})
        new = _bundle_snapshot_from_versions({"backend": "1.0.1"})

        diff = old.diff_against(new)

        assert diff.change_kind == ChangeKind.PATCH
        assert diff.breaking == ()
        assert diff.added == ()

    def test_minor_increase_is_minor(self):
        old = _bundle_snapshot_from_versions({"backend": "1.0.0"})
        new = _bundle_snapshot_from_versions({"backend": "1.1.0"})

        diff = old.diff_against(new)

        assert diff.change_kind == ChangeKind.MINOR
        assert "dependency minor increased: backend (1.0.0 -> 1.1.0)" in diff.added

    def test_major_increase_is_breaking(self):
        old = _bundle_snapshot_from_versions({"backend": "1.2.3"})
        new = _bundle_snapshot_from_versions({"backend": "2.0.0"})

        diff = old.diff_against(new)

        assert diff.change_kind == ChangeKind.BREAKING
        assert "dependency major increased: backend (1.2.3 -> 2.0.0)" in diff.breaking

    def test_patch_decrease_warns_and_is_patch(self, caplog):
        old = _bundle_snapshot_from_versions({"backend": "1.0.2"})
        new = _bundle_snapshot_from_versions({"backend": "1.0.1"})

        diff = old.diff_against(new)

        assert diff.change_kind == ChangeKind.PATCH
        assert any("patch version decreased" in rec.getMessage() for rec in caplog.records)

    def test_minor_decrease_warns_and_is_breaking(self, caplog):
        old = _bundle_snapshot_from_versions({"backend": "1.2.0"})
        new = _bundle_snapshot_from_versions({"backend": "1.1.9"})

        diff = old.diff_against(new)

        assert diff.change_kind == ChangeKind.BREAKING
        assert "dependency minor decreased: backend (1.2.0 -> 1.1.9)" in diff.breaking
        assert any("minor version decreased" in rec.getMessage() for rec in caplog.records)

    def test_major_decrease_warns_and_is_breaking(self, caplog):
        old = _bundle_snapshot_from_versions({"backend": "2.0.0"})
        new = _bundle_snapshot_from_versions({"backend": "1.9.9"})

        diff = old.diff_against(new)

        assert diff.change_kind == ChangeKind.BREAKING
        assert "dependency major decreased: backend (2.0.0 -> 1.9.9)" in diff.breaking
        assert any("major version decreased" in rec.getMessage() for rec in caplog.records)

    def test_no_change_is_none(self):
        old = _bundle_snapshot_from_versions({"backend": "1.0.0"})
        new = _bundle_snapshot_from_versions({"backend": "1.0.0"})

        diff = old.diff_against(new)

        assert diff.change_kind == ChangeKind.NONE
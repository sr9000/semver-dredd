"""Tests for semver-dredd's programmatic structured API."""

from semverdredd import ChangeKind, compare, compare_and_suggest


# Use paths/module names instead of module objects
PYGEOMETRY1 = "example.py.pygeometry1"
PYGEOMETRY2 = "example.py.pygeometry2"


class TestStructuredAPI:
    def test_compare_returns_pure_data(self):
        result = compare(PYGEOMETRY1, PYGEOMETRY2)
        assert result.change_kind == ChangeKind.MINOR
        assert result.severity == "warn"
        assert "minor" in result.description.lower()

    def test_compare_and_suggest(self):
        result = compare_and_suggest(PYGEOMETRY1, PYGEOMETRY2, "1.0.20260213001")
        assert result.change_kind == ChangeKind.MINOR
        assert str(result.current_version).startswith("1.0.")
        assert str(result.suggested_version).startswith("1.1.")

    def test_compare_includes_diff_details(self):
        result = compare(PYGEOMETRY1, PYGEOMETRY2)
        assert result.diff is not None
        assert result.diff.has_changes
        # v1 -> v2 adds volume function and translate method
        assert any("volume" in item for item in result.diff.added)
        assert any("translate" in item for item in result.diff.added)
        # No breaking changes
        assert len(result.diff.breaking) == 0

    def test_compare_breaking_diff_details(self):
        # v2 -> v1 is breaking
        result = compare(PYGEOMETRY2, PYGEOMETRY1)
        assert result.change_kind == ChangeKind.BREAKING
        assert result.diff.has_changes
        assert any("volume" in item for item in result.diff.breaking)
        assert any("translate" in item for item in result.diff.breaking)

    def test_compare_and_suggest_includes_diff(self):
        result = compare_and_suggest(PYGEOMETRY1, PYGEOMETRY2, "1.0.20260213001")
        assert result.diff is not None
        assert result.diff.has_changes
        assert any("volume" in item for item in result.diff.added)


class VersionRecordingPlugin:
    """Stub plugin that records version strings passed to generate_snapshot."""

    def __init__(self):
        self.seen_versions = []

    @property
    def name(self):
        return "version-recorder"

    @property
    def snapshot_format_class(self):
        return None

    def validate_path(self, path):
        return True, ""

    def generate_snapshot(self, path, version, options=None):
        from semverdredd import SnapshotResult

        self.seen_versions.append(version)
        return SnapshotResult(True, f"version: '{version}'\napi: {{}}\n")


class TestVersionThreading:
    """compare()/compare_and_suggest() pass meaningful versions to plugins."""

    def _register(self):
        from semverdredd.plugin_manager import get_plugin_manager

        plugin = VersionRecordingPlugin()
        get_plugin_manager().register(plugin)
        return plugin

    def _unregister(self):
        from semverdredd.plugin_manager import get_plugin_manager

        get_plugin_manager().unregister("version-recorder")

    def test_compare_threads_explicit_versions(self):
        plugin = self._register()
        try:
            compare(
                "old", "new",
                plugin="version-recorder",
                old_version="1.2.3",
                new_version="1.3.0",
            )
            assert plugin.seen_versions == ["1.2.3", "1.3.0"]
        finally:
            self._unregister()

    def test_compare_defaults_remain_000(self):
        plugin = self._register()
        try:
            compare("old", "new", plugin="version-recorder")
            assert plugin.seen_versions == ["0.0.0", "0.0.0"]
        finally:
            self._unregister()

    def test_compare_and_suggest_threads_current_version(self):
        plugin = self._register()
        try:
            compare_and_suggest(
                "old", "new", "2.5.20260101001", plugin="version-recorder"
            )
            assert plugin.seen_versions == ["2.5.20260101001", "2.5.20260101001"]
        finally:
            self._unregister()

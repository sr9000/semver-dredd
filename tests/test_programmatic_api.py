"""Tests for semver-dredd's programmatic structured API."""

from semverdredd import ChangeType, compare, compare_and_suggest


# Use paths/module names instead of module objects
PYGEOMETRY1 = "example.py.pygeometry1"
PYGEOMETRY2 = "example.py.pygeometry2"


class TestStructuredAPI:
    def test_compare_returns_pure_data(self):
        result = compare(PYGEOMETRY1, PYGEOMETRY2)
        assert result.change_type == ChangeType.MINOR
        assert result.severity == "warn"
        assert "minor" in result.description.lower()

    def test_compare_and_suggest(self):
        result = compare_and_suggest(PYGEOMETRY1, PYGEOMETRY2, "1.0.20260213001")
        assert result.change_type == ChangeType.MINOR
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
        assert result.change_type == ChangeType.MAJOR
        assert result.diff.has_changes
        assert any("volume" in item for item in result.diff.breaking)
        assert any("translate" in item for item in result.diff.breaking)

    def test_compare_and_suggest_includes_diff(self):
        result = compare_and_suggest(PYGEOMETRY1, PYGEOMETRY2, "1.0.20260213001")
        assert result.diff is not None
        assert result.diff.has_changes
        assert any("volume" in item for item in result.diff.added)

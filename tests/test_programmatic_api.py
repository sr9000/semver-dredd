"""Tests for semver-dredd's programmatic structured API."""

from example import pygeometry1, pygeometry2
from semverdredd import ChangeType, compare, compare_and_suggest


class TestStructuredAPI:
    def test_compare_returns_pure_data(self):
        result = compare(pygeometry1, pygeometry2)
        assert result.change_type == ChangeType.MINOR
        assert result.severity == "warn"
        assert "minor" in result.description.lower()

    def test_compare_and_suggest(self):
        result = compare_and_suggest(pygeometry1, pygeometry2, "1.0.20260213001")
        assert result.change_type == ChangeType.MINOR
        assert str(result.current_version).startswith("1.0.")
        assert str(result.suggested_version).startswith("1.1.")

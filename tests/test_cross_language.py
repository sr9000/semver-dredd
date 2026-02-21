"""Tests for cross-language snapshot loading, diff, and classification."""

import pytest
from pathlib import Path

from semverdredd.snapshot_io import (
    NormalizedSnapshot,
    load_snapshot,
    FunctionSignature,
    Parameter,
    TypeDefinition,
    Field,
)
from semverdredd.xldiff import (
    diff_snapshots,
    compare_snapshots,
)
from semverdredd.change_kind import ChangeKind
from semverdredd.protocols import DiffResult


FIXTURES_DIR = Path(__file__).parent / "fixtures"


class TestNormalizedSnapshot:
    """Tests for loading and normalizing snapshots."""

    def test_load_go_v1_baseline(self):
        snap = load_snapshot(FIXTURES_DIR / "go" / "v1_baseline.yaml")
        assert snap.schema_version == 2
        assert snap.version == "1.0.0"
        assert snap.language == "go"
        assert "Area" in snap.functions
        assert "Point" in snap.types

    def test_load_go_v2_minor(self):
        snap = load_snapshot(FIXTURES_DIR / "go" / "v2_minor.yaml")
        assert snap.version == "1.1.0"
        assert "Volume" in snap.functions
        assert "Translate" in snap.types["Point"].methods

    def test_function_signature_parsing(self):
        snap = load_snapshot(FIXTURES_DIR / "go" / "v1_baseline.yaml")
        area = snap.functions["Area"]
        assert len(area.parameters) == 2
        assert area.parameters[0].name == "w"
        assert area.parameters[0].type == "float64"
        assert not area.parameters[0].optional
        assert len(area.returns) == 1

    def test_type_definition_parsing(self):
        snap = load_snapshot(FIXTURES_DIR / "go" / "v1_baseline.yaml")
        point = snap.types["Point"]
        assert len(point.fields) == 2
        assert point.fields[0].name == "X"
        assert "Distance" in point.methods

    def test_roundtrip_yaml(self):
        snap = load_snapshot(FIXTURES_DIR / "go" / "v1_baseline.yaml")
        yaml_str = snap.to_yaml()
        reloaded = NormalizedSnapshot.from_yaml_str(yaml_str)
        assert reloaded.version == snap.version
        assert reloaded.language == snap.language
        assert set(reloaded.functions.keys()) == set(snap.functions.keys())
        assert set(reloaded.types.keys()) == set(snap.types.keys())


class TestSnapshotDiff:
    """Tests for cross-language diff engine."""

    def test_no_changes(self):
        snap = load_snapshot(FIXTURES_DIR / "go" / "v1_baseline.yaml")
        diff = diff_snapshots(snap, snap)
        assert not diff.breaking
        assert not diff.added
        assert not diff.has_changes

    def test_added_function(self):
        old = load_snapshot(FIXTURES_DIR / "go" / "v1_baseline.yaml")
        new = load_snapshot(FIXTURES_DIR / "go" / "v2_minor.yaml")
        diff = diff_snapshots(old, new)
        assert "function added: Volume" in diff.added
        assert not diff.breaking

    def test_added_method(self):
        old = load_snapshot(FIXTURES_DIR / "go" / "v1_baseline.yaml")
        new = load_snapshot(FIXTURES_DIR / "go" / "v2_minor.yaml")
        diff = diff_snapshots(old, new)
        assert "type Point: method added: Translate" in diff.added

    def test_added_field(self):
        old = load_snapshot(FIXTURES_DIR / "go" / "v1_baseline.yaml")
        new = load_snapshot(FIXTURES_DIR / "go" / "v2_minor.yaml")
        diff = diff_snapshots(old, new)
        assert "type Point: field added: Z" in diff.added

    def test_removed_function(self):
        old = load_snapshot(FIXTURES_DIR / "go" / "v2_minor.yaml")
        new = load_snapshot(FIXTURES_DIR / "go" / "v1_baseline.yaml")
        diff = diff_snapshots(old, new)
        assert "function removed: Volume" in diff.breaking

    def test_removed_field(self):
        old = load_snapshot(FIXTURES_DIR / "go" / "v1_baseline.yaml")
        new = load_snapshot(FIXTURES_DIR / "go" / "v3_breaking.yaml")
        diff = diff_snapshots(old, new)
        assert "type Point: field removed: Y" in diff.breaking

    def test_parameter_count_change(self):
        old = load_snapshot(FIXTURES_DIR / "go" / "v1_baseline.yaml")
        new = load_snapshot(FIXTURES_DIR / "go" / "v3_breaking.yaml")
        diff = diff_snapshots(old, new)
        assert any("parameters removed" in b for b in diff.breaking)

    def test_return_type_change(self):
        old = load_snapshot(FIXTURES_DIR / "go" / "v1_baseline.yaml")
        new = load_snapshot(FIXTURES_DIR / "go" / "v3_breaking.yaml")
        diff = diff_snapshots(old, new)
        assert any("return type changed" in b for b in diff.breaking)


class TestChangeClassification:
    """Tests for change type classification."""

    def test_no_changes_is_none(self):
        snap = load_snapshot(FIXTURES_DIR / "go" / "v1_baseline.yaml")
        diff = diff_snapshots(snap, snap)
        assert diff.change_kind == ChangeKind.NONE

    def test_additions_only_is_minor(self):
        old = load_snapshot(FIXTURES_DIR / "go" / "v1_baseline.yaml")
        new = load_snapshot(FIXTURES_DIR / "go" / "v2_minor.yaml")
        diff = diff_snapshots(old, new)
        assert diff.change_kind == ChangeKind.MINOR

    def test_breaking_is_breaking(self):
        old = load_snapshot(FIXTURES_DIR / "go" / "v1_baseline.yaml")
        new = load_snapshot(FIXTURES_DIR / "go" / "v3_breaking.yaml")
        diff = diff_snapshots(old, new)
        assert diff.change_kind == ChangeKind.BREAKING

    def test_compare_snapshots_returns_diff_result(self):
        old = load_snapshot(FIXTURES_DIR / "go" / "v1_baseline.yaml")
        new = load_snapshot(FIXTURES_DIR / "go" / "v2_minor.yaml")
        diff = compare_snapshots(old, new)
        assert diff.change_kind == ChangeKind.MINOR
        assert isinstance(diff, DiffResult)


class TestBackwardCompatibility:
    """Tests for loading v1 format snapshots."""

    def test_load_v1_style_python_snapshot(self):
        # Simulates a v1 Python snapshot (no schema_version, uses 'classes')
        v1_yaml = """
version: "1.0.0"
api:
  functions:
    area:
      parameters:
        - width
        - height
      defaults_count: 0
  classes:
    Point:
      methods:
        __init__:
          parameters:
            - self
            - x
            - y
          defaults_count: 0
      fields:
        - x
        - y
"""
        snap = NormalizedSnapshot.from_yaml_str(v1_yaml)
        assert snap.schema_version == 1
        assert snap.language == "python"
        assert "area" in snap.functions
        assert "Point" in snap.types

    def test_v1_parameters_converted_to_v2(self):
        v1_yaml = """
version: "1.0.0"
api:
  functions:
    calc:
      parameters:
        - a
        - b
      defaults_count: 1
  classes: {}
"""
        snap = NormalizedSnapshot.from_yaml_str(v1_yaml)
        calc = snap.functions["calc"]
        assert len(calc.parameters) == 2
        assert calc.parameters[0].type == "unknown"
        assert not calc.parameters[0].optional  # first param is required
        assert calc.parameters[1].optional  # second param has default

"""Tests for the pluggable snapshot format and diff scorer system.

Verifies that:
- The default behaviour is unchanged when plugin returns None.
- A plugin can provide a custom SnapshotFormat class.
- A plugin can provide a custom DiffScorer.
- The SnapshotFormat protocol is satisfied by NormalizedSnapshot.
- ChangeKind ↔ ChangeType bridge works correctly.
"""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Any, Optional

import pytest
import yaml

from semverdredd.plugin_base import (
    ChangeKind,
    DiffResult,
    DiffScorer,
    LanguagePlugin,
    SnapshotFormat,
    SnapshotResult,
)
from semverdredd.snapshot_io import NormalizedSnapshot
from semverdredd.xldiff import (
    ChangeType,
    DefaultDiffScorer,
    change_kind_to_type,
    change_type_to_kind,
    compare_snapshots,
)


# ---------------------------------------------------------------------------
# Protocol conformance
# ---------------------------------------------------------------------------

class TestSnapshotFormatProtocol:
    """NormalizedSnapshot must satisfy the SnapshotFormat protocol."""

    def test_normalized_snapshot_is_snapshot_format(self):
        assert isinstance(NormalizedSnapshot, type)
        # runtime_checkable Protocol check on an instance
        snap = NormalizedSnapshot(
            schema_version=2,
            version="1.0.0",
            language="python",
            source_kind="module",
            source_path="example",
            functions={},
            types={},
        )
        assert isinstance(snap, SnapshotFormat)

    def test_has_required_methods(self):
        """NormalizedSnapshot exposes all SnapshotFormat methods."""
        assert callable(getattr(NormalizedSnapshot, "to_yaml", None))
        assert callable(getattr(NormalizedSnapshot, "from_yaml_str", None))
        assert callable(getattr(NormalizedSnapshot, "from_file", None))
        assert callable(getattr(NormalizedSnapshot, "to_dict", None))

    def test_version_property(self):
        snap = NormalizedSnapshot(
            schema_version=2,
            version="2.3.4",
            language="go",
            source_kind="package",
            source_path="example",
            functions={},
            types={},
        )
        assert snap.version == "2.3.4"


# ---------------------------------------------------------------------------
# ChangeKind ↔ ChangeType bridge
# ---------------------------------------------------------------------------

class TestChangeKindBridge:
    @pytest.mark.parametrize("ct, ck", [
        (ChangeType.NONE, ChangeKind.NONE),
        (ChangeType.PATCH, ChangeKind.PATCH),
        (ChangeType.MINOR, ChangeKind.MINOR),
        (ChangeType.MAJOR, ChangeKind.BREAKING),
    ])
    def test_round_trip(self, ct, ck):
        assert change_type_to_kind(ct) == ck
        assert change_kind_to_type(ck) == ct


# ---------------------------------------------------------------------------
# DefaultDiffScorer
# ---------------------------------------------------------------------------

_YAML_V2_BASELINE = yaml.dump({
    "schema_version": 2,
    "version": "1.0.0",
    "language": "python",
    "source": {"kind": "module", "path": "mymod"},
    "api": {
        "functions": {
            "foo": {
                "parameters": [
                    {"name": "x", "type": "int", "optional": False},
                ],
                "returns": [],
            },
        },
        "types": {},
    },
}, default_flow_style=False)

_YAML_V2_MINOR = yaml.dump({
    "schema_version": 2,
    "version": "1.1.0",
    "language": "python",
    "source": {"kind": "module", "path": "mymod"},
    "api": {
        "functions": {
            "foo": {
                "parameters": [
                    {"name": "x", "type": "int", "optional": False},
                ],
                "returns": [],
            },
            "bar": {
                "parameters": [],
                "returns": [],
            },
        },
        "types": {},
    },
}, default_flow_style=False)

_YAML_V2_BREAKING = yaml.dump({
    "schema_version": 2,
    "version": "2.0.0",
    "language": "python",
    "source": {"kind": "module", "path": "mymod"},
    "api": {
        "functions": {},
        "types": {},
    },
}, default_flow_style=False)


class TestDefaultDiffScorer:
    def test_no_change(self):
        snap = NormalizedSnapshot.from_yaml_str(_YAML_V2_BASELINE)
        scorer = DefaultDiffScorer()
        result = scorer.diff(snap, snap)
        assert result.change_kind == ChangeKind.NONE
        assert not result.has_changes

    def test_minor_change(self):
        old = NormalizedSnapshot.from_yaml_str(_YAML_V2_BASELINE)
        new = NormalizedSnapshot.from_yaml_str(_YAML_V2_MINOR)
        scorer = DefaultDiffScorer()
        result = scorer.diff(old, new)
        assert result.change_kind == ChangeKind.MINOR
        assert result.has_changes
        assert any("bar" in a for a in result.added)

    def test_breaking_change(self):
        old = NormalizedSnapshot.from_yaml_str(_YAML_V2_BASELINE)
        new = NormalizedSnapshot.from_yaml_str(_YAML_V2_BREAKING)
        scorer = DefaultDiffScorer()
        result = scorer.diff(old, new)
        assert result.change_kind == ChangeKind.BREAKING
        assert result.has_changes
        assert any("foo" in b for b in result.breaking)

    def test_compare_convenience(self):
        """compare() is an alias for diff()."""
        old = NormalizedSnapshot.from_yaml_str(_YAML_V2_BASELINE)
        new = NormalizedSnapshot.from_yaml_str(_YAML_V2_MINOR)
        scorer = DefaultDiffScorer()
        assert scorer.compare(old, new) == scorer.diff(old, new)

    def test_diff_result_matches_compare_snapshots(self):
        """DefaultDiffScorer should agree with the legacy compare_snapshots."""
        old = NormalizedSnapshot.from_yaml_str(_YAML_V2_BASELINE)
        new = NormalizedSnapshot.from_yaml_str(_YAML_V2_MINOR)

        scorer = DefaultDiffScorer()
        result = scorer.diff(old, new)
        change, diff = compare_snapshots(old, new)

        assert change_type_to_kind(change) == result.change_kind
        assert diff.breaking == result.breaking
        assert diff.added == result.added


# ---------------------------------------------------------------------------
# Custom SnapshotFormat + custom DiffScorer via LanguagePlugin
# ---------------------------------------------------------------------------

@dataclass
class ToySnapshot:
    """A trivially simple snapshot for testing the pluggable system."""
    version: str
    names: frozenset[str]

    def to_yaml(self) -> str:
        return yaml.dump({"version": self.version, "names": sorted(self.names)})

    @classmethod
    def from_yaml_str(cls, yaml_str: str) -> "ToySnapshot":
        data = yaml.safe_load(yaml_str)
        return cls(version=data.get("version", ""), names=frozenset(data.get("names", [])))

    @classmethod
    def from_file(cls, path: Path | str) -> "ToySnapshot":
        return cls.from_yaml_str(Path(path).read_text())

    def to_dict(self) -> dict[str, Any]:
        return {"version": self.version, "names": sorted(self.names)}


class ToyDiffScorer(DiffScorer):
    """Scores diffs of ToySnapshot: removed names → breaking, added → minor."""

    def diff(self, old: ToySnapshot, new: ToySnapshot) -> DiffResult:
        removed = old.names - new.names
        added = new.names - old.names
        if removed:
            kind = ChangeKind.BREAKING
        elif added:
            kind = ChangeKind.MINOR
        else:
            kind = ChangeKind.NONE
        return DiffResult(
            change_kind=kind,
            breaking=tuple(f"removed: {n}" for n in sorted(removed)),
            added=tuple(f"added: {n}" for n in sorted(added)),
        )


class ToyPlugin(LanguagePlugin):
    """A toy plugin that uses a custom snapshot format and diff scorer."""

    @property
    def name(self) -> str:
        return "toy"

    def generate_snapshot(self, path: str, version: str, options: Optional[dict[str, Any]] = None) -> SnapshotResult:
        snap = ToySnapshot(version=version, names=frozenset(["a", "b"]))
        return SnapshotResult(success=True, yaml_content=snap.to_yaml())

    @property
    def snapshot_format_class(self) -> type[SnapshotFormat] | None:
        return ToySnapshot  # type: ignore[return-value]

    @property
    def diff_scorer(self) -> DiffScorer | None:
        return ToyDiffScorer()


class TestCustomPlugin:
    def test_toy_snapshot_roundtrip(self):
        snap = ToySnapshot(version="1.0.0", names=frozenset(["x", "y"]))
        yaml_str = snap.to_yaml()
        loaded = ToySnapshot.from_yaml_str(yaml_str)
        assert loaded.version == snap.version
        assert loaded.names == snap.names

    def test_toy_diff_scorer_no_change(self):
        old = ToySnapshot(version="1.0.0", names=frozenset(["a", "b"]))
        new = ToySnapshot(version="1.0.0", names=frozenset(["a", "b"]))
        result = ToyDiffScorer().diff(old, new)
        assert result.change_kind == ChangeKind.NONE

    def test_toy_diff_scorer_minor(self):
        old = ToySnapshot(version="1.0.0", names=frozenset(["a"]))
        new = ToySnapshot(version="1.0.0", names=frozenset(["a", "b"]))
        result = ToyDiffScorer().diff(old, new)
        assert result.change_kind == ChangeKind.MINOR
        assert ("added: b",) == result.added

    def test_toy_diff_scorer_breaking(self):
        old = ToySnapshot(version="1.0.0", names=frozenset(["a", "b"]))
        new = ToySnapshot(version="1.0.0", names=frozenset(["a"]))
        result = ToyDiffScorer().diff(old, new)
        assert result.change_kind == ChangeKind.BREAKING
        assert ("removed: b",) == result.breaking

    def test_plugin_hooks(self):
        plugin = ToyPlugin()
        assert plugin.snapshot_format_class is ToySnapshot
        assert isinstance(plugin.diff_scorer, ToyDiffScorer)

    def test_default_plugin_hooks_are_none(self):
        """A plugin that doesn't override hooks returns None."""
        class MinimalPlugin(LanguagePlugin):
            @property
            def name(self) -> str:
                return "minimal"

            def generate_snapshot(self, path, version, options=None):
                return SnapshotResult(True, "")

        p = MinimalPlugin()
        assert p.snapshot_format_class is None
        assert p.diff_scorer is None

    def test_toy_snapshot_save_load(self, tmp_path):
        snap = ToySnapshot(version="0.5.0", names=frozenset(["alpha", "beta"]))
        fpath = tmp_path / "snap.yaml"
        fpath.write_text(snap.to_yaml())
        loaded = ToySnapshot.from_file(fpath)
        assert loaded.version == "0.5.0"
        assert loaded.names == frozenset(["alpha", "beta"])


# ---------------------------------------------------------------------------
# Integration: _resolve helpers
# ---------------------------------------------------------------------------

class TestResolveHelpers:
    def test_resolve_snapshot_class_default(self):
        from semverdredd import _resolve_snapshot_class
        assert _resolve_snapshot_class(None) is NormalizedSnapshot

    def test_resolve_snapshot_class_custom(self):
        from semverdredd import _resolve_snapshot_class
        plugin = ToyPlugin()
        assert _resolve_snapshot_class(plugin) is ToySnapshot

    def test_resolve_diff_scorer_default(self):
        from semverdredd import _resolve_diff_scorer
        scorer = _resolve_diff_scorer(None)
        assert isinstance(scorer, DefaultDiffScorer)

    def test_resolve_diff_scorer_custom(self):
        from semverdredd import _resolve_diff_scorer
        plugin = ToyPlugin()
        scorer = _resolve_diff_scorer(plugin)
        assert isinstance(scorer, ToyDiffScorer)


# ---------------------------------------------------------------------------
# DiffResult dataclass
# ---------------------------------------------------------------------------

class TestDiffResult:
    def test_defaults(self):
        r = DiffResult(change_kind=ChangeKind.NONE)
        assert r.breaking == ()
        assert r.added == ()
        assert not r.has_changes

    def test_has_changes_true(self):
        r = DiffResult(change_kind=ChangeKind.MINOR, added=("something",))
        assert r.has_changes

    def test_frozen(self):
        r = DiffResult(change_kind=ChangeKind.NONE)
        with pytest.raises(AttributeError):
            r.change_kind = ChangeKind.MAJOR  # type: ignore[misc]

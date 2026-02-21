"""Cross-language API diff engine for semver-dredd.

This module compares two NormalizedSnapshots and produces a detailed diff
that explains what changed and whether changes are breaking or additive.

Works with snapshots from any supported language (Python, Go, Java).
"""

from __future__ import annotations

from snapshot.change_kind import ChangeKind
from snapshot.protocols import DiffScorer, DiffResult
from snapshot import FunctionSignature, TypeDefinition, NormalizedSnapshot


def diff_snapshots(old: NormalizedSnapshot, new: NormalizedSnapshot) -> DiffResult:
    """Compare two snapshots and return a DiffResult."""
    breaking: list[str] = []
    added: list[str] = []

    # Compare functions
    _diff_functions(old.functions, new.functions, breaking, added)

    # Compare types
    _diff_types(old.types, new.types, breaking, added)

    if breaking:
        change = ChangeKind.BREAKING
    elif added:
        change = ChangeKind.MINOR
    else:
        change = ChangeKind.NONE

    return DiffResult(
        change_kind=change,
        breaking=tuple(breaking),
        added=tuple(added),
    )


def _diff_functions(
    old: dict[str, FunctionSignature],
    new: dict[str, FunctionSignature],
    breaking: list[str],
    added: list[str],
) -> None:
    """Compare function sets."""
    old_names = set(old.keys())
    new_names = set(new.keys())

    # Removed functions -> breaking
    for name in sorted(old_names - new_names):
        breaking.append(f"function removed: {name}")

    # Added functions -> additive
    for name in sorted(new_names - old_names):
        added.append(f"function added: {name}")

    # Changed functions
    for name in sorted(old_names & new_names):
        _diff_signature(
            f"function {name}",
            old[name],
            new[name],
            breaking,
            added,
        )


def _diff_types(
    old: dict[str, TypeDefinition],
    new: dict[str, TypeDefinition],
    breaking: list[str],
    added: list[str],
) -> None:
    """Compare type sets."""
    old_names = set(old.keys())
    new_names = set(new.keys())

    # Removed types -> breaking
    for name in sorted(old_names - new_names):
        breaking.append(f"type removed: {name}")

    # Added types -> additive
    for name in sorted(new_names - old_names):
        added.append(f"type added: {name}")

    # Changed types
    for name in sorted(old_names & new_names):
        _diff_type(name, old[name], new[name], breaking, added)


def _diff_type(
    name: str,
    old: TypeDefinition,
    new: TypeDefinition,
    breaking: list[str],
    added: list[str],
) -> None:
    """Compare two type definitions."""
    # Compare fields
    old_fields = {f.name: f for f in old.fields}
    new_fields = {f.name: f for f in new.fields}

    old_field_names = set(old_fields.keys())
    new_field_names = set(new_fields.keys())

    # Removed fields -> breaking
    for field_name in sorted(old_field_names - new_field_names):
        breaking.append(f"type {name}: field removed: {field_name}")

    # Added fields -> additive
    for field_name in sorted(new_field_names - old_field_names):
        added.append(f"type {name}: field added: {field_name}")

    # Changed fields (type changes)
    for field_name in sorted(old_field_names & new_field_names):
        old_field = old_fields[field_name]
        new_field = new_fields[field_name]
        if old_field.type != new_field.type:
            breaking.append(
                f"type {name}: field {field_name} type changed: "
                f"{old_field.type} -> {new_field.type}"
            )

    # Compare methods
    old_methods = old.methods
    new_methods = new.methods

    old_method_names = set(old_methods.keys())
    new_method_names = set(new_methods.keys())

    # Removed methods -> breaking
    for method_name in sorted(old_method_names - new_method_names):
        breaking.append(f"type {name}: method removed: {method_name}")

    # Added methods -> additive
    for method_name in sorted(new_method_names - old_method_names):
        added.append(f"type {name}: method added: {method_name}")

    # Changed methods
    for method_name in sorted(old_method_names & new_method_names):
        _diff_signature(
            f"type {name}: method {method_name}",
            old_methods[method_name],
            new_methods[method_name],
            breaking,
            added,
        )


def _diff_signature(
    prefix: str,
    old: FunctionSignature,
    new: FunctionSignature,
    breaking: list[str],
    added: list[str],
) -> None:
    """Compare two function/method signatures."""
    old_params = old.parameters
    new_params = new.parameters

    # Count required params
    old_required = sum(1 for p in old_params if not p.optional)
    new_required = sum(1 for p in new_params if not p.optional)

    # Check for breaking signature changes
    is_breaking = False
    is_additive = False

    # More required params -> breaking
    if new_required > old_required:
        breaking.append(
            f"{prefix}: requires more parameters " f"({old_required} -> {new_required})"
        )
        is_breaking = True

    # Fewer total params (removed) -> breaking
    if len(new_params) < len(old_params):
        breaking.append(
            f"{prefix}: parameters removed " f"({len(old_params)} -> {len(new_params)})"
        )
        is_breaking = True

    # More total params with same or fewer required -> additive
    if len(new_params) > len(old_params) and new_required <= old_required:
        added.append(
            f"{prefix}: new optional parameters added "
            f"({len(old_params)} -> {len(new_params)})"
        )
        is_additive = True

    # Fewer required (more defaults) -> additive
    if new_required < old_required and not is_breaking:
        added.append(
            f"{prefix}: fewer required parameters "
            f"({old_required} -> {new_required})"
        )
        is_additive = True

    # Check parameter type changes (only for params that exist in both)
    min_params = min(len(old_params), len(new_params))
    for i in range(min_params):
        old_p = old_params[i]
        new_p = new_params[i]

        # Type change -> breaking
        if (
            old_p.type != new_p.type
            and old_p.type != "unknown"
            and new_p.type != "unknown"
        ):
            breaking.append(
                f"{prefix}: parameter '{old_p.name}' type changed: "
                f"{old_p.type} -> {new_p.type}"
            )
            is_breaking = True

        # Optional -> Required -> breaking
        if old_p.optional and not new_p.optional:
            breaking.append(
                f"{prefix}: parameter '{old_p.name}' changed from optional to required"
            )
            is_breaking = True

        # Required -> Optional -> additive (already captured by required count)

    # Check return type changes
    if old.returns and new.returns:
        old_ret = old.returns[0]
        new_ret = new.returns[0]
        if (
            old_ret.type != new_ret.type
            and old_ret.type != "unknown"
            and new_ret.type != "unknown"
        ):
            breaking.append(
                f"{prefix}: return type changed: {old_ret.type} -> {new_ret.type}"
            )
            is_breaking = True
    elif old.returns and not new.returns:
        # Had returns, now doesn't -> breaking
        breaking.append(f"{prefix}: return value removed")
        is_breaking = True
    elif not old.returns and new.returns:
        # Didn't have returns, now does -> could be breaking for callers
        # But typically additive; leave as-is for now
        pass


def compare_snapshots(
    old: NormalizedSnapshot,
    new: NormalizedSnapshot,
) -> DiffResult:
    """Compare two snapshots and return a DiffResult."""
    return diff_snapshots(old, new)


def compare_snapshot_files(
    old_path: str,
    new_path: str,
) -> DiffResult:
    """Compare two snapshot files."""
    from semverdredd.registry import load_snapshot

    old = load_snapshot(old_path)
    new = load_snapshot(new_path)
    return compare_snapshots(old, new)


# ---------------------------------------------------------------------------
# Default diff scorer
# ---------------------------------------------------------------------------


class DefaultDiffScorer(DiffScorer):
    """Default diff scorer wrapping ``diff_snapshots``."""

    def diff(self, old: NormalizedSnapshot, new: NormalizedSnapshot) -> DiffResult:
        return diff_snapshots(old, new)

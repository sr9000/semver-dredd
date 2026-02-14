"""API diff utilities for semver-dredd.

These helpers power the CLI's `--details` output and can also be used
programmatically.

The goal is to explain *why* a change is MAJOR/MINOR by listing:
- breaking changes (removals / incompatible signature changes)
- additions (new functions/classes/methods, new optional params)

No logging/printing in this module.
"""

from __future__ import annotations

from types import ModuleType

from semverdredd import (
    APISignature,
    ChangeType,
    ClassAPI,
    ModuleAPI,
    compare_signatures,
)
from semverdredd.result import APIDiff


def _fmt_sig(sig: APISignature) -> str:
    # Keep it simple: name(param1, param2, ...)
    params = ", ".join(sig.parameters)
    return f"{sig.name}({params})"


def diff_modules(old: ModuleAPI, new: ModuleAPI) -> APIDiff:
    """Compute a human-readable API diff between two ModuleAPI objects."""

    breaking: list[str] = []
    added: list[str] = []

    # Functions removed/added
    for func_name in sorted(old.functions):
        if func_name not in new.functions:
            breaking.append(f"function removed: {func_name}")

    for func_name in sorted(new.functions):
        if func_name not in old.functions:
            added.append(f"function added: {func_name}")

    # Functions changed
    for func_name in sorted(set(old.functions) & set(new.functions)):
        old_sig = old.functions[func_name]
        new_sig = new.functions[func_name]
        change = compare_signatures(old_sig, new_sig)
        if change == ChangeType.MAJOR:
            breaking.append(f"function signature changed (breaking): {_fmt_sig(old_sig)} -> {_fmt_sig(new_sig)}")
        elif change == ChangeType.MINOR:
            added.append(f"function signature changed (compatible): {_fmt_sig(old_sig)} -> {_fmt_sig(new_sig)}")

    # Classes removed/added
    for class_name in sorted(old.classes):
        if class_name not in new.classes:
            breaking.append(f"class removed: {class_name}")

    for class_name in sorted(new.classes):
        if class_name not in old.classes:
            added.append(f"class added: {class_name}")

    # Classes changed
    for class_name in sorted(set(old.classes) & set(new.classes)):
        breaking_cls, added_cls = diff_classes(old.classes[class_name], new.classes[class_name])
        for b in breaking_cls:
            breaking.append(f"class {class_name}: {b}")
        for a in added_cls:
            added.append(f"class {class_name}: {a}")

    return APIDiff(breaking=tuple(breaking), added=tuple(added))


def diff_classes(old: ClassAPI, new: ClassAPI) -> tuple[list[str], list[str]]:
    """Return (breaking, added) change lists for a class."""

    breaking: list[str] = []
    added: list[str] = []

    for method_name in sorted(old.methods):
        if method_name not in new.methods:
            breaking.append(f"method removed: {method_name}")

    for method_name in sorted(new.methods):
        if method_name not in old.methods:
            added.append(f"method added: {method_name}")

    for method_name in sorted(set(old.methods) & set(new.methods)):
        old_sig = old.methods[method_name]
        new_sig = new.methods[method_name]
        change = compare_signatures(old_sig, new_sig)
        if change == ChangeType.MAJOR:
            breaking.append(f"method signature changed (breaking): {_fmt_sig(old_sig)} -> {_fmt_sig(new_sig)}")
        elif change == ChangeType.MINOR:
            added.append(f"method signature changed (compatible): {_fmt_sig(old_sig)} -> {_fmt_sig(new_sig)}")

    return breaking, added


def diff_module_objects(old_module: ModuleType, new_module: ModuleType) -> APIDiff:
    """Convenience: diff two imported module objects."""

    return diff_modules(ModuleAPI.from_module(old_module), ModuleAPI.from_module(new_module))

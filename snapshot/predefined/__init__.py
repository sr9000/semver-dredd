"""snapshot.predefined — built-in snapshot component models.

All five predefined types are automatically registered with the global
:data:`~semverdredd.registry.default_registry` on first import so they
can be round-tripped through YAML by the registry.

Language-specific argument types (e.g. ``PythonArgument``) live in their
respective language plugins.

Usage::

    from snapshot.predefined import (
        Variable, Argument,
        Function, ClassField, ClassMethod,
    )
"""

from __future__ import annotations

from snapshot.predefined.models import (  # Models; Type ID constants; Bulk lists
    ALL_CLASSES,
    ALL_TYPE_IDS,
    ARGUMENT_TYPE_ID,
    CLASS_FIELD_TYPE_ID,
    CLASS_METHOD_TYPE_ID,
    FUNCTION_TYPE_ID,
    VARIABLE_TYPE_ID,
    Argument,
    ClassField,
    ClassMethod,
    Function,
    Variable,
)


def _register_all() -> None:
    """Register every predefined model in the default registry (idempotent)."""
    from semverdredd.registry import default_registry

    for cls in ALL_CLASSES:
        try:
            default_registry.register(cls)
        except ValueError:
            pass  # already registered — safe to ignore


_register_all()


__all__ = [
    # Models
    "Variable",
    "Argument",
    "Function",
    "ClassField",
    "ClassMethod",
    # Type ID constants
    "VARIABLE_TYPE_ID",
    "ARGUMENT_TYPE_ID",
    "FUNCTION_TYPE_ID",
    "CLASS_FIELD_TYPE_ID",
    "CLASS_METHOD_TYPE_ID",
    # Bulk access
    "ALL_CLASSES",
    "ALL_TYPE_IDS",
]

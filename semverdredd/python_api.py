"""Python-specific API types for semver-dredd.

These classes are used for introspecting Python modules.
They are internal implementation details used by the Python plugin.
"""

from __future__ import annotations

import inspect
from dataclasses import dataclass
from types import ModuleType
from typing import TYPE_CHECKING, Any

if TYPE_CHECKING:
    from snapshot import ChangeKind


@dataclass
class APISignature:
    """Represents the signature of a callable (function/method)."""

    name: str
    parameters: list[str]
    defaults_count: int

    @classmethod
    def from_callable(cls, name: str, obj: Any) -> "APISignature":
        """Create an APISignature from a callable object."""
        sig = inspect.signature(obj)
        params = list(sig.parameters.keys())
        defaults_count = sum(
            1
            for p in sig.parameters.values()
            if p.default is not inspect.Parameter.empty
        )
        return cls(name=name, parameters=params, defaults_count=defaults_count)


@dataclass
class ClassAPI:
    """Represents the public API of a class."""

    name: str
    methods: dict[str, APISignature]
    fields: set[str]  # Public fields (for structured types only)

    @classmethod
    def from_class(cls, name: str, klass: type) -> "ClassAPI":
        """Extract public API from a class."""
        methods = {}
        fields = set()

        # Extract methods
        for attr_name in dir(klass):
            if attr_name.startswith("_") and not attr_name == "__init__":
                continue
            attr = getattr(klass, attr_name)
            if callable(attr):
                try:
                    methods[attr_name] = APISignature.from_callable(attr_name, attr)
                except (ValueError, TypeError):
                    pass

        # Extract fields for structured types
        if _is_namedtuple(klass):
            fields = set(getattr(klass, "_fields", ()))
        elif _is_dataclass(klass):
            fields = set(getattr(klass, "__dataclass_fields__", {}).keys())
        elif _is_pydantic_model(klass):
            # Support both Pydantic v1 and v2
            if hasattr(klass, "model_fields"):  # v2
                fields = set(klass.model_fields.keys())
            elif hasattr(klass, "__fields__"):  # v1
                fields = set(klass.__fields__.keys())
        elif hasattr(klass, "__slots__"):
            # __slots__ defines allowed attributes
            slots = getattr(klass, "__slots__", ())
            if isinstance(slots, str):
                fields = {slots}
            else:
                fields = set(slots)

        return cls(name=name, methods=methods, fields=fields)


def _is_namedtuple(klass: type) -> bool:
    """Check if class is a namedtuple."""
    return (
        hasattr(klass, "_fields")
        and hasattr(klass, "_field_defaults")
        and issubclass(klass, tuple)
    )


def _is_dataclass(klass: type) -> bool:
    """Check if class is a dataclass."""
    return hasattr(klass, "__dataclass_fields__")


def _is_pydantic_model(klass: type) -> bool:
    """Check if class is a Pydantic model."""
    return hasattr(klass, "model_fields") or hasattr(klass, "__fields__")


@dataclass
class ModuleAPI:
    """Represents the public API of a module."""

    functions: dict[str, APISignature]
    classes: dict[str, ClassAPI]

    @classmethod
    def from_module(cls, module: ModuleType) -> "ModuleAPI":
        """Extract public API from a module."""
        functions = {}
        classes = {}

        for name in dir(module):
            if name.startswith("_"):
                continue
            obj = getattr(module, name)
            if inspect.isclass(obj):
                classes[name] = ClassAPI.from_class(name, obj)
            elif callable(obj):
                try:
                    functions[name] = APISignature.from_callable(name, obj)
                except (ValueError, TypeError):
                    pass

        return cls(functions=functions, classes=classes)


def compare_signatures(old: APISignature, new: APISignature) -> "ChangeKind":
    """Compare two function/method signatures for compatibility."""
    from snapshot.change_kind import ChangeKind

    old_required = len(old.parameters) - old.defaults_count
    new_required = len(new.parameters) - new.defaults_count

    # If new version requires more parameters, it's a breaking change
    if new_required > old_required:
        return ChangeKind.BREAKING

    # If parameters were removed entirely, it's breaking
    if len(new.parameters) < len(old.parameters):
        return ChangeKind.BREAKING

    # If new optional parameters were added, it's a minor change
    if len(new.parameters) > len(old.parameters):
        return ChangeKind.MINOR

    # If required count decreased (more defaults), it's minor
    if new_required < old_required:
        return ChangeKind.MINOR

    return ChangeKind.NONE


def compare_classes(old: ClassAPI, new: ClassAPI) -> "ChangeKind":
    """Compare two class APIs for compatibility."""
    from snapshot.change_kind import ChangeKind

    change_rank = {
        ChangeKind.NONE: 0,
        ChangeKind.PATCH: 1,
        ChangeKind.MINOR: 2,
        ChangeKind.BREAKING: 3,
    }

    max_change = ChangeKind.NONE

    # Check for removed methods (breaking)
    for method_name in old.methods:
        if method_name not in new.methods:
            return ChangeKind.BREAKING

    # Check for changed methods
    for method_name, old_method in old.methods.items():
        if method_name in new.methods:
            change = compare_signatures(old_method, new.methods[method_name])
            if change_rank[change] > change_rank[max_change]:
                max_change = change

    # Check for added methods (minor)
    for method_name in new.methods:
        if method_name not in old.methods:
            if change_rank[max_change] < change_rank[ChangeKind.MINOR]:
                max_change = ChangeKind.MINOR

    # Check for removed fields (breaking - for structured types)
    for field_name in old.fields:
        if field_name not in new.fields:
            return ChangeKind.BREAKING

    # Check for added fields (minor - for structured types)
    for field_name in new.fields:
        if field_name not in old.fields:
            if change_rank[max_change] < change_rank[ChangeKind.MINOR]:
                max_change = ChangeKind.MINOR

    return max_change


def compare_modules(old: ModuleAPI, new: ModuleAPI) -> "ChangeKind":
    """Compare two module APIs and return the type of change."""
    from snapshot.change_kind import ChangeKind

    change_rank = {
        ChangeKind.NONE: 0,
        ChangeKind.PATCH: 1,
        ChangeKind.MINOR: 2,
        ChangeKind.BREAKING: 3,
    }

    max_change = ChangeKind.NONE

    # Check for removed functions (breaking)
    for func_name in old.functions:
        if func_name not in new.functions:
            return ChangeKind.BREAKING

    # Check for removed classes (breaking)
    for class_name in old.classes:
        if class_name not in new.classes:
            return ChangeKind.BREAKING

    # Check for changed functions
    for func_name, old_func in old.functions.items():
        if func_name in new.functions:
            change = compare_signatures(old_func, new.functions[func_name])
            if change_rank[change] > change_rank[max_change]:
                max_change = change

    # Check for changed classes
    for class_name, old_class in old.classes.items():
        if class_name in new.classes:
            change = compare_classes(old_class, new.classes[class_name])
            if change_rank[change] > change_rank[max_change]:
                max_change = change

    # Check for added functions (minor)
    for func_name in new.functions:
        if func_name not in old.functions:
            if change_rank[max_change] < change_rank[ChangeKind.MINOR]:
                max_change = ChangeKind.MINOR

    # Check for added classes (minor)
    for class_name in new.classes:
        if class_name not in old.classes:
            if change_rank[max_change] < change_rank[ChangeKind.MINOR]:
                max_change = ChangeKind.MINOR

    return max_change


def detect_change(old_module: ModuleType, new_module: ModuleType) -> "ChangeKind":
    """Detect the type of API change between two module versions."""
    old_api = ModuleAPI.from_module(old_module)
    new_api = ModuleAPI.from_module(new_module)
    return compare_modules(old_api, new_api)

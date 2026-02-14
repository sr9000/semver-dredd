"""
Automatically increments semver number based on interface changes.

semver consists of three numbers: major, minor, and patch.

Major version is incremented when there are breaking changes to the public API.
Minor version is incremented when there are new features added to the public API, but no breaking changes.
Patch version is equal YYYYMMDDZZZ.
- YYYY is the current year.
- MM is the current month.
- DD is the current day.
- ZZZ is a zero-padded incremental number that starts at 001 for each day and increments with each patch release on the same day.
"""

import inspect
from dataclasses import dataclass
from enum import Enum
from types import ModuleType
from typing import Any


class ChangeType(Enum):
    """Type of API change detected."""
    NONE = "none"
    PATCH = "patch"
    MINOR = "minor"
    MAJOR = "major"


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
            1 for p in sig.parameters.values()
            if p.default is not inspect.Parameter.empty
        )
        return cls(name=name, parameters=params, defaults_count=defaults_count)


@dataclass
class ClassAPI:
    """Represents the public API of a class."""
    name: str
    methods: dict[str, APISignature]

    @classmethod
    def from_class(cls, name: str, klass: type) -> "ClassAPI":
        """Extract public API from a class."""
        methods = {}
        for attr_name in dir(klass):
            if attr_name.startswith("_") and not attr_name == "__init__":
                continue
            attr = getattr(klass, attr_name)
            if callable(attr):
                try:
                    methods[attr_name] = APISignature.from_callable(attr_name, attr)
                except (ValueError, TypeError):
                    pass
        return cls(name=name, methods=methods)


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


def compare_signatures(old: APISignature, new: APISignature) -> ChangeType:
    """Compare two function/method signatures for compatibility."""
    old_required = len(old.parameters) - old.defaults_count
    new_required = len(new.parameters) - new.defaults_count

    # If new version requires more parameters, it's a breaking change
    if new_required > old_required:
        return ChangeType.MAJOR

    # If parameters were removed entirely, it's breaking
    if len(new.parameters) < len(old.parameters):
        return ChangeType.MAJOR

    # If new optional parameters were added, it's a minor change
    if len(new.parameters) > len(old.parameters):
        return ChangeType.MINOR

    # If required count decreased (more defaults), it's minor
    if new_required < old_required:
        return ChangeType.MINOR

    return ChangeType.NONE


def compare_classes(old: ClassAPI, new: ClassAPI) -> ChangeType:
    """Compare two class APIs for compatibility."""
    max_change = ChangeType.NONE

    # Check for removed methods (breaking)
    for method_name in old.methods:
        if method_name not in new.methods:
            return ChangeType.MAJOR

    # Check for changed methods
    for method_name, old_method in old.methods.items():
        if method_name in new.methods:
            change = compare_signatures(old_method, new.methods[method_name])
            if change.value > max_change.value:
                max_change = change

    # Check for added methods (minor)
    for method_name in new.methods:
        if method_name not in old.methods:
            if max_change.value < ChangeType.MINOR.value:
                max_change = ChangeType.MINOR

    return max_change


def compare_modules(old: ModuleAPI, new: ModuleAPI) -> ChangeType:
    """Compare two module APIs and return the type of change."""
    max_change = ChangeType.NONE

    # Check for removed functions (breaking)
    for func_name in old.functions:
        if func_name not in new.functions:
            return ChangeType.MAJOR

    # Check for removed classes (breaking)
    for class_name in old.classes:
        if class_name not in new.classes:
            return ChangeType.MAJOR

    # Check for changed functions
    for func_name, old_func in old.functions.items():
        if func_name in new.functions:
            change = compare_signatures(old_func, new.functions[func_name])
            if change.value > max_change.value:
                max_change = change

    # Check for changed classes
    for class_name, old_class in old.classes.items():
        if class_name in new.classes:
            change = compare_classes(old_class, new.classes[class_name])
            if change.value > max_change.value:
                max_change = change

    # Check for added functions (minor)
    for func_name in new.functions:
        if func_name not in old.functions:
            if max_change.value < ChangeType.MINOR.value:
                max_change = ChangeType.MINOR

    # Check for added classes (minor)
    for class_name in new.classes:
        if class_name not in old.classes:
            if max_change.value < ChangeType.MINOR.value:
                max_change = ChangeType.MINOR

    return max_change


def detect_change(old_module: ModuleType, new_module: ModuleType) -> ChangeType:
    """Detect the type of API change between two module versions."""
    old_api = ModuleAPI.from_module(old_module)
    new_api = ModuleAPI.from_module(new_module)
    return compare_modules(old_api, new_api)

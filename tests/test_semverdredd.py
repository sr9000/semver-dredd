"""
Tests for semver-dredd using pygeometry1 and pygeometry2 as test modules.
"""

import pytest

from semverdredd import (
    ChangeType,
    APISignature,
    ClassAPI,
    ModuleAPI,
    compare_signatures,
    compare_classes,
    compare_modules,
    detect_change,
)
from example import pygeometry1, pygeometry2


class TestAPISignature:
    """Tests for APISignature class."""

    def test_from_callable_simple_function(self):
        """Test extracting signature from a simple function."""
        sig = APISignature.from_callable("area", pygeometry1.area)
        assert sig.name == "area"
        assert sig.parameters == ["width", "height"]
        assert sig.defaults_count == 0

    def test_from_callable_with_defaults(self):
        """Test extracting signature from function with defaults."""
        sig = APISignature.from_callable("volume", pygeometry2.volume)
        assert sig.name == "volume"
        assert sig.parameters == ["width", "height", "depth"]
        assert sig.defaults_count == 0

    def test_from_callable_class_init(self):
        """Test extracting signature from class __init__."""
        sig = APISignature.from_callable("__init__", pygeometry1.Point.__init__)
        assert sig.name == "__init__"
        assert "self" in sig.parameters
        assert "x" in sig.parameters
        assert "y" in sig.parameters

    def test_from_callable_class_init_with_defaults(self):
        """Test extracting signature from class __init__ with defaults."""
        sig = APISignature.from_callable("__init__", pygeometry2.Point.__init__)
        assert sig.name == "__init__"
        assert "z" in sig.parameters
        assert sig.defaults_count == 1  # z has default


class TestClassAPI:
    """Tests for ClassAPI class."""

    def test_from_class_pygeometry1_point(self):
        """Test extracting class API from pygeometry1.Point."""
        api = ClassAPI.from_class("Point", pygeometry1.Point)
        assert api.name == "Point"
        assert "__init__" in api.methods
        assert "distance" in api.methods

    def test_from_class_pygeometry2_point(self):
        """Test extracting class API from pygeometry2.Point."""
        api = ClassAPI.from_class("Point", pygeometry2.Point)
        assert api.name == "Point"
        assert "__init__" in api.methods
        assert "distance" in api.methods
        assert "translate" in api.methods  # New method in pygeometry2


class TestModuleAPI:
    """Tests for ModuleAPI class."""

    def test_from_module_pygeometry1(self):
        """Test extracting module API from pygeometry1."""
        api = ModuleAPI.from_module(pygeometry1)
        assert "area" in api.functions
        assert "Point" in api.classes

    def test_from_module_pygeometry2(self):
        """Test extracting module API from pygeometry2."""
        api = ModuleAPI.from_module(pygeometry2)
        assert "area" in api.functions
        assert "volume" in api.functions  # New function
        assert "Point" in api.classes


class TestCompareSignatures:
    """Tests for compare_signatures function."""

    def test_identical_signatures(self):
        """Test comparing identical signatures."""
        sig1 = APISignature("func", ["a", "b"], 0)
        sig2 = APISignature("func", ["a", "b"], 0)
        assert compare_signatures(sig1, sig2) == ChangeType.NONE

    def test_added_optional_parameter(self):
        """Test adding optional parameter is minor change."""
        sig1 = APISignature("func", ["a", "b"], 0)
        sig2 = APISignature("func", ["a", "b", "c"], 1)
        assert compare_signatures(sig1, sig2) == ChangeType.MINOR

    def test_added_required_parameter(self):
        """Test adding required parameter is major change."""
        sig1 = APISignature("func", ["a", "b"], 0)
        sig2 = APISignature("func", ["a", "b", "c"], 0)
        assert compare_signatures(sig1, sig2) == ChangeType.MAJOR

    def test_removed_parameter(self):
        """Test removing parameter is major change."""
        sig1 = APISignature("func", ["a", "b", "c"], 0)
        sig2 = APISignature("func", ["a", "b"], 0)
        assert compare_signatures(sig1, sig2) == ChangeType.MAJOR

    def test_made_parameter_optional(self):
        """Test making parameter optional is minor change."""
        sig1 = APISignature("func", ["a", "b"], 0)
        sig2 = APISignature("func", ["a", "b"], 1)
        assert compare_signatures(sig1, sig2) == ChangeType.MINOR


class TestCompareClasses:
    """Tests for compare_classes function."""

    def test_pygeometry_point_classes(self):
        """Test comparing Point classes from pygeometry1 and pygeometry2."""
        old_api = ClassAPI.from_class("Point", pygeometry1.Point)
        new_api = ClassAPI.from_class("Point", pygeometry2.Point)
        change = compare_classes(old_api, new_api)
        # pygeometry2.Point adds translate method and z parameter (optional)
        # Adding method -> MINOR, adding optional param -> MINOR
        assert change == ChangeType.MINOR

    def test_removed_method_is_major(self):
        """Test that removing a method is a major change."""
        old_api = ClassAPI("Test", {"method1": APISignature("method1", ["self"], 0)})
        new_api = ClassAPI("Test", {})
        assert compare_classes(old_api, new_api) == ChangeType.MAJOR


class TestCompareModules:
    """Tests for compare_modules function."""

    def test_pygeometry1_vs_pygeometry2(self):
        """Test comparing pygeometry1 and pygeometry2 modules."""
        old_api = ModuleAPI.from_module(pygeometry1)
        new_api = ModuleAPI.from_module(pygeometry2)
        change = compare_modules(old_api, new_api)
        # pygeometry2 adds volume function and Point.translate method
        # Both are additions -> MINOR
        assert change == ChangeType.MINOR

    def test_removed_function_is_major(self):
        """Test that removing a function is a major change."""
        old_api = ModuleAPI(
            functions={"func1": APISignature("func1", [], 0)},
            classes={}
        )
        new_api = ModuleAPI(functions={}, classes={})
        assert compare_modules(old_api, new_api) == ChangeType.MAJOR

    def test_removed_class_is_major(self):
        """Test that removing a class is a major change."""
        old_api = ModuleAPI(
            functions={},
            classes={"MyClass": ClassAPI("MyClass", {})}
        )
        new_api = ModuleAPI(functions={}, classes={})
        assert compare_modules(old_api, new_api) == ChangeType.MAJOR


class TestDetectChange:
    """Tests for detect_change function."""

    def test_detect_change_pygeometry1_to_pygeometry2(self):
        """Test detecting change between pygeometry1 and pygeometry2."""
        change = detect_change(pygeometry1, pygeometry2)
        # pygeometry2 adds new function and method -> MINOR
        assert change == ChangeType.MINOR

    def test_detect_change_same_module(self):
        """Test detecting change for same module returns NONE."""
        change = detect_change(pygeometry1, pygeometry1)
        assert change == ChangeType.NONE

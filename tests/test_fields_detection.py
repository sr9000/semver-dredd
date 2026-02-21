"""Tests specifically for fields detection implementation."""

import pytest
from dataclasses import dataclass
from collections import namedtuple
from semverdredd.python_api import ClassAPI, compare_classes, APISignature
from semverdredd import ChangeKind

try:
    from pydantic import BaseModel
    HAS_PYDANTIC = True
except ImportError:
    HAS_PYDANTIC = False

# Helper to create ClassAPI without having to import all dependencies
def create_class_api(name, methods=None, fields=None):
    return ClassAPI(name, methods or {}, fields or set())

class TestFieldsDetection:
    """Tests for field extraction mechanisms."""

    def test_dataclass_fields(self):
        @dataclass
        class MyData:
            x: int
            y: str = "default"

        api = ClassAPI.from_class("MyData", MyData)
        assert "x" in api.fields
        assert "y" in api.fields
        assert len(api.fields) == 2

    def test_namedtuple_fields(self):
        Point = namedtuple("Point", ["x", "y", "z"])
        api = ClassAPI.from_class("Point", Point)
        assert api.fields == {"x", "y", "z"}

    def test_slots_fields(self):
        class Slotted:
            __slots__ = ["a", "b"]
            def __init__(self):
                pass

        api = ClassAPI.from_class("Slotted", Slotted)
        assert api.fields == {"a", "b"}

    def test_single_slot_string(self):
        class SingleSlot:
            __slots__ = "value"

        api = ClassAPI.from_class("SingleSlot", SingleSlot)
        assert api.fields == {"value"}

    def test_normal_class_no_fields(self):
        class Normal:
            def __init__(self):
                self.x = 1  # Should NOT be detected

        api = ClassAPI.from_class("Normal", Normal)
        assert api.fields == set()

    @pytest.mark.skipif(not HAS_PYDANTIC, reason="pydantic not installed")
    def test_pydantic_real_model(self):
        class User(BaseModel):
            id: int
            name: str
            email: str = "example@test.com"

        api = ClassAPI.from_class("User", User)
        assert "id" in api.fields
        assert "name" in api.fields
        assert "email" in api.fields
        assert len(api.fields) == 3

    # Keeping mocks to ensure logic works even if import fails or structure mimics pydantic
    def test_pydantic_v1_mock(self):
        class MockPydanticV1:
            __fields__ = {"f1": None, "f2": None}

        api = ClassAPI.from_class("MockPv1", MockPydanticV1)
        assert api.fields == {"f1", "f2"}

    def test_pydantic_v2_mock(self):
        class MockPydanticV2:
            model_fields = {"f3": None, "f4": None}

        api = ClassAPI.from_class("MockPv2", MockPydanticV2)
        assert api.fields == {"f3", "f4"}


class TestFieldComparison:
    """Tests for how field changes affect versioning."""

    def test_added_field_is_minor(self):
        old_api = create_class_api("Test", fields={"x"})
        new_api = create_class_api("Test", fields={"x", "y"})

        change = compare_classes(old_api, new_api)
        assert change == ChangeKind.MINOR

    def test_removed_field_is_major(self):
        old_api = create_class_api("Test", fields={"x", "y"})
        new_api = create_class_api("Test", fields={"x"})

        change = compare_classes(old_api, new_api)
        assert change == ChangeKind.BREAKING

    def test_renamed_field_is_major(self):
        # Effectively remove 'x' and add 'z' -> MAJOR
        old_api = create_class_api("Test", fields={"x"})
        new_api = create_class_api("Test", fields={"z"})

        change = compare_classes(old_api, new_api)
        assert change == ChangeKind.BREAKING

    def test_no_field_changes(self):
        old_api = create_class_api("Test", fields={"x", "y"})
        new_api = create_class_api("Test", fields={"y", "x"})

        change = compare_classes(old_api, new_api)
        assert change == ChangeKind.NONE

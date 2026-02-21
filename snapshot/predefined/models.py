"""Predefined snapshot component models for semver-dredd.

These dataclasses represent the building blocks of a public API snapshot.
Each leaf type carries a ``SNAPSHOT_TYPE_ID`` UUID so it can be stored and
retrieved via the :class:`~semverdredd.registry.SnapshotRegistry`.

UUIDs were generated via::

    uuid.uuid5(uuid.NAMESPACE_URL, "semver-dredd:predefined:<ClassName>")

Hierarchy
---------
* :class:`Variable`       — a named value (field, constant, parameter with default)
* :class:`Argument`       — a function argument (same shape as Variable)
* :class:`PythonArgument` — Python-specific argument with calling-convention flags
* :class:`Function`       — a callable: name + return type + args
* :class:`ClassField`     — a class/struct field (same shape as Variable)
* :class:`ClassMethod`    — a class method (same shape as Function)
"""

from __future__ import annotations

import uuid
from dataclasses import dataclass
from pathlib import Path
from typing import Any

import yaml

# ---------------------------------------------------------------------------
# UUID helpers
# ---------------------------------------------------------------------------
_NS = uuid.NAMESPACE_URL


def _uid(name: str) -> str:
    return str(uuid.uuid5(_NS, f"semver-dredd:predefined:{name}"))


# ---------------------------------------------------------------------------
# Variable
# ---------------------------------------------------------------------------
VARIABLE_TYPE_ID = _uid("Variable")


@dataclass(frozen=True)
class Variable:
    """A named variable / constant with an optional default value.

    YAML example::

        snapshot_type_id: <VARIABLE_TYPE_ID>
        name: max_retries
        type: int
        default: "3"
    """

    SNAPSHOT_TYPE_ID: str = VARIABLE_TYPE_ID

    name: str = ""
    type: str = "unknown"
    default: str | None = None

    # --- SnapshotFormat protocol ----------------------------------------

    @property
    def version(self) -> str:  # noqa: D102
        return "0"

    def to_dict(self) -> dict[str, Any]:
        return {
            "snapshot_type_id": self.SNAPSHOT_TYPE_ID,
            "name": self.name,
            "type": self.type,
            "default": self.default,
        }

    def to_yaml(self) -> str:
        return yaml.dump(self.to_dict(), default_flow_style=False, sort_keys=False)

    @classmethod
    def from_yaml_str(cls, yaml_str: str) -> "Variable":
        data = yaml.safe_load(yaml_str)
        return cls(
            name=data.get("name", ""),
            type=data.get("type", "unknown"),
            default=data.get("default"),
        )

    @classmethod
    def from_file(cls, path: Path | str) -> "Variable":
        return cls.from_yaml_str(Path(path).read_text())

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "Variable":
        return cls(
            name=data.get("name", ""),
            type=data.get("type", "unknown"),
            default=data.get("default"),
        )


# ---------------------------------------------------------------------------
# Argument
# ---------------------------------------------------------------------------
ARGUMENT_TYPE_ID = _uid("Argument")


@dataclass(frozen=True)
class Argument:
    """A function argument — same attributes as :class:`Variable`.

    YAML example::

        snapshot_type_id: <ARGUMENT_TYPE_ID>
        name: timeout
        type: float
        default: "30.0"
    """

    SNAPSHOT_TYPE_ID: str = ARGUMENT_TYPE_ID

    name: str = ""
    type: str = "unknown"
    default: str | None = None

    # --- SnapshotFormat protocol ----------------------------------------

    @property
    def version(self) -> str:
        return "0"

    def to_dict(self) -> dict[str, Any]:
        return {
            "snapshot_type_id": self.SNAPSHOT_TYPE_ID,
            "name": self.name,
            "type": self.type,
            "default": self.default,
        }

    def to_yaml(self) -> str:
        return yaml.dump(self.to_dict(), default_flow_style=False, sort_keys=False)

    @classmethod
    def from_yaml_str(cls, yaml_str: str) -> "Argument":
        data = yaml.safe_load(yaml_str)
        return cls(
            name=data.get("name", ""),
            type=data.get("type", "unknown"),
            default=data.get("default"),
        )

    @classmethod
    def from_file(cls, path: Path | str) -> "Argument":
        return cls.from_yaml_str(Path(path).read_text())

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "Argument":
        return cls(
            name=data.get("name", ""),
            type=data.get("type", "unknown"),
            default=data.get("default"),
        )


# ---------------------------------------------------------------------------
# PythonArgument
# ---------------------------------------------------------------------------
PYTHON_ARGUMENT_TYPE_ID = _uid("PythonArgument")


@dataclass(frozen=True)
class PythonArgument:
    """Python-specific function argument with calling-convention metadata.

    Extends :class:`Argument` with three mutually-exclusive boolean flags:

    * ``position_only``   — declared before ``/``
    * ``pos_and_named``   — the default (neither ``/`` nor ``*``)
    * ``named_only``      — declared after ``*`` or ``*args``

    YAML example::

        snapshot_type_id: <PYTHON_ARGUMENT_TYPE_ID>
        name: self
        type: MyClass
        default: null
        position_only: false
        pos_and_named: false
        named_only: false
    """

    SNAPSHOT_TYPE_ID: str = PYTHON_ARGUMENT_TYPE_ID

    name: str = ""
    type: str = "unknown"
    default: str | None = None
    position_only: bool = False
    pos_and_named: bool = True
    named_only: bool = False

    # --- SnapshotFormat protocol ----------------------------------------

    @property
    def version(self) -> str:
        return "0"

    def to_dict(self) -> dict[str, Any]:
        return {
            "snapshot_type_id": self.SNAPSHOT_TYPE_ID,
            "name": self.name,
            "type": self.type,
            "default": self.default,
            "position_only": self.position_only,
            "pos_and_named": self.pos_and_named,
            "named_only": self.named_only,
        }

    def to_yaml(self) -> str:
        return yaml.dump(self.to_dict(), default_flow_style=False, sort_keys=False)

    @classmethod
    def from_yaml_str(cls, yaml_str: str) -> "PythonArgument":
        data = yaml.safe_load(yaml_str)
        return cls.from_dict(data)

    @classmethod
    def from_file(cls, path: Path | str) -> "PythonArgument":
        return cls.from_yaml_str(Path(path).read_text())

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "PythonArgument":
        return cls(
            name=data.get("name", ""),
            type=data.get("type", "unknown"),
            default=data.get("default"),
            position_only=data.get("position_only", False),
            pos_and_named=data.get("pos_and_named", True),
            named_only=data.get("named_only", False),
        )


# ---------------------------------------------------------------------------
# Function
# ---------------------------------------------------------------------------
FUNCTION_TYPE_ID = _uid("Function")


@dataclass(frozen=True)
class Function:
    """A standalone function (or static method when stored inside a class snapshot).

    ``args`` may contain :class:`Argument` *or* :class:`PythonArgument`
    instances — the serialisation stores them as plain dicts inside the YAML.

    YAML example::

        snapshot_type_id: <FUNCTION_TYPE_ID>
        name: compute_area
        result_type: float
        args:
          - name: width
            type: float
            default: null
          - name: height
            type: float
            default: null
    """

    SNAPSHOT_TYPE_ID: str = FUNCTION_TYPE_ID

    name: str = ""
    result_type: str = "void"
    args: tuple[Argument | PythonArgument, ...] = ()

    # --- SnapshotFormat protocol ----------------------------------------

    @property
    def version(self) -> str:
        return "0"

    def to_dict(self) -> dict[str, Any]:
        args_list = [_arg_to_dict(a) for a in self.args]
        return {
            "snapshot_type_id": self.SNAPSHOT_TYPE_ID,
            "name": self.name,
            "result_type": self.result_type,
            "args": args_list,
        }

    def to_yaml(self) -> str:
        return yaml.dump(self.to_dict(), default_flow_style=False, sort_keys=False)

    @classmethod
    def from_yaml_str(cls, yaml_str: str) -> "Function":
        data = yaml.safe_load(yaml_str)
        return cls.from_dict(data)

    @classmethod
    def from_file(cls, path: Path | str) -> "Function":
        return cls.from_yaml_str(Path(path).read_text())

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "Function":
        args = tuple(_arg_from_dict(a) for a in data.get("args", []))
        return cls(
            name=data.get("name", ""),
            result_type=data.get("result_type", "void"),
            args=args,
        )


# ---------------------------------------------------------------------------
# ClassField
# ---------------------------------------------------------------------------
CLASS_FIELD_TYPE_ID = _uid("ClassField")


@dataclass(frozen=True)
class ClassField:
    """A public field of a class or struct — same shape as :class:`Variable`.

    YAML example::

        snapshot_type_id: <CLASS_FIELD_TYPE_ID>
        name: radius
        type: float
        default: null
    """

    SNAPSHOT_TYPE_ID: str = CLASS_FIELD_TYPE_ID

    name: str = ""
    type: str = "unknown"
    default: str | None = None

    # --- SnapshotFormat protocol ----------------------------------------

    @property
    def version(self) -> str:
        return "0"

    def to_dict(self) -> dict[str, Any]:
        return {
            "snapshot_type_id": self.SNAPSHOT_TYPE_ID,
            "name": self.name,
            "type": self.type,
            "default": self.default,
        }

    def to_yaml(self) -> str:
        return yaml.dump(self.to_dict(), default_flow_style=False, sort_keys=False)

    @classmethod
    def from_yaml_str(cls, yaml_str: str) -> "ClassField":
        data = yaml.safe_load(yaml_str)
        return cls.from_dict(data)

    @classmethod
    def from_file(cls, path: Path | str) -> "ClassField":
        return cls.from_yaml_str(Path(path).read_text())

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "ClassField":
        return cls(
            name=data.get("name", ""),
            type=data.get("type", "unknown"),
            default=data.get("default"),
        )


# ---------------------------------------------------------------------------
# ClassMethod
# ---------------------------------------------------------------------------
CLASS_METHOD_TYPE_ID = _uid("ClassMethod")


@dataclass(frozen=True)
class ClassMethod:
    """A public method of a class — same shape as :class:`Function`.

    YAML example::

        snapshot_type_id: <CLASS_METHOD_TYPE_ID>
        name: distance
        result_type: float
        args:
          - name: other
            type: Point
            default: null
    """

    SNAPSHOT_TYPE_ID: str = CLASS_METHOD_TYPE_ID

    name: str = ""
    result_type: str = "void"
    args: tuple[Argument | PythonArgument, ...] = ()

    # --- SnapshotFormat protocol ----------------------------------------

    @property
    def version(self) -> str:
        return "0"

    def to_dict(self) -> dict[str, Any]:
        args_list = [_arg_to_dict(a) for a in self.args]
        return {
            "snapshot_type_id": self.SNAPSHOT_TYPE_ID,
            "name": self.name,
            "result_type": self.result_type,
            "args": args_list,
        }

    def to_yaml(self) -> str:
        return yaml.dump(self.to_dict(), default_flow_style=False, sort_keys=False)

    @classmethod
    def from_yaml_str(cls, yaml_str: str) -> "ClassMethod":
        data = yaml.safe_load(yaml_str)
        return cls.from_dict(data)

    @classmethod
    def from_file(cls, path: Path | str) -> "ClassMethod":
        return cls.from_yaml_str(Path(path).read_text())

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "ClassMethod":
        args = tuple(_arg_from_dict(a) for a in data.get("args", []))
        return cls(
            name=data.get("name", ""),
            result_type=data.get("result_type", "void"),
            args=args,
        )


# ---------------------------------------------------------------------------
# Internal helpers
# ---------------------------------------------------------------------------

def _arg_to_dict(arg: Argument | PythonArgument) -> dict[str, Any]:
    """Serialize an argument to a plain dict (strips SNAPSHOT_TYPE_ID)."""
    d = arg.to_dict()
    d.pop("snapshot_type_id", None)
    if isinstance(arg, PythonArgument):
        d["_arg_kind"] = "python"
    return d


def _arg_from_dict(data: dict[str, Any]) -> Argument | PythonArgument:
    """Deserialize an argument dict into the appropriate type."""
    if data.get("_arg_kind") == "python" or any(
        k in data for k in ("position_only", "pos_and_named", "named_only")
    ):
        return PythonArgument.from_dict(data)
    return Argument.from_dict(data)


# ---------------------------------------------------------------------------
# Registry of all predefined type IDs
# ---------------------------------------------------------------------------

ALL_TYPE_IDS: dict[str, str] = {
    "Variable": VARIABLE_TYPE_ID,
    "Argument": ARGUMENT_TYPE_ID,
    "PythonArgument": PYTHON_ARGUMENT_TYPE_ID,
    "Function": FUNCTION_TYPE_ID,
    "ClassField": CLASS_FIELD_TYPE_ID,
    "ClassMethod": CLASS_METHOD_TYPE_ID,
}

ALL_CLASSES: list[type] = [
    Variable,
    Argument,
    PythonArgument,
    Function,
    ClassField,
    ClassMethod,
]

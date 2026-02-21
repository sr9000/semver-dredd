"""Python plugin implementation for semver-dredd."""

from __future__ import annotations

import importlib
import inspect
import sys
import uuid as _uuid
from pathlib import Path
from typing import Any, Optional

import yaml

from semverdredd.plugin_base import LanguagePlugin, SnapshotResult
from snapshot.predefined import (
    Argument,
    ClassField,
    ClassMethod,
    Function,
    PythonArgument,
    Variable,
)

# ---------------------------------------------------------------------------
# SNAPSHOT_TYPE_ID for the Python plugin's snapshot format
# ---------------------------------------------------------------------------

PYTHON_SNAPSHOT_TYPE_ID = str(
    _uuid.uuid5(_uuid.NAMESPACE_URL, "semver-dredd:plugin:python:PythonSnapshot")
)


class PythonSnapshot:
    """Python-specific API snapshot produced by the Python plugin.

    Stored as a YAML document with the following top-level fields::

        snapshot_type_id: <PYTHON_SNAPSHOT_TYPE_ID>
        schema_version: 3
        version: "1.0.0"
        language: python
        source:
          kind: module
          path: mylib
        api:
          variables:
            MAX_SIZE:
              type: int
              default: "100"
          functions:
            compute:
              result_type: float
              args:
                - name: x
                  type: float
                  position_only: false
                  pos_and_named: true
                  named_only: false
                  default: null
          types:
            MyClass:
              fields:
                - name: value
                  type: str
                  default: null
              methods:
                do_thing:
                  result_type: void
                  args: []
    """

    SNAPSHOT_TYPE_ID: str = PYTHON_SNAPSHOT_TYPE_ID

    def __init__(
        self,
        version: str = "",
        source_kind: str = "module",
        source_path: str = "",
        variables: dict[str, Variable] | None = None,
        functions: dict[str, Function] | None = None,
        types: dict[str, tuple[list[ClassField], dict[str, ClassMethod]]] | None = None,
    ) -> None:
        self._version = version
        self.source_kind = source_kind
        self.source_path = source_path
        self.variables: dict[str, Variable] = variables or {}
        self.functions: dict[str, Function] = functions or {}
        self.types: dict[str, tuple[list[ClassField], dict[str, ClassMethod]]] = types or {}

    @property
    def version(self) -> str:
        return self._version

    # ------------------------------------------------------------------
    # Serialization
    # ------------------------------------------------------------------

    def to_dict(self) -> dict[str, Any]:
        variables: dict[str, Any] = {
            name: {"type": v.type, "default": v.default}
            for name, v in self.variables.items()
        }
        functions: dict[str, Any] = {
            name: {
                "result_type": f.result_type,
                "args": [self._arg_to_dict(a) for a in f.args],
            }
            for name, f in self.functions.items()
        }
        types: dict[str, Any] = {}
        for type_name, (fields, methods) in self.types.items():
            types[type_name] = {
                "fields": [
                    {"name": cf.name, "type": cf.type, "default": cf.default}
                    for cf in fields
                ],
                "methods": {
                    mname: {
                        "result_type": m.result_type,
                        "args": [self._arg_to_dict(a) for a in m.args],
                    }
                    for mname, m in methods.items()
                },
            }
        return {
            "snapshot_type_id": self.SNAPSHOT_TYPE_ID,
            "schema_version": 3,
            "version": self._version,
            "language": "python",
            "source": {"kind": self.source_kind, "path": self.source_path},
            "api": {"variables": variables, "functions": functions, "types": types},
        }

    @staticmethod
    def _arg_to_dict(arg: Argument | PythonArgument) -> dict[str, Any]:
        if isinstance(arg, PythonArgument):
            return {
                "name": arg.name,
                "type": arg.type,
                "default": arg.default,
                "position_only": arg.position_only,
                "pos_and_named": arg.pos_and_named,
                "named_only": arg.named_only,
            }
        return {"name": arg.name, "type": arg.type, "default": arg.default}

    def to_yaml(self) -> str:
        return yaml.dump(self.to_dict(), default_flow_style=False, sort_keys=False)

    # ------------------------------------------------------------------
    # Deserialization
    # ------------------------------------------------------------------

    @classmethod
    def from_yaml_str(cls, yaml_str: str) -> "PythonSnapshot":
        data = yaml.safe_load(yaml_str)
        return cls._from_dict(data)

    @classmethod
    def from_file(cls, path: Path | str) -> "PythonSnapshot":
        return cls.from_yaml_str(Path(path).read_text())

    @classmethod
    def _from_dict(cls, data: dict[str, Any]) -> "PythonSnapshot":
        source = data.get("source", {})
        api = data.get("api", {})
        variables = {
            name: Variable(name=name, type=v.get("type", "unknown"), default=v.get("default"))
            for name, v in api.get("variables", {}).items()
        }
        functions = {
            name: Function(
                name=name,
                result_type=f.get("result_type", "void"),
                args=tuple(cls._arg_from_dict(a) for a in f.get("args", [])),
            )
            for name, f in api.get("functions", {}).items()
        }
        types: dict[str, tuple[list[ClassField], dict[str, ClassMethod]]] = {}
        for type_name, td in api.get("types", {}).items():
            fields = [
                ClassField(name=fd["name"], type=fd.get("type", "unknown"), default=fd.get("default"))
                for fd in td.get("fields", [])
            ]
            methods = {
                mname: ClassMethod(
                    name=mname,
                    result_type=m.get("result_type", "void"),
                    args=tuple(cls._arg_from_dict(a) for a in m.get("args", [])),
                )
                for mname, m in td.get("methods", {}).items()
            }
            types[type_name] = (fields, methods)
        return cls(
            version=data.get("version", ""),
            source_kind=source.get("kind", "module"),
            source_path=source.get("path", ""),
            variables=variables,
            functions=functions,
            types=types,
        )

    @staticmethod
    def _arg_from_dict(data: dict[str, Any]) -> Argument | PythonArgument:
        if any(k in data for k in ("position_only", "pos_and_named", "named_only")):
            return PythonArgument(
                name=data.get("name", ""),
                type=data.get("type", "unknown"),
                default=data.get("default"),
                position_only=data.get("position_only", False),
                pos_and_named=data.get("pos_and_named", True),
                named_only=data.get("named_only", False),
            )
        return Argument(
            name=data.get("name", ""),
            type=data.get("type", "unknown"),
            default=data.get("default"),
        )


# ---------------------------------------------------------------------------
# Introspection helpers
# ---------------------------------------------------------------------------

def _get_type_hint(annotation: Any) -> str:
    if annotation is inspect.Parameter.empty:
        return "unknown"
    try:
        if hasattr(annotation, "__name__"):
            return annotation.__name__
        return str(annotation).replace("typing.", "")
    except Exception:
        return "unknown"


def _inspect_function(name: str, func: Any) -> Function:
    try:
        sig = inspect.signature(func)
    except (ValueError, TypeError):
        return Function(name=name)
    try:
        hints = inspect.get_annotations(func)
    except Exception:
        hints = {}
    result_type = _get_type_hint(hints.get("return", inspect.Parameter.empty))
    args: list[PythonArgument] = []
    for param_name, param in sig.parameters.items():
        kind = param.kind
        position_only = kind == inspect.Parameter.POSITIONAL_ONLY
        named_only = kind == inspect.Parameter.KEYWORD_ONLY
        pos_and_named = not position_only and not named_only and kind not in (
            inspect.Parameter.VAR_POSITIONAL,
            inspect.Parameter.VAR_KEYWORD,
        )
        default: str | None = None
        if param.default is not inspect.Parameter.empty:
            try:
                default = repr(param.default)
            except Exception:
                default = "..."
        type_hint = _get_type_hint(hints.get(param_name, param.annotation))
        args.append(
            PythonArgument(
                name=param_name,
                type=type_hint,
                default=default,
                position_only=position_only,
                pos_and_named=pos_and_named,
                named_only=named_only,
            )
        )
    return Function(name=name, result_type=result_type, args=tuple(args))


def _inspect_class(cls_obj: Any) -> tuple[list[ClassField], dict[str, ClassMethod]]:
    fields: list[ClassField] = []
    methods: dict[str, ClassMethod] = {}

    annotations: dict[str, Any] = {}
    for klass in reversed(cls_obj.__mro__):
        annotations.update(getattr(klass, "__annotations__", {}))

    seen_fields: set[str] = set()
    for attr_name, annotation in annotations.items():
        if attr_name.startswith("_"):
            continue
        type_str = _get_type_hint(annotation)
        default: str | None = None
        if hasattr(cls_obj, attr_name):
            val = getattr(cls_obj, attr_name)
            if not callable(val):
                try:
                    default = repr(val)
                except Exception:
                    default = "..."
        fields.append(ClassField(name=attr_name, type=type_str, default=default))
        seen_fields.add(attr_name)

    for slot in getattr(cls_obj, "__slots__", []):
        if not slot.startswith("_") and slot not in seen_fields:
            fields.append(ClassField(name=slot, type="unknown"))
            seen_fields.add(slot)

    for method_name, member in inspect.getmembers(cls_obj, predicate=inspect.isfunction):
        if method_name.startswith("_") and method_name != "__init__":
            continue
        try:
            hints = inspect.get_annotations(member)
        except Exception:
            hints = {}
        result_type = _get_type_hint(hints.get("return", inspect.Parameter.empty))
        try:
            sig = inspect.signature(member)
        except (ValueError, TypeError):
            methods[method_name] = ClassMethod(name=method_name)
            continue
        args: list[PythonArgument] = []
        for param_name, param in sig.parameters.items():
            kind = param.kind
            position_only = kind == inspect.Parameter.POSITIONAL_ONLY
            named_only = kind == inspect.Parameter.KEYWORD_ONLY
            pos_and_named = not position_only and not named_only and kind not in (
                inspect.Parameter.VAR_POSITIONAL,
                inspect.Parameter.VAR_KEYWORD,
            )
            default = None
            if param.default is not inspect.Parameter.empty:
                try:
                    default = repr(param.default)
                except Exception:
                    default = "..."
            type_hint = _get_type_hint(hints.get(param_name, param.annotation))
            args.append(
                PythonArgument(
                    name=param_name,
                    type=type_hint,
                    default=default,
                    position_only=position_only,
                    pos_and_named=pos_and_named,
                    named_only=named_only,
                )
            )
        methods[method_name] = ClassMethod(
            name=method_name, result_type=result_type, args=tuple(args)
        )
    return fields, methods


# ---------------------------------------------------------------------------
# Plugin
# ---------------------------------------------------------------------------


class PythonPlugin(LanguagePlugin):
    """Python language support plugin for semver-dredd.

    Analyzes Python modules using introspection (inspect module).
    Produces :class:`PythonSnapshot` YAML using the predefined component models.
    """

    @property
    def name(self) -> str:
        return "python"

    @property
    def version(self) -> str:
        return "1.1.0"

    @property
    def description(self) -> str:
        return "Analyzes Python modules using introspection (predefined component models)"

    @property
    def snapshot_format_class(self) -> type:
        return PythonSnapshot

    def validate_path(self, path: str) -> tuple[bool, str]:
        p = Path(path)
        if p.exists():
            if p.is_dir():
                if not (p / "__init__.py").exists():
                    return False, f"Directory '{path}' is not a Python package (no __init__.py)"
                return True, ""
            if p.is_file() and p.suffix == ".py":
                return True, ""
        if path and ("." in path or path.isidentifier()):
            return True, ""
        return False, f"'{path}' is not a valid Python module path or name"

    def generate_snapshot(
        self, path: str, version: str, options: Optional[dict[str, Any]] = None
    ) -> SnapshotResult:
        try:
            module = self._import_module(path)
        except Exception as e:
            return SnapshotResult(False, "", f"Failed to import module: {e}")
        try:
            snap = self._build_snapshot(module, version, path)
            return SnapshotResult(True, snap.to_yaml())
        except Exception as e:
            return SnapshotResult(False, "", f"Failed to generate snapshot: {e}")

    def _import_module(self, module_path: str) -> Any:
        module_fs_path = Path(module_path)
        if module_fs_path.exists():
            if module_fs_path.is_dir():
                module_name = module_fs_path.name
                parent = str(module_fs_path.parent)
            else:
                module_name = module_fs_path.stem
                parent = str(module_fs_path.parent)
            sys.path.insert(0, parent)
            try:
                return importlib.import_module(module_name)
            finally:
                if sys.path and sys.path[0] == parent:
                    sys.path.pop(0)
        return importlib.import_module(module_path)

    def _build_snapshot(self, module: Any, version: str, path: str) -> PythonSnapshot:
        variables: dict[str, Variable] = {}
        functions: dict[str, Function] = {}
        types: dict[str, tuple[list[ClassField], dict[str, ClassMethod]]] = {}
        source_path = str(Path(path).resolve()) if Path(path).exists() else path

        for attr_name in dir(module):
            if attr_name.startswith("_"):
                continue
            try:
                obj = getattr(module, attr_name)
            except Exception:
                continue
            obj_module = getattr(obj, "__module__", None)
            if obj_module and obj_module != module.__name__:
                continue
            if inspect.isclass(obj):
                fields, meths = _inspect_class(obj)
                types[attr_name] = (fields, meths)
            elif callable(obj):
                functions[attr_name] = _inspect_function(attr_name, obj)
            else:
                type_str = type(obj).__name__
                try:
                    default = repr(obj)
                except Exception:
                    default = "..."
                variables[attr_name] = Variable(name=attr_name, type=type_str, default=default)

        return PythonSnapshot(
            version=version,
            source_kind="module",
            source_path=source_path,
            variables=variables,
            functions=functions,
            types=types,
        )

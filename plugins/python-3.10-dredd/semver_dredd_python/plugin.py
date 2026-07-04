"""Python plugin implementation for semver-dredd."""

from __future__ import annotations

import importlib
import inspect
import logging
import pkgutil
import sys
import types
import uuid as _uuid
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Optional

import yaml

logger = logging.getLogger(__name__)


from semverdredd.plugin_base import LanguagePlugin, SnapshotResult
from snapshot.models import (
    Field,
    FunctionSignature,
    NormalizedSnapshot,
    Parameter,
    TypeDefinition,
)
from snapshot.predefined import (
    Argument,
    ClassField,
    ClassMethod,
    Function,
    Variable,
)
from snapshot.protocols import DiffResult

# ---------------------------------------------------------------------------
# PythonArgument -- Python-specific argument type (lives in this plugin)
# ---------------------------------------------------------------------------

PYTHON_ARGUMENT_TYPE_ID = str(
    _uuid.uuid5(_uuid.NAMESPACE_URL, "semver-dredd:predefined:PythonArgument")
)


@dataclass(frozen=True)
class PythonArgument(Argument):
    """Python-specific function argument with calling-convention metadata.

    Extends Argument with three mutually-exclusive boolean flags describing
    where in a Python function signature the parameter appears:

    * position_only -- before /
    * pos_and_named -- normal parameter (default)
    * named_only    -- after * or *args
    """

    SNAPSHOT_TYPE_ID: str = PYTHON_ARGUMENT_TYPE_ID

    # name, type, default inherited from Argument -> Variable
    position_only: bool = False
    pos_and_named: bool = True
    named_only: bool = False

    def to_dict(self) -> dict[str, Any]:
        d = super().to_dict()
        d["position_only"] = self.position_only
        d["pos_and_named"] = self.pos_and_named
        d["named_only"] = self.named_only
        return d

    # to_yaml, from_yaml_str, from_file inherited from Variable

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


def _register_python_argument() -> None:
    from semverdredd.registry import default_registry
    try:
        default_registry.register(PythonArgument)
    except ValueError:
        pass


_register_python_argument()


# ---------------------------------------------------------------------------
# SNAPSHOT_TYPE_ID for the Python plugin snapshot format
# ---------------------------------------------------------------------------

PYTHON_SNAPSHOT_TYPE_ID = str(
    _uuid.uuid5(_uuid.NAMESPACE_URL, "semver-dredd:plugin:python:PythonSnapshot")
)


class PythonSnapshot:
    """Python-specific API snapshot produced by the Python plugin."""

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
        variables_d: dict[str, Any] = {
            name: {"type": v.type, "default": v.default}
            for name, v in self.variables.items()
        }
        functions_d: dict[str, Any] = {
            name: {
                "result_type": f.result_type,
                "args": [self._arg_to_dict(a) for a in f.args],
            }
            for name, f in self.functions.items()
        }
        types_d: dict[str, Any] = {}
        for type_name, (fields, methods) in self.types.items():
            types_d[type_name] = {
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
            "api": {"variables": variables_d, "functions": functions_d, "types": types_d},
        }

    @staticmethod
    def _arg_to_dict(arg: Any) -> dict[str, Any]:
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
    def _arg_from_dict(data: dict[str, Any]) -> Any:
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

    # ------------------------------------------------------------------
    # Diff (Comparable protocol)
    # ------------------------------------------------------------------

    def diff_against(self, other: "PythonSnapshot"):
        """Compare this snapshot against *other*.

        Implements :class:`~snapshot.protocols.Comparable` by converting both
        sides to a :class:`~snapshot.models.NormalizedSnapshot` and delegating
        — all conversion knowledge stays inside the snapshot class.
        """
        return _to_normalized(self).diff_against(_to_normalized(other))


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


def _stable_default_repr(value: Any) -> str:
    """Return a deterministic representation suitable for API snapshots."""
    if isinstance(value, (types.MemberDescriptorType, types.GetSetDescriptorType)):
        return "<descriptor>"
    if value is None or isinstance(value, (bool, int, float, str, bytes)):
        return repr(value)
    if isinstance(value, (tuple, list, set, frozenset)):
        return type(value).__name__
    if isinstance(value, dict):
        return "dict"
    value_type = type(value)
    return f"<{value_type.__module__}.{value_type.__qualname__}>"


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
            default = _stable_default_repr(param.default)
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
    return Function(name=name, result_type=result_type, args=tuple(args))  # type: ignore[arg-type]


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
            if isinstance(val, (types.MemberDescriptorType, types.GetSetDescriptorType)):
                default = None
            elif not callable(val):
                default = _stable_default_repr(val)
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
        m_args: list[PythonArgument] = []
        for param_name, param in sig.parameters.items():
            kind = param.kind
            position_only = kind == inspect.Parameter.POSITIONAL_ONLY
            named_only = kind == inspect.Parameter.KEYWORD_ONLY
            pos_and_named = not position_only and not named_only and kind not in (
                inspect.Parameter.VAR_POSITIONAL,
                inspect.Parameter.VAR_KEYWORD,
            )
            p_default: str | None = None
            if param.default is not inspect.Parameter.empty:
                p_default = _stable_default_repr(param.default)
            type_hint = _get_type_hint(hints.get(param_name, param.annotation))
            m_args.append(
                PythonArgument(
                    name=param_name,
                    type=type_hint,
                    default=p_default,
                    position_only=position_only,
                    pos_and_named=pos_and_named,
                    named_only=named_only,
                )
            )
        methods[method_name] = ClassMethod(
            name=method_name, result_type=result_type, args=tuple(m_args)  # type: ignore[arg-type]
        )
    return fields, methods


# ---------------------------------------------------------------------------
# Diff scorer
# ---------------------------------------------------------------------------

def _to_normalized(snap: PythonSnapshot) -> NormalizedSnapshot:
    """Convert a PythonSnapshot to NormalizedSnapshot for diff_against."""
    functions: dict[str, FunctionSignature] = {}
    for name, variable in snap.variables.items():
        functions[f"variable:{name}"] = FunctionSignature(
            name=f"variable:{name}",
            parameters=(
                Parameter(name="type", type=variable.type, optional=False),
                Parameter(name="default", type=str(variable.default), optional=True),
            ),
        )

    for name, func in snap.functions.items():
        params = tuple(
            Parameter(name=a.name, type=a.type, optional=a.default is not None)
            for a in func.args
        )
        functions[name] = FunctionSignature(name=name, parameters=params)

    types: dict[str, TypeDefinition] = {}
    for type_name, (fields, methods) in snap.types.items():
        norm_fields = tuple(
            Field(name=f.name, type=f.type) for f in fields
        )
        norm_methods: dict[str, FunctionSignature] = {}
        for mname, method in methods.items():
            mparams = tuple(
                Parameter(name=a.name, type=a.type, optional=a.default is not None)
                for a in method.args
            )
            norm_methods[mname] = FunctionSignature(name=mname, parameters=mparams)
        types[type_name] = TypeDefinition(
            name=type_name, fields=norm_fields, methods=norm_methods
        )

    return NormalizedSnapshot(
        schema_version=3,
        version=snap.version,
        language="python",
        source_kind=snap.source_kind,
        source_path=snap.source_path,
        functions=functions,
        types=types,
    )


# ---------------------------------------------------------------------------
# Plugin
# ---------------------------------------------------------------------------


class PythonPlugin(LanguagePlugin):
    """Python language support plugin for semver-dredd."""

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

    @property
    def metadata(self) -> dict[str, Any]:
        return {
            "scope": {
                "syntax": "python dotted module/package names",
                "include_mode": "recursive allow-list",
                "exclude_mode": "recursive dotted-prefix exclusion after include",
                "empty_include": "analyze the whole configured package/module surface",
            },
            "plugin_options": [],
            "runtime_requirements": {
                "python": ">=3.10",
                "external_tools": [],
            },
            "features": ["metadata", "machine_readable_inventory"],
        }


    def validate_path(self, path: str) -> tuple[bool, str]:
        p = Path(path)
        if p.exists():
            if p.is_dir():
                return True, ""
            if p.is_file() and p.suffix == ".py":
                return True, ""
        if path and ("." in path or path.isidentifier()):
            return True, ""
        return False, f"'{path}' is not a valid Python module path or name"

    def generate_snapshot(
        self, path: str, version: str, options: Optional[dict[str, Any]] = None
    ) -> SnapshotResult:
        path_obj = Path(path)
        if path_obj.exists() and path_obj.is_dir() and not (path_obj / "__init__.py").exists():
            try:
                snap = self._build_directory_snapshot(path_obj, version, options)
                return SnapshotResult(True, snap.to_yaml())
            except Exception as e:
                return SnapshotResult(False, "", f"Failed to generate directory snapshot: {e}")

        try:
            module = self._import_module(path)
        except Exception as e:
            return SnapshotResult(False, "", f"Failed to import module: {e}")
        try:
            snap = self._build_snapshot(module, version, path, options)
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

    @staticmethod
    def _has_private_component(dotted_name: str) -> bool:
        """True if any dot-separated component of dotted_name starts with '_'."""
        return any(part.startswith("_") for part in dotted_name.split("."))

    @staticmethod
    def _matches_scope_item(module_name: str, item: Any) -> bool:
        """True if module_name equals item or is nested under it (dotted prefix)."""
        item_str = str(item)
        return module_name == item_str or module_name.startswith(item_str + ".")

    def _discover_submodule_names(self, module: Any) -> list[str]:
        """Recursively discover public submodule dotted names under *module*.

        Skips any submodule with a '_'-prefixed path component. Import
        failures are logged at debug level and the submodule is skipped --
        this keeps discovery best-effort rather than fatal.
        """
        module_path = getattr(module, "__path__", None)
        if module_path is None:
            return []
        names: list[str] = []
        for finder, name, _is_pkg in pkgutil.walk_packages(
            module_path, prefix=module.__name__ + "."
        ):
            if self._has_private_component(name):
                continue
            names.append(name)
        return names

    def _resolve_scan_targets(
        self, module: Any, options: Optional[dict[str, Any]]
    ) -> list[Any]:
        """Resolve which module objects contribute to the snapshot.

        Behavior:
        - If the root module defines ``__all__``, scope recursion is skipped
          entirely; only the root module's ``__all__``-listed names are used
          (include/exclude do not apply in this mode).
        - Otherwise, the root module plus all recursively discovered public
          submodules are candidates. ``include`` (allow-list, recursive
          dotted-name prefix match) and ``exclude`` (applied after include,
          same prefix-match semantics) from options narrow the candidate set.
        """
        if hasattr(module, "__all__"):
            return [module]

        candidate_names = [module.__name__] + self._discover_submodule_names(module)

        include = list((options or {}).get("include") or [])
        exclude = list((options or {}).get("exclude") or [])

        if include:
            candidate_names = [
                name
                for name in candidate_names
                if any(self._matches_scope_item(name, item) for item in include)
            ]
        if exclude:
            candidate_names = [
                name
                for name in candidate_names
                if not any(self._matches_scope_item(name, item) for item in exclude)
            ]

        targets: list[Any] = []
        for name in candidate_names:
            if name == module.__name__:
                targets.append(module)
                continue
            try:
                targets.append(importlib.import_module(name))
            except Exception as e:
                logger.debug("Skipping submodule %r: failed to import (%s)", name, e)

        if not candidate_names:
            logger.warning(
                "Python scope include/exclude matched no modules under %r",
                module.__name__,
            )

        return targets

    def _scan_module_members(
        self, mod: Any, *, respect_all: bool
    ) -> tuple[
        dict[str, Variable],
        dict[str, Function],
        dict[str, tuple[list[ClassField], dict[str, ClassMethod]]],
    ]:
        """Extract public variables/functions/types directly defined on *mod*."""
        variables: dict[str, Variable] = {}
        functions: dict[str, Function] = {}
        types: dict[str, tuple[list[ClassField], dict[str, ClassMethod]]] = {}

        allowed_names: set[str] | None = None
        if respect_all and hasattr(mod, "__all__"):
            allowed_names = set(mod.__all__)

        for attr_name in dir(mod):
            if attr_name.startswith("_"):
                continue
            if allowed_names is not None and attr_name not in allowed_names:
                continue
            try:
                obj = getattr(mod, attr_name)
            except Exception:
                continue
            obj_module = getattr(obj, "__module__", None)
            if allowed_names is None and obj_module and obj_module != mod.__name__:
                continue
            if inspect.isclass(obj):
                fields, meths = _inspect_class(obj)
                types[attr_name] = (fields, meths)
            elif callable(obj):
                functions[attr_name] = _inspect_function(attr_name, obj)
            else:
                type_str = type(obj).__name__
                default = _stable_default_repr(obj)
                variables[attr_name] = Variable(name=attr_name, type=type_str, default=default)

        return variables, functions, types

    def _build_snapshot(
        self,
        module: Any,
        version: str,
        path: str,
        options: Optional[dict[str, Any]] = None,
    ) -> PythonSnapshot:
        source_path = str(Path(path).resolve()) if Path(path).exists() else path
        respect_all = hasattr(module, "__all__")

        variables: dict[str, Variable] = {}
        functions: dict[str, Function] = {}
        types: dict[str, tuple[list[ClassField], dict[str, ClassMethod]]] = {}

        for target in self._resolve_scan_targets(module, options):
            t_vars, t_funcs, t_types = self._scan_module_members(
                target, respect_all=respect_all
            )
            for bucket, incoming in (
                (variables, t_vars),
                (functions, t_funcs),
                (types, t_types),
            ):
                for name, value in incoming.items():
                    if name in bucket:
                        logger.warning(
                            "Python scope collision: %r discovered in multiple "
                            "modules; keeping first occurrence",
                            name,
                        )
                        continue
                    bucket[name] = value

        return PythonSnapshot(
            version=version,
            source_kind="module",
            source_path=source_path,
            variables=variables,
            functions=functions,
            types=types,
        )

    def _build_directory_snapshot(
        self,
        root: Path,
        version: str,
        options: Optional[dict[str, Any]] = None,
    ) -> PythonSnapshot:
        """Build a namespaced snapshot for a repository/root directory.

        ``include`` is interpreted as importable top-level packages/modules under
        the root. Entries are scanned as real packages and then namespaced with
        the include item so unrelated packages can be tracked by one root config
        without collisions.
        """
        include = list((options or {}).get("include") or [])
        if not include:
            raise ValueError("Directory snapshots require include[] with package/module names")

        root_str = str(root.resolve())
        sys.path.insert(0, root_str)
        try:
            variables: dict[str, Variable] = {}
            functions: dict[str, Function] = {}
            types: dict[str, tuple[list[ClassField], dict[str, ClassMethod]]] = {}

            for item in include:
                module_name = str(item)
                if not module_name or self._has_private_component(module_name):
                    continue
                module = importlib.import_module(module_name)
                module_options = dict(options or {})
                module_options["include"] = [module_name]
                snap = self._build_snapshot(module, version, module_name, module_options)

                for name, value in snap.variables.items():
                    variables[f"{module_name}.{name}"] = value
                for name, value in snap.functions.items():
                    functions[f"{module_name}.{name}"] = value
                for name, value in snap.types.items():
                    types[f"{module_name}.{name}"] = value
        finally:
            if sys.path and sys.path[0] == root_str:
                sys.path.pop(0)

        return PythonSnapshot(
            version=version,
            source_kind="directory",
            source_path=str(root.resolve()),
            variables=variables,
            functions=functions,
            types=types,
        )


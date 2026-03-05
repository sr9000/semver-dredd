"""Go plugin implementation for semver-dredd."""

from __future__ import annotations

import subprocess
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
)

try:
    from importlib.resources import files
except ImportError:  # pragma: no cover
    files = None  # type: ignore[assignment]


# ---------------------------------------------------------------------------
# SNAPSHOT_TYPE_ID for the Go plugin snapshot format
# ---------------------------------------------------------------------------
GO_SNAPSHOT_TYPE_ID = str(
    _uuid.uuid5(_uuid.NAMESPACE_URL, "semver-dredd:plugin:go:GoSnapshot")
)


class GoSnapshot:
    """Go-specific API snapshot produced by the Go plugin.

    Stored as a YAML document with the following top-level fields::

        snapshot_type_id: <GO_SNAPSHOT_TYPE_ID>
        schema_version: 3
        version: "1.0.0"
        language: go
        source:
          kind: package
          path: ./pkg/geometry
        api:
          functions:
            Area:
              result_type: int
              args:
                - name: w
                  type: int
                  default: null
                - name: h
                  type: int
                  default: null
          types:
            Point:
              fields:
                - name: X
                  type: float64
                  default: null
              methods:
                Distance:
                  result_type: float64
                  args:
                    - name: other
                      type: "*Point"
                      default: null
    """

    SNAPSHOT_TYPE_ID: str = GO_SNAPSHOT_TYPE_ID

    def __init__(
        self,
        version: str = "",
        source_kind: str = "package",
        source_path: str = "",
        functions: dict[str, Function] | None = None,
        types: dict[str, tuple[list[ClassField], dict[str, ClassMethod]]] | None = None,
    ) -> None:
        self._version = version
        self.source_kind = source_kind
        self.source_path = source_path
        self.functions: dict[str, Function] = functions or {}
        self.types: dict[str, tuple[list[ClassField], dict[str, ClassMethod]]] = (
            types or {}
        )

    @property
    def version(self) -> str:
        return self._version

    # ------------------------------------------------------------------
    # Serialization
    # ------------------------------------------------------------------

    def to_dict(self) -> dict[str, Any]:
        functions: dict[str, Any] = {
            name: {
                "result_type": f.result_type,
                "args": [
                    {"name": a.name, "type": a.type, "default": a.default}
                    for a in f.args
                ],
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
                        "args": [
                            {"name": a.name, "type": a.type, "default": a.default}
                            for a in m.args
                        ],
                    }
                    for mname, m in methods.items()
                },
            }
        return {
            "snapshot_type_id": self.SNAPSHOT_TYPE_ID,
            "schema_version": 3,
            "version": self._version,
            "language": "go",
            "source": {"kind": self.source_kind, "path": self.source_path},
            "api": {
                "functions": functions,
                "types": types,
            },
        }

    def to_yaml(self) -> str:
        return yaml.dump(self.to_dict(), default_flow_style=False, sort_keys=False)

    # ------------------------------------------------------------------
    # Deserialization
    # ------------------------------------------------------------------

    @classmethod
    def from_yaml_str(cls, yaml_str: str) -> "GoSnapshot":
        data = yaml.safe_load(yaml_str)
        return cls._from_dict(data)

    @classmethod
    def from_file(cls, path: Path | str) -> "GoSnapshot":
        return cls.from_yaml_str(Path(path).read_text())

    @classmethod
    def _from_dict(cls, data: dict[str, Any]) -> "GoSnapshot":
        source = data.get("source", {})
        api = data.get("api", {})

        functions = {
            name: Function(
                name=name,
                result_type=f.get("result_type", "void"),
                args=tuple(
                    Argument(
                        name=a.get("name", ""),
                        type=a.get("type", "unknown"),
                        default=a.get("default"),
                    )
                    for a in f.get("args", f.get("parameters", []))
                ),
            )
            for name, f in api.get("functions", {}).items()
        }

        types: dict[str, tuple[list[ClassField], dict[str, ClassMethod]]] = {}
        for type_name, td in api.get("types", {}).items():
            fields = [
                ClassField(
                    name=fd.get("name", ""),
                    type=fd.get("type", "unknown"),
                    default=fd.get("default"),
                )
                for fd in td.get("fields", [])
            ]
            methods = {
                mname: ClassMethod(
                    name=mname,
                    result_type=m.get("result_type", "void"),
                    args=tuple(
                        Argument(
                            name=a.get("name", ""),
                            type=a.get("type", "unknown"),
                            default=a.get("default"),
                        )
                        for a in m.get("args", m.get("parameters", []))
                    ),
                )
                for mname, m in td.get("methods", {}).items()
            }
            types[type_name] = (fields, methods)

        return cls(
            version=data.get("version", ""),
            source_kind=source.get("kind", "package"),
            source_path=source.get("path", ""),
            functions=functions,
            types=types,
        )

    # ------------------------------------------------------------------
    # Diff (Comparable protocol)
    # ------------------------------------------------------------------

    def diff_against(self, other: "GoSnapshot"):
        """Compare this snapshot against *other*.

        Implements :class:`~snapshot.protocols.Comparable` by converting both
        sides to a :class:`~snapshot.models.NormalizedSnapshot` and delegating
        — all conversion knowledge stays inside the snapshot class.
        """
        return _go_snapshot_to_normalized(self).diff_against(
            _go_snapshot_to_normalized(other)
        )

def _go_snapshot_to_normalized(snap: "GoSnapshot"):
    """Convert GoSnapshot to NormalizedSnapshot for use with diff_snapshots."""
    from snapshot.models import (
        NormalizedSnapshot,
        FunctionSignature,
        TypeDefinition,
        Parameter,
        Field,
    )

    functions = {}
    for name, func in snap.functions.items():
        params = tuple(
            Parameter(name=a.name, type=a.type, optional=(a.default is not None))
            for a in func.args
        )
        functions[name] = FunctionSignature(name=name, parameters=params, returns=())

    types: dict = {}
    for type_name, type_data in snap.types.items():
        if isinstance(type_data, tuple):
            fields_list, methods_dict = type_data
        else:
            fields_list = getattr(type_data, "fields", [])
            methods_dict = getattr(type_data, "methods", {})

        fields = tuple(Field(name=f.name, type=f.type) for f in fields_list)
        methods = {}
        for mname, method in methods_dict.items():
            mparams = tuple(
                Parameter(name=a.name, type=a.type, optional=(a.default is not None))
                for a in method.args
            )
            methods[mname] = FunctionSignature(name=mname, parameters=mparams, returns=())
        types[type_name] = TypeDefinition(name=type_name, fields=fields, methods=methods)

    return NormalizedSnapshot(
        version=snap.version,
        language="go",
        functions=functions,
        types=types,
    )


class _GoDiffScorer:
    """Backward-compatible scorer: delegates to GoSnapshot.diff_against."""

    def diff(self, old: "GoSnapshot", new: "GoSnapshot"):
        return old.diff_against(new)


# ---------------------------------------------------------------------------
# Parser helpers
# ---------------------------------------------------------------------------

def _get_parser_dir() -> Path | None:
    """Get the path to the bundled Go parser directory."""
    if files is None:
        return None
    try:
        parser_pkg = files("semver_dredd_go").joinpath("parser")
        return Path(str(parser_pkg))
    except Exception:
        return None


# ---------------------------------------------------------------------------
# Plugin
# ---------------------------------------------------------------------------

class GoPlugin(LanguagePlugin):
    """Go language support plugin for semver-dredd.

    Analyzes Go packages using AST parsing via a bundled Go parser.
    Requires Go 1.20+ to be installed.

    The bundled Go parser emits schema v3 YAML which is deserialized into
    :class:`GoSnapshot` using the predefined component models
    (:class:`~snapshot.predefined.Function`, :class:`~snapshot.predefined.ClassField`,
    :class:`~snapshot.predefined.ClassMethod`, :class:`~snapshot.predefined.Argument`).
    """

    @property
    def name(self) -> str:
        return "go"

    @property
    def version(self) -> str:
        return "1.1.0"

    @property
    def description(self) -> str:
        return "Analyzes Go packages using bundled AST parser (predefined component models)"

    @property
    def snapshot_format_class(self) -> type:
        return GoSnapshot

    def validate_path(self, path: str) -> tuple[bool, str]:
        p = Path(path)
        if not p.exists():
            return False, f"Path does not exist: {path}"
        if not p.is_dir():
            return False, f"Path must be a directory for Go: {path}"
        go_files = list(p.glob("*.go"))
        if not go_files:
            return False, f"No .go files found in: {path}"
        return True, ""

    def get_parser_resource_path(self) -> Optional[Path]:
        return _get_parser_dir()

    @property
    def diff_scorer(self):
        return _GoDiffScorer()

    def generate_snapshot(
        self, path: str, version: str, options: Optional[dict[str, Any]] = None
    ) -> SnapshotResult:
        """Generate snapshot using bundled Go parser."""
        parser_dir = _get_parser_dir()

        if parser_dir is None or not parser_dir.exists():
            return SnapshotResult(
                False, "",
                "Go parser not found. Ensure semver-dredd-go is properly installed."
            )

        if not (parser_dir / "go.mod").exists():
            return SnapshotResult(
                False, "",
                f"Go parser incomplete: go.mod not found in {parser_dir}"
            )

        try:
            subprocess.run(["go", "version"], check=True, capture_output=True)
        except FileNotFoundError:
            return SnapshotResult(False, "", "'go' executable not found. Please install Go 1.20+.")
        except subprocess.CalledProcessError as e:
            return SnapshotResult(
                False, "",
                f"Go check failed: {e.stderr.decode() if e.stderr else str(e)}"
            )

        cmd = [
            "go", "run", ".",
            "--dir", str(Path(path).absolute()),
            "--version", version,
        ]

        try:
            result = subprocess.run(
                cmd, check=True, capture_output=True, text=True, cwd=str(parser_dir)
            )
            # Re-wrap the raw YAML into GoSnapshot format (adds snapshot_type_id)
            raw_snap = GoSnapshot._from_dict(
                _upgrade_legacy_yaml(result.stdout)
            )
            raw_snap._version = version
            return SnapshotResult(True, raw_snap.to_yaml())
        except subprocess.CalledProcessError as e:
            msg = (e.stderr or "").strip() or str(e)
            return SnapshotResult(False, "", f"Go parser failed: {msg}")


def _upgrade_legacy_yaml(yaml_str: str) -> dict[str, Any]:
    """Parse Go parser output (schema v2) and normalise to GoSnapshot dict format."""
    import yaml as _yaml
    data = _yaml.safe_load(yaml_str)
    if not isinstance(data, dict):
        return {}

    api = data.get("api", {})

    # Normalise function entries: schema v2 uses 'parameters'/'returns',
    # GoSnapshot._from_dict handles both via fallback to 'parameters'.
    functions: dict[str, Any] = {}
    for fname, fdata in api.get("functions", {}).items():
        params = fdata.get("parameters", fdata.get("args", []))
        returns = fdata.get("returns", [])
        # Use first return value as result_type
        result_type = "void"
        if returns:
            first = returns[0]
            result_type = first.get("type", "void") if isinstance(first, dict) else str(first)
        functions[fname] = {
            "result_type": result_type,
            "args": [
                {
                    "name": p.get("name", "") if isinstance(p, dict) else str(p),
                    "type": p.get("type", "unknown") if isinstance(p, dict) else "unknown",
                    "default": p.get("default") if isinstance(p, dict) else None,
                }
                for p in params
            ],
        }

    types: dict[str, Any] = {}
    for tname, tdata in api.get("types", api.get("classes", {})).items():
        fields_raw = tdata.get("fields", [])
        fields = [
            {
                "name": f.get("name", "") if isinstance(f, dict) else str(f),
                "type": f.get("type", "unknown") if isinstance(f, dict) else "unknown",
                "default": f.get("default") if isinstance(f, dict) else None,
            }
            for f in fields_raw
        ]
        methods: dict[str, Any] = {}
        for mname, mdata in tdata.get("methods", {}).items():
            params = mdata.get("parameters", mdata.get("args", []))
            returns = mdata.get("returns", [])
            result_type = "void"
            if returns:
                first = returns[0]
                result_type = first.get("type", "void") if isinstance(first, dict) else str(first)
            methods[mname] = {
                "result_type": result_type,
                "args": [
                    {
                        "name": p.get("name", "") if isinstance(p, dict) else str(p),
                        "type": p.get("type", "unknown") if isinstance(p, dict) else "unknown",
                        "default": p.get("default") if isinstance(p, dict) else None,
                    }
                    for p in params
                ],
            }
        types[tname] = {"fields": fields, "methods": methods}

    source = data.get("source", {})
    return {
        "snapshot_type_id": GO_SNAPSHOT_TYPE_ID,
        "schema_version": 3,
        "version": data.get("version", ""),
        "language": "go",
        "source": source,
        "api": {"functions": functions, "types": types},
    }

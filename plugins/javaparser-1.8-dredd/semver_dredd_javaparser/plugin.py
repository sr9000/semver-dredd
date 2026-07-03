"""JavaParser plugin implementation for semver-dredd.

Uses the JavaParser library (https://javaparser.org/) for proper AST-based
Java source analysis instead of regex-based extraction.
"""

from __future__ import annotations

import logging
import subprocess
import uuid as _uuid
from pathlib import Path
from typing import Any, Optional

import yaml

logger = logging.getLogger(__name__)


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
# SNAPSHOT_TYPE_ID for the JavaParser plugin snapshot format
# ---------------------------------------------------------------------------
JAVAPARSER_SNAPSHOT_TYPE_ID = str(
    _uuid.uuid5(
        _uuid.NAMESPACE_URL, "semver-dredd:plugin:javaparser:JavaParserSnapshot"
    )
)


class JavaParserSnapshot:
    """Java-specific API snapshot produced by the JavaParser plugin.

    Uses the same schema v3 YAML format as JavaSnapshot but with a
    distinct ``SNAPSHOT_TYPE_ID`` so the registry can tell them apart.

    Stored as a YAML document::

        snapshot_type_id: <JAVAPARSER_SNAPSHOT_TYPE_ID>
        schema_version: 3
        version: "1.0.0"
        language: java
        source:
          kind: directory
          path: ./src/main/java
        api:
          functions:
            MathUtils.add:
              result_type: int
              args:
                - name: a
                  type: int
                  default: null
                - name: b
                  type: int
                  default: null
          types:
            Point:
              fields:
                - name: x
                  type: double
                  default: null
              methods:
                distance:
                  result_type: double
                  args:
                    - name: other
                      type: Point
                      default: null
    """

    SNAPSHOT_TYPE_ID: str = JAVAPARSER_SNAPSHOT_TYPE_ID

    def __init__(
        self,
        version: str = "",
        source_kind: str = "directory",
        source_path: str = "",
        functions: dict[str, Function] | None = None,
        types: (
            dict[str, tuple[list[ClassField], dict[str, ClassMethod]]] | None
        ) = None,
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
            "language": "java",
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
    def from_yaml_str(cls, yaml_str: str) -> "JavaParserSnapshot":
        data = yaml.safe_load(yaml_str)
        return cls._from_dict(data)

    @classmethod
    def from_file(cls, path: Path | str) -> "JavaParserSnapshot":
        return cls.from_yaml_str(Path(path).read_text())

    @classmethod
    def _from_dict(cls, data: dict[str, Any]) -> "JavaParserSnapshot":
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
        for type_name, td in api.get("types", api.get("classes", {})).items():
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
            source_kind=source.get("kind", "directory"),
            source_path=source.get("path", ""),
            functions=functions,
            types=types,
        )

    # ------------------------------------------------------------------
    # Diff (Comparable protocol)
    # ------------------------------------------------------------------

    def diff_against(self, other: "JavaParserSnapshot"):
        """Compare this snapshot against *other*.

        Implements :class:`~snapshot.protocols.Comparable` by converting both
        sides to a :class:`~snapshot.models.NormalizedSnapshot` and delegating.
        """
        return _javaparser_snapshot_to_normalized(self).diff_against(
            _javaparser_snapshot_to_normalized(other)
        )


def _javaparser_snapshot_to_normalized(snap: "JavaParserSnapshot"):
    """Convert JavaParserSnapshot to NormalizedSnapshot for diff support."""
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
            methods[mname] = FunctionSignature(
                name=mname, parameters=mparams, returns=()
            )
        types[type_name] = TypeDefinition(
            name=type_name, fields=fields, methods=methods
        )

    return NormalizedSnapshot(
        version=snap.version,
        language="java",
        functions=functions,
        types=types,
    )


# ---------------------------------------------------------------------------
# Parser helpers
# ---------------------------------------------------------------------------


def _get_parser_dir() -> Path | None:
    """Get the path to the bundled JavaParser-based parser directory."""
    if files is None:
        return None
    try:
        parser_pkg = files("semver_dredd_javaparser").joinpath("parser")
        return Path(str(parser_pkg))
    except Exception:
        return None


def _get_classpath(parser_dir: Path) -> str | None:
    """Build the classpath string with all bundled JARs."""
    lib_dir = parser_dir / "lib"
    if not lib_dir.exists():
        return None
    jars = list(lib_dir.glob("*.jar"))
    if not jars:
        return None
    return ":".join(str(j) for j in sorted(jars))


# ---------------------------------------------------------------------------
# Plugin
# ---------------------------------------------------------------------------


class JavaParserPlugin(LanguagePlugin):
    """Java language support plugin using JavaParser AST analysis.

    Analyzes Java source files using the JavaParser library
    (https://javaparser.org/) for accurate AST-based extraction of classes,
    interfaces, fields, and methods.

    Requires JDK 1.8+ to be installed.
    """

    @property
    def name(self) -> str:
        return "javaparser"

    @property
    def version(self) -> str:
        return "1.0.0"

    @property
    def description(self) -> str:
        return "Analyzes Java source using JavaParser AST library"

    @property
    def snapshot_format_class(self) -> type:
        return JavaParserSnapshot

    @property
    def metadata(self) -> dict[str, Any]:
        return {
            "scope": {
                "syntax": "Java package prefixes",
                "include_mode": "recursive allow-list",
                "exclude_mode": "exclude after include; trailing '*' excludes one package level",
                "empty_include": "analyze all parsed public API under the configured path",
            },
            "plugin_options": [],
            "runtime_requirements": {
                "python": ">=3.10",
                "external_tools": ["javac>=1.8", "java>=1.8"],
            },
            "features": ["metadata", "machine_readable_inventory"],
        }

    def validate_path(self, path: str) -> tuple[bool, str]:
        p = Path(path)
        if not p.exists():
            return False, f"Path does not exist: {path}"
        if not p.is_dir():
            return False, f"Path must be a directory for Java: {path}"
        java_files = list(p.rglob("*.java"))
        if not java_files:
            return False, f"No .java files found in: {path}"
        return True, ""

    def get_parser_resource_path(self) -> Optional[Path]:
        return _get_parser_dir()

    def _compile_parser(
        self, parser_dir: Path, classpath: str
    ) -> tuple[bool, str]:
        src = parser_dir / "Main.java"
        cls_file = parser_dir / "Main.class"
        if cls_file.exists() and cls_file.stat().st_mtime >= src.stat().st_mtime:
            return True, ""
        cmd = ["javac", "-cp", classpath, str(src)]
        try:
            subprocess.run(cmd, check=True, capture_output=True, text=True)
            return True, ""
        except FileNotFoundError:
            return False, "'javac' not found. Please install JDK 1.8+."
        except subprocess.CalledProcessError as e:
            return False, f"Compilation failed: {e.stderr or str(e)}"

    def generate_snapshot(
        self, path: str, version: str, options: Optional[dict[str, Any]] = None
    ) -> SnapshotResult:
        """Generate snapshot using the bundled JavaParser-based parser."""
        parser_dir = _get_parser_dir()

        if parser_dir is None or not parser_dir.exists():
            return SnapshotResult(
                False,
                "",
                "JavaParser parser not found. "
                "Ensure javaparser-1.8-dredd is properly installed.",
            )

        classpath = _get_classpath(parser_dir)
        if classpath is None:
            return SnapshotResult(
                False,
                "",
                "Required JAR files not found in parser/lib/. "
                "Plugin may be corrupted or incomplete.",
            )

        ok, err = self._compile_parser(parser_dir, classpath)
        if not ok:
            return SnapshotResult(False, "", err)

        full_cp = f"{classpath}:{parser_dir}"
        cmd = [
            "java",
            "-cp",
            full_cp,
            "Main",
            "--dir",
            str(Path(path).absolute()),
            "--version",
            version,
        ]

        try:
            result = subprocess.run(
                cmd, check=True, capture_output=True, text=True
            )
            raw_snap = JavaParserSnapshot._from_dict(
                _upgrade_legacy_yaml(result.stdout)
            )
            raw_snap._version = version
            _filter_snapshot_scope(raw_snap, options)
            return SnapshotResult(True, raw_snap.to_yaml())

        except FileNotFoundError:
            return SnapshotResult(
                False,
                "",
                "'java' executable not found. Please install JRE/JDK 1.8+.",
            )
        except subprocess.CalledProcessError as e:
            msg = (e.stderr or "").strip() or str(e)
            return SnapshotResult(False, "", f"JavaParser failed: {msg}")


def _matches_package_scope(name: str, item: Any) -> bool:
    """Match a function/type name against a package-prefix scope item.

    ``item`` may end with a trailing ``*`` to mean "this package only, not
    nested sub-packages". Otherwise matching is recursive: ``item`` matches
    ``name`` itself and any dotted-prefix descendant of it.
    """
    item_str = str(item)
    if item_str.endswith("*"):
        prefix = item_str[:-1].rstrip(".")
        if not name.startswith(prefix + "."):
            return False
        rest = name[len(prefix) + 1 :]
        return "." not in rest.rsplit(".", 1)[0] if "." in rest else True
    return name == item_str or name.startswith(item_str + ".")


def _filter_snapshot_scope(
    snap: "JavaParserSnapshot", options: Optional[dict[str, Any]]
) -> None:
    """Apply include/exclude package-prefix scope filtering in place.

    Mirrors the regex Java plugin's scope semantics: ``include`` is a
    recursive package-prefix allow-list (empty means keep everything),
    ``exclude`` is applied after include and supports a trailing ``*`` for
    non-recursive (single package level) exclusion.
    """
    if not options:
        return
    include = list(options.get("include") or [])
    exclude = list(options.get("exclude") or [])
    if not include and not exclude:
        return

    def keep(name: str) -> bool:
        if include and not any(_matches_package_scope(name, item) for item in include):
            return False
        if exclude and any(_matches_package_scope(name, item) for item in exclude):
            return False
        return True

    snap.functions = {name: f for name, f in snap.functions.items() if keep(name)}
    snap.types = {name: t for name, t in snap.types.items() if keep(name)}

    if include and not snap.functions and not snap.types:
        logger.warning(
            "JavaParser scope include/exclude matched no functions or types "
            "(include=%r, exclude=%r)",
            include,
            exclude,
        )


def _upgrade_legacy_yaml(yaml_str: str) -> dict[str, Any]:
    """Parse Java parser output (schema v2) and normalise to snapshot dict format."""

    import yaml as _yaml

    data = _yaml.safe_load(yaml_str)
    if not isinstance(data, dict):
        return {}

    api = data.get("api", {})

    functions: dict[str, Any] = {}
    for fname, fdata in api.get("functions", {}).items():
        params = fdata.get("parameters", fdata.get("args", []))
        returns = fdata.get("returns", [])
        result_type = "void"
        if returns:
            first = returns[0]
            result_type = (
                first.get("type", "void") if isinstance(first, dict) else str(first)
            )
        functions[fname] = {
            "result_type": result_type,
            "args": [
                {
                    "name": p.get("name", "") if isinstance(p, dict) else str(p),
                    "type": (
                        p.get("type", "unknown") if isinstance(p, dict) else "unknown"
                    ),
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
                "type": (
                    f.get("type", "unknown") if isinstance(f, dict) else "unknown"
                ),
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
                result_type = (
                    first.get("type", "void")
                    if isinstance(first, dict)
                    else str(first)
                )
            methods[mname] = {
                "result_type": result_type,
                "args": [
                    {
                        "name": (
                            p.get("name", "") if isinstance(p, dict) else str(p)
                        ),
                        "type": (
                            p.get("type", "unknown")
                            if isinstance(p, dict)
                            else "unknown"
                        ),
                        "default": p.get("default") if isinstance(p, dict) else None,
                    }
                    for p in params
                ],
            }
        types[tname] = {"fields": fields, "methods": methods}

    source = data.get("source", {})
    return {
        "snapshot_type_id": JAVAPARSER_SNAPSHOT_TYPE_ID,
        "schema_version": 3,
        "version": data.get("version", ""),
        "language": "java",
        "source": source,
        "api": {"functions": functions, "types": types},
    }

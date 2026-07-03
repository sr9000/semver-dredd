"""Built-in bundle plugin."""

from __future__ import annotations

import uuid as _uuid
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Optional

import yaml

from semverdredd.plugin_base import LanguagePlugin, SnapshotResult
from semverdredd.version import Version
from snapshot.change_kind import ChangeKind
from snapshot.protocols import DiffResult


BUNDLE_SNAPSHOT_TYPE_ID = str(
    _uuid.uuid5(_uuid.NAMESPACE_URL, "semver-dredd:plugin:bundle:BundleSnapshot")
)


@dataclass(frozen=True)
class BundleDependency:
    name: str
    path: str
    version: str


class BundleSnapshot:
    """Snapshot of a bundle of dependency VERSION files."""

    SNAPSHOT_TYPE_ID: str = BUNDLE_SNAPSHOT_TYPE_ID

    def __init__(
        self,
        version: str = "",
        source_kind: str = "bundle",
        source_path: str = "",
        dependencies: dict[str, BundleDependency] | None = None,
    ) -> None:
        self._version = version
        self.source_kind = source_kind
        self.source_path = source_path
        self.dependencies = dependencies or {}

    @property
    def version(self) -> str:
        return self._version

    def to_dict(self) -> dict[str, Any]:
        return {
            "snapshot_type_id": self.SNAPSHOT_TYPE_ID,
            "schema_version": 3,
            "version": self._version,
            "language": "bundle",
            "source": {"kind": self.source_kind, "path": self.source_path},
            "api": {
                "dependencies": {
                    name: {
                        "path": dep.path,
                        "version": dep.version,
                    }
                    for name, dep in sorted(self.dependencies.items())
                }
            },
        }

    def to_yaml(self) -> str:
        return yaml.dump(self.to_dict(), default_flow_style=False, sort_keys=False)

    @classmethod
    def from_yaml_str(cls, yaml_str: str) -> "BundleSnapshot":
        data = yaml.safe_load(yaml_str)
        return cls._from_dict(data)

    @classmethod
    def from_file(cls, path: Path | str) -> "BundleSnapshot":
        return cls.from_yaml_str(Path(path).read_text())

    @classmethod
    def _from_dict(cls, data: dict[str, Any]) -> "BundleSnapshot":
        source = data.get("source", {})
        deps = data.get("api", {}).get("dependencies", {})
        dependencies = {
            name: BundleDependency(
                name=name,
                path=str(dep.get("path", "")),
                version=str(dep.get("version", "")),
            )
            for name, dep in deps.items()
        }
        return cls(
            version=str(data.get("version", "")),
            source_kind=str(source.get("kind", "bundle")),
            source_path=str(source.get("path", "")),
            dependencies=dependencies,
        )

    def diff_against(self, other: "BundleSnapshot") -> DiffResult:
        """Temporary placeholder until bundle diff semantics land."""
        return DiffResult(change_kind=ChangeKind.NONE)


class BundlePlugin(LanguagePlugin):
    """Built-in aggregate plugin for VERSION-file bundles."""

    @property
    def name(self) -> str:
        return "bundle"

    @property
    def version(self) -> str:
        return "0.1.0"

    @property
    def description(self) -> str:
        return "Analyzes bundles of VERSION files without a language-specific parser"

    @property
    def snapshot_format_class(self) -> type:
        return BundleSnapshot

    @property
    def metadata(self) -> dict[str, Any]:
        return {
            "scope": {
                "syntax": "paths to VERSION files in include[]",
                "include_mode": "explicit dependency list",
                "exclude_mode": "not used",
                "empty_include": "invalid for bundle snapshots",
            },
            "plugin_options": [],
            "runtime_requirements": {
                "python": ">=3.10",
                "external_tools": [],
            },
            "features": ["metadata", "machine_readable_inventory"],
        }

    def validate_path(self, path: str) -> tuple[bool, str]:
        """Bundle uses config include paths rather than validating a source tree."""
        return True, ""

    def generate_snapshot(
        self, path: str, version: str, options: Optional[dict[str, Any]] = None
    ) -> SnapshotResult:
        include = list((options or {}).get("include") or [])
        if not include:
            return SnapshotResult(
                False,
                "",
                "Bundle plugin requires include[] entries pointing to VERSION files",
            )

        try:
            dependencies = self._load_dependencies(path, include)
        except ValueError as e:
            return SnapshotResult(False, "", str(e))

        snapshot = BundleSnapshot(
            version=version,
            source_kind="bundle",
            source_path=str(Path(path).resolve()) if Path(path).exists() else str(path),
            dependencies=dependencies,
        )
        return SnapshotResult(True, snapshot.to_yaml())

    def _load_dependencies(
        self, base_path: str, include_items: list[Any]
    ) -> dict[str, BundleDependency]:
        base_dir = Path(base_path).resolve() if Path(base_path).exists() else Path.cwd()
        dependencies: dict[str, BundleDependency] = {}

        for item in include_items:
            item_str = str(item)
            if any(char in item_str for char in "*?["):
                raise ValueError(f"Bundle plugin does not support globs in include: {item_str!r}")

            raw_path = Path(item_str)
            version_path = raw_path if raw_path.is_absolute() else (base_dir / raw_path)
            version_path = version_path.resolve()

            if not version_path.exists() or not version_path.is_file():
                raise ValueError(f"Bundle dependency VERSION file not found: {item_str}")

            version_text = version_path.read_text().strip()
            Version.parse(version_text)

            rel_path = self._relative_path(version_path, base_dir)
            name = self._derive_dependency_name(rel_path)
            dependencies[name] = BundleDependency(
                name=name,
                path=rel_path.as_posix(),
                version=version_text,
            )

        return dependencies

    @staticmethod
    def _relative_path(version_path: Path, base_dir: Path) -> Path:
        try:
            return version_path.relative_to(base_dir)
        except ValueError:
            return version_path

    @staticmethod
    def _derive_dependency_name(relative_path: Path) -> str:
        if relative_path.name == "VERSION":
            parent = relative_path.parent.as_posix()
            return parent if parent not in ("", ".") else "VERSION"
        return relative_path.with_suffix("").as_posix()
"""Go plugin implementation for semver-dredd."""

from __future__ import annotations

import subprocess
from pathlib import Path
from typing import Any, Optional

from semverdredd.plugin_base import LanguagePlugin, SnapshotResult

try:
    from importlib.resources import files
except ImportError:  # pragma: no cover
    files = None  # type: ignore[assignment]


def _get_parser_dir() -> Path | None:
    """Get the path to the bundled Go parser directory."""
    if files is None:
        return None
    try:
        parser_pkg = files("semver_dredd_go").joinpath("parser")
        return Path(str(parser_pkg))
    except Exception:
        return None


class GoPlugin(LanguagePlugin):
    """Go language support plugin for semver-dredd.

    Analyzes Go packages using AST parsing via a bundled Go parser.
    Requires Go 1.20+ to be installed.
    """

    @property
    def name(self) -> str:
        return "go"

    @property
    def version(self) -> str:
        return "1.0.0"

    @property
    def description(self) -> str:
        return "Analyzes Go packages using bundled AST parser"

    def validate_path(self, path: str) -> tuple[bool, str]:
        """Validate that the path is a valid Go package."""
        p = Path(path)

        if not p.exists():
            return False, f"Path does not exist: {path}"

        if not p.is_dir():
            return False, f"Path must be a directory for Go: {path}"

        # Check for .go files
        go_files = list(p.glob("*.go"))
        if not go_files:
            return False, f"No .go files found in: {path}"

        return True, ""

    def get_parser_resource_path(self) -> Optional[Path]:
        """Return path to bundled parser resources."""
        return _get_parser_dir()

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

        # Check if go.mod exists
        if not (parser_dir / "go.mod").exists():
            return SnapshotResult(
                False, "",
                f"Go parser incomplete: go.mod not found in {parser_dir}"
            )

        # Check if 'go' is available
        try:
            subprocess.run(
                ["go", "version"],
                check=True,
                capture_output=True
            )
        except FileNotFoundError:
            return SnapshotResult(
                False, "",
                "'go' executable not found. Please install Go 1.20+."
            )
        except subprocess.CalledProcessError as e:
            return SnapshotResult(
                False, "",
                f"Go check failed: {e.stderr.decode() if e.stderr else str(e)}"
            )

        # Run the parser
        cmd = [
            "go", "run", ".",
            "--dir", str(Path(path).absolute()),
            "--version", version,
        ]

        try:
            result = subprocess.run(
                cmd,
                check=True,
                capture_output=True,
                text=True,
                cwd=str(parser_dir)
            )
            return SnapshotResult(True, result.stdout)
        except subprocess.CalledProcessError as e:
            msg = (e.stderr or "").strip() or str(e)
            return SnapshotResult(False, "", f"Go parser failed: {msg}")

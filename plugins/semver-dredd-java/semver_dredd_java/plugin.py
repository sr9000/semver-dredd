"""Java plugin implementation for semver-dredd."""

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
    """Get the path to the bundled Java parser directory."""
    if files is None:
        return None
    try:
        parser_pkg = files("semver_dredd_java").joinpath("parser")
        return Path(str(parser_pkg))
    except Exception:
        return None


class JavaPlugin(LanguagePlugin):
    """Java language support plugin for semver-dredd.

    Analyzes Java source files using a bundled regex-based parser.
    Requires JDK 11+ to be installed.
    """

    @property
    def name(self) -> str:
        return "java"

    @property
    def version(self) -> str:
        return "1.0.0"

    @property
    def description(self) -> str:
        return "Analyzes Java source using bundled parser"

    def validate_path(self, path: str) -> tuple[bool, str]:
        """Validate that the path contains Java source files."""
        p = Path(path)

        if not p.exists():
            return False, f"Path does not exist: {path}"

        if not p.is_dir():
            return False, f"Path must be a directory for Java: {path}"

        # Check for .java files (recursively)
        java_files = list(p.rglob("*.java"))
        if not java_files:
            return False, f"No .java files found in: {path}"

        return True, ""

    def get_parser_resource_path(self) -> Optional[Path]:
        """Return path to bundled parser resources."""
        return _get_parser_dir()

    def _get_jar_path(self) -> Optional[Path]:
        """Get path to snakeyaml JAR."""
        parser_dir = _get_parser_dir()
        if parser_dir:
            jar = parser_dir / "lib" / "snakeyaml-2.2.jar"
            if jar.exists():
                return jar
        return None

    def _compile_parser(self, parser_dir: Path, jar_path: Path) -> tuple[bool, str]:
        """Compile the Java parser if needed."""
        src = parser_dir / "main.java"
        cls = parser_dir / "main.class"

        # Skip if already compiled and up-to-date
        if cls.exists() and cls.stat().st_mtime >= src.stat().st_mtime:
            return True, ""

        cmd = ["javac", "-cp", str(jar_path), str(src)]
        try:
            subprocess.run(cmd, check=True, capture_output=True, text=True)
            return True, ""
        except FileNotFoundError:
            return False, "'javac' not found. Please install JDK 11+."
        except subprocess.CalledProcessError as e:
            return False, f"Compilation failed: {e.stderr or str(e)}"

    def generate_snapshot(
        self, path: str, version: str, options: Optional[dict[str, Any]] = None
    ) -> SnapshotResult:
        """Generate snapshot using bundled Java parser."""
        parser_dir = _get_parser_dir()

        if parser_dir is None or not parser_dir.exists():
            return SnapshotResult(
                False, "",
                "Java parser not found. Ensure semver-dredd-java is properly installed."
            )

        jar_path = self._get_jar_path()
        if jar_path is None:
            return SnapshotResult(
                False, "",
                "snakeyaml JAR not found. Plugin may be corrupted or incomplete."
            )

        # Compile if needed
        ok, err = self._compile_parser(parser_dir, jar_path)
        if not ok:
            return SnapshotResult(False, "", err)

        # Run parser
        cmd = [
            "java", "-cp", f"{jar_path}:{parser_dir}", "main",
            "--dir", str(Path(path).absolute()),
            "--version", version,
        ]

        try:
            result = subprocess.run(
                cmd,
                check=True,
                capture_output=True,
                text=True
            )
            return SnapshotResult(True, result.stdout)
        except FileNotFoundError:
            return SnapshotResult(
                False, "",
                "'java' executable not found. Please install JRE/JDK 11+."
            )
        except subprocess.CalledProcessError as e:
            msg = (e.stderr or "").strip() or str(e)
            return SnapshotResult(False, "", f"Java parser failed: {msg}")

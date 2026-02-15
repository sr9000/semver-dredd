from __future__ import annotations

import subprocess
from pathlib import Path
from typing import Any, Optional

from semverdredd.plugin_base import LanguagePlugin, SnapshotResult

try:
    from importlib.resources import files
except ImportError:  # pragma: no cover
    files = None  # type: ignore[assignment]


def _resource_parser_dir(*parts: str) -> Path | None:
    """Resolve a parser directory shipped inside the core distribution.

    In this repo we keep parsers under the top-level `parser/` folder, which is
    included as package data for the `semverdredd` package.
    """
    if files is None:
        return None
    try:
        candidate = files("semverdredd").joinpath(*parts)
        return Path(str(candidate))
    except Exception:
        return None


def _dev_parser_dir(*parts: str) -> Path:
    # semverdredd/plugins/go.py -> semverdredd -> repo root
    return Path(__file__).resolve().parents[2].joinpath(*parts)


class GoPlugin(LanguagePlugin):
    @property
    def name(self) -> str:
        return "go"

    @property
    def version(self) -> str:
        return "1.0.0"

    @property
    def description(self) -> str:
        return "Analyzes Go packages using bundled parser (go run)"

    def generate_snapshot(self, path: str, version: str, options: Optional[dict[str, Any]] = None) -> SnapshotResult:
        parser_dir = _resource_parser_dir("parser", "golang")
        if not parser_dir or not parser_dir.exists():
            parser_dir = _dev_parser_dir("parser", "golang")

        if not parser_dir.exists():
            return SnapshotResult(False, "", "Go parser not found in package resources.")

        cmd = [
            "go",
            "run",
            ".",
            "--dir",
            str(Path(path).absolute()),
            "--version",
            version,
        ]

        try:
            result = subprocess.run(cmd, check=True, capture_output=True, text=True, cwd=str(parser_dir))
            return SnapshotResult(True, result.stdout)
        except FileNotFoundError:
            return SnapshotResult(False, "", "Error: 'go' executable not found.")
        except subprocess.CalledProcessError as e:
            msg = (e.stderr or "").strip() or str(e)
            return SnapshotResult(False, "", msg)


class JavaPlugin(LanguagePlugin):
    @property
    def name(self) -> str:
        return "java"

    @property
    def version(self) -> str:
        return "1.0.0"

    @property
    def description(self) -> str:
        return "Analyzes Java source using bundled parser (javac/java)"

    def generate_snapshot(self, path: str, version: str, options: Optional[dict[str, Any]] = None) -> SnapshotResult:
        java_dir = _resource_parser_dir("parser", "java")
        if not java_dir or not java_dir.exists():
            java_dir = _dev_parser_dir("parser", "java")

        jar = java_dir / "lib" / "snakeyaml-2.2.jar"
        src = java_dir / "main.java"

        if not jar.exists():
            return SnapshotResult(False, "", f"Error: Missing {jar}. Install snakeyaml jar or use Maven build.")

        compile_cmd = ["javac", "-cp", str(jar), str(src)]
        try:
            subprocess.run(compile_cmd, check=True, capture_output=True, text=True)
        except subprocess.CalledProcessError as e:
            return SnapshotResult(False, "", f"javac failed: {e.stderr or e}")
        except FileNotFoundError:
            return SnapshotResult(False, "", "Error: 'javac' executable not found.")

        cmd = [
            "java",
            "-cp",
            f"{jar}:{java_dir}",
            "main",
            "--dir",
            str(Path(path).absolute()),
            "--version",
            version,
        ]

        try:
            result = subprocess.run(cmd, check=True, capture_output=True, text=True)
            return SnapshotResult(True, result.stdout)
        except subprocess.CalledProcessError as e:
            msg = (e.stderr or "").strip() or str(e)
            return SnapshotResult(False, "", msg)
        except FileNotFoundError:
            return SnapshotResult(False, "", "Error: 'java' executable not found.")

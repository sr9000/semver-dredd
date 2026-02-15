from __future__ import annotations

import subprocess
from pathlib import Path
from typing import Optional, Any

from semverdredd import LanguagePlugin, SnapshotResult
from semverdredd.plugins.go import _resource_parser_dir, _dev_parser_dir


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

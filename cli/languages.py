from abc import ABC, abstractmethod
from pathlib import Path
import subprocess
from typing import Tuple, Optional, Dict

class LanguagePlugin(ABC):
    @property
    @abstractmethod
    def name(self) -> str:
        """The language name (e.g. 'go', 'java')."""
        pass

    @abstractmethod
    def generate_snapshot(self, path: str, version: str, use_color: bool) -> Tuple[int, str]:
        """
        Generates a snapshot YAML string.
        Returns: (exit_code, yaml_output)
        """
        pass

class GoPlugin(LanguagePlugin):
    @property
    def name(self) -> str:
        return "go"

    def generate_snapshot(self, path: str, version: str, use_color: bool) -> Tuple[int, str]:
        # Assuming we are running from the installed package location
        # or development root.
        # We need to find the parser directory relative to this file.
        # This file is in cli/languages.py. Parser is in ../parser/golang

        # When installed, the parsers might not be there?
        # For now assuming dev structure as seen in context.
        parser_dir = Path(__file__).parent.parent / "parser" / "golang"

        cmd = [
            "go", "run", ".",
            "--dir", str(Path(path).absolute()),
            "--version", version,
        ]

        try:
            result = subprocess.run(cmd, check=True, capture_output=True, text=True, cwd=str(parser_dir))
            return 0, result.stdout
        except FileNotFoundError:
            return 1, "Error: 'go' executable not found."
        except subprocess.CalledProcessError as e:
            return e.returncode or 1, str(e.stderr or e)

class JavaPlugin(LanguagePlugin):
    @property
    def name(self) -> str:
        return "java"

    def generate_snapshot(self, path: str, version: str, use_color: bool) -> Tuple[int, str]:
        java_dir = Path(__file__).parent.parent / "parser" / "java"
        jar = java_dir / "lib" / "snakeyaml-2.2.jar"
        src = java_dir / "main.java"

        if not jar.exists():
            return 1, f"Error: Missing {jar}. Install snakeyaml jar or use Maven build."

        # Compile
        compile_cmd = ["javac", "-cp", str(jar), str(src)]
        try:
            subprocess.run(compile_cmd, check=True, capture_output=True, text=True)
        except subprocess.CalledProcessError as e:
             return 1, f"javac failed: {e.stderr or e}"
        except FileNotFoundError:
            return 1, "Error: 'javac' executable not found."

        cmd = [
            "java", "-cp", f"{jar}:{java_dir}", "main",
            "--dir", str(Path(path).absolute()),
            "--version", version,
        ]

        try:
            result = subprocess.run(cmd, check=True, capture_output=True, text=True)
            return 0, result.stdout
        except subprocess.CalledProcessError as e:
            return e.returncode or 1, str(e.stderr or e)
        except FileNotFoundError:
            return 1, "Error: 'java' executable not found."

_REGISTRY: Dict[str, LanguagePlugin] = {
    "go": GoPlugin(),
    "java": JavaPlugin()
}

_PLUGINS_LOADED = False

def load_plugins():
    global _PLUGINS_LOADED
    if _PLUGINS_LOADED:
        return

    import sys

    # Python 3.10+ uses importlib.metadata.entry_points(group=...)
    # Older versions use importlib.metadata.entry_points().get(...)
    if sys.version_info >= (3, 10):
        from importlib.metadata import entry_points
        plugins = entry_points(group='semver_dredd.plugins')
    else:
        from importlib.metadata import entry_points
        plugins = entry_points().get('semver_dredd.plugins', [])

    for entry in plugins:
        try:
            plugin_cls = entry.load()
            plugin = plugin_cls()
            register_plugin(plugin)
        except Exception as e:
            # We silently ignore failed plugins for now, or print to stderr if we could
            pass

    _PLUGINS_LOADED = True

def get_plugin(lang: str) -> Optional[LanguagePlugin]:
    load_plugins()
    return _REGISTRY.get(lang.lower())

def register_plugin(plugin: LanguagePlugin):
    _REGISTRY[plugin.name.lower()] = plugin

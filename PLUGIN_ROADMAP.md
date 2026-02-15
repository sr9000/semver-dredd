# Plugin System Refactoring Roadmap

## Executive Summary

This document outlines the plan to refactor semver-dredd's plugin system from a hardcoded, path-dependent implementation to a robust, entry-point-based architecture following Python community best practices.

**Key Goals:**
- Make Python itself a plugin (not special-cased in core)
- Use `entry_points` for plugin discovery (standard Python mechanism)
- Support user-managed plugin directory (`~/.semver-dredd/plugins/`)
- Provide CLI commands for plugin management (`install`, `remove`, `list`)
- Package each language plugin as an independent, installable package

---

## Current State Analysis

### Problems with Current Implementation

1. **Hardcoded Path Resolution**
   ```python
   # cli/languages.py - current approach
   parser_dir = Path(__file__).parent.parent / "parser" / "golang"
   ```
   - Breaks when installed via `pip` (parsers not in expected location)
   - Requires development directory structure
   - Not portable across environments

2. **Python is Special-Cased**
   - Python module analysis is embedded in `semverdredd/__init__.py`
   - Go/Java use plugins, Python uses direct imports
   - Inconsistent API surface

3. **No Plugin Management**
   - Users cannot install/remove language support
   - No discovery mechanism for third-party plugins
   - Registry is compile-time only

4. **Cross-Language Assets Bundling**
   - Go parser requires `go run .` from source directory
   - Java parser requires JAR in specific location
   - No standard way to locate these assets

---

## Target Architecture

### 1. Core Package Structure

```
semver-dredd/                          # Core package (this repo)
├── pyproject.toml
├── semverdredd/
│   ├── __init__.py                    # Core API (ChangeType, Version, compare logic)
│   ├── plugin_base.py                 # ABC for LanguagePlugin
│   ├── plugin_manager.py              # Discovery, loading, registry
│   ├── snapshot_schema.py             # Normalized snapshot format
│   ├── diff.py                        # Cross-language diff logic
│   ├── xldiff.py                      # Existing cross-language diff
│   ├── version.py                     # Version parsing/increment
│   └── result.py                      # Pure data result types
├── cli/
│   ├── __init__.py                    # CLI entry point
│   ├── config.py                      # Config loading
│   └── commands/
│       ├── __init__.py
│       ├── compare.py
│       ├── status.py
│       ├── bake.py
│       ├── init.py
│       └── plugin.py                  # NEW: plugin management commands
└── tests/
```

### 2. Plugin Package Structure (Template)

Each language plugin will be a separate installable package. Distribution package names SHOULD follow one of the schemes below (preferred is the vendor-aware form):

```
# Preferred (supports multiple plugin vendors for the same language/version):
language-<lang_version>-<plugin_source>-<plugin_version>[-extras]

# Backwards-compatible simpler form (no vendor):
language-<lang_version>-<plugin_version>[-extras]
```

- language: short language id (e.g. `python`, `go`, `java`)
- lang_version: the target language/runtime version (e.g. `3.10`, `1.20`, `17`)
- plugin_source: short vendor or distribution id (e.g. `core`, `official`, `acme`, `gogen`) to allow multiple implementations for the same language/runtime
- plugin_version: semver for the plugin itself (e.g. `1.0.0`)
- extras: optional qualifiers (platform, arch, debug) if needed

Examples (vendor-aware):
- `python-3.10-core-1.0.0` (official/core Python plugin targeting Python 3.10)
- `go-1.20-gogen-1.0.0` (Go AST plugin from vendor `gogen` targeting Go 1.20)
- `java-17-acme-1.0.0` (Java plugin from `acme` targeting Java 17)

Note: the distribution (PyPI/package) name uses one of the above schemes. The importable Python module inside the distribution should still expose a stable entry point module (for example `semver_dredd_python.plugin:PythonPlugin`) and register an entry-point under `semver_dredd.plugins`. This keeps discovery stable while allowing simple, descriptive distribution names and multiple vendors.

Example layout (distribution name + internal importable package) using the vendor-aware form:

```
python-3.10-core-1.0.0/                 # distribution package (PyPI name)
├── pyproject.toml                        # project.name = "python-3.10-core-1.0.0"
├── semver_dredd_python/                  # importable Python package (module name)
│   ├── __init__.py
│   ├── plugin.py                        # PythonPlugin(LanguagePlugin)
│   └── analyzer.py                      # Python-specific analysis logic
└── tests/

go-1.20-gogen-1.0.0/                      # distribution package
├── pyproject.toml
├── semver_dredd_go/                      # importable Python package
│   ├── __init__.py
│   ├── plugin.py                        # GoPlugin(LanguagePlugin)
│   └── parser/                          # Bundled Go source
│       ├── go.mod
│       ├── go.sum
│       └── main.go
└── tests/

java-17-acme-1.0.0/                       # distribution package
├── pyproject.toml
├── semver_dredd_java/
│   ├── __init__.py
│   ├── plugin.py                        # JavaPlugin(LanguagePlugin)
│   └── parser/
│       ├── main.java
│       └── lib/
│           └── snakeyaml-2.2.jar
└── tests/
```

---

## Implementation Phases

### Phase 1: Core Plugin Infrastructure

#### 1.1 Create Plugin Base Class

Create `semverdredd/plugin_base.py`:

```python
from abc import ABC, abstractmethod
from typing import Tuple, Optional, Dict, Any
from dataclasses import dataclass
from pathlib import Path

@dataclass
class SnapshotResult:
    """Result of snapshot generation."""
    success: bool
    yaml_content: str
    error_message: Optional[str] = None

class LanguagePlugin(ABC):
    """Abstract base class for language plugins.
    
    All language support (including Python) must implement this interface.
    """
    
    @property
    @abstractmethod
    def name(self) -> str:
        """Unique identifier for this language (e.g., 'python', 'go', 'java')."""
        pass
    
    @property
    def display_name(self) -> str:
        """Human-readable name (defaults to capitalized `name`)."""
        return self.name.capitalize()
    
    @property
    def version(self) -> str:
        """Plugin version string."""
        return "0.0.0"
    
    @property
    def description(self) -> str:
        """Short description of the plugin."""
        return f"{self.display_name} language support for semver-dredd"
    
    @abstractmethod
    def generate_snapshot(
        self, 
        path: str, 
        version: str, 
        options: Optional[Dict[str, Any]] = None
    ) -> SnapshotResult:
        """Generate a YAML snapshot of the public API.
        
        Args:
            path: Path to source directory or module
            version: Version string to embed in snapshot
            options: Optional plugin-specific options
            
        Returns:
            SnapshotResult with YAML content or error
        """
        pass
    
    def validate_path(self, path: str) -> Tuple[bool, str]:
        """Validate that the given path is suitable for this plugin.
        
        Args:
            path: Path to validate
            
        Returns:
            (is_valid, error_message_if_invalid)
        """
        p = Path(path)
        if not p.exists():
            return False, f"Path does not exist: {path}"
        return True, ""
    
    def get_parser_resource_path(self) -> Optional[Path]:
        """Return path to bundled parser resources (if any).
        
        Uses importlib.resources for reliable resource location.
        """
        return None
```

#### 1.2 Create Plugin Manager

Create `semverdredd/plugin_manager.py`:

```python
import sys
from pathlib import Path
from typing import Dict, Optional, List
from importlib.metadata import entry_points
import logging

from semverdredd.plugin_base import LanguagePlugin

logger = logging.getLogger(__name__)

ENTRY_POINT_GROUP = "semver_dredd.plugins"
USER_PLUGIN_DIR_NAME = ".semver-dredd/plugins"

class PluginManager:
    """Manages discovery, loading, and access to language plugins."""
    
    def __init__(self, user_plugin_dir: Optional[Path] = None):
        self._registry: Dict[str, LanguagePlugin] = {}
        self._loaded = False
        
        # User-level plugin directory
        if user_plugin_dir:
            self.user_plugin_dir = user_plugin_dir
        else:
            self.user_plugin_dir = Path.home() / USER_PLUGIN_DIR_NAME
    
    def ensure_plugin_dir(self) -> Path:
        """Ensure user plugin directory exists and return its path."""
        self.user_plugin_dir.mkdir(parents=True, exist_ok=True)
        return self.user_plugin_dir
    
    def load_plugins(self, force: bool = False) -> None:
        """Discover and load all available plugins.
        
        Args:
            force: If True, reload even if already loaded
        """
        if self._loaded and not force:
            return
        
        # Add user plugin dir to sys.path for discovery
        plugin_dir_str = str(self.user_plugin_dir)
        if self.user_plugin_dir.exists() and plugin_dir_str not in sys.path:
            sys.path.insert(0, plugin_dir_str)
        
        # Discover via entry points
        discovered = entry_points(group=ENTRY_POINT_GROUP)
        
        for ep in discovered:
            try:
                plugin_cls = ep.load()
                plugin = plugin_cls()
                self.register(plugin)
                logger.debug(f"Loaded plugin: {ep.name} -> {plugin.name}")
            except Exception as e:
                logger.warning(f"Failed to load plugin '{ep.name}': {e}")
        
        self._loaded = True
    
    def register(self, plugin: LanguagePlugin) -> None:
        """Register a plugin instance.
        
        Args:
            plugin: Plugin instance to register
        """
        name = plugin.name.lower()
        if name in self._registry:
            logger.info(f"Replacing existing plugin: {name}")
        self._registry[name] = plugin
    
    def unregister(self, name: str) -> bool:
        """Unregister a plugin by name.
        
        Args:
            name: Plugin name to remove
            
        Returns:
            True if plugin was removed, False if not found
        """
        name = name.lower()
        if name in self._registry:
            del self._registry[name]
            return True
        return False
    
    def get(self, name: str) -> Optional[LanguagePlugin]:
        """Get a plugin by name.
        
        Args:
            name: Language name (case-insensitive)
            
        Returns:
            Plugin instance or None
        """
        self.load_plugins()
        return self._registry.get(name.lower())
    
    def list_plugins(self) -> List[LanguagePlugin]:
        """List all registered plugins.
        
        Returns:
            List of plugin instances
        """
        self.load_plugins()
        return list(self._registry.values())
    
    def list_names(self) -> List[str]:
        """List names of all registered plugins.
        
        Returns:
            List of plugin names
        """
        self.load_plugins()
        return list(self._registry.keys())
    
    def is_loaded(self) -> bool:
        """Check if plugins have been loaded."""
        return self._loaded


# Global singleton instance
_manager: Optional[PluginManager] = None

def get_plugin_manager() -> PluginManager:
    """Get the global plugin manager instance."""
    global _manager
    if _manager is None:
        _manager = PluginManager()
    return _manager

def get_plugin(name: str) -> Optional[LanguagePlugin]:
    """Convenience function to get a plugin by name."""
    return get_plugin_manager().get(name)

def list_plugins() -> List[LanguagePlugin]:
    """Convenience function to list all plugins."""
    return get_plugin_manager().list_plugins()
```

#### 1.3 Update pyproject.toml for Entry Points

```toml
[project.entry-points."semver_dredd.plugins"]
# Built-in plugins (during transition period)
# These will be removed once plugins are separate packages
# Note: project.name (distribution) should follow the naming scheme: language-<lang_version>-<plugin_source>-<plugin_version>
# Example distribution names: "python-3.10-core-1.0.0", "go-1.20-gogen-1.0.0", "java-17-acme-1.0.0"
python = "semver_dredd_python:PythonPlugin"
go = "semver_dredd_go.plugin:GoPlugin"
java = "semver_dredd_java:JavaPlugin"
```

---

### Phase 2: Python Plugin Extraction

#### 2.1 Create Python Plugin Package

The Python plugin extracts the existing `ModuleAPI.from_module()` logic into a plugin.

**File:** `semver_dredd_python/plugin.py`

```python
import importlib
import sys
from pathlib import Path
from typing import Optional, Dict, Any

from semverdredd.plugin_base import LanguagePlugin, SnapshotResult

class PythonPlugin(LanguagePlugin):
    """Python language support plugin for semver-dredd."""
    
    @property
    def name(self) -> str:
        return "python"
    
    @property
    def version(self) -> str:
        return "1.0.0"
    
    @property
    def description(self) -> str:
        return "Analyzes Python modules using introspection (inspect module)"
    
    def validate_path(self, path: str) -> tuple[bool, str]:
        """Validate Python module path."""
        p = Path(path)
        
        # Check if it's a directory with __init__.py
        if p.is_dir():
            init_file = p / "__init__.py"
            if not init_file.exists():
                return False, f"Directory '{path}' is not a Python package (no __init__.py)"
            return True, ""
        
        # Check if it's a .py file
        if p.is_file() and p.suffix == ".py":
            return True, ""
        
        # Try as importable module name
        # This is valid even if path doesn't exist as file
        if "." in path or path.isidentifier():
            return True, ""
        
        return False, f"'{path}' is not a valid Python module path or name"
    
    def generate_snapshot(
        self, 
        path: str, 
        version: str, 
        options: Optional[Dict[str, Any]] = None
    ) -> SnapshotResult:
        """Generate snapshot by importing and introspecting Python module."""
        import yaml
        
        try:
            module = self._import_module(path)
        except ImportError as e:
            return SnapshotResult(
                success=False,
                yaml_content="",
                error_message=f"Failed to import module: {e}"
            )
        except Exception as e:
            return SnapshotResult(
                success=False,
                yaml_content="",
                error_message=f"Error loading module: {e}"
            )
        
        # Use existing ModuleAPI extraction
        from semverdredd import ModuleAPI
        from semverdredd.snapshot import APISnapshot
        
        try:
            snapshot = APISnapshot.from_module(module, version)
            yaml_content = yaml.dump(
                snapshot.to_dict(), 
                default_flow_style=False, 
                sort_keys=False
            )
            return SnapshotResult(success=True, yaml_content=yaml_content)
        except Exception as e:
            return SnapshotResult(
                success=False,
                yaml_content="",
                error_message=f"Failed to generate snapshot: {e}"
            )
    
    def _import_module(self, module_path: str):
        """Import a module from path or name."""
        path = Path(module_path)
        
        if path.exists():
            if path.is_dir():
                module_name = path.name
                sys.path.insert(0, str(path.parent))
            else:
                module_name = path.stem
                sys.path.insert(0, str(path.parent))
            
            try:
                return importlib.import_module(module_name)
            finally:
                sys.path.pop(0)
        else:
            return importlib.import_module(module_path)
```

**File:** `semver_dredd_python/pyproject.toml`

```toml
[project]
name = "python-3.10-core-1.0.0"  # distribution name following the recommended scheme
version = "1.0.0"
description = "Python language plugin for semver-dredd"
requires-python = ">=3.10"
dependencies = [
    "semver-dredd>=0.2.0",
    "PyYAML>=6.0",
]

[project.entry-points."semver_dredd.plugins"]
python = "semver_dredd_python.plugin:PythonPlugin"

[build-system]
requires = ["setuptools>=61.0"]
build-backend = "setuptools.build_meta"
```

---

### Phase 3: Go Plugin Extraction

#### 3.1 Create Go Plugin Package

**File:** `semver_dredd_go/plugin.py`

```python
import subprocess
from pathlib import Path
from typing import Optional, Dict, Any

from semverdredd.plugin_base import LanguagePlugin, SnapshotResult

# Use importlib.resources for Python 3.9+
try:
    from importlib.resources import files, as_file
except ImportError:
    from importlib_resources import files, as_file


class GoPlugin(LanguagePlugin):
    """Go language support plugin for semver-dredd."""
    
    @property
    def name(self) -> str:
        return "go"
    
    @property
    def version(self) -> str:
        return "1.0.0"
    
    @property
    def description(self) -> str:
        return "Analyzes Go packages using AST parsing"
    
    def validate_path(self, path: str) -> tuple[bool, str]:
        """Validate Go module path."""
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
        """Get path to bundled Go parser source."""
        try:
            # This resolves to the installed package location
            parser_pkg = files("semver_dredd_go").joinpath("parser")
            return Path(str(parser_pkg))
        except Exception:
            return None
    
    def generate_snapshot(
        self, 
        path: str, 
        version: str, 
        options: Optional[Dict[str, Any]] = None
    ) -> SnapshotResult:
        """Generate snapshot using bundled Go parser."""
        
        parser_path = self.get_parser_resource_path()
        if parser_path is None or not parser_path.exists():
            return SnapshotResult(
                success=False,
                yaml_content="",
                error_message=(
                    "Go parser not found. Ensure the Go plugin distribution "
                    "(name format: go-<lang_version>-<plugin_version>) is installed."
                )
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
                success=False,
                yaml_content="",
                error_message="'go' executable not found. Please install Go."
            )
        except subprocess.CalledProcessError as e:
            return SnapshotResult(
                success=False,
                yaml_content="",
                error_message=f"Go check failed: {e.stderr.decode() if e.stderr else str(e)}"
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
                cwd=str(parser_path)
            )
            return SnapshotResult(success=True, yaml_content=result.stdout)
        except subprocess.CalledProcessError as e:
            return SnapshotResult(
                success=False,
                yaml_content="",
                error_message=f"Go parser failed: {e.stderr or str(e)}"
            )
```

**File:** `semver_dredd_go/pyproject.toml`

```toml
[project]
name = "go-1.20-gogen-1.0.0"  # distribution name following the recommended scheme
version = "1.0.0"
description = "Go language plugin for semver-dredd"
requires-python = ">=3.10"
dependencies = [
    "semver-dredd>=0.2.0",
]

[project.entry-points."semver_dredd.plugins"]
go = "semver_dredd_go.plugin:GoPlugin"

[build-system]
requires = ["setuptools>=61.0"]
build-backend = "setuptools.build_meta"

[tool.setuptools.package-data]
semver_dredd_go = [
    "parser/*.go",
    "parser/go.mod",
    "parser/go.sum",
]
```

---

### Phase 4: Java Plugin Extraction

#### 4.1 Create Java Plugin Package

**File:** `semver_dredd_java/plugin.py`

```python
import subprocess
import tempfile
from pathlib import Path
from typing import Optional, Dict, Any

from semverdredd.plugin_base import LanguagePlugin, SnapshotResult

try:
    from importlib.resources import files
except ImportError:
    from importlib_resources import files


class JavaPlugin(LanguagePlugin):
    """Java language support plugin for semver-dredd."""
    
    @property
    def name(self) -> str:
        return "java"
    
    @property
    def version(self) -> str:
        return "1.0.0"
    
    @property
    def description(self) -> str:
        return "Analyzes Java packages using reflection"
    
    def validate_path(self, path: str) -> tuple[bool, str]:
        """Validate Java source path."""
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
        """Get path to bundled Java parser."""
        try:
            parser_pkg = files("semver_dredd_java").joinpath("parser")
            return Path(str(parser_pkg))
        except Exception:
            return None
    
    def _get_jar_path(self) -> Optional[Path]:
        """Get path to snakeyaml JAR."""
        parser_path = self.get_parser_resource_path()
        if parser_path:
            jar = parser_path / "lib" / "snakeyaml-2.2.jar"
            if jar.exists():
                return jar
        return None
    
    def _compile_parser(self, parser_path: Path, jar_path: Path) -> tuple[bool, str]:
        """Compile the Java parser if needed."""
        src = parser_path / "main.java"
        cls = parser_path / "main.class"
        
        # Skip if already compiled and up-to-date
        if cls.exists() and cls.stat().st_mtime >= src.stat().st_mtime:
            return True, ""
        
        cmd = ["javac", "-cp", str(jar_path), str(src)]
        try:
            subprocess.run(cmd, check=True, capture_output=True, text=True)
            return True, ""
        except FileNotFoundError:
            return False, "'javac' not found. Please install JDK."
        except subprocess.CalledProcessError as e:
            return False, f"Compilation failed: {e.stderr or str(e)}"
    
    def generate_snapshot(
        self, 
        path: str, 
        version: str, 
        options: Optional[Dict[str, Any]] = None
    ) -> SnapshotResult:
        """Generate snapshot using bundled Java parser."""
        
        parser_path = self.get_parser_resource_path()
        if parser_path is None or not parser_path.exists():
            return SnapshotResult(
                success=False,
                yaml_content="",
                error_message=(
                    "Java parser not found. Ensure the Java plugin distribution "
                    "(name format: java-<lang_version>-<plugin_version>) is installed."
                )
            )
        
        jar_path = self._get_jar_path()
        if jar_path is None:
            return SnapshotResult(
                success=False,
                yaml_content="",
                error_message="snakeyaml JAR not found. Plugin may be corrupted."
            )
        
        # Compile if needed
        ok, err = self._compile_parser(parser_path, jar_path)
        if not ok:
            return SnapshotResult(success=False, yaml_content="", error_message=err)
        
        # Run parser
        cmd = [
            "java", "-cp", f"{jar_path}:{parser_path}", "main",
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
            return SnapshotResult(success=True, yaml_content=result.stdout)
        except FileNotFoundError:
            return SnapshotResult(
                success=False,
                yaml_content="",
                error_message="'java' executable not found. Please install JRE/JDK."
            )
        except subprocess.CalledProcessError as e:
            return SnapshotResult(
                success=False,
                yaml_content="",
                error_message=f"Java parser failed: {e.stderr or str(e)}"
            )
```

**File:** `semver_dredd_java/pyproject.toml`

```toml
[project]
name = "java-17-acme-1.0.0"  # distribution name following the recommended scheme
version = "1.0.0"
description = "Java language plugin for semver-dredd"
requires-python = ">=3.10"
dependencies = [
    "semver-dredd>=0.2.0",
]

[project.entry-points."semver_dredd.plugins"]
java = "semver_dredd_java.plugin:JavaPlugin"

[build-system]
requires = ["setuptools>=61.0"]
build-backend = "setuptools.build_meta"

[tool.setuptools.package-data]
semver_dredd_java = [
    "parser/*.java",
    "parser/lib/*.jar",
]
```

---

### Phase 5: CLI Plugin Management Commands

#### 5.1 Add Plugin Commands

**File:** `cli/commands/plugin.py`

```python
import subprocess
import sys
from pathlib import Path
from argparse import Namespace

from semverdredd.plugin_manager import get_plugin_manager

EXIT_OK = 0
EXIT_ERROR = 1


def cmd_plugin_list(args: Namespace) -> int:
    """List installed plugins."""
    manager = get_plugin_manager()
    plugins = manager.list_plugins()
    
    if not plugins:
        print("No plugins installed.")
        return EXIT_OK
    
    print("Installed plugins:")
    print("-" * 50)
    for plugin in sorted(plugins, key=lambda p: p.name):
        print(f"  {plugin.name:12} v{plugin.version:10} - {plugin.description}")
    
    print("-" * 50)
    print(f"Plugin directory: {manager.user_plugin_dir}")
    return EXIT_OK


def cmd_plugin_install(args: Namespace) -> int:
    """Install a plugin package."""
    manager = get_plugin_manager()
    target_dir = manager.ensure_plugin_dir()
    
    source = args.source
    
    # Use pip to install into the plugin directory
    cmd = [
        sys.executable, "-m", "pip", "install",
        "--target", str(target_dir),
        "--upgrade",
        source
    ]
    
    print(f"Installing plugin from: {source}")
    print(f"Target directory: {target_dir}")
    
    result = subprocess.run(cmd)
    
    if result.returncode == 0:
        # Force reload plugins
        manager.load_plugins(force=True)
        print("\nPlugin installed successfully.")
        print("Run 'semver-dredd plugin list' to see installed plugins.")
        return EXIT_OK
    else:
        print("\nPlugin installation failed.", file=sys.stderr)
        return EXIT_ERROR


def cmd_plugin_remove(args: Namespace) -> int:
    """Remove an installed plugin."""
    manager = get_plugin_manager()
    target_dir = manager.user_plugin_dir
    
    plugin_name = args.name.lower()
    
    # Map plugin name to package name
    # Convention: plugin "go" -> package "semver_dredd_go"
    package_name = f"semver_dredd_{plugin_name}"
    
    cmd = [
        sys.executable, "-m", "pip", "uninstall",
        "--yes",
        package_name
    ]
    
    # Note: pip uninstall doesn't support --target, so we need to
    # handle user-installed plugins differently
    
    package_dir = target_dir / package_name
    if package_dir.exists():
        import shutil
        shutil.rmtree(package_dir)
        print(f"Removed plugin directory: {package_dir}")
        
        # Also remove .dist-info
        for dist_info in target_dir.glob(f"{package_name.replace('_', '-')}*.dist-info"):
            shutil.rmtree(dist_info)
        
        manager.unregister(plugin_name)
        print(f"Plugin '{plugin_name}' removed successfully.")
        return EXIT_OK
    else:
        print(f"Plugin '{plugin_name}' not found in user directory.", file=sys.stderr)
        print("Note: System-installed plugins cannot be removed with this command.")
        return EXIT_ERROR


def cmd_plugin_info(args: Namespace) -> int:
    """Show detailed information about a plugin."""
    manager = get_plugin_manager()
    plugin = manager.get(args.name)
    
    if plugin is None:
        print(f"Plugin '{args.name}' not found.", file=sys.stderr)
        return EXIT_ERROR
    
    print(f"Plugin: {plugin.name}")
    print(f"Display Name: {plugin.display_name}")
    print(f"Version: {plugin.version}")
    print(f"Description: {plugin.description}")
    
    parser_path = plugin.get_parser_resource_path()
    if parser_path:
        print(f"Parser Path: {parser_path}")
    
    return EXIT_OK
```

#### 5.2 Update CLI Main

Add to `cli/__init__.py`:

```python
# Add plugin subcommand group
plugin_parser = subparsers.add_parser(
    "plugin",
    help="Manage language plugins",
)
plugin_subparsers = plugin_parser.add_subparsers(dest="plugin_command", required=True)

# plugin list
plugin_list_parser = plugin_subparsers.add_parser(
    "list",
    help="List installed plugins",
)
plugin_list_parser.set_defaults(func=cmd_plugin_list)

# plugin install
plugin_install_parser = plugin_subparsers.add_parser(
    "install",
    help="Install a plugin package",
)
plugin_install_parser.add_argument(
    "source",
    help="Package name (PyPI) or path to plugin package",
)
plugin_install_parser.set_defaults(func=cmd_plugin_install)

# plugin remove
plugin_remove_parser = plugin_subparsers.add_parser(
    "remove",
    help="Remove an installed plugin",
)
plugin_remove_parser.add_argument(
    "name",
    help="Plugin name to remove (e.g., 'go', 'java')",
)
plugin_remove_parser.set_defaults(func=cmd_plugin_remove)

# plugin info
plugin_info_parser = plugin_subparsers.add_parser(
    "info",
    help="Show plugin details",
)
plugin_info_parser.add_argument(
    "name",
    help="Plugin name",
)
plugin_info_parser.set_defaults(func=cmd_plugin_info)
```

---

### Phase 6: Programmatic API Update

#### 6.1 Add Plugin Registry to Programmatic API

**File:** `semverdredd/__init__.py` (additions)

```python
# Plugin system exports
from semverdredd.plugin_base import LanguagePlugin, SnapshotResult
from semverdredd.plugin_manager import (
    PluginManager,
    get_plugin_manager,
    get_plugin,
    list_plugins,
)

# Update __all__
__all__ = [
    # ... existing exports ...
    
    # Plugin system
    "LanguagePlugin",
    "SnapshotResult", 
    "PluginManager",
    "get_plugin_manager",
    "get_plugin",
    "list_plugins",
]
```

#### 6.2 Custom Plugin Registry for Programmatic Use

```python
# Example: Programmatic API with custom plugins
from semverdredd import PluginManager, LanguagePlugin

# Create isolated manager (doesn't affect global state)
manager = PluginManager(user_plugin_dir=None)  # No user dir scanning

# Register custom plugin
class MyCustomPlugin(LanguagePlugin):
    @property
    def name(self) -> str:
        return "rust"
    
    def generate_snapshot(self, path, version, options=None):
        # Custom implementation
        ...

manager.register(MyCustomPlugin())

# Use it
plugin = manager.get("rust")
result = plugin.generate_snapshot("./my-crate", "1.0.0")
```

---

### Phase 7: Migration and Cleanup

#### 7.1 Migration Steps

1. **Create separate plugin packages** in a `plugins/` directory for predefined (official) plugins, or as separate repositories for third-party plugins. The project's `plugins/` folder will hold the official, pre-bundled distributions using the vendor-aware naming scheme `language-<lang_version>-<plugin_source>-<plugin_version>[-extras]`.
2. **Move parser source files** from `parser/` to respective plugin packages
3. **Update core package** to not include parsers
4. **Update documentation** with plugin installation instructions
5. **Add integration tests** for plugin discovery

---

## Final Directory Structure

```
semver-dredd/                          # Core (this repo after refactor)
├── pyproject.toml
├── semverdredd/
│   ├── __init__.py
│   ├── plugin_base.py                 # NEW
│   ├── plugin_manager.py              # NEW
│   ├── diff.py
│   ├── xldiff.py
│   ├── snapshot.py
│   ├── snapshot_io.py
│   ├── version.py
│   └── result.py
├── cli/
│   ├── __init__.py
│   ├── config.py
│   └── commands/
│       └── plugin.py                  # NEW
└── tests/

plugins/                               # Predefined/official plugins (in-repo)
├── python-3.10-core-1.0.0/
│   ├── pyproject.toml
│   └── semver_dredd_python/
│       ├── __init__.py
│       └── plugin.py
├── go-1.20-gogen-1.0.0/
│   ├── pyproject.toml
│   └── semver_dredd_go/
│       ├── __init__.py
│       ├── plugin.py
│       └── parser/
│           ├── go.mod
│           ├── go.sum
│           └── main.go
└── java-17-acme-1.0.0/
    ├── pyproject.toml
    └── semver_dredd_java/
        ├── __init__.py
        ├── plugin.py
        └── parser/
            ├── main.java
            └── lib/
                └── snakeyaml-2.2.jar

```

---

## Updated meta-package example

**File:** `semver-dredd-all/pyproject.toml`

```toml
[project]
name = "semver-dredd-all"  # meta-package; may also be replaced by a collection with explicit plugin names
version = "1.0.0"
description = "Semver-dredd with all official language plugins"
dependencies = [
    "semver-dredd>=0.2.0",
    "python-3.10-core-1.0.0>=1.0.0",
    "go-1.20-gogen-1.0.0>=1.0.0",
    "java-17-acme-1.0.0>=1.0.0",
]
```

---

## Usage Examples After Refactor

### CLI Usage

```bash
# List available plugins
semver-dredd plugin list

# Install Go plugin (vendor-aware package name)
semver-dredd plugin install go-1.20-gogen-1.0.0

# Install from local path (development)
semver-dredd plugin install ./plugins/go-1.20-gogen-1.0.0

# Remove a plugin (use language id)
semver-dredd plugin remove go

# Use a plugin
semver-dredd init --lang go ./mypackage
semver-dredd status --lang python ./mylib
```

### Programmatic API

```python
from semverdredd import get_plugin, list_plugins, PluginManager

# Use global registry (includes user-installed plugins)
go_plugin = get_plugin("go")
result = go_plugin.generate_snapshot("./mypackage", "1.0.0")

# List all available plugins
for plugin in list_plugins():
    print(f"{plugin.name}: {plugin.description}")

# Custom isolated registry
manager = PluginManager()
manager.load_plugins()
python_plugin = manager.get("python")
```

---

## Brief Summary

| Phase | Description                |
|-------|----------------------------|
| 1     | Core Plugin Infrastructure |
| 2     | Python Plugin Extraction   |
| 3     | Go Plugin Extraction       |
| 4     | Java Plugin Extraction     |
| 5     | CLI Plugin Management      |
| 6     | Programmatic API Update    |
| 7     | Migration and Cleanup      |

---

## Open Questions

1. **Monorepo vs Multi-repo**: Should plugins live in `plugins/` subdirectory or separate repositories?
2. **Plugin versioning**: Should plugins declare compatible semver-dredd core versions?
3. **Pre-compiled binaries**: Should Go/Java plugins optionally include pre-compiled binaries for common platforms?
4. **Plugin marketplace**: Future consideration for a plugin registry/index?

---

## References

- [Python Entry Points Specification](https://packaging.python.org/en/latest/specifications/entry-points/)
- [importlib.resources documentation](https://docs.python.org/3/library/importlib.resources.html)
- [pluggy - plugin framework used by pytest](https://pluggy.readthedocs.io/)
- [setuptools package data](https://setuptools.pypa.io/en/latest/userguide/datafiles.html)

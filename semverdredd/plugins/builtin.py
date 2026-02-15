"""Built-in plugin registration.

In editable/dev installs, entry point metadata may not be present.
To keep the CLI usable without requiring packaging steps, we always
register a small set of built-in plugins.

This doesn't prevent entry-point discovery; discovered plugins can
still override these defaults.
"""

from __future__ import annotations

from semverdredd.plugins.go import GoPlugin
from semverdredd.plugins.java import JavaPlugin
from semverdredd.plugins.python import PythonPlugin


def register_builtin_plugins(manager) -> None:
    # Import locally to avoid any heavy imports at module import time.
    manager.register(PythonPlugin(), origin="builtin")
    manager.register(GoPlugin(), origin="builtin")
    manager.register(JavaPlugin(), origin="builtin")

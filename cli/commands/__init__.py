"""CLI command implementations for semver-dredd."""

from cli.commands.bake import cmd_bake
from cli.commands.bump import cmd_bump
from cli.commands.compare import cmd_compare
from cli.commands.init import cmd_init
from cli.commands.patch import cmd_patch
from cli.commands.plugin import (
    cmd_plugin_info,
    cmd_plugin_install,
    cmd_plugin_list,
    cmd_plugin_remove,
)
from cli.commands.snapshot import cmd_snapshot
from cli.commands.status import cmd_status
from cli.commands.template import cmd_template

__all__ = [
    "cmd_bake",
    "cmd_bump",
    "cmd_compare",
    "cmd_init",
    "cmd_patch",
    "cmd_plugin_info",
    "cmd_plugin_install",
    "cmd_plugin_list",
    "cmd_plugin_remove",
    "cmd_snapshot",
    "cmd_status",
    "cmd_template",
]

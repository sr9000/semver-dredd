import pytest

from semverdredd.plugin_manager import PluginManager
from semverdredd.plugin_base import LanguagePlugin, SnapshotResult


class MockPlugin(LanguagePlugin):
    """A minimal plugin for testing."""

    @property
    def name(self) -> str:
        return "mock"

    @property
    def version(self) -> str:
        return "0.1.0"

    def generate_snapshot(self, path: str, version: str, options=None) -> SnapshotResult:
        return SnapshotResult(True, f"mock: {path} {version}")


def test_plugin_manager_can_register_and_retrieve():
    """Test that PluginManager can register and retrieve plugins."""
    mgr = PluginManager()
    plugin = MockPlugin()

    mgr.register(plugin)

    p = mgr.get("mock")
    assert p is not None
    assert p.name == "mock"
    assert p.version == "0.1.0"


def test_plugin_manager_list_plugins():
    """Test that PluginManager can list registered plugins."""
    mgr = PluginManager()
    mgr.register(MockPlugin())

    plugins = mgr.list_plugins()
    names = [p.name for p in plugins]

    assert "mock" in names


def test_plugin_manager_unregister():
    """Test that PluginManager can unregister plugins."""
    mgr = PluginManager()
    mgr.register(MockPlugin())

    assert mgr.get("mock") is not None
    assert mgr.unregister("mock") is True
    assert mgr.get("mock") is None


def test_plugin_manager_case_insensitive():
    """Test that plugin names are case-insensitive."""
    mgr = PluginManager()
    mgr.register(MockPlugin())

    assert mgr.get("MOCK") is not None
    assert mgr.get("Mock") is not None
    assert mgr.get("mock") is not None


class RecordingPlugin(LanguagePlugin):
    """A stub plugin that records the options it receives."""

    def __init__(self):
        self.seen_options = []

    @property
    def name(self) -> str:
        return "recording"

    def validate_path(self, path: str):
        return True, ""

    def generate_snapshot(self, path: str, version: str, options=None) -> SnapshotResult:
        self.seen_options.append(options)
        return SnapshotResult(True, f"version: '{version}'\napi: {{}}\n")


def test_options_reach_generate_snapshot_via_cli_helper():
    """include/exclude/plugin_options flow through _generate_snapshot_yaml."""
    from cli.utils import _generate_snapshot_yaml
    from semverdredd.plugin_manager import get_plugin_manager

    plugin = RecordingPlugin()
    mgr = get_plugin_manager()
    mgr.register(plugin)
    try:
        extra = {
            "include": ["pkg.core"],
            "exclude": ["pkg.core._private"],
            "plugin_options": {"timeout_seconds": 30},
        }
        exit_code, yaml_str = _generate_snapshot_yaml(
            "recording", "some/path", "1.2.3", False, extra_options=extra
        )
        assert exit_code == 0
        assert len(plugin.seen_options) == 1
        opts = plugin.seen_options[0]
        assert opts["include"] == ["pkg.core"]
        assert opts["exclude"] == ["pkg.core._private"]
        assert opts["plugin_options"] == {"timeout_seconds": 30}
        # CLI-internal keys still present
        assert opts["use_color"] is False
    finally:
        mgr.unregister("recording")


def test_options_reach_generate_snapshot_via_programmatic_api():
    """semverdredd.compare forwards options to the plugin."""
    from semverdredd import compare
    from semverdredd.plugin_manager import get_plugin_manager

    plugin = RecordingPlugin()
    mgr = get_plugin_manager()
    mgr.register(plugin)
    try:
        options = {"include": ["pkg"], "plugin_options": {"x": 1}}
        result = compare("old/path", "new/path", plugin="recording", options=options)
        assert result is not None
        assert len(plugin.seen_options) == 2
        for opts in plugin.seen_options:
            assert opts == options
    finally:
        mgr.unregister("recording")


def test_plugin_without_options_still_works():
    """Plugins ignoring options keys behave exactly as before."""
    from cli.utils import _generate_snapshot_yaml
    from semverdredd.plugin_manager import get_plugin_manager

    plugin = MockPlugin()
    mgr = get_plugin_manager()
    mgr.register(plugin)
    try:
        exit_code, yaml_str = _generate_snapshot_yaml(
            "mock", ".", "1.0.0", False, extra_options=None
        )
        assert exit_code == 0
        assert "1.0.0" in yaml_str
    finally:
        mgr.unregister("mock")

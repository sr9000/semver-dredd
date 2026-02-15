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

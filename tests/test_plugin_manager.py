import pytest

from semverdredd.plugin_manager import PluginManager
from semverdredd.plugin_base import LanguagePlugin, SnapshotResult
from semver_dredd_go.plugin import GoPlugin
from semver_dredd_java.plugin import JavaPlugin
from semver_dredd_javaparser.plugin import JavaParserPlugin
from semver_dredd_python.plugin import PythonPlugin


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


class MetadataPlugin(LanguagePlugin):
    @property
    def name(self) -> str:
        return "metadata"

    @property
    def metadata(self) -> dict:
        return {
            "scope": {"syntax": "dotted-module"},
            "features": ["metadata", "machine_readable_inventory"],
            "plugin_options": ["timeout_seconds"],
        }

    def generate_snapshot(self, path: str, version: str, options=None) -> SnapshotResult:
        return SnapshotResult(True, "metadata")


class HaveOnlyPlugin(LanguagePlugin):
    @property
    def name(self) -> str:
        return "have-only"

    def have(self, feature: str) -> bool:
        return feature == "metadata"

    def generate_snapshot(self, path: str, version: str, options=None) -> SnapshotResult:
        return SnapshotResult(True, "have-only")


class InvalidMetadataPlugin(LanguagePlugin):
    @property
    def name(self) -> str:
        return "invalid-metadata"

    @property
    def metadata(self):
        return ["not", "a", "dict"]

    def generate_snapshot(self, path: str, version: str, options=None) -> SnapshotResult:
        return SnapshotResult(True, "invalid")


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


def test_plugin_manager_describe_plugin_defaults():
    mgr = PluginManager()
    mgr.register(MockPlugin())

    metadata = mgr.describe_plugin("mock")

    assert metadata is not None
    assert metadata["name"] == "mock"
    assert metadata["display_name"] == "Mock"
    assert metadata["version"] == "0.1.0"
    assert metadata["origin"] == "manual"
    assert metadata["features"] == []
    assert metadata["snapshot_format"] == {
        "class": None,
        "snapshot_type_id": None,
    }


def test_plugin_manager_describe_plugin_uses_structured_metadata():
    mgr = PluginManager()
    mgr.register(MetadataPlugin())

    metadata = mgr.describe_plugin("metadata")

    assert metadata is not None
    assert metadata["scope"] == {"syntax": "dotted-module"}
    assert metadata["plugin_options"] == ["timeout_seconds"]
    assert metadata["features"] == ["machine_readable_inventory", "metadata"]


def test_plugin_manager_describe_plugin_falls_back_to_have():
    mgr = PluginManager()
    mgr.register(HaveOnlyPlugin())

    metadata = mgr.describe_plugin("have-only")

    assert metadata is not None
    assert metadata["features"] == ["metadata"]


def test_plugin_manager_invalid_metadata_is_ignored(caplog):
    import logging

    mgr = PluginManager()
    mgr.register(InvalidMetadataPlugin())

    with caplog.at_level(logging.WARNING, logger="semverdredd.plugin_manager"):
        metadata = mgr.describe_plugin("invalid-metadata")

    assert metadata is not None
    assert metadata["features"] == []
    assert any("non-dict metadata" in rec.getMessage().lower() for rec in caplog.records)


@pytest.mark.parametrize(
    ("plugin", "expected_name", "expected_scope_syntax", "required_tool"),
    [
        (PythonPlugin(), "python", "python dotted module/package names", None),
        (GoPlugin(), "go", "root-relative Go import paths", "go>=1.20"),
        (JavaPlugin(), "java", "Java package prefixes", "java>=1.8"),
        (JavaParserPlugin(), "javaparser", "Java package prefixes", "java>=1.8"),
    ],
)
def test_official_plugins_expose_inventory_metadata(
    plugin, expected_name, expected_scope_syntax, required_tool
):
    mgr = PluginManager()
    mgr.register(plugin)

    metadata = mgr.describe_plugin(expected_name)

    assert metadata is not None
    assert metadata["name"] == expected_name
    assert metadata["scope"]["syntax"] == expected_scope_syntax
    assert metadata["plugin_options"] == []
    assert metadata["features"] == ["machine_readable_inventory", "metadata"]
    if required_tool is None:
        assert metadata["runtime_requirements"]["external_tools"] == []
    else:
        assert required_tool in metadata["runtime_requirements"]["external_tools"]
    assert metadata["snapshot_format"]["class"] is not None
    assert metadata["snapshot_format"]["snapshot_type_id"] is not None


# ---------------------------------------------------------------------------
# Plugin lifecycle hardening: conflicts + manifest-based removal
# ---------------------------------------------------------------------------


class AnotherMockPlugin(LanguagePlugin):
    """A different class that claims the same plugin name as MockPlugin."""

    @property
    def name(self) -> str:
        return "mock"

    def generate_snapshot(self, path: str, version: str, options=None) -> SnapshotResult:
        return SnapshotResult(True, "other")


def test_register_name_conflict_warns(caplog):
    """Registering a different class under an existing name warns loudly."""
    import logging

    mgr = PluginManager()
    mgr.register(MockPlugin())
    with caplog.at_level(logging.WARNING, logger="semverdredd.plugin_manager"):
        mgr.register(AnotherMockPlugin())
    assert any("conflict" in rec.getMessage().lower() for rec in caplog.records)


def test_register_same_class_is_quiet(caplog):
    """Re-registering the same plugin class does not warn."""
    import logging

    mgr = PluginManager()
    mgr.register(MockPlugin())
    with caplog.at_level(logging.WARNING, logger="semverdredd.plugin_manager"):
        mgr.register(MockPlugin())
    assert not [r for r in caplog.records if r.levelno >= logging.WARNING]


def test_duplicate_snapshot_type_id_warns(caplog, tmp_path):
    """Two plugins claiming the same SNAPSHOT_TYPE_ID produce a warning."""
    import logging

    class SnapFormatA:
        SNAPSHOT_TYPE_ID = "11111111-2222-3333-4444-555555555555"

    class SnapFormatB:
        SNAPSHOT_TYPE_ID = "11111111-2222-3333-4444-555555555555"

    class PluginA(LanguagePlugin):
        @property
        def name(self):
            return "snap-a"

        @property
        def snapshot_format_class(self):
            return SnapFormatA

        def generate_snapshot(self, path, version, options=None):
            return SnapshotResult(True, "")

    class PluginB(LanguagePlugin):
        @property
        def name(self):
            return "snap-b"

        @property
        def snapshot_format_class(self):
            return SnapFormatB

        def generate_snapshot(self, path, version, options=None):
            return SnapshotResult(True, "")

    from semverdredd.registry import default_registry

    mgr = PluginManager(user_plugin_dir=tmp_path / "no-plugins")
    mgr.register(PluginA())
    mgr.register(PluginB())
    try:
        with caplog.at_level(logging.WARNING, logger="semverdredd.plugin_manager"):
            mgr.load_plugins(force=True)
        assert any(
            "snapshot type conflict" in rec.getMessage().lower()
            for rec in caplog.records
        )
    finally:
        default_registry.unregister(SnapFormatA.SNAPSHOT_TYPE_ID)


class TestDiscoveryPrecedence:
    """Entry points are preferred; the builtin list is only a fallback."""

    def test_entry_points_win_when_installed(self, tmp_path):
        """With plugins pip-installed, discovery uses entry points."""
        mgr = PluginManager(user_plugin_dir=tmp_path / "no-plugins")
        mgr.load_plugins()
        infos = {i.name: i for i in mgr.list_plugins()}
        # The test environment installs the bundled plugins via pip,
        # so they must be discovered through entry points.
        for name in ("python", "go", "java"):
            assert name in infos, f"plugin '{name}' not discovered"
            assert infos[name].origin == "entry_point"

    def test_builtin_fallback_without_entry_points(self, monkeypatch, tmp_path):
        """Editable/dev installs still discover python/go/java via fallback."""
        import semverdredd.plugin_manager as pm

        monkeypatch.setattr(pm, "entry_points", lambda **kw: [])
        mgr = PluginManager(user_plugin_dir=tmp_path / "no-plugins")
        mgr.load_plugins()
        infos = {i.name: i for i in mgr.list_plugins()}
        for name in ("python", "go", "java"):
            assert name in infos, f"plugin '{name}' not discovered via fallback"
            assert infos[name].origin == "builtin"


class TestPluginManifest:
    """plugin install/remove manifest handling."""

    def _make_manager(self, monkeypatch, tmp_path):
        import semverdredd.plugin_manager as pm

        mgr = PluginManager(user_plugin_dir=tmp_path)
        mgr._loaded = True  # skip discovery in tests
        monkeypatch.setattr(pm, "get_plugin_manager", lambda: mgr)
        return mgr

    def test_manifest_roundtrip(self, tmp_path):
        from cli.commands.plugin import _load_manifest, _record_installation

        _record_installation(
            tmp_path, ["go"], "plugins/go-1.20-dredd", ["semver_dredd_go", "x.dist-info"]
        )
        manifest = _load_manifest(tmp_path)
        assert manifest["go"]["source"] == "plugins/go-1.20-dredd"
        assert manifest["go"]["paths"] == ["semver_dredd_go", "x.dist-info"]

    def test_remove_uses_manifest(self, monkeypatch, tmp_path, capsys):
        import argparse

        from cli.commands.plugin import _record_installation, cmd_plugin_remove

        self._make_manager(monkeypatch, tmp_path)

        # Simulate a previous install
        (tmp_path / "semver_dredd_fake").mkdir()
        (tmp_path / "fake-1.0.dist-info").mkdir()
        (tmp_path / "unrelated_pkg").mkdir()
        _record_installation(
            tmp_path, ["fake"], "fake-src", ["semver_dredd_fake", "fake-1.0.dist-info"]
        )

        args = argparse.Namespace(name="fake", color=False)
        assert cmd_plugin_remove(args) == 0

        assert not (tmp_path / "semver_dredd_fake").exists()
        assert not (tmp_path / "fake-1.0.dist-info").exists()
        # Unrelated content is untouched
        assert (tmp_path / "unrelated_pkg").exists()

        # Manifest entry is gone
        from cli.commands.plugin import _load_manifest

        assert "fake" not in _load_manifest(tmp_path)

    def test_remove_untracked_reports_clearly(self, monkeypatch, tmp_path, capsys):
        import argparse

        from cli.commands.plugin import cmd_plugin_remove

        self._make_manager(monkeypatch, tmp_path)

        args = argparse.Namespace(name="ghost", color=False)
        assert cmd_plugin_remove(args) == 1

        err = capsys.readouterr().err
        assert "not tracked" in err
        assert "Nothing removable" in err

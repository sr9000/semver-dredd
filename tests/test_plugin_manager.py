import pytest

from semverdredd.plugin_manager import PluginManager


@pytest.mark.parametrize(
    "lang,cls_path",
    [
        ("python", "semverdredd.plugins.python.PythonPlugin"),
        ("go", "semverdredd.plugins.go.GoPlugin"),
        ("java", "semverdredd.plugins.java.JavaPlugin"),
    ],
)
def test_builtin_plugins_can_be_registered_manually(lang: str, cls_path: str):
    mod_name, cls_name = cls_path.rsplit(".", 1)
    mod = __import__(mod_name, fromlist=[cls_name])
    cls = getattr(mod, cls_name)

    mgr = PluginManager()
    mgr.register(cls())

    p = mgr.get(lang)
    assert p is not None
    assert p.name == lang

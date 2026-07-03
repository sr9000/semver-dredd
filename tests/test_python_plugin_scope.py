"""Use-case tests for Python plugin include/exclude scope behavior.

Fixtures live under tests/fixtures/python_scope/:
- scopepkg/            -- no __all__, exercises recursive submodule discovery,
                           private-name skipping, and include/exclude filtering.
- scopepkg_all/         -- has __all__, exercises __all__-respecting behavior.
"""

from pathlib import Path

import pytest

from semver_dredd_python.plugin import PythonPlugin, PythonSnapshot

FIXTURES_DIR = Path(__file__).parent / "fixtures" / "python_scope"


def _snapshot_names(plugin: PythonPlugin, path: str, options: dict | None = None) -> dict:
    result = plugin.generate_snapshot(path, "1.0.0", options=options)
    assert result.success, result.error_message
    snap = PythonSnapshot.from_yaml_str(result.yaml_content)
    return {
        "functions": set(snap.functions.keys()),
        "types": set(snap.types.keys()),
    }


class TestNoScope:
    """No include/exclude configured: behavior must match legacy no-scope output."""

    def test_all_module_recursion_default(self):
        plugin = PythonPlugin()
        names = _snapshot_names(plugin, str(FIXTURES_DIR / "scopepkg"))
        # Top-level members from scopepkg/__init__.py (empty) plus recursively
        # discovered public submodules merged in.
        assert "included_func" in names["functions"]
        assert "excluded_func" in names["functions"]
        assert "nested_func" in names["functions"]
        assert "IncludedClass" in names["types"]
        # Private submodule must never be discovered.
        assert "hidden_func" not in names["functions"]

    def test_respects_all_when_present(self):
        plugin = PythonPlugin()
        names = _snapshot_names(plugin, str(FIXTURES_DIR / "scopepkg_all"))
        assert "visible_func" in names["functions"]
        assert "invisible_func" not in names["functions"]


class TestIncludeExclude:
    """Include/exclude scope: module/package allow-list + exclude-after-include."""

    def test_include_only_module_allowlist(self):
        plugin = PythonPlugin()
        names = _snapshot_names(
            plugin,
            str(FIXTURES_DIR / "scopepkg"),
            options={"include": ["scopepkg.pub"]},
        )
        assert "included_func" in names["functions"]
        assert "IncludedClass" in names["types"]
        assert "excluded_func" not in names["functions"]
        assert "nested_func" not in names["functions"]

    def test_exclude_after_include(self):
        plugin = PythonPlugin()
        names = _snapshot_names(
            plugin,
            str(FIXTURES_DIR / "scopepkg"),
            options={"exclude": ["scopepkg.other"]},
        )
        assert "included_func" in names["functions"]
        assert "nested_func" in names["functions"]
        assert "excluded_func" not in names["functions"]

    def test_include_and_exclude_together(self):
        plugin = PythonPlugin()
        names = _snapshot_names(
            plugin,
            str(FIXTURES_DIR / "scopepkg"),
            options={
                "include": ["scopepkg.pub", "scopepkg.nested"],
                "exclude": ["scopepkg.nested"],
            },
        )
        assert "included_func" in names["functions"]
        assert "nested_func" not in names["functions"]
        assert "excluded_func" not in names["functions"]

    def test_include_matches_nothing_yields_empty_api(self, caplog):
        plugin = PythonPlugin()
        names = _snapshot_names(
            plugin,
            str(FIXTURES_DIR / "scopepkg"),
            options={"include": ["scopepkg.does_not_exist"]},
        )
        assert names["functions"] == set()
        assert names["types"] == set()

    def test_empty_include_list_analyzes_whole_surface(self):
        plugin = PythonPlugin()
        names = _snapshot_names(
            plugin,
            str(FIXTURES_DIR / "scopepkg"),
            options={"include": []},
        )
        assert "included_func" in names["functions"]
        assert "excluded_func" in names["functions"]

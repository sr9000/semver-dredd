"""Use-case tests for Go plugin import-path include/exclude scope.

Fixture package layout under tests/fixtures/go_scope/:
- (root)          -> RootFunc (unprefixed, root package)
- sub/            -> SubFunc          (import path "sub")
- sub/internal/   -> InternalFunc     (import path "sub/internal", nested)
- other/          -> OtherFunc        (import path "other")
"""

import shutil
from pathlib import Path

import pytest

from semver_dredd_go.plugin import GoPlugin, GoSnapshot

FIXTURES_DIR = Path(__file__).parent / "fixtures" / "go_scope"

pytestmark = pytest.mark.skipif(
    shutil.which("go") is None, reason="Go toolchain not available"
)


def _snapshot_names(options: dict | None = None) -> set:
    plugin = GoPlugin()
    result = plugin.generate_snapshot(str(FIXTURES_DIR), "1.0.0", options=options)
    assert result.success, result.error_message
    snap = GoSnapshot.from_yaml_str(result.yaml_content)
    return set(snap.functions.keys()) | set(snap.types.keys())


class TestNoScope:
    def test_no_scope_includes_everything(self):
        names = _snapshot_names()
        assert "RootFunc" in names
        assert "sub/SubFunc" in names
        assert "sub/internal/InternalFunc" in names
        assert "other/OtherFunc" in names


class TestIncludeExclude:
    def test_include_import_path(self):
        names = _snapshot_names({"include": ["sub"]})
        assert "sub/SubFunc" in names
        # recursive include -- nested package stays in scope
        assert "sub/internal/InternalFunc" in names
        assert "RootFunc" not in names
        assert "other/OtherFunc" not in names

    def test_exclude_nested_package_with_trailing_star(self):
        names = _snapshot_names({"exclude": ["sub/internal*"]})
        assert "RootFunc" in names
        assert "sub/SubFunc" in names
        assert "sub/internal/InternalFunc" not in names
        assert "other/OtherFunc" in names

    def test_include_and_exclude_together(self):
        names = _snapshot_names(
            {"include": ["sub"], "exclude": ["sub/internal*"]}
        )
        assert "sub/SubFunc" in names
        assert "sub/internal/InternalFunc" not in names
        assert "RootFunc" not in names
        assert "other/OtherFunc" not in names

    def test_include_matches_nothing_yields_empty_api(self):
        names = _snapshot_names({"include": ["does/not/exist"]})
        assert names == set()

    def test_empty_include_analyzes_whole_surface(self):
        names = _snapshot_names({"include": []})
        assert "RootFunc" in names
        assert "other/OtherFunc" in names

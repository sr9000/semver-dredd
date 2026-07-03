"""Use-case tests for Java (regex) plugin package-prefix include/exclude scope.

Fixture package layout under tests/fixtures/java_scope/:
- com.example.api            -> Included.includedMethod
- com.example.api.internal   -> Internal.internalMethod (nested under api)
- com.example.other          -> Other.otherMethod
"""

from pathlib import Path

import pytest

from semver_dredd_java.plugin import JavaPlugin, JavaSnapshot

FIXTURES_DIR = Path(__file__).parent / "fixtures" / "java_scope"

pytestmark = pytest.mark.skipif(
    __import__("shutil").which("javac") is None or __import__("shutil").which("java") is None,
    reason="JDK (javac/java) not available",
)


def _snapshot_names(options: dict | None = None) -> set:
    plugin = JavaPlugin()
    result = plugin.generate_snapshot(str(FIXTURES_DIR), "1.0.0", options=options)
    assert result.success, result.error_message
    snap = JavaSnapshot.from_yaml_str(result.yaml_content)
    return set(snap.functions.keys()) | set(snap.types.keys())


class TestNoScope:
    def test_no_scope_includes_everything(self):
        names = _snapshot_names()
        assert "com.example.api.Included.includedMethod" in names
        assert "com.example.api.internal.Internal.internalMethod" in names
        assert "com.example.other.Other.otherMethod" in names


class TestIncludeExclude:
    def test_include_package_prefix(self):
        names = _snapshot_names({"include": ["com.example.api"]})
        assert "com.example.api.Included.includedMethod" in names
        # recursive include -- nested package stays in scope
        assert "com.example.api.internal.Internal.internalMethod" in names
        assert "com.example.other.Other.otherMethod" not in names

    def test_exclude_nested_package_with_trailing_star(self):
        names = _snapshot_names({"exclude": ["com.example.api.internal*"]})
        assert "com.example.api.Included.includedMethod" in names
        assert "com.example.api.internal.Internal.internalMethod" not in names
        assert "com.example.other.Other.otherMethod" in names

    def test_include_and_exclude_together(self):
        names = _snapshot_names(
            {
                "include": ["com.example.api"],
                "exclude": ["com.example.api.internal*"],
            }
        )
        assert "com.example.api.Included.includedMethod" in names
        assert "com.example.api.internal.Internal.internalMethod" not in names
        assert "com.example.other.Other.otherMethod" not in names

    def test_include_matches_nothing_yields_empty_api(self):
        names = _snapshot_names({"include": ["com.example.does.not.exist"]})
        assert names == set()

    def test_empty_include_analyzes_whole_surface(self):
        names = _snapshot_names({"include": []})
        assert "com.example.api.Included.includedMethod" in names
        assert "com.example.other.Other.otherMethod" in names

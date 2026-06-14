"""Tests for the CLI configuration system."""

import os
from unittest.mock import patch

from cli.config import (
    load_config,
    load_config_with_meta,
    resolve_command_context,
    apply_config_defaults,
    Config,
    _parse_env_file,
    _parse_bool,
    _load_yaml_config,
    _deep_merge_dicts,
)


class TestParseBool:
    """Test boolean parsing from strings."""

    def test_parse_bool_true_values(self):
        assert _parse_bool("true") is True
        assert _parse_bool("True") is True
        assert _parse_bool("TRUE") is True
        assert _parse_bool("1") is True
        assert _parse_bool("yes") is True
        assert _parse_bool("Yes") is True
        assert _parse_bool("on") is True
        assert _parse_bool("ON") is True

    def test_parse_bool_false_values(self):
        assert _parse_bool("false") is False
        assert _parse_bool("False") is False
        assert _parse_bool("FALSE") is False
        assert _parse_bool("0") is False
        assert _parse_bool("no") is False
        assert _parse_bool("No") is False
        assert _parse_bool("off") is False
        assert _parse_bool("OFF") is False

    def test_parse_bool_none(self):
        assert _parse_bool(None) is None

    def test_parse_bool_passthrough(self):
        assert _parse_bool(True) is True
        assert _parse_bool(False) is False

    def test_parse_bool_invalid(self):
        assert _parse_bool("invalid") is None
        assert _parse_bool("maybe") is None


class TestParseEnvFile:
    """Test .env file parsing."""

    def test_parse_env_file_basic(self, tmp_path):
        env_file = tmp_path / ".env"
        env_file.write_text("KEY=value\nANOTHER=123\n")
        result = _parse_env_file(env_file)
        assert result == {"KEY": "value", "ANOTHER": "123"}

    def test_parse_env_file_with_comments(self, tmp_path):
        env_file = tmp_path / ".env"
        env_file.write_text("# This is a comment\nKEY=value\n# Another comment\n")
        result = _parse_env_file(env_file)
        assert result == {"KEY": "value"}

    def test_parse_env_file_empty_lines(self, tmp_path):
        env_file = tmp_path / ".env"
        env_file.write_text("KEY=value\n\n\nANOTHER=123\n")
        result = _parse_env_file(env_file)
        assert result == {"KEY": "value", "ANOTHER": "123"}

    def test_parse_env_file_quoted_values(self, tmp_path):
        env_file = tmp_path / ".env"
        env_file.write_text('KEY="quoted value"\nSINGLE=\'single quoted\'\n')
        result = _parse_env_file(env_file)
        assert result == {"KEY": "quoted value", "SINGLE": "single quoted"}

    def test_parse_env_file_missing(self, tmp_path):
        env_file = tmp_path / ".env.nonexistent"
        result = _parse_env_file(env_file)
        assert result == {}

    def test_parse_env_file_no_equals(self, tmp_path):
        env_file = tmp_path / ".env"
        env_file.write_text("KEY=value\nINVALID_LINE\nANOTHER=123\n")
        result = _parse_env_file(env_file)
        assert result == {"KEY": "value", "ANOTHER": "123"}


class TestLoadYamlConfig:
    """Test YAML config file loading."""

    def test_load_yaml_config_basic(self, tmp_path):
        config_file = tmp_path / ".semver.yaml"
        config_file.write_text("""
schema_version: 1
plugin: go
policies:
  allow_breaking_changes: true
""")
        result = _load_yaml_config(config_file)
        assert result["schema_version"] == 1
        assert result["plugin"] == "go"
        assert result["policies"]["allow_breaking_changes"] is True

    def test_load_yaml_config_missing(self, tmp_path):
        config_file = tmp_path / ".semver.yaml.nonexistent"
        result = _load_yaml_config(config_file)
        assert result == {}

    def test_load_yaml_config_empty(self, tmp_path):
        config_file = tmp_path / ".semver.yaml"
        config_file.write_text("")
        result = _load_yaml_config(config_file)
        assert result == {}

    def test_load_yaml_config_malformed_warns(self, tmp_path, capsys):
        """Malformed YAML produces a stderr warning and returns {}."""
        config_file = tmp_path / ".semver.yaml"
        config_file.write_text("plugin: [unclosed\npolicies: {bad")
        result = _load_yaml_config(config_file)
        assert result == {}
        captured = capsys.readouterr()
        assert "Failed to parse config file" in captured.err
        assert str(config_file) in captured.err

    def test_load_yaml_config_non_mapping_warns(self, tmp_path, capsys):
        """A YAML file that is not a mapping warns and returns {}."""
        config_file = tmp_path / ".semver.yaml"
        config_file.write_text("- just\n- a\n- list\n")
        result = _load_yaml_config(config_file)
        assert result == {}
        captured = capsys.readouterr()
        assert "must contain a YAML mapping" in captured.err

    def test_load_yaml_config_valid_no_warning(self, tmp_path, capsys):
        """Valid config produces no warning."""
        config_file = tmp_path / ".semver.yaml"
        config_file.write_text("plugin: go\n")
        result = _load_yaml_config(config_file)
        assert result == {"plugin": "go"}
        captured = capsys.readouterr()
        assert captured.err == ""

    def test_load_yaml_config_missing_no_warning(self, tmp_path, capsys):
        """Missing config file produces no warning."""
        config_file = tmp_path / ".semver.yaml.nonexistent"
        result = _load_yaml_config(config_file)
        assert result == {}
        captured = capsys.readouterr()
        assert captured.err == ""


class TestLoadConfig:
    """Test the full config loading with priority."""

    def test_load_config_defaults(self, tmp_path):
        """Test default values when no config files exist."""
        config = load_config(cwd=tmp_path)
        assert config.allow_breaking_changes is False
        assert config.color is None
        assert config.plugin == "python"
        assert config.baked_file == "baked.yaml"
        assert config.current_file == "current.yaml"
        assert config.version_file == "VERSION"

    def test_load_config_from_yaml(self, tmp_path):
        """Test loading from .semver.yaml file."""
        config_file = tmp_path / ".semver.yaml"
        config_file.write_text("""
schema_version: 1
plugin: go
policies:
  allow_breaking_changes: true
output:
  color: true
files:
  baked: custom_baked.yaml
  current: custom_current.yaml
  version: CUSTOM_VERSION
""")
        config = load_config(cwd=tmp_path)
        assert config.allow_breaking_changes is True
        assert config.color is True
        assert config.plugin == "go"
        assert config.baked_file == "custom_baked.yaml"
        assert config.current_file == "custom_current.yaml"
        assert config.version_file == "CUSTOM_VERSION"

    def test_load_config_env_overrides_yaml(self, tmp_path):
        """Test .env file overrides .semver.yaml."""
        config_file = tmp_path / ".semver.yaml"
        config_file.write_text("""
plugin: python
policies:
  allow_breaking_changes: false
""")
        env_file = tmp_path / ".env"
        env_file.write_text("""
SEMVER_DREDD_ALLOW_BREAKING=true
SEMVER_DREDD_PLUGIN=java
""")
        config = load_config(cwd=tmp_path)
        assert config.allow_breaking_changes is True
        assert config.plugin == "java"

    def test_load_config_real_env_overrides_env_file(self, tmp_path):
        """Test real environment variables override .env file."""
        env_file = tmp_path / ".env"
        env_file.write_text("""
SEMVER_DREDD_ALLOW_BREAKING=false
SEMVER_DREDD_PLUGIN=go
""")
        with patch.dict(os.environ, {
            "SEMVER_DREDD_ALLOW_BREAKING": "true",
            "SEMVER_DREDD_PLUGIN": "java",
        }):
            config = load_config(cwd=tmp_path)
            assert config.allow_breaking_changes is True
            assert config.plugin == "java"

    def test_load_config_priority_chain(self, tmp_path):
        """Test full priority chain: yaml < .env < env vars."""
        # Layer 1: .semver.yaml sets everything to one value
        config_file = tmp_path / ".semver.yaml"
        config_file.write_text("""
plugin: python
policies:
  allow_breaking_changes: false
output:
  color: false
""")
        # Layer 2: .env overrides some values
        env_file = tmp_path / ".env"
        env_file.write_text("""
SEMVER_DREDD_ALLOW_BREAKING=true
""")
        # Layer 3: real env var overrides again
        with patch.dict(os.environ, {"SEMVER_DREDD_COLOR": "true"}):
            config = load_config(cwd=tmp_path)
            # plugin stays from yaml (not overridden)
            assert config.plugin == "python"
            # allow_breaking comes from .env
            assert config.allow_breaking_changes is True
            # color comes from real env var
            assert config.color is True


class TestScopeOptions:
    """Test include / exclude / plugin_options parsing and forwarding."""

    def test_defaults_empty(self, tmp_path):
        config = load_config(cwd=tmp_path)
        assert config.include == []
        assert config.exclude == []
        assert config.plugin_options == {}
        assert config.snapshot_options() == {}

    def test_load_from_yaml(self, tmp_path):
        config_file = tmp_path / ".semver.yaml"
        config_file.write_text("""
plugin: python
include:
  - mypackage.core
  - mypackage.utils
exclude:
  - mypackage.core._private
plugin_options:
  timeout_seconds: 30
  extra_classpath: ["/opt/libs/custom.jar"]
""")
        config = load_config(cwd=tmp_path)
        assert config.include == ["mypackage.core", "mypackage.utils"]
        assert config.exclude == ["mypackage.core._private"]
        assert config.plugin_options == {
            "timeout_seconds": 30,
            "extra_classpath": ["/opt/libs/custom.jar"],
        }

    def test_non_array_include_rejected(self, tmp_path):
        config_file = tmp_path / ".semver.yaml"
        config_file.write_text("include: mypackage\n")
        import pytest

        with pytest.raises(ValueError, match="include"):
            load_config(cwd=tmp_path)

    def test_scope_item_shapes_preserved(self, tmp_path):
        config_file = tmp_path / ".semver.yaml"
        config_file.write_text(
            """
include:
  - pkg.core
  - 42
  - {kind: class, name: Api}
exclude:
  - pkg.internal
  - {kind: module, name: x}
"""
        )
        config = load_config(cwd=tmp_path)
        assert config.include == ["pkg.core", 42, {"kind": "class", "name": "Api"}]
        assert config.exclude == ["pkg.internal", {"kind": "module", "name": "x"}]

    def test_snapshot_options_only_set_keys(self, tmp_path):
        config_file = tmp_path / ".semver.yaml"
        config_file.write_text("include:\n  - pkg\n")
        config = load_config(cwd=tmp_path)
        opts = config.snapshot_options()
        assert opts == {"include": ["pkg"]}
        # exclude / plugin_options must be absent so plugins that ignore
        # these keys behave exactly as before
        assert "exclude" not in opts
        assert "plugin_options" not in opts

    def test_apply_config_defaults_sets_snapshot_options(self):
        import argparse
        args = argparse.Namespace()
        config = Config(include=["pkg"], plugin_options={"a": 1})
        apply_config_defaults(args, config)
        assert args.snapshot_options == {
            "include": ["pkg"],
            "plugin_options": {"a": 1},
        }


class TestApplyConfigDefaults:
    """Test applying config to argparse namespace."""

    def test_apply_config_defaults_allow_breaking(self):
        """Test allow_breaking is applied from config."""
        import argparse
        args = argparse.Namespace(allow_breaking=False, disallow_breaking=False)
        config = Config(allow_breaking_changes=True)
        apply_config_defaults(args, config)
        assert args.allow_breaking is True

    def test_apply_config_defaults_cli_overrides(self):
        """Test CLI args override config defaults."""
        import argparse
        args = argparse.Namespace(allow_breaking=True, disallow_breaking=False)
        config = Config(allow_breaking_changes=False)
        apply_config_defaults(args, config)
        # CLI explicitly set, should remain True
        assert args.allow_breaking is True

    def test_apply_config_defaults_color(self):
        """Test color is applied from config."""
        import argparse
        args = argparse.Namespace(color=None)
        config = Config(color=True)
        apply_config_defaults(args, config)
        assert args.color is True

    def test_apply_config_defaults_plugin(self):
        """Test plugin is applied from config."""
        import argparse
        # Case 1: CLI arg not set (None) -> use config
        args = argparse.Namespace(plugin=None)
        config = Config(plugin="go")
        apply_config_defaults(args, config)
        assert args.plugin == "go"

        # Case 2: CLI arg set "python" (user explicit) -> keep user value
        # Wait, my logic in config.py respects explicit "python" if passed,
        # but argparse default is usually "python".
        # I changed CLI default to None, so if user types `init` (no --plugin), args.plugin is None.
        # If user types `init --plugin python`, args.plugin is "python".
        args = argparse.Namespace(plugin="python")
        config = Config(plugin="go")
        apply_config_defaults(args, config)
        assert args.plugin == "python"

    def test_apply_config_defaults_file_paths(self):
        """Test file paths are applied from config."""
        import argparse
        args = argparse.Namespace(
            baked=None,
            current_file=None,
            version_file=None,
        )
        config = Config(
            baked_file="custom.yaml",
            current_file="custom_current.yaml",
            version_file="CUSTOM_VER",
        )
        apply_config_defaults(args, config)
        assert args.baked == "custom.yaml"
        assert args.current_file == "custom_current.yaml"
        assert args.version_file == "CUSTOM_VER"


class TestMergeSemantics:
    def test_deep_merge_dicts_rules(self):
        base = {
            "obj": {"a": 1, "b": {"x": 1}, "drop": "me"},
            "arr": [1, 2],
            "scalar": "old",
            "remove": 1,
        }
        override = {
            "obj": {"b": {"y": 2}, "drop": None},
            "arr": [3],
            "scalar": "new",
            "remove": None,
            "added": True,
        }
        merged = _deep_merge_dicts(base, override)
        assert merged["obj"] == {"a": 1, "b": {"x": 1, "y": 2}}
        assert merged["arr"] == [1, 2, 3]
        assert merged["scalar"] == "new"
        assert "remove" not in merged
        assert merged["added"] is True


class TestMultiDocumentConfig:
    def test_single_document_compat(self, tmp_path):
        cfg = tmp_path / ".semver.yaml"
        cfg.write_text("plugin: go\n")
        loaded = load_config_with_meta(cwd=tmp_path)
        assert len(loaded.raw_documents) == 1
        assert loaded.raw_documents[0].data["plugin"] == "go"

    def test_multi_document_preserves_order_and_candidates(self, tmp_path):
        cfg = tmp_path / ".semver.yaml"
        cfg.write_text(
            """
plugin: python
include:
  - base
---
plugin: go
source:
  path: .
---
plugin: java
source:
  path: .
"""
        )
        loaded = load_config_with_meta(cwd=tmp_path)
        assert [d.index for d in loaded.raw_documents] == [0, 1, 2]
        assert [i for i, _ in loaded.candidate_documents] == [1, 2]
        first = loaded.candidate_documents[0][1]
        second = loaded.candidate_documents[1][1]
        assert first["plugin"] == "go"
        assert second["plugin"] == "java"
        assert first["include"] == ["base"]


class TestCommandContextResolution:
    def test_resolved_source_layer_from_config(self, tmp_path, monkeypatch):
        (tmp_path / "dummy.go").write_text("package dummy\n")
        cfg = tmp_path / ".semver.yaml"
        cfg.write_text(
            """
plugin: go
source:
  path: .
files:
  version: VERSION
"""
        )
        monkeypatch.chdir(tmp_path)
        import argparse

        args = argparse.Namespace(
            command="status",
            plugin=None,
            module=None,
            path=None,
            include=None,
            exclude=None,
            override=False,
            version_file=None,
        )
        loaded = load_config_with_meta(cwd=tmp_path)
        resolved = resolve_command_context(args, loaded, cwd=tmp_path)
        assert resolved.plugin == "go"
        assert resolved.plugin_layer == "config"
        assert resolved.source_path == "."
        assert resolved.source_layer == "config"
        assert resolved.version_file == "VERSION"
        assert resolved.version_file_layer == "config"

    def test_cli_include_exclude_append_and_override(self, tmp_path, monkeypatch):
        (tmp_path / "dummy.go").write_text("package dummy\n")
        cfg = tmp_path / ".semver.yaml"
        cfg.write_text(
            """
plugin: go
source:
  path: .
include: [a, b]
exclude: [x]
"""
        )
        monkeypatch.chdir(tmp_path)
        import argparse

        base_args = argparse.Namespace(
            command="status",
            plugin=None,
            module=None,
            path=None,
            include=["b", "c"],
            exclude=["x", "y"],
            override=False,
            version_file=None,
        )
        loaded = load_config_with_meta(cwd=tmp_path)
        resolved = resolve_command_context(base_args, loaded, cwd=tmp_path)
        assert resolved.include == ["a", "b", "b", "c"]
        assert resolved.exclude == ["x", "x", "y"]
        assert any("Duplicate include" in w for w in resolved.warnings)
        assert any("Duplicate exclude" in w for w in resolved.warnings)

        override_args = argparse.Namespace(
            command="status",
            plugin=None,
            module=None,
            path=None,
            include=["only"],
            exclude=["none"],
            override=True,
            version_file=None,
        )
        resolved_override = resolve_command_context(override_args, loaded, cwd=tmp_path)
        assert resolved_override.include == ["only"]
        assert resolved_override.exclude == ["none"]

    def test_candidate_fallback_first_valid(self, tmp_path, monkeypatch):
        (tmp_path / "dummy.go").write_text("package dummy\n")
        cfg = tmp_path / ".semver.yaml"
        cfg.write_text(
            """
plugin: python
---
plugin: go
source:
  path: ./missing
---
plugin: go
source:
  path: .
"""
        )
        monkeypatch.chdir(tmp_path)
        import argparse

        args = argparse.Namespace(
            command="status",
            plugin=None,
            module=None,
            path=None,
            include=None,
            exclude=None,
            override=False,
            version_file=None,
        )
        loaded = load_config_with_meta(cwd=tmp_path)
        resolved = resolve_command_context(args, loaded, cwd=tmp_path)
        assert resolved.candidate_index == 2
        assert len(resolved.candidate_attempts) == 2
        assert resolved.candidate_attempts[0].ok is False
        assert resolved.candidate_attempts[1].ok is True

    def test_candidate_all_fail_lists_attempts(self, tmp_path, monkeypatch):
        cfg = tmp_path / ".semver.yaml"
        cfg.write_text(
            """
plugin: python
---
plugin: does-not-exist
source:
  path: .
---
plugin: go
source:
  path: ./missing
"""
        )
        monkeypatch.chdir(tmp_path)
        import argparse
        import pytest

        args = argparse.Namespace(
            command="status",
            plugin=None,
            module=None,
            path=None,
            include=None,
            exclude=None,
            override=False,
            version_file=None,
        )
        loaded = load_config_with_meta(cwd=tmp_path)
        with pytest.raises(ValueError) as exc:
            resolve_command_context(args, loaded, cwd=tmp_path)
        msg = str(exc.value)
        assert "doc#1" in msg
        assert "doc#2" in msg
        assert "not installed" in msg

    def test_cli_plugin_override_selects_matching_candidate(self, tmp_path, monkeypatch):
        (tmp_path / "dummy.go").write_text("package dummy\n")
        cfg = tmp_path / ".semver.yaml"
        cfg.write_text(
            """
plugin: python
---
plugin: python
source:
  path: example.py.pygeometry1
---
plugin: go
source:
  path: .
"""
        )
        monkeypatch.chdir(tmp_path)
        import argparse

        args = argparse.Namespace(
            command="status",
            plugin="go",
            module=None,
            path=None,
            include=None,
            exclude=None,
            override=False,
            version_file=None,
        )
        loaded = load_config_with_meta(cwd=tmp_path)
        resolved = resolve_command_context(args, loaded, cwd=tmp_path)
        assert resolved.plugin == "go"
        assert resolved.candidate_index == 2

    def test_env_plugin_override_and_absent_override_plugin(self, tmp_path, monkeypatch):
        (tmp_path / "dummy.go").write_text("package dummy\n")
        cfg = tmp_path / ".semver.yaml"
        cfg.write_text(
            """
plugin: python
---
plugin: python
source:
  path: example.py.pygeometry1
---
plugin: go
source:
  path: .
"""
        )
        monkeypatch.chdir(tmp_path)
        import argparse
        import pytest

        with patch.dict(os.environ, {"SEMVER_DREDD_PLUGIN": "go"}):
            args = argparse.Namespace(
                command="status",
                plugin=None,
                module=None,
                path=None,
                include=None,
                exclude=None,
                override=False,
                version_file=None,
            )
            loaded = load_config_with_meta(cwd=tmp_path)
            resolved = resolve_command_context(args, loaded, cwd=tmp_path)
            assert resolved.plugin == "go"
            assert resolved.candidate_index == 2

        with patch.dict(os.environ, {"SEMVER_DREDD_PLUGIN": "java"}):
            args = argparse.Namespace(
                command="status",
                plugin=None,
                module=None,
                path=None,
                include=None,
                exclude=None,
                override=False,
                version_file=None,
            )
            loaded = load_config_with_meta(cwd=tmp_path)
            with pytest.raises(ValueError, match="not present in any config candidate"):
                resolve_command_context(args, loaded, cwd=tmp_path)


class TestConfigGet:
    """Test Config.get() method for nested access."""

    def test_get_nested_value(self):
        config = Config(_raw={"policies": {"custom": {"nested": "value"}}})
        assert config.get("policies", "custom", "nested") == "value"

    def test_get_missing_value(self):
        config = Config(_raw={"policies": {}})
        assert config.get("policies", "missing", default="default") == "default"

    def test_get_default(self):
        config = Config(_raw={})
        assert config.get("nonexistent", default=42) == 42

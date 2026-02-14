"""Tests for the CLI configuration system."""

import os
from unittest.mock import patch

from cli.config import (
    load_config,
    apply_config_defaults,
    Config,
    _parse_env_file,
    _parse_bool,
    _load_yaml_config,
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
language: go
policies:
  allow_breaking_changes: true
""")
        result = _load_yaml_config(config_file)
        assert result["schema_version"] == 1
        assert result["language"] == "go"
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


class TestLoadConfig:
    """Test the full config loading with priority."""

    def test_load_config_defaults(self, tmp_path):
        """Test default values when no config files exist."""
        config = load_config(cwd=tmp_path)
        assert config.allow_breaking_changes is False
        assert config.color is None
        assert config.language == "python"
        assert config.baked_file == "baked.yaml"
        assert config.current_file == "current.yaml"
        assert config.version_file == "VERSION"

    def test_load_config_from_yaml(self, tmp_path):
        """Test loading from .semver.yaml file."""
        config_file = tmp_path / ".semver.yaml"
        config_file.write_text("""
schema_version: 1
language: go
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
        assert config.language == "go"
        assert config.baked_file == "custom_baked.yaml"
        assert config.current_file == "custom_current.yaml"
        assert config.version_file == "CUSTOM_VERSION"

    def test_load_config_env_overrides_yaml(self, tmp_path):
        """Test .env file overrides .semver.yaml."""
        config_file = tmp_path / ".semver.yaml"
        config_file.write_text("""
language: python
policies:
  allow_breaking_changes: false
""")
        env_file = tmp_path / ".env"
        env_file.write_text("""
SEMVER_DREDD_ALLOW_BREAKING=true
SEMVER_DREDD_LANG=java
""")
        config = load_config(cwd=tmp_path)
        assert config.allow_breaking_changes is True
        assert config.language == "java"

    def test_load_config_real_env_overrides_env_file(self, tmp_path):
        """Test real environment variables override .env file."""
        env_file = tmp_path / ".env"
        env_file.write_text("""
SEMVER_DREDD_ALLOW_BREAKING=false
SEMVER_DREDD_LANG=go
""")
        with patch.dict(os.environ, {
            "SEMVER_DREDD_ALLOW_BREAKING": "true",
            "SEMVER_DREDD_LANG": "java",
        }):
            config = load_config(cwd=tmp_path)
            assert config.allow_breaking_changes is True
            assert config.language == "java"

    def test_load_config_priority_chain(self, tmp_path):
        """Test full priority chain: yaml < .env < env vars."""
        # Layer 1: .semver.yaml sets everything to one value
        config_file = tmp_path / ".semver.yaml"
        config_file.write_text("""
language: python
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
            # language stays from yaml (not overridden)
            assert config.language == "python"
            # allow_breaking comes from .env
            assert config.allow_breaking_changes is True
            # color comes from real env var
            assert config.color is True


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

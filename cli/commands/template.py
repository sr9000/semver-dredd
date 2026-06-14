"""template command — generate a comprehensive .semver.yaml configuration template."""

from __future__ import annotations

import argparse
from pathlib import Path

from cli.utils import DEFAULT_CONFIG_FILE, EXIT_OK, _print_level, _should_use_color

# Comprehensive template content with all options and comments
_TEMPLATE = """# semver-dredd configuration file
# This file configures semver-dredd behavior for your project.
# Place this file in your project root as '.semver.yaml'
#
# Configuration Priority (lowest to highest):
# 1. .semver.yaml (this file) - lowest priority
# 2. .env file - overrides .semver.yaml
# 3. Environment variables - override .env
# 4. CLI arguments - highest priority (always win)
#
# Note: This priority system only applies to CLI usage.
# Programmatic API calls ignore all config files.

# Schema version for this configuration file
# Currently supported: 1
schema_version: 1

# Project plugin (optional, defaults to 'python')
# Supported: python, go, java (or any installed plugin)
# Can be overridden by SEMVER_DREDD_PLUGIN env var or --plugin CLI arg
# plugin: python

# Policies section controls semver-dredd behavior
policies:
  # Whether to allow breaking changes (MAJOR version bumps)
  # If false, semver-dredd will exit with error code 10 when breaking changes are detected
  # If true, breaking changes are allowed but logged as warnings
  # Can be overridden by SEMVER_DREDD_ALLOW_BREAKING env var or --allow-breaking CLI flag
  allow_breaking_changes: false

# Output configuration
output:
  # Color mode for log output
  # true: always use ANSI colors
  # false: never use colors
  # null/omit: auto-detect (color if stderr is a TTY)
  # Can be overridden by SEMVER_DREDD_COLOR env var or --color/--no-color CLI flags
  # color: null

  # Severity levels for different change types
  # Controls the log level (info/warn/error) for each change type
  severity_by_change:
    # NONE: No API changes detected (but patch bump still occurs)
    none: info
    # PATCH: Implementation changes only
    patch: info
    # MINOR: New features added (backward compatible)
    minor: warn
    # MAJOR: Breaking changes detected
    major: error

# File paths configuration
# Can be overridden by environment variables or CLI arguments
files:
  # Baked API snapshot file
  # Env var: SEMVER_DREDD_BAKED_FILE
  # CLI: --baked
  baked: baked.yaml

  # Current API snapshot file (generated during status command)
  # Env var: SEMVER_DREDD_CURRENT_FILE
  # CLI: --current-file
  current: current.yaml

  # Version file
  # Env var: SEMVER_DREDD_VERSION_FILE
  # CLI: --version-file
  version: VERSION

# Versioning configuration
versioning:
  # Patch numbering scheme:
  #   date (default) - YYYYMMDDZZZ (date + daily counter)
  #   integer        - conventional incrementing patch (0, 1, 2, ...);
  #                    resets to 0 on major/minor bumps
  patch_scheme: date

# Analysis scope (optional)
# Flat lists of opaque strings forwarded to the language plugin via its
# options dict. Interpretation (packages, paths, globs) is plugin-specific.
# NOTE: the bundled python/go/java plugins receive these but do not filter
# by them yet (see the plans/ roadmap for status).
# include:
#   - mypackage.core
#   - mypackage.utils
# exclude:
#   - mypackage.core._private

# Free-form plugin options (optional)
# Forwarded to the plugin as-is; never validated by the framework.
# Plugins must silently ignore unknown keys.
# plugin_options:
#   timeout_seconds: 30
#   source_encoding: "UTF-8"

# Environment Variables Reference:
# ================================
# SEMVER_DREDD_ALLOW_BREAKING - Set to 'true' or 'false'
# SEMVER_DREDD_COLOR - Set to 'true' or 'false'
# SEMVER_DREDD_PLUGIN - Set to 'python', 'go', or 'java' (or plugin name)
# SEMVER_DREDD_BAKED_FILE - Path to baked.yaml
# SEMVER_DREDD_CURRENT_FILE - Path to current.yaml
# SEMVER_DREDD_VERSION_FILE - Path to VERSION file
#
# .env file example:
# ------------------
# SEMVER_DREDD_ALLOW_BREAKING=true
# SEMVER_DREDD_COLOR=false
# SEMVER_DREDD_BAKED_FILE=api/baked.yaml
"""


def cmd_template(args: argparse.Namespace) -> int:
    """Generate a comprehensive .semver.yaml template with all options and comments."""
    use_color = _should_use_color(getattr(args, "color", None))

    # Write to file or print to stdout
    if args.out:
        Path(args.out).write_text(_TEMPLATE)
        _print_level("info", f"Wrote template to {args.out}", use_color=use_color)
    else:
        print(_TEMPLATE)

    return EXIT_OK

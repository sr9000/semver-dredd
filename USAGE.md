# semver-dredd CLI usage

This document describes the command-line interface, important flags, and common
workflows.

## Command overview

```bash
semver-dredd --help
semver-dredd <command> --help
```

Primary commands:

- `init` — create config, baseline snapshot, and version file
- `status` — compare current code to baked baseline
- `bake` — replace the baked baseline with the current API
- `compare` — compare two explicit sources directly
- `snapshot` — generate a standalone snapshot
- `bump` — increment a semantic version directly
- `patch` — generate a patch value with the active scheme
- `template` — print a commented config template
- `plugin` — inspect/install/remove plugins

## Config precedence

For CLI usage, the effective precedence is:

1. config file
2. `.env`
3. environment variables
4. CLI arguments

This affects plugin selection, source path, managed file paths, color policy,
breaking-change policy, and patch numbering scheme.

## Typical workflow

```bash
semver-dredd init . --plugin python --version 1.0.0
semver-dredd status --details
semver-dredd bake
```

If `.semver.yaml` defines `source.path`, later commands can omit the positional
path.

## `init`

Initialize semver-dredd for a project.

```bash
semver-dredd init ./src --plugin go --version 1.0.0
```

Notes:

- `--plugin` is required
- writes `.semver.yaml`, baked snapshot, and `VERSION`
- can use `--patch-scheme integer` when you want conventional patch increments

## `status`

Compare current API state against the baked baseline.

```bash
semver-dredd status mypackage --plugin python
semver-dredd status --details
semver-dredd status --allow-breaking
semver-dredd status --date 2026-06-15
```

Useful behavior:

- updates `current.yaml`
- suggests the next version from the detected change kind
- exits non-zero on breaking changes unless allowed
- reads plugin/path from config when available

Scope controls:

```bash
semver-dredd status --include mypackage.api --exclude mypackage.api.internal
semver-dredd status --include mypackage.api --override
```

By default CLI `--include` / `--exclude` append to config arrays; `--override`
replaces them.

## `bake`

Lock the current API as the new release baseline.

```bash
semver-dredd bake mypackage --plugin python
semver-dredd bake mypackage --plugin python --version 2.0.0
```

Behavior:

- updates `baked.yaml`
- writes `VERSION`
- auto-computes the next version unless `--version` is given

## `compare`

Compare two explicit targets directly.

```bash
semver-dredd compare old_module new_module
semver-dredd compare ./v1/pkg ./v2/pkg --plugin go
semver-dredd compare old_module new_module --details --current 1.2.0
```

Use this when you do not want the baked/current managed-file workflow.

## `snapshot`

Generate a standalone snapshot.

```bash
semver-dredd snapshot --plugin python --path mypackage --version 1.0.0
semver-dredd snapshot --out snapshot.yaml
```

Config-driven behavior:

- plugin/path default from config when present
- version defaults from the resolved `VERSION` file unless overridden
- scope flags append to config arrays unless `--override` is used

## `bump`

Increment a version for a known change kind.

```bash
semver-dredd bump --current 1.0.0 --change minor
```

## `patch`

Generate just the patch component.

```bash
semver-dredd patch
semver-dredd patch --current 20260305001
```

Patch scheme can come from config, env, or explicit CLI flags.

## `template`

Print the full commented config template.

```bash
semver-dredd template
semver-dredd template --out .semver.yaml
```

Use this together with [`example/semver_showcase.yaml`](example/semver_showcase.yaml)
and [`SCHEMA.md`](SCHEMA.md).

## `plugin`

Manage or inspect plugins.

```bash
semver-dredd plugin
semver-dredd plugin list
semver-dredd plugin list --json
semver-dredd plugin list --yaml
semver-dredd plugin info python
semver-dredd plugin install python-3.10-dredd
semver-dredd plugin remove python
```

Notes:

- `semver-dredd plugin` with no subcommand prints group help
- installs are tracked so removal can target the installed package accurately
- machine-readable plugin inventory is already shipped

## Typical language-specific examples

```bash
# Python
semver-dredd init mypackage --plugin python --version 1.0.0
semver-dredd status --details

# Go
semver-dredd snapshot --plugin go --path ./pkg/api --version 1.0.0

# Java
semver-dredd snapshot --plugin java --path ./src/main/java --version 1.0.0

# Bundle
semver-dredd snapshot --plugin bundle --path . --version 1.0.0   --include services/api/VERSION --include sdk-python/VERSION
```

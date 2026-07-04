# semver-dredd schema reference

This document covers two related but different things:

1. the `.semver.yaml` configuration schema used by the CLI
2. the snapshot YAML envelopes emitted by plugins and loaded by the registry

For a full commented config example, see
[`example/semver_showcase.yaml`](example/semver_showcase.yaml).

## 1. `.semver.yaml` configuration

Current top-level keys:

```yaml
schema_version: 1
plugin: python
source:
  path: mypackage.api
files:
  baked: baked.yaml
  current: current.yaml
  version: VERSION
policies:
  allow_breaking_changes: false
output:
  color: null
  severity_by_change:
    none: info
    patch: info
    minor: warn
    major: error
versioning:
  patch_scheme: date
include: []
exclude: []
plugin_options: {}
```

### Key meanings

| Key | Meaning |
|-----|---------|
| `schema_version` | config schema version; current value is `1` |
| `plugin` | default plugin key |
| `source.path` | default source/module/path for pathless commands |
| `files.*` | managed baked/current/version file locations |
| `policies.allow_breaking_changes` | whether BREAKING exits are allowed |
| `output.color` | `true`, `false`, or `null` for auto |
| `output.severity_by_change` | documented mapping; current CLI still uses built-in severities |
| `versioning.patch_scheme` | `date` or `integer` |
| `include` | plugin-specific scope items |
| `exclude` | plugin-specific scope items removed after include |
| `plugin_options` | opaque plugin-specific options |

### Config precedence

For CLI use, values resolve in this order:

`config < .env < environment < CLI`

### Multi-document candidate configs

`.semver.yaml` may contain multiple YAML documents. semver-dredd evaluates them
in order and can fall back to later candidates when plugin/path validation fails.

Pattern:

```yaml
# candidate 0
schema_version: 1
plugin: python
source:
  path: mypackage
---
# candidate 1
schema_version: 1
plugin: go
source:
  path: ./pkg/api
```

## 2. Snapshot schema versions

Two schema families are relevant today:

| Version/family | Status | Notes |
|----------------|--------|-------|
| `NormalizedSnapshot` schema v2 | current built-in default model | used when no plugin-specific snapshot format is supplied |
| plugin snapshot envelope v3 | current plugin-specific envelope | includes `snapshot_type_id` and generator metadata when provided |

That distinction is intentional.

## 3. Plugin snapshot envelope (v3-style)

Plugin-specific snapshots commonly serialize this top-level shape:

```yaml
snapshot_type_id: "<UUID>"
schema_version: 3
version: "1.2.0"
language: python
source:
  kind: module
  path: mypackage.api
api:
  # plugin-specific payload
generator:
  plugin_name: python
  plugin_version: "1.0.0"
  plugin_source: entry_point
  config_path: .semver.yaml
  candidate_index: 0
```

### Envelope fields

| Field | Meaning |
|-------|---------|
| `snapshot_type_id` | registry dispatch key |
| `schema_version` | plugin envelope schema version |
| `version` | version of the analyzed library/module |
| `language` | plugin/language family |
| `source.kind` | source category such as `module`, `package`, `directory`, `bundle` |
| `source.path` | analyzed path/module name |
| `api` | plugin-specific snapshot body |
| `generator` | provenance metadata for plugin/config selection |

The `generator` block is optional for compatibility with older snapshots.

## 4. Official plugin payload examples

### Python snapshot

```yaml
snapshot_type_id: "..."
schema_version: 3
version: "1.0.0"
language: python
source:
  kind: module
  path: mypackage.api
api:
  variables:
    MAX_RETRIES:
      type: int
      default: "3"
  functions:
    greet:
      result_type: str
      args:
        - name: name
          type: str
          default: null
          position_only: false
          pos_and_named: true
          named_only: false
  types:
    Point:
      fields: []
      methods: {}
```

Python arguments use exactly one of:

- `position_only: true`
- `pos_and_named: true`
- `named_only: true`

### Go snapshot

```yaml
snapshot_type_id: "..."
schema_version: 3
version: "1.0.0"
language: go
source:
  kind: package
  path: ./pkg/api
api:
  functions: {}
  types: {}
```

### Java / JavaParser snapshots

```yaml
snapshot_type_id: "..."
schema_version: 3
version: "1.0.0"
language: java
source:
  kind: directory
  path: ./src/main/java
api:
  functions: {}
  types: {}
```

### Bundle snapshot

The built-in `bundle` plugin serializes dependency VERSION files under
`api.dependencies`:

```yaml
snapshot_type_id: "..."
schema_version: 3
version: "1.0.0"
language: bundle
source:
  kind: bundle
  path: /repo/root
api:
  dependencies:
    backend:
      path: services/backend/VERSION
      version: 2.3.0
    sdk-python:
      path: sdk-python/VERSION
      version: 1.4.1
```

For `bundle`, `include[]` items are explicit paths to VERSION files.

## 5. `NormalizedSnapshot` (built-in default model)

When a plugin does not supply a custom snapshot class, semver-dredd can use the
built-in `NormalizedSnapshot` model.

Important fields:

| Field | Meaning |
|-------|---------|
| `schema_version` | currently `2` |
| `version` | analyzed version |
| `language` | language identifier |
| `source_kind` | module/package/directory/etc. |
| `source_path` | analyzed source |
| `functions` | top-level functions |
| `types` | top-level types |

This is separate from the plugin v3 envelope and should be documented as such.

## 6. Related references

- [`USAGE.md`](USAGE.md)
- [`HOWTO.md`](HOWTO.md)
- [`snapshot/README.md`](snapshot/README.md)
- [`example/semver_showcase.yaml`](example/semver_showcase.yaml)

# Include / Exclude Filtering — Design Proposal

## Motivation

Projects rarely expose their entire source tree as public API surface.
Internal helpers, generated code, test utilities, and vendor directories
should not affect semantic versioning decisions.

This proposal adds **`include`** and **`exclude`** lists to `.semver.yaml`
so users can precisely control which parts of their codebase participate in
the semver analysis.

## Multi-document `.semver.yaml`

Real-world repositories are often polyglot — a Java backend, Python
scripts, and a Go CLI living side by side.  Each language needs its own
plugin, include/exclude rules, file paths, and `plugin_options`.

To support this without splitting into multiple config files,
`.semver.yaml` becomes a **multi-document YAML file** (documents separated
by `---`).

### Layout

```yaml
# ── Document 0: shared defaults ──────────────────────────────
# No `plugin` key → these values apply to every plugin unless
# a per-plugin document overrides them.
policies:
  allow_breaking_changes: false
output:
  color: true
---
# ── Document 1: Java backend ─────────────────────────────────
plugin: javaparser

files:
  baked:   java-baked.yaml
  current: java-current.yaml
  version: VERSION

include:
  - com.example.api
  - com.example.spi
exclude:
  - com.example.api.internal

plugin_options:
  source_encoding: UTF-8
  compiler_source_level: "11"
---
# ── Document 2: Python tooling ───────────────────────────────
plugin: python

files:
  baked:   py-baked.yaml
  current: py-current.yaml

include:
  - mypackage.core
  - mypackage.utils
exclude:
  - mypackage.core._private
---
# ── Document 3: Go CLI ───────────────────────────────────────
plugin: go

files:
  baked:   go-baked.yaml
  current: go-current.yaml

include:
  - github.com/org/repo/cmd
```

### Resolution rules

| # | Rule                                | Detail                                                                                                                                                                                                                                                          |
|---|-------------------------------------|-----------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------|
| 1 | **Parse all documents**             | `yaml.safe_load_all()` instead of `yaml.safe_load()`.                                                                                                                                                                                                           |
| 2 | **Shared defaults**                 | The first document that has **no `plugin` key** (or whose `plugin` is absent/null) is the *defaults document*. Its keys are inherited by every plugin-specific document. At most one such document may exist; if absent, defaults are empty.                    |
| 3 | **Per-plugin documents**            | Every document that **has a `plugin` key** is plugin-specific. When the CLI resolves config for a plugin (via `--plugin` or `SEMVER_DREDD_PLUGIN`), it deep-merges the defaults document with the matching plugin document — plugin document wins on conflicts. |
| 4 | **Single-document backward compat** | A file with one document and no `---` separators works exactly as today — the loader treats it as a combined defaults + plugin document. **No existing config breaks.**                                                                                         |
| 5 | **Duplicate plugin documents**      | If multiple documents declare the same `plugin`, the **last one wins** (like duplicate YAML keys). A warning is logged.                                                                                                                                         |
| 6 | **CLI `--plugin` selects**          | `semver-dredd snapshot --plugin javaparser` → loader picks the `javaparser` document, merges with defaults, and uses that as the active config.                                                                                                                 |

### Core loader changes (sketch)

```python
def _load_yaml_config(path: Path) -> dict[str, Any]:
    """Load multi-document .semver.yaml."""
    import yaml

    with open(path) as f:
        docs = list(yaml.safe_load_all(f))

    if not docs:
        return {}

    # Single-document file — behave exactly as before.
    if len(docs) == 1:
        return docs[0] or {}

    # Multi-document: split into defaults + per-plugin.
    defaults = {}
    by_plugin: dict[str, dict] = {}
    for doc in docs:
        if not isinstance(doc, dict):
            continue
        if "plugin" not in doc or doc["plugin"] is None:
            defaults = doc  # last one without plugin wins
        else:
            by_plugin[doc["plugin"]] = doc

    # Stash everything so load_config() can resolve later.
    return {"_defaults": defaults, "_per_plugin": by_plugin}
```

The existing `load_config()` gains an optional `plugin_name` parameter.
When `_per_plugin` is present, it deep-merges `_defaults` with the
matching plugin document (or falls back to `_defaults` alone if no
document matches).

## Configuration Format

`include` and `exclude` are **flat lists of opaque strings** stored in a
plugin document inside `.semver.yaml`.  Their interpretation is **entirely
plugin-specific** — the core framework passes them through without
modification.

```yaml
plugin: javaparser

include:
  - src/main/java/com/example/myapp
  - src/main/java/com/example/utils
exclude:
  - src/main/java/com/example/myapp/internal
  - src/main/java/com/example/utils/Helper.java
```

Strings may represent directories, files, packages, module paths, glob
patterns, class names, or any other concept meaningful to the plugin.

## Semantics

### Core rules (all plugins)

| Rule                                 | Description                                                                                                                                                                                                                                        |
|--------------------------------------|----------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------|
| **Plugin rules first**               | The plugin defines what each string means and how matching works. The rules below are *defaults* — a plugin MAY override any of them when the language warrants it.                                                                                |
| **`include` is allow-list**          | When `include` is non-empty, **only** entities matching at least one include pattern are analysed. When `include` is empty or absent, everything under the scan path is included.                                                                  |
| **`exclude` is deny-list**           | Entities matching any exclude pattern are removed **after** the include filter. `exclude` always wins over `include`.                                                                                                                              |
| **Directory inclusion is recursive** | Including a directory means all its subdirectories and files are analysed as well — unless further narrowed by `exclude`.                                                                                                                          |
| **No transitive dependency chasing** | Plugins SHOULD NOT follow imports / dependencies that resolve outside the `include` scope. Types referenced from excluded or external code are treated as opaque — they are assumed "always compatible" and never trigger breaking-change reports. |

### Recursive vs non-recursive directories

Some languages distinguish between "this directory only" and "this directory
and everything below it".  Plugins MAY introduce a convention to let users
express that difference.  For example a Java plugin could treat:

* `com.example.api` — the package **and** its sub-packages (recursive, the
  default)
* `com.example.api!` — **only** that exact package, no sub-packages

The exact syntax is plugin-defined.  Plugins that do not need this
distinction simply treat every directory entry as recursive.

## Extension point: `plugin_options`

`include` and `exclude` cover the most common filtering need, but plugins
may require arbitrary, unforeseen configuration — custom compiler flags,
source encoding, extra classpaths, feature toggles, etc.

Rather than inventing a new top-level key for every possible knob, the
config file supports a single **`plugin_options`** escape hatch: a
free-form YAML mapping that is forwarded **as-is** to the plugin.  The
framework never inspects or validates its contents.

```yaml
plugin: javaparser

include:
  - com.example.api
exclude:
  - com.example.api.internal

# Anything goes — the plugin decides what it means.
plugin_options:
  source_encoding: UTF-8
  extra_classpath:
    - /opt/libs/custom.jar
  compiler_source_level: "11"
  strip_annotations: true
```

### Design rationale

* **Ugly but powerful** — this is an expert knob.  Users who write
  `plugin_options` are expected to know their plugin's documentation and
  accept that the schema is plugin-defined.
* **Forward-compatible** — new plugin features never require changes to the
  core config loader or CLI flags.
* **Completely opaque to the framework** — the core treats `plugin_options`
  as `dict[str, Any] | None` and passes it through untouched.

### Accessing `plugin_options` in a plugin

```python
def generate_snapshot(self, path, version, options=None):
    opts = options or {}
    plugin_opts = opts.get("plugin_options") or {}

    encoding = plugin_opts.get("source_encoding", "UTF-8")
    extra_cp = plugin_opts.get("extra_classpath") or []
    # ... use them however you like
```

Plugins SHOULD silently ignore unknown keys inside `plugin_options` so that
a config file can carry options for multiple plugins without breaking any of
them.

## How the `options` dict is built

The CLI config loader reads `.semver.yaml`, merges environment layers, and
builds the `options` dict that is passed to
`LanguagePlugin.generate_snapshot()`:

```python
options = {
    "include": ["com.example.api", ...],          # from .semver.yaml
    "exclude": ["com.example.api.internal", ...],  # from .semver.yaml
    "plugin_options": { ... },                     # from .semver.yaml, raw dict
    "use_color": True,                             # from CLI / env
}
```

Plugins access them with:

```python
include = (options or {}).get("include") or []
exclude = (options or {}).get("exclude") or []
plugin_opts = (options or {}).get("plugin_options") or {}
```

## Plugin implementation guidelines

1. **Parse include/exclude early** — convert the raw strings to whatever
   internal representation is efficient (compiled globs, package prefixes,
   path sets, …).
2. **Filter at source collection time** — skip files, packages, or modules
   before parsing where possible to keep analysis fast.
3. **Treat external references as opaque** — if a public method parameter
   type comes from an excluded or out-of-scope package, record the type
   name as-is without resolving or validating it.
4. **Document the syntax** — each plugin README should explain what kinds of
   strings are accepted and any special suffixes or wildcards.
5. **Ignore unknown `plugin_options` keys** — be tolerant of options
   intended for a different plugin sharing the same config file.

## Examples

### Single-plugin project (backward compatible)

```yaml
plugin: python

include:
  - mypackage.core
  - mypackage.utils
exclude:
  - mypackage.core._private
```

### Polyglot project (multi-document)

```yaml
# ── Shared ────────────────────────────────────────────────────
policies:
  allow_breaking_changes: false
---
# ── Java ──────────────────────────────────────────────────────
plugin: javaparser

files:
  baked:   java-baked.yaml
  current: java-current.yaml

include:
  - com.example.api
  - com.example.spi
exclude:
  - com.example.api.internal

plugin_options:
  compiler_source_level: "11"
---
# ── Python ────────────────────────────────────────────────────
plugin: python

files:
  baked:   py-baked.yaml
  current: py-current.yaml

include:
  - mypackage.core
  - mypackage.utils
exclude:
  - mypackage.core._private
---
# ── Go ────────────────────────────────────────────────────────
plugin: go

files:
  baked:   go-baked.yaml
  current: go-current.yaml

include:
  - github.com/org/repo/pkg
exclude:
  - github.com/org/repo/pkg/internal
```

Usage:

```bash
semver-dredd snapshot --plugin javaparser   # uses Java document
semver-dredd snapshot --plugin python       # uses Python document
semver-dredd snapshot --plugin go           # uses Go document
```

## Non-goals

* **Glob / regex engine in core** — plugins own their matching logic.
* **Automatic API-surface detection** — heuristics belong in plugins, not
  in the framework.
* **Enforcing a single syntax** — languages are too different for a
  universal pattern language to be practical.
* **Cross-document references** — plugin documents are independent; one
  document cannot reference or inherit from another plugin document (only
  from the shared defaults).

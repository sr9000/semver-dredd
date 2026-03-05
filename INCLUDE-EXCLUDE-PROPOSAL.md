# Include / Exclude Filtering — Design Proposal

## Motivation

Projects rarely expose their entire source tree as public API surface.
Internal helpers, generated code, test utilities, and vendor directories
should not affect semantic versioning decisions.

This proposal adds **`include`** and **`exclude`** lists to `.semver.yaml`
so users can precisely control which parts of their codebase participate in
the semver analysis.

## Configuration Format

`include` and `exclude` are **flat lists of opaque strings** stored in
`.semver.yaml`.  Their interpretation is **entirely plugin-specific** — the
core framework passes them through without modification.

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

## Examples by language

### Java (`javaparser` plugin)

```yaml
include:
  - com.example.api          # package + sub-packages (recursive)
  - com.example.spi          # same
exclude:
  - com.example.api.internal # drop internal sub-package
```

### Python

```yaml
include:
  - mypackage.core
  - mypackage.utils
exclude:
  - mypackage.core._private
```

### Go

```yaml
include:
  - github.com/org/repo/pkg
exclude:
  - github.com/org/repo/pkg/internal
```

## Non-goals

* **Glob / regex engine in core** — plugins own their matching logic.
* **Automatic API-surface detection** — heuristics belong in plugins, not
  in the framework.
* **Enforcing a single syntax** — languages are too different for a
  universal pattern language to be practical.

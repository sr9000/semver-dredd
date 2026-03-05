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

## How plugins receive filters

The `include` and `exclude` lists are read from `.semver.yaml` by the CLI
config loader and forwarded to `LanguagePlugin.generate_snapshot()` via the
`options` dict:

```python
options = {
    "include": ["src/main/java/com/example/myapp", ...],
    "exclude": ["src/main/java/com/example/myapp/internal", ...],
}
```

Plugins access them with:

```python
include = (options or {}).get("include") or []
exclude = (options or {}).get("exclude") or []
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

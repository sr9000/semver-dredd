# Include / Exclude Filtering — Design Proposal

## Motivation

Projects rarely expose their entire source tree as public API surface.
Internal helpers, generated code, test utilities, and vendor directories
should not affect semantic versioning decisions.

This proposal adds **`include`** and **`exclude`** lists to `.semver.yaml`
so users can precisely control which parts of their codebase participate in
the semver analysis.

## Multi-document `.semver.yaml`

A single API surface may be analysable by several plugins — a project
might prefer `javaparser` (AST-based, accurate) but accept `java`
(regex-based, no JDK required) as a fallback.  Rather than forcing the
user to pick one up-front, `.semver.yaml` becomes a **multi-document YAML
file** (documents separated by `---`) where each document is a **plugin
candidate** listed in **priority order**.

The CLI walks the list, picks the first candidate whose plugin is
installed and whose `validate_path()` succeeds, and uses that document's
config.

### Layout

```yaml
# ── Document 0: shared defaults ──────────────────────────────
# No `plugin` key → inherited by every candidate below.
policies:
  allow_breaking_changes: false
output:
  color: true
---
# ── Document 1: preferred — AST-based parser ─────────────────
plugin: javaparser

include:
  - com.example.api
  - com.example.spi
exclude:
  - com.example.api.internal

plugin_options:
  source_encoding: UTF-8
  compiler_source_level: "11"
---
# ── Document 2: fallback — regex-based parser ────────────────
plugin: java

include:
  - com.example.api
  - com.example.spi
exclude:
  - com.example.api.internal
```

Here both documents describe the **same** API surface.  If the
`javaparser` plugin is installed and the JDK is available, document 1 is
used.  Otherwise the CLI falls through to document 2 (`java`).

### Resolution rules

| # | Rule | Detail |
|---|------|--------|
| 1 | **Parse all documents** | `yaml.safe_load_all()` instead of `yaml.safe_load()`. |
| 2 | **Shared defaults** | A document with **no `plugin` key** (or `plugin: null`) is the *defaults document*.  Its keys are inherited by every candidate. At most one such document may exist; if absent, defaults are empty. |
| 3 | **Ordered candidate list** | Documents **with a `plugin` key** form an ordered list of candidates.  The same plugin name MAY appear more than once (e.g. different `include` scopes tried in order). |
| 4 | **First-match wins** | The CLI iterates candidates top-to-bottom.  For each candidate it checks: (a) is the plugin installed? (b) does `validate_path()` succeed?  The first candidate that passes both checks is selected. |
| 5 | **`--plugin` overrides** | `semver-dredd snapshot --plugin java` skips the priority walk and directly selects the first candidate whose `plugin` equals `java`.  If none matches, error. |
| 6 | **Single-document backward compat** | A file with one document and no `---` separators works exactly as today — the loader treats it as a combined defaults + single candidate. **No existing config breaks.** |

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

    # Multi-document: split into defaults + ordered candidates.
    defaults = {}
    candidates: list[dict] = []
    for doc in docs:
        if not isinstance(doc, dict):
            continue
        if "plugin" not in doc or doc["plugin"] is None:
            defaults = doc
        else:
            candidates.append(doc)

    return {"_defaults": defaults, "_candidates": candidates}
```

The existing `load_config()` gains an optional `plugin_name` parameter.
When `_candidates` is present and `plugin_name` is given, it finds the
first candidate matching that name and deep-merges with `_defaults`.
When `plugin_name` is `None`, it walks candidates in order, probing
each plugin for availability, and returns the first viable match merged
with `_defaults`.

### Polyglot repositories

A multi-document `.semver.yaml` describes **one API surface**, not an
entire repository.  Polyglot projects that expose multiple independent
API surfaces should place a **separate `.semver.yaml`** (and `VERSION`
file) in each surface's directory:

```
my-repo/
├── backend/
│   ├── .semver.yaml      ← Java API surface
│   ├── VERSION
│   └── src/main/java/…
├── sdk-python/
│   ├── .semver.yaml      ← Python SDK surface
│   ├── VERSION
│   └── mypackage/…
└── cli-go/
    ├── .semver.yaml      ← Go CLI surface
    ├── VERSION
    └── cmd/…
```

Each surface is versioned independently.  CI runs `semver-dredd` once
per directory:

```bash
cd backend      && semver-dredd snapshot
cd sdk-python   && semver-dredd snapshot
cd cli-go       && semver-dredd snapshot
```

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

### Plugin fallback chain

The user prefers `javaparser` but accepts `java` when no JDK is
available:

```yaml
# ── defaults ──────────────────────────────────────────────────
policies:
  allow_breaking_changes: false
---
# ── preferred: AST-based ─────────────────────────────────────
plugin: javaparser

include:
  - com.example.api
exclude:
  - com.example.api.internal

plugin_options:
  compiler_source_level: "11"
---
# ── fallback: regex-based ────────────────────────────────────
plugin: java

include:
  - com.example.api
exclude:
  - com.example.api.internal
```

```bash
semver-dredd snapshot          # auto-picks javaparser, falls back to java
semver-dredd snapshot --plugin java   # force the fallback
```

### Polyglot repo (one `.semver.yaml` per surface)

```
my-repo/
├── backend/
│   ├── .semver.yaml          ← javaparser → java fallback
│   └── VERSION
├── sdk-python/
│   ├── .semver.yaml          ← python only
│   └── VERSION
└── cli-go/
    ├── .semver.yaml          ← go only
    └── VERSION
```

```bash
# CI runs each surface independently
for dir in backend sdk-python cli-go; do
  (cd "$dir" && semver-dredd snapshot)
done
```

## Non-goals

* **Glob / regex engine in core** — plugins own their matching logic.
* **Automatic API-surface detection** — heuristics belong in plugins, not
  in the framework.
* **Enforcing a single syntax** — languages are too different for a
  universal pattern language to be practical.
* **Multiple API surfaces in one config** — each `.semver.yaml` describes
  exactly one API surface.  Polyglot repos use one config per directory.

# Configuration & Plugin API Evolution Proposal

## 1. Philosophy & Motivation

The goal of semver-dredd is to provide **language-agnostic** semantic versioning analysis. The core framework should handle the "mechanics" (config loading, snapshot diffing, change verification, report generation) while leaving the "understanding" of code and API surfaces strictly to plugins.

This proposal unifies several enhancements to the configuration and plugin system:
1.  **Flexible Scope**: Adding `include` / `exclude` to precisely define API surfaces.
2.  **Priority Chains**: Allowing fallback plugins (e.g., AST-based → regex-based) via multi-document config.
3.  **Future Proofing**: Ensuring the API supports non-code domains (CLI, REST, gRPC) without framework changes.
4.  **Aggregate Versioning**: A built-in `bundle` plugin for multi-surface repositories that ship a single release.

The guiding principle is **"Plugin Rules First"**. The framework extracts common structure (snapshots, diffs) but treats configuration constraints (paths, filters, options) as opaque data passed to the plugin.

---

## 2. Configuration Architecture

To support complex setups without config file proliferation, we evolve `.semver.yaml` into a **multi-document** structure.

### 2.1 Multi-document Priority Chain

A single API surface might be analysable by multiple plugins. For example, a user might prefer `javaparser` (AST-based, needs JDK) but accept `java` (regex-based, standalone) as a fallback.

`.semver.yaml` becomes a **list of plugin candidates** separated by `---`. The CLI walks this list top-to-bottom and finds the **first viable candidate** (plugin installed + `validate_path()` succeeds).

**Example `.semver.yaml`:**

```yaml
# ── Document 0: Shared Defaults ──────────────────────────────
# No `plugin` key → inherited by every candidate below.
policies:
  allow_breaking_changes: false
output:
  color: true
---
# ── Candidate 1: Preferred (AST-based) ───────────────────────
plugin: javaparser

include:
  - com.example.api
plugin_options:
  compiler_source_level: "11"
---
# ── Candidate 2: Fallback (Regex-based) ──────────────────────
plugin: java

include:
  - com.example.api
```

### 2.2 Polyglot Repositories (One Config Per Surface)

A multi-document config describes **one API surface**. Polyglot repositories with multiple independent artifacts (e.g., a Backend + a CLI + an SDK) must place a separate `.semver.yaml` and `VERSION` file in each surface's root.

```text
my-repo/
├── backend/
│   ├── .semver.yaml      ← Java API surface
│   └── VERSION
├── sdk-python/
│   ├── .semver.yaml      ← Python SDK surface
│   └── VERSION
└── cli/
    ├── .semver.yaml      ← Go CLI surface
    └── VERSION
```

CI runs `semver-dredd` independently in each directory.

### 2.3 Resolution Rules & Loader Logic

| # | Rule                       | Detail                                                                                                                          |
|---|----------------------------|---------------------------------------------------------------------------------------------------------------------------------|
| 1 | **Defaults Document**      | The first document with **no `plugin` key** is the *defaults*. Its keys are merged into every candidate.                        |
| 2 | **Candidate Selection**    | Documents **with a `plugin` key** form the candidate list. The CLI checks availability and `validate_path()` for each in order. |
| 3 | **`--plugin` Override**    | Passing `--plugin <name>` skips the priority walk and selects the first candidate matching that name.                           |
| 4 | **Backward Compatibility** | A single-document file works exactly as before (treated as a combined defaults + candidate).                                    |

---

## 3. Scope Definition: Include / Exclude

Plugins need to know *what* to analyse. We introduce `include` and `exclude` lists.

### 3.1 Format & Semantics

These are **flat lists of opaque strings**. The framework passes them to the plugin as-is.

```yaml
plugin: python
include:
  - mypackage.core
  - mypackage.utils
exclude:
  - mypackage.core._private
```

**Core Semantic Defaults:**
1.  **Plugin Interpretation**: Strings can be packages, directories, glob patterns, or module paths. The plugin decides.
2.  **Allow/Deny List**: If `include` is present, only matching items are analysed. `exclude` removes items from the set.
3.  **Recursive by Default**: Including a directory implies including its children.
4.  **Opaque Dependencies**: Plugins **should not** follow imports outside the included scope. External types are treated as opaque/compatible.

### 3.2 Recursive vs Non-recursive

Plugins may implement syntax to distinguish recursion if needed (e.g., `pkg` vs `pkg!`). This is plugin-specific behavior.

---

## 4. Advanced Configuration: `plugin_options`

To avoid polluting the top-level schema with every possible compiler flag or timeout setting, we add an **escape hatch**.

### 4.1 The Dictionary
`plugin_options` is a free-form dictionary forwarded directly to the plugin. The framework **never** validates its contents.

```yaml
# "Ugly but powerful"
plugin_options:
  source_encoding: "UTF-8"
  extra_classpath: ["/opt/libs/custom.jar"]
  allow_runtime_execution: true
  timeout_seconds: 30
```

### 4.2 Implementation Guidelines
- Plugins access this via `options.get("plugin_options")`.
- Plugins **must** silently ignore unknown keys (to allow sharing config between plugins if necessary).
- This is the place for "power user" features.

---

## 5. Domain Agnosticism: Beyond Libraries

Strategies for applying semver to CLI tools, REST APIs, gRPC, etc.

### 5.1 The "Room" for Plugins
The framework provides generic value objects (`SnapshotResult`, `DiffResult`, `ChangeKind`) but does **not** force a specific snapshot model (`NormalizedSnapshot` functions/types).

**Plugins are free to:**
1.  Define their own Snapshot class (e.g., `CliSnapshot` with `commands` instead of `functions`).
2.  Implement `Comparable` to define their own diff logic.
3.  Treat `path` as a resource string (file path, URL, connection string).

### 5.2 Traps & Guidance for Plugin Authors

| Challenge                    | Guidance                                                                                                                  |
|------------------------------|---------------------------------------------------------------------------------------------------------------------------|
| **Path is not a source dir** | Override `validate_path()`. It defaults to checking directory existence, but your plugin might need a file or a URL.      |
| **Runtime Introspection**    | If parsing `--help` or inspecting a live API, explicitly document security risks. Use `plugin_options` to gate execution. |
| **Breaking Changes**         | "Breaking" is domain-specific. A changed HTTP status code or a renamed CLI flag is breaking. Document your rules clearly. |

### 5.3 Framework Guarantees

To ensure plugins can evolve independently of the core:
- **`path`** is never interpreted by the framework (core won't crash if it's a URL).
- **`plugin_options`** is never inspected.
- **`DiffResult`** is the only required output contract.
- **`SnapshotFormat`** protocol is stable.

---

## 6. Aggregate Versioning: The `bundle` Plugin

Polyglot repositories (section 2.2) version each API surface independently.
But some projects also ship a **single bundle** — a release artifact that
bundles all surfaces together (an SDK, a Docker image, a distribution
tarball).  That bundle needs its own `VERSION`, and its bump must reflect
the **heaviest** change across all constituent surfaces.

### 6.1 The Problem

```text
my-repo/
├── backend/VERSION     1.2.0 → 1.3.0   (MINOR — new endpoint)
├── sdk-python/VERSION  2.0.1 → 2.0.2   (PATCH — bugfix)
├── cli/VERSION         0.9.0 → 1.0.0   (BREAKING — renamed command)
└── VERSION             ???              ← must become BREAKING
```

No existing plugin can handle this — it is not about analysing source
code, it is about **watching other VERSION files** and propagating the
worst-case bump.

### 6.2 Design: Blind Dependency Tracking

A **built-in** `bundle` plugin that:

1.  Reads a list of tracked `VERSION` files (configured via `include`).
2.  Produces a snapshot that is simply a map of dependency names →
    current version strings.
3.  Diffs old snapshot vs new: compares each dependency's semver to
    determine the per-dependency change kind.
4.  Returns the **maximum** `ChangeKind` across all dependencies.

It is "blind" — it knows nothing about Java, Python, or Go.  It only
reads version strings and compares them.

### 6.3 Configuration

```yaml
plugin: bundle

include:
  - ./backend/VERSION
  - ./sdk-python/VERSION
  - ./cli/VERSION
```

The `path` argument is unused (or points to the repo root).  All
information comes from `include`.

### 6.4 Snapshot Format

```yaml
snapshot_type_id: <BUNDLE_SNAPSHOT_UUID>
schema_version: 1
version: "3.5.0"
language: bundle
source:
  kind: aggregate
  path: .
api:
  dependencies:
    backend: "1.3.0"
    sdk-python: "2.0.2"
    cli: "1.0.0"
```

### 6.5 Diff Logic

For each tracked dependency, compare old version → new version:

| Old → New                    | Change kind |
|------------------------------|-------------|
| Major bumped (1.x → 2.x)     | BREAKING    |
| Minor bumped (1.2.x → 1.3.x) | MINOR       |
| Patch bumped (1.2.3 → 1.2.4) | PATCH       |
| No change                    | NONE        |
| Dependency removed           | BREAKING    |
| Dependency added             | MINOR       |

The aggregate result is `max(all per-dependency change kinds)`.

### 6.6 Workflow

```bash
# 1. Run each surface
(cd backend     && semver-dredd bump)
(cd sdk-python  && semver-dredd bump)
(cd cli         && semver-dredd bump)

# 2. Run the bundle — reads the VERSION files written above
semver-dredd bump   # uses plugin: bundle from .semver.yaml
```

The bundle plugin fits naturally into CI pipelines:  individual surface
jobs run first, then a final job runs the bundle bump.

### 6.7 Why Built-in

This plugin ships with the core because:
- It depends on **no** external tooling (no compilers, no parsers).
- It solves a problem that arises directly from the polyglot repository
  pattern the framework itself encourages (section 2.2).
- Its snapshot format and diff logic are trivial and stable.
- Third-party plugins should not need to reinvent semver comparison.

---

## 7. Non-goals

* **Universal Globbing**: We will not write a regex engine in the core. Pattern matching belongs in plugins.
* **Automatic Detection**: We will not try to guess "public API" surfaces using heuristics in the framework.
* **Cross-document Inheritance**: Plugin documents in the yaml are independent (except for shared defaults). One plugin config cannot inherit from another.
* **Mixed-Surface Configs**: One `.semver.yaml` per API surface. No defining Java and Python APIs in a single file unless they are fallbacks for the same surface.

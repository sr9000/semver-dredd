# Include/Exclude Proposal — Implementation Status Report

**Date**: 2026-06-14
**Reviewer**: semver-dredd automated review
**Source document**: `INCLUDE-EXCLUDE-PROPOSAL.md` (June 2026 draft)

---

## 1. Executive Summary

Three of six proposal features are fully implemented in the current codebase; the
remaining three are accurately marked as proposed/unimplemented. The
framework-level plumbing is complete end-to-end — configuration values are parsed,
stored, and forwarded to plugins correctly. What remains is either
**plugin-specific consumption** of those values or **entirely additive** features
(multi-document YAML, bundle plugin) that require no changes to existing code.

The proposal's own status table is **accurate and up to date**.

---

## 2. Per-Feature Verification

### 2.1 `include` / `exclude` Config Plumbing (Proposal §3)

**Status: ✅ Implemented**

**Evidence:**

| Layer | File | What it does |
|-------|------|--------------|
| Parsing | `cli/config.py:274-275` | `_parse_str_list(merged.get("include"))` and same for `exclude` — reads flat lists from `.semver.yaml` |
| Storage | `cli/config.py:54-55` | `Config` dataclass fields `include: list[str]`, `exclude: list[str]` |
| Forwarding | `cli/config.py:73-86` | `Config.snapshot_options()` builds `{"include": [...], "exclude": [...]}` only when non-empty |
| CLI injection | `cli/config.py:337-338` | `apply_config_defaults()` sets `args.snapshot_options` |
| Plugin delivery | `cli/utils.py:145-165` | `_generate_snapshot_yaml(extra_options=...)` merges into `options` dict; passed to `plugin.generate_snapshot(path, version, options=options)` |

**Assessment:** The entire data path from `.semver.yaml` → plugin `options` dict is
functional. Plugins receive `include` and `exclude` keys when configured.

---

### 2.2 `plugin_options` Escape Hatch (Proposal §4)

**Status: ✅ Implemented**

**Evidence:**

| Layer | File | What it does |
|-------|------|--------------|
| Parsing | `cli/config.py:276-279` | Reads `plugin_options` as a dict; silently defaults to `{}` when missing or non-dict |
| Storage | `cli/config.py:58` | `Config.plugin_options: dict[str, Any]` |
| Forwarding | `cli/config.py:84-85` | `snapshot_options()` includes `"plugin_options": dict(self.plugin_options)` when non-empty |

**Assessment:** Correctly opaque — the framework never validates or inspects
contents. Plugins receive `options["plugin_options"]` as-is when configured.

---

### 2.3 Plugin-Side Interpretation of `include`/`exclude` (Proposal §3.1)

**Status: 🚧 Not Implemented**

**Evidence — all three bundled plugins accept `options` but ignore scope keys:**

| Plugin | File | `options` usage |
|--------|------|-----------------|
| Python | `plugins/python-3.10-dredd/semver_dredd_python/plugin.py:473-484` | `options` parameter received, never read. Iterates `dir(module)` unfiltered. |
| Go | `plugins/go-1.20-dredd/semver_dredd_go/plugin.py:333-379` | `options` parameter received, passed to nothing. Parser analyzes all `.go` files in the directory. |
| Java | `plugins/java-1.8-dredd/semver_dredd_java/plugin.py:355-399` | `options` parameter received, passed to nothing. Parser analyzes all `.java` files recursively. |

**What's needed:**

- **Python plugin**: Filter `dir(module)` results by `obj.__module__` prefix matching against `include` patterns; exclude `_private` subpackages matching `exclude`.
- **Go plugin**: Pass include/exclude strings to the Go parser CLI (`--include`, `--exclude` flags) and filter at the AST level.
- **Java plugin**: Pass package filters to the Java parser; filter classes by fully-qualified package name.

---

### 2.4 Multi-Document Priority Chain (Proposal §2)

**Status: 🚧 Not Implemented**

**Evidence:**

- `cli/config.py:159-161` uses `yaml.safe_load(f)` — a single-document loader.
- No usage of `yaml.safe_load_all()` anywhere in the codebase.
- No candidate-selection loop, no defaults-document merging logic.

**What's needed:**

1. Replace `yaml.safe_load` with `yaml.safe_load_all` to yield multiple documents.
2. Identify the defaults document (first doc with no `plugin` key) per §2.3 rule 1.
3. Iterate candidate documents (those with `plugin` key), merge defaults, and call `validate_path()` on each in order.
4. Support `--plugin <name>` CLI override to skip the priority walk (§2.3 rule 3).
5. Maintain backward compatibility: single-document files continue to work unchanged (§2.3 rule 4).

---

### 2.5 Domain Agnosticism (Proposal §5)

**Status: ✅ Already True of Current API**

**Evidence:**

| Constraint | How it's satisfied |
|-----------|--------------------|
| `path` is never interpreted by framework | `LanguagePlugin.validate_path()` and `generate_snapshot()` treat it as an opaque string. Framework never checks file type, URL format, etc. |
| `plugin_options` is never inspected | `cli/config.py` stores as raw dict, forwards opaquely |
| `DiffResult` is the only required output | `LanguagePlugin.generate_snapshot()` returns `SnapshotResult`; diff logic is delegated to the snapshot class via `Comparable.diff_against()` |
| `SnapshotFormat` protocol is stable | `snapshot/protocols.py` defines `to_yaml`, `from_yaml_str`, `from_file`, `to_dict` — no framework-level assumptions about content |
| Plugins can define custom snapshot classes | `LanguagePlugin.snapshot_format_class` property (line 66-73 of `plugin_base.py`) returns `None` for default `NormalizedSnapshot` or a custom class |

**Assessment:** No framework changes needed. The architecture already supports
non-code domains (CLI tools, REST APIs, gRPC) through custom plugins.

---

### 2.6 Aggregate `bundle` Plugin (Proposal §6)

**Status: 🚧 Not Implemented**

**Evidence:**

- No `bundle` plugin class, module, or package exists in the repository.
- No `bundle` entry point in any `pyproject.toml`.
- No `BundleSnapshot` class or semver-comparison aggregation logic.
- `semver-dredd plugin list` would not show a `bundle` entry.

**What's needed:**

1. Create a built-in plugin (proposal §6.7 argues it should ship with core, not as a separate package).
2. Implement `BundlePlugin(LanguagePlugin)` with `name = "bundle"`.
3. `generate_snapshot()` reads VERSION files listed in `options["include"]`, builds a `BundleSnapshot` mapping dependency names → version strings.
4. `BundleSnapshot.diff_against()` compares each dependency's semver (old vs new) and returns `max(all per-dependency ChangeKind)` per §6.5 rules.
5. Register as entry point `bundle = "semverdredd.bundle_plugin:BundlePlugin"`.

---

## 3. Forwarding Chain Verification

The complete data flow from configuration to plugin is:

```
.semver.yaml
  │
  │  include:
  │    - mypackage.core
  │  exclude:
  │    - mypackage.core._private
  │  plugin_options:
  │    timeout_seconds: 30
  │
  ▼
cli/config.py :: load_config()
  │  _parse_str_list(merged.get("include"))   → Config.include
  │  _parse_str_list(merged.get("exclude"))   → Config.exclude
  │  merged.get("plugin_options")             → Config.plugin_options
  │
  ▼
Config.snapshot_options()
  │  returns: {
  │    "include": ["mypackage.core"],
  │    "exclude": ["mypackage.core._private"],
  │    "plugin_options": {"timeout_seconds": 30}
  │  }
  │
  ▼
apply_config_defaults(args, config)
  │  args.snapshot_options = config.snapshot_options()
  │
  ▼
cli/utils.py :: _generate_snapshot_yaml(extra_options=args.snapshot_options)
  │  options = {"use_color": use_color}
  │  options.update(extra_options)   ← merges include/exclude/plugin_options
  │
  ▼
plugin.generate_snapshot(path, version, options=options)
  │  Plugin receives the full options dict
  │  (currently ignores include/exclude/plugin_options)
```

**Verdict:** The pipeline is end-to-end functional. The gap is solely in
plugin-side consumption.

---

## 4. Programmatic API

The programmatic API (`semverdredd.compare`, `semverdredd.compare_and_suggest`)
also supports forwarding options:

```python
result = compare(
    "mymodule.v1", "mymodule.v2",
    plugin="python",
    options={"include": ["mymodule.core"], "plugin_options": {"x": 1}},
    ...
)
```

This is documented in `README.md` and works correctly — the `options` parameter
is passed through to `plugin.generate_snapshot()`.

---

## 5. Summary Table

| # | Feature | Proposal Status | Verified Status | Notes |
|---|---------|----------------|-----------------|-------|
| §3 | `include`/`exclude` plumbing | ✅ Implemented | ✅ **Confirmed** | Full pipeline works |
| §4 | `plugin_options` escape hatch | ✅ Implemented | ✅ **Confirmed** | Opaque forwarding correct |
| §3.1 | Plugin-side filtering | 🚧 Proposed | 🚧 **Confirmed** | All 3 plugins ignore keys |
| §2 | Multi-document YAML | 🚧 Proposed | 🚧 **Confirmed** | Single-doc only (`safe_load`) |
| §5 | Domain agnosticism | ✅ Already true | ✅ **Confirmed** | No framework constraints |
| §6 | Bundle plugin | 🚧 Proposed | 🚧 **Confirmed** | Not present at all |

**Accuracy of proposal's own status table: 6/6 correct.**

---

## 6. Recommendations

### Priority 1 — Plugin-Side Filtering (§3.1)

This is the highest-value remaining feature. The framework plumbing exists;
only plugin logic is needed. Suggested order:

1. **Python plugin** — easiest to implement using `obj.__module__` prefix
   matching. Add `_matches_scope(obj_module, include, exclude)` helper.
2. **Java plugin** — pass `--include`/`--exclude` flags to `main.java`, filter
   classes by package name during parsing.
3. **Go plugin** — pass flags to the Go parser, filter at the AST package level.

Each plugin should document its interpretation of include/exclude strings
(package names for Python/Java, directory paths for Go).

### Priority 2 — Multi-Document YAML (§2)

Enables fallback-plugin chains (e.g., `javaparser` → `java`). Requires:

- `yaml.safe_load_all` integration
- Candidate selection loop with `validate_path()` fallback
- Defaults-document merge logic
- Backward compatibility: single-doc files must continue working

### Priority 3 — Bundle Plugin (§6)

Lowest urgency but architecturally clean. Should be a built-in plugin in
`semverdredd/` rather than a separate pip package, per the proposal's reasoning
in §6.7. Implementation is straightforward: read VERSION files, compare semver
strings, return max ChangeKind.

---

## 7. Conclusion

The `INCLUDE-EXCLUDE-PROPOSAL.md` document is an **accurate and well-maintained**
specification. Its status table correctly reflects the current state of the
codebase. The framework-level foundations are solid; the remaining work is
incremental and can be prioritized independently.
# Current State vs. Plugin Roadmap — Comparison

## Overall: All 7 phases are substantially implemented ✅

---

## Phase 1: Core Plugin Infrastructure — ✅ DONE (enhanced)

| Roadmap item | Status | Notes |
|---|---|---|
| `semverdredd/plugin_base.py` — `LanguagePlugin` ABC + `SnapshotResult` | ✅ Done | Extra hooks added: `snapshot_format_class` + `diff_scorer` (not in spec) |
| `semverdredd/plugin_manager.py` — `PluginManager` with entry-points + user dir | ✅ Done | Richer than spec: adds `PluginInfo` dataclass; `list_plugins()` returns `list[PluginInfo]` not `list[LanguagePlugin]` |
| `pyproject.toml` transition entry-points | ⚠️ Not done | Spec said to add `[project.entry-points."semver_dredd.plugins"]` during transition; omitted intentionally because plugin_manager does direct-import fallback |
| `semverdredd/registry.py` — UUID snapshot type registry | ➕ Extra | Not in roadmap but implemented; needed for multi-format snapshot dispatch |

---

## Phase 2: Python Plugin Extraction — ✅ DONE (well beyond spec)

| Roadmap item | Status | Notes |
|---|---|---|
| `plugins/semver-dredd-python/semver_dredd_python/plugin.py` | ✅ Done | 551 lines vs ~90 in spec; adds `PythonArgument`, `PythonSnapshot`, full introspection |
| `plugins/semver-dredd-python/pyproject.toml` | ✅ Done | Name is `semver-dredd-python` (simpler form, explicitly permitted by roadmap) |
| Entry-point `python = "semver_dredd_python:PythonPlugin"` | ✅ Done | |

---

## Phase 3: Go Plugin Extraction — ✅ DONE

| Roadmap item | Status | Notes |
|---|---|---|
| `plugins/semver-dredd-go/semver_dredd_go/plugin.py` | ✅ Done | Matches spec |
| `plugins/semver-dredd-go/pyproject.toml` | ✅ Done | Name `semver-dredd-go` (simpler form) |
| Bundled Go parser source in `semver_dredd_go/parser/` | ✅ Done | |

---

## Phase 4: Java Plugin Extraction — ✅ DONE

| Roadmap item | Status | Notes |
|---|---|---|
| `plugins/semver-dredd-java/semver_dredd_java/plugin.py` | ✅ Done | Matches spec |
| `plugins/semver-dredd-java/pyproject.toml` | ✅ Done | Name `semver-dredd-java` (simpler form) |
| Bundled Java parser + snakeyaml JAR | ✅ Done | |

---

## Phase 5: CLI Plugin Management — ✅ DONE (integrated, not split)

| Roadmap item | Status | Notes |
|---|---|---|
| `plugin list` command | ✅ Done | In `cli/__init__.py:cmd_plugin_list` |
| `plugin install` command | ✅ Done | In `cli/__init__.py:cmd_plugin_install` |
| `plugin remove` command | ✅ Done | In `cli/__init__.py:cmd_plugin_remove` |
| `plugin info` command | ✅ Done | In `cli/__init__.py:cmd_plugin_info` |
| **`cli/commands/plugin.py`** (separate file per target arch) | ❌ Not done | All plugin commands are inline in `cli/__init__.py` (1 257 lines total) |

---

## Phase 6: Programmatic API Update — ✅ DONE

| Roadmap item | Status | Notes |
|---|---|---|
| Export `LanguagePlugin`, `SnapshotResult`, `PluginManager`, `get_plugin`, `list_plugins` from `semverdredd` | ✅ Done | Also exports `SnapshotRegistry`, `DefaultDiffScorer`, `DiffScorer`, `DiffResult`, `SnapshotFormat` |
| `compare()` / `compare_and_suggest()` work with any plugin | ✅ Done | |

---

## Phase 7: Migration and Cleanup — ✅ MOSTLY DONE

| Roadmap item | Status | Notes |
|---|---|---|
| Plugin packages as separate installable packages | ✅ Done | |
| `semver-dredd-all` meta-package | ✅ Done | Uses simple names |
| Move parser sources out of core | ✅ Done | `parser/` lives inside each plugin package |
| Update documentation | ⚠️ Partial | README updated but docs/schema.md may lag |

---

## Target Directory Structure Gaps

Roadmap's final `semverdredd/` layout vs. what exists:

| File | Roadmap | Exists? | Notes |
|---|---|---|---|
| `__init__.py` | ✅ | ✅ | |
| `plugin_base.py` | ✅ | ✅ | |
| `plugin_manager.py` | ✅ | ✅ | |
| `diff.py` | ✅ | ✅ | |
| **`xldiff.py`** | ✅ in spec | ❌ Missing | Listed in target arch but `diff.py` already covers cross-language diff; likely a stale reference |
| **`snapshot_schema.py`** | ✅ in spec | ❌ Missing | Replaced by top-level `snapshot/` package (better design) |
| `snapshot.py` | ✅ | ✅ | But contains **legacy Python-centric** `APISnapshot`/`SourceInfo` classes that were never cleaned up |
| `snapshot_io.py` | ✅ | ✅ | |
| `version.py` | ✅ | ✅ | |
| `result.py` | ✅ | ✅ | |
| **`python_api.py`** | ❌ not in spec | ✅ Present | 260 lines of Python-specific `ModuleAPI`/`ClassAPI` — belongs in the Python plugin, not core |

Roadmap's final `cli/` layout vs. what exists:

| Path | Roadmap | Exists? | Notes |
|---|---|---|---|
| `cli/__init__.py` | ✅ | ✅ | 1 257 lines — very large |
| `cli/config.py` | ✅ | ✅ | |
| **`cli/commands/__init__.py`** | ✅ in spec | ❌ Missing | |
| **`cli/commands/compare.py`** | ✅ in spec | ❌ Missing | Commands are inline in `cli/__init__.py` |
| **`cli/commands/status.py`** | ✅ in spec | ❌ Missing | |
| **`cli/commands/bake.py`** | ✅ in spec | ❌ Missing | |
| **`cli/commands/init.py`** | ✅ in spec | ❌ Missing | |
| **`cli/commands/plugin.py`** | ✅ in spec | ❌ Missing | |

Plugin directory naming:

| Roadmap preferred name | Actual name |
|---|---|
| `plugins/python-3.10-core-1.0.0/` | `plugins/semver-dredd-python/` |
| `plugins/go-1.20-gogen-1.0.0/` | `plugins/semver-dredd-go/` |
| `plugins/java-17-acme-1.0.0/` | `plugins/semver-dredd-java/` |

Roadmap explicitly permits this simpler backwards-compatible form, so this is fine.

---

## Extra items not in roadmap (enhancements)

| Item | Description |
|---|---|
| `snapshot/` top-level package (1 016 lines) | Full snapshot type system: `models.py`, `protocols.py`, `change_kind.py`, `predefined/` — far richer than anything in the roadmap |
| `semverdredd/registry.py` | UUID-based snapshot type registry for multi-format YAML dispatch |
| `snapshot_format_class` / `diff_scorer` hooks on `LanguagePlugin` | Allows plugins to supply custom snapshot types and diff logic |
| `PluginInfo` dataclass | Tracks origin (`entry_point` / `builtin` / `manual`) per plugin |
| `Comparable` protocol | Snapshots can diff themselves; engine doesn't need to know their structure |
| `snapshot/predefined/` | Reusable cross-language primitives (Variable, Function, ClassField, ClassMethod, Argument) |

---

## Pending cleanup tasks (roadmap intent, not yet done)

1. **`semverdredd/python_api.py`** — 260 lines of Python-specific introspection code in the *core* package. Violates the "Python is just a plugin" principle. Should move into `plugins/semver-dredd-python/`.

2. **`semverdredd/snapshot.py`** — Contains a Python-centric `APISnapshot` class that duplicates what the Python plugin already provides via `PythonSnapshot`. Likely legacy; the `save_version_file` helper it exports is still used by the CLI.

3. **`cli/commands/` split** — `cli/__init__.py` is 1 257 lines. Roadmap's final structure shows splitting into `commands/compare.py`, `commands/status.py`, `commands/bake.py`, `commands/init.py`, `commands/plugin.py`.

4. **`semverdredd/xldiff.py`** — Listed in target architecture but never created. Either the name should be added as an alias/re-export of `diff.py`, or the target architecture should be updated to drop it.

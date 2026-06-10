# semver-dredd — Repository Review

**Date:** June 10, 2026
**Scope:** Usability and extensibility of the tool
**Reviewer:** Automated code review (GitHub Copilot)

> **Resolution status (June 10, 2026):** most findings below have since been
> addressed — see `plans/improve-and-smoke-tests.md` for the commit-by-commit
> record. In particular:
>
> | Finding | Status |
> |---------|--------|
> | Silent config failures (§2.2) | ✅ Fixed — malformed `.semver.yaml` warns on stderr |
> | `include`/`exclude`/`plugin_options` not implemented (§4) | ✅ Plumbed through config → plugins (plugin-side filtering still pending) |
> | `compare()` hardcodes `"0.0.0"` (§2.2) | ✅ Fixed — real versions threaded through |
> | Non-pluggable patch scheme (§2.2) | ✅ Fixed — `versioning.patch_scheme: date\|integer` |
> | Fragile plugin removal (§2.2) | ✅ Fixed — manifest-tracked install/remove |
> | Silent `SNAPSHOT_TYPE_ID` conflicts (§3.2) | ✅ Fixed — visible warnings |
> | Built-in plugins hardcoded in core (§3.2) | ✅ Fixed — entry points preferred, list is a dev fallback |
> | Docs oversell unimplemented features (§4) | ✅ Fixed — status banners in proposal + README |
> | `snapshot` vs `semverdredd.models` home confusion (§3.2) | ⬜ Still open |
> | No plugin compat check (§3.2) | ⬜ Still open |

---

## 1. Executive Summary

semver-dredd is a language-agnostic semantic-versioning analyzer that detects
API changes (BREAKING / MINOR / PATCH / NONE) and suggests version bumps. It
ships a clean plugin architecture (Python, Go, Java) discovered via entry
points, a layered configuration system, and both a CLI and a programmatic API.

Overall the project is **well-architected and pleasant to extend**, with a
crisp separation between the "mechanics" (core engine) and the "understanding"
(language plugins). The main weaknesses are (a) a noticeable gap between
documented/proposed features and what is actually implemented, (b) a few
fragile spots in plugin install/removal, and (c) some opinionated defaults
(date-based patch numbers) that may surprise users.

| Dimension      | Rating (1–5) | One-line verdict                                            |
|----------------|:------------:|-------------------------------------------------------------|
| Usability      |     3.5      | Rich CLI & docs, but some sharp edges and opinionated rules |
| Extensibility  |     4.5      | Excellent plugin contracts; minor coupling in the core      |
| Documentation  |     4.0      | Strong README/HOWTO, but oversells unimplemented features   |

---

## 2. Usability

### 2.1 Pros

- **Comprehensive CLI surface.** A full set of subcommands covers the whole
  workflow: `init`, `status`, `bake`, `compare`, `snapshot`, `bump`, `patch`,
  `template`, and `plugin` (`cli/__init__.py`). The verbs map cleanly to a
  real release workflow (init → develop → status → bake).
- **Layered configuration with clear precedence.** `.semver.yaml` < `.env` <
  environment variables < CLI flags is implemented and documented
  (`cli/config.py`, `load_config` / `apply_config_defaults`). This is exactly
  what CI users expect and is rare to get right.
- **Good first-run ergonomics.** `template` emits a heavily-commented
  `.semver.yaml`, and `init` scaffolds `baked.yaml` + `VERSION` so users are
  not staring at a blank page.
- **Strong documentation.** `README.md` is thorough (commands, env vars, exit
  codes, workflow), and `HOWTO.md` is an excellent, concrete plugin-authoring
  guide.
- **Predictable automation contract.** Dedicated exit codes (`0` success,
  `1` error, `10` breaking-not-allowed) make CI gating trivial.
- **Programmatic API.** `compare()` / `compare_and_suggest()` return structured
  dataclasses (`CompareResult`, `SuggestVersionResult`) and deliberately ignore
  config files — a clean, embeddable contract.
- **Color handling.** Every command exposes `--color/--no-color` with
  auto-detection (`color: null`), which is friendly for both terminals and logs.

### 2.2 Cons

- **Opinionated, non-standard patch scheme.** Patches are
  `YYYYMMDDZZZ` date numbers rather than conventional incrementing integers.
  This is unusual, not strict-SemVer-friendly for downstream tooling, and is
  baked into the core rather than being a pluggable policy.
- **`compare` discards version context.** In `semverdredd/__init__.py`,
  `compare()` generates both snapshots with a hardcoded `"0.0.0"` version. It
  works because only the API surface is diffed, but it is a confusing smell and
  prevents version-aware plugins from doing anything useful.
- **Fragile plugin removal.** `cmd_plugin_remove` (`cli/commands/plugin.py`) is
  explicitly "best-effort" — it guesses directory/dist-info names with glob
  patterns and cannot remove system-installed plugins. Users can easily end up
  in a half-removed state.
- **`--target` install + `sys.path` injection.** `plugin install` installs into
  `~/.semver-dredd/plugins` via `pip --target` and the manager prepends that to
  `sys.path` (`plugin_manager.load_plugins`). This bypasses normal environment
  isolation and can cause dependency/version conflicts that are hard to debug.
- **Silent config failures.** `_load_yaml_config` swallows all exceptions and
  returns `{}` on any parse error (`cli/config.py`). A malformed `.semver.yaml`
  is silently ignored rather than reported, which can mask user mistakes.
- **Minimal `.env` parser.** The hand-rolled parser explicitly does not support
  escapes/multiline and ignores I/O errors silently — fine for simple cases,
  surprising for complex ones.
- **`module` argument is overloaded.** The same positional means "module name"
  for Python but "path" for Go/Java; help text repeats the caveat everywhere
  rather than the tool resolving it.

---

## 3. Extensibility

### 3.1 Pros

- **Clean plugin ABC.** `LanguagePlugin` (`semverdredd/plugin_base.py`) requires
  only `name` and `generate_snapshot()`; everything else
  (`version`, `description`, `display_name`, `validate_path`,
  `snapshot_format_class`) has sensible defaults. The barrier to a new plugin is
  genuinely low.
- **Entry-point discovery.** Plugins register under the
  `semver_dredd.plugins` group and are auto-discovered after `pip install`,
  with **no core code changes** required (`plugin_manager.py`). This is the
  right, idiomatic Python extension model.
- **Pluggable snapshot formats.** The `SnapshotFormat` + `Comparable` protocols
  (`snapshot/protocols.py`) let a plugin define its own data model and its own
  diff logic, while the core only depends on `DiffResult`
  (`change_kind` + descriptions). This cleanly supports non-code domains
  (CLI/REST/gRPC) described in the proposal.
- **UUID-based type registry.** `SnapshotRegistry` (`semverdredd/registry.py`)
  dispatches deserialization by `snapshot_type_id`, with graceful fallback to
  `NormalizedSnapshot`. This makes YAML snapshots self-describing and
  forward/backward compatible.
- **Reusable building blocks.** `snapshot/predefined/` provides immutable,
  pre-registered components (`Argument`, `Function`, `ClassField`,
  `ClassMethod`, …) so plugin authors can model an API surface without
  reinventing primitives.
- **Composable diff.** `NormalizedSnapshot.diff_against` delegates down to
  `TypeDefinition` and `FunctionSignature` (`snapshot/models.py`), so the diff
  rules are localized and easy to reason about.
- **Robustness to broken plugins.** Discovery wraps each plugin load in
  try/except and guards against partially-imported (circular) modules, so one
  bad plugin does not crash the tool.

### 3.2 Cons

- **Built-in plugins hardcoded in the core.** `plugin_manager.py` carries an
  explicit `_builtin_specs` list for `python`/`go`/`java`. This couples the
  "language-agnostic" core to specific plugin module names and undercuts the
  pure entry-point story.
- **Circular-import workarounds signal fragility.** Both the builtin loader and
  the entry-point loader contain logic to skip "partially-loaded" modules, and
  `semverdredd/__init__.py` documents why eager loading was removed. It works,
  but it is delicate and easy to regress.
- **Misleading module-home comments.** `snapshot/models.py` claims "canonical
  home is `semverdredd.models`" and `registry.py` repeats that the canonical
  code "currently lives under the top-level `snapshot` package." The
  intended/actual home is inconsistent, which will confuse future contributors.
- **No formal plugin versioning/compat check.** The core never validates that a
  plugin targets a compatible core API version; a stale third-party plugin can
  fail in obscure ways at snapshot/diff time.
- **`snapshot_format_class` registration is silent on conflict.** UUID
  collisions raise inside `register()`, but the manager catches and only
  `debug`-logs the failure (`load_plugins`), so two plugins sharing a UUID fail
  invisibly.

---

## 4. Documentation vs. Implementation Gap

The repo ships an ambitious `INCLUDE-EXCLUDE-PROPOSAL.md`, but a code audit
shows several headline features are **not yet implemented**:

| Proposed feature                          | Status        | Evidence                                                                 |
|-------------------------------------------|---------------|--------------------------------------------------------------------------|
| `include` / `exclude` scope lists         | Not implemented | No handling in `cli/config.py`; only appears in template comments        |
| Multi-document `.semver.yaml` (`---`) chain | Not implemented | `_load_yaml_config` uses `yaml.safe_load` (single doc), no candidate walk |
| `plugin_options` escape hatch             | Not implemented | Never read; `generate_snapshot(options=...)` is always called with `None` |
| Built-in `bundle` plugin                  | Not implemented | No `bundle` plugin anywhere; only doc references                          |
| Priority-chain plugin fallback            | Not implemented | `apply_config_defaults` resolves a single `plugin` string                 |

This is the single biggest usability risk: a reader of the docs/proposal could
reasonably expect these features to exist. Recommendation: clearly mark the
proposal as "design / not yet shipped," or implement a subset.

---

## 5. Recommendations (Prioritized)

1. **Reconcile docs with reality.** Add a "Status: proposed" banner to
   `INCLUDE-EXCLUDE-PROPOSAL.md` and note in `README.md` which features are
   live. (Low effort, high trust payoff.)
2. **Implement `include`/`exclude` + `plugin_options` plumbing.** These are
   small, additive config fields that unlock most of the proposal's value and
   are already documented in the template.
3. **Make patch scheme pluggable.** Allow a conventional integer patch mode via
   config so downstream SemVer tooling interoperates.
4. **Harden plugin lifecycle.** Replace best-effort glob removal with a
   manifest of installed plugins; surface install/remove conflicts loudly.
5. **Surface config errors.** Log a warning (not silence) when `.semver.yaml`
   fails to parse.
6. **Resolve the `snapshot` vs `semverdredd.models` home.** Pick one canonical
   location and update the shim comments to remove contributor confusion.
7. **Decouple built-in plugins.** Prefer entry points for python/go/java and
   keep the hardcoded list only as a dev/editable-install fallback.

---

## 6. Conclusion

semver-dredd's **extensibility is its standout strength** — the plugin ABC,
protocol-based snapshot formats, and UUID registry form a genuinely clean,
language-agnostic foundation. **Usability is solid but uneven**: the CLI, config
layering, and docs are strong, while opinionated versioning, fragile plugin
management, and an oversold feature set are the main friction points. Closing
the doc-vs-code gap and hardening the plugin lifecycle would move this from a
promising tool to a polished one.

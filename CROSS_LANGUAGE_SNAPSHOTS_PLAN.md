# Cross-language snapshots plan (Go + Java + Python)

This doc is a product+engineering plan for extending **semver-dredd** from “Python-only semver inference” into a **cross-language API snapshot + diff + policy gate** tool.

> Goal: in repos where you *can’t* access older versions of the code, semver-dredd should still work by comparing **`baked.yaml` (baseline)** vs **a newly generated snapshot** (current code), producing:
>
>- `current.yaml` (snapshot of current API + suggested next version)
>- `VERSION` (plain text current version)
>- CLI output (human) and programmatic result (pure data)

---

## TL;DR scope

- **Already built** (current repo state):
  - Python snapshot format (`baked.yaml` / `current.yaml`) for Python modules.
  - CLI: `init`, `status`, `bake` for Python.
  - Go parser (native): emits a baked.yaml-like YAML including types.
  - Java parser (native, lightweight): emits a baked.yaml-like YAML including types.
  - CLI: `snapshot` command to run the Go/Java parser.

- **Missing** (this plan):
  1) A stable **cross-language snapshot schema** (documented + versioned)
  2) A Python-side **loader + normalizer** for Go/Java-produced YAML
  3) A **snapshot-to-snapshot diff engine** that understands type/signature changes
  4) A **change-type classifier** (NONE/PATCH/MINOR/MAJOR) based on diff rules
  5) CLI wiring to use snapshots for `status`/`bake` in Go/Java repos
  6) Tests + fixtures for Go/Java snapshots and diffs

---

## Design principles

- **Don’t parse “implementation”**: parse only “public API surface”.
- **Same output for all languages**: a single YAML schema so diffs are consistent.
- **Stable keys**: identify API items in a way that is deterministic (name + owner + kind).
- **Type-aware but pragmatic**:
  - we store type strings as emitted by the language parser
  - we normalize where possible (e.g. whitespace)
  - we do not attempt full type-system equivalence across languages (yet)
- **Strict where it matters**:
  - removing API items is MAJOR
  - making params *more required* is MAJOR
  - changing param/return types is MAJOR (with optional escape hatch later)

---

## Snapshot schema proposal (Schema v2)

### File-level

```yaml
schema_version: 2
version: 1.2.20260214001
language: python|go|java
source:
  # Optional: points to what was analyzed
  kind: module|package|directory
  path: "src/mylib"  # user-supplied
api:
  functions: { ... }
  types: { ... }
```

### Functions

Keyed by a stable identifier. Recommended:
- Python: `funcName`
- Go: `FuncName`
- Java static: `TypeName.method`

```yaml
api:
  functions:
    Area:
      parameters:
        - name: w
          type: int
          optional: false
        - name: h
          type: int
          optional: false
      returns:
        - name: ""
          type: int
          optional: false
```

### Types (classes / structs / records)

Key: type name (or fully-qualified later).

```yaml
api:
  types:
    Point:
      fields:
        - name: x
          type: float
          optional: false
      methods:
        Distance:
          parameters: [...]
          returns: [...]
```

Notes:
- `optional` is **best-effort**; semantics differ per language.
- For Python, we may not reliably infer field types—use `type: "unknown"` unless available.

---

## Diff model (cross-language)

Define a diff output (pure data) that can be rendered to CLI and used to classify changes.

### Diff categories

- **Breaking** (MAJOR)
  - function removed
  - type removed
  - method removed
  - field removed
  - signature change that reduces compatibility:
    - parameter removed or re-ordered
    - parameter changed from optional→required
    - parameter type changed
    - return type changed

- **Additive** (MINOR)
  - new function/type/method/field
  - signature change that expands compatibility:
    - new optional param

- **Patch-only** (PATCH)
  - if snapshots identical but user indicates implementation changed (hard offline)
  - in offline snapshot mode, PATCH basically means “no API changes”

---

## TODO checklist (implementation tasks)

### Milestone 0 — Spec + repo hygiene ✅

- [x] Add `docs/schema.md` describing snapshot schema v2 (with examples per language)
- [x] Add `schema_version` field to Go parser output
- [x] Add `schema_version` field to Java parser output
- [x] Extend Python snapshot writer (`semverdredd/snapshot.py`) to emit `schema_version`, `language`, `source`
- [x] Keep backward compatibility: load schema v1 and upgrade in-memory

Deliverable:
- Clear contract for snapshot I/O and a migration story.

---

### Milestone 1 — Python-side snapshot loader/normalizer ✅

- [x] Implement `semverdredd/snapshot_io.py`:
  - `load_snapshot(path) -> NormalizedSnapshot`
  - Accept schema v1 and v2
  - Normalize ordering (sort) and trivial type whitespace

- [x] Define a normalized in-memory structure:
  - `Snapshot(version: str, language: str, functions: dict, types: dict)`

- [x] Add tests for:
  - parsing existing Python `baked.yaml`
  - parsing Go parser output YAML
  - parsing Java parser output YAML

Deliverable:
- `Snapshot` object that is language-agnostic.

---

### Milestone 2 — Cross-language diff engine ✅

- [x] Implement `semverdredd/xldiff.py`:
  - `diff_snapshots(old: Snapshot, new: Snapshot) -> APIDiff`
  - produce items like:
    - `function removed: Area`
    - `type Point: field added: Z`
    - `type Point: method signature changed (breaking): Distance(int)->Distance(string)`

- [x] Signature comparison function:
  - compare param count and optionality
  - compare param types
  - compare return types

- [x] Decide initial strictness for types:
  - default: any type change == breaking
  - later: allow configurable relaxations

Deliverable:
- A detailed diff usable by CLI `--details`.

---

### Milestone 3 — Change classification engine ✅

- [x] Implement `classify_change(diff: APIDiff) -> ChangeType`:
  - breaking present => MAJOR
  - else additive present => MINOR
  - else => NONE

- [x] Keep current Python-specific `detect_change()` for Python module-to-module.
- [x] Add a new entrypoint for snapshots:
  - `compare_snapshots(old_snapshot: Snapshot, new_snapshot: Snapshot) -> CompareResult`

Deliverable:
- Cross-language change inference.

---

### Milestone 4 — CLI: snapshot-based workflow (no old source needed) ✅

Add new "snapshot mode" commands or extend existing ones.

Option A (minimal new surface):
- [x] `semver-dredd xl-init --lang go --path ./pkg` → creates `.semver.yaml`, `baked.yaml`, `VERSION`
- [x] `semver-dredd xl-status --lang go --path ./pkg` → generates temp snapshot, diffs vs baked, writes `current.yaml`
- [x] `semver-dredd xl-bake --lang go --path ./pkg` → updates baseline + VERSION

Option B (keep `snapshot` as plumbing):
- [x] `xl-status` internally executes `snapshot` to a temp buffer and loads it

Also:
- [x] Add `--details` in snapshot mode
- [x] Ensure policy gate behavior matches Python mode:
  - MAJOR disallowed => exit 10
  - MAJOR allowed => warn severity

Deliverable:
- Users can run semver-dredd in Go/Java repos without git history.

---

### Milestone 5 — Programmatic API ✅

- [x] Add pure-data functions:
  - `load_snapshot()`
  - `compare_snapshot_files(baked_path, current_path)`

- [x] Ensure no logging; only structured return types.

Deliverable:
- CI tools can integrate without parsing CLI text.

---

### Milestone 6 — Fixtures + tests + CI ✅

- [x] Add fixtures in `tests/fixtures/go/*.yaml`
- [x] Tests:
  - added function => MINOR
  - removed function => MAJOR
  - field type change => MAJOR
  - return type change => MAJOR
  - parameter count change => MAJOR

- [ ] Add smoke tests that run Go parser on tiny package (optional, guard if `go` present)
- [ ] Add smoke tests that run Java parser (guard if `javac` present AND snakeyaml jar present)

Deliverable:
- Confidence that cross-language semantics remain stable.

---

## Open questions / follow-ups

1) **Type normalization**
   - Do we normalize `int32` vs `int`? Probably not; keep exact.

2) **Fully-qualified names**
   - Go packages, Java packages: should types be `pkg.Type`? Likely yes for real-world.

3) **Overloads (Java)**
   - Java allows overloaded methods; current key `methodName` is ambiguous.
   - Plan: key methods by `name(signature)` or include parameter types in the key.

4) **Generics**
   - Java generics and Go type params: store type string; treat changes as breaking.

5) **Optionality semantics**
   - Go optionality is approximate.
   - Java has no optional params (except overloads / varargs).

---

## Suggested sequence (pragmatic)

1. Milestone 0 + 1 (schema + loader)
2. Milestone 2 (diff)
3. Milestone 3 (classification)
4. Milestone 4 (CLI wiring)
5. Milestone 6 (fixtures/tests)
6. Milestone 5 (programmatic API) where needed

---

## Definition of Done

- `semver-dredd status --lang go --path ./...` works in a repo with only current code and a committed `baked.yaml`.
- It produces `current.yaml` with next suggested version.
- It enforces breaking-change policy (exit 10 unless allowed).
- `--details` prints breaking vs added items.
- Tests cover type and signature changes.

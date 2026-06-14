# Official Plugin Scope Behavior

## Motivation

Core already forwards `include`, `exclude`, and `plugin_options`, but official
plugins currently ignore scope. This phase makes the documented scope model real
for Python, Go, regex Java, and JavaParser, while keeping syntax plugin-specific.

Before editing any plugin package, read `plugins/agent.md` and the local
`agent.md` for that plugin directory.

## Touched Files

- `plugins/agent.md` and per-plugin `agent.md` as required reading, not edits by
  default
- `plugins/python-3.10-dredd/semver_dredd_python/plugin.py`
- `plugins/python-3.10-dredd/semver_dredd_python/python_api.py`
- `plugins/go-1.20-dredd/semver_dredd_go/plugin.py`
- `plugins/go-1.20-dredd/semver_dredd_go/parser/main.go`
- `plugins/java-1.8-dredd/semver_dredd_java/plugin.py`
- `plugins/java-1.8-dredd/semver_dredd_java/parser/main.java`
- `plugins/javaparser-1.8-dredd/semver_dredd_javaparser/plugin.py`
- `plugins/javaparser-1.8-dredd/semver_dredd_javaparser/parser/Main.java`
- plugin `README.md` files
- `tests/test_cross_language.py`
- `tests/test_fields_detection.py`
- new plugin-specific tests as needed

## Commit-Sized Steps

### 1. Add shared test vocabulary for scope behavior

- Create fixtures that contain public, private, included, excluded, nested, and
  match-nothing API members.
- Assert core passes the raw include/exclude arrays through unchanged.
- Assert each official plugin documents unsupported item shapes with warnings or
  plugin-specific errors.

Definition of Done:

- Failing tests describe expected official plugin behavior before implementation.
- Tests avoid trivial implementation checks and validate user-visible snapshots.

### 2. Implement Python package/module scope

- Treat `include` items as module/package names, not filesystem paths.
- Empty include scans the whole configured path API surface.
- Non-empty include enters allow-list mode.
- Apply `exclude` after include.
- Ignore entities starting with `_`.
- Respect `__all__` when present.
- If `__all__` is missing, recursively discover module files/subpackages,
  import each module path, introspect, merge snapshots, and log collisions.
- Do not add `plugin_options.import_submodules` or `static_analysis`.

Definition of Done:

- Tests cover `__all__`, no-`__all__` recursion, private members, include,
  exclude, nested package behavior, and collision logging.
- Existing Python demo still passes.

### 3. Implement Java regex package-prefix scope

- Treat `include` items as Java package prefixes.
- Empty include means all parsed public API under `--path`.
- Apply exclude after include.
- Keep parser-specific options in `plugin_options` and separate from scope.

Definition of Done:

- Tests cover included package, excluded nested package, empty include, and
  match-nothing warnings at the right verbosity.
- Plugin README documents exact syntax and limitations.

### 4. Implement JavaParser package-prefix scope

- Match JavaParser behavior to regex Java where possible.
- Keep it a separate plugin with no universal-default assumption.
- Use parser output filtering unless parser-level filtering is clearly safer and
  tested.

Definition of Done:

- Tests mirror regex Java package-prefix tests.
- Differences between Java and JavaParser are documented.

### 5. Implement Go import-path scope

- Treat `include` items as Go import paths resolved relative to the root path.
- Empty include analyzes the root API surface.
- Non-empty include analyzes package roots selected by import path.
- Apply exclude after include.
- Ensure tests are never part of the API surface.

Definition of Done:

- Tests cover package-level include/exclude, root-relative resolution, and test
  file exclusion.
- Go plugin README documents scope syntax.

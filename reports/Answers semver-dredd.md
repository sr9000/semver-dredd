## Current understanding

I re-checked the proposal, the status report, and the code paths in `semverdredd/`, `cli/`, `snapshot/`, and the plugin packages.

The previous report is broadly correct, with one important precision: in addition to `python`, `go`, and regex `java`, the `javaparser` plugin also currently accepts `options` but does not consume `include`, `exclude`, or `plugin_options`.

Implementation status remains:

- ✅ Framework config plumbing exists: `.semver.yaml` → `Config.include/exclude/plugin_options` → `args.snapshot_options` → `plugin.generate_snapshot(..., options=...)`.
- ✅ Programmatic API forwards `options` too.
- ✅ Domain-agnostic plugin architecture is already mostly in place: custom snapshots + `Comparable.diff_against()` are the real contract.
- 🚧 Remaining proposal work:
  1. plugin-side `include` / `exclude` behavior,
  2. multi-document `.semver.yaml` candidate selection,
  3. built-in `bundle` plugin.

---

## How I think the rest of the proposal would be implemented

### 1. Plugin-side `include` / `exclude`

This is not a core feature anymore; the core already forwards the data. The work is now per plugin.

Recommended baseline behavior:

- If `include` is empty: analyze the plugin's current default scope.
- If `include` is non-empty: analyze only matching API items / packages / files / modules.
- Always apply `exclude` after `include`.
- Treat patterns as recursive by default.
- Do not follow imported dependencies outside scope.

Likely per-plugin implementation:

- **Python**: match against module names / object `__module__`; optionally package paths. Easiest first target.
- **Java regex plugin**: parser should preserve package-qualified names, then filter by package/class prefix.
- **JavaParser plugin**: similar to Java regex, but better AST support.
- **Go plugin**: probably match package directory/file paths, because Go public API is package-based rather than nested namespace-based.

Potential usability issue: if each plugin invents different syntax, users will be confused. We may want a documented common convention like:

> USER COMMENT: nope, not all languages use similar syntax and units of compilation/execution. And semver even can be used with protobuf/swagger of even more excotic content, driven by plugins. That is the reason, why syntax of include/exclude lines is up to plugin.
>
> It would be sweet to use dot separated strings, but it is only recommendation. Plugins are free to use even array of objects. The only requirement: include and exclude is an arrays type

```yaml
include:
  - package.or.module.prefix
exclude:
  - package.or.module.prefix._private
```

and then plugin-specific advanced modes under `plugin_options`.

---

### 2. Multi-document `.semver.yaml`

Current `cli/config.py` uses `yaml.safe_load()`, so this needs a config-loader redesign.

Minimal implementation shape:

- Keep existing `load_config()` behavior for single-doc files.
- Add internal parsing with `yaml.safe_load_all()`.
- If there is one doc: preserve current behavior exactly.
- If multiple docs:
  - first document without `plugin` = shared defaults,
  - documents with `plugin` = candidates,
  - merge defaults into each candidate,
  - select first candidate whose plugin is installed and whose `validate_path(path)` passes.

Important architecture issue: config loading currently happens before command execution and does not know the command's source path until later. Candidate selection needs the source path, so it likely cannot live entirely inside the current `load_config()` function unless we pass command args into config resolution. Better options:

1. **Two-phase config**: load raw config docs first, then resolve plugin candidate after parsing CLI args.
2. **Command-level resolver**: commands that need plugins call `resolve_config_for_path(args.module/path, plugin_override)`.
3. **Keep global config simple**: only use multi-doc candidate resolution for `init/status/bake/compare/snapshot`, not for `plugin`, `patch`, `template`.

---

### 3. Built-in `bundle` plugin

This can be implemented inside core, but plugin discovery currently expects entry points or installed plugin packages. Since core `pyproject.toml` has only the `semver-dredd` CLI script and no `semver_dredd.plugins` entry point, we need decide how to expose a built-in core plugin.

Implementation options:

- Add `semverdredd/bundle_plugin.py` and register it as a core package entry point in `pyproject.toml`:

```toml
[project.entry-points."semver_dredd.plugins"]
bundle = "semverdredd.bundle_plugin:BundlePlugin"
```

- Or add it to `_BUILTIN_FALLBACK_SPECS`, but that is currently intended only for repo-bundled external plugins, not true core plugins.

Snapshot shape is straightforward:

```yaml
snapshot_type_id: <uuid>
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
```

Diff logic:

- removed dependency → `BREAKING`
- added dependency → `MINOR`
- major bump → `BREAKING`
- minor bump → `MINOR`
- patch bump → `PATCH`
- no changes → `NONE`
- aggregate = max severity

Potential usability issue: `bundle` in proposal says `include` contains `VERSION` paths, but the current CLI requires a positional `module/path` for `init/status/bake`. For `bundle`, that path is mostly unused. We need decide whether users should run:

```bash
semver-dredd init . --plugin bundle
semver-dredd status .
```

or whether the CLI should support pathless usage when config has `plugin: bundle`.

---

## Usability review: what feels good vs rough

### Good / already easy

- `semver-dredd init ./mypackage` is a good first command.
- Default plugin is `python`, which is sane for Python projects.
- Plugin API is conceptually clean: `LanguagePlugin.generate_snapshot()` + custom snapshot class + `diff_against()`.
- `HOWTO.md` is unusually strong and explains plugin writing well.
- `docs/schema.md` documents the YAML snapshot envelope and examples.
- Config forwarding is conservative: plugins that ignore unknown options still work.

### Rough edges for jump-in users

- `snapshot` requires `--plugin`, `--path`, and `--version`, even though config could provide plugin and VERSION could provide version.
- `include`/`exclude` exists in docs/config but does nothing in bundled plugins, which can surprise users.
- No CLI flags for one-off scope, e.g. `--include mypkg.core --exclude mypkg._internal`.
- The config template warns that filtering is not implemented; once implemented, it should include real language-specific examples.
- Multi-document config candidate selection has UX ambiguity: users may not know which candidate was chosen unless verbose output explains it.
- Plugin authoring requires writing quite a lot of snapshot serialization boilerplate.
- Snapshot formats are clear to plugin authors but may be too exposed to casual users.
- `bundle` plugin UX needs path/default decisions to avoid awkward commands.

---

## Questions to decide scope and requirements

### A. What deliverable do you want next?

1. Do you want me to produce a **usability review report** under `reports/`, similar to the existing implementation-status report?
   - no
2. Or do you want a **technical implementation plan** for the remaining proposal features?
   - no
3. Or do you want both: `reports/proposal-implementation-plan.md` and `reports/usability-review.md`?
   - no
4. Should I also update `INCLUDE-EXCLUDE-PROPOSAL.md`, `README.md`, `HOWTO.md`, or only write new reports?
   - yes, please update them and keep them in an actual state

### B. Target user experience

5. What is the ideal first-run command? Should it be as simple as:

   ```bash
   semver-dredd init .
   semver-dredd status
   semver-dredd bake
   ```

   with plugin/path inferred from config?

   - yes, that is primary goal, while `--plugin` argument is required at least for `init` command. after that, plugin  name can be written in `.semver.yaml` config. make sure `--plugin` argument always take precedence over config (with warning message when they are differs)

     also i think about delegating `options` section to the plug for initialization.

6. Should `status` and `bake` require the module/path positional argument forever, or should they default to a configured `source.path` / current directory?

   - i think here the same situation as with a `--plugin` — remember path at `init`. if path different from current dir, use `--path` argument.

7. Should `snapshot` read plugin/version/path from config and VERSION by default, or stay explicit?

   - read it from `VERSION` file. `.semver.yaml` save path to the generated version file. it cn be overwritten at `init` command with `--version-path` argument

8. Should `semver-dredd init` ask questions interactively when no plugin is provided, or should it remain non-interactive and deterministic?

   - looks like for now all required information can be easily provided via command args. i think verbose `help` will be enough.

9. Should there be a `semver-dredd doctor` command to explain config, selected plugin, plugin availability, and scope matching?

   - no. instead logging with verbosity level should be used to reflect what happening (err/warn by default, `-v` for info level (O(1) logs, once per tool call) and `-vv` for debug level (O(n) logs, for every plugin/include/api member etc.); `-vvv` for debug level with explicit arguments dump for maximum observability)

### C. Include/exclude usability

10. Should `include` / `exclude` have a **common syntax across all official plugins**, or remain fully plugin-specific?

    - nope, not all languages use similar syntax and units of compilation/execution. And semver even can be used with protobuf/swagger of even more excotic content, driven by plugins. That is the reason, why syntax of include/exclude lines is up to plugin.

      It would be sweet to use dot separated strings, but it is only recommendation. Plugins are free to use even array of objects. The only requirement: include and exclude is an arrays type

11. Do you prefer simple prefix matching as the default? Example:

    ```yaml
    include: [mypackage.api]
    exclude: [mypackage.api.internal]
    ```

    - for those API surfaces that support it - yes, like java or python

12. Should glob syntax be supported by official plugins? Example:

    ```yaml
    include: ["src/**/*.go"]
    exclude: ["**/*_test.go"]
    ```

    - globbing looks advanced and sophisticated feature. prefer to use `path/to/module` as a default approach for predefined plugin.

13. Should recursion be implicit forever, or should we support a non-recursive marker like `pkg!` as the proposal mentions?

    - i think let include behave recursive by default (recommended for all plugins), while exclusion supports `*` (star) to match exclusion rules. that works as expected — exclusion became explicit and have single *home* `exclude` array. Example:

      ```yaml
      include:
      - api/v1
      - api/experimental
      exclude:
      - api/v1/admin
      - api/experimental/*
      ```

      Example states: track v1 and experimental apis, while exclude admin api and any nested experimental (keeping only top level experimental api surface)

14. Should invalid include/exclude patterns be warnings, hard errors, or silently ignored?

    - they should be logged, severity is upto plugin

15. If `include` matches nothing, should the command fail? I lean **yes**, because otherwise users get false confidence.

    - upto plugin, recommended warning

      IFF include is an empty array — included whole `path` api surface

16. If `exclude` matches nothing, should that be allowed silently? I lean **yes**, maybe verbose warning only.

    - upto plugin, recommended warning

17. Should command-line overrides exist?

    ```bash
    semver-dredd status . --include mypkg.api --exclude mypkg.internal
    ```

    - looks like advanced tool usage. i thik `--config` argument will cover most usecases

      -  `.semver.yaml` — main *mode*
      - `.semver.dev.yaml` — dev *mode*, runned with `semver-dredd status --config .semver.dev.yaml`
      - `.semver.my-custom_mode.yaml` — another customized mode, runned with `semver-dredd status --config .semver.my-custom_mode.yaml`

      arguments `--include` and `--exclude` merged with existing arrays. if argument `--override` provided, *includes* and *excludes* are replaces with argument provided.

18. If both config and CLI include/exclude are present, should CLI replace config or append to config?

    - append. warning on collisions

### D. Python plugin behavior

19. For Python, should `include` match module/package names only, filesystem paths only, or both?

    - module/package names only, while entities start with `_` effectively ignored
20. Should `include: mypackage` include submodules not imported by `mypackage.__init__`? Current plugin uses import/introspection, so it only sees what is exposed/imported.

    - if i'm correct, python import allows to import submodule, even it is not exposed by `__init__` — that follows recursive nature of `include` requires to scan files and subfolders inside module, before starting to introspect them
21. Should Python plugin move from runtime introspection toward static AST parsing to support package-wide include/exclude better?

    - static file/folders scanning + runtime introspection of collected modules paths
22. Should runtime import side effects be treated as acceptable, or do we need safer static analysis?

    - respect dudner all array and ignore entities starting from `_` to collect the most accurate api surface

      if dudner all array missing, dive recursively into module files to collect api surface (separate submodules introspection with final merge results and resolve collisions if any)
23. Should `plugin_options` support flags like:

    ```yaml
    plugin_options:
      import_submodules: true
      static_analysis: false
    ```
    
    - both are bad design, `include` already recursive by nature, and static/regex/runtime is a nature of the plugin

### E. Java / JavaParser plugin behavior

24. Should Java `include` match package prefixes (`com.example.api`) rather than filesystem paths?
    - package prefixes
25. Should `javaparser` become the recommended default Java plugin, with regex `java` as fallback?
    - it is different plugins, neither used by default, except it is only plugin for `language`
26. Should multi-document config prioritize `javaparser` → `java` automatically in templates for Java projects?
    - multidocument already specifies what plugin to use AND order of subdocuments defines fallback order
27. Should Java plugins expose `plugin_options` for classpath/source level before include/exclude work?
    - it is orthogonal features, include/exclude defines api surface, while plugin options provides *fine tuning* for a specific plugin

### F. Go plugin behavior

28. Should Go `include` match package directories, Go import paths, files, or exported symbol prefixes?
    - Go import paths
29. Is package-level filtering enough for Go, or do users need file/symbol-level filtering?
    - package-level filtering is enough, public/private members do the rest
30. Should Go test files always be excluded by default?
    - tests is never an api surface
31. Should Go plugin support module root + package include list, or continue expecting one package directory as path?
    - `--path` is a root in any sense it is acceptable for a plugin to correctly resolve includes/excludes

### G. Multi-document config

32. Should multi-document config be limited to plugin fallback candidates for one API surface, exactly as proposed?

    - it is supposed, while different plugins can handle includes/exclude differently in some conditions.

      and some plugins can miss some api surface mebers, while others not.

      it could be perfect to have compatible snapshots between different plugins (of same language), but it is only recommendation, and compatabilitu is not strictly required.

      if snapshot were taken with one plugin, and baking happened with another — best effort is acceptable behavior — put any conflicts/assumptions or ignores to logs so user can decide how harmful it is.

33. Should the selected candidate be written into `current.yaml` or logs for traceability?

    - snapshot should trace it's plugin source

34. If no candidate validates, should the error show all attempted candidates and reasons? I strongly recommend yes.

    - yes

35. How should `--plugin` override behave if the requested plugin is not present in any candidate doc?
    - fail
    
36. Should environment variable `SEMVER_DREDD_PLUGIN` behave like `--plugin` override?

    - yes, while precedence is CMDARGs -> ENVs -> CONFIG

37. Should defaults merge be shallow or deep? Example: if candidate has `plugin_options`, should it merge with defaults `plugin_options` or replace it?

    - missing fields — added; existing fields: objects and arrays merged, else replace (numbers, booleans, strings); null always overwritten if shared, and overrides if candidate specific (behaves like *remove*)

### H. Bundle plugin UX

38. Should `bundle` use `include` for VERSION files as proposed, or a clearer key like:

    ```yaml
    plugin_options:
      dependencies:
        backend: ./backend/VERSION
    ```

    - use include, same key for same purpose

39. How should dependency names be derived if `include` is just a path? Parent directory name? File stem? Explicit map?

    - it's up to plugin, expected any member can be identified with FQN
40. Should `bundle` support globs?

    ```yaml
    include:
      - "*/VERSION"
    ```

    - no

41. If a tracked VERSION file is missing, should that be `BREAKING`, hard error, or ignored?

    - hard error
42. Should added dependencies be `MINOR` as proposed, or configurable?

    - its minor by its nature — adding new, without breaking any existing
43. Should dependency version decreases be `BREAKING`, hard error, or special warning?

    - wow, that's unexpected… TY for pointing it out… while i'm confused how it could happen and what problem should solve for maintainers… Yes, it can be used, for example, revert dependency due to critical vulnerability/broken functionality. Decreased version behaves a little bit different:

      - decrease patch - patch changes (patch are safe to up and down)
      - decrease minor - breaking change (minor are safe to go up only)
      - decrease major - breaking, like any major change

      while decreased version is manageable and meaningful, expected a warning message
44. Should bundle snapshots store dependency paths as well as names, to avoid ambiguity?

    - yes

### I. Plugin author experience

45. Should we reduce plugin boilerplate by providing a helper base class for common function/type snapshots?

    - thats why some plugins provided by default — they are working examples to start with, not only predefined defaults
46. Should there be a `semver-dredd plugin scaffold mylang` command?

    - no, semver-dredd manage api surface version, it is not a ctl for its own plugins
47. Should snapshot schema examples move closer to HOWTO so plugin authors do not need to jump between docs?

    - yes
48. Should the plugin contract include explicit helper functions to parse options?

    ```python
    ScopeOptions.from_options(options)
    ```

    - plugin contract essentially driven by core, core *requires* plugin to implement some features.

      while to be future proof, add `plugin.have("feature name")` — so in future if semverr becomes able to do something else using plugins, but optional from version perspective, this features can be implemented as a feature.

      for example, plugin can be able to provide, say, last update timestamp, and core can use this feature to enrich snapshot. or logs. or anything if want. while versioning works as expected even without such feature.

49. Should plugins be required to document their include/exclude semantics in `plugin info`?

    - recommended
50. Should `plugin info python` show supported options and scope syntax?

    - think `semver-dredd list` enumerates all installed plugins with their info. flag `--json` or `--yaml` provides description in a machine readable format

### J. Compatibility and rollout

51. Should include/exclude implementation be a breaking behavior change? Existing users with config keys may suddenly see narrower snapshots once plugins start respecting them.

    - break current behavior, we a still `0.x.x` and allow to break anything
52. Do we need a transition flag like:

    ```yaml
    plugin_options:
      enable_scope_filtering: true
    ```

    or should documented config keys take effect immediately?
    
    - anything out of `plugin_options` is a required keys, as semverr reach `1.0.0` they will be fixed there forever
53. Should tests assert that unknown `plugin_options` are ignored by all official plugins?

    - official plugins need a fix, flags can be put here like "ignore `_` methods", or ""
54. What Python versions and plugin package versions must stay compatible?

    - target minimal version is python 3.10: for core, for plugins and ever for python plugin introspection, while essentially core+plugin runtime python is not required to match minimal python version that api surface plugin collect and analyze. it is just coincidence or more correct consequence of the way what plugin uses runtime introspection and practically shares python runtime with introspected code base


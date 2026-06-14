# Pre-1.0 Completion Roadmap

Source report: `reports/complete-semver-tool-gap-report.md`.

## Goal

Bring `semver-dredd` from the current architecturally sound prototype to a
pre-1.0 complete tool with config-driven workflows, reliable plugin selection,
observable behavior, scoped official plugins, plugin metadata, snapshot
provenance, a built-in `bundle` plugin, and synchronized documentation/tests.

## Guiding Constraints

- Preserve the existing architectural boundary: core orchestrates mechanics;
  plugins understand API surfaces and own snapshot diff semantics.
- Keep `semverdredd/` pure logic. CLI printing/logging belongs in `cli/`.
- Keep `plugin_options` opaque to core and backward-compatible for plugins.
- Do not make core assumptions about language-specific include/exclude syntax.
- Treat every phase as a sequence of small patches; the repository should remain
  green after each patch.
- Until a planned behavior is implemented, public docs must label it as planned,
  not shipped.

## Release-Level Success Criteria

- The documented first-run workflow works:

  ```bash
  semver-dredd init . --plugin python --version 1.0.0
  semver-dredd status --details
  semver-dredd bake
  ```

- `--config`, `.env`, shell environment, and CLI arguments resolve with the
  precedence `CMDARGs -> ENVs -> CONFIG`.
- Single-document configs remain compatible; multi-document configs support
  ordered plugin fallback candidates.
- `include` and `exclude` are array-valued and preserve plugin-specific item
  shapes, including objects.
- Official Python, Go, Java, and JavaParser plugins honor their documented scope
  semantics.
- Global verbosity explains config selection, plugin selection, candidate
  fallback, scope matching, snapshot compatibility assumptions, and bundle
  dependency decreases.
- Plugin list/info have machine-readable output and describe scope/options.
- Snapshots contain stable generator/provenance metadata while older snapshots
  remain loadable.
- The built-in `bundle` plugin implements the full VERSION dependency diff
  matrix.
- README, HOWTO, schema docs, include/exclude proposal, plugin READMEs, and tests
  all describe and verify the same shipped behavior.

## Phase Order

1. `01-cli-config-resolution.md` — establish command context, pathless workflow,
   `--config`, precedence, CLI scope overrides.
2. `02-config-candidates-and-scope-model.md` — support multi-document configs,
   candidate fallback, merge semantics, and `list[Any]` scope arrays.
3. `03-observability-and-traceability.md` — introduce global verbosity and stable
   snapshot generator provenance.
4. `04-official-plugin-scope.md` — make Python, Go, Java, and JavaParser honor
   include/exclude.
5. `05-plugin-metadata-and-machine-readable-inventory.md` — add optional plugin
   feature discovery and structured plugin inventory output.
6. `06-bundle-plugin.md` — add built-in bundle plugin and bundle snapshot diffing.
7. `07-documentation-and-release-hardening.md` — synchronize docs, examples,
   smoke coverage, and release gates.

## Cross-Phase Quality Gates

Run after each implementation patch unless the patch is docs-only:

```bash
poetry run pytest -v
```

Run when plugin packages or examples are touched:

```bash
pip install -e plugins/python-3.10-dredd
pip install -e plugins/go-1.20-dredd
pip install -e plugins/java-1.8-dredd
pip install -e plugins/javaparser-1.8-dredd
bash example/demo_python.sh
bash scripts/smoke.sh python unit
```

For Go/Java parser changes, also run the relevant parser build/test commands in
the plugin package once confirmed by local plugin `agent.md` files.

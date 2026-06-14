# Agent Notes — Meta-package (`semver-dredd-all`)

Packaging-only meta-package: installs semver-dredd core + the official plugin
packages. No runtime code, no scope behavior of its own.

- `pyproject.toml` — aggregate dependency list.
- `README.md` — install summary.

```bash
pip install semver-dredd-all
semver-dredd plugin list
```

## Editing notes

- Don't add runtime code unless the packaging strategy changes.
- Keep the dependency list aligned with the official supported plugin set.
- If `javaparser` becomes officially recommended, or `bundle` becomes a core
  plugin, decide whether this meta-package should install it. Users expect
  `pip install semver-dredd-all` to provide every official plugin.

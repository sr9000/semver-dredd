# Agent Notes — Meta-package (`semver-dredd-all`)

This is a packaging-only meta-package. It installs semver-dredd core plus the
official plugin packages.

## Contents

- `pyproject.toml` — dependency list for aggregate install.
- `README.md` — installation summary.

## Usage

```bash
pip install semver-dredd-all
semver-dredd plugin list
```

## Editing notes

- Do not add runtime code here unless the packaging strategy changes.
- Keep dependency list aligned with official supported plugin set.
- If `javaparser` becomes officially recommended or if `bundle` becomes a core
  plugin, decide whether this meta-package should mention/install it.

## Scope-related notes

This package has no scope behavior itself. It is relevant only because users may
expect `pip install semver-dredd-all` to install every official plugin that
supports documented `include`/`exclude` behavior.

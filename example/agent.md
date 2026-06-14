# Agent Notes — `example/` Demos

This directory contains small language fixtures and demo scripts. It is named
`example/` in the repo, but it functions as the demos/fixtures area.

## Layout

- `demo_python.sh` — end-to-end Python workflow using `example.py.pygeometry1`
  and `example.py.pygeometry2` module names.
- `demo_go.sh` — end-to-end Go workflow using `go/gogeometry1` and
  `go/gogeometry2` directories.
- `demo_java.sh` — end-to-end regex Java workflow using `java/javageometry1`
  and `java/javageometry2` directories.
- `py/`, `go/`, `java/` — minimal old/new API fixture pairs.

## What demos prove

- `geometry1` → `geometry2` is a `MINOR` change due to added public API.
- Reverse comparison is `BREAKING` and asserted by `tests/smoke/assert_demo.sh`.
- Demo scripts exercise `init`, `status`, `compare`, `snapshot` where relevant,
  and `bake`.

## Run commands

```bash
bash example/demo_python.sh
bash example/demo_go.sh      # requires Go + go plugin
bash example/demo_java.sh    # requires Java/JDK + java plugin

# Smoke assertions around demos
bash tests/smoke/assert_demo.sh python
bash tests/smoke/assert_demo.sh go
bash tests/smoke/assert_demo.sh java
```

## Style notes

- Demo scripts use temporary work dirs and should clean up after themselves.
- They set `PYTHONPATH` to the repo root so examples import local code.
- Keep fixtures intentionally tiny; they are for behavior demonstration, not
  exhaustive parser testing.

## Scope-related notes

These demos currently do not cover `include`/`exclude`. If adding scope demos,
prefer one focused example per language and ensure smoke assertions remain easy
to read.

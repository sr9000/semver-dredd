# Agent Notes — `example/` (demos + fixtures)

Small language fixtures and demo scripts. Named `example/` but serves as the
demos/fixtures area.

## Layout

- `demo_python.sh` — Python workflow using `example.py.pygeometry1/2` modules.
- `demo_go.sh` — Go workflow using `go/gogeometry1/2` dirs.
- `demo_java.sh` — regex Java workflow using `java/javageometry1/2` dirs.
- `py/`, `go/`, `java/` — minimal old/new API fixture pairs.

## What demos prove

- `geometry1` → `geometry2` is `MINOR` (added public API); reverse is `BREAKING`
  (asserted by `tests/smoke/assert_demo.sh`).
- Scripts exercise `init`, `status`, `compare`, `snapshot` (where relevant), `bake`.

## Commands

```bash
bash example/demo_python.sh
bash example/demo_go.sh      # needs Go + go plugin
bash example/demo_java.sh    # needs JDK + java plugin
bash tests/smoke/assert_demo.sh python   # | go | java
```

## Style

- Scripts use temp work dirs and clean up after themselves.
- They set `PYTHONPATH` to repo root so examples import local code.
- Keep fixtures tiny — for behavior demonstration, not exhaustive parser testing.
- Demos don't cover `include`/`exclude`; if adding scope demos, one focused
  example per language and keep smoke assertions readable.

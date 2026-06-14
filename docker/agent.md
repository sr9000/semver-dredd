# Agent Notes — `docker/`

This directory contains Dockerfiles for isolated smoke-test environments. The
Compose file is at repo root: `docker-compose.smoke.yml`.

## Layout

- `Dockerfile.python` — installs core + Python plugin; runs Python demo smoke.
- `Dockerfile.go` — installs core + Go plugin; pre-downloads Go parser modules.
- `Dockerfile.java` — installs core + Java regex plugin; downloads pinned
  SnakeYAML JAR and pre-compiles parser.
- `Dockerfile.unit` — installs core + official plugins + pytest and runs unit
  tests.
- `README.md` — smoke image overview and run examples.

## Main commands

```bash
# Build and run every smoke service, then clean up
bash scripts/smoke.sh

# Run only selected services
bash scripts/smoke.sh python unit

# Skip build when images already exist
bash scripts/smoke.sh --no-build python

# Manual compose invocation
docker compose -f docker-compose.smoke.yml up \
  --abort-on-container-exit --exit-code-from python python
```

## Important behavior

- Runtime mounts repo read-only at `/repo`; images install code at build time.
- Builds assert plugin discovery via `semver-dredd plugin list` so broken
  installation fails early.
- Go/Java images try to front-load network/toolchain work at build time.
- `scripts/smoke.sh` runs services one by one and cleans containers between
  runs.

## Scope-related notes

Smoke tests currently exercise init/status/bake/compare classification for
Python, Go, and regex Java demos. They do **not** yet assert `include`/`exclude`
filtering, multi-document config, `javaparser`, or `bundle` behavior.

If implementing proposal features, add smoke coverage only after unit tests
prove deterministic behavior; parser/toolchain smoke failures are more costly to
debug.

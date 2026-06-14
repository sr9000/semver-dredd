# Agent Notes — `docker/`

Dockerfiles for isolated smoke-test environments. Compose file is at repo root:
`docker-compose.smoke.yml`. Overview/examples in `docker/README.md`.

## Images

- `Dockerfile.python` — core + Python plugin; runs Python demo smoke.
- `Dockerfile.go` — core + Go plugin; pre-downloads Go parser modules.
- `Dockerfile.java` — core + regex Java plugin; downloads pinned SnakeYAML JAR,
  pre-compiles parser.
- `Dockerfile.unit` — core + official plugins + pytest; runs unit tests.

## Commands

```bash
bash scripts/smoke.sh                 # build+run all services, then clean up
bash scripts/smoke.sh python unit     # selected services only
bash scripts/smoke.sh --no-build python
docker compose -f docker-compose.smoke.yml up \
  --abort-on-container-exit --exit-code-from python python
```

## Behavior

- Runtime mounts repo read-only at `/repo`; images install code at build time.
- Builds assert discovery via `semver-dredd plugin list` so broken installs fail
  early; Go/Java images front-load network/toolchain work at build time.
- `scripts/smoke.sh` runs services one by one and cleans containers between runs.

## Scope

Smoke currently covers init/status/bake/compare classification for Python, Go, and
regex Java demos. It does NOT yet assert `include`/`exclude`, multi-document
config, `javaparser`, or `bundle`. Add smoke coverage only after unit tests prove
deterministic behavior — parser/toolchain smoke failures are costly to debug.

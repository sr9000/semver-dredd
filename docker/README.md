# Smoke-test Docker images

These images power the Docker Compose smoke tests defined in
`../docker-compose.smoke.yml`. Each image installs the semver-dredd core plus
one language plugin and runs that language's end-to-end demo with outcome
assertions (`tests/smoke/assert_demo.sh`).

| Dockerfile | Base image | Installs | Runs |
|------------|-----------|----------|------|
| `Dockerfile.python` | `python:3.10-slim` | core + `python-3.10-dredd` | `assert_demo.sh python` |
| `Dockerfile.go` | `golang:1.20-bookworm` | core + `go-1.20-dredd` (Go modules pre-fetched) | `assert_demo.sh go` |
| `Dockerfile.java` | `eclipse-temurin:21-jdk-jammy` | core + `java-1.8-dredd` (snakeyaml jar fetched, parser pre-compiled) | `assert_demo.sh java` |
| `Dockerfile.unit` | `python:3.10-slim` | core + all three plugins + pytest | `pytest tests/` |

## Design notes

- The repository is mounted **read-only** at `/repo` at runtime; images are
  self-contained (code is installed at build time) so nothing writes into the
  mount. The pytest cache is disabled for the same reason.
- Every image asserts `semver-dredd plugin list` shows the expected plugin at
  build time, so a broken plugin install fails the build, not the test run.
- The Java parser's runtime dependency (`snakeyaml-2.2.jar`) is not committed
  to the repository; `Dockerfile.java` downloads the pinned version from Maven
  Central and pre-compiles the parser.
- `Dockerfile.go` pre-downloads the bundled Go parser's modules so the smoke
  run itself needs no network access.

## Running

```bash
# Everything (build + run + aggregate + cleanup)
bash scripts/smoke.sh

# A subset
bash scripts/smoke.sh python unit

# A single service by hand
docker compose -f docker-compose.smoke.yml up \
  --abort-on-container-exit --exit-code-from python python
```

# Smoke-test image: semver-dredd core + go plugin (Go 1.20 toolchain + Python)
FROM golang:1.20-bookworm

RUN apt-get update \
    && apt-get install -y --no-install-recommends python3 python3-pip python3-venv \
    && rm -rf /var/lib/apt/lists/*

# Isolated venv keeps pip happy on Debian (PEP 668)
ENV VIRTUAL_ENV=/opt/venv
RUN python3 -m venv "$VIRTUAL_ENV"
ENV PATH="$VIRTUAL_ENV/bin:$PATH"

WORKDIR /app

COPY pyproject.toml README.md ./
COPY cli ./cli
COPY semverdredd ./semverdredd
COPY snapshot ./snapshot
COPY plugins/go-1.20-dredd ./plugins/go-1.20-dredd

RUN pip install --no-cache-dir . ./plugins/go-1.20-dredd

# Pre-fetch Go modules for the bundled parser so smoke runs are offline
RUN cd "$(python3 -c 'import semver_dredd_go, pathlib; print(pathlib.Path(semver_dredd_go.__file__).parent / "parser")')" \
    && go mod download

# Sanity check: the plugin must be discoverable
RUN semver-dredd plugin list | grep -q go

WORKDIR /repo
CMD ["bash", "tests/smoke/assert_demo.sh", "go"]

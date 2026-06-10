# Smoke-test image: semver-dredd core + java plugin (JDK + Python)
FROM eclipse-temurin:21-jdk-jammy

RUN apt-get update \
    && apt-get install -y --no-install-recommends python3 python3-pip python3-venv curl ca-certificates \
    && rm -rf /var/lib/apt/lists/*

ENV VIRTUAL_ENV=/opt/venv
RUN python3 -m venv "$VIRTUAL_ENV"
ENV PATH="$VIRTUAL_ENV/bin:$PATH"

WORKDIR /app

COPY pyproject.toml README.md ./
COPY cli ./cli
COPY semverdredd ./semverdredd
COPY snapshot ./snapshot
COPY plugins/java-1.8-dredd ./plugins/java-1.8-dredd

RUN pip install --no-cache-dir . ./plugins/java-1.8-dredd

# The snakeyaml runtime jar is not committed to the repo; fetch the pinned
# version the parser expects and pre-compile the parser.
RUN PARSER_DIR="$(python3 -c 'import semver_dredd_java, pathlib; print(pathlib.Path(semver_dredd_java.__file__).parent / "parser")')" \
    && mkdir -p "$PARSER_DIR/lib" \
    && curl -fsSL -o "$PARSER_DIR/lib/snakeyaml-2.2.jar" \
        https://repo1.maven.org/maven2/org/yaml/snakeyaml/2.2/snakeyaml-2.2.jar \
    && javac -cp "$PARSER_DIR/lib/snakeyaml-2.2.jar" "$PARSER_DIR/main.java"

# Sanity check: the plugin must be discoverable
RUN semver-dredd plugin list | grep -q java

WORKDIR /repo
CMD ["bash", "tests/smoke/assert_demo.sh", "java"]

# Agent Notes — Java Regex Plugin (`java-1.8-dredd`)

Plugin key: `java`  
Entry point: `semver_dredd_java:JavaPlugin`  
Implementation: `semver_dredd_java/plugin.py`  
Bundled parser: `semver_dredd_java/parser/main.java`

## How it works

- Requires JDK 1.8+ (`javac` and `java`) in `PATH`.
- `validate_path()` requires an existing directory with recursive `*.java`.
- Compiles `parser/main.java` on first run / when source is newer.
- Runs parser with SnakeYAML on classpath.
- Parser output is upgraded/normalized into `JavaSnapshot` with
  `snapshot_type_id`.
- Diffing converts `JavaSnapshot` to `NormalizedSnapshot` and delegates.

## Package data

`pyproject.toml` includes:

- `parser/*.java`
- `parser/lib/*.jar`

Note: Docker downloads `snakeyaml-2.2.jar` for smoke images if needed; be
careful with vendored binary dependencies.

## Commands

```bash
pip install -e plugins/java-1.8-dredd
semver-dredd snapshot --plugin java --path example/java/javageometry1 --version 1.0.0
bash example/demo_java.sh
```

## Scope-related notes

The plugin currently receives `options` but does not use `include`, `exclude`,
or `plugin_options`.

If implementing scope, package-prefix matching is the most user-friendly
default:

```yaml
include:
  - com.example.api
exclude:
  - com.example.api.internal
```

Because this parser is regex-based, verify whether parser output preserves
enough package-qualified information before filtering. For complex Java parsing,
prefer the `javaparser` plugin.

# Agent Notes — Java Regex Plugin (`java-1.8-dredd`)

Key `java` · entry `semver_dredd_java:JavaPlugin` · impl
`semver_dredd_java/plugin.py` · parser `semver_dredd_java/parser/main.java`.

## How it works

- Requires JDK 1.8+ (`javac`, `java`) in `PATH`.
- `validate_path()` requires an existing dir with recursive `*.java`.
- Compiles `parser/main.java` on first run / when source is newer; runs with
  SnakeYAML on classpath.
- Output normalized into `JavaSnapshot` (with `snapshot_type_id`); diffing converts
  to `NormalizedSnapshot` and delegates.
- Package data (`pyproject.toml`): `parser/*.java`, `parser/lib/*.jar`. Docker
  downloads `snakeyaml-2.2.jar` for smoke images — be careful with vendored binaries.

## Commands

```bash
pip install -e plugins/java-1.8-dredd
semver-dredd snapshot --plugin java --path example/java/javageometry1 --version 1.0.0
bash example/demo_java.sh
```

## Scope (not yet implemented)

Package-prefix matching is the friendliest default:

```yaml
include: [com.example.api]
exclude: [com.example.api.internal]
```

Being regex-based, verify the parser output preserves enough package-qualified
info before filtering. For complex Java parsing, prefer the `javaparser` plugin.

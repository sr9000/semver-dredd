# Agent Notes — JavaParser Plugin (`javaparser-1.8-dredd`)

Key `javaparser` · entry `semver_dredd_javaparser:JavaParserPlugin` · impl
`semver_dredd_javaparser/plugin.py` · parser
`semver_dredd_javaparser/parser/Main.java`.

## How it works

- Requires JDK 1.8+ (`javac`, `java`) in `PATH`.
- Uses the JavaParser AST library — more accurate than the regex `java` plugin.
- Compiles `Main.java` on first run / when newer; runs with all `parser/lib/*.jar`
  on classpath.
- Output normalized into `JavaParserSnapshot` (own UUID); diffing converts to
  `NormalizedSnapshot` and delegates.

## Discovery

Entry-point only — NOT in core's editable/dev fallback list. Install editable for
local work:

```bash
pip install -e plugins/javaparser-1.8-dredd
semver-dredd plugin list
semver-dredd snapshot --plugin javaparser --path example/java/javageometry1 --version 1.0.0
```

No dedicated demo/smoke service yet.

## Scope (not yet implemented)

Should likely become the preferred Java implementation for package-prefix
filtering — AST parsing preserves package/class context better than regex. Example
multi-document config:

```yaml
source:
  path: ./src/main/java
---
plugin: javaparser
include: [com.example.api]
---
plugin: java
include: [com.example.api]
```

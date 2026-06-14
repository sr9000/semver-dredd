# Agent Notes — JavaParser Plugin (`javaparser-1.8-dredd`)

Plugin key: `javaparser`  
Entry point: `semver_dredd_javaparser:JavaParserPlugin`  
Implementation: `semver_dredd_javaparser/plugin.py`  
Bundled parser: `semver_dredd_javaparser/parser/Main.java`

## How it works

- Requires JDK 1.8+ (`javac` and `java`) in `PATH`.
- Uses JavaParser AST library for more accurate Java extraction than regex
  `java` plugin.
- Compiles `Main.java` on first run / when source is newer.
- Runs parser with all `parser/lib/*.jar` files on classpath.
- Parser output is upgraded/normalized into `JavaParserSnapshot` with its own
  UUID.
- Diffing converts to `NormalizedSnapshot` and delegates.

## Discovery note

This plugin is entry-point-only. It is not in `semverdredd.plugin_manager`'s
editable/dev fallback list. For local work, install it editable:

```bash
pip install -e plugins/javaparser-1.8-dredd
semver-dredd plugin list
```

## Commands

```bash
semver-dredd snapshot --plugin javaparser --path example/java/javageometry1 --version 1.0.0
```

There is no dedicated demo/smoke service for this plugin yet.

## Scope-related notes

The plugin currently receives `options` but does not use `include`, `exclude`,
or `plugin_options`.

This should likely become the preferred Java implementation for package-prefix
filtering because AST parsing can preserve package/class context more reliably
than regex parsing.

For multi-document config, a likely Java setup is:

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

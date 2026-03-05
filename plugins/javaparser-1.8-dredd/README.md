# javaparser-1.8-dredd

JavaParser-based Java 1.8+ language plugin for semver-dredd.

This plugin uses the [JavaParser](https://javaparser.org/) library for proper
AST-based analysis of Java source code, providing more accurate extraction of
classes, interfaces, fields, and method signatures than regex-based approaches.

## Installation

```bash
pip install javaparser-1.8-dredd
```

Or install from local path (development):

```bash
pip install ./plugins/javaparser-1.8-dredd
```

## Requirements

- Python 3.10+
- semver-dredd >= 0.1.0
- **JDK 1.8+** installed (both `javac` and `java` must be in PATH)

## Usage

Once installed, the plugin is automatically discovered by semver-dredd via
entry points (no configuration needed):

```bash
# List plugins to verify installation
semver-dredd plugin list

# Generate snapshot for a Java source directory
semver-dredd snapshot --plugin javaparser --path ./src/main/java --version 1.0.0
```

## How it works

This plugin bundles:
- A Java parser (`Main.java`) that uses the **JavaParser** library for
  full AST analysis
- `javaparser-core-3.28.0.jar` — the JavaParser library
- `snakeyaml-2.2.jar` — for YAML output

The parser is compiled on-the-fly using `javac` (first run only) and then
executed via `java` to analyze the target directory.

### What it extracts

- **Public classes and interfaces** — names and structure
- **Public/protected fields** — name and type
- **Public/protected methods** — name, parameter types/names, return type
- **Constructors** — treated as methods with the class name
- **Public static methods** — additionally exposed as package-level functions

### Differences from `java-1.8-dredd`

| Feature | `java-1.8-dredd` (regex) | `javaparser-1.8-dredd` (AST) |
|---------|--------------------------|------------------------------|
| Parsing approach | Regex-based | Full AST via JavaParser |
| Accuracy | Good for simple code | Handles complex Java syntax |
| Generic types | Basic support | Full generic type resolution |
| Annotations | Stripped | Properly handled |
| Nested classes | Limited | Full support |
| Plugin name | `java` | `javaparser` |

Both plugins can coexist — they register under different names (`java` vs
`javaparser`).

## Bundled Dependencies

| Library | Version | License |
|---------|---------|---------|
| [JavaParser](https://javaparser.org/) | 3.28.0 | LGPL-3.0 / Apache-2.0 |
| [SnakeYAML](https://bitbucket.org/snakeyaml/snakeyaml/) | 2.2 | Apache-2.0 |

## Plugin Discovery

This plugin is discovered **exclusively via Python entry points** (group
`semver_dredd.plugins`). It is **not** registered as a built-in plugin.
The entry point is configured in `pyproject.toml`:

```toml
[project.entry-points."semver_dredd.plugins"]
javaparser = "semver_dredd_javaparser:JavaParserPlugin"
```

# Java parser (experimental)

This is the native Java parser used by semver-dredd to export a public API snapshot.

## Requirements

- JDK 21+
- Maven (optional, for building a fat jar)

If Maven isn't available, you can compile and run directly with `javac/java`.

## Run (no Maven)

```bash
# From repo root
javac -cp parser/java/lib/snakeyaml-2.2.jar parser/java/main.java
java  -cp parser/java/lib/snakeyaml-2.2.jar:parser/java main --dir ./path/to/java/src --version 1.0.0 --out baked.yaml
```

## Run (with Maven)

```bash
mvn -f parser/java/maven.pom package
java -jar parser/java/target/java-parser-0.1.0.jar --dir ./src --version 1.0.0
```

## Notes

- This is a lightweight regex-based extractor, good for simple Java libraries.
- It snapshots:
  - public/protected fields
  - public/protected methods
  - public static methods are also exported as `api.functions` with key `TypeName.methodName`
- For full Java grammar support, consider replacing with JavaParser.

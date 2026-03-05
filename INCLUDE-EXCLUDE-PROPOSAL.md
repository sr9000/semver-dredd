proposal to have `include` and `exclude` options in the `.semver.yaml` file, to specify which:

- modules
- directories
- files
- classes
- functions
- methods
- fields
- etc...

should be included or excluded from the semantic versioning analysis. Common advice is to define the `include` and
`exclude` options as lists of strings. The strings will be interpreted by plugins using plugin and language specific
rules.

For example, in a Java project, the `include` option could specify a list of package names or class names to include in
the analysis, while the `exclude` option could specify a list of package names or class names to exclude from the
analysis. In a JavaScript project, the `include` option could specify a list of file paths or function names to include
in the analysis, while the `exclude` option could specify a list of file paths or function names to exclude from the
analysis.

Example `.semver.yaml` file with `include` and `exclude` options:

```yaml
version: 1.0.0
include:
  - src/main/java/com/example/myapp
  - src/main/java/com/example/utils
exclude:
  - src/main/java/com/example/myapp/internal
  - src/main/java/com/example/utils/Helper.java
```

It can be complicated to determine what is API surface, but saint approach is do not recursively going into
subdirectories.
Plugin SHOULD treat any dependencies outside of the included as "always compatible" and not report any breaking changes
for them.

BUT, ofcourse, there is no one-size-fits-all solution, and the specific implementation of the `include` and `exclude`
options will depend on the needs of the project and the capabilities of the plugins being used. The important thing is
to provide a flexible and customizable way for users to specify which parts of their codebase should be included or
excluded from the semantic versioning analysis, so that they can focus on the parts of their codebase that are most
relevant to their versioning strategy.

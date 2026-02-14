# Go parser (experimental)

This is the native Go parser used by semver-dredd to export a public API snapshot.

## Output format

The YAML shape matches semver-dredd's snapshot format:

```yaml
version: 1.0.0
api:
  functions:
    FuncName:
      parameters:
        - name: x
          type: int
          optional: false
      returns:
        - name: ""
          type: error
          optional: false
  types:
    TypeName:
      fields:
        - name: Field
          type: string
      methods:
        MethodName:
          parameters: ...
          returns: ...
```

## Run

```bash
go run ./parser/golang --dir ./path/to/package --version 1.0.0 --out baked.yaml
```

Notes:
- Only **exported** things are treated as public API (`ast.IsExported`).
- Struct fields: only exported fields.
- Functions/methods: only exported.

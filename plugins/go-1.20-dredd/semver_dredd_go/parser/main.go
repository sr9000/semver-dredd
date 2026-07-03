package main

import (
	"flag"
	"fmt"
	"go/ast"
	"go/parser"
	"go/token"
	"os"
	"path/filepath"
	"sort"
	"strings"

	yaml "github.com/goccy/go-yaml"
)

type Param struct {
	Name string `yaml:"name"`
	Type string `yaml:"type"`
	// Optional is best-effort: becomes true when there's an obvious pointer/slice/map/interface
	// or when the parameter is variadic.
	Optional bool `yaml:"optional"`
}

type FuncSig struct {
	Parameters []Param `yaml:"parameters"`
	Returns    []Param `yaml:"returns,omitempty"`
}

type Field struct {
	Name string `yaml:"name"`
	Type string `yaml:"type"`
}

type TypeDef struct {
	Fields  []Field           `yaml:"fields,omitempty"`
	Methods map[string]FuncSig `yaml:"methods,omitempty"`
}

type Source struct {
	Kind string `yaml:"kind"`
	Path string `yaml:"path"`
}

type Snapshot struct {
	SchemaVersion int              `yaml:"schema_version"`
	Version       string           `yaml:"version"`
	Language      string           `yaml:"language"`
	Source        Source           `yaml:"source"`
	API           struct {
		Functions map[string]FuncSig `yaml:"functions"`
		Types     map[string]TypeDef `yaml:"types"`
	} `yaml:"api"`
}

func main() {
	var dir string
	var version string
	var out string

	flag.StringVar(&dir, "dir", ".", "Directory with Go package")
	flag.StringVar(&version, "version", "", "Version string to store in snapshot")
	flag.StringVar(&out, "out", "", "Output YAML file (default: stdout)")
	flag.Parse()

	if version == "" {
		fmt.Fprintln(os.Stderr, "--version is required")
		os.Exit(2)
	}

	snap, err := parseDirTree(dir, version)

	if err != nil {
		fmt.Fprintln(os.Stderr, err)
		os.Exit(1)
	}

	b, err := yaml.Marshal(snap)
	if err != nil {
		fmt.Fprintln(os.Stderr, err)
		os.Exit(1)
	}

	if out == "" {
		os.Stdout.Write(b)
		return
	}

	if err := os.WriteFile(out, b, 0o644); err != nil {
		fmt.Fprintln(os.Stderr, err)
		os.Exit(1)
	}
}

// parseSinglePackageDir parses one directory (non-recursive) as a single Go
// package and returns its exported functions/types unprefixed. Returns
// (nil, nil, nil) when the directory contains no parseable Go package
// (e.g. no .go files) so callers can skip it during a tree walk.
func parseSinglePackageDir(dir string) (map[string]FuncSig, map[string]TypeDef, error) {
	fset := token.NewFileSet()
	pkgs, err := parser.ParseDir(fset, dir, func(fi os.FileInfo) bool {
		// skip tests
		return !strings.HasSuffix(fi.Name(), "_test.go")
	}, parser.ParseComments)
	if err != nil {
		return nil, nil, err
	}

	pkgNames := make([]string, 0, len(pkgs))
	for name := range pkgs {
		pkgNames = append(pkgNames, name)
	}
	sort.Strings(pkgNames)
	if len(pkgNames) == 0 {
		return nil, nil, nil
	}

	pkg := pkgs[pkgNames[0]]

	functions := map[string]FuncSig{}
	types := map[string]TypeDef{}

	// First pass: types and functions
	for _, f := range pkg.Files {

		for _, decl := range f.Decls {
			switch d := decl.(type) {
			case *ast.GenDecl:
				if d.Tok != token.TYPE {
					continue
				}
				for _, spec := range d.Specs {
					ts, ok := spec.(*ast.TypeSpec)
					if !ok {
						continue
					}
					st, ok := ts.Type.(*ast.StructType)
					if !ok {
						continue
					}

					fields := []Field{}
					for _, fld := range st.Fields.List {
						ft := exprString(fld.Type)
						if len(fld.Names) == 0 {
							// embedded field
							fields = append(fields, Field{Name: ft, Type: ft})
							continue
						}
						for _, n := range fld.Names {
							if n == nil {
								continue
							}
							// Only exported fields are considered public
							if !ast.IsExported(n.Name) {
								continue
							}
							fields = append(fields, Field{Name: n.Name, Type: ft})
						}
					}

					types[ts.Name.Name] = TypeDef{Fields: fields, Methods: map[string]FuncSig{}}
				}
			case *ast.FuncDecl:
				if d.Recv != nil {
					// methods handled in second pass
					continue
				}
				// Only exported functions
				if !ast.IsExported(d.Name.Name) {
					continue
				}
				functions[d.Name.Name] = funcTypeToSig(d.Type)
			}
		}
	}

	// Second pass: methods
	for _, f := range pkg.Files {
		for _, decl := range f.Decls {
			d, ok := decl.(*ast.FuncDecl)
			if !ok || d.Recv == nil {
				continue
			}
			// Only exported methods
			if !ast.IsExported(d.Name.Name) {
				continue
			}

			recvType := receiverBaseType(d.Recv)
			if recvType == "" {
				continue
			}

			td, ok := types[recvType]
			if !ok {
				// Not a struct we captured, but keep simple: ignore
				continue
			}
			if td.Methods == nil {
				td.Methods = map[string]FuncSig{}
			}
			td.Methods[d.Name.Name] = funcTypeToSig(d.Type)
			types[recvType] = td
		}
	}

	return functions, types, nil
}

// parseDirTree walks dir recursively, treating each subdirectory containing
// Go files as its own package. The root package's functions/types are kept
// unprefixed (preserving pre-scope behavior for the common single-package
// case); nested packages are prefixed with their slash-separated import
// path relative to the root (Go import-path convention), e.g. "sub/pkg.Area".
// Hidden directories, "vendor", and "testdata" are skipped.
func parseDirTree(rootDir string, version string) (*Snapshot, error) {
	abs, err := filepath.Abs(rootDir)
	if err != nil {
		return nil, err
	}

	snap := &Snapshot{
		SchemaVersion: 2,
		Version:       version,
		Language:      "go",
		Source: Source{
			Kind: "package",
			Path: rootDir,
		},
	}
	snap.API.Functions = map[string]FuncSig{}
	snap.API.Types = map[string]TypeDef{}

	foundAny := false

	walkErr := filepath.Walk(abs, func(path string, info os.FileInfo, err error) error {
		if err != nil {
			return err
		}
		if !info.IsDir() {
			return nil
		}
		base := filepath.Base(path)
		if path != abs && (strings.HasPrefix(base, ".") || base == "vendor" || base == "testdata") {
			return filepath.SkipDir
		}

		functions, types, perr := parseSinglePackageDir(path)
		if perr != nil {
			return perr
		}
		if functions == nil && types == nil {
			return nil // no Go package in this directory
		}
		foundAny = true

		relPath, rerr := filepath.Rel(abs, path)
		if rerr != nil {
			return rerr
		}
		prefix := ""
		if relPath != "." {
			prefix = filepath.ToSlash(relPath) + "/"
		}

		for name, sig := range functions {
			snap.API.Functions[prefix+name] = sig
		}
		for name, td := range types {
			snap.API.Types[prefix+name] = td
		}
		return nil
	})
	if walkErr != nil {
		return nil, walkErr
	}
	if !foundAny {
		return nil, fmt.Errorf("no Go packages found in %s", abs)
	}

	return snap, nil
}


func receiverBaseType(fl *ast.FieldList) string {
	if fl == nil || len(fl.List) == 0 {
		return ""
	}
	t := fl.List[0].Type
	// receiver can be *T or T
	if se, ok := t.(*ast.StarExpr); ok {
		return exprString(se.X)
	}
	return exprString(t)
}

func funcTypeToSig(ft *ast.FuncType) FuncSig {
	sig := FuncSig{}
	sig.Parameters = fieldListToParams(ft.Params, false)
	sig.Returns = fieldListToParams(ft.Results, true)
	return sig
}

func fieldListToParams(fl *ast.FieldList, isReturn bool) []Param {
	if fl == nil {
		return nil
	}
	params := []Param{}
	idx := 0
	for _, f := range fl.List {
		pt := exprString(f.Type)
		opt := isOptionalType(f.Type)

		// variadic
		if _, ok := f.Type.(*ast.Ellipsis); ok {
			opt = true
		}

		if len(f.Names) == 0 {
			// unnamed return or param
			name := ""
			if !isReturn {
				name = fmt.Sprintf("arg%d", idx)
			}
			params = append(params, Param{Name: name, Type: pt, Optional: opt})
			idx++
			continue
		}
		for _, n := range f.Names {
			name := n.Name
			params = append(params, Param{Name: name, Type: pt, Optional: opt})
			idx++
		}
	}
	return params
}

func isOptionalType(expr ast.Expr) bool {
	switch t := expr.(type) {
	case *ast.StarExpr:
		return true
	case *ast.ArrayType:
		return true
	case *ast.MapType:
		return true
	case *ast.InterfaceType:
		return true
	case *ast.Ellipsis:
		return true
	case *ast.ChanType:
		return true
	case *ast.SelectorExpr:
		_ = t
		return false
	default:
		return false
	}
}

func exprString(expr ast.Expr) string {
	switch t := expr.(type) {
	case *ast.Ident:
		return t.Name
	case *ast.StarExpr:
		return "*" + exprString(t.X)
	case *ast.SelectorExpr:
		return exprString(t.X) + "." + t.Sel.Name
	case *ast.ArrayType:
		if t.Len == nil {
			return "[]" + exprString(t.Elt)
		}
		return "[N]" + exprString(t.Elt)
	case *ast.MapType:
		return "map[" + exprString(t.Key) + "]" + exprString(t.Value)
	case *ast.Ellipsis:
		return "..." + exprString(t.Elt)
	case *ast.InterfaceType:
		return "interface{}"
	case *ast.FuncType:
		return "func"
	default:
		return fmt.Sprintf("%T", expr)
	}
}

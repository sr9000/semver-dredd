import com.github.javaparser.StaticJavaParser;
import com.github.javaparser.ast.CompilationUnit;
import com.github.javaparser.ast.Modifier;
import com.github.javaparser.ast.body.*;
import com.github.javaparser.ast.type.Type;

import org.yaml.snakeyaml.DumperOptions;
import org.yaml.snakeyaml.Yaml;

import java.io.IOException;
import java.nio.charset.StandardCharsets;
import java.nio.file.Files;
import java.nio.file.Path;
import java.util.*;
import java.util.stream.Stream;

/**
 * JavaParser-based API extractor for semver-dredd.
 *
 * Uses the JavaParser library for proper AST analysis instead of regex-based
 * extraction. Produces YAML output in schema v2 format which the Python
 * plugin wrapper upgrades to v3.
 *
 * Extracts:
 *  - Public classes and interfaces (names, fields, methods)
 *  - Public/protected fields with types
 *  - Public/protected methods with full signatures
 *  - Public static methods are additionally exposed as package-level functions
 */
public class Main {

    public static void main(String[] args) throws Exception {
        Map<String, String> flags = parseFlags(args);
        String dir = flags.getOrDefault("--dir", ".");
        String version = flags.get("--version");
        String out = flags.getOrDefault("--out", "");

        if (version == null || version.isBlank()) {
            System.err.println("--version is required");
            System.exit(2);
        }

        Map<String, Object> snapshot = parseDirectory(Path.of(dir), version);

        DumperOptions opts = new DumperOptions();
        opts.setDefaultFlowStyle(DumperOptions.FlowStyle.BLOCK);
        opts.setPrettyFlow(true);

        Yaml yaml = new Yaml(opts);
        String outYaml = yaml.dump(snapshot);

        if (out.isBlank()) {
            System.out.print(outYaml);
        } else {
            Files.writeString(Path.of(out), outYaml, StandardCharsets.UTF_8);
        }
    }

    private static Map<String, String> parseFlags(String[] args) {
        Map<String, String> flags = new HashMap<>();
        for (int i = 0; i < args.length; i++) {
            String a = args[i];
            if (!a.startsWith("--")) continue;
            String v = "";
            if (i + 1 < args.length && !args[i + 1].startsWith("--")) {
                v = args[i + 1];
                i++;
            }
            flags.put(a, v);
        }
        return flags;
    }

    private static Map<String, Object> parseDirectory(Path dir, String version) throws IOException {
        Map<String, Object> functions = new LinkedHashMap<>();
        Map<String, Object> types = new LinkedHashMap<>();

        List<Path> files = new ArrayList<>();
        if (Files.isRegularFile(dir) && dir.toString().endsWith(".java")) {
            files.add(dir);
        } else {
            try (Stream<Path> walk = Files.walk(dir)) {
                walk.filter(p -> p.toString().endsWith(".java"))
                    .filter(p -> !p.getFileName().toString().endsWith("Test.java"))
                    .sorted()
                    .forEach(files::add);
            }
        }

        for (Path p : files) {
            parseJavaFile(p, functions, types);
        }


        Map<String, Object> api = new LinkedHashMap<>();
        api.put("functions", functions);
        api.put("types", types);

        Map<String, Object> source = new LinkedHashMap<>();
        source.put("kind", "directory");
        source.put("path", dir.toString());

        Map<String, Object> snap = new LinkedHashMap<>();
        snap.put("schema_version", 2);
        snap.put("version", version);
        snap.put("language", "java");
        snap.put("source", source);
        snap.put("api", api);
        return snap;
    }

    private static void parseJavaFile(
            Path filePath,
            Map<String, Object> functions,
            Map<String, Object> types
    ) {
        CompilationUnit cu;
        try {
            cu = StaticJavaParser.parse(filePath);
        } catch (Exception e) {
            System.err.println("Warning: failed to parse " + filePath + ": " + e.getMessage());
            return;
        }

        String pkg = cu.getPackageDeclaration()
                .map(pd -> pd.getNameAsString())
                .orElse("");

        for (TypeDeclaration<?> typeDecl : cu.getTypes()) {
            if (!isPublicOrDefault(typeDecl)) continue;

            String simpleTypeName = typeDecl.getNameAsString();
            String typeName = pkg.isEmpty() ? simpleTypeName : pkg + "." + simpleTypeName;

            Map<String, Object> typeDef = new LinkedHashMap<>();
            List<Map<String, Object>> fields = new ArrayList<>();
            Map<String, Object> methods = new LinkedHashMap<>();

            // Extract fields
            for (FieldDeclaration field : typeDecl.getFields()) {
                if (!isPublicOrProtected(field)) continue;
                String fieldType = field.getElementType().asString();
                for (VariableDeclarator var : field.getVariables()) {
                    Map<String, Object> f = new LinkedHashMap<>();
                    f.put("name", var.getNameAsString());
                    // Include array brackets if present in the variable
                    String varType = fieldType;
                    Type varDeclType = var.getType();
                    if (varDeclType.isArrayType()) {
                        varType = varDeclType.asString();
                    }
                    f.put("type", varType);
                    fields.add(f);
                }
            }

            // Extract methods and constructors
            for (MethodDeclaration method : typeDecl.getMethods()) {
                if (!isPublicOrProtected(method)) continue;

                boolean isStatic = method.isStatic();
                String retType = method.getType().asString();
                String methodName = method.getNameAsString();

                Map<String, Object> sig = buildMethodSignature(method.getParameters(), retType);
                methods.put(methodName, sig);

                // Expose public static methods as package-level functions
                if (isStatic) {
                    functions.put(typeName + "." + methodName, sig);
                }
            }

            // Extract constructors (public/protected only)
            if (typeDecl instanceof ClassOrInterfaceDeclaration) {
                for (ConstructorDeclaration ctor : ((ClassOrInterfaceDeclaration) typeDecl).getConstructors()) {
                    if (!isPublicOrProtected(ctor)) continue;
                    String ctorName = ctor.getNameAsString();
                    Map<String, Object> sig = buildMethodSignature(ctor.getParameters(), typeName);
                    // If there are overloaded constructors, keep the last one
                    methods.put(ctorName, sig);
                }
            }

            if (!fields.isEmpty()) typeDef.put("fields", fields);
            if (!methods.isEmpty()) typeDef.put("methods", methods);
            types.put(typeName, typeDef);
        }
    }

    private static Map<String, Object> buildMethodSignature(
            List<com.github.javaparser.ast.body.Parameter> params,
            String retType
    ) {
        Map<String, Object> sig = new LinkedHashMap<>();
        List<Map<String, Object>> paramList = new ArrayList<>();

        for (com.github.javaparser.ast.body.Parameter param : params) {
            Map<String, Object> p = new LinkedHashMap<>();
            p.put("name", param.getNameAsString());
            String type = param.getType().asString();
            if (param.isVarArgs()) {
                type = type + "[]";
                p.put("optional", true);
            } else {
                p.put("optional", false);
            }
            p.put("type", type);
            paramList.add(p);
        }

        sig.put("parameters", paramList);
        if (retType != null && !retType.isBlank() && !retType.equals("void")) {
            List<Map<String, Object>> returns = new ArrayList<>();
            Map<String, Object> ret = new LinkedHashMap<>();
            ret.put("name", "");
            ret.put("type", retType);
            ret.put("optional", false);
            returns.add(ret);
            sig.put("returns", returns);
        }
        return sig;
    }

    // Check if a type declaration is public (or package-private, which we treat as public for top-level)
    private static boolean isPublicOrDefault(TypeDeclaration<?> decl) {
        // Top-level types without explicit access modifier are package-private
        // We include public and package-private top-level types
        return !decl.getModifiers().contains(Modifier.privateModifier())
            && !decl.getModifiers().contains(Modifier.protectedModifier());
    }

    private static boolean isPublicOrProtected(FieldDeclaration decl) {
        return decl.getModifiers().contains(Modifier.publicModifier())
            || decl.getModifiers().contains(Modifier.protectedModifier());
    }

    private static boolean isPublicOrProtected(MethodDeclaration decl) {
        return decl.getModifiers().contains(Modifier.publicModifier())
            || decl.getModifiers().contains(Modifier.protectedModifier());
    }

    private static boolean isPublicOrProtected(ConstructorDeclaration decl) {
        return decl.getModifiers().contains(Modifier.publicModifier())
            || decl.getModifiers().contains(Modifier.protectedModifier());
    }
}

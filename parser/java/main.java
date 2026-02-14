import org.yaml.snakeyaml.DumperOptions;
import org.yaml.snakeyaml.Yaml;

import java.io.IOException;
import java.nio.charset.StandardCharsets;
import java.nio.file.Files;
import java.nio.file.Path;
import java.util.*;
import java.util.regex.Matcher;
import java.util.regex.Pattern;

public class main {
    // Very small, dependency-light Java parser.
    // It does not aim to be a complete Java grammar parser.
    // It extracts:
    //  - public classes/interfaces (names)
    //  - public/protected fields (name + type)
    //  - public/protected methods (name + param types/names + return type)
    //  - public static methods are additionally exported under api.functions
    //
    // Intended for the repo examples and simple Java libraries. For real-world code,
    // we'd eventually want to replace this with a proper parser (e.g., JavaParser).

    static class Param {
        public String name;
        public String type;
        public boolean optional;

        public Param(String name, String type, boolean optional) {
            this.name = name;
            this.type = type;
            this.optional = optional;
        }
    }

    static class FuncSig {
        public List<Map<String, Object>> parameters = new ArrayList<>();
        public List<Map<String, Object>> returns = new ArrayList<>();
    }

    static class Field {
        public String name;
        public String type;

        public Field(String name, String type) {
            this.name = name;
            this.type = type;
        }
    }

    static class TypeDef {
        public List<Map<String, Object>> fields = new ArrayList<>();
        public Map<String, Object> methods = new LinkedHashMap<>();
    }

    @SuppressWarnings("unchecked")
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
        opts.setSortKeys(false);

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
            if (!a.startsWith("--")) {
                continue;
            }
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
        Map<String, Object> api = new LinkedHashMap<>();
        Map<String, Object> functions = new LinkedHashMap<>();
        Map<String, Object> types = new LinkedHashMap<>();

        List<Path> files = new ArrayList<>();
        if (Files.isRegularFile(dir) && dir.toString().endsWith(".java")) {
            files.add(dir);
        } else {
            try (var walk = Files.walk(dir)) {
                walk.filter(p -> p.toString().endsWith(".java"))
                        .filter(p -> !p.getFileName().toString().endsWith("Test.java"))
                        .forEach(files::add);
            }
        }

        Collections.sort(files);

        for (Path p : files) {
            String src = Files.readString(p, StandardCharsets.UTF_8);
            parseJavaFile(src, functions, types);
        }

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

    private static void parseJavaFile(String src, Map<String, Object> functions, Map<String, Object> types) {
        // Remove comments (best-effort)
        src = src.replaceAll("(?s)/\\*.*?\\*/", " ");
        src = src.replaceAll("//.*", " ");

        // Find public class/interface definitions
        Pattern typePat = Pattern.compile("(?s)(public\\s+)?(class|interface|record)\\s+([A-Za-z_][A-Za-z0-9_]*)[^\\{]*\\{(.*?)\\}\s*", Pattern.MULTILINE);
        Matcher m = typePat.matcher(src);

        while (m.find()) {
            String kind = m.group(2);
            String typeName = m.group(3);
            String body = m.group(4);

            TypeDef td = new TypeDef();

            // Fields: public/protected <type> <name>;
            Pattern fieldPat = Pattern.compile("(public|protected)\\s+([A-Za-z0-9_<>,\\[\\]\\.? ]+)\\s+([A-Za-z_][A-Za-z0-9_]*)\\s*(=|;)");
            Matcher fm = fieldPat.matcher(body);
            while (fm.find()) {
                String type = normalizeType(fm.group(2));
                String name = fm.group(3);
                td.fields.add(mapOf("name", name, "type", type));
            }

            // Methods: (public|protected) [static] <ret> <name>(<params>)
            Pattern methodPat = Pattern.compile("(public|protected)\\s+(static\\s+)?([A-Za-z0-9_<>,\\[\\]\\.? ]+)\\s+([A-Za-z_][A-Za-z0-9_]*)\\s*\\(([^)]*)\\)");
            Matcher mm = methodPat.matcher(body);
            while (mm.find()) {
                boolean isStatic = mm.group(2) != null;
                String retType = normalizeType(mm.group(3));
                String methodName = mm.group(4);
                String paramsRaw = mm.group(5);

                Map<String, Object> sig = parseMethodSignature(paramsRaw, retType);
                td.methods.put(methodName, sig);

                // Also expose public static methods as package functions
                if (isStatic) {
                    functions.put(typeName + "." + methodName, sig);
                }
            }

            Map<String, Object> tdMap = new LinkedHashMap<>();
            if (!td.fields.isEmpty()) tdMap.put("fields", td.fields);
            if (!td.methods.isEmpty()) tdMap.put("methods", td.methods);

            types.put(typeName, tdMap);
        }

        // Also capture top-level public static functions in utility classes is handled above.
        // Java doesn't have standalone functions.
    }

    private static Map<String, Object> parseMethodSignature(String paramsRaw, String retType) {
        Map<String, Object> sig = new LinkedHashMap<>();
        List<Map<String, Object>> params = new ArrayList<>();

        String trimmed = paramsRaw.trim();
        if (!trimmed.isEmpty()) {
            String[] parts = trimmed.split(",");
            int idx = 0;
            for (String p : parts) {
                String pp = p.trim();
                if (pp.isEmpty()) continue;

                // Remove common modifiers/annotations
                pp = pp.replaceAll("@[A-Za-z0-9_.]+", "").trim();
                pp = pp.replaceAll("\\bfinal\\b", "").trim();

                // varargs: Type... name
                boolean optional = false;
                if (pp.contains("...")) {
                    optional = true;
                    pp = pp.replace("...", "[]");
                }

                String[] tokens = pp.split("\\s+");
                if (tokens.length == 1) {
                    // no name, just type
                    params.add(mapOf("name", "arg" + idx, "type", normalizeType(tokens[0]), "optional", optional));
                } else {
                    String name = tokens[tokens.length - 1];
                    String type = String.join(" ", Arrays.copyOf(tokens, tokens.length - 1));
                    params.add(mapOf("name", name, "type", normalizeType(type), "optional", optional));
                }
                idx++;
            }
        }

        sig.put("parameters", params);
        if (retType != null && !retType.isBlank() && !retType.equals("void")) {
            sig.put("returns", List.of(mapOf("name", "", "type", retType, "optional", false)));
        }
        return sig;
    }

    private static String normalizeType(String t) {
        if (t == null) return "";
        // collapse whitespace
        return t.trim().replaceAll("\\s+", " ");
    }

    private static Map<String, Object> mapOf(Object... kv) {
        Map<String, Object> m = new LinkedHashMap<>();
        for (int i = 0; i < kv.length; i += 2) {
            m.put(String.valueOf(kv[i]), kv[i + 1]);
        }
        return m;
    }
}

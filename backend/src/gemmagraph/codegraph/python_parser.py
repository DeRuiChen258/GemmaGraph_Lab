import ast
import hashlib

from gemmagraph.codegraph.schema import Symbol


def parse(path: str, text: str):
    tree = ast.parse(text, filename=path)
    lines = text.splitlines()
    symbols, links, references = [], [], []

    def add(name, kind, start, end):
        ident = f"{path}::{name}"
        source = "\n".join(lines[start - 1:end])
        symbols.append(Symbol(id=ident, path=path, name=name, kind=kind, start_line=start,
                              end_line=end, source_hash=hashlib.sha256(source.encode()).hexdigest(),
                              text=source))
        return ident

    module = add("<module>", "file", 1, max(1, len(lines)))

    def walk(node, parent, prefix=""):
        for child in ast.iter_child_nodes(node):
            if isinstance(child, (ast.FunctionDef, ast.AsyncFunctionDef, ast.ClassDef)):
                name = prefix + child.name
                ident = add(name, "class" if isinstance(child, ast.ClassDef) else "function",
                            min([child.lineno] + [d.lineno for d in child.decorator_list]), child.end_lineno)
                links.append(dict(source=parent, target=ident, kind="contains"))
                if isinstance(child, ast.ClassDef):
                    for base in child.bases:
                        references.append((ident, ast.unparse(base), "inherits"))
                walk(child, ident, name + ".")
            else:
                if isinstance(child, ast.Call):
                    references.append((parent, ast.unparse(child.func), "calls"))
                elif isinstance(child, ast.Import):
                    references.extend((parent, a.name, "imports") for a in child.names)
                elif isinstance(child, ast.ImportFrom):
                    references.extend((parent, ((child.module or "") + "." + a.name).strip("."), "imports")
                                      for a in child.names)
                walk(child, parent, prefix)
    walk(tree, module)
    return symbols, links, references

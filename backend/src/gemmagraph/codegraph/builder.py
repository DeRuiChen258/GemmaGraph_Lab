import hashlib
from collections import defaultdict
from pathlib import Path

from gemmagraph.codegraph.python_parser import parse
from gemmagraph.codegraph.schema import CodeIndex, Relation, Symbol
from gemmagraph.services.workspaces import is_public, tree_hash


def build(root: Path) -> CodeIndex:
    symbols, links, refs, diagnostics = [], [], [], []
    file_count = python_count = parsed = 0
    for p in sorted(root.rglob("*")):
        path = p.relative_to(root).as_posix()
        if not p.is_file() or not is_public(path):
            continue
        file_count += 1
        if p.suffix != ".py":
            continue
        python_count += 1
        if p.stat().st_size > 512_000:
            diagnostics.append(dict(path=path, reason="file_too_large"))
            continue
        try:
            text = p.read_text()
            ss, ls, rr = parse(path, text)
            symbols.extend(ss)
            links.extend(ls)
            refs.extend(rr)
            parsed += 1
        except (SyntaxError, UnicodeError) as e:
            diagnostics.append(dict(path=path, reason=type(e).__name__, line=getattr(e, "lineno", None)))
    names = defaultdict(list)
    for s in symbols:
        names[s.name.split(".")[-1]].append(s.id)
        if s.kind == "file":
            names[Path(s.path).stem].append(s.id)
    unresolved = set()
    for source, name, kind in refs:
        targets = names.get(name.split(".")[-1], [])
        same_file = [t for t in targets if t.split("::")[0] == source.split("::")[0]]
        targets = same_file or targets
        if len(targets) == 1:
            links.append(dict(source=source, target=targets[0], kind=kind,
                              confidence="approximate"))
        else:
            ident = "unresolved::" + hashlib.sha256(name.encode()).hexdigest()[:16]
            if ident not in unresolved:
                symbols.append(Symbol(id=ident, path="", name=name, kind="unresolved", start_line=0,
                                      end_line=0, source_hash="", text=""))
                unresolved.add(ident)
            links.append(dict(source=source, target=ident, kind=kind, confidence="unresolved"))
    unique = {(x["source"], x["target"], x["kind"]): x for x in links}
    return CodeIndex(tree_hash=tree_hash(root), symbols=symbols,
                     relations=[Relation(**v) for v in unique.values()], diagnostics=diagnostics,
                     file_count=file_count, python_count=python_count, parsed_count=parsed)

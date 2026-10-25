import os

from gemmagraph.codegraph.builder import build
from gemmagraph.codegraph.schema import CodeIndex
from gemmagraph.services.workspaces import resolve_inside


class IndexStore:
    def __init__(self, settings, workspaces):
        self.root, self.workspaces = settings.data_dir / "indexes", workspaces

    def load_or_build(self, repository):
        path = resolve_inside(self.root, repository["tree_hash"] + "-ast-v1.json")
        if path.exists():
            return CodeIndex.model_validate_json(path.read_text())
        value = build(self.workspaces.source(repository["snapshot_id"]))
        path.parent.mkdir(parents=True, exist_ok=True)
        temp = path.with_suffix(".tmp")
        temp.write_text(value.model_dump_json())
        os.replace(temp, path)
        return value

    @staticmethod
    def subgraph(index, node=None, query="", hops=1, limit=200):
        symbols = {s.id: s for s in index.symbols}
        if node:
            selected = {node} & symbols.keys()
        else:
            selected = {s.id for s in index.symbols if query.lower() in (s.name + s.path).lower()}
            selected = set(sorted(selected)[:limit])
        for _ in range(min(2, hops)):
            adjacent = {r.target if r.source in selected else r.source for r in index.relations
                        if r.source in selected or r.target in selected}
            selected.update(sorted(adjacent - selected)[:max(0, limit - len(selected))])
        return dict(nodes=[symbols[k].model_dump(exclude={"text"}) for k in sorted(selected)],
                    edges=[r.model_dump() for r in index.relations
                           if r.source in selected and r.target in selected],
                    truncated=len(selected) >= limit, total_nodes=len(symbols),
                    coverage=index.parsed_count / max(1, index.python_count))

import math
import re
from collections import Counter, deque


def terms(text):
    return re.findall(r"[a-z0-9]+", re.sub(r"([a-z])([A-Z])", r"\1 \2", text).lower())


def retrieve(index, issue, method, token_budget, config, failure=""):
    symbols = {s.id: s for s in index.symbols if s.kind in {"function", "class", "file"}}
    docs = {k: Counter(terms(s.path + " " + s.name + " " + s.text)) for k, s in symbols.items()}
    query = set(terms(issue + " " + failure))
    average = sum(sum(v.values()) for v in docs.values()) / max(1, len(docs))
    df = Counter(t for v in docs.values() for t in v)
    scores = {}
    for k, counts in docs.items():
        length = sum(counts.values())
        scores[k] = sum(math.log(1 + (len(docs) - df[t] + .5) / (df[t] + .5))
                        * counts[t] * 2.2 / (counts[t] + 1.2 * (.25 + .75 * length / max(1, average)))
                        for t in query if counts[t])
    ranked = sorted(symbols, key=lambda k: (-scores[k], k))
    seeds = ranked[:config.get("seed_count", 8)]
    distance = dict.fromkeys(seeds, 0)
    if method != "lexical":
        adjacency = {}
        for r in index.relations:
            adjacency.setdefault(r.source, set()).add(r.target)
            adjacency.setdefault(r.target, set()).add(r.source)
        queue = deque(seeds)
        while queue and len(distance) < config.get("max_candidates", 64):
            ident = queue.popleft()
            if distance[ident] >= config.get("graph_hops", 2):
                continue
            for target in sorted(adjacency.get(ident, ())):
                if target in symbols and target not in distance:
                    distance[target] = distance[ident] + 1
                    queue.append(target)
                    if len(distance) >= config.get("max_candidates", 64):
                        break
    else:
        distance = dict.fromkeys(ranked, 0)
    maximum = max(scores.values(), default=1) or 1

    def priority(k):
        s = symbols[k]
        score = (.6 * scores[k] / maximum + .25 / (1 + distance[k])
                 + .15 * bool(s.path and s.path in failure))
        return score / math.sqrt(1 + len(s.text) / 512)

    if method == "lexical_graph_budget":
        order = sorted(distance, key=lambda k: (-priority(k), k))
    elif method == "lexical_graph":
        order = sorted(distance, key=lambda k: (distance[k], seeds.index(k) if k in seeds else 999, k))
    else:
        order = ranked
    selected, used, spans = [], 0, {}
    for k in order:
        s = symbols[k]
        if any(a <= s.start_line and s.end_line <= b for a, b in spans.get(s.path, [])):
            continue
        available = token_budget - used
        if available < 64:
            break
        lines, text = s.text.splitlines(), ""
        for line in lines:
            candidate = text + line + "\n"
            if math.ceil(len(candidate) / 3) > min(available, 1600):
                break
            text = candidate
        if not text:
            continue
        cost = math.ceil(len(text) / 3)
        end = s.start_line + len(text.splitlines()) - 1
        selected.append(dict(id=k, path=s.path, symbol_id=k, start_line=s.start_line, end_line=end,
                             score=round(scores[k], 4), relation_distance=distance[k],
                             relation_path="lexical seed" if distance[k] == 0 else f"graph:{distance[k]} hops",
                             source_hash=s.source_hash, text=text, tokens=cost,
                             token_count_mode="estimated", truncated=end < s.end_line))
        spans.setdefault(s.path, []).append((s.start_line, end))
        used += cost
    return selected

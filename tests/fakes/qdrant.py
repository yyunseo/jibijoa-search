from dataclasses import dataclass
from typing import Any, Optional


@dataclass
class FakePoint:
    id: int
    payload: dict
    vector: Optional[list] = None
    score: float = 0.0


def _get(payload: dict, key: str) -> Any:
    cur: Any = payload
    for part in key.split("."):
        if not isinstance(cur, dict) or part not in cur:
            return None
        cur = cur[part]
    return cur


def _match(payload: dict, cond) -> bool:
    val = _get(payload, cond.key)
    m = cond.match
    kind = type(m).__name__
    if kind == "MatchAny":
        return val in m.any
    if kind == "MatchValue":
        return val == m.value
    if kind == "MatchText":
        return val is not None and m.text in str(val)
    raise NotImplementedError(kind)


def _passes(payload: dict, flt) -> bool:
    if flt is None:
        return True
    return all(_match(payload, c) for c in (flt.must or []))


def describe_filter(flt) -> list:
    if flt is None:
        return []
    out = []
    for c in flt.must or []:
        m = c.match
        kind = type(m).__name__
        if kind == "MatchAny":
            value = {"count": len(m.any), "values": sorted(map(str, m.any))[:20]}
        else:
            value = getattr(m, "value", getattr(m, "text", None))
        out.append({"key": c.key, "match": kind, "value": value})
    return out


class FakeQdrantClient:
    def __init__(self, collections: dict):
        self.collections = collections
        self.calls = []

    def search(self, collection_name, query_vector, query_filter=None, limit=10,
               with_payload=True, score_threshold=None, **kwargs):
        self.calls.append({"op": "search", "collection": collection_name, "limit": limit,
                           "score_threshold": score_threshold, "filter": describe_filter(query_filter)})
        hits = []
        for p in self.collections.get(collection_name, []):
            if not _passes(p.payload, query_filter):
                continue
            score = sum(a * b for a, b in zip(query_vector, p.vector))
            if score_threshold is not None and score < score_threshold:
                continue
            hits.append(FakePoint(p.id, p.payload, p.vector, score))
        hits.sort(key=lambda h: (-h.score, h.id))
        return hits[:limit]

    def scroll(self, collection_name, scroll_filter=None, limit=10, offset=None,
               with_payload=True, with_vectors=False, **kwargs):
        self.calls.append({"op": "scroll", "collection": collection_name, "limit": limit,
                           "offset": offset, "with_vectors": with_vectors,
                           "filter": describe_filter(scroll_filter)})
        pts = [p for p in self.collections.get(collection_name, []) if _passes(p.payload, scroll_filter)]
        start = offset or 0
        page = pts[start:start + limit]
        nxt = start + limit if start + limit < len(pts) else None
        return [FakePoint(p.id, p.payload, p.vector if with_vectors else None) for p in page], nxt

"""Tests for the hybrid rerank in rag/query.py.

`rerank` is a pure function over a candidate list (no LanceDB/Ollama): it blends
vector similarity (1 - cosine distance) with query/chunk lexical overlap and
returns the top-k. Run under .venv-rag (rag/__init__ imports query → lancedb).
"""

from rag import query


def _hit(text, score):
    return {"text": text, "source": "x.pdf", "page": 1, "score": score}


def test_lexical_overlap_promotes_token_matching_chunk():
    # B has lower vector similarity but contains the query terms; with a balanced
    # alpha it should outrank A, which is vector-close but shares no tokens.
    hits = [
        _hit("generic combat rules and conditions", 0.20),   # vec_sim 0.80, lex 0
        _hit("Goblin Warrior Nimble Escape Scimitar", 0.40),  # vec_sim 0.60, lex 1
    ]
    out = query.rerank("goblin warrior", hits, k=2, alpha=0.5)
    assert out[0]["text"].startswith("Goblin Warrior")


def test_alpha_one_is_pure_vector_order():
    hits = [
        _hit("goblin warrior", 0.40),   # vec_sim 0.60
        _hit("unrelated text", 0.10),    # vec_sim 0.90
    ]
    out = query.rerank("goblin warrior", hits, k=2, alpha=1.0)
    assert out[0]["text"] == "unrelated text"   # higher vec_sim wins outright


def test_returns_at_most_k():
    hits = [_hit(f"chunk {i}", 0.1 * i) for i in range(5)]
    assert len(query.rerank("chunk", hits, k=3, alpha=0.7)) == 3


def test_none_score_treated_as_worst():
    hits = [
        _hit("no distance here", None),       # vec_sim 0
        _hit("goblin warrior here", 0.50),    # vec_sim 0.50
    ]
    out = query.rerank("goblin warrior", hits, k=2, alpha=1.0)
    assert out[0]["text"] == "goblin warrior here"


def test_rerank_exposes_component_scores():
    out = query.rerank("goblin", [_hit("a goblin appears", 0.3)], k=1, alpha=0.7)
    h = out[0]
    assert "vec_sim" in h and "lex" in h and "rerank_score" in h
    assert h["lex"] == 1.0   # the single query token is present


def test_empty_query_falls_back_to_vector():
    hits = [_hit("alpha", 0.4), _hit("beta", 0.1)]
    out = query.rerank("", hits, k=2, alpha=0.5)
    assert out[0]["text"] == "beta"  # nothing to lexically match → vector order

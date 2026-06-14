"""Query the RAG index: vector retrieval, optionally grounded LLM answer.

    python -m rag.query "goblin statblock"            # top-k chunks
    python -m rag.query "how does grappling work" -k 8
    python -m rag.query "stat block for a goblin" --answer   # LLM answer w/ citations

Reusable from code:
    from rag import search, answer
    hits = search("goblin", k=5)
    text = answer("what is a goblin's AC?")

Retrieval and generation errors propagate (no empty-result masking of an outage).
"""

import argparse
import re
import sys

import lancedb
import ollama

from . import config

_TOKEN_RE = re.compile(r"[a-z0-9]{2,}")


def _tokens(text):
    return set(_TOKEN_RE.findall((text or "").lower()))


def rerank(query, hits, k=5, alpha=None):
    """Re-rank vector candidates by ALPHA*vec_sim + (1-ALPHA)*lexical_overlap.

    `vec_sim` = 1 - cosine distance (a missing distance counts as 0). `lexical`
    = fraction of query tokens present in the chunk. Returns the top-k hits,
    each annotated with `vec_sim`, `lex`, and `rerank_score`.
    """
    if alpha is None:
        alpha = config.RERANK_ALPHA
    qt = _tokens(query)
    scored = []
    for h in hits:
        dist = h.get("score")
        vec_sim = 1.0 - dist if dist is not None else 0.0
        lex = (len(qt & _tokens(h["text"])) / len(qt)) if qt else 0.0
        scored.append(
            {**h, "vec_sim": vec_sim, "lex": lex,
             "rerank_score": alpha * vec_sim + (1.0 - alpha) * lex}
        )
    scored.sort(key=lambda x: x["rerank_score"], reverse=True)
    return scored[:k]


def _client():
    return ollama.Client(host=config.OLLAMA_HOST)


def _embed_query(client, text):
    return client.embeddings(
        model=config.EMBED_MODEL, prompt=config.EMBED_QUERY_PREFIX + text
    )["embedding"]


def search(query, k=5, rerank_candidates=None):
    """Return the top-k chunks for ``query`` as a list of dicts.

    By default this pulls `config.RERANK_CANDIDATES` by vector then hybrid-reranks
    down to k. Pass ``rerank_candidates=0`` for pure vector retrieval.
    """
    if rerank_candidates is None:
        rerank_candidates = config.RERANK_CANDIDATES
    do_rerank = rerank_candidates and rerank_candidates > k
    limit = max(k, rerank_candidates) if do_rerank else k

    db = lancedb.connect(config.DB_PATH)
    if config.TABLE not in db.list_tables().tables:
        raise RuntimeError(
            f"Table '{config.TABLE}' not found in {config.DB_PATH}. "
            f"Run `python -m rag.ingest --rebuild` first."
        )
    qvec = _embed_query(_client(), query)
    rows = (
        db.open_table(config.TABLE)
        .search(qvec)
        .metric(config.SEARCH_METRIC)
        .limit(limit)
        .to_list()
    )
    hits = [
        {
            "text": h["text"],
            "source": h["source"],
            "page": h["page"],
            "score": h.get("_distance"),
        }
        for h in rows
    ]
    return rerank(query, hits, k) if do_rerank else hits[:k]


def answer(query, k=5):
    """Retrieve top-k context and have the chat model answer, grounded + cited."""
    hits = search(query, k=k)
    context = "\n\n".join(
        f"[{h['source']} p.{h['page']}]\n{h['text']}" for h in hits
    )
    prompt = (
        "You are a D&D 5e rules assistant. Answer the question using ONLY the "
        "context below. Cite the source and page for each fact like (source p.N). "
        "If the answer isn't in the context, say so.\n\n"
        f"Context:\n{context}\n\nQuestion: {query}"
    )
    resp = _client().chat(
        model=config.CHAT_MODEL,
        messages=[{"role": "user", "content": prompt}],
    )
    return resp["message"]["content"]


def main(argv=None):
    parser = argparse.ArgumentParser(description="Query the RAG index.")
    parser.add_argument("query", help="Search query")
    parser.add_argument("-k", type=int, default=5, help="Number of chunks (default 5)")
    parser.add_argument(
        "--answer",
        action="store_true",
        help="Generate a grounded LLM answer instead of raw chunks.",
    )
    args = parser.parse_args(argv)

    if args.answer:
        print(answer(args.query, k=args.k))
        return

    hits = search(args.query, k=args.k)
    if not hits:
        print("No matches.", file=sys.stderr)
        return
    for i, h in enumerate(hits, 1):
        print(f"\n#{i}  {h['source']} p.{h['page']}  (dist={h['score']:.4f})")
        print(h["text"][:600].strip())


if __name__ == "__main__":
    main()

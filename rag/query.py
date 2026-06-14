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
import sys

import lancedb
import ollama

from . import config


def _client():
    return ollama.Client(host=config.OLLAMA_HOST)


def _embed_query(client, text):
    return client.embeddings(
        model=config.EMBED_MODEL, prompt=config.EMBED_QUERY_PREFIX + text
    )["embedding"]


def search(query, k=5):
    """Return the top-k chunks for ``query`` as a list of dicts."""
    db = lancedb.connect(config.DB_PATH)
    if config.TABLE not in db.list_tables().tables:
        raise RuntimeError(
            f"Table '{config.TABLE}' not found in {config.DB_PATH}. "
            f"Run `python -m rag.ingest --rebuild` first."
        )
    qvec = _embed_query(_client(), query)
    hits = (
        db.open_table(config.TABLE)
        .search(qvec)
        .metric(config.SEARCH_METRIC)
        .limit(k)
        .to_list()
    )
    return [
        {
            "text": h["text"],
            "source": h["source"],
            "page": h["page"],
            "score": h.get("_distance"),
        }
        for h in hits
    ]


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

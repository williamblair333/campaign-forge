# rag — local statblock/rules RAG

Self-hosted retrieval over a PDF rules corpus. PDF → chunks → Ollama embeddings
→ LanceDB → vector retrieval → optional grounded LLM answer. No cloud calls.

## Stack

| Piece | What | Where |
|---|---|---|
| Embeddings | `nomic-embed-text` (768-dim) | Ollama `:11434` |
| Generation | `llama3.1:8b` | Ollama `:11434` |
| Vector store | LanceDB | `rag/lancedb/` (gitignored) |
| Corpus | SRD 5.2.1 (CC-BY-4.0) | `rag/corpus/` (see ATTRIBUTION.md) |
| Python | `.venv-rag` | repo root |

## Dependency: the Ollama container must be running

Ollama runs in Docker (GPU, RTX 3060). The host `ollama` command is a wrapper
around this container — there is no native binary. After a reboot the container
may be down; start it with:

```bash
docker start open-webui-ollama-1
# or, from scratch:
docker compose -f /opt/proj/git/review/open-webui/docker-compose-cuda.yaml -p open-webui up -d ollama
docker exec open-webui-ollama-1 ollama pull nomic-embed-text
docker exec open-webui-ollama-1 ollama pull llama3.1:8b
```

A query against a stopped Ollama fails loudly with a connection error — that is
intentional (an outage must not look like an empty result).

## Setup

```bash
uv venv .venv-rag --python 3.13
uv pip install --python .venv-rag/bin/python -r rag/requirements.txt
```

## Ingest

```bash
.venv-rag/bin/python -m rag.ingest --rebuild        # all PDFs in rag/corpus/
.venv-rag/bin/python -m rag.ingest path/to/x.pdf    # specific files (append)
```

## Query

```bash
# top-k chunks
.venv-rag/bin/python -m rag.query "Goblin Warrior stat block" -k 5

# grounded LLM answer with (source p.N) citations
.venv-rag/bin/python -m rag.query "What is a goblin's AC and HP?" -k 6 --answer
```

From code (Phase 5 prep.py will use this):

```python
from rag import search, answer
hits = search("nimble escape", k=5)     # list of {text, source, page, score}
text = answer("how does grappling work?")  # grounded string
```

Config knobs (all env-overridable): see `config.py` — `OLLAMA_HOST`,
`RAG_EMBED_MODEL`, `RAG_CHAT_MODEL`, `RAG_CHUNK_CHARS`, `RAG_CHUNK_OVERLAP`.

## Chunking — layout-aware (statblock bleed fixed)

Extraction is **column-aware**: `order_blocks()` reads pymupdf text blocks down
the left column then the right (full-width titles act as flow breaks between
vertical bands), instead of the flat `get_text("text")` that interleaved the
SRD's two-column monster pages row-by-row. Chunking is **boundary-aware**:
`pack_chunks()` greedily fills up to `RAG_CHUNK_CHARS` but breaks only on
paragraph (blank-line) boundaries, so a statblock stays in one chunk; a single
paragraph longer than the limit falls back to character windows (`_chunks`).

Before this change, "Adult Red Dragon breath weapon" retrieved a chunk whose
tail bled into the **Young Red Dragon** statblock (wrong AC/HP); after, the top
hit is the Adult Red Dragon's own contiguous block. Pure functions are unit
-tested in `test_rag_ingest.py`.

> **An algorithm change requires a full rebuild, not an append** — re-run
> `ingest --rebuild` so old fixed-window chunks don't linger alongside new ones.

Residual: the SRD statblock tables still carry tab/newline noise from the PDF's
cell layout (e.g. `AC 12\t`, repeated `MOD SAVE`); that's inherent to the source
table and orthogonal to chunking. An optional rerank pass over top-k is a
possible future refinement.

## Reset

```bash
rm -rf rag/lancedb      # then re-run ingest
```

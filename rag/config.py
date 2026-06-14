"""Shared configuration for the campaign-forge RAG harness.

All knobs are overridable via environment variables so prep.py (Phase 5) and
ad-hoc runs can repoint at a different Ollama host or model without code edits.
"""

import os
from pathlib import Path

# Ollama (self-hosted, GPU). The open-webui compose binds 0.0.0.0:11434.
OLLAMA_HOST = os.environ.get("OLLAMA_HOST", "http://localhost:11434")
EMBED_MODEL = os.environ.get("RAG_EMBED_MODEL", "nomic-embed-text")
CHAT_MODEL = os.environ.get("RAG_CHAT_MODEL", "llama3.1:8b")

# nomic-embed-text requires task prefixes; without them retrieval quality drops
# sharply. Documents and queries must use matching asymmetric prefixes.
EMBED_DOC_PREFIX = "search_document: "
EMBED_QUERY_PREFIX = "search_query: "
# Cosine is the right metric for nomic embeddings (L2 over un-normalized vectors
# gives misleading distances).
SEARCH_METRIC = "cosine"

# On-disk locations (relative to this package).
RAG_DIR = Path(__file__).resolve().parent
CORPUS_DIR = RAG_DIR / "corpus"
DB_PATH = str(RAG_DIR / "lancedb")
TABLE = os.environ.get("RAG_TABLE", "rules")

# Chunking: paragraph-boundary packing up to this many chars (a statblock fits
# in ~1200); overlap carries the previous chunk's tail for cross-boundary recall.
CHUNK_CHARS = int(os.environ.get("RAG_CHUNK_CHARS", "1200"))
CHUNK_OVERLAP = int(os.environ.get("RAG_CHUNK_OVERLAP", "200"))

# Hybrid rerank: pull RERANK_CANDIDATES by vector, then re-score each as
# ALPHA*vector_similarity + (1-ALPHA)*lexical_overlap and keep the top-k. This
# lifts the specific statblock above generic rules text when the query names a
# creature. Set RAG_RERANK_CANDIDATES=0 to disable (pure vector). ALPHA stays
# vector-dominant so paraphrase queries (no shared tokens) aren't penalised hard.
RERANK_CANDIDATES = int(os.environ.get("RAG_RERANK_CANDIDATES", "20"))
RERANK_ALPHA = float(os.environ.get("RAG_RERANK_ALPHA", "0.7"))

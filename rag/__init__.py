"""Local RAG harness for campaign-forge.

Embeds a PDF rules corpus into LanceDB via Ollama and answers grounded queries
(e.g. statblock retrieval). Fully self-hosted: GPU Ollama on :11434, LanceDB on
disk. See ingest.py and query.py for the CLI entry points and the reusable
``search`` / ``answer`` functions.
"""

from .query import answer, search

__all__ = ["search", "answer"]

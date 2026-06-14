"""Ingest a PDF corpus into LanceDB via Ollama embeddings.

    python -m rag.ingest                 # ingest every PDF in rag/corpus/
    python -m rag.ingest path/to/x.pdf   # ingest specific files
    python -m rag.ingest --rebuild       # drop the table and re-ingest from scratch

Embedding errors (Ollama down, model not pulled) propagate — a failed ingest
must be loud, never a half-populated index that looks empty on query.
"""

import argparse
import sys
from pathlib import Path

import fitz  # pymupdf
import lancedb
import ollama
from tqdm import tqdm

from . import config


def _chunks(text, size, overlap):
    """Sliding character windows over a single page's text."""
    text = text.strip()
    if not text:
        return
    step = max(1, size - overlap)
    for start in range(0, len(text), step):
        window = text[start : start + size].strip()
        if window:
            yield window


def extract_chunks(pdf_path):
    """Yield (chunk_text, page_number) for one PDF."""
    doc = fitz.open(pdf_path)
    try:
        for page_index in range(doc.page_count):
            page_text = doc.load_page(page_index).get_text("text")
            for chunk in _chunks(page_text, config.CHUNK_CHARS, config.CHUNK_OVERLAP):
                yield chunk, page_index + 1
    finally:
        doc.close()


def embed(client, text):
    """Embed one chunk. Raises on backend failure (model name in the message)."""
    resp = client.embeddings(
        model=config.EMBED_MODEL, prompt=config.EMBED_DOC_PREFIX + text
    )
    return resp["embedding"]


def build_rows(client, pdf_paths):
    rows = []
    for pdf_path in pdf_paths:
        pairs = list(extract_chunks(pdf_path))
        source = Path(pdf_path).name
        for i, (chunk, page) in enumerate(
            tqdm(pairs, desc=source, unit="chunk")
        ):
            rows.append(
                {
                    "vector": embed(client, chunk),
                    "text": chunk,
                    "source": source,
                    "page": page,
                    "chunk_id": f"{source}#p{page}#{i}",
                }
            )
    return rows


def main(argv=None):
    parser = argparse.ArgumentParser(description="Ingest PDFs into LanceDB.")
    parser.add_argument("paths", nargs="*", help="PDF files (default: rag/corpus/*.pdf)")
    parser.add_argument(
        "--rebuild",
        action="store_true",
        help="Drop the existing table and rebuild from scratch.",
    )
    args = parser.parse_args(argv)

    if args.paths:
        pdf_paths = [Path(p) for p in args.paths]
    else:
        pdf_paths = sorted(config.CORPUS_DIR.glob("*.pdf"))

    missing = [str(p) for p in pdf_paths if not p.exists()]
    if missing:
        parser.error(f"PDF(s) not found: {', '.join(missing)}")
    if not pdf_paths:
        parser.error(f"No PDFs found in {config.CORPUS_DIR}")

    client = ollama.Client(host=config.OLLAMA_HOST)
    print(f"Embedding via {config.EMBED_MODEL} @ {config.OLLAMA_HOST}", file=sys.stderr)
    rows = build_rows(client, pdf_paths)
    if not rows:
        parser.error("No text extracted from the given PDFs.")

    db = lancedb.connect(config.DB_PATH)
    existing = config.TABLE in db.list_tables().tables
    if args.rebuild or not existing:
        db.create_table(config.TABLE, data=rows, mode="overwrite")
        action = "rebuilt"
    else:
        db.open_table(config.TABLE).add(rows)
        action = "appended to"

    print(
        f"{action} table '{config.TABLE}': {len(rows)} chunks from "
        f"{len(pdf_paths)} file(s) -> {config.DB_PATH}"
    )


if __name__ == "__main__":
    main()

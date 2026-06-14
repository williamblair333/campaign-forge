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
    """Sliding character windows over a single page's text.

    Fallback for a single paragraph longer than `size` (a statblock that won't
    fit whole); boundary-aware packing handles the common case.
    """
    text = text.strip()
    if not text:
        return
    step = max(1, size - overlap)
    for start in range(0, len(text), step):
        window = text[start : start + size].strip()
        if window:
            yield window


def order_blocks(blocks, page_width):
    """Join pymupdf text blocks in human reading order, column-aware.

    The SRD's monster pages are two-column; pymupdf's flat ``get_text("text")``
    interleaves the columns row-by-row, splicing the tail of one statblock into
    the head of its page-neighbour. This reads each column top-to-bottom (left,
    then right), with full-width blocks (titles/rules spanning both columns)
    acting as flow breaks between vertical bands.

    `blocks`: iterable of pymupdf block tuples — only indices 0-4
    (x0, y0, x1, y1, text) are used. Returns paragraphs joined by blank lines.
    """
    blocks = [b for b in blocks if str(b[4]).strip()]
    if not blocks:
        return ""

    mid = page_width / 2.0
    center = lambda b: (b[0] + b[2]) / 2.0          # noqa: E731
    full = lambda b: (b[2] - b[0]) > 0.6 * page_width  # noqa: E731

    narrow = [b for b in blocks if not full(b)]
    left = [b for b in narrow if center(b) < mid]
    right = [b for b in narrow if center(b) >= mid]
    two_column = len(left) >= 2 and len(right) >= 2

    if not two_column:
        ordered = sorted(blocks, key=lambda b: (round(b[1], 1), b[0]))
        return "\n\n".join(str(b[4]).strip() for b in ordered)

    # Full-width blocks split the page into vertical bands; within each band,
    # read the left column then the right column.
    fulls = sorted((b for b in blocks if full(b)), key=lambda b: b[1])
    boundaries = [b[1] for b in fulls]

    def band_of(y):
        return sum(1 for bnd in boundaries if y >= bnd)

    bands: dict[int, list] = {}
    for b in narrow:
        bands.setdefault(band_of(b[1]), []).append(b)

    out: list[str] = []
    for i in range(len(fulls) + 1):
        band = bands.get(i, [])
        col_left = sorted((b for b in band if center(b) < mid), key=lambda b: b[1])
        col_right = sorted((b for b in band if center(b) >= mid), key=lambda b: b[1])
        out += [str(b[4]).strip() for b in col_left]
        out += [str(b[4]).strip() for b in col_right]
        if i < len(fulls):
            out.append(str(fulls[i][4]).strip())

    return "\n\n".join(x for x in out if x)


def pack_chunks(text, size, overlap):
    """Greedily pack paragraphs up to `size`, breaking only on blank lines.

    Keeps a whole statblock in one chunk instead of bisecting it on a fixed
    character boundary. A single paragraph longer than `size` falls back to
    `_chunks` windowing. `overlap` carries the tail of the previous chunk into
    the next for cross-boundary recall.
    """
    paras = [p.strip() for p in text.split("\n\n") if p.strip()]
    chunks: list[str] = []
    cur = ""
    for p in paras:
        if len(p) > size:
            if cur:
                chunks.append(cur)
                cur = ""
            chunks.extend(_chunks(p, size, overlap))
            continue
        if cur and len(cur) + 2 + len(p) > size:
            chunks.append(cur)
            tail = cur[-overlap:] if overlap else ""
            cur = f"{tail}\n\n{p}" if tail and len(tail) + 2 + len(p) <= size else p
        else:
            cur = f"{cur}\n\n{p}" if cur else p
    if cur:
        chunks.append(cur)
    return [c for c in chunks if c.strip()]


def extract_page_text(page):
    """Column-aware plain text for one page (text blocks only)."""
    blocks = [
        b for b in page.get_text("blocks")
        if (len(b) < 7 or b[6] == 0) and str(b[4]).strip()   # block_type 0 = text
    ]
    return order_blocks(blocks, page.rect.width)


def extract_chunks(pdf_path):
    """Yield (chunk_text, page_number) for one PDF."""
    doc = fitz.open(pdf_path)
    try:
        for page_index in range(doc.page_count):
            page_text = extract_page_text(doc.load_page(page_index))
            for chunk in pack_chunks(page_text, config.CHUNK_CHARS, config.CHUNK_OVERLAP):
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

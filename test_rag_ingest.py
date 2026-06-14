"""Tests for the layout-aware chunking in rag/ingest.py.

Pure functions only (no fitz / Ollama / LanceDB): column-ordered block
extraction and boundary-aware paragraph packing. Block tuples mimic pymupdf's
get_text("blocks") shape: (x0, y0, x1, y1, text, block_no, block_type).
"""

from rag import ingest


def blk(x0, y0, x1, y1, text):
    return (x0, y0, x1, y1, text, 0, 0)


# ── order_blocks (column-aware reading order) ──────────────────────────────────

PAGE_W = 600


def test_order_two_columns_left_then_right():
    blocks = [
        blk(40, 100, 260, 140, "L2"),
        blk(40, 40, 260, 80, "L1"),
        blk(320, 40, 560, 80, "R1"),
        blk(320, 100, 560, 140, "R2"),
    ]
    assert ingest.order_blocks(blocks, PAGE_W).split("\n\n") == ["L1", "L2", "R1", "R2"]


def test_order_full_width_header_above_two_columns():
    blocks = [
        blk(40, 10, 560, 30, "HEADER"),        # full width → its own flow break
        blk(40, 60, 260, 90, "L1"),
        blk(40, 120, 260, 150, "L2"),
        blk(320, 60, 560, 90, "R1"),
        blk(320, 120, 560, 150, "R2"),
    ]
    assert ingest.order_blocks(blocks, PAGE_W).split("\n\n") == \
        ["HEADER", "L1", "L2", "R1", "R2"]


def test_order_single_column_top_to_bottom():
    blocks = [
        blk(40, 80, 560, 120, "P2"),
        blk(40, 20, 560, 60, "P1"),
    ]
    assert ingest.order_blocks(blocks, PAGE_W).split("\n\n") == ["P1", "P2"]


def test_order_skips_empty_blocks():
    blocks = [blk(40, 20, 560, 60, "P1"), blk(40, 80, 560, 120, "   ")]
    assert ingest.order_blocks(blocks, PAGE_W).split("\n\n") == ["P1"]


# ── pack_chunks (boundary-aware packing) ───────────────────────────────────────

def test_pack_small_paras_into_one_chunk():
    chunks = ingest.pack_chunks("Alpha\n\nBeta\n\nGamma", size=100, overlap=0)
    assert len(chunks) == 1
    assert "Alpha" in chunks[0] and "Gamma" in chunks[0]


def test_pack_breaks_at_paragraph_boundary_not_midword():
    p1, p2 = "x" * 80, "y" * 80
    chunks = ingest.pack_chunks(p1 + "\n\n" + p2, size=100, overlap=0)
    assert len(chunks) == 2
    assert chunks[0] == p1
    assert chunks[1] == p2


def test_pack_keeps_statblock_paragraph_whole():
    statblock = ("GOBLIN " * 150).strip()   # ~1049 chars, one paragraph, < size
    chunks = ingest.pack_chunks(statblock, size=1200, overlap=200)
    assert len(chunks) == 1
    assert chunks[0] == statblock


def test_pack_windows_oversized_paragraph():
    chunks = ingest.pack_chunks("z" * 300, size=100, overlap=20)
    assert len(chunks) > 1
    assert all(len(c) <= 100 for c in chunks)


# ── _chunks (existing fallback windower) ───────────────────────────────────────

def test_chunks_slides_with_overlap():
    out = list(ingest._chunks("abcdefghij", size=4, overlap=1))  # step=3
    assert out[0] == "abcd"
    assert out[-1].endswith("j")

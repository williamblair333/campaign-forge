# Roadmap

---

## Completed

### Phase 1 — Foundation ✅ (2026-06-04)
- Kanka Community Edition deployed via Docker Compose
- Three upstream bugs patched for single-domain self-hosted installs
- REST API verified end-to-end: campaigns, locations, characters, organisations, events, notes, tags, entity attributes
- `kanka_client.py` Python client written and tested
- Public GitHub repo created: https://github.com/williamblair333/campaign-forge

### Phase 2 — World creation conversation loop ✅ (2026-06-04)
- `world_builder.py` — conversational CLI: describe campaign → Claude extracts entities → pushed to Kanka CE
- `map_tools.py` — parse FMG `.map` exports; `parse` shows summary, `sync` pushes burgs→locations and states→organisations with duplicate-skip
- `scripts/fmg-setup.sh` — clones Azgaar/Fantasy-Map-Generator, serves on http://localhost:8082 via nginx (localhost-only bind)

### Phase 3 — Foundry VTT integration ✅ (2026-06-05)
- Foundry VTT 14.363 installed via felddy Docker image, running at http://100.118.143.57:30000
- `docker-compose.foundry.yml` + `scripts/foundry-setup.sh` — manage Foundry lifecycle (start/stop/backup)
- `foundry-vtt-mcp` cloned and npm-installed — 37 MCP tools available
- License key and admin key stored in `.env`
- **WebSocket fixed (2026-06-05):** switched to `network_mode: host`; join page form now renders for remote Tailscale browsers
- MCP bridge serverHost now auto-detects from `window.location.hostname` — no manual config needed
- **Smoke tests PASSED (2026-06-13):** end-to-end Claude→bridge→Foundry verified (world info, scenes, create + read-back NPC actor)
- **Added `delete-actors` MCP tool (2026-06-13):** GM-gated, PERMANENT; preserved as `patches/delete-actors.patch` (fork is gitignored)

### Phase 4 — Local AI / RAG ✅ (2026-06-13; chunking tuned 2026-06-14)
- Built **in-repo `rag/`** (decision: skipped `dnd-llm-game`) — GPU Ollama + LanceDB over SRD 5.2.1 (CC-BY-4.0)
- `rag/ingest.py` + `rag/query.py`; reusable `search`/`answer`; retrieval + grounded answers verified
- **Layout-aware chunking** (PR #16): column-ordered extraction + paragraph-boundary packing fixed the two-column statblock bleed (cross-attribution). Re-ingested (1761 chunks); `test_rag_ingest.py`. Only optional refinement left: a top-k rerank.

### Phase 5 — CampaignGenerator integration ✅ (2026-06-14)
- `kanka_sync.py` — pull world_state from Kanka CE → write `world_state.md` (PR #11; verified vs live campaign 1). Paginated `kanka_client._get_all`.
- `kanka_push.py` — push an edited `world_state.md` back to Kanka CE: parse section-profile → match by name → create/update (PR #12). Dry-run by default, `--apply` commits, never deletes; skip-if-unchanged (no HTML clobber); continue-on-error. Generic `KankaClient.create()`/`update()`. 19 pytest cases. Round-trip verified lossless against live campaign 1.
- `prep.py` reads `world_state.md` as a grounding source — already wired via `config.yaml` (`world_state → docs/world_state.md`); no CampaignGenerator change needed. Post-session update step = `kanka_push.py --apply` after the distill/synthesise pipeline regenerates the doc.

### Phase 7 — Self-hosted 5e data layer ✅ (2026-06-14)
- `dnd5e_mcp.py` — FastMCP server: `lookup_monster`, `lookup_spell`, `lookup_item`, `search_5e`
- Full 5etools compendium loaded from `revilowaldow/5etools-mirror-2.github.io` into DuckDB in-memory (4440 monsters, 558 spells, 1773 items); exact + fuzzy (jaro_winkler ≥ 0.85) lookup
- `scripts/dnd5e-fetch.sh` — sparse-clone fetch; auto-runs on first startup; data gitignored
- 20 pytest cases; `mnehmos.open5e.mcp` (cloud) retired

### Phase 7 — AI Table (table/ module) ✅ Phase A (2026-06-14)
- `table/` module: orchestrator, gm_agent (3 backends), player_agent, personas, combat, dice, transcript, smoke_test
- Claude Sonnet GM + Ollama llama3.1:8b players; `--gm-backend cli` uses Max subscription (no API key)
- `--stream` flag for live stdout; comprehensive dice parser (kh/kl/dh/dl, case-insensitive)
- Monster HP auto-apply via `RollRequest.target`; condition removal via `conditions_remove`
- Phase A live run: TPK Round 5, 65 turns. 88 tests passing. (PRs #28, #29, #30)

### Phase 6 — MCP servers ✅ (2026-06-14)
- **campaign-forge `kanka_mcp.py`** — FastMCP server exposing the Kanka sync engine: `kanka_pull` (read-only), `kanka_push_preview` (dry-run), `kanka_push_apply` (commit; never deletes). Guarded FastMCP import (core unit-tested without `mcp`); pinned `requirements-mcp.txt`; `.mcp.json.example`. 5 tests; server build + live pull verified. (PR #14)
- **CampaignGenerator `mcp_server.py`** — the named tools already existed: `get_world_state`, `get_campaign_state`, `run_prep` (= `session_prep`), plus ~20 more.
- **`run_session_pipeline` — intentionally not built.** CG's `sd_*` pipeline is deliberately human-gated (no pipeline-runner by design; see `docs/cli/session_doc_pipeline.md`). Auto-chaining would bypass the review gates and burn tokens on unreviewed plans. Per-stage explicitly-invoked tools are the path if CG-side automation is wanted later.

---

## In Progress

### AI Table — Phase B (5 players, 3 combats)
- Gate: human eyeball Phase A transcript (`transcript.md`) first
- If cleared: add 3 remaining Ollama player personas, run 3 distinct combats, verify HP/condition tracking improved
- Phase C (Kokoro TTS) follows after Phase B sign-off

---

## Planned

### Polish shipped 2026-06-14
- RAG **layout-aware chunking** (PR #16) + **hybrid rerank** (PR #18).
- **FMG headless map-gen** pinned to v1.99 (PR #19) — `scripts/fmg-generate.py` (Playwright) → map_tools-compatible JSON → Kanka sync. Closes the "FMG has no REST API" gap.
- `foundryvtt-rest-api` — **skipped by decision** (MCP bridge already covers Foundry).

### Resolved 2026-06-14
- **Kanka CE upstream patches** — verified, **no PR warranted** (minio already fixed upstream via s3→minio endpoint; isApi removal is deploy-specific; ports are local). Patches stay local-only.
- **`map_tools.py` docstring** — fixed (PR #21).

### Next candidates (optional / research — core stack is usable)
- Migrate FMG off the v1.99 pin — only if a newer FMG feature is wanted (needs Node-24 toolchain + Vite build + re-reverse the new export; the v1.99 pin works for the seeded-map → Kanka pipeline).
- Per-stage CampaignGenerator MCP tools (gate-respecting) — only if Claude-driven CG post-session automation is wanted.
- **Autonomous AI table** — MOVED TO IN PROGRESS (brainstorming complete 2026-06-14).

---

## Research / Exploration (not committed phases)

### Autonomous AI table — AI GM + distinct AI players (optional voice)
- One AI GM (Claude) + N AI players (local Ollama / mixed models), each a distinct
  persona, playing AI-authored one-shot modules. Optional per-agent TTS (Kokoro first).
- Consumes existing infra: `rag/` (SRD rulings), Foundry MCP (scene/dice/tokens),
  Kanka (`kanka_sync.py` canon), CampaignGenerator (transcript → narrative).
- Correctly sequenced after Phases 5–6. Gate: prove the loop with the weekend
  experiment (1 GM + 2 players, 1 combat, text-only) before scoping further.
- Full writeup: `reviews/ai-table-gm-and-players-exploration.md` (gitignored, local).

---

## Open Questions

- Can Fantasy Map Generator be headlessly driven (Puppeteer/Playwright) for agent-triggered generation?
- What's the canonical source of truth for campaign state — Kanka CE or CampaignGenerator flat markdown files?
- ~~Is there a Docker-composable Open5e or 5etools API for fully offline 5e data?~~ ✅ RESOLVED — `dnd5e_mcp.py` (Phase 7, PR #27): no Docker container needed; DuckDB in-memory + 5etools mirror sparse-clone.

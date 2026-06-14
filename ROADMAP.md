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

### Phase 6 — MCP servers ✅ (2026-06-14)
- **campaign-forge `kanka_mcp.py`** — FastMCP server exposing the Kanka sync engine: `kanka_pull` (read-only), `kanka_push_preview` (dry-run), `kanka_push_apply` (commit; never deletes). Guarded FastMCP import (core unit-tested without `mcp`); pinned `requirements-mcp.txt`; `.mcp.json.example`. 5 tests; server build + live pull verified. (PR #14)
- **CampaignGenerator `mcp_server.py`** — the named tools already existed: `get_world_state`, `get_campaign_state`, `run_prep` (= `session_prep`), plus ~20 more.
- **`run_session_pipeline` — intentionally not built.** CG's `sd_*` pipeline is deliberately human-gated (no pipeline-runner by design; see `docs/cli/session_doc_pipeline.md`). Auto-chaining would bypass the review gates and burn tokens on unreviewed plans. Per-stage explicitly-invoked tools are the path if CG-side automation is wanted later.

---

## In Progress

_(none)_

---

## Planned

### Polish shipped 2026-06-14
- RAG **layout-aware chunking** (PR #16) + **hybrid rerank** (PR #18).
- **FMG headless map-gen** pinned to v1.99 (PR #19) — `scripts/fmg-generate.py` (Playwright) → map_tools-compatible JSON → Kanka sync. Closes the "FMG has no REST API" gap.
- `foundryvtt-rest-api` — **skipped by decision** (MCP bridge already covers Foundry).

### Next candidates (optional / external — core stack is usable)
- **Upstream the 3 Kanka CE patches** as PRs to `kinnewig/kanka-community-edition` — external publishing; needs an explicit go-ahead (deferred).
- Fix `map_tools.py` docstring (".map = JSON" is wrong; json bridge is `fmg-generate.py`).
- Migrate FMG off the v1.99 pin (Node 24 + Vite build + parser re-verify) only if a newer FMG is wanted.
- Per-stage CampaignGenerator MCP tools (gate-respecting) — only if Claude-driven CG post-session automation is wanted.

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
- Is there a Docker-composable Open5e or 5etools API for fully offline 5e data?

# campaign-forge — Session Handoff

**Date:** 2026-06-14
**Status:** Phase 3 COMPLETE — Kanka CE + world builder + map tools + Foundry VTT all running. WebSocket fixed. foundry-vtt-mcp installed and MCP bridge auto-detect deployed. **Smoke tests PASSED 2026-06-13** — full Claude→bridge→Foundry round-trip verified (get-world-info, list-scenes, created NPC actor from SRD compendium, read back full statblock). Docker Port Registry established and all inter-project port conflicts resolved (2026-06-07); dcup `up -f` flag-order bug fixed 2026-06-13. **Phase 4 (local RAG) DONE 2026-06-13** — in-repo `rag/` over SRD 5.2.1 on GPU Ollama; retrieval + grounded answers work, chunking quality tuning pending. **Phase 5 COMPLETE 2026-06-14** — `kanka_sync.py` pulls Kanka CE → `world_state.md` (PR #11); `kanka_push.py` pushes an edited `world_state.md` back into Kanka (create/update, dry-run by default, never deletes — PR #12); and `prep.py` already reads `world_state.md` as a required grounding doc (config-declared, no CampaignGenerator change needed). The Kanka ⇄ CampaignGenerator sync loop is closed. **Phase 6 COMPLETE 2026-06-14** — `kanka_mcp.py` (PR #14) exposes the sync engine as MCP tools (`kanka_pull` / `kanka_push_preview` / `kanka_push_apply`) so Claude drives it directly; CampaignGenerator's `mcp_server.py` already had `get_world_state` / `get_campaign_state` / `run_prep` (as `session_prep`). The 4th named tool `run_session_pipeline` was **intentionally not built** — CG's `sd_*` pipeline is deliberately human-gated (no runner by design; see `project_campaigngenerator_pipeline_gates` memory). Also explored an **autonomous AI table** (AI GM + distinct AI players, optional voice) — writeup in `reviews/` (gitignored), logged as a research track in ROADMAP.
**Origin sessions:** CampaignGenerator analysis + architecture discussion → Kanka CE deployment → world builder + map tools → Foundry VTT setup → Foundry WebSocket debugging → Foundry join page WebGL investigation

---

## What This Project Is

A self-hosted, AI-orchestrated TTRPG campaign management stack. The goal is to build the **infrastructure and integration layer** that lets a DM:

1. Talk to Claude to create and evolve a campaign world
2. Have Claude push structured entities (NPCs, locations, factions, events) into a self-hosted world-state store
3. Generate and manage maps, scenes, and VTT content programmatically
4. Run sessions through Foundry VTT with AI-assisted prep
5. Post-session: process transcripts → narrative documents → updated world state

CampaignGenerator (at `/opt/proj/CampaignGenerator`) remains the **application-layer brain** — encounter prep, narrative pipeline, grounding docs. This project builds the **infrastructure layer** beneath and around it.

---

## Phase 1 Status: DONE ✅

### What was built

- Cloned Kanka CE to `/opt/proj/campaign-forge/kanka-ce`
- Full Docker Compose stack running (8 containers): Laravel PHP, MariaDB, Redis, MinIO, Meilisearch, Thumbor, Mailpit
- Stack is accessible at **http://localhost:8081**
- Admin user: `williamblair333@gmail.com` / `KankaForge2026!`
- API token stored in `/opt/proj/campaign-forge/.env` as `KANKA_TOKEN`
- Campaign created: "The Shattered Realm" (id=1)
- Python client: `/opt/proj/campaign-forge/kanka_client.py` — full CRUD for campaigns, locations, characters, organisations, events, notes, tags, entity attributes

### Bug fixes applied to Kanka CE source

1. **`app/Services/DomainService.php`** — removed `$request->is('api/*')` from `isApi()`.
   - **Why:** On single-domain self-hosted installs, this caused `/api/*` requests to register routes under the API subdomain (`api.kanka.io`) without the `/api` path prefix, so they never matched incoming requests.
   - Fix: `isApi()` now only checks the request host against `config('domains.api')`.

2. **`config/filesystems.php`** — added `minio` disk definition.
   - **Why:** `.env.example` ships with `FILESYSTEM_DRIVER=minio` but no `minio` disk was defined in the config. Campaign creation threw "Disk [minio] does not have a configured driver."

3. **`docker-compose.yml`** — decoupled host port mappings from container ports.
   - `REDIS_HOST_PORT` (default 6379) overrides only the host-side Redis port binding.
   - `MINIO_HOST_PORT` / `MINIO_CONSOLE_HOST_PORT` override MinIO host ports.
   - **Why:** On this machine, ports 6379 (Redis) and 9000 (MinIO/Portainer) were occupied.
   - Local `.env` uses: `REDIS_HOST_PORT=6380`, `MINIO_HOST_PORT=9010`, `MINIO_CONSOLE_HOST_PORT=9011`

### Kanka CE entity schema (confirmed via API)

| Entity type | API path | Key fields |
|---|---|---|
| locations | `/campaigns/{id}/locations` | name, type, entry, parent_location_id |
| characters | `/campaigns/{id}/characters` | name, title, entry, is_dead |
| organisations | `/campaigns/{id}/organisations` | name, type, entry |
| events | `/campaigns/{id}/events` | name, type, entry, date |
| notes | `/campaigns/{id}/notes` | name, type, entry, is_pinned |
| tags | `/campaigns/{id}/tags` | name, colour, type |
| entity attributes | `/campaigns/{id}/entities/{eid}/attributes` | name, value, type (0-5) |

### Key finding: `.mcp.json` is dev tooling only

The `laravel-boost` MCP server in Kanka CE's `.mcp.json` is a Laravel developer assistant (code navigation, test running), **not** a campaign entity CRUD interface. All entity management goes through the REST API at `/api/1.0/`.

---

## The Full Stack (Verified Self-Hosted Tools)

| Layer | Tool | Source | MCP/API |
|---|---|---|---|
| World state / lore store | Kanka Community Edition | [kinnewig/kanka-community-edition](https://github.com/kinnewig/kanka-community-edition) | ✅ REST API at localhost:8081 |
| VTT | Foundry VTT | foundryvtt.com (one-time license) | ✅ via bridge |
| VTT ↔ Claude MCP bridge | foundry-vtt-mcp | [adambdooley/foundry-vtt-mcp](https://github.com/adambdooley/foundry-vtt-mcp) | ✅ 37 MCP tools |
| VTT REST API | foundryvtt-rest-api | [ThreeHats/foundryvtt-rest-api](https://github.com/ThreeHats/foundryvtt-rest-api) | ✅ REST |
| Local AI / lore RAG | dnd-llm-game | [tegridydev/dnd-llm-game](https://github.com/tegridydev/dnd-llm-game) | ✅ FastAPI REST + SSE |
| 5e rules data (local) | dnd5e_mcp.py | self-hosted, full 5etools compendium via DuckDB in-memory | ✅ MCP (Python) |
| Map generation | Fantasy Map Generator | [Azgaar/Fantasy-Map-Generator](https://github.com/Azgaar/Fantasy-Map-Generator) | ⚠️ Docker, GeoJSON export only |
| Campaign prep / narrative | CampaignGenerator | `/opt/proj/CampaignGenerator` | ✅ existing |

**VTT alternative (free):** [skyloutyr/VTT](https://github.com/skyloutyr/VTT) — if Foundry license is not wanted
**Lightweight VTT alternative:** [Dungeon Revealer](https://github.com/dungeon-revealer/dungeon-revealer) — Docker, fog-of-war focused

---

## End-to-End Workflow (What We're Building Toward)

```
CAMPAIGN CREATION
─────────────────
DM talks to Claude
  → Claude extracts entities (NPCs, locations, factions, history)
  → kanka_client.py: creates articles for each entity via REST API
  → Fantasy Map Generator: generate world map → export GeoJSON
  → Foundry VTT: import map as scene

PRE-SESSION PREP
────────────────
DM: "Session 4 — party infiltrates the capital"
  → CampaignGenerator/prep.py reads world_state.md (synced from Kanka CE)
  → Lore Oracle checks new beat against canon [human review]
  → Encounter Architect generates encounter doc
  → foundry-vtt-mcp: creates Scene, populates NPC actors, sets fog of war
  → dnd-llm-game: RAG over local PDFs for statblocks (fully offline)

DURING SESSION
──────────────
  Players connect to self-hosted Foundry VTT
  DM runs session — maps, tokens, fog of war, dice
  Zoom records → session.vtt

POST-SESSION
────────────
  vtt_summary.py → summaries/session_N.md
  scene_extract.py → vtt_extractions/
  sd_consistency.py → check vs campaign state [human review]
  sd_plan.py → narrative plan [human review]
  sd_narrate.py → per-character narration
  assemble.py → final session doc (sent to players)
  campaign_state.py + distill.py → update grounding docs
  Claude via kanka_client.py → update NPC states, location states, timeline
```

---

## Build Order

### Phase 1 — Foundation ✅ DONE
- [x] Clone and Docker-compose Kanka CE locally
- [x] Verify REST API works — entity CRUD confirmed
- [x] Document the Kanka CE entity schema (see table above)
- [x] Write `kanka_client.py` — Python client for all key entity types

### Phase 2 — World creation conversation loop ✅ DONE
- [x] `world_builder.py` — conversational CLI: describe campaign → Claude extracts entities → pushed to Kanka CE
- [x] `map_tools.py` — parse Azgaar FMG `.map` exports; `parse` shows summary, `sync` pushes burgs + states
- [x] `scripts/fmg-setup.sh` — serves FMG on http://localhost:8082 via nginx

### Phase 3 — Foundry VTT integration ✅ DONE (smoke tests pending)
- [x] Foundry VTT 14.363 running via felddy Docker image at http://100.118.143.57:30000
- [x] `docker-compose.foundry.yml` + `scripts/foundry-setup.sh` — lifecycle management
- [x] `foundry-vtt-mcp` cloned and npm-installed (37 MCP tools)
- [x] **WebSocket fixed** — switched to `network_mode: host`; remote Tailscale browsers can now connect
- [x] **Smoke tests PASSED (2026-06-13)** — GM logged in on dma64, MCP bridge connected on port `31415` (serverHost blank/auto-detect). Claude created NPC actor "MCP Smoke Test Goblin" from `dnd5e.monsters` and read back full statblock. End-to-end write path confirmed.
- [x] **Added `delete-actors` MCP tool (2026-06-13)** — the bridge had no actor-delete. Added a GM-gated, `deleteData`-HIGH_RISK-gated, PERMANENT delete-actors tool across 4 files in the (gitignored) foundry-vtt-mcp fork. **Local fork edit saved as `patches/delete-actors.patch`** — reapply with `git apply` after any re-clone, then `npm run build:server build:foundry` and redeploy `packages/foundry-module/dist/*` → `foundry/data/Data/modules/foundry-mcp-bridge/dist/`. Loading it needs: (a) Foundry browser F5, (b) foundry-mcp MCP server reconnect (`/mcp`). World backed up first to `foundry-world-backup-the-shattered-realm-2026-06-13.tgz`.
- [ ] Optionally wire foundryvtt-rest-api as a REST alternative

### Phase 4 — Local AI / RAG ✅ DONE (2026-06-13; chunking tuned 2026-06-14)
- [x] **Decision:** skipped dnd-llm-game; built a **minimal in-repo RAG** in `rag/` instead (less bloat, full control). See `rag/README.md`.
- [x] Ollama stands up via the existing open-webui CUDA compose (GPU RTX 3060, `:11434`). Container `open-webui-ollama-1`. Models: `nomic-embed-text` (embed) + `llama3.1:8b` (gen). Native `ollama` is a Docker wrapper, not a binary.
- [x] Corpus: official **SRD 5.2.1** (CC-BY-4.0) in `rag/corpus/` (+ ATTRIBUTION.md). Re-download URL recorded.
- [x] Pipeline: `rag/ingest.py` (PDF→chunks→embed→LanceDB) + `rag/query.py` (retrieve + grounded `--answer`). Reusable `from rag import search, answer`. **1,596 chunks** ingested, 12 MB LanceDB.
- [x] Statblock retrieval verified end-to-end: "Goblin Warrior Nimble Escape Scimitar" → SRD p.290 ranks #1–3 (cosine 0.26); grounded LLM answer with citations works.
- [x] **Chunking tuned (PR #16, 2026-06-14):** `order_blocks()` reads columns left-then-right (full-width titles = flow breaks); `pack_chunks()` packs to paragraph boundaries so a statblock stays one chunk. Fixed the cross-attribution bleed — "Adult Red Dragon breath weapon" now returns the Adult (not Young) Red Dragon. Re-ingested (1761 chunks). `test_rag_ingest.py` (9 cases). **Algo changes need `ingest --rebuild`, not append.** Optional rerank over top-k is the only remaining refinement; SRD table tab/newline noise is inherent to the PDF.
- [x] **`.gitignore`:** `rag/lancedb/`, `rag/corpus/*.pdf`, `.venv-rag/` all ignored.
- [ ] **Post-reboot:** Ollama container may be down — `docker start open-webui-ollama-1` (queries fail loudly if it's not up).

### Phase 5 — CampaignGenerator integration ✅ DONE (2026-06-14)
- [x] `kanka_sync.py` — pull world_state from Kanka CE → write world_state.md (PR #11).
- [x] `kanka_push.py` — push an edited world_state.md back to Kanka CE: parse the section-profile doc → match by name → create/update (PR #12). **Dry-run by default, `--apply` commits, never deletes**, skip-if-unchanged (no HTML clobber), continue-on-error. Generic `KankaClient.create()`/`update()` added. 19 pytest cases.
- [x] Wire prep.py to read world_state.md — **no code change needed**: `config/config.yaml` already declares `world_state → docs/world_state.md` and `prep.py`/`assemble_docs` loads it as a *required* grounding doc. Integration is operational: `kanka_sync.py --output docs/world_state.md` (in the campaign workspace) feeds the slot; `kanka_push.py --input docs/world_state.md --apply` pushes session changes back.
- [x] Post-session Kanka update step = `kanka_push.py --apply` after the distill/synthesise pipeline regenerates `world_state.md`.

### Phase 6 — MCP servers ✅ DONE (2026-06-14)
- [x] **campaign-forge `kanka_mcp.py`** (PR #14) — FastMCP server exposing the Kanka sync engine: `kanka_pull` (read-only) / `kanka_push_preview` (dry-run) / `kanka_push_apply` (commit, never deletes). Guarded FastMCP import (core unit-tested without `mcp`); `requirements-mcp.txt`, `.mcp.json.example`. Server build + live pull verified.
- [x] CampaignGenerator `mcp_server.py` already exposed `run_prep` (= `session_prep`), `get_world_state`, `get_campaign_state` (+ ~20 more) — no change needed.
- [x] `run_session_pipeline` — **intentionally not built.** CG's `sd_*` pipeline is deliberately human-gated (no runner by design; `docs/cli/session_doc_pipeline.md`). Per-stage gate-respecting tools are the path if CG-side automation is wanted. See `project_campaigngenerator_pipeline_gates` memory.

---

## Service Ports (Local)

| Service | Host port | Notes |
|---|---|---|
| Kanka CE web | 8081 | Main app |
| MariaDB | 3306 | DB |
| Redis | 6380 | `.env` override; docker-compose default is now 6381 (6379 reserved for Uncle-J langfuse) |
| MinIO S3 | 9010 | Host port (internal: 9000) |
| MinIO Console | 9011 | Admin UI |
| Meilisearch | 7700 | Search |
| Mailpit | 8025 | Email UI |
| Thumbor | 8888 | Image proxy |

## Start Kanka CE

```bash
cd /opt/proj/campaign-forge/kanka-ce
vendor/bin/sail up -d
```

## Stop Kanka CE

```bash
cd /opt/proj/campaign-forge/kanka-ce
vendor/bin/sail down
```

---

## Open Questions (still to resolve)

1. **5e data layer** — ✅ RESOLVED. `dnd5e_mcp.py` FastMCP server (4 tools: `lookup_monster` / `lookup_spell` / `lookup_item` / `search_5e`) loads full 5etools compendium via DuckDB in-memory (4440 monsters, 558 spells, 1773 items). `scripts/dnd5e-fetch.sh` auto-populates `data/dnd5e/` on first run. `mnehmos.open5e.mcp` retired. See spec PR #24 for design rationale.
2. **Map generation gap** — ✅ RESOLVED (PR #19). Headless Playwright gen ships as `scripts/fmg-generate.py`, pinned to FMG v1.99. v1.99 pin migration deferred indefinitely (needs Node 24 + Vite rebuild; not worth it unless a newer FMG feature is required).
3. **Sync strategy** — ✅ RESOLVED (Phase 5). Kanka CE is the canonical source of truth. `kanka_sync.py` pulls → `world_state.md`; `kanka_push.py` pushes edits back. Loop is closed.
4. **Kanka CE upstream patches** — ✅ RESOLVED (2026-06-14). Verified no upstream PRs warranted — minio fix already upstream; isApi removal is deploy-specific. Patches stay local-only.
5. **foundry-vtt-mcp API key** — need to confirm how to generate a Foundry API key for the bridge (admin panel or artisan command).

---

## GitHub

https://github.com/williamblair333/campaign-forge

---

## Start Next Session With

```bash
cd /opt/proj/campaign-forge
source .env

# Check Kanka CE (start if needed: cd kanka-ce && vendor/bin/sail up -d)
curl -s -H "Authorization: Bearer $KANKA_TOKEN" http://localhost:8081/api/1.0/campaigns | python3 -m json.tool

# Check Foundry VTT (start if needed: bash scripts/foundry-setup.sh)
bash scripts/foundry-setup.sh status

# RAG (Phase 4, DONE): Ollama auto-restarts (unless-stopped). If down:
#   docker start open-webui-ollama-1
#   .venv-rag/bin/python -m rag.query "Goblin Warrior stat block" -k 5
# Foundry bridge: smoke tests PASSED. delete-actors tool added (PERMANENT, GM-only).
#   After any foundry-vtt-mcp re-clone: git apply patches/delete-actors.patch,
#   rebuild, redeploy dist, then Foundry F5 + Claude /mcp reconnect.
#
# Phases 5 & 6 DONE: Kanka ⇄ CampaignGenerator loop closed + driven from Claude.
#   CLI:  python kanka_sync.py --campaign 1 --output docs/world_state.md         # pull
#         python kanka_push.py --campaign 1 --input docs/world_state.md          # push (dry run)
#         python kanka_push.py --campaign 1 --input docs/world_state.md --apply  # push (commit)
#         (export KANKA_TOKEN first — `set -a; source .env; set +a`)
#   MCP:  python3 -m venv .venv-mcp && .venv-mcp/bin/pip install -r requirements-mcp.txt
#         register kanka_mcp.py via .mcp.json.example (pass KANKA_TOKEN in env block)
#         tools: kanka_pull / kanka_push_preview / kanka_push_apply
#
# Core build COMPLETE + polished. Done 2026-06-14 (this session): self-hosted 5e data layer
# (dnd5e_mcp.py — PR #27): 4440 monsters, 558 spells, 1773 items via DuckDB in-memory from
# 5etools mirror-2; retire mnehmos.open5e.mcp. Also done earlier: RAG hybrid rerank (PR #18),
# RAG layout-aware chunking (PR #16), FMG headless map-gen pinned to v1.99 (PR #19).
# foundryvtt-rest-api: SKIPPED by decision (MCP bridge already covers it).
#
# 5e MCP: python3 -m venv .venv-dnd5e && .venv-dnd5e/bin/pip install -r requirements-dnd5e.txt
#         bash scripts/dnd5e-fetch.sh   # one-time; auto-runs on startup if data absent
#         register dnd5e_mcp.py via .mcp.json.example
#         tools: lookup_monster / lookup_spell / lookup_item / search_5e
#
# ACTIVE NEXT TASK — AI Table Experiment (design spec in progress):
#   Brainstorming complete (2026-06-14). Decisions locked:
#     - Incremental: Phase A (1 GM + 2 players, 1 combat) → B (5 players, 3 combats) → C (Kokoro TTS)
#     - World: The Shattered Realm (Kanka CE canon); kanka_sync before play, kanka_push after
#     - 3 combats = standalone tests (HP/resources reset between each), not a narrative one-shot
#     - Models: Claude Sonnet (GM), Ollama llama3.1:8b (all 5 players)
#     - Module: table/ (orchestrator, gm_agent, player_agent, personas, combat, dice, transcript, smoke_test)
#     - Gating: smoke_test → AI GM dry run → Phase A → Phase B → Phase C (TTS)
#   NEXT SESSION: finish design sections 2–N (agents, turn-taking, combat loop, output),
#   write spec to docs/superpowers/specs/2026-06-14-ai-table-design.md, commit,
#   then invoke writing-plans skill for the implementation plan.
#
# Remaining backlog (optional / research — NOT usage blockers):
#   - Kanka CE upstream PRs: RESOLVED 2026-06-14 — verified, NO PR warranted
#     (minio already fixed upstream via s3→minio endpoint; isApi removal is
#     deploy-specific). Patches stay local-only. See kanka-upstream-patches-verdict memory.
#   - map_tools.py docstring: FIXED (PR #21).
#   - Migrate FMG off the v1.99 pin: NOT worth it now — needs a Node-24 toolchain
#     (system has 20; no nvm/fnm; apt caps at 20) + Vite build + re-reverse the new
#     export (the TS rewrite likely moves pack/burgs off global scope, breaking the
#     clean headless extraction). v1.99 does the job. Defer unless a newer feature is needed.
#
# FMG headless usage: bash scripts/fmg-setup.sh  (serves v1.99 on :8082)
#   python3 -m venv .venv-fmg && .venv-fmg/bin/pip install -r requirements-fmg.txt
#   .venv-fmg/bin/playwright install chromium
#   .venv-fmg/bin/python scripts/fmg-generate.py --seed 1234 --out maps/world.json
#   python3 map_tools.py sync maps/world.json --dry-run
```

## Key Infrastructure Notes

**Docker Port Registry:** Master port map for all `/opt/proj` Docker stacks is in session memory (`reference_docker_port_registry.md`). Always consult before assigning any new host port. Uncle-J langfuse owns 5433 and 6379. kanka-ce owns 5173.

**Foundry networking:** `network_mode: host` — container uses host network stack directly. No Docker NAT. Port 30000 accessible on all host interfaces. Tailscale IP: `100.118.143.57:30000`.

**Why host networking:** Docker's DNAT+conntrack routed return packets via the main routing table, which doesn't contain Tailscale peer routes (those are in table 52 only). This silently dropped WebSocket upgrade responses from remote Tailscale peers while allowing short-lived HTTP GETs to complete. Switching to host networking bypasses Docker NAT entirely.

**MCP bridge host:** auto-detected from `window.location.hostname` — leave the "Websocket Server Host" setting blank. Works for localhost, LAN, and Tailscale without manual config. Port stays `31415`.

**Retrieval stack (added 2026-06-13):**
- **jcodemunch** — repo is indexed as `williamblair333/campaign-forge` (10 files, 62 symbols). Use the stack tools (`search_symbols`, `get_symbol_source`, etc.) for code nav, not grep. Re-index after structural edits if the watch daemon hasn't.
- **memweave** is centralized: one global store `~/.uncle-j-memory`, fed nightly by `sync_memory.sh --all` from the Refinery; campaign-forge transcripts are already in it. The documented command now resolves from this root via gitignored symlinks (`.venv-memweave`, `scripts/memweave` → Refinery): `.venv-memweave/bin/python scripts/memweave/mw_search.py "query" --k 5`. Do NOT install memweave per-project.
- **`/understand` graph** lives in `.understand-anything/` (gitignored). `/understand-dashboard` serves it (Vite; picks a free port, 5173 is kanka-ce's). Good for orienting into the Phase 5 surface (kanka_client → world_builder → rag).

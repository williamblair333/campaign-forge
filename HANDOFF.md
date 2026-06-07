# campaign-forge — Session Handoff

**Date:** 2026-06-07
**Status:** Phase 3 COMPLETE — Kanka CE + world builder + map tools + Foundry VTT all running. WebSocket fixed. foundry-vtt-mcp installed and MCP bridge auto-detect deployed. **Smoke tests still pending — must run browser from dma64 directly (WebGL required).** Docker Port Registry established and all inter-project port conflicts resolved (2026-06-07).
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
| 5e rules data (local) | mnehmos.open5e.mcp | [Mnehmos/mnehmos.open5e.mcp](https://github.com/Mnehmos/mnehmos.open5e.mcp) | ✅ MCP (TypeScript) |
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
- [ ] **TODO: smoke tests** — GM logs into world, MCP bridge now auto-detects serverHost (leave blank), port `31415`. Claude creates a Scene and NPC actor to confirm end-to-end.
- [ ] Optionally wire foundryvtt-rest-api as a REST alternative

### Phase 4 — Local AI / RAG (START HERE)
- [ ] Stand up dnd-llm-game (FastAPI + Ollama + LanceDB)
- [ ] Upload PDF rulebooks as lore corpus
- [ ] Test statblock retrieval from local PDFs
- [ ] Decide: keep dnd-llm-game as a sidecar, or fold RAG into CampaignGenerator directly

### Phase 5 — CampaignGenerator integration
- [ ] Add Kanka CE sync to CampaignGenerator:
  - `kanka_sync.py` — pull world_state from Kanka CE → write world_state.md
  - Post-session: push updated NPC/location states back to Kanka CE
- [ ] Wire prep.py to read from Kanka CE as a grounding source
- [ ] Build the post-session Kanka update step (after distill.py runs)

### Phase 6 — MCP server for CampaignGenerator itself
- [ ] Extend `mcp_server.py` in CampaignGenerator to expose:
  - `run_prep` — trigger prep.py from Claude Desktop
  - `run_session_pipeline` — trigger sd_*.py pipeline
  - `get_world_state` — return current grounding docs
  - `get_campaign_state` — return current campaign state

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

1. **5e data layer** — dnd-mcp hits dnd5eapi.co (cloud). For fully self-hosted, need a local Open5e or 5etools API container. Investigate `5e-srd-api` Docker images.
2. **Map generation gap** — Fantasy Map Generator has no REST API. Options: (a) Puppeteer/Playwright automation, (b) seed-based URL parameters, (c) ComfyUI via foundry-vtt-mcp for battlemaps specifically.
3. **Sync strategy** — CampaignGenerator uses flat markdown files. Kanka CE uses a database. Decide on canonical source of truth and sync direction.
4. **Kanka CE upstream patches** — the 3 fixes (DomainService, filesystems.php, docker-compose.yml) should probably be submitted as PRs to the upstream repo.
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

# Then: Phase 3 smoke tests — MUST run browser on dma64 directly (not remote)
# Foundry uses PixiJS which requires WebGL; a remote/headless browser will not work.
#
# 1. On dma64: open http://localhost:30000/join (or http://100.118.143.57:30000/join)
#    — the player selector form should appear (Gamemaster card visible)
# 2. Log in as Gamemaster (password: FoundryGM2026!)
# 3. Settings → Module Settings → Foundry MCP Bridge:
#    - Websocket Server Host: (leave blank — auto-detects from page URL)
#    - MCP Port: 31415
#    - Allow Write Operations: ✅
# 4. Run MCP backend: node packages/server/dist/index.js (in foundry-vtt-mcp/)
# 5. Ask Claude: "List scenes in my Foundry world" to verify bridge
# After that: Phase 4 — dnd-llm-game RAG setup
```

## Key Infrastructure Notes

**Docker Port Registry:** Master port map for all `/opt/proj` Docker stacks is in session memory (`reference_docker_port_registry.md`). Always consult before assigning any new host port. Uncle-J langfuse owns 5433 and 6379. kanka-ce owns 5173.

**Foundry networking:** `network_mode: host` — container uses host network stack directly. No Docker NAT. Port 30000 accessible on all host interfaces. Tailscale IP: `100.118.143.57:30000`.

**Why host networking:** Docker's DNAT+conntrack routed return packets via the main routing table, which doesn't contain Tailscale peer routes (those are in table 52 only). This silently dropped WebSocket upgrade responses from remote Tailscale peers while allowing short-lived HTTP GETs to complete. Switching to host networking bypasses Docker NAT entirely.

**MCP bridge host:** auto-detected from `window.location.hostname` — leave the "Websocket Server Host" setting blank. Works for localhost, LAN, and Tailscale without manual config. Port stays `31415`.

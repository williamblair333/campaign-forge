# campaign-forge — Session Handoff

**Date:** 2026-06-04
**Status:** Phase 1 COMPLETE — Kanka CE running, REST API verified, Python client working
**Origin sessions:** CampaignGenerator analysis + architecture discussion → Kanka CE deployment

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

## Phase 1 Status: DONE

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

### Phase 2 — World creation conversation loop (START HERE)
- [ ] Build `world_builder.py` — conversational CLI that:
  - Takes DM's campaign description as input
  - Calls Claude to extract structured entities (NPCs, locations, factions, history)
  - Pushes entities to Kanka CE via `kanka_client.py`
  - Outputs summary of what was created
- [ ] Wire up Fantasy Map Generator (Docker) — generate map, export GeoJSON, document import path into Foundry

### Phase 3 — Foundry VTT integration
- [ ] Install Foundry VTT (self-hosted Node server)
- [ ] Install and configure foundry-vtt-mcp (37 tools)
- [ ] Test: Claude creates a Scene in Foundry via MCP
- [ ] Test: Claude creates an NPC actor in Foundry
- [ ] Optionally wire foundryvtt-rest-api as a REST alternative

### Phase 4 — Local AI / RAG
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
| Redis | 6380 | Redis host port (internal: 6379) |
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

1. **Foundry VTT license** — one-time purchase required. If not available, use skyloutyr/VTT instead (free, no MCP bridge yet).
2. **5e data layer** — dnd-mcp hits dnd5eapi.co (cloud). For fully self-hosted, need a local Open5e or 5etools API container. Investigate `5e-srd-api` Docker images.
3. **Map generation gap** — Fantasy Map Generator has no REST API. Options: (a) Puppeteer/Playwright automation, (b) seed-based URL parameters, (c) ComfyUI via foundry-vtt-mcp for battlemaps specifically.
4. **Sync strategy** — CampaignGenerator uses flat markdown files. Kanka CE uses a database. Decide on canonical source of truth and sync direction.
5. **Kanka CE upstream patches** — the 3 fixes above (DomainService, filesystems.php, docker-compose.yml) should probably be submitted as PRs to the upstream repo.

---

## Start Next Session With

```bash
cd /opt/proj/campaign-forge
# Load env
source .env
# Verify Kanka CE is up
curl -s -H "Authorization: Bearer $KANKA_TOKEN" http://localhost:8081/api/1.0/campaigns | python3 -m json.tool
# Then: build world_builder.py — Phase 2
```

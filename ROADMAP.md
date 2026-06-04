# Roadmap

---

## Completed (recent)

### Phase 1 — Foundation ✅ (2026-06-04)
- Kanka Community Edition deployed via Docker Compose
- Three upstream bugs patched for single-domain self-hosted installs
- REST API verified end-to-end: campaigns, locations, characters, organisations, events, notes, tags, entity attributes
- `kanka_client.py` Python client written and tested
- Public GitHub repo created: https://github.com/williamblair333/campaign-forge

---

## In Progress

Nothing currently in progress.

---

## Planned

### Phase 2 — World creation conversation loop
- `world_builder.py` — conversational CLI
  - DM describes campaign setting as free text
  - Claude extracts structured entities (locations, NPCs, factions, history beats)
  - Entities pushed to Kanka CE via `kanka_client.py`
  - Summary printed of everything created
- Fantasy Map Generator setup — Docker, GeoJSON export, Foundry import path documented

### Phase 3 — Foundry VTT integration
- Foundry VTT self-hosted Node server setup
- `foundry-vtt-mcp` installed and configured (37 MCP tools)
- Smoke tests: Claude creates a Scene and NPC actor in Foundry via MCP
- Optional: `foundryvtt-rest-api` as REST alternative

### Phase 4 — Local AI / RAG
- `dnd-llm-game` (FastAPI + Ollama + LanceDB) stood up in Docker
- PDF rulebooks ingested as lore corpus
- Statblock retrieval from local PDFs tested and benchmarked
- Decision: keep as sidecar or fold RAG into CampaignGenerator directly

### Phase 5 — CampaignGenerator integration
- `kanka_sync.py` — pull world_state from Kanka CE → write `world_state.md`
- Post-session: push updated NPC/location states back to Kanka CE
- `prep.py` reads from Kanka CE as a grounding source
- Post-session Kanka update step wired after `distill.py` runs

### Phase 6 — MCP server for CampaignGenerator
- Extend `mcp_server.py` in CampaignGenerator to expose:
  - `run_prep` — trigger prep pipeline from Claude Desktop
  - `run_session_pipeline` — trigger full post-session pipeline
  - `get_world_state` — return current grounding docs
  - `get_campaign_state` — return current campaign state

---

## Open Questions

- Does Foundry VTT require a paid license, or is skyloutyr/VTT a viable free alternative for this stack?
- Can Fantasy Map Generator be headlessly driven (Puppeteer/Playwright) for agent-triggered generation?
- What's the canonical source of truth for campaign state — Kanka CE or CampaignGenerator flat markdown files?
- Is there a Docker-composable Open5e or 5etools API for fully offline 5e data?

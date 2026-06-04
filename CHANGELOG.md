# Changelog

All notable changes to campaign-forge are documented here.

Format follows [Keep a Changelog](https://keepachangelog.com/en/1.1.0/).

---

## [Unreleased]

### Planned
- `world_builder.py` — conversational CLI: DM describes world → Claude extracts entities → Kanka CE
- Fantasy Map Generator Docker setup + GeoJSON import path to Foundry
- Foundry VTT + foundry-vtt-mcp integration (Phase 3)
- dnd-llm-game local RAG setup (Phase 4)
- CampaignGenerator ↔ Kanka CE sync layer (Phase 5)

---

## [0.1.0] — 2026-06-04

### Added
- `kanka_client.py` — Python REST client for Kanka Community Edition
  - Full CRUD for: campaigns, locations, characters, organisations, events, notes, tags
  - `set_attributes()` for entity-level key/value metadata
  - Environment-variable configuration (`KANKA_BASE_URL`, `KANKA_TOKEN`)
  - Demo function that exercises all entity types end-to-end
- `patches/kanka-ce.patch` — three bug fixes for single-domain self-hosted Kanka CE
  - `DomainService::isApi()` — removed path-based API detection that broke route registration on single-domain installs
  - `config/filesystems.php` — added missing `minio` disk definition
  - `docker-compose.yml` — decoupled `REDIS_HOST_PORT` / `MINIO_HOST_PORT` from container-internal ports
- `SETUP.md` — complete step-by-step setup guide from a fresh system
- `README.md` — project overview and quick start
- `.env.example` — template for campaign-forge environment configuration
- `.gitignore` — excludes secrets, generated files, and `kanka-ce/` (cloned by user during setup)
- `LICENSE` — GNU General Public License v3.0

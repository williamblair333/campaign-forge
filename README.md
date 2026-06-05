# campaign-forge

**Self-hosted, AI-orchestrated TTRPG campaign management.**

campaign-forge is an infrastructure and integration layer that lets a Dungeon Master use Claude to build and maintain a living campaign world — creating NPCs, locations, factions, and timelines in a self-hosted world-state store, generating maps, running sessions through a VTT, and automatically processing session transcripts back into structured lore.

> **Status:** Phase 3 complete — Kanka CE, world builder, map tools, and Foundry VTT all running. Building toward full session pipeline.

---

## What You Get

| Capability | Tool | Status |
|---|---|---|
| World-state store | Kanka Community Edition (self-hosted) | ✅ Running |
| AI entity creation via REST API | `kanka_client.py` | ✅ Working |
| Conversational world builder | `world_builder.py` | ✅ Working |
| Map import (Azgaar FMG) | `map_tools.py` + `scripts/fmg-setup.sh` | ✅ Working |
| Virtual tabletop | Foundry VTT 14.363 (self-hosted) | ✅ Running |
| VTT ↔ Claude MCP bridge | `foundry-vtt-mcp` (37 tools) | 🔧 Installed, smoke tests pending |
| Local 5e rules / statblock RAG | dnd-llm-game (Ollama + LanceDB) | 🔜 Phase 4 |
| Campaign prep pipeline | CampaignGenerator integration | 🔜 Phase 5 |
| Post-session narrative generation | CampaignGenerator | 🔜 Phase 5 |

---

## How It Works

```
DM describes world to Claude
  → Claude extracts entities (NPCs, locations, factions, history)
  → campaign-forge pushes them into Kanka CE via REST API
  → Kanka CE stores structured world state

Pre-session:
  CampaignGenerator reads world state from Kanka CE
  → Generates encounter docs, NPC notes, scene descriptions
  → Foundry VTT MCP bridge creates scenes, tokens, fog of war

During session:
  Players connect to self-hosted Foundry VTT

Post-session:
  Session transcript → summaries → narrative docs
  Updated NPC/location/timeline data pushed back to Kanka CE
```

---

## Stack

| Layer | Component |
|---|---|
| World state / lore | [Kanka Community Edition](https://github.com/kinnewig/kanka-community-edition) |
| VTT | [Foundry VTT](https://foundryvtt.com) |
| VTT ↔ Claude bridge | [foundry-vtt-mcp](https://github.com/adambdooley/foundry-vtt-mcp) |
| Local AI / RAG | [dnd-llm-game](https://github.com/tegridydev/dnd-llm-game) |
| 5e rules data | [mnehmos.open5e.mcp](https://github.com/Mnehmos/mnehmos.open5e.mcp) |
| Map generation | [Fantasy Map Generator](https://github.com/Azgaar/Fantasy-Map-Generator) |
| Campaign narrative pipeline | [CampaignGenerator](https://github.com/kostadis/CampaignGenerator) |

---

## Prerequisites

- Linux/macOS host (Windows WSL2 should work)
- [Docker](https://docs.docker.com/get-docker/) and Docker Compose v2
- Python 3.10+
- Git
- ~4 GB free RAM, ~10 GB free disk

---

## Quick Start

```bash
# 1. Clone campaign-forge
git clone https://github.com/wblair8689/campaign-forge.git
cd campaign-forge

# 2. Clone and patch Kanka CE
git clone https://github.com/kinnewig/kanka-community-edition kanka-ce
git -C kanka-ce apply ../patches/kanka-ce.patch

# 3. Install Kanka CE PHP dependencies (uses Docker — no PHP needed locally)
cd kanka-ce
docker run --rm -u "$(id -u):$(id -g)" \
  -v "$(pwd):/var/www/html" -w /var/www/html \
  laravelsail/php84-composer:latest \
  composer install --ignore-platform-reqs

# 4. Configure environment
cp .env.example .env
bash gen-passwords.sh
# Edit .env: set KANKA_CE_DATA, REDIS_HOST_PORT=6380 if 6379 is occupied, etc.

# 5. Start the stack
vendor/bin/sail up -d
vendor/bin/sail artisan kanka:install
vendor/bin/sail artisan setup:meilisearch

# 6. Create MinIO buckets
docker exec kanka_ce_minio mc alias set kanka http://localhost:9000 sail <MINIO_PASSWORD>
docker exec kanka_ce_minio mc mb --ignore-existing kanka/kanka kanka/thumbnails
docker exec kanka_ce_minio mc anonymous set public kanka/kanka kanka/thumbnails

# 7. Create your admin user
vendor/bin/sail artisan user:add --admin "Your Name" "you@example.com"

# 8. Generate an API token
cd ..
cp .env.example .env
# Paste your token (from Kanka CE Settings → API) into .env

# 9. Verify everything
pip install requests
python kanka_client.py
```

Kanka CE is now running at **http://localhost:8081**.

For the full step-by-step walkthrough, see [SETUP.md](SETUP.md).

---

## Project Layout

```
campaign-forge/
├── kanka_client.py           # Python REST client for Kanka CE
├── world_builder.py          # Conversational world builder (Claude → Kanka CE)
├── map_tools.py              # Azgaar FMG .map parser and Kanka CE sync
├── docker-compose.foundry.yml # Foundry VTT (felddy image, ports 30000 + 31415)
├── foundry-vtt-mcp/          # MCP bridge: 37 tools connecting Claude to Foundry
├── foundry/data/             # Foundry persistent data (worlds, config, cache)
├── scripts/
│   ├── foundry-setup.sh      # Foundry lifecycle (start/stop/backup)
│   └── fmg-setup.sh          # Fantasy Map Generator local server
├── patches/
│   └── kanka-ce.patch        # Bug fixes applied to Kanka CE for single-domain installs
├── .env.example              # Template: KANKA_*, FOUNDRY_*, ANTHROPIC_API_KEY
├── SETUP.md                  # Step-by-step setup guide
└── CHANGELOG.md
```

`kanka-ce/` is not included — it is cloned and patched during setup.

---

## Why These Patches?

Three bugs in Kanka CE affect single-domain self-hosted installs:

1. **`DomainService::isApi()`** — path-based API detection caused routes to be registered under `api.kanka.io` without the `/api` prefix, so all REST calls returned 404. Fixed: host-only detection.
2. **`config/filesystems.php`** — the `minio` disk referenced in `.env.example` was never defined. Fixed: added the disk.
3. **`docker-compose.yml`** — `REDIS_PORT` and `MINIO_PORT` were used for both the host-side port binding and the in-container app connection. Fixed: split into `*_HOST_PORT` variants.

These are submitted as patches rather than included directly due to Kanka CE's Commons Clause license.

---

## License

campaign-forge code (everything except the `kanka-ce/` directory) is licensed under the [GNU General Public License v3.0](LICENSE).

Kanka Community Edition is licensed under the [Commons Clause](https://commonsclause.com/) + its upstream license — see `kanka-ce/LICENSE`. Do not use Kanka CE commercially without reviewing that license.

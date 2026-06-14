# Changelog

All notable changes to campaign-forge are documented here.

Format follows [Keep a Changelog](https://keepachangelog.com/en/1.1.0/).

---

## 2026-06-13 — Retrieval-stack integration: jcodemunch index, memweave access, /understand graph

### Added
- **jcodemunch index** for this repo (`williamblair333/campaign-forge`, 10 files / 62 symbols). It was never indexed; code navigation now routes through the stack instead of brute-force reads.
- **memweave reachable from the project root** via two gitignored symlinks into `/opt/proj/Uncle-J-s-Refinery` (`.venv-memweave`, `scripts/memweave`). memweave is a *centralized* stack tool — one global store at `~/.uncle-j-memory`, fed nightly by `sync_memory.sh --all` — so campaign-forge transcripts were already searchable; the symlinks just make the documented `mw_search.py` command resolve here too. No per-project install (that would fragment the corpus).
- **`/understand` knowledge graph** under `.understand-anything/` (gitignored): 55 nodes / 91 edges over the 20-file project scope (vendored `kanka-ce/` + `foundry-vtt-mcp/` excluded), 5 architectural layers, 9-step tour. Built via the understand-anything plugin (pinned pnpm 9.15.4 through corepack since Node 20 here can't run pnpm 11). View with `/understand-dashboard`.

### Changed
- **`.gitignore`** (PR #9): ignore the memweave symlinks (`.venv-memweave`, `scripts/memweave` — no trailing slash so the pattern matches a symlink) and the generated `.understand-anything/` graph output.

---

## 2026-06-13 — Phase 4 local RAG; Foundry smoke tests passed; delete-actors tool

### Added
- **`rag/`** — in-repo local RAG harness: PDF corpus → Ollama embeddings (`nomic-embed-text`) → LanceDB → retrieval + grounded answers (`llama3.1:8b`), fully self-hosted on GPU Ollama. `rag/ingest.py`, `rag/query.py`, `rag/config.py`; reusable `from rag import search, answer`; pinned `rag/requirements.txt`. Corpus: SRD 5.2.1 (CC-BY-4.0, `rag/corpus/ATTRIBUTION.md`). 1,596 chunks ingested.
- **`delete-actors`** MCP tool in the foundry-vtt-mcp fork — the bridge had no actor-delete. GM-gated + `deleteData` HIGH_RISK perm + PERMANENT (no undo). Preserved as **`patches/delete-actors.patch`** (fork is gitignored). Touched data-access.ts, queries.ts, tools/token-manipulation.ts, backend.ts.
- **`.gitignore`** entries: `.venv-rag/`, `rag/lancedb/`, `rag/corpus/*.pdf`, `foundry-world-backup-*.tgz`.

### Fixed
- **`/opt/lib/docker-port-registry/dcup`** (shared tool, backup `dcup.bak.2026-06-13`) — (1) `dcup up -f file` execed `docker compose up -f file` but `-f`/`-p` are global flags that must precede the subcommand → now re-emitted up front; (2) `grep -c … || echo 0` produced `"0\n0"` breaking the stale-claim reconcile numeric test.

### Changed
- **Phase 3 Foundry smoke tests PASSED** — end-to-end Claude→bridge→Foundry verified (world info, scenes, create + read-back NPC actor); test actor later deleted via the new `delete-actors` tool.
- Ollama container (`open-webui-ollama-1`) set to `restart=unless-stopped` so RAG survives reboots.
- Kanka CE stack brought back up via `dcup`.

---

## 2026-06-07 — Docker Port Registry established; inter-project port conflicts resolved

### Added
- Docker Port Registry (session memory) — master port map for all `/opt/proj` Docker projects; standing policy: always consult before assigning any new host port

### Fixed
- **`kanka-ce/docker-compose.yml`** — redis host port default 6379→6381 (Uncle-J langfuse owns 6379; `.env` still overrides to 6380 — no runtime change on this machine)
- **`foc-exec/docker-compose.yml`** — Vite host port 5173→5274, postgres default 5433→5435 (kanka-ce owns 5173; Uncle-J langfuse owns 5433)
- **`proj-fog-of-chess/docker-compose.yml`** — Vite host port 5173→5275, postgres default 5433→5436

---

## 2026-06-04 — Phase 1 complete: Kanka CE deployed, REST API verified, docs + repo published

### Added
- `kanka_client.py` — Python REST client; CRUD for campaigns, locations, characters, organisations, events, notes, tags, and entity attributes; demo function exercises all entity types
- `patches/kanka-ce.patch` — three bug fixes for single-domain self-hosted Kanka CE (see below)
- `SETUP.md` — complete hand-holding setup guide from a fresh system (13 sections, covers port conflicts, troubleshooting)
- `README.md` — general-audience overview with quick start, stack table, patch rationale, and license notes
- `CHANGELOG.md`, `HANDOFF.md`, `LICENSE` (GPL v3), `.gitignore`, `.env.example`
- Public GitHub repo: https://github.com/williamblair333/campaign-forge

### Fixed (in Kanka CE via patch)
- `app/Services/DomainService.php` — removed `$request->is('api/*')` from `isApi()`; on single-domain installs this caused all `/api/*` routes to be registered without the `/api` prefix, returning 404 for every REST call
- `config/filesystems.php` — added missing `minio` disk definition; `.env.example` referenced it but it was never defined, causing 500 on every entity creation
- `docker-compose.yml` — split `REDIS_HOST_PORT` / `MINIO_HOST_PORT` from container-internal port vars so hosts with occupied ports 6379 / 9000 can remap without breaking the app

### State
- Kanka CE running at `http://localhost:8081`, all 8 containers healthy
- Campaign "The Shattered Realm" (id=1) created; API token in `/opt/proj/campaign-forge/.env`
- All CRUD entity types confirmed working end-to-end

---

## 2026-06-05 — Phase 3 complete: Foundry VTT running, foundry-vtt-mcp installed

### Added
- `docker-compose.foundry.yml` — Foundry VTT 14.363 via felddy Docker image; exposes port 30000 (web) and 31415 (MCP WebSocket)
- `scripts/foundry-setup.sh` — lifecycle wrapper: start / stop / restart / status / logs / backup
- `foundry-vtt-mcp/` — MCP bridge repo cloned and npm-installed (37 MCP tools); connects Claude to Foundry
- `foundry/data/` — Foundry data directory with cached binary (`container_cache/foundryvtt-14.363.zip`)
- `FOUNDRY_LICENSE_KEY`, `FOUNDRY_ADMIN_KEY`, `FOUNDRY_RELEASE_URL` added to `.env` (timed URL consumed; binary cached)

### State
- Foundry VTT running at http://localhost:30000 (container healthy)
- GM admin login: see `.env` → `FOUNDRY_ADMIN_KEY`
- Remaining: wire foundry-vtt-mcp bridge and run smoke tests

---

## 2026-06-04 — Phase 2 complete: world builder and map tools

### Added
- `world_builder.py` — conversational CLI: DM describes campaign → Claude extracts entities (locations, characters, organisations, events, notes) → pushed to Kanka CE via tool-use API; supports `--dry-run`, `--yes`, `--description`, `--campaign-id`
- `map_tools.py` — parse Azgaar Fantasy Map Generator `.map` (JSON) exports; `parse` command shows summary, `sync` command pushes burgs→locations and states→organisations to Kanka CE with duplicate-skip
- `scripts/fmg-setup.sh` — clones Azgaar/Fantasy-Map-Generator and serves it on http://localhost:8082 via nginx (localhost-only bind)

---

## 2026-06-05 — Fix: Foundry WebSocket unreachable from remote Tailscale peers

### Fixed
- **Foundry join page blank for remote browser** — `docker-compose.foundry.yml` switched from `ports: ["100.118.143.57:30000:30000/tcp"]` to `network_mode: host`.

  **Root cause:** Docker's NAT (DNAT + conntrack) for a specific-IP port binding routes return packets through the kernel's main routing table. Tailscale peer routes (`100.120.43.24`, etc.) only exist in routing table 52, not main. The WebSocket TCP upgrade establishes from the remote browser but the server's response packets were mis-routed, silently dropping the connection before the socket.io `connection` event ever fired. HTTP GET requests completed because they're short-lived and conntrack managed to resolve them; the sustained WebSocket handshake exposed the asymmetric routing failure.

  With `network_mode: host`, Foundry's Node.js process binds directly to port 30000 on the host network stack — no Docker iptables NAT involved. Tailscale traffic hits the process directly.

- **MCP bridge host setting** — with host networking, the Foundry module's "Websocket Server Host" setting must be `127.0.0.1` (not `host.docker.internal`), since the container's localhost is now the host's localhost.

### Changed
- `docker-compose.foundry.yml` — replaced `ports` + `extra_hosts` with `network_mode: host`

### Diagnosed (no code change needed)
- Session cookie `SameSite=Strict` — confirmed NOT the issue; cookie was delivered correctly
- `getJoinData` socket event — confirmed working; returns world + users correctly
- All four join Handlebars templates — confirmed loading via socket
- GM credentials — confirmed working via direct POST login
- `JoinGameForm.render()` — confirmed rendering form in headless Chromium from dma64

## 2026-06-05 — Debug: Foundry join page blank (WebGL unavailable in browser)

### Investigated
- **Root cause found:** `PIXI.Assets.init()` crashes with `TypeError: Cannot read properties of undefined (reading 'getExtension')` in PixiJS `detectCompressedTextures`. PixiJS probes WebGL GPU extensions before anything else; if WebGL is unavailable the init throws, `Setup.create()` never runs, and the join form never renders — leaving only the background splash image.
- **Server confirmed fully healthy:** socket.io connects, session cookie valid, `getJoinData` returns world + users, all four Handlebars templates load via socket. Problem is 100% client-side.
- **Browser must have WebGL enabled** — access Foundry from the local machine (dma64) where the GPU/display is available, not from a remote or headless browser.
- Temporarily disabled `foundry-mcp-bridge` module (renamed folder) to rule out module interference — not the cause; restored afterward.

### No code changes this session.

---

## 2026-06-06 — Fix: Foundry MCP bridge serverHost hardcoded to localhost

### Fixed
- **`foundry-vtt-mcp/packages/foundry-module/src/constants.ts`** — `MCP_HOST` changed from `'localhost'` to `''` (empty = auto-detect). When connecting from a remote browser (e.g. Tailscale), `localhost:31415` resolved to the user's local machine rather than the server, silently failing the WebSocket connection.
- **`foundry-vtt-mcp/packages/foundry-module/src/settings.ts`** — `getBridgeConfig()` now resolves an empty `serverHost` to `window.location.hostname` at connect time. Works transparently for localhost, LAN, and Tailscale — no manual setting needed. `validateSettings()` updated to accept blank host. Setting hint updated to document the auto-detect behaviour.
- Built (`tsc`) and synced to `foundry/data/Data/modules/foundry-mcp-bridge/dist/`.

## [Unreleased]

### Planned
- Foundry VTT MCP smoke tests: Claude creates Scene and NPC actor via foundry-vtt-mcp
- `foundryvtt-rest-api` as optional REST alternative to MCP bridge
- `dnd-llm-game` local RAG setup (Phase 4)
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

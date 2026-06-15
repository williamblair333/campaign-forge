# Changelog

All notable changes to campaign-forge are documented here.

Format follows [Keep a Changelog](https://keepachangelog.com/en/1.1.0/).

---

## 2026-06-14 — AI table Phase A live run complete; two bug fixes merged (PRs #29, #30)

### Added
- `table/gm_agent.py` — three GM backends: `GMAgent` (Anthropic SDK), `CLIGMAgent` (claude CLI subprocess, Max subscription), `OllamaGMAgent` (local Ollama HTTP); `make_gm_agent(backend)` factory; `auto` picks SDK if `ANTHROPIC_API_KEY` set, else CLI
- `--gm-backend {sdk,cli,ollama,auto}` and `--stream` flags on `table/orchestrator.py` main
- `CLIGMAgent` uses `--safe-mode` flag to skip MCP server startup (avoids 120 s+ delay); 180 s timeout
- `RollRequest.target: str | None` — orchestrator auto-applies `-roll` to target HP when `"damage"` in `purpose`; GM prompt updated to populate `target` on damage rolls
- `CombatState.remove_condition()` — conditions can now be removed (previously add-only)
- `conditions_remove` key in `scene_update` schema and `_apply_scene_update` handler
- GM system prompt extended with instructions for `target` and `conditions_remove`

### Fixed
- Comprehensive dice parser in `table/dice.py`: accepts `dX` (no leading 1), `NdXkh/klK` (keep), `NdXdh/dlK` (drop), case-insensitive, space-stripped; graceful fallback to 1d20 on unknown formula instead of crash
- Monster damage rolls no longer silently skip HP delta — auto-apply via `RollRequest.target`
- Stale conditions (e.g. Concentration) now removable via `conditions_remove` in GM JSON output

### Live run
- Phase A first run: TPK in Round 5, 65 turns, ~65 min. Transcript saved in `transcript.md` (gitignored). GM narration quality confirmed excellent; all D&D 5e rules correctly adjudicated (concentration, death saves, unconscious = auto-crit with advantage, TPK detection). Phase A gate: human eyeball the transcript for persona distinctiveness.

### Tests
- 88 tests passing (up from 61 at PR #28 merge) — 27 new tests across dice, gm_agent, combat, and orchestrator modules

---

## 2026-06-14 — AI table experiment designed (brainstorming session, no code)

### Decided
- **AI table approach:** incremental milestones — Phase A (1 GM + 2 players, 1 combat, text-only) → Phase B (5 players, 3 combats) → Phase C (Kokoro TTS)
- **World:** The Shattered Realm (Kanka CE canon); AI GM syncs `world_state.md` before play, pushes new entities back after
- **3 combats:** standalone combat tests (HP/resources reset between each), not a narrative one-shot
- **Voice:** text transcript first; Kokoro TTS (Apache-2.0, 54 voicepacks) as Phase C follow-on
- **Module layout:** `table/orchestrator.py`, `gm_agent.py`, `player_agent.py`, `personas.py`, `combat.py`, `dice.py`, `transcript.py`, `smoke_test.py`, `tts/kokoro.py`
- **Models:** Claude Sonnet for GM; Ollama `llama3.1:8b` for all 5 players (zero API cost)
- **Gating:** smoke-test (all services alive) → AI GM dry run (single scene, no players) → Phase A → Phase B → Phase C
- Spec write-up in progress; writing-plans to follow next session

---

## 2026-06-14 — Phase 7: self-hosted 5e data layer (dnd5e_mcp.py) shipped (PR #27)

### Added
- `dnd5e_mcp.py` — FastMCP server with 4 tools: `lookup_monster`, `lookup_spell`, `lookup_item`, `search_5e`
- `test_dnd5e_mcp.py` — 20 pytest cases (all fixture-based; no real data files required in CI)
- `scripts/dnd5e-fetch.sh` — sparse-clones 5etools compendium from mirror-2 into `data/dnd5e/` (gitignored); auto-runs on first startup via `ensure_data()`
- `requirements-dnd5e.txt` — isolated venv; `mcp[cli]>=1.2,<2`, `duckdb>=0.10`, `requests>=2.31`

### Fixed
- `scripts/dnd5e-fetch.sh`: mirror-3 (5etools-mirror-3) was dead (404); switched to `revilowaldow/5etools-mirror-2.github.io`; added `--no-cone` for git sparse-checkout with individual files; added mirror-fragility comment with recovery instructions
- `dnd5e_mcp.py`: excluded `foundry.json` / `index.json` / `sources.json` from `load_data()` — `foundry.json` uses the `spell`/`monster` envelope but contains Foundry VTT overlay data that was poisoning exact-name lookups

### Changed
- `.mcp.json.example`: added `dnd5e` server entry + `_setup_dnd5e` comment; retired `mnehmos.open5e.mcp`
- `README.md`: replaced `mnehmos.open5e.mcp` row with `dnd5e_mcp.py`
- `HANDOFF.md`: open question #1 marked RESOLVED; stack table row updated

### Pre-mortem findings addressed
- ENVIRONMENTAL: `duckdb` ImportError → actionable setup message + `sys.exit(1)`; `ensure_data()` fetch failure → actionable stderr with exact manual command
- OBSERVABILITY: startup banner `[dnd5e_mcp] loaded N monsters, M spells, K items` to stderr
- SCALE (advisory): foundry.json exclusion also reduces startup memory slightly

---

## 2026-06-14 — map_tools docstring fix; Kanka upstream patches verified (no PR)

### Fixed
- **`map_tools.py`** — corrected the module docstring: it parses the `{pack:{burgs,states}}` JSON from `scripts/fmg-generate.py --format json`, not a raw FMG `.map` (which is pipe-delimited and unparseable here). The old "Save As .map → sync" workflow never worked. Docstring-only. (PR #21)

### Investigated (no change — verified correct to leave local-only)
- **Kanka CE upstream patches** — rigorously verified against `kinnewig/kanka-community-edition` `nightly` (default branch). **No upstream PRs warranted:** (1) the `minio`-disk fix is already solved upstream a different way (`FILESYSTEM_DRIVER=s3` with the s3 disk's `AWS_ENDPOINT` pointed at the bundled MinIO); (2) the `isApi()` `is('api/*')` check is plausibly an intentional single-domain accommodation — our removal is deploy-specific, not a provable universal bug; (3) the docker-compose port vars are a local port-conflict convenience. All three stay as local patches in the gitignored `kanka-ce/` tree.

---

## 2026-06-14 — FMG headless map-gen (pinned v1.99) + RAG hybrid rerank

### Added
- **`scripts/fmg-generate.py`** — headless (Playwright) FMG map generation, closing the "FMG has no REST API" gap. Loads a locally-served FMG with a `--seed`, waits for the cell graph, then serializes. `--format json` (default) emits `{info, pack:{burgs, states}}` — exactly what `map_tools.py` parses; `--format map` emits FMG's native `.map`. Isolated `.venv-fmg` (`requirements-fmg.txt`, pinned `playwright`). Verified end-to-end: seed 1234 → 137 KB JSON → `map_tools sync --dry-run` = 25 states → organisations, 286 burgs → locations (campaign 1). (PR #19)
- **`rag/query.py` hybrid rerank** — `search()` pulls `RERANK_CANDIDATES` (20) by vector then re-scores `ALPHA*vec_sim + (1-ALPHA)*lexical_overlap`, keeping the top-k; lifts the named statblock above generic rules. Vector-dominant (`alpha=0.7`); `RAG_RERANK_CANDIDATES=0` disables. `test_rag_query.py` (6 cases). (PR #18)

### Fixed / Changed
- **`scripts/fmg-setup.sh`** — pinned to FMG **v1.99**. Upstream FMG (v1.100+) is a Vite/TS rewrite (Node ≥24) with `index.html` under `src/`; the static nginx serve returned **403**. Now re-checks-out an existing newer clone to the tag and guards root `index.html` before serving.
- **Corrected a long-standing doc error:** a real FMG `.map` is a custom pipe-delimited format, NOT JSON, so `map_tools.py` (which `json.load`s `{pack:{burgs,states}}`) cannot parse it — the old manual "Save As .map → sync" path never worked. `fmg-generate.py --format json` is the working bridge. (`map_tools.py`'s own docstring inaccuracy left as a noted follow-up.)
- **`.gitignore`** — `.venv-fmg/`, `maps/`, `Fantasy-Map-Generator/`.

### Decided (not built)
- **`foundryvtt-rest-api`** — skipped (user decision): the MCP bridge already provides Foundry integration; a redundant REST module + relay in the live campaign world is new surface for no new capability.

---

## 2026-06-14 — RAG: layout-aware chunking (statblock bleed fixed)

### Changed
- **`rag/ingest.py`** — replaced flat `get_text("text")` + fixed char-windows with **column-aware extraction** (`order_blocks()`: read the left column top-to-bottom then the right; full-width titles act as flow breaks between vertical bands) and **boundary-aware packing** (`pack_chunks()`: fill to `RAG_CHUNK_CHARS` but break only on paragraph boundaries so a statblock stays in one chunk; oversized paragraphs fall back to `_chunks()` windows). `extract_page_text()` wires `get_text("blocks")` → `order_blocks`. (PR #16)
- Live index rebuilt (1761 chunks). Before/after on the same query: "Adult Red Dragon breath weapon" previously returned a chunk that bled into the **Young Red Dragon** statblock (AC 18 / HP 178 — wrong creature); after, the top hit is the **Adult Red Dragon**'s own contiguous block (AC 19 / HP 256). An algorithm change requires `ingest --rebuild`, not an append (documented in `rag/README.md`).

### Added
- **`test_rag_ingest.py`** — 9 cases (two-column ordering, full-width header bands, single column, paragraph packing, statblock-whole, oversized-paragraph fallback). Pure functions, no Ollama/PDF needed (run under `.venv-rag`).

---

## 2026-06-14 — Phase 6: Kanka sync exposed as MCP tools

### Added
- **`kanka_mcp.py`** — a FastMCP server exposing the Phase 5 sync engine to a Claude client: `kanka_pull` (Kanka → world_state.md, read-only), `kanka_push_preview` (DRY RUN create/update/skip plan — safe default), `kanka_push_apply` (commit; never deletes, skip-if-unchanged, continue-on-error; preview-first, explicit). The FastMCP import is guarded (lazy in `build_server`) so the core functions import and unit-test without the `mcp` package; tool wrappers return clean errors (missing `KANKA_TOKEN` / input file) and surface raw `create/update/skip/failed` counts. (PR #14)
- **`requirements-mcp.txt`** — pins `mcp[cli]>=1.2,<2` (FastMCP import path has moved across majors); install into a gitignored `.venv-mcp/`.
- **`.mcp.json.example`** — registration template; `KANKA_TOKEN` must be passed in the server `env` block (MCP servers don't inherit the shell `.env`).
- **`test_kanka_mcp.py`** — 5 cases. Server build verified under a real `mcp` install (registers all 3 tools); live read-only pull + preview = `skip=4` (round-trip lossless through the MCP layer).

### Confirmed / decided (no code change)
- **3 of the 4 named Phase 6 tools already existed** in CampaignGenerator's `mcp_server.py`: `get_world_state`, `get_campaign_state`, and `run_prep` (as `session_prep`) — alongside ~20 other tools (query_lore, rpg_search, mempalace search, npc_table, dossier proposer).
- **`run_session_pipeline` intentionally NOT built.** CampaignGenerator's `sd_*` post-session pipeline is deliberately human-gated (`docs/cli/session_doc_pipeline.md`: every stage boundary is a `HUMAN REVIEW` checkpoint; the monolith was split into stages to enforce them; no pipeline-runner ships by design). Auto-chaining would violate that invariant, burn LLM tokens on unreviewed plans, and require guessing per-session args in a third-party repo. The "Claude drives sync" intent is served on the campaign-forge side by `kanka_mcp.py`.

---

## 2026-06-14 — Phase 5 COMPLETE: world_state.md → Kanka CE push-back; prep.py grounding confirmed

### Added
- **`kanka_push.py`** — the inverse of `kanka_sync.py` and the second half of Phase 5. Deterministically parses a section-profile `world_state.md` back into entities (no LLM) and reconciles them with the live campaign: match by name (exact, case-insensitive) against Kanka, then **create / update / skip**. **Dry-run by default; `--apply` commits; never deletes.** Skip-if-unchanged normalizes Kanka's stored HTML through the same `html_to_text` as the pull, so a plain-text round-trip never clobbers richer entries. Continue-on-error per entity (a 422 doesn't abort the batch; a re-run retries). Entity boundaries gate on the full `**Name**` header shape, so inline/leading markdown bold in a body never splits an entity. Kanka's own entity ids are the dedup key — no local manifest to drift.
- **`kanka_client.py`** — additive: generic `create(campaign_id, entity_type, **fields)` and `update(campaign_id, entity_type, record_id, **fields)` (PATCH) for uniform entity-type dispatch. Existing per-type `create_*` / `list_*` methods unchanged.
- **`test_kanka_push.py`** — 19 pytest cases: parser flag/title/date/body coverage, round-trip against `kanka_sync.entity_block`, plan/apply create-update-skip, case-insensitive match, field whitelist, continue-on-error, bold-in-body boundary.

### Confirmed (no code change)
- **`prep.py` already reads `world_state.md`** — the remaining Phase 5 item needed no CampaignGenerator edit. `config/config.yaml` lists `world_state → docs/world_state.md` in `documents`, and `assemble_user_prompt → assemble_docs` loads every configured doc (`load_file` hard-exits if a configured doc is missing → world_state is a *required* grounding source). Integration is operational: in the campaign workspace run `kanka_sync.py --output docs/world_state.md` to feed the slot, then `kanka_push.py --input docs/world_state.md --apply` to push session changes back. Loop closed.

### Verified
- `pytest`: 19 passed. Live dry-run vs Kanka campaign 1: pull→push = `skip=4 / create=0 / update=0` (round-trip lossless); an edited doc plans exactly **1 update + 1 create**, correctly classified under `## NPCs`.

---

## 2026-06-13 — Phase 5 (start): Kanka CE → world_state.md grounding bridge

### Added
- **`kanka_sync.py`** — pulls every entity for a Kanka CE campaign and renders a CampaignGenerator-shaped `world_state.md` grounding doc (`## NPCs / ## Factions / ## Locations / ## World Events / ## Threads`), matching the profile layout `synthesise_world_state.py` emits. Kanka `characters → NPCs`, `organisations → Factions`, `locations → Locations`, `events → World Events`, `notes → Threads & Mysteries`. Stdlib HTML→text strip of Kanka's HTML `entry` fields (no bs4/bleach dep). `--output` is required and never defaults to a canonical doc (mirrors `synthesise_world_state.py` overwrite safety); `--stdout` for preview; `is_private` entities skipped unless `--include-private`. Verified end-to-end against live Kanka CE campaign 1 ("The Shattered Realm").
- **`kanka_client.py`** — additive: `_get_all()` follows Kanka's `links.next` pagination (list endpoints page at 30; a >30-entity campaign was silently truncated at page 1), `list_events()`, `list_notes()`, and `list_all(campaign_id, entity_type)`. Existing single-page `list_*` methods unchanged (backward compatible).

### Changed
- **`.gitignore`** — ignore `reviews/` (exploratory writeups / design scratch, not shipped).

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

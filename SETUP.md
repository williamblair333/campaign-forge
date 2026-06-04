# campaign-forge — Complete Setup Guide

This guide walks you through setting up the full campaign-forge stack from scratch on a fresh Linux or macOS machine. Every command is shown exactly as you need to run it.

**Time required:** 20–40 minutes depending on internet speed.

---

## Table of Contents

1. [What You're Installing](#1-what-youre-installing)
2. [Prerequisites](#2-prerequisites)
3. [Get the Code](#3-get-the-code)
4. [Set Up Kanka CE](#4-set-up-kanka-ce)
5. [Configure Environment](#5-configure-environment)
6. [Start the Stack](#6-start-the-stack)
7. [First-Time Installation](#7-first-time-installation)
8. [Create Your Admin Account](#8-create-your-admin-account)
9. [Get Your API Token](#9-get-your-api-token)
10. [Wire Up the Python Client](#10-wire-up-the-python-client)
11. [Verify Everything Works](#11-verify-everything-works)
12. [Stopping and Starting](#12-stopping-and-starting)
13. [Troubleshooting](#13-troubleshooting)

---

## 1. What You're Installing

**Kanka Community Edition** is a self-hosted world-building and campaign management web app. It stores your NPCs, locations, factions, timelines, and notes in a structured database with a full REST API.

**campaign-forge** is the Python tooling that sits on top of it — letting Claude (or you, directly) create and update world entities programmatically.

The Docker stack that will run on your machine:

| Container | What it does | Port |
|---|---|---|
| `kanka_ce_laravel` | The web app (PHP) | 8081 |
| `kanka_ce_mariadb` | Database | 3306 |
| `kanka_ce_redis` | Cache and queues | 6379 |
| `kanka_ce_minio` | File/image storage (S3-compatible) | 9000 |
| `kanka_ce_meilisearch` | Full-text search | 7700 |
| `kanka_ce_thumbor` | Image resizing proxy | 8888 |
| `kanka_ce_mailpit` | Local email (dev only) | 8025 |

---

## 2. Prerequisites

### Docker

```bash
# Check if Docker is installed
docker --version
docker compose version
```

If not installed: https://docs.docker.com/get-docker/

You need Docker Engine ≥ 20 and Docker Compose ≥ v2 (the `docker compose` command, not the older `docker-compose`).

**Add yourself to the docker group** (so you don't need `sudo`):

```bash
sudo usermod -aG docker $USER
# Log out and back in for this to take effect
```

### Python

```bash
python3 --version   # needs 3.10+
pip3 install requests
```

### Git

```bash
git --version
```

### Disk space

You need about 10 GB free — mostly for the Docker images.

```bash
df -h .
```

---

## 3. Get the Code

```bash
git clone https://github.com/wblair8689/campaign-forge.git
cd campaign-forge
```

---

## 4. Set Up Kanka CE

### 4a. Clone Kanka CE

```bash
git clone https://github.com/kinnewig/kanka-community-edition kanka-ce
```

### 4b. Apply the patches

campaign-forge ships three bug fixes for single-domain self-hosted installs. Apply them now:

```bash
git -C kanka-ce apply ../patches/kanka-ce.patch
```

You should see output like:

```
Checking patch app/Services/DomainService.php...
Checking patch config/filesystems.php...
Checking patch docker-compose.yml...
Checking patch .env.example...
```

No errors means the patches applied cleanly.

### 4c. Install PHP dependencies

Kanka CE is a Laravel app. Its PHP dependencies install via Composer. We use Docker to run Composer so you don't need PHP installed locally:

```bash
cd kanka-ce

docker run --rm \
  -u "$(id -u):$(id -g)" \
  -v "$(pwd):/var/www/html" \
  -w /var/www/html \
  laravelsail/php84-composer:latest \
  composer install --ignore-platform-reqs
```

This downloads ~150 PHP packages into `kanka-ce/vendor/`. It takes 2–5 minutes.

---

## 5. Configure Environment

### 5a. Create the .env file

```bash
# Still inside kanka-ce/
cp .env.example .env
```

### 5b. Generate random passwords

```bash
bash gen-passwords.sh
```

This fills in `DB_PASSWORD`, `DB_ROOT_PASSWORD`, `MINIO_PASSWORD`, `MEILISEARCH_KEY`, and `REVERB_APP_SECRET` with random values. **Do not skip this.**

### 5c. Set the data directory

This is where Docker will store persistent data (database files, uploaded images, etc.). It defaults to `/opt/kanka-data`.

```bash
mkdir -p /opt/kanka-data/{mariadb,redis,minio,thumbor,meilisearch}
```

If you want it somewhere else, edit `.env`:

```
KANKA_CE_DATA=/your/preferred/path
```

Then create the subdirectories at that path instead.

### 5d. Check for port conflicts

The stack needs these ports free: **8081, 3306, 6379, 9000, 7700, 8025, 8888**.

```bash
ss -tlnp | awk '{print $4}' | grep -oP ':\K[0-9]+$' | sort -n
```

**If any of those ports are taken:**

| Conflict | Fix in .env |
|---|---|
| Port 6379 (Redis) taken | Add `REDIS_HOST_PORT=6380` |
| Port 9000 (MinIO) taken | Add `MINIO_HOST_PORT=9010` and `MINIO_CONSOLE_HOST_PORT=9011` |
| Port 8081 (web app) taken | Change `APP_PORT=8082` (or any free port) |
| Port 3306 (MariaDB) taken | Change `DB_PORT=3307` |

---

## 6. Start the Stack

```bash
# Still inside kanka-ce/
vendor/bin/sail up -d
```

Docker will pull the images (first run: ~5 minutes) and start all 8 containers.

Verify they're all running:

```bash
docker compose ps
```

You should see all containers with status `Up` or `healthy`.

---

## 7. First-Time Installation

Wait for MariaDB to be ready (usually 10–15 seconds after `sail up`):

```bash
# Wait until this outputs "1" (MariaDB ready)
until docker exec kanka_ce_mariadb mariadb -u root -p$(grep DB_ROOT_PASSWORD .env | cut -d= -f2) kanka -h localhost --silent -e "SELECT 1" 2>/dev/null; do
  echo "Waiting for MariaDB..."
  sleep 2
done
echo "Ready!"
```

Now run the Kanka installer:

```bash
vendor/bin/sail artisan kanka:install
```

This runs all database migrations (takes ~30 seconds) and seeds initial data. At the end you'll see:

```
Kanka successfully installed.
```

Set up the search index:

```bash
vendor/bin/sail artisan setup:meilisearch
```

Configure MinIO (file storage) — **replace `<MINIO_PASSWORD>` with the value from your `.env`**:

```bash
MINIO_PASSWORD=$(grep '^MINIO_PASSWORD=' .env | cut -d= -f2)

docker exec kanka_ce_minio mc alias set kanka http://localhost:9000 sail "$MINIO_PASSWORD"
docker exec kanka_ce_minio mc mb --ignore-existing kanka/kanka kanka/thumbnails
docker exec kanka_ce_minio mc anonymous set public kanka/kanka kanka/thumbnails
```

---

## 8. Create Your Admin Account

```bash
vendor/bin/sail artisan user:add --admin "Your Name" "your@email.com"
```

You'll be prompted for a password. Choose something strong.

---

## 9. Get Your API Token

1. Open **http://localhost:8081** in your browser
2. Log in with the email and password you just set
3. Go to **Settings → API** (top-right menu → your name → Settings → API tab)
4. Click **Create new token**, give it a name like `campaign-forge-dev`
5. Copy the token — you only see it once

> Alternatively, generate a token via artisan:
>
> ```bash
> vendor/bin/sail artisan tinker --no-interaction <<'EOF'
> $user = App\Models\User::first();
> $token = $user->createToken('campaign-forge-dev');
> echo $token->accessToken . "\n";
> EOF
> ```

---

## 10. Wire Up the Python Client

Go back to the campaign-forge project root:

```bash
cd ..   # back to campaign-forge/
```

Copy the example env file:

```bash
cp .env.example .env
```

Edit `.env` and fill in your token:

```bash
KANKA_BASE_URL=http://localhost:8081
KANKA_TOKEN=paste-your-token-here
KANKA_CAMPAIGN_ID=1
```

---

## 11. Verify Everything Works

```bash
python kanka_client.py
```

Expected output:

```
Listing campaigns...
  Found 0 campaign(s)
Creating test campaign...
  Created: Demo World (id=1)

Creating location in campaign 1...
  Created location: The Wandering Market (id=1, entity_id=1)

Creating character in campaign 1...
  Created character: Sera Voss (id=1)

Creating organisation in campaign 1...
  Created organisation: The Fourth Circle (id=1)

Done. Kanka CE REST API is fully operational.
```

Open **http://localhost:8081** and you should see your new campaign with the location, character, and organisation already in it.

**Phase 1 complete.** You now have a fully working self-hosted world-state store with a Python API client.

---

## 12. Stopping and Starting

**Stop the stack (data is preserved):**

```bash
cd kanka-ce
vendor/bin/sail down
```

**Start it again:**

```bash
cd kanka-ce
vendor/bin/sail up -d
```

**Remove everything including data** (destructive — wipes the database):

```bash
vendor/bin/sail down -v
rm -rf /opt/kanka-data   # or wherever KANKA_CE_DATA points
```

---

## 13. Troubleshooting

### "Port is already allocated"

A port the stack needs is in use. See [Section 5d](#5d-check-for-port-conflicts) for how to remap ports.

### API returns `{"error": "Page not found"}`

Make sure you applied the patches in step 4b. The `DomainService` patch is required for single-domain installs. Verify:

```bash
git -C kanka-ce diff app/Services/DomainService.php
```

You should see the `is('api/*')` line removed.

### `{"error": "Disk [minio] does not have a configured driver."}`

The `filesystems.php` patch didn't apply. Check:

```bash
git -C kanka-ce diff config/filesystems.php | grep minio
```

If empty, re-apply the patch: `git -C kanka-ce apply ../patches/kanka-ce.patch`

### Login page shows 500 error

Check the Laravel log:

```bash
docker exec kanka_ce_laravel tail -30 /var/www/html/storage/logs/laravel-$(date +%Y-%m-%d).log
```

Common cause: Redis connection refused. Check that `REDIS_PORT=6379` (the internal port) is set correctly in `kanka-ce/.env`. `REDIS_HOST_PORT` is only for the host-side mapping.

### MinIO buckets not accessible

Re-run the MinIO setup commands from [Section 7](#7-first-time-installation).

### Containers keep restarting

```bash
docker compose logs kanka_ce_laravel --tail=50
```

Usually a misconfigured `.env` value. Re-read the environment configuration steps.

---

## What's Next

Once Phase 1 is running, the next steps are:

- **Phase 2 — World Builder** (`world_builder.py`): Conversational CLI that takes a campaign description, calls Claude to extract entities, and populates Kanka CE
- **Phase 3 — Foundry VTT**: Connect your VTT to Kanka CE and Claude via the foundry-vtt-mcp bridge
- **Phase 4 — Local RAG**: Stand up dnd-llm-game for fully offline 5e statblock retrieval
- **Phase 5 — CampaignGenerator Integration**: Wire the full prep and post-session narrative pipeline

See [HANDOFF.md](HANDOFF.md) for the current state and full build order.

# Self-Hosting NexusAI

## Prerequisites

- Docker Desktop (includes Docker Compose v2)
- Nothing else — Postgres and Redis are bundled in the Compose file

## Setup

### 1. Clone the repository

```bash
git clone https://github.com/your-org/nexusai
cd nexusai
```

### 2. Generate a vault encryption key

The vault requires a 32-byte (64 hex character) AES-256 key. Generate one now and keep it safe — losing it means losing access to all stored secrets.

```bash
python -c "import secrets; print(secrets.token_hex(32))"
# example output: a3f1c2d4e5b6a7f8c9d0e1f2a3b4c5d6e7f8a9b0c1d2e3f4a5b6c7d8e9f0a1b2
```

### 3. Configure environment variables

```bash
cp .env.example .env
```

Edit `.env` and fill in every `CHANGE_ME` value:

| Variable | Required | Description |
|----------|----------|-------------|
| `APP_ENV` | No | `development` or `production`. Controls log verbosity and debug mode. Default: `development` |
| `APP_DEBUG` | No | Enable FastAPI debug mode. Set `false` in production. Default: `true` |
| `APP_SECRET_KEY` | **Yes** | Random string, minimum 32 characters. Used for internal signing. |
| `API_HOST` | No | Interface to bind. `0.0.0.0` to listen on all interfaces. Default: `0.0.0.0` |
| `API_PORT` | No | Port for the FastAPI backend. Default: `8000` |
| `API_PREFIX` | No | URL prefix for all API routes. Default: `/api/v1` |
| `POSTGRES_HOST` | No | Postgres hostname. When using Docker Compose, this is `postgres` (the service name). Default: `localhost` |
| `POSTGRES_PORT` | No | Postgres port. Default: `5432` |
| `POSTGRES_DB` | **Yes** | Database name. Default in example: `nexusai` |
| `POSTGRES_USER` | **Yes** | Postgres username. |
| `POSTGRES_PASSWORD` | **Yes** | Postgres password. Use a strong random value in production. |
| `DATABASE_URL` | **Yes** | Full asyncpg connection string. Docker Compose overrides this automatically to use the internal `postgres` hostname. |
| `REDIS_HOST` | No | Redis hostname. When using Docker Compose: `redis`. Default: `localhost` |
| `REDIS_PORT` | No | Redis port. Default: `6379` |
| `REDIS_PASSWORD` | **Yes** | Redis password. Set the same value in `REDIS_URL`. |
| `REDIS_URL` | **Yes** | Full Redis connection string. Docker Compose overrides to use the internal `redis` hostname. |
| `VAULT_ENCRYPTION_KEY` | **Yes** | 64 hex characters (32 bytes). AES-256-GCM master key for all vault secrets. Never rotate this without first decrypting and re-encrypting all vault entries. |
| `CACHE_EMBEDDING_MODEL` | No | FastEmbed model name for semantic cache L3. Default: `all-MiniLM-L6-v2` |
| `CACHE_SIMILARITY_THRESHOLD` | No | Cosine similarity threshold (0–1) for L3 cache hits. Default: `0.95`. Lower = more aggressive caching, higher = stricter matching. |
| `CACHE_TTL_SECONDS` | No | How long cache entries live before expiry. Default: `3600` (1 hour) |
| `CORS_ORIGINS` | No | Comma-separated list of allowed CORS origins for the dashboard. Default: `http://localhost:3000,http://localhost:5173` |
| `VITE_API_BASE_URL` | No | Frontend-side API base URL (baked into the React build). Default: `http://localhost:8000/api/v1` |

### 4. Start all services

```bash
docker compose up -d
```

Docker Compose starts four containers: `postgres`, `redis`, `api`, and `frontend`. The `api` container waits for Postgres and Redis health checks before starting. First boot takes 1–2 minutes while the FastEmbed embedding model is downloaded.

### 5. Verify everything is running

```bash
docker compose ps
# All four services should show "healthy" or "running"
```

## Health check endpoints

| Endpoint | What it checks |
|----------|---------------|
| `GET /health` | API process is alive (always 200 if the process is running) |
| `GET /health/db` | Postgres connection is healthy |
| `GET /health/cache` | Redis connection is healthy |

```bash
curl http://localhost:8000/health
# {"status": "ok"}

curl http://localhost:8000/health/db
# {"status": "ok", "latency_ms": 2}
```

## Accessing the dashboard and API docs

- **Dashboard**: `http://localhost:3000` — React UI for managing agents, MCP servers, vault, and viewing sessions
- **API docs (Swagger)**: `http://localhost:8000/docs` — interactive OpenAPI documentation for all endpoints
- **API docs (ReDoc)**: `http://localhost:8000/redoc`

## Upgrading

```bash
git pull
docker compose down
docker compose build --no-cache
docker compose up -d
```

If a release includes a database migration, the API container applies it automatically on startup via Alembic. Check `docker compose logs api` for migration output.

> **Note**: Never `docker compose down -v` unless you intend to wipe all data. The `-v` flag removes named volumes including `postgres_data` and `redis_data`.

## Running in production

For production deployments, change these from the defaults:

1. `APP_ENV=production` and `APP_DEBUG=false`
2. Set `CORS_ORIGINS` to your actual frontend domain
3. Put a TLS-terminating reverse proxy (nginx, Caddy, Cloudflare Tunnel) in front of port 8000
4. Do not expose port 5432 or 6379 to the public internet — remove the `ports:` sections for `postgres` and `redis` in `docker-compose.yml`, or use a separate `docker-compose.prod.yml` override
5. Store `VAULT_ENCRYPTION_KEY` in a secrets manager (not in `.env` on disk)

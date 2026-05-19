# Arbiter

A self-hosted MCP (Model Context Protocol) gateway that gives teams centralized control over AI tool access: secret management, semantic caching, RBAC, and full audit logging.

## Quick Start

```bash
# 1. Copy env file and fill in values
cp .env.example .env

# 2. Start all services
docker compose up -d

# 3. Verify API is live
curl http://localhost:8000/health
```

## Architecture Summary

```
Client (Claude / any MCP agent)
        |
        v
  [Arbiter API Gateway]  :8000
        |
  +-----------+----------+-----------+
  |           |          |           |
[Vault]  [Cache]    [RBAC]      [Proxy]
  |           |          |           |
[Postgres] [Redis]  [Postgres]  [MCP Servers]
```

### Core Services

| Service | Responsibility |
|---------|---------------|
| Vault | AES-256 encryption at rest for API keys / secrets |
| Cache | Semantic deduplication of tool calls via embeddings |
| RBAC | Per-agent, per-tool permission matrix |
| Proxy | MCP protocol forwarding with full event capture |

## Services (docker-compose)

| Container | Port | Description |
|-----------|------|-------------|
| api | 8000 | FastAPI backend |
| postgres | 5432 | Primary database |
| redis | 6379 | Cache + session store |
| frontend | 3000 | React dashboard |

## Project Structure

```
arbiter/
  backend/          FastAPI application
    app/
      api/v1/       REST endpoints
      core/         Config, deps, security
      db/           Models, migrations, schema
      services/     Vault, Cache, Proxy, RBAC
      schemas/      Pydantic request/response models
    tests/
  frontend/         React + TypeScript dashboard
    src/
      api/          Axios client
      pages/        Dashboard, Agents, Sessions
      components/   Shared UI
  infra/            Nginx reverse proxy config
```

## Environment Variables

See `.env.example` for all required variables.

## Development

```bash
# Backend only
cd backend && pip install -r requirements.txt
uvicorn app.main:app --reload

# Frontend only
cd frontend && npm install && npm run dev
```

## License

Private — all rights reserved.

<div align="center">

<img src="frontend/src/assets/logo-transparent.png" alt="Arbiter" width="72" />

# Arbiter — MCP Gateway for AI Agents

> Control what your agents touch. Observe everything they do.

![License](https://img.shields.io/badge/license-private-red)
![FastAPI](https://img.shields.io/badge/FastAPI-0.115-009688?logo=fastapi)
![React](https://img.shields.io/badge/React-18-61DAFB?logo=react)
![PostgreSQL](https://img.shields.io/badge/PostgreSQL-16-4169E1?logo=postgresql)
![Deployed on Railway](https://img.shields.io/badge/deployed%20on-Railway-7C3AED?logo=railway)

[**Live Demo →**](https://arbiterai.dev) · [**API Docs →**](https://arbiterai.dev/api/v1/docs) · [**Contact**](mailto:jaidensy07@gmail.com)

</div>

---

## Why Arbiter?

When you connect an AI agent directly to MCP servers, you get no access control, no audit trail, no secret management, and no cost optimization. Every agent has the same permissions. Leaked keys are invisible. Runaway agents have nothing stopping them.

Arbiter is a developer-first [Model Context Protocol (MCP)](https://modelcontextprotocol.io) gateway that sits between your AI agents and their tools — one central place to enforce tool-level permissions, store secrets, cache responses, and watch every session in real time.

## Features

- **Agent Identity** — Each agent gets a scoped cryptographic API key. No shared credentials. Know exactly which agent called what.
- **Tool-Level RBAC** — Grant only the tools each agent needs. `read_file` ≠ `delete_file`. Your dev agent shouldn't have prod database access.
- **Encrypted Vault** — API keys and credentials stored with AES-256-GCM, injected at proxy time. Agents never see raw keys in plaintext.
- **Semantic Cache** — Identical (and semantically similar) tool calls return cached results via pgvector ANN search. Fewer API calls, lower cost.
- **Full Observability** — Every session, every tool call, every response. Logged with duration, cache status, and agent identity. Searchable and visualized.
- **Rate Limiting** — Per-agent, per-tool rate limits enforced at the gateway.
- **SSO Support** — Google and GitHub OAuth out of the box.

```
Your AI Agent
      │  Bearer nxai_...
      ▼
┌─────────────────────────────────────┐
│           Arbiter Gateway           │
│                                     │
│  ┌─────────┐  ┌───────┐  ┌───────┐ │
│  │  RBAC   │  │ Vault │  │ Cache │ │
│  └────┬────┘  └───┬───┘  └───┬───┘ │
│       │           │           │     │
│       └───────────┴───────────┘     │
│                   │                 │
│              ┌────▼────┐            │
│              │  Proxy  │            │
│              └────┬────┘            │
└───────────────────┼─────────────────┘
                    │
          ┌─────────┴──────────┐
          ▼                    ▼
   MCP Server A          MCP Server B
  (GitHub, Slack…)     (Filesystem…)
```

---

## Quick start

### Cloud (recommended)

```bash
# 1. Register at https://arbiterai.dev
# 2. Create an agent and copy its API key
# 3. Point your MCP client at the Arbiter proxy

# In your Claude Desktop / MCP config:
{
  "mcpServers": {
    "your-server": {
      "url": "https://nexusai-api-production.up.railway.app/api/v1/proxy/tool-call",
      "headers": {
        "Authorization": "Bearer nxai_your_agent_key"
      }
    }
  }
}
```

### Self-hosted

```bash
# 1. Clone and configure
git clone https://github.com/JaidenSy/Arbiter.git
cd Arbiter
cp .env.example .env   # fill in DATABASE_URL, REDIS_URL, VAULT_ENCRYPTION_KEY, APP_SECRET_KEY

# 2. Start everything
docker compose up -d

# 3. Confirm it's live
curl http://localhost:8000/health
# → {"status":"ok"}
```

Then open [http://localhost:3000](http://localhost:3000) to access the dashboard.

---

## How it works

### 1 — Register an agent

```bash
curl -X POST http://localhost:8000/api/v1/agents \
  -H "Authorization: Bearer <your-jwt>" \
  -d '{"name": "my-claude-agent", "scope": "full"}'

# → { "api_key": "nxai_abc123..." }   ← shown once, store it
```

### 2 — Grant tool permissions

```bash
curl -X POST http://localhost:8000/api/v1/agents/<agent-id>/permissions \
  -H "Authorization: Bearer <your-jwt>" \
  -d '{"mcp_server_id": "<server-id>", "tool_name": "read_file"}'
```

### 3 — Proxy tool calls through Arbiter

```bash
curl -X POST http://localhost:8000/api/v1/proxy/tool-call \
  -H "Authorization: Bearer nxai_abc123..." \
  -d '{
    "server_name": "filesystem",
    "tool_name": "read_file",
    "params": { "path": "/app/config.json" }
  }'

# → { "result": {...}, "cache_hit": false, "duration_ms": 42 }
```

Every call is logged. If the agent tries a tool it wasn't granted, it gets a 403 — not a silent pass-through.

---

## Comparison

| | **Arbiter** | LiteLLM | Portkey | Build it yourself |
|---|:---:|:---:|:---:|:---:|
| Per-agent identity | ✅ | ❌ | ❌ | ~3 months |
| Tool-level RBAC | ✅ | ❌ | ❌ | ~2 months |
| Encrypted secrets vault | ✅ | ❌ | ❌ | ~2 months |
| Semantic cache (pgvector) | ✅ | Partial | Partial | ~3 months |
| Full request/response audit log | ✅ | Partial | ✅ | ~1 month |
| MCP protocol native | ✅ | ❌ | ❌ | depends |
| Self-hosted | ✅ | ✅ | ❌ | ✅ |
| **Cost** | **$0–$29/mo** | Free/OSS | $49+/mo | **$50k–90k eng** |

---

## Stack

| Layer | Technology |
|---|---|
| API | FastAPI 0.115, Python 3.12 |
| Database | PostgreSQL 16 + pgvector |
| Cache | Redis 7 |
| Embeddings | sentence-transformers (all-MiniLM-L6-v2) |
| Frontend | React 18, TypeScript, Vite, Tailwind |
| Auth | JWT + bcrypt + Google/GitHub OAuth2 |
| Billing | Stripe |
| Deploy | Railway (API) + Vercel (frontend) |

## Project structure

```
Arbiter/
├── backend/
│   ├── app/
│   │   ├── api/v1/endpoints/   # agents, proxy, vault, sessions, billing, sso…
│   │   ├── core/               # config, security, dependencies
│   │   ├── db/                 # SQLAlchemy models + Alembic migrations
│   │   ├── schemas/            # Pydantic request/response models
│   │   └── services/           # vault, cache, rbac, proxy, billing, email
│   ├── requirements.txt
│   └── Dockerfile
├── frontend/
│   ├── src/
│   │   ├── pages/              # Dashboard, Agents, Sessions, Settings, Landing…
│   │   ├── components/         # Shared UI components
│   │   ├── api/                # Axios client + TypeScript types
│   │   └── context/            # Auth context
│   └── Dockerfile
└── docker-compose.yml
```

## Environment variables

See [`.env.example`](.env.example) for all required variables. Required at minimum:

| Variable | Description |
|---|---|
| `DATABASE_URL` | PostgreSQL asyncpg DSN |
| `REDIS_URL` | Redis DSN |
| `VAULT_ENCRYPTION_KEY` | 64-char hex (AES-256 key) |
| `APP_SECRET_KEY` | Session signing key |
| `JWT_SECRET_KEY` | JWT signing secret |

## Development

```bash
# Backend
cd backend
pip install -r requirements.txt
cp ../.env.example ../.env
uvicorn app.main:app --reload

# Frontend (separate terminal)
cd frontend
pnpm install
pnpm dev
```

---

## License

Private — all rights reserved.

---

Built by [@JaidenSy](https://github.com/JaidenSy)

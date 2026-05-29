<div align="center">

<img src="frontend/src/assets/logo-transparent.png" alt="Arbiter" width="72" />

# Arbiter

**The MCP gateway your AI agents actually need.**

![License](https://img.shields.io/badge/license-private-red)
![FastAPI](https://img.shields.io/badge/FastAPI-0.115-009688?logo=fastapi)
![React](https://img.shields.io/badge/React-18-61DAFB?logo=react)
![PostgreSQL](https://img.shields.io/badge/PostgreSQL-16-4169E1?logo=postgresql)
![Deployed on Railway](https://img.shields.io/badge/deployed%20on-Railway-7C3AED?logo=railway)

[**Live Demo →**](https://arbiterai.dev) · [**API Docs →**](https://arbiterai.dev/api/v1/docs) · [**Contact**](mailto:jaidensy07@gmail.com)

</div>

---

## The problem

Most teams give every AI agent the same credentials and let it call any tool it wants. There's no audit trail, no access control, and secrets are copy-pasted into environment variables or hardcoded in prompts.

When something goes wrong — a runaway agent, a leaked key, a compliance audit — you have nothing.

## What Arbiter does

Arbiter is a self-hosted MCP gateway that sits between your AI agents and your MCP servers. Every tool call flows through it, giving you:

- **Agent identity** — every agent gets its own cryptographic API key. No shared credentials.
- **Tool-level RBAC** — grant only the tools each agent needs. `read_file` ≠ `delete_file`.
- **Encrypted vault** — secrets stored with AES-256-GCM, injected at proxy time. Agents never see raw keys.
- **Semantic cache** — identical (and similar) tool calls return cached responses via pgvector ANN search.
- **Full audit log** — every request and response captured with duration, cache status, and agent identity.
- **Rate limiting** — per-agent, per-tool rate limits enforced at the gateway.

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

```bash
# 1. Clone and configure
git clone https://github.com/JaidenSy/nexvault.git
cd nexvault
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
nexvault/
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

<div align="center">

<img src="frontend/src/assets/logo-transparent.png" alt="Arbiter" width="72" />

# Arbiter

**The MCP security gateway for AI agents.**

![License](https://img.shields.io/badge/license-proprietary-red)
![FastAPI](https://img.shields.io/badge/FastAPI-0.115-009688?logo=fastapi)
![React](https://img.shields.io/badge/React-18-61DAFB?logo=react)
![PostgreSQL](https://img.shields.io/badge/PostgreSQL-16-4169E1?logo=postgresql)
![Deployed on Railway](https://img.shields.io/badge/deployed%20on-Railway-7C3AED?logo=railway)

[**arbiterai.dev →**](https://arbiterai.dev) · [**API Docs →**](https://arbiterai.dev/docs) · [**support@arbiterai.dev**](mailto:support@arbiterai.dev)

</div>

---

## The problem

Most teams give every AI agent the same credentials and let it call any tool it wants. There's no audit trail, no access control, and secrets are copy-pasted into environment variables or hardcoded in prompts.

When something goes wrong — a runaway agent, a leaked key, a compliance audit — you have nothing.

## What Arbiter does

Arbiter is a hosted MCP gateway that sits between your AI agents and your MCP servers. Every tool call flows through it, giving you:

- **Agent identity** — every agent gets its own cryptographic API key (`nxai_...`). No shared credentials.
- **Tool-level RBAC** — grant only the tools each agent needs. `read_file` ≠ `delete_file`.
- **Encrypted vault** — secrets stored with AES-256-GCM, injected at proxy time. Agents never see raw keys.
- **Semantic cache** — identical (and similar) tool calls return cached responses via pgvector ANN search (Pro+).
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

## How it works

### 1 — Register an agent

```bash
curl -X POST https://api.arbiterai.dev/api/v1/agents \
  -H "Authorization: Bearer <your-jwt>" \
  -d '{"name": "my-claude-agent"}'

# → { "api_key": "nxai_abc123..." }   ← shown once, store it
```

### 2 — Grant tool permissions

```bash
curl -X POST https://api.arbiterai.dev/api/v1/agents/<agent-id>/permissions \
  -H "Authorization: Bearer <your-jwt>" \
  -d '{"mcp_server_id": "<server-id>", "tool_name": "read_file"}'
```

### 3 — Proxy tool calls through Arbiter

```bash
curl -X POST https://api.arbiterai.dev/api/v1/proxy/tool-call \
  -H "Authorization: Bearer nxai_abc123..." \
  -d '{
    "server_name": "filesystem",
    "tool_name": "read_file",
    "params": { "path": "/app/config.json" }
  }'

# → { "result": {...}, "cached": false, "agent_id": "agt_xyz789" }
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
| Self-hosted | Enterprise | ✅ | ❌ | ✅ |
| **Cost** | **$0–$29/mo** | Free/OSS | $49+/mo | **$50k–90k eng** |

---

## Plans

| | Free | Pro ($29/mo) | Enterprise |
|--|------|-------------|------------|
| Agents | 2 | 25 | Unlimited |
| MCP Servers | 3 | 50 | Unlimited |
| Tool calls/mo | 5,000 | 100,000 | Unlimited |
| Secrets | 10 | 100 | Unlimited |
| Semantic cache | ✗ | ✓ | ✓ |
| Self-hosted | ✗ | ✗ | ✓ |

---

## Stack

| Layer | Technology |
|---|---|
| API | FastAPI 0.115, Python 3.12 |
| Database | PostgreSQL 16 + pgvector |
| Cache | Redis 7 |
| Embeddings | sentence-transformers (all-MiniLM-L6-v2, Pro+) |
| Frontend | React 18, TypeScript, Vite, Tailwind CSS |
| Auth | JWT HS256 (60min) + refresh tokens, bcrypt, Google/GitHub OAuth2 |
| Billing | Stripe (checkout, portal, webhooks) |
| Deploy | Railway (API + DB + Redis) · Vercel (frontend) |
| Package manager | pnpm |

---

## Project structure

```
arbiter/
├── backend/
│   ├── app/
│   │   ├── api/v1/endpoints/   # agents, proxy, vault, sessions, billing, sso, org…
│   │   ├── core/               # config, security, dependencies
│   │   ├── db/models/          # SQLAlchemy models (migrations 001–022)
│   │   ├── schemas/            # Pydantic request/response models
│   │   ├── services/           # proxy, vault, cache, rbac, billing, auth, email
│   │   └── tasks/              # background jobs (GDPR 30-day purge)
│   ├── tests/
│   ├── requirements.txt
│   └── Dockerfile
├── frontend/
│   ├── src/
│   │   ├── pages/              # Dashboard, Agents, Sessions, Vault, Permissions…
│   │   ├── components/         # Sidebar, AuthModal, CommandPalette, UpgradeModal…
│   │   ├── api/                # typed API client + types
│   │   └── context/            # AuthContext, PaletteContext
│   ├── pnpm-lock.yaml
│   └── Dockerfile
└── .github/workflows/          # deploy-staging CI
```

---

## Local development

**Backend:**
```bash
cd backend
python -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt
cp .env.example .env          # fill in values
alembic upgrade head
uvicorn app.main:app --reload --port 8000
```

**Frontend:**
```bash
cd frontend
pnpm install
cp .env.example .env.local    # fill in VITE_API_BASE_URL etc.
pnpm dev
```

**Required env vars** — see `backend/.env.example` and `frontend/.env.example`:

| Variable | Description |
|---|---|
| `DATABASE_URL` | `postgresql+asyncpg://...` |
| `REDIS_URL` | Redis DSN |
| `JWT_SECRET_KEY` | Min 32 chars in production |
| `VAULT_ENCRYPTION_KEY` | AES-256 Fernet key |
| `STRIPE_SECRET_KEY` | Stripe live/test secret |
| `STRIPE_WEBHOOK_SECRET` | Stripe webhook signing secret |

---

## Security

Responsible disclosure: **security@arbiterai.dev**
DMCA agent: DMCA-1073513 · dmca@arbiterai.dev

---

## License

Proprietary. All rights reserved © 2026 Arbiter.
This codebase is not licensed for redistribution, modification, or commercial use by third parties.

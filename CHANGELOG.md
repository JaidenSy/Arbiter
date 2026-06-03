# Changelog

All notable changes to Arbiter are documented here.

## [0.2.1] — 2026-06-03

### Added
- **Docs tab in dashboard sidebar** — logged-in users can now navigate directly to `/docs` from the sidebar without going back to the landing page. Also included in the product walkthrough tour.

### Fixed
- **Gateway URL now defaults to the correct production URL** — the Gateway URL field in Settings previously defaulted to `http://localhost:8000/api/v1`, implying users needed to run Arbiter locally. It now defaults to the live Railway backend URL. The field also now correctly drives where the dashboard sends API requests (changing it and saving takes effect on reload).

## [0.2.0] — 2026-05-30

### Added
- Privacy policy live at `/privacy`, linked from signup and all footers
- Accessibility: skip-nav link, `eslint-plugin-jsx-a11y` enabled
- Copyright headers on core backend files

### Fixed
- Free tier MCP server count corrected on landing page (5 → 3)
- CI: upgraded to Node 22, pinned pnpm to v9 via action-setup
- Self-hosted tier gating — available to all plans, not Enterprise-only

## [0.1.0] — Initial release

- MCP gateway with agent identity and scoped API keys
- Tool-level access control (permissions) per agent
- Encrypted secrets vault
- Semantic caching
- Full agent chain observability (sessions + traces)
- Multi-tenant org support with role-based access
- Stripe billing integration (Free / Pro / Enterprise)
- Google and GitHub OAuth

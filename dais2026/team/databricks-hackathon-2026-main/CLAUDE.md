# CLAUDE.md

Guidance for working in this repository. Read this before generating
Databricks code, running CLI commands, or deploying. Human-oriented setup
steps live in [SETUP.md](SETUP.md) — this file is the machine-oriented
summary of the defaults that must hold.

## Project

**Lumen Virtue** — a full-stack TypeScript [Databricks App](https://docs.databricks.com/aws/en/dev-tools/databricks-apps/)
built with [AppKit](https://www.databricks.com/devhub/docs/appkit/v0/). It
explores the **Virtue Foundation** healthcare-facility dataset (DAIS 2026
Marketplace listing), reading it live from a Lakebase synced table, with Genie
Q&A, an AI assistant, and a Lakebase outreach worklist.

- **Frontend:** React + TypeScript + Vite + Tailwind under `client/`.
- **Backend:** Express (TypeScript) + AppKit SDK under `server/`
  (`server.ts`, `routes/`). Shared types in `shared/`; SQL query assets in
  `config/queries/`.
- **Entry point:** `mise run dev` (`npm run dev`) — the AppKit server boots
  and serves the client via Vite middleware.
- **Bundle:** `lumen-virtue` — a Databricks Asset Bundle (DABs). Config in
  [databricks.yml](databricks.yml).
- **Purpose:** DAIS 2026 hackathon. Merge to `main`, then deploy to the shared
  demo workspace for the integrated demo.

## Commands

All workflows go through `mise` (run `mise tasks` for the full list); each
wraps the underlying `npm` script:

- `mise run install` — install deps (`npm install`) and hooks (`prek install`)
- `mise run dev` — run the dev server with hot reload
- `mise run build` — build the app (server + client) for production
- `mise run check` — lint + format check (CI equivalent)
- `mise run lint` — ESLint (app) + taplo (TOML)
- `mise run fmt` — auto-format with Prettier and taplo
- `mise run typecheck` — TypeScript type checking (`tsc`, server + client)
- `mise run test` — run the Vitest suite

The npm scripts are also available directly (`npm run dev`, `npm run build`,
`npm run lint`, `npm run format:fix`, `npm run typecheck`, `npm run test`).
End-to-end tests use Playwright: `npm run test:e2e`.

## Deployment — bundle & profile

The bundle (`lumen-virtue`) has a single `default` target that deploys to the
shared demo workspace (`https://dbc-5bcc65d8-a106.cloud.databricks.com`). Its
variables (SQL warehouse, Genie space, Lakebase branch/database, serving
endpoint) are set in that target. Authenticate a CLI profile against the shared
workspace, then deploy.

```bash
# Standard profile name across the team is `hackathon`
databricks bundle validate -p hackathon
databricks bundle deploy   -p hackathon
databricks bundle run app  -p hackathon
```

Merge to `main` and pull latest before deploying so the shared workspace
reflects the integrated team code.

## Hard rules

- **Never commit credentials.** `~/.databrickscfg` is per-machine. Nothing
  under it, and no tokens/secrets, ever land in this repo.
- **Always pass an explicit `-p` profile** on Databricks CLI commands — do
  not rely on `DEFAULT`. The team convention is `-p hackathon`.
- **Add bundle resources** (apps, jobs, pipelines) under the `resources:`
  block in `databricks.yml` (or `resources/*.yml`). The app is defined under
  `resources.apps.app`.
- **Runtime config** is injected by Databricks Apps via `app.yaml` (env vars
  from the bound resources). Locally it comes from `.env` (git-ignored); see
  `.env.example`.

## Tooling notes

- **Node 24** and **npm**; tool versions managed by mise in `mise.toml`.
- **TypeScript** project graph: `tsconfig.json` references
  `tsconfig.client.json` and `tsconfig.server.json` (both extend
  `tsconfig.shared.json`). Build: Vite (client) + tsdown (server).
- **ESLint** (`eslint.config.js`) and **Prettier** (`.prettierrc.json`,
  `.prettierignore`) for lint/format; **taplo** for TOML.
- **prek** runs ESLint (`eslint --fix`) and Prettier (`prettier --write`) on
  staged files at commit time via `mise exec --` (`prek.toml`).
- **Vitest** for unit tests; **Playwright** (`@playwright/test`,
  `client/playwright.config.ts`) for browser e2e.
- `shared/appkit-types/` holds **auto-generated** AppKit type declarations —
  do not hand-edit; regenerate with `npm run typegen`. `appkit.plugins.json`
  is managed by `npm run sync`.

<!-- appkit-instructions-start -->

## Databricks AppKit

This project uses Databricks AppKit packages. For AI assistant guidance on using these packages, refer to:

- **@databricks/appkit** (Backend SDK): [./node_modules/@databricks/appkit/CLAUDE.md](./node_modules/@databricks/appkit/CLAUDE.md)
- **@databricks/appkit-ui** (UI Integration, Charts, Tables, SSE, and more.): [./node_modules/@databricks/appkit-ui/CLAUDE.md](./node_modules/@databricks/appkit-ui/CLAUDE.md)

### Databricks Skills

For enhanced AI assistance with Databricks CLI operations, authentication, data exploration, and app development, install the Databricks skills:

```bash
databricks aitools install
```

<!-- appkit-instructions-end -->

## Installed agent tooling (travels with the repo)

- **Databricks agent skills** are installed at project scope under
  `.claude/skills/`. Use them for implementation patterns instead of
  guessing. Refresh with `databricks aitools install --project`.
- **DevHub Docs MCP server** (`devhub-docs`, HTTP, read-only, no credentials)
  is wired at project scope in `.mcp.json`, pointing at
  `https://developers.databricks.com/api/mcp`. Use it to look up Databricks
  docs on demand. Approve the project MCP server on first launch.

## When unsure

- Prefer the project-scoped skills and the `devhub-docs` MCP server over
  recalling Databricks or AppKit APIs from memory.
- For setup/auth questions, see [SETUP.md](SETUP.md).
- Ask before creating new Databricks resources (catalogs, schemas, instances,
  endpoints) or before deploying to the shared workspace.

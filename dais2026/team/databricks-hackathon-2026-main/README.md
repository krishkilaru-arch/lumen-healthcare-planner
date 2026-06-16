# DAIS 2026 Hackathon — Lumen Virtue

This repository is the main working project for the DAIS 2026 hackathon. It
hosts **Lumen Virtue**, a full-stack TypeScript [Databricks App](https://docs.databricks.com/aws/en/dev-tools/databricks-apps/)
built with [AppKit](https://www.databricks.com/devhub/docs/appkit/v0/) (React,
TypeScript, Tailwind CSS), deployed via a Databricks Asset Bundle. The app
explores the **Virtue Foundation** healthcare-facility dataset (DAIS 2026
Marketplace listing), reading it live from a Lakebase synced table.

Each person develops locally; everything is merged to `main` and deployed to
the shared workspace for the integrated demo.

## What this project includes

- A healthcare-facility explorer over the Virtue Foundation dataset, with Genie
  Q&A, an AI assistant, and a Lakebase outreach worklist.
- Databricks Asset Bundle configuration for deploying to the shared demo
  workspace.
- SQL query assets for KPI and reporting use cases (`config/queries/`).
- Setup and workspace conventions documented for team members and coding agents.

## Enabled AppKit plugins

- **Analytics** — SQL query execution against Databricks SQL Warehouses
- **Lakebase** — fully managed Postgres (OLTP) on Databricks
- **Genie** — AI/BI Genie conversational interface for natural-language queries
- **Server** — Express HTTP server with static file serving and Vite dev mode

## Tech stack

- **Frontend**: React, TypeScript, Vite, Tailwind CSS, React Router
- **UI components**: Radix UI, shadcn/ui, AppKit UI
- **Backend**: Express (TypeScript), AppKit SDK
- **Databricks**: Databricks Asset Bundles, Lakebase (Postgres)
- **Tooling**: [mise](https://mise.jdx.dev/) (task runner + tool versions),
  Node 24, ESLint, Prettier, Vitest, [Playwright](https://playwright.dev/),
  taplo (TOML), [prek](https://github.com/j178/prek) (pre-commit hooks)

## Prerequisites

- Node.js v22+ (mise pins Node 24)
- Databricks CLI (for deployment)
- Access to a Databricks workspace

## Getting started

1. Install [mise](https://mise.jdx.dev/getting-started.html).
2. Copy the env template and fill in your Databricks/Lakebase credentials:

   ```sh
   cp .env.example .env
   ```

   `mise` auto-loads `.env` for all tasks. For the Lakebase plugin, see the
   [Lakebase plugin docs](https://www.databricks.com/devhub/docs/appkit/v0/plugins/lakebase).

3. Install dependencies and pre-commit hooks:

   ```sh
   mise run install
   ```

4. Run the app in development mode with hot reload:

   ```sh
   mise run dev    # or: npm run dev
   ```

   The app will be available at the URL shown in the console output.

## Common tasks

All workflows go through `mise` (which wraps the underlying `npm`/tooling
scripts — run `mise tasks` for the full list):

- `mise run install` — install dependencies + pre-commit hooks
- `mise run dev` — run the dev server with hot reload
- `mise run build` — build the app (server + client) for production
- `mise run check` — lint + format check (CI equivalent)
- `mise run lint` — ESLint (app) + taplo (TOML)
- `mise run fmt` — auto-format with Prettier and taplo
- `mise run typecheck` — TypeScript type checking (`tsc`, server + client)
- `mise run test` — run the Vitest suite

The equivalent npm scripts are also available directly: `npm run dev`,
`npm run build`, `npm run lint`, `npm run format:fix`, `npm run typecheck`,
`npm run test`.

## Databricks authentication

Authenticate the CLI with OAuth (recommended over legacy PATs). Credentials are
saved to `~/.databrickscfg` and must never be committed.

```bash
databricks auth login --host <YOUR_WORKSPACE_URL> --profile hackathon
databricks auth profiles
databricks current-user me --profile hackathon
```

Install the repo's project-scoped agent tooling:

```bash
databricks aitools install --project
databricks aitools list --project
```

## Deployment with Databricks Asset Bundles

The bundle (`lumen-virtue`) has a single `default` target that deploys to the
shared demo workspace (`https://dbc-5bcc65d8-a106.cloud.databricks.com`). Its
variables (SQL warehouse, Genie space, Lakebase branch/database, serving
endpoint) are set in that target. Authenticate a CLI profile against the shared
workspace, then deploy. Always pass an explicit `-p` profile.

```bash
databricks bundle validate -p hackathon
databricks bundle deploy   -p hackathon
databricks bundle run app  -p hackathon
```

Merge to `main` and pull latest before deploying so the shared workspace
reflects the integrated team code.

## Project structure

```
* client/          # React frontend (src/, public/)
* server/          # Express backend (server.ts, routes/)
* shared/          # Shared types between client and server
* config/
  * queries/       # SQL query files
* databricks.yml   # Bundle configuration (single `default` target → shared workspace)
* app.yaml         # Databricks App configuration
* appkit.plugins.json  # AppKit plugin configuration
* mise.toml        # Task runner + tool versions
* .env.example     # Environment variables example
```

## Notes

- Never commit credentials or Databricks config files; `~/.databrickscfg` is
  per-machine.
- Add bundle resources (apps, jobs, pipelines) under the `resources:` block in
  `databricks.yml` (or `resources/*.yml`). The app is defined under
  `resources.apps.app`.
- For setup/auth details, see [SETUP.md](SETUP.md). Conventions for coding
  agents live in [CLAUDE.md](CLAUDE.md).

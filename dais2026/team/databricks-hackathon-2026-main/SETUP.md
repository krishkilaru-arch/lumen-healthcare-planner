# DAIS 2026 Hackathon — Environment Setup

The code lives in this GitHub repo (the integration point). Everyone develops
locally and deploys to **one shared Databricks workspace** for the integrated
demo. The bundle (`lumen-virtue`) has a single `default` target pointed at that
shared workspace; its resource variables are baked into the target.

We standardize on the profile name **`hackathon`** so commands look identical
for everyone. Credentials stay local and are never committed.

---

## 1. Install prerequisites

- **[mise](https://mise.jdx.dev/getting-started.html)** — task runner + tool
  versions (provisions Node 24 and the rest of the toolchain).
- **Databricks CLI** — for deployment.

macOS (Homebrew):

```bash
brew tap databricks/tap
brew install databricks
databricks --version   # need 1.0.0+
```

Windows: use WSL, then follow the macOS/Linux steps.

## 2. Authenticate to the shared workspace

The bundle deploys to the shared workspace, so authenticate the `hackathon`
profile against it:

```bash
databricks auth login --host https://dbc-5bcc65d8-a106.cloud.databricks.com --profile hackathon
databricks auth profiles                          # hackathon should show Valid = YES
databricks current-user me --profile hackathon     # should return your user
```

`~/.databrickscfg` is written on your own machine — **never commit it.**

## 3. Install agent skills (project-scoped, committed)

```bash
databricks aitools install --project
databricks aitools list --project
```

## 4. Develop locally

Install dependencies and pre-commit hooks, then run the dev server:

```bash
cp .env.example .env   # fill in Databricks/Lakebase credentials; mise auto-loads it
mise run install       # npm install + prek install
mise run dev           # AppKit server + Vite client with hot reload
```

See [README.md](README.md) for the full task list (`mise run build`, `check`,
`lint`, `fmt`, `typecheck`, `test`).

## 5. Deploy to the shared workspace

`default` is the only target (no `-t` needed). Always pass `-p hackathon`:

```bash
databricks bundle validate -p hackathon
databricks bundle deploy   -p hackathon
databricks bundle run app  -p hackathon
```

Pull the latest from GitHub before each deploy so the shared workspace reflects
merged team code.

> ⚠️ Local `bundle deploy` ships **whatever is in `dist/` and `client/dist/`**.
> Run `mise run build` first, or you'll deploy stale/missing artifacts. CI (next
> section) is the canonical deploy path and always builds fresh.

## 6. Automated deployment (CI/CD)

Every merge to `main` automatically deploys to the shared workspace via GitHub
Actions ([.github/workflows/deploy.yml](.github/workflows/deploy.yml)). The
pipeline:

1. **Validate** — reuses the PR checks (lint/format + typecheck + test); the
   deploy is gated on these passing.
2. **Build** — `mise run build` produces the server bundle (`dist/`) and client
   assets (`client/dist/`) **in CI**. These artifacts are what get shipped; the
   platform does not rebuild. `databricks.yml` force-includes them via
   `sync.include` (they're otherwise git-ignored).
3. **Deploy** — `databricks bundle validate` → `deploy` → `run app` against the
   shared workspace. `run app` restarts the app so the new code goes live.

### Required GitHub secrets (one-time, admin)

CI has no `~/.databrickscfg`, so it authenticates with **service-principal OAuth
(M2M)** via unified-auth env vars. Add these as repository secrets (or scope
them to the `shared-demo` GitHub Environment the workflow references):

| Secret                     | Value                                                   |
| -------------------------- | ------------------------------------------------------- |
| `DATABRICKS_CLIENT_ID`     | OAuth client ID of a service principal in the workspace |
| `DATABRICKS_CLIENT_SECRET` | That service principal's OAuth secret                   |

The workspace host is set in the workflow `env` (same host the bundle target
uses), so no host secret is needed.

The service principal must be able to deploy the bundle and have access to the
bound resources (SQL warehouse, Genie space, Lakebase, serving endpoint) —
grant it the same permissions a deploying user would have.

## 7. Docs MCP Server (gives your editor agent access to Databricks docs)

Connects your coding agent (VS Code, Cursor, Claude Code) to the DevHub docs so
it can look things up without leaving the editor. Read-only, no credentials.

**This is already wired up in the repo** — no install command needed. The
`devhub-docs` server (HTTP, `https://developers.databricks.com/api/mcp`) is
committed at project scope so it travels with the repo:

- Claude Code: [.mcp.json](.mcp.json)
- Cursor / VS Code: [.cursor/mcp.json](.cursor/mcp.json)

Just **open the repo in your editor and enable the server** the first time:

- Claude Code: on first launch it prompts to approve the project MCP server —
  approve `devhub-docs`. (Check status with `claude mcp list`.)
- VS Code / Cursor: Command Palette → `MCP: List Servers` → select
  `devhub-docs` → Start Server. It should go to **Running** with 2 tools.

Verify by asking your agent: _"What are the available docs on devhub?"_ — it
should return the docs index.

> Note: Claude Desktop only supports local (stdio) servers from the CLI; add
> this remote server via the app's Settings → Connectors if you want it there.

---

## Conventions

- **Profile:** `hackathon`, pointed at the shared demo workspace.
- **Credentials:** in `~/.databrickscfg` per person — never in the repo.
- **Integration point:** this GitHub repo. Merge to `main`, pull latest, then
  deploy for the demo.
- **Agent defaults:** coding agents read [CLAUDE.md](CLAUDE.md) for the
  profile/bundle conventions above — keep it in sync if these defaults change.

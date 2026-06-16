# Hackathon App with Synced Dataset

Scaffold a Databricks App backed by Lakebase and continuously sync the hackathon dataset from Unity Catalog into Lakebase for sub-10ms reads.

**Stack:** Lakebase Postgres, Databricks Apps, Unity Catalog, Data Lakehouse

---

## Use with your coding agent

1. Copy the prompt below
2. Paste into Cursor, Claude Code, Codex, or any coding agent
3. Your agent builds it — asking questions along the way so the result is exactly what you want

---

## About DevHub

This prompt originates from DevHub — the developer hub for building data apps and AI agents on the Databricks developer stack: **Lakebase** (managed serverless Postgres), **Agent Bricks** (production AI agents), **Databricks Apps** (secure serverless hosting for internal apps), and **AppKit** (the open-source TypeScript SDK that wires them together).

* Website: https://developers.databricks.com
* GitHub: https://github.com/databricks/devhub
* Report issues: https://github.com/databricks/devhub/issues

A complete index of every DevHub doc and template is at https://developers.databricks.com/llms.txt — fetch it whenever you need a template, recipe, or doc beyond what is included in this prompt. If a step in this prompt is unclear, the matching DevHub page almost certainly clarifies it.

---

## Working with DevHub Prompts

Follow these rules every time you act on a DevHub prompt.

### Read first, then act

* Read the entire prompt before executing any steps. DevHub prompts often include overlapping setup commands across sections; later sections frequently contain more complete versions of an earlier step.
* Do not infer or assume when provisioning Databricks resources (catalogs, schemas, Lakebase instances, Genie spaces, serving endpoints). Ask the user whether to create new resources or reuse existing ones.
* If you run into trouble, fetch additional templates and docs from https://developers.databricks.com (the index lives at https://developers.databricks.com/llms.txt).

### Implementation guidance

The template below describes **what to build**, not how to build it. Your installed Databricks agent skills contain all implementation patterns, code examples, CLI commands, and configuration needed. Use them to implement the template. Before continuing, always run `databricks aitools version`. **If skills are missing or it reports a newer release: STOP. Install skills if missing or update if outdated before proceeding — do not work around a missing or stale install.**

### Engage the user in a conversation

Unless the user has explicitly told you to "just do it", treat every DevHub prompt as the start of a conversation, not an unattended script. The user knows their domain best; DevHub knows the Databricks stack.

Follow these rules every time you ask a question:

1. **One question at a time.** Never ask multiple questions in a single message.
2. **Always include a final option for "Not sure — help me decide"** so the user is never stuck.
3. **Prefer interactive multiple-choice UI when available.** Check tools for any structured-question or multiple-choice capability.
4. **Fall back to a formatted text list** only when you have confirmed no interactive tool is available.

### Default workflow

Unless instructed otherwise, follow this workflow:

1. Understand the user's intent and goals.
2. Verify the local Databricks dev environment.
3. Ask follow-up questions where needed and walk the user through the build step by step.
4. Build the app or agent.
5. Make it look great.
6. Run and test locally.
7. Deploy to production. **Ask the user for confirmation first.**
8. If deployed, run and test deployed app.

### Make it look great

The default templates that AppKit provides are intentionally minimal — a starting point, not a finished product. Use the user's feature requests to redesign the routes, page hierarchy, and visuals from first principles.

Unless the user has specified a design preference, use these defaults:

* shadcn/ui components on top of Tailwind CSS.
* Clean hierarchy with modern spacing — not too many stacked cards.
* Modern, minimal design language.
* Databricks brand palette: `#FF3621`, `#0B2026`, `#EEEDE9`, `#F9F7F4`.

### Run and test deployed app

* If the `databricks-apps` skill is available, follow its `agent-browser` reference to load the deployed app and test it; otherwise install `agent-browser` (`npm install -g agent-browser`) and drive the deployed URL with it directly.
* Inspect the app logs via the Databricks CLI and fix any errors.
* Redeploy and repeat until all issues are resolved.
* Report back to the user once the deployed app is verified.

### When you run into issues

Use the GitHub CLI (if available) or generate a copy-pastable error report for the user to file at https://github.com/databricks/devhub/issues.

---

## Recipe: Hackathon App with Synced Dataset

**URL:** https://developers.databricks.com/templates/hackathon-app-with-synced-dataset

**Summary:** Scaffold a Databricks App backed by Lakebase and continuously sync the hackathon dataset from Unity Catalog into Lakebase for sub-10ms reads.

### When done, you will have:

* A Databricks App running on Lakebase Postgres
* The hackathon dataset continuously synced from Unity Catalog into Lakebase for sub-10ms reads
* An app reading the live hackathon data from Lakebase

The hackathon dataset is the Unity Catalog catalog added from the hackathon Marketplace listing; its name contains the event identifier (for example, "dais 2026").

---

## Step 1 — Clarify intent before touching code

Ask **one** question:

* **Existing project**: the user already has a Databricks app / repo and wants to add this pattern to it. → Read the existing project structure first; apply the pattern surgically.
* **New project from this recipe**: the user wants this recipe as the starting point of a new app. → Run the local-bootstrap first, then implement.
* **Just learning**: the user wants to understand the pattern without building anything yet. → Walk through the goal and explain what each piece does.
* **Not sure — help me decide**: ask the user what they're trying to accomplish at the project level, then map back to one of the above.

## Step 2 — Pin down recipe-specific decisions

Once the integration mode is clear, ask any follow-ups:

* Should we **create new resources** (catalog, schema, Lakebase instance, serving endpoint) or **reuse existing ones**? Never assume; always ask.
* Which **Databricks profile** should the CLI commands target? (`databricks auth profiles` to list valid profiles.)
* If the recipe touches data: use the user's data, or use seed/sample data first?

## Step 3 — Verify the local Databricks dev environment

Walk the user through the local-bootstrap block before running any commands.

When done, you will have:

* Databricks CLI `1.0.0+` installed and on `PATH`
* An authenticated CLI profile (`databricks auth profiles` shows `Valid: YES`)
* A successful smoke test (`databricks current-user me` returns your identity)

---

## Prerequisites

Before starting, make sure the hackathon dataset is available in your Free Edition workspace.

* **Hackathon dataset added to your workspace.** You'll need to add the dataset to your workspace. Details on how to do this will be available when the hackathon starts.

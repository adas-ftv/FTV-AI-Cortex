# CLAUDE.md — FTV AI Cortex

**FTV AI Cortex** is FTV Capital's internal portal that catalogs the prompts, custom
tools, connectors, skills, plug-ins, and workflows the firm uses with Claude (and, where
noted, ChatGPT). The live product is a single self-contained `index.html` served via
GitHub Pages. This file orients any Claude session to the repo so facts don't have to be
re-derived each time.

> **Keep this file current.** Treat updating CLAUDE.md as part of any cortex edit — see
> [Self-maintenance protocol](#self-maintenance-protocol) at the bottom. The
> [Registry inventory](#registry-inventory) is the section most likely to drift.

---

## Repository layout

Three **distinct, unrelated stacks** live in this repo. Know which one you're touching.

| Path | What it is | Status |
|---|---|---|
| `index.html` | **THE live app.** 3,700+ line single-file React 18 + in-browser Babel SPA. No build step. Deployed via GitHub Pages. | Live — primary focus |
| `streamlit_app.py`, `sourcing_dashboard.py` | Separate Streamlit + Snowflake "sourcing dashboard" (Python). Deps in `requirements.txt` / `environment.yml`. | Separate app |
| `ai-cortex/` | Fresh Vite + React 19 scaffold. Intended as an eventual rewrite of `index.html`, but currently **untouched boilerplate** (default counter demo). | Not live — scaffold only |

There is no root `package.json`, no root README, and **no `.github/` CI workflow**.

---

## Working on the cortex (`index.html`)

This is where ~all feature work happens.

- **No build step.** Edit `index.html` directly. To verify, open it in a browser (or
  serve it, e.g. `python3 -m http.server` from the repo root) and confirm the app renders
  and the relevant tab looks right — the in-browser Babel transpiler means a syntax slip
  produces a **blank navy page**, not a build error.
- **Pinned CDN dependencies** (lines ~7–9) — do not bump casually:
  - React 18 (`unpkg.com/react@18/umd/react.production.min.js`)
  - ReactDOM 18 (`unpkg.com/react-dom@18`)
  - **Babel Standalone `7.23.10`** (`unpkg.com/@babel/standalone@7.23.10`) — pinned on
    purpose. The `<script type="text/babel" data-presets="react">` tag (line ~29) forces
    the **classic** JSX runtime (`React.createElement`). If Babel is unpinned or
    `data-presets="react"` is dropped, newer Babel emits the automatic runtime
    (`import { jsx } ...`), which a classic inline script can't use → blank page with
    *"Cannot use import statement outside a module."*
- **Analytics:** Google Analytics 4, measurement id `G-9VW1MVE100` (lines ~11–16).
- **Component model:** one big React component tree defined inside the `text/babel`
  script. Content is data-driven from the registries below; the JSX mostly `.map()`s over
  them.

### How content is rendered
- **Connectors, Custom Tools, and Apps are NOT separate arrays.** They are
  `TOOLS_REGISTRY` entries discriminated by their `type` field and split at render time
  via `useMemo` filters: `fCustomTools` (line ~2804), `fConnectors` (line ~2819,
  `t.type === "Connector"`), `fSkills` (line ~2833, firm-enabled only), `fPlugins`
  (line ~2866). Tab counts derive from these (`customToolsCount`/`connectorsCount`/
  `pluginsCount`, lines ~2884–2893).
- **Downloadable skills are a separate registry, not a `TOOLS_REGISTRY` filter.**
  `DOWNLOAD_SKILLS` is rendered via its own `.map()` in the Skills tab's "Downloadable"
  section, alongside the firm-enabled `SKILLS_REGISTRY` section. The Skills tab count
  (`skillsCount`, line ~2892) is `totalFirmSkillsCount + DOWNLOAD_SKILLS.length` —
  a fixed total independent of active tag/workflow filters (do not swap this back to a
  filtered `.length`, that was a prior bug). `skillCountByWorkflow` (nearby) sums
  firm + downloadable skills per workflow for the Start Here tile labels.
- **Tabs** are declared in the `tabs` array (line ~2911). There are 8:
  `⚡ Start Here` · `📋 Prompt Library` · `🛠️ Custom Tools` · `🔗 Connectors` ·
  `🧠 Skills` · `🔌 Plug-ins` · `🔧 External Tools` · `📖 Claude Guides`.
- **Cross-linking:** an item shows up on the **Start Here** workflow tiles and in a
  workflow's detail view via its `workflowIds`. A shared `workflowItems()` helper unions
  items across `TOOLS_REGISTRY`/`SKILLS_REGISTRY`/`PLUGINS_REGISTRY` in both directions (a
  workflow's `toolIds` **and** each item's own `workflowIds`), so always give a new item
  accurate `workflowIds` or it will be invisible on those pages. Note `DOWNLOAD_SKILLS`
  is **not** included in `workflowItems()` — its workflow tie-in only feeds
  `skillCountByWorkflow` for the Start Here tile's skill count, not the tool count/detail
  list. The Start Here tile count itself is split: `workflowItems(wf).filter(it => it.type
  !== "Skill").length` for tools (avoids double-counting firm skills that `skillCountByWorkflow`
  already covers) plus `skillCountByWorkflow[wf.id]` for skills.

### Common recipe — add a skill
- **Firm-enabled (auto-fires):** append to `SKILLS_REGISTRY` matching the existing shape
  (`id, type:"Skill", name, platform, badge, link, desc, note, tags[], workflowIds[]`).
- **Downloadable (.skill file on SharePoint):** append to `DOWNLOAD_SKILLS` instead —
  lighter shape (`id, name, desc, tags[], workflowIds[], link`), rendered in the same
  Skills tab under its own "Downloadable" section. Verify the SharePoint link resolves
  before shipping (dead `.skill` links have shipped before).
- Either way, give it real `workflowIds`, then bump the relevant count in the
  [Registry inventory](#registry-inventory) below. Same pattern for tools/connectors
  (`TOOLS_REGISTRY`), plug-ins (`PLUGINS_REGISTRY`), external tools (`EXTERNAL_TOOLS`), and
  prompts (`PROMPTS_REGISTRY`).

---

## Registry inventory

All content registries are top-level `const` arrays near the top of `index.html`. **Line
numbers and counts are approximate and drift as the file is edited** — the stable anchor
is the variable name (grep for it). Refresh per the
[Self-maintenance protocol](#self-maintenance-protocol).

| Registry | Line (approx) | Entries | Purpose |
|---|---|---|---|
| `TOOLS_REGISTRY` | ~120 | 17 | Custom Tools + Connectors + Apps + MCP Servers, split by `type` |
| `SKILLS_REGISTRY` | ~297 | 13 | Firm-enabled Claude Skills (auto-fire; excludes downloadables) |
| `DOWNLOAD_SKILLS` | ~430 | 8 | Downloadable `.skill` files (SharePoint), rendered via `.map()` in the Skills tab |
| `PLUGINS_REGISTRY` | ~501 | 7 | Anthropic *Claude for Financial Services* plug-ins |
| `PROMPTS_REGISTRY` | ~570 | 13 | Prompt Library (Deep Research + Due Diligence) |
| `WORKFLOWS` | ~2289 | 7 | Start Here workflows; hold `toolIds`/`promptIds`, accent color |
| `GUIDES` | ~2368 | 6 | Claude Guides tab content |
| `EXTERNAL_TOOLS` | ~2616 | 3 | Third-party tools (QuikIRR, Fellow AI, Encore Compliance) |

**Item shape** (tools/skills/plugins share this):
`id, type, name, platform, badge, link, desc, note, tags[], workflowIds[]`.
`DOWNLOAD_SKILLS` items use a lighter shape: `id, name, desc, tags[], workflowIds[], link`
(no `type`/`platform`/`badge` — those fields are implied by the "Downloadable" section).
`WORKFLOWS` items use `id, icon, label, desc, accent, toolIds[], promptIds[], tip`.
`PROMPTS_REGISTRY` items use numeric `id, category, title, source (SharePoint URL), desc,
labels[], workflowIds[], text` (backtick prompt template).

---

## Babel / blank-page gotchas

Because JSX is transpiled in the browser, these mistakes silently blank the page. Check
them first when the app won't render:

- **No stray/duplicate `{`** in the registries — a lone extra brace (a recurring bug in
  `SKILLS_REGISTRY`) throws `Unexpected token` and kills the whole app.
- **ASCII only in JSX text.** Unicode bullets (`•`) and arrows (`→`) break the Babel
  parse — use `*` / `-` in JSX children (they're fine inside string literals/emoji in the
  tab labels, but avoid them as bare JSX text).
- **Wrap bare ternaries** that render markup in a fragment: `{cond ? <>…</> : null}`.
- **Keep Babel pinned** to `7.23.10` with `data-presets="react"` (see above).

---

## Conventions

- **SharePoint links** for downloadable skills/prompts use the bases `SP_BASE` (line ~57)
  and `SP_LIST` (line ~58). Reuse them rather than hardcoding full URLs; verify a link
  resolves before shipping (dead `.skill` links have shipped before).
- **Theming:** color palette `C` (line ~34), tag styles `TAG` (line ~43), type→style map
  `TYPE_MAP` (line ~50). Reuse these instead of inline hex where possible.
- **Modernist style helpers:** `RADIUS = 0` and `RULE(w)` (line ~40-41). All borders are
  `2px solid`, all borderRadius are `0`. No boxShadow except on floating overlays.
- **Icons:** `Icon` component (line ~70) + `ICON` dictionary (line ~75) provide monochrome
  Lucide-style inline SVG icons. Use `<Icon d={ICON.keyName} size={N} color={C.textSec}/>`
  — never emoji in UI elements. Workflow/guide/tab `icon` fields store string keys into
  `ICON`, not emoji.
- **Typography:** Archivo font loaded from Google Fonts. Font stack is
  `'Archivo',system-ui,sans-serif`.
- **Badges** signal rollout state: `Active`, `Rolling Out`, `Active Pilot`.
- **Workflow naming:** the "Diligence & Analysis" workflow keeps the `id` `cim-diligence`
  for data integrity even though its display label was renamed — change labels, not ids.

---

## Git / branch / deploy workflow

- **Branches:** Claude works on `claude/…`-prefixed branches; open a PR rather than
  pushing to the base/deploy branch directly (a guardrail blocks direct pushes there).
- **GitHub Pages** serves the root `index.html` via **"Deploy from a branch"** (there is
  no Actions workflow file). Merging into the Pages source branch triggers a fresh
  deployment; edits aren't live until then. Pages builds have occasionally gotten stuck
  in `queued` — a trivial nudge commit/PR to the source branch re-triggers a build.
- **Commit signing:** commits are expected to be SSH-signed (unsigned commits show as
  "Unverified" on GitHub).

---

## Streamlit sourcing dashboard (secondary)

- Run: `streamlit run streamlit_app.py` (or `sourcing_dashboard.py`).
- Deps: `requirements.txt` (`streamlit`, `pandas`, `plotly`,
  `snowflake-snowpark-python`) or the conda env `sourcing-dashboard` in `environment.yml`
  (Python 3.10, Snowflake channel).
- Independent of the React app — pulls data from Snowflake via Snowpark.

## `ai-cortex/` Vite scaffold (in progress)

- Setup: `cd ai-cortex && npm install`, then `npm run dev` (Vite dev server),
  `npm run build`, `npm run lint`.
- Currently the **default Vite + React 19 template** (counter demo). No cortex content
  has been migrated. Do **not** treat it as the live app — that's the root `index.html`.

---

## Self-maintenance protocol

This file has no generator script or hook — it stays accurate because each session
updates it as part of editing the cortex. When you change `index.html`:

1. **Registry edits** — if you add, remove, or rename entries in any registry (or add a
   new registry, tab, guide, or workflow), update the [Registry inventory](#registry-inventory)
   table in the **same** change: adjust the affected count, and the approximate line
   number if it shifted materially. Add or remove a row for a new/removed registry.
2. **New gotchas or conventions** — if you hit (and fix) a new blank-page cause or adopt
   a new convention, add a bullet so the next session doesn't rediscover it.
3. **Refresh line numbers** when they've drifted:
   ```
   grep -n "const TOOLS_REGISTRY\|const SKILLS_REGISTRY\|const DOWNLOAD_SKILLS\|const PLUGINS_REGISTRY\|const PROMPTS_REGISTRY\|const WORKFLOWS\|const GUIDES\|const EXTERNAL_TOOLS" index.html
   ```
   To re-count a registry's entries, count its `id:` fields between its opening `[` and
   closing `];`.

Keep it scannable: tables and tight bullets, detailed enough to prevent re-discovery,
short enough not to rot.

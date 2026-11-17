# Libredesk — REA-style Analysis (Phase 1: clone, verify, analyse, plan)

**Date:** 2026-11-16. **Purpose:** Libredesk is the BASE for a hybrid live-chat clone.
Chatwoot's good settings/layout/features are to be ported INTO Libredesk.
No hybrid building was done in this phase.

**Note on method:** the REA skill (`~/workspace/custom-skills/reverse-engineer-anything/SKILL.md`)
says: "For ordinary analysis of a complete source repository, use normal repository
tools and do not run REA readiness or provider commands." This repo is a complete
source repository, so the analysis below is direct source inspection (file counts,
line counts, grep-verified symbols), not a binary decompilation. No REA engine run
was needed or performed.

## 1. Verified repo facts (all checked 2026-11-16, live)

| Fact | Verified value |
|---|---|
| Repo / remote | `https://github.com/abhinavxd/libredesk` (origin fetch + push) — real/original repo, by abhinavxd (team behind Listmonk, Zerodha Tech) |
| Local path | `~/workspace/libredesk` |
| Clone type | Full (non-shallow): `git rev-parse --is-shallow-repository` = `false` |
| Default branch | `main` |
| HEAD commit | `1b6ecc0a5f05d22ee32ebc99efa4f962647be65a` — "Merge pull request #784 from abhinavxd/db-perf", 2026-11-14 19:06:25 +0530 |
| Commits on HEAD | 2,896 |
| Latest stable release | **v2.9.2**, published 2026-10-31 (GitHub API `releases/latest`) |
| Newer pre-release tags | v2.10.0-rc.3 (latest tag by date), v2.9.2-rc.1 — so HEAD is past v2.9.2, on the road to v2.10.0 |
| LICENSE | **GNU AGPL-3.0** (LICENSE file, first line "GNU AFFERO GENERAL PUBLIC LICENSE Version 3"; GitHub API `license.spdx_id` = `AGPL-3.0`). No enterprise/ carve-out, no paid tier. |
| GitHub stars / forks | **3,155 stars, 337 forks**, 15 watchers (GitHub API, live 2026-11-16) |
| Created | 2024-05-12 — young project (~2.5 years old) |
| Open issues | 130 |
| Repo size | GitHub `size` = 12,364 KB; working tree 29 MB; 42,992 objects in pack |
| Go version | go 1.27.3 (`go.mod`) |
| Files (excl. .git) | **1,479** total |
| Go code | **364 files** in `cmd/` + `internal/`, **60,349 lines** (non-test) + 30,052 test lines |
| Frontend | **991 files**, 556 `.vue` + 402 `.js`, **102,038 lines** (Vue + JS) |
| DB tables | **57 `CREATE TABLE`** in `schema.sql` |
| i18n languages | 14 locale files in `i18n/` (en-US, de-DE, fr-FR, es-ES, fa-IR, ja-JP, …) |

## 2. Architecture map (verified in source)

### 2.1 Single-binary build
- Entry: `cmd/main.go` — one Go process serves everything: agent inbox, website
  chat widget, admin panel, HTTP API, WebSocket server.
- Only external services: **PostgreSQL 17** (`postgres:17-alpine`) + **Redis 7**
  (`redis:7-alpine`), per `docker-compose.yml` (3 services: app on :9000, db, redis).
- First run: `./libredesk --install --idempotent-install --yes --config config.toml`
  then `--upgrade --yes`, then serve. Config: `config.toml` (`config.sample.toml`
  documents log level, encryption key, server :9000, session 9h, upload fs/S3,
  local login + OIDC).
- **Go is NOT installed on this VM** (`go: command not found`) — Phase 2 must
  install Go 1.27+ (and Node/pnpm for the frontend build) before building.

### 2.2 Go backend — `cmd/` (HTTP handlers, one file per area)
`main.go, handlers.go, websocket.go, chat.go, conversation.go, messages.go,
inboxes.go, teams.go, tags.go, macro.go, automation.go, sla.go, csat.go,
report.go, search.go, settings.go, roles.go, users.go, webhooks.go,
helpcenter.go, ai.go, aiagent.go, aitools.go, whatsapp_*.go, widget_*.go
(widget_ws.go, widget_campaign*.go, widget_help.go, widget_transcript.go),
business_hours.go, custom_attributes.go, views.go, statuses.go, priorities.go,
activity_log.go, notifications.go, oauth.go, oidc.go, media.go, draft.go …`

### 2.3 Go backend — `internal/` (domain packages, one per concern)
`ai, aiagent, activity_log, attachment, auth, authz, autoassigner, automation,
business_hours, conversation, csat, custom_attribute, helpcenter, inbox
(channel/email, channel/livechat, channel/whatsapp), macro, media, migrations,
notification, oidc, report, role, search, setting, sla, streamqueue, tag,
team, template, user, version, view, webhook, whatsapp, ws, …`
- `internal/inbox/inbox.go` — `Inbox` interface; channels: `email`, `livechat`, `whatsapp`.
- `internal/ws/` — WebSocket server for agents; `cmd/widget_ws.go` — widget
  WebSocket (widgets join by **inbox UUID**, never numeric ID — line 226 comment).
- `internal/search/`, `internal/report/`, `internal/csat/`, `internal/sla/`,
  `internal/macro/`, `internal/automation/`, `internal/webhook/` — all present.

### 2.4 Vue frontend — `frontend/`
- Two apps: `frontend/apps/main/` (agent dashboard + admin) and
  `frontend/apps/widget/` (embeddable chat widget), plus `frontend/shared-ui/`
  (shared components/composables) and `frontend/src/components/` (legacy/shared).
- Main app structure: `apps/main/src/{api, components, composables, constants,
  features, layouts, router, stores, utils, views, websocket.js}`.
  Admin features live under `features/admin/` — incl. `features/admin/ai/`
  (`SnippetForm.vue`, `snippetColumns.js`) and `features/admin/inbox/`
  (`LivechatInboxForm.vue`); admin AI views under `views/admin/ai/`
  (`AISnippets.vue`, `CreateOrEditAssistant.vue`).
- Widget app: `apps/widget/src/{App.vue, api, components, composables, layouts,
  main.js, store, utils, views, websocket.js}` + `ArticleReader.vue` (help
  articles inside the widget).
- Stack: Vue + Tailwind, Vite build, pnpm workspace, Cypress e2e tests.

### 2.5 Inboxes / channels (verified)
- **3 channels only:** live chat, email (IMAP/SMTP, Google/Microsoft OAuth),
  WhatsApp (Meta Cloud API). No Facebook/Instagram/Telegram/SMS/TikTok/LINE.
- Live-chat inbox config (`cmd/inboxes.go`): branding light/dark, theme
  (system/light/dark), session duration, quick replies, pre-chat form
  (`cmd/chat.go` creates visitor contacts + session tokens).
- Multiple inboxes: Admin → Channel → Inboxes; each inbox gets a 2-line
  snippet for the site. One inbox per website = the 5–6 sites plan works.
- Widget: real-time, file uploads, pre-chat form, JWT identity checks (per docs).

### 2.6 Shared inbox / workflow (verified present)
- Teams (`cmd/teams.go`, `internal/team`), tags, custom statuses, custom
  attributes, custom priorities, snoozing, full-text search (`internal/search`).
- **Macros** = saved replies + conversation actions in one step
  (`cmd/macro.go`, `internal/macro`) — this is Libredesk's "canned responses".
- **Automations** — rules on conversation events: tag/assign/route
  (`cmd/automation.go`, `internal/automation` incl. evaluator, time triggers).
- **Auto-assignment** — round-robin / by agent capacity (`internal/autoassigner`).
- **Views** — personal + shared views/filters (`cmd/views.go`, `views` table).
- **SLA** — policies, breach warnings (`cmd/sla.go`, `internal/sla`, `sla_policies`,
  `applied_slas`, `sla_events` tables). **Business hours** (`internal/business_hours`).
- **CSAT + reports** — `cmd/csat.go` (incl. widget CSAT page), `cmd/report.go`
  (overview counts/charts, SLA, CSAT, message volume, tag distribution).
- **Private notes + @mentions** — present: `messages.go` "Send private note",
  `messages_delete.go` (delete own private notes), `conversation_mentions` table,
  `handleGetMentionedConversations`, `cmd/ai.go:401` posts AI summaries as a
  private note. **Typing indicators** — present in code: `internal/conversation/ws.go:150`
  broadcasts typing events to widget clients; `internal/ws/client.go:166` guards
  agent typing broadcasts.
- **Campaigns / proactive messages** — present: `cmd/widget_campaign*.go`
  (campaign handlers, stats, working-hours checks), `internal/inbox/channel/livechat/proactive`.
- **Roles/permissions + SSO** — `cmd/roles.go`, `internal/role`, `internal/authz`,
  `oidc.go`/`oauth.go` (Google/Microsoft/any OIDC), per-action permissions
  (`roles:manage`, `macros:manage`, `automations:manage`, `inboxes:manage`,
  `help_center:manage`, `general_settings:manage` …).
- **Activity logs** (`internal/activity_log`, `activity_logs` table), **API +
  webhooks** (`cmd/webhooks.go` — get/create/update/delete/toggle/test, encrypted),
  **contacts + contact notes** (`contact_notes`, `contact_channel_identities` tables).

### 2.7 Help centre (knowledge base)
- `cmd/helpcenter.go`, `internal/helpcenter`; tables: `help_centers`,
  `article_collections`, `help_articles`, `help_article_feedback`,
  `help_search_queries`. Searchable, multilingual, own theme/logo/CSS/JS,
  custom domain (per docs). Widget can read articles (`ArticleReader.vue`).

### 2.8 AI assistant + copilot (the key part for the hybrid)
- **Admin → AI** settings: `cmd/ai.go` — `GetProviderConfig` / `UpdateProviderConfig` /
  `TestProviderConfig` per provider type (`completion` vs `embedding`).
- **Providers: any OpenAI-compatible endpoint.** `internal/ai/openai.go`:
  "OpenAIClient talks to any OpenAI-compatible API (base URL selects the host)",
  default `https://api.openai.com/v1`. Presets (per Libredesk docs): OpenAI,
  Anthropic, OpenRouter, Groq, Together AI, Ollama; any other endpoint by base URL.
  **No Gemini preset found in the code** — Gemini must be connected via its
  OpenAI-compatible base URL (Phase 4 to verify). One telling trace:
  `internal/ai/openai_test.go:114` mentions "Gemini 3 returns a thought signature
  in extra_content on each tool call" — the client is tested against Gemini-style
  responses.
- **Two providers to configure:** `completion` (drafting, copilot, summaries, tag
  suggestions, assistant responses) and `embedding` (turns snippets, help-centre
  articles, tags into vectors for search). Changing embedding model/dimensions
  re-embeds automatically (per docs).
- **Knowledge base = Snippets + help articles.** `internal/ai/knowledgebase.go`:
  "snippetSource indexes enabled knowledge base snippets"; published help-centre
  articles are searched too when "Allow AI assistants to use this article" is on.
  Tables: `ai_knowledge_base`, `embeddings`, `ai_prompts`, `ai_providers`,
  `ai_tools`, `ai_assistants`, `ai_assistant_tools`, `ai_agent_events`,
  `copilot_messages`, `ai_faq_suggestions`.
- **AI assistant** (`internal/aiagent/` — `aiagent.go`, `worker.go` 915 lines,
  `prompt.go`, `tools.go`, `faq.go`, `citations.go`, `otp.go`): answers live-chat
  questions from the KB, calls your own APIs (tools), **hands off to a human**
  when it cannot help; stats per assistant (`GetAssistantStats`).
  **Agent copilot** (`internal/ai/copilot.go`, `ai.go: Completion/CompletionRaw`):
  drafts replies, summarises conversations, suggests tags, finds answers.
- AI features are labelled **beta** in the docs and need an OpenAI-compatible
  provider (own API cost only — no licence fee, no paid tier).
- **Gemini hook point for Phase 4:** `Admin → AI` → set completion provider base
  URL to Gemini's OpenAI-compatible endpoint + API key + model; set embedding
  provider the same way (or a separate embedding model); load book data as
  Snippets/help articles; the assistant then answers from that KB only.

### 2.9 What is NOT in Libredesk (verified gaps)
- No native mobile app (responsive web only; PWA files exist: `public/manifest.webmanifest`, `sw.js`).
- No Facebook/Instagram/Telegram/SMS/TikTok/LINE channels.
- No dedicated **Live View / visitor-monitoring dashboard** (no page/time-on-site,
  geo, online-users map found; only typing indicators + conversation Live View
  in the sense of ongoing conversations). Treat as **missing** until Phase 2 test.
- No **collision detection** found (no "another agent is replying" warning in code).
- No voice/video calls (no Twilio/Agora/Jitsi integration found).
- No multi-portal help centre per brand (one help centre per instance, per docs).

## 3. Chatwoot features worth porting — status in Libredesk + difficulty

Source: `~/workspace/research_notes/best-free-open-source-live-chat-20261116-0555/report.md`
(Chatwoot 39,951★, v4.19.1, MIT core + `enterprise/` commercial; Rails 7.2 + Vue 3,
Postgres + Redis + Sidekiq) plus the Libredesk source checks above.
Difficulty = effort to add into Libredesk (Go + Vue), single user, 5–6 sites.

| # | Chatwoot feature | In Libredesk? | Difficulty | Notes for this use case |
|---|---|---|---|---|
| 1 | Live View / visitor monitoring (who is on site, pages, time, geo) | **Missing** (typing only) | **Medium** (6–10 h) | Highest-value port for a live-chat feel. Needs: widget heartbeat/page-view events → new WS event + small admin page. No geo DB needed for v1. |
| 2 | Canned responses layout (slash `/` insert in reply box, account-wide list) | **Partially** — Macros exist, but no slash-insert canned-reply picker in the composer | **Easy** (2–4 h) | Add a `/` picker that inserts a macro's reply text. High value for repeated book answers. |
| 3 | Custom views / saved filters layout | **Present** (personal + shared views, `cmd/views.go`) | **Easy** (1–3 h) | Only polish: Chatwoot-style "Mine / Unassigned / All" default folders + saved-filter chips. |
| 4 | Private notes + @mentions | **Present** (private notes, mentions table, mentioned-conversations view) | **Easy** (1–2 h) | Polish only: @-autocomplete in the reply box. Single user — low priority. |
| 5 | Collision detection ("X is replying") | **Missing** | **Medium** (4–6 h) | Needs typing/replying presence per conversation. Single user — low priority, do last. |
| 6 | Campaigns / proactive chat (timed greeting per site) | **Partially** — widget campaigns + proactive messages exist | **Easy** (2–4 h) | Polish: Chatwoot-style per-inbox campaign editor (delay, pages, business-hours check already exists). |
| 7 | Reports / CSAT layout (Chatwoot-style dashboard cards) | **Present** (overview counts/charts, SLA, CSAT, volume, tags) | **Easy** (2–4 h) | Polish only: rearrange into Chatwoot-style cards; no new data needed. |
| 8 | Widget pre-chat form + appearance settings | **Present** (pre-chat form, branding light/dark, theme, session duration, quick replies) | **Easy** (1–3 h) | Polish: per-inbox greeting text, widget colour/position, avatar — most already in `LivechatInboxForm.vue`. |
| 9 | Inbox layout: Mine/Unassigned/All + labels + priority + teams | **Present** (teams, tags, custom statuses, priorities, views) | **Easy** (1–2 h) | Layout polish only. |
| 10 | Auto-assignment by availability/capacity | **Present** (`internal/autoassigner`) | — (0 h) | Single user — nothing to port. |
| 11 | Help centre multi-portal per brand/site | **Missing** (one help centre) | **Hard** (10–16 h) | For 5–6 book sites, one portal with per-site collections may be enough — do NOT build multi-portal in v1; use collections + per-site assistants instead. |
| 12 | Native mobile apps (iOS/Android) | **Missing** (PWA only) | **Hard** (out of scope) | Skip. Responsive web + PWA is enough for one user. |
| 13 | Extra channels (FB/Instagram/Telegram/SMS) | **Missing** (email/chat/WhatsApp only) | **Hard** (out of scope) | Skip — his sites need website chat only. |
| 14 | Captain AI / voice / SSO / SLA (Chatwoot paid) | **Present in Libredesk, free** (AI, SSO, SLA all in AGPL code) | — (0 h) | This is the whole point of the hybrid: no port needed. |

**Port priority for Phase 3 (single user, book Q&A):** 1 Live View, 2 canned-reply `/` picker,
6 campaigns polish, 7 reports layout, 8 widget appearance — then 3/4/9 polish.
Skip in v1: 5 collision, 11 multi-portal, 12 mobile apps, 13 extra channels.

## 4. Hybrid plan (what Phase 2–4 will do)

- **Base:** Libredesk as cloned here (`main`, past v2.9.2). Keep its Go+Vue code,
  its AI, its AGPL licence (any distributed/modified version stays AGPL-3.0).
- **Ported in:** Chatwoot-style layout/settings from the table above (priority order).
- **AI:** Libredesk's own AI (assistant + copilot), provider pointed at Gemini
  (OpenAI-compatible base URL) in Phase 4; book catalogue loaded as
  Snippets/help-centre articles so answers come from the site's own books.
- **Not ported:** Chatwoot code itself — different stack (Rails vs Go), so
  features are **rebuilt in Libredesk's idiom**, not copied file-for-file.
  Chatwoot's Captain AI is NOT ported (it is enterprise/paid code); Libredesk's
  AI replaces it.

## 5. Time estimates for next phases (ESTIMATES, ranges in hours — not promises)

| Phase | Work | Estimate |
|---|---|---|
| Phase 2 | Build/run Libredesk locally, test widget + AI | **4–8 h** |
| Phase 3 | Port Chatwoot-style features (priority list §3) | **20–40 h** (Live View 6–10 h; canned `/` picker 2–4 h; campaigns/reports/widget polish 6–12 h; views/notes/layout polish 4–8 h; testing/fixes 4–8 h) |
| Phase 4 | Connect Gemini for book Q&A, test on the books site | **6–12 h** (provider config + embedding check 1–2 h; book catalogue → snippets/articles 2–4 h; prompts + per-site assistant + handoff rules 2–3 h; live test on Premium Books Library + fixes 2–4 h) |
| **Total (Phases 2–4)** | | **≈ 30–60 h** |

Caveats: Go 1.27+ and Node/pnpm are not yet installed on this VM; first build may
take longer. Estimates assume no major upstream breakage and one site tested first,
then the other 4–5 sites (each extra site ≈ 30–60 min: new inbox + snippet set).

# Libredesk Phase 3 Report — Chatwoot-style features ported into Libredesk

**Date:** 2026-11-16. **Base:** Libredesk `abhinavxd/libredesk`, HEAD `1b6ecc0a` (v2.9.2), AGPL-3.0.
**Scope:** port Chatwoot-style features INTO Libredesk (Go + Vue) in `~/workspace/libredesk` only.
No Chatwoot code copied file-for-file (different stack: Rails vs Go) — every feature was
rebuilt in Libredesk's Go/Vue idiom. AI provider config was **not** touched (no Gemini key yet —
Phase 4). Skipped per brief: collision detection, multi-portal help centre, native mobile
apps, extra channels (FB/Instagram/Telegram/SMS).

**Status: COMPLETE (features 1–4 built, feature 5 verified-present).**
Server running at http://localhost:9000 (VM-local only, not a public link), new binary
`v2.10.0-rc.3 (#1b6ecc0a 2026-11-16T07:47:19+0000)`, PID 12510 at end of phase.
**Tests: 36/36 pass** (`~/workspace/libredesk/phase-2-test.py`, results in
`phase-2-test-results.json`). Phase 2 had 29/29; this phase added 8 new steps (Live View ×6,
macro-picker data path ×2) and all previous steps still pass.
**Time spent: ~1.5 hours** (within the 20–40h Phase 3 estimate).

## 1. Live View / visitor monitoring — BUILT ✅
Chatwoot-style "who is on the site right now" page.

**Backend (new `cmd/liveview.go`, ~200 lines):**
- In-memory registry only — no DB migration, no geo lookup in v1. A visitor is
  registered on widget WS join, its page is updated on every `page_visit`, its
  last-seen time is refreshed on every `ping` (widget pings every 10s); entries with
  no heartbeat for 60s are pruned, and closing the tab removes the visitor at once.
- `GET /api/v1/live-view` (agent permission `conversations:read`) returns online
  visitors, newest first: name, email, inbox (id/uuid/name), current URL/title,
  `first_seen`/`last_seen`, `seconds_on_site`, and the UUID of the visitor's latest
  open conversation (one cheap query each) so an agent can jump straight into the chat.
- Route added in `cmd/handlers.go`.

**Hooks (`cmd/widget_ws.go`):** `handleInboxJoin` now also returns the inbox numeric ID
and name; `liveViewTrackJoin` on join, `liveViewTrackPing` on ping,
`liveViewTrackPage` on page_visit, `liveViewTrackLeave` on disconnect.

**Frontend:**
- New view `frontend/apps/main/src/views/liveview/LiveView.vue`: green "Visitors online"
  badge, table (Visitor / Site / Current page / Time on site / Open chat → routes to
  `/inboxes/all/conversation/<uuid>`), polls every 10s (paused while the tab is hidden),
  time-on-site ticks every second from `first_seen`.
- Route `/live-view` in `frontend/apps/main/src/router/index.js`; sidebar nav entry
  (Eye icon, `conversations:read`) in `PrimaryNavItems.vue`; `api.getLiveView` in
  `frontend/apps/main/src/api/index.js`; 9 `liveView.*` keys in `i18n/en-US.json`
  (verified served live from `/api/v1/lang/en-US`).

**Tests (new, in `phase-2-test.py`):** unauthenticated `GET /api/v1/live-view` → 401;
empty list before any join; a minimal stdlib-only WebSocket client joins the widget
with the visitor token, receives `joined`, sends a `page_visit`, and the visitor then
appears in Live View with the right page URL and linked conversation UUID; after the
WS closes the visitor is gone. **All 6 pass.**
- Test bug found and fixed during the phase: the WS client kept the HTTP handshake
  bytes in its read buffer, so its first "frame" was the literal `HT` of the response.
  The server-side join had actually worked (log: "widget client joined live chat").

**Known limits (documented in code):** registry is per-process and in-memory (lost on
server restart; a visitor with two tabs open counts once per connection, kept alive
while at least one tab is connected); no geo/city lookup in v1.

## 2. Canned-reply `/` picker — BUILT ✅
Type `/` in the reply composer → a dropdown of macros (canned replies); pick one and
its reply text is inserted at the cursor, surrounding text preserved.

- New `frontend/apps/main/src/components/editor/macroSuggestion.js` (char `/`, spaces
  allowed) and `MacroList.vue` (modelled on `MentionList.vue`: same keyboard nav,
  same popup positioning; each row shows the macro name + Reply/Actions hint).
- New `MacroMention` extension (`Mention.extend`, own name so it stays separate from
  the `@` mention) registered in `buildConversationExtensions`
  (`editorExtensions.js`). Its suggestion `command` deletes the typed `/query` range
  and inserts the macro's reply text at the cursor — no mention node is ever inserted.
- Threaded through `useTextEditor.js` → `ConversationEditor.vue` (new props
  `enableMacroSuggestions` / `getMacroSuggestions` / `onMacroSelected`).
- `ReplyBoxContent.vue`: enabled for replies only (`messageType === 'reply'` — the
  send path applies macro actions only for the reply context); `getMacroSuggestions`
  uses the existing `macroStore.searchMacros` (already scoped to the "replying" view)
  and `onMacroSelected` fetches content via `macroStore.fetchMacroContent` and records
  the macro (id + actions, **without** `message_content`) on the conversation — exactly
  like the palette picker, but without triggering ReplyBox's watcher that would replace
  the whole draft with the macro text.
- Discovery: composer placeholder hint now ends "Type / for a canned reply."
  (`editor.hint.full` in `i18n/en-US.json`).

**Tests (new):** `GET /api/v1/macros/search?q=Book&view=replying` finds "Book greeting";
`GET /api/v1/macros/<id>` returns its message content. **Both pass.** The picker UI
itself (dropdown, keyboard nav, cursor insert) is verified by the production frontend
build only — see "Not verified" below.

## 3. Campaigns polish — VERIFIED PRESENT ✅ (no code change needed)
The per-inbox campaign editor already has everything Chatwoot-style: per-campaign
enabled toggle, `delay_seconds`, `include_urls`/`exclude_urls`, audience selection,
per-inbox `campaign_cooldown` (Go-duration validated), and business-hours selection
(`WidgetCampaigns.vue`, used by `LivechatInboxForm.vue`). Verified by reading the
component; no build was needed. If a gap is found in live use, it is a small polish
job, not a build.

## 4. Reports/CSAT layout polish — BUILT (small) ✅
`OverviewView.vue` already had Chatwoot-style cards (Open Conversations, Agent Status,
CSAT, Message Volume, SLA, tags). Added one genuine card to row 1: **"Visitors online"**
fed by the new Live View endpoint, with a link to the Live View page. It refreshes with
the other card stats; a failure is silent so the overview never breaks for agents
without `conversations:read`. No new data or endpoint was needed beyond feature 1.

## 5. Widget appearance / pre-chat + views/notes/layout — VERIFIED PRESENT ✅
- **Widget appearance:** `LivechatInboxForm.vue` already has a full branding section
  (logo, primary colour with contrast warning, home-screen background type/colour/
  gradient/image, fade) and a launcher section (logo, spacing, position), plus
  `config.greeting_message`. No change needed.
- **Views:** Mine / Unassigned / All / Mentioned already exist as
  `/inboxes/:type(assigned|unassigned|all|mentioned)` routes.
- **Notes:** `@`-mentions with autocomplete already exist for private notes
  (`enableMentions` + `getSuggestions` in the composer).

## Files changed
- New: `cmd/liveview.go`; `frontend/apps/main/src/components/editor/macroSuggestion.js`;
  `frontend/apps/main/src/components/editor/MacroList.vue`;
  `frontend/apps/main/src/views/liveview/LiveView.vue`.
- Modified: `cmd/handlers.go`, `cmd/widget_ws.go`, `i18n/en-US.json`,
  `frontend/apps/main/src/api/index.js`, `frontend/apps/main/src/router/index.js`,
  `frontend/apps/main/src/components/editor/editorExtensions.js`,
  `frontend/apps/main/src/components/editor/useTextEditor.js`,
  `frontend/apps/main/src/components/editor/ConversationEditor.vue`,
  `frontend/apps/main/src/components/sidebar/PrimaryNavItems.vue`,
  `frontend/apps/main/src/features/conversation/ReplyBoxContent.vue`,
  `frontend/apps/main/src/views/reports/OverviewView.vue`,
  `phase-2-test.py` (8 new steps + stdlib WS client).
- Rebuilt: frontend `pnpm build:main` (exit 0, 57s; Live View chunk
  `LiveView-D7XtHCna.js` and `MacroList-EpvW4h5V.js` present; picker wiring
  `getMacroSuggestions`/`onMacroSelected`/`enableMacroSuggestions` and `char:"/"`
  present in the built chunks); Go binary rebuilt + re-stuffed
  (`stuffbin`, 40.9 MB); server restarted detached (`setsid nohup`, PID 12510).
  `go vet ./cmd/` clean.

## Test results (exact evidence)
- `python3 phase-2-test.py` → **36/36 steps passed** (run 2026-11-16 ~07:49 UTC).
  New steps all PASS: `live-view requires auth` (401), `live-view empty before any
  visitor joins` (200, `data: []`), `live-view: widget WS join acknowledged`
  (`{'type': 'joined', ...}`), `live-view: visitor listed after WS join` (visitors=1),
  `live-view: visitor page + conversation linked`
  (url=`https://premium-books-library.pages.dev/books/tafseer`, conversation UUID
  matched), `live-view: visitor gone after WS close` (visitors=0),
  `macro search finds 'Book greeting' (slash-picker data)`, `macro content fetchable
  for slash-picker insert` (len=84). All 28 pre-existing steps still pass.
  (One run during the phase showed 33/34 with the WS join failing — that was the
  test-client handshake-buffer bug above, not a server bug; fixed and re-run green.)
- `go vet ./cmd/` → clean. `pnpm build:main` → exit 0.

## Not completed / not verified
- **Visual check of the new pages not done:** the Live View page, the `/` picker
  dropdown and the Overview "Visitors online" card were verified only through the
  production build (chunks + strings present) and API tests. No browser/screenshot
  check was possible from this VM session — the user should open
  http://localhost:9000 (VM-local) and confirm the pages render, and try `/` in a
  reply. Same standing limitation as Phase 2 (dashboard visuals, live WebSocket push
  to agents, email/WhatsApp, AI reply).
- **Campaigns and feature 5 needed no code** (verified present, §3/§5) — if the user
  finds a specific gap in live use, name it and it will be built then.
- **Phase 4 not started** (needs user go-ahead + Gemini API key).

## Reboot / restart reminder (from Phase 2, still true)
Nothing in this local setup survives a VM reboot except files under `~`. After a
reboot: recreate the Postgres `libredesk` role + database, restart Postgres/Redis,
re-run `--install` + `--upgrade` if needed, reset the System password, and restart
the server detached — commands in `phase-2-report.md` §3. The binary and frontend
under `~/workspace/libredesk` survive (they are files, not DB state).

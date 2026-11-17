# Libredesk Phase 4 Report — Gemini book Q&A (multi-site design)

Date: 2026-11-16. Status: **complete and tested end to end.**
Server: http://localhost:9000 (VM-local only — no public link).
Gemini proxy: http://127.0.0.1:18080 (healthy).

## 1. What was delivered

- Libredesk's AI is connected to the user's Gemini API through a local
  forwarding proxy, so the real key never appears in any file, log,
  command argument or Libredesk config.
- One shared AI assistant, **"Premium Books Assistant"** (id 1, user id 3),
  answers visitors' book questions from the knowledge base and gives,
  for every book it names: **title, author, category, site name, and the
  book Link** (exactly as in the KB entry, never invented).
- Knowledge base: **1,200 real books** from the live Premium Books Library
  catalogue, loaded as **37 help-centre articles (one per category)**,
  all embedded and searchable. Snippets: 0.
- Multi-site design: one Libredesk **inbox per website**, all sharing the
  same assistant and the same KB. Premium Books Library is inbox 1
  (UUID `4ff24cff-ecbc-488b-8dc8-c69197e975cd`). **The other three book
  websites are still missing — their names/URLs were not supplied yet —
  so their inboxes and catalogues are NOT in the system. Do not invent
  them.** When the user supplies them, each gets an inbox + its catalogue
  loaded the same way (`phase-4-kb-load.py` has a `SITES` list for this).
- Phases 2 and 3 were re-verified as part of this phase (36/36 tests,
  Live View page/API, `/` picker, server setup). One real Phase 3 defect
  was found and fixed: the Live View page had no server route (§7).

## 2. Gemini proxy (the key never leaves the vault)

- File: `~/workspace/libredesk/gemini-proxy.py` (Python stdlib,
  `ThreadingHTTPServer`, binds 127.0.0.1:18080).
  Control script: `~/workspace/libredesk/phase-4-proxy.sh`
  (`start` / `stop` / `status`; pidfile `phase-4-proxy.pid`,
  log `phase-4-proxy.log`).
- Forwards `GET /v1/models`, `POST /v1/chat/completions`,
  `POST /v1/embeddings` to
  `https://generativelanguage.googleapis.com/v1beta/openai`.
  It drops Libredesk's dummy Authorization header and applies the real
  key only on the approved egress request via the
  dynamic-credentials surrogate helper
  (`add_surrogate_to_request(req, "custom.gemini",
  allowed_hosts=["generativelanguage.googleapis.com"])`).
  Refuses redirects. Logs only method/path/status/size — never headers
  or bodies.
- Libredesk is configured with base URL `http://localhost:18080/v1`.
  The `/v1` prefix is required because Libredesk appends
  `/chat/completions` and `/embeddings` to the base URL; the proxy
  strips the `/v1` prefix when forwarding upstream.
- Verified with curl chat completions through the proxy (no key in the
  command) and by the AI tests in §6.

## 3. AI configuration (set via Libredesk API, tested 200)

- Completion provider: `openai`, base URL `http://localhost:18080/v1`,
  api_key = dummy placeholder (stored encrypted in Libredesk; the proxy
  drops it), model **`gemini-3-flash-preview`**, max_tokens 1024.
- Embedding provider: `openai`, same base URL, model
  **`gemini-embedding-2`**, dimensions 768, embedding_max_tokens 2048.
- Assistant "Premium Books Assistant" (id 1, user_id 3): tone friendly,
  response_length balanced, max_turns 10, citations + handoff enabled.
- Instructions (summary): answer book questions only from the knowledge
  base; for every book named give title, author, category, site name and
  the Link exactly as given in the KB entry; never invent a title, author
  or link; if no book matches, say so plainly; answer in the visitor's
  language. Setup script: `phase-4-setup.py` (idempotent; reads the test
  login password at runtime from `phase-2-test.py`, writes no new copy;
  state in `phase-4-state.json`). Instruction update script:
  `phase-4-update-instructions.py`.
- Model substitutions (verified against the key's model list):
  `gemini-2.5-flash` is listed by `/v1/models` but completions are
  rejected 404 ("This model models/gemini-2.5-flash is no longer
  available to new users") — hence `gemini-3-flash-preview`.
  `text-embedding-004` is NOT in this key's model list (64 models) —
  hence `gemini-embedding-001` first, then `gemini-embedding-2` (§4).

## 4. Knowledge base — source, counts, and the snippet → article migration

- Source: live catalogue fetched from
  https://premium-books-library.pages.dev/json/search-index.json —
  **14,779 entries** (snapshot `phase-4-books.json`). Fields:
  `n`=id, `t`=title, `a`=author, `c`=category slug, `ce`=category name,
  `d`=Google Drive link. **The book's link IS the Drive link (`d`)** —
  the site links each book out to Drive; no per-book detail-page URL
  pattern was found in the site's JS bundle.
- Loaded: **1,200 books** (stratified round-robin across 37 categories,
  ~32 per category), each entry in the format
  `Book / Author / Category / Site: Premium Books Library
  (https://premium-books-library.pages.dev) / Link: <drive url>`.
  Loader: `phase-4-kb-load.py` (0 failed). Reformat script:
  `phase-4-kb-reformat.py`.
- First loaded as 1,200 individual Snippets, then **migrated to 37
  per-category help-centre articles** (`phase-4-kb-articles.py`;
  collection "Books", help centre id 1, collection id 1, published,
  `ai_enabled: true`, `locale: "en-US"`). All 1,200 snippets deleted
  (snippets now 0). Counts in `phase-4-kb-articles.json`.
- Why the migration: Libredesk embeds one API request per snippet.
  The Gemini free-tier quota for `gemini-embedding-001` is
  **1,000 requests/day per model** — exhausted after 845/1,200 snippets
  had embedded ("Please retry in 21h50m", ~10:09 UTC 2026-11-16).
  Articles chunk at up to 2000 tokens, so the whole KB needs ~37
  embedding requests instead of 1,200.
- Embedding model switched to `gemini-embedding-2` (100 requests/minute
  limit, no daily exhaustion observed).
- **Embedding storm and fix (2026-11-16 ~10:14–10:16 UTC):** after the
  articles were created, the reconcile loop kept retrying while ~1,200
  stale background embed jobs (enqueued by the earlier snippet PUTs,
  items captured by value before deletion, carrying both the old and
  new embedding models) were still draining — ~340–390 embedding
  requests/minute hit the proxy, mostly 429s, and no article finished
  embedding (1/38 had a fingerprint). Fix: **restarted the Libredesk
  server** (in-memory job queue cleared; reconcile then retried only
  the 38 existing articles, a ~40-request burst inside the 100/min
  budget). After the restart: **38/38 articles embedded**. Current
  count: 42 help articles, all 42 embedded (the extra 4 are duplicate
  "How to find a book by name or type" articles created by repeated
  runs of `phase-2-test.py`; harmless test artefacts).
- Total proxy traffic today: ~5,990 embedding POSTs (mostly the storm
  and the 1,200-snippet load).

## 5. Tests — Phase 4 (`phase-4-test.py`, results `phase-4-test-results.json`, replies `phase-4-ai-replies.json`)

12/13 steps passed on the first run; the one failure was a transient
Gemini 429 on the no-match preview, which **passed on retry** (see
below). Verbatim replies:

- **By name** — "I am looking for the book The 5 AM Club":
  > "Yes, we have **The 5 AM Club** by **Robin Sharma**. It is in the
  > **Self-Help, Success & Psychology** category from **Premium Books
  > Library**, and you can find it at this link:
  > https://drive.google.com/file/d/1A2abuW9dS8VqeEQBdEa1LRDXfXefGIBq/view"
- **By category** — "Can you suggest a history book": three real books
  with author, category, site and Drive link, e.g. **The Fourth Turning:
  An American Prophecy** by William Strauss and Neil Howe.
- **No match** — "Do you have the book Tafseer Ibn Kathir?":
  > "That book is not in the library. Would you like me to help you find
  > a similar book on Islamic history or Quranic studies?"
  No title, author or link invented. (First run of this preview got a
  429 rate-limit from Gemini and was retried after 60s — passed.)
  Honest note: **"Tafseer Ibn Kathir" is NOT in the live catalogue**
  (0 hits for any spelling/Urdu variant) — the Phase 2 human-agent
  reply claiming it existed was scripted test fiction.
- **Urdu** — "مجھے زیرو پوائنٹ کتاب چاہیے": Urdu reply listing
  **زیرو پوائنٹ ۱** and **زیرو پوائنٹ (جلد ۲)** by جاوید چوہدری with
  category, site and Drive links. (One earlier run of this preview
  omitted the links — LLM non-determinism; the instructions require
  links on every book, but compliance is not guaranteed on every reply.
  Re-run passed with links.)
- **Widget end to end** — visitor asked for "The 5 AM Club" in the
  Premium Books Library inbox; conversation assigned to the AI
  assistant user (id 3); the assistant replied in the live conversation:
  > "Walaikum Assalam! I'm happy to help you find that book. The 5 AM
  > Club by Robin Sharma is available in the Self-Help, Success &
  > Psychology category on the Premium Books Library site. You can
  > access it here: https://drive.google.com/file/d/1A2abuW9dS8VqeEQBdEa1LRDXfXefGIBq/view"
  (plus the worker's "Did that help you find the book?" follow-up).
  Note: assistant replies arrive with `sender_type: "agent"`, and the
  messages endpoint returns `{"results": [...], "total": ...}` — the
  first version of `phase-4-test.py` assumed a plain list and crashed
  on this; fixed in the final script.

## 6. Phases 2–3 re-verification (per the user's correction)

- `phase-2-test.py`: **36/36 steps passed**, run twice — before and
  after the server rebuild in §7. Covers login, root page, inboxes,
  Live View API + widget WebSocket join/list/gone, widget conversation,
  agent reply, macro creation + slash-picker search, help centre,
  article create/read, AI config pages (completion + embedding, proxy
  base URL and models, api_key masked), assistants list, snippets empty.
  (The summary's "37/37" for the post-reboot run was a miscount; the
  script has 36 steps and all pass.)
- Live View page: `LiveView-*.js` chunk exists in
  `frontend/dist/main/assets/`; sidebar links to it; router defines
  `/live-view`; Reports Overview card uses i18n key
  `liveView.visitorsOnline` (source `OverviewView.vue`).
- `/` picker: `MacroList-*.js` chunk exists and `char:"/"` is present in
  the built bundle; macro search + content fetch pass in the test suite.
- Server + proxy: Libredesk up at http://localhost:9000 (root 200),
  proxy `/healthz` ok, Postgres 16 + Redis 7 running.

## 7. Defect found and fixed during re-verification — Live View page 404

- The Vue router defines `/live-view` and the sidebar links to it, but
  the Go server registered SPA routes only for `/`, `/inboxes/*`,
  `/teams/*`, `/views/*`, `/admin/*`, `/contacts/*`, `/reports/*`,
  `/account/*`, `/reset-password`, `/set-password`. A direct visit or
  refresh of `/live-view` returned **404 "Route not found"** (in-app
  navigation from the sidebar worked, which is why Phase 3 testing
  missed it).
- Fix: added `g.GET("/live-view/{all:*}", authPage(serveIndexPage))`
  in `cmd/handlers.go` (line 430), rebuilt the server with
  `go build -o libredesk cmd/*.go` (Go 1.27.3) and restarted it.
  Verified: authenticated `GET /live-view` → **200** (SPA index);
  unauthenticated → redirect to login (301/302, as for the other SPA
  routes); `GET /api/v1/live-view` → 200.
- Build trap recorded: the first rebuild attempt silently failed —
  `go build ... | head` masked the real exit code, and the link step
  failed with "text file busy" because the old server was still running
  the binary. The binary's timestamp (07:47) exposed it. Correct
  procedure: **stop the server first, build without a pipe, check the
  exit code and the new timestamp**, then restart. New binary:
  51,312,711 bytes, 2026-11-16 10:27 UTC (was 40,947,898 bytes, 07:47).
- No other top-level Vue route is missing from the server: `/`, `/contacts`,
  `/reports`, `/inboxes`, `/account`, `/admin`, `/reset-password`,
  `/set-password` are all registered. No Phase 1–3 features were changed.

## 8. Failures and limits, honestly recorded

- `gemini-2.5-flash` completions rejected 404 ("no longer available to
  new users") — using `gemini-3-flash-preview`.
- `text-embedding-004` not in this key's model list — using
  `gemini-embedding-2`.
- `gemini-embedding-001` daily quota (1,000/day) exhausted mid-load —
  forced the snippet → article migration and the model switch.
- Embedding storm after the migration (~340–390 req/min, mostly 429s)
  from stale background embed jobs — fixed by server restart (§4).
- One Gemini 429 on a preview call (retried, passed); free-tier
  per-minute limits can still bite on bursts of chat completions.
- Urdu preview once omitted the book links (LLM non-determinism);
  re-run passed.
- Two VM reboots earlier in the day wiped Postgres/Redis (only
  `~/workspace` survives); recovery is documented in
  `phase-2-report.md` §3. **Nothing in this local setup survives a
  reboot except files under `~`** — after any reboot the database must
  be recreated and the services restarted.
- Not verified: visual browser check of the Live View page and the `/`
  dropdown (API + bundle checks only); live WebSocket push to a real
  browser; email/WhatsApp channels; AI reply under real visitor load.

## 9. Files

- `gemini-proxy.py`, `phase-4-proxy.sh`, `phase-4-proxy.pid`,
  `phase-4-proxy.log` — proxy + control.
- `phase-4-setup.py`, `phase-4-state.json` — AI config + assistant.
- `phase-4-kb-load.py`, `phase-4-kb-reformat.py`,
  `phase-4-kb-articles.py`, `phase-4-update-instructions.py` — KB.
- `phase-4-books.json` (14,779-entry catalogue snapshot),
  `phase-4-kb.json`, `phase-4-kb-articles.json` — data.
- `phase-4-test.py`, `phase-4-test-results.json`,
  `phase-4-ai-replies.json` — tests + verbatim replies.
- This report: `phase-4-report.md`.
- Changed in this phase: `cmd/handlers.go` (one route added) and the
  rebuilt `./libredesk` binary.

## 10. Time spent

Phase 4 overall: about 2 hours of active work across the morning of
2026-11-16 (proxy + AI config + KB load + migration + tests), plus
waiting time for Gemini quota windows and the reconcile loop, and
~45 minutes in the final stretch (embedding-storm fix, end-to-end
tests, Phase 2/3 re-verification, Live View route fix + rebuild).
The user's correction stands: careful re-checking took longer than the
original 6–12h estimate implied for the whole phase, and quality was
put ahead of speed.

## 11. Items awaiting the user's decision / input

1. **Names and URLs of the other three book websites** — needed to
   create their inboxes and load their catalogues into the one combined
   system. (The Premium Books site's footer links to other sites he
   owns, but those were NOT confirmed as the four book websites, so
   they are not used here.)
2. Whether to publish this Libredesk setup anywhere public — it
   currently runs only on this VM at http://localhost:9000.
3. Nothing else is blocked: the Premium Books Library inbox, assistant
   and KB are live and tested.

## 12. Phase 4h — the user's two chatbot suggestions (2026-11-17)

Implemented on the user's direct order (no longer deferred): the shared
assistant already covered all 129,230 books across the four sites; these
two suggestions build on that. Work done 2026-11-17 ~16:00–16:20 PKT.
Scripts: `phase-4h-update-instructions.py`, `phase-4h-test.py`,
`phase-4h-test-retry.py`. Results: `phase-4h-test-results.json`,
`phase-4h-ai-replies.json`, `phase-4h-test-retry-results.json`,
`phase-4h-ai-replies-retry.json`.

### Suggestion 1 — Premium paywall (implemented in instructions)
- **Rule added** (completion instructions + assistant instructions +
  guardrails, assistant "Premium Books Assistant" id 1): Premium Books
  Library is a paid library. For a Premium book the assistant must NOT
  give the direct Drive link from the KB entry. It must give the Premium
  entry link `https://premium-books-library.pages.dev`, name the exact
  book title and author, and tell the visitor to open the link, complete
  the access step first (pay on WhatsApp and enter the access code —
  monthly Rs 100 for 30 days, yearly Rs 500 for 365 days, lifetime
  Rs 1,000), then search the site for the book title. The entry link
  leads to the access/pay box first, not straight to the book.
- **Entry URL — honest caveat:** the Premium site has no per-book pages
  (verified in Phase 4f: no `/books/` or detail route in its JS bundle),
  and no separate `/access` route could be verified in this session —
  the live homepage fetch failed (JS SPA, no extractable content) and
  web search found no access route. The instruction therefore uses the
  site homepage as the entry link (the site's front door, where the
  access box is shown to a visitor without a code, per the user's own
  description of the flow). If the owner confirms a different entry URL,
  it is a one-line change in `phase-4h-update-instructions.py`.
- **Reverse direction unchanged:** a book on another site still gets
  that site's direct Link from the KB entry (Best Selling → Open
  Library ISBN link; Unread → Goodreads/WorldCat link; Urdu Free →
  archive.org `details_url`).

### Suggestion 2 — book requests (implemented in instructions)
- **Rule added:** if no book in any of the four catalogues matches, the
  assistant says plainly that the book is not in the library AND offers
  2–3 in-chat options: (1) send a request for this book so it can be
  added to the website, (2) suggest a similar book from the library,
  (3) nothing more for now. If the visitor confirms the request, the
  assistant asks for the exact title and author and confirms the request
  is noted in this conversation for the library team.
- **What the platform supports, honestly:** Libredesk has no native
  book-request button or ticket field, so the offer works through the
  conversation itself — the options are text the visitor replies to,
  and the confirmed request lives in the conversation for the team to
  see in the inbox. No automatic ticket, tag or WhatsApp message is
  created. (No WhatsApp number for requests was supplied, so none was
  invented.)

### What was verified
- The new instructions were written to the server (PUT completion
  config 200, PUT assistant 200) and **read back and verified stored**
  — completion instructions contain "PREMIUM BOOKS RULE" and "BOOK
  REQUEST RULE"; assistant instructions contain the Premium exception
  and guardrails contain the entry link. (First verification attempt
  failed only because it read `data.config.instructions` while the API
  returns `data.instructions`; fixed and re-verified True/True.)
- KB state at the time: 129,230 books / 258 articles, **76/258 embedded**.

### Tests — BLOCKED by the Gemini embedding quota, not by the changes
- **Run 1** (`phase-4h-test.py`): **4/9 passed** — login, inbox found,
  widget conversation created, assigned to assistant. All 4 book
  previews failed: the Premium preview got the assistant's error
  fallback ("couldn't complete your request"), the other three got
  HTTP 429 "The AI provider is rate limiting requests". The widget AI
  reply never arrived in 120 s.
- **Retry** (`phase-4h-test-retry.py`, 90 s cooldown, previews spaced
  75 s apart, widget polled 180 s): **5/10 passed** (same 4 infra
  steps + conversation-UUID step). All 4 previews failed again with
  HTTP 429; no widget AI reply in 180 s.
- **Cause confirmed in the proxy log:** a stream of
  `POST /v1/embeddings 429` (30,244 total 429s in the log) — the
  reconcile loop is retrying every second against the exhausted daily
  embedding quota, so each assistant query's embedding is also
  rejected. The quota window ends ~13:00 PKT tomorrow (2026-11-18),
  per the 13:15 verification. **Nothing was invented in any reply,
  and no test is claimed as passed that was not.**
- **Remaining:** re-run `phase-4h-test-retry.py` after the quota reset
  (~13:00 PKT 2026-11-18) so the four book answers can be verified
  verbatim — Premium entry link with no Drive link, cross-site links
  both directions, and the no-match request offer. No new schedule was
  created for this; the decision is the user's.

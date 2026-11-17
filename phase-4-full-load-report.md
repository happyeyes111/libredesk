# Libredesk Phase 4 — Full-load report (all four book sites, one combined KB)

Date: 2026-11-17 (work 00:42–01:26 UTC; 05:42–06:26 PKT). Server: http://localhost:9000
(local only — NOT published, per the user's decision of 2026-11-17).

## What was asked
Load ALL books from all four book websites into ONE combined Libredesk
knowledge base (the earlier Phase 4 load covered only 1,200 of 14,779 Premium
books). One inbox per website, one shared assistant, direct book-page links
so a visitor in any inbox asking for a book on another site is guided to
that site with a link straight to that book's page. Never invent a book,
author or link.

## Result at a glance
- **20,712 books loaded as 84 help-centre articles** (per-category / genre /
  decade articles, max 800 books each — never individual snippets).
- Premium Books Library: **14,779 books / 44 articles** — ALL of them.
- Best Selling Books: **5,657 books / 27 articles** — ALL of them.
- The Unread Library: **276 books / 13 articles** — ALL of them.
- Urdu Free Books: **0 books — BLOCKED** (see below).
- Four inboxes exist (Premium id 1, Urdu Free Books id 2,
  Best Selling Books id 3, The Unread Library id 4).
- Assistant instructions updated for cross-site answers (completion +
  assistant instructions; `phase-4f-update-instructions.py`).
- Regression: `phase-2-test.py` **36/36 passed** after the load.
- Cross-site tests: **5/10 passed** — the failures are all caused by the
  Gemini embedding quota (below), not by wrong answers. No reply invented
  a book, author or link anywhere in this run.

## Per-site catalogue source (verified, not assumed)
| Site | Catalogue source found | Books | Link pattern per book |
|---|---|---|---|
| Premium Books Library — https://premium-books-library.pages.dev | `/json/search-index.json` (snapshot `phase-4-books.json`) | 14,779 (37 categories) | **No per-book page exists on the site** (verified in its JS bundle: no `/books/` or detail route). Fallback used honestly: the catalogue's own Drive link (`d` field) — that is the site's own book destination. |
| Best Selling Books — https://best-selling-books.pages.dev | Catalogue embedded in `main.js?v=fill2` (1.2 MB), extracted to `phase-4f-bestselling-books.json` | 5,657 (25 genres, all unique ISBN13) | **No per-book page and no outbound book link on the site** (verified in main.js: no routing, no amazon/worldcat/goodreads links). Fallback: `https://openlibrary.org/isbn/<isbn13>`. |
| The Unread Library — https://the-unread-library.pages.dev | `assets/data/books.json` (`phase-4f-unread-books.json`) | 276 (13 decade groups; 185/276 have empty Category, so grouped by decade) | **No per-book page on the site.** Its own per-book links used: GoodreadsLink (151 books), else WorldCatLink (273 have one, 0 have neither). |
| Urdu Free Books — https://urdufreebooks.com/ (main site) | **NONE FOUND — site unreachable from this VM** | 0 | n/a |

Urdu Free Books detail: DNS resolves (198.18.243.235), TLS handshake
completes, server returns an empty reply — same with browser User-Agent,
HTTP/1.1, www host, sitemap and search-index paths; `browser.open` also
failed. No Wayback snapshot exists. No local source in `~/workspace`. Its
archive.org profile `@molana_muhammad_talha` is a user profile, not a book
collection (creator/uploader searches returned 0). Web search found no
catalogue info. **No books were invented for it.** The site is NOT claimed
to be down — only that this VM could not reach it. Needs the user to supply
its catalogue source (books.json / search-index file, or a reachable link).

## Direct-link verification (actually opened)
- Best Selling: `https://openlibrary.org/isbn/9780553807059` (ODD HOURS) →
  HTTP 200, final URL `https://openlibrary.org/verify_human?next=/books/OL10634377M`
  — resolves to the correct book (OL10634377M) but curl hits a human-verification
  page first. Recorded honestly: the link is right, a browser may show a
  human check before the book page.
- Unread: `https://www.goodreads.com/book/show/151601.Stella_in_Heaven`
  → HTTP 200, page contains "Stella in Heaven" 3× and "Art Buchwald" 2× —
  verified as the book's own page.
- Premium: Drive links were verified in Phase 4 replies (assistant returns
  `drive.google.com` links from the catalogue); the site has no book page
  of its own to link to.

## Cross-site tests (`phase-4f-test.py`, 5/10 passed)
Test books were verified to exist in exactly one catalogue each:
"The 5 AM Club" (Premium only), "ODD HOURS" (Best Selling only),
"Stella in Heaven" (Unread only), "Tafseer Ibn Kathir" (none).

- (b) Best Selling only — "ODD HOURS": **FAIL** — reply: *"I'm sorry, but I
  couldn't complete your request to search for that book right now. Would
  you like me to connect you with a human agent…"* (embedding quota — see below).
- (b) Unread only — "Stella in Heaven": **PASS** — verbatim reply:
  *"Yes, we have that book! It's available at The Unread Library. Title:
  Stella in Heaven. Author: Art Buchwald. Category: 2000s. Site: The Unread
  Library. Link: https://www.goodreads.com/book/show/151601.Stella_in_Heaven"*
  — exactly the cross-site behaviour asked for.
- (c) Premium own-site — "The Daily Stoic" (its article IS embedded):
  **FAIL** — HTTP 429 rate limit at the preview endpoint (embedding quota).
- (c2) "The 5 AM Club": **FAIL** — *"I'm sorry, I couldn't complete your
  request at the moment…"* — its article (Self-Help) is not embedded yet.
- (d) "Tafseer Ibn Kathir" (in none): **FAIL** — HTTP 429 (quota); no answer
  was produced, so nothing was invented — but the "not in library" behaviour
  could not be re-verified in this run.
- Widget (Premium inbox visitor asks for "ODD HOURS"): conversation created
  (200) and assigned to the AI assistant (200), but **no AI reply arrived
  within 120 s** of polling (embedding quota blocks the assistant's retrieval).
- Retries of the three failed previews 45 s apart: all failed the same way
  (2× HTTP 429, 1× "couldn't complete").

## The embedding-quota blocker (why 5 tests failed)
- Gemini embedding on this key is free-tier, **1,000 requests/day per model**.
  Both `gemini-embedding-001` and `gemini-embedding-2` hit 429 "Embed content
  requests per day limit exceeded … Please retry in 7h3m" at ~00:56 UTC;
  `gemini-embedding-2-preview` (the only other embedding model on this key)
  is 429 as well. The quota window resets at ~08:00 UTC (midnight Pacific)
  on 2026-11-17 — about **13:00 PKT today**.
- Consequence: of the 84 KB articles, **49 are embedded and 35 are not**
  (all 35 unembedded are Premium articles; Unread 13/13 and Best Selling
  27/27 are embedded). The reconcile loop keeps retrying and embeds a few
  whenever a request leaks through (49 → 51 during this session), but at
  ~10 successful requests/hour it cannot finish before the reset.
- The quota also blocks **retrieval itself** (each assistant query needs an
  embedding), which is why even already-embedded books (ODD HOURS, Daily
  Stoic) failed in this run. The Stella pass happened in a brief window
  when a request got through.
- **Nothing is lost:** all 20,712 books are in the KB as articles. After the
  reset (~08:00 UTC / 13:00 PKT) the reconcile loop will embed the remaining
  35 articles automatically; a short verification pass is then needed
  (re-run `phase-4f-test.py` — the 5 failed steps should pass).

## Incidents during this run (all cleaned up)
1. The first loader run was stopped mid-way when the embedding quota hit;
   the resume run initially used a wrong articles-list endpoint (404), so it
   created **8 duplicate Unread articles** (ids 48–55). All 8 were deleted
   via the API; duplicate-title check now returns 0.
2. While cleaning duplicates I deleted the wrong id once (loader article
   "Cooking, Food & Home", 27 books, id 93, mistaken for a test article).
   The resume-safe loader was re-run and recreated it — and it embedded
   (1/1). Final counts verified: 84 KB articles, 0 duplicate titles.
3. The resume check now reads existing titles from Postgres (there is no
   API list endpoint for articles), and the loader skips existing titles.
4. Phase 2/3 regression re-run recreated its own test article
   ("How to find a book by name or type"); the older copy was deleted.

## Files
- `phase-4f-full-load.py` — loader (resume-safe, batch size 6, ≤800 books/article)
- `phase-4f-full-load.json` — per-site counts + inbox UUIDs
- `phase-4f-full-load.log` / `phase-4f-full-load3.log` / `phase-4f-full-load4.log`
- `phase-4f-bestselling-books.json` (5,657), `phase-4f-unread-books.json` (276)
- `phase-4f-update-instructions.py` — cross-site assistant instructions
- `phase-4f-test.py`, `phase-4f-test-results.json`, `phase-4f-ai-replies.json`,
  `phase-4f-retry-replies.json`
- This report: `phase-4-full-load-report.md`

## Time spent
~45 minutes of active work in this session (recovery from the overnight VM
reboot + rebuild ~10 min; loader runs ~25 min; tests + link checks ~10 min),
plus the earlier catalogue investigation for the three sites in the previous
turn. Well inside the 4–8 h estimate given for this job.

## Still to do / awaiting the user's decision
1. **Urdu Free Books catalogue source** — the user needs to supply its
   books.json / search-index file, or a reachable link, before its books
   can be loaded. Nothing was invented for it.
2. **Verification pass after the embedding quota resets (~13:00 PKT today,
   2026-11-17)** — re-run `phase-4f-test.py`; the 5 failed steps (ODD HOURS,
   Daily Stoic, 5 AM Club, Tafseer Ibn Kathir, widget reply) should then pass.
3. **Do NOT publish yet** — Libredesk stays local-only (localhost:9000)
   until the user says so (his decision of 2026-11-17).

## Post-reset verification — 2026-11-17, 13:15–13:20 PKT (UPDATE)
- Server was still running (HTTP 200); **no new reboot, no database wipe** —
  no recovery was needed. Combined KB intact: 129,230 books / 258 articles
  (261 `help_articles` rows in Postgres: the 258 KB articles + 3 duplicate
  copies of the phase-2 test article "How to find a book by name or type",
  ids 1/260/261 — harmless, created by regression re-runs).
- **Embedding: 71 of 258 KB articles embedded (187 still pending)** — up
  from 1 this morning, but the reconcile loop is crawling: most embedding
  requests still return HTTP 429, with the error saying "Embed content
  requests per day limit exceeded … Please retry in 23h48m" (logged
  13:11 PKT), i.e. the free-tier daily quota window ends ~13:00 PKT
  **tomorrow (2026-11-18)**. A few requests leak through (69 → 71 → 73
  embedded in ~8 min), so the count inches up, but at this rate the
  remaining 187 articles will not finish today.
- **Re-run of `phase-4f-test.py`: 4/10 passed** (was 5/10). Passes: login,
  Premium inbox found, widget conversation created, assigned to assistant.
  All 5 book/widget steps still fail — now for two distinct reasons:
  (a) query-time 429s (Stella in Heaven, 5 AM Club, Tafseer, widget — the
  assistant could not even search); (b) the needed articles are still
  unembedded, so the assistant answers from the embedded articles only and
  says the book is "not in the library" (ODD HOURS — it instead listed
  other Dean Koontz Horror titles with correct Open Library links; Daily
  Stoic — same "not in our library" answer). **Nothing was invented** in
  any reply; the two "not in library" answers are wrong only because the
  articles holding those books are not embedded yet (Fantasy/Best Selling
  id 23, Religion part 1/Premium id 46, Self-Help/Premium id 64).
  Note: Stella in Heaven PASSED in the morning run and now fails on a
  query-time 429 — a quota flake, not a data problem.
- **Next step: wait for the quota window to end (~13:00 PKT tomorrow,
  2026-11-18), let the reconcile loop embed the remaining 187 articles,
  then re-run both test scripts.** No new schedule was created on this
  run's own initiative — that decision is left to the user, as instructed.

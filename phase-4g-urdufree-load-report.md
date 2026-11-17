# Libredesk Phase 4g — Urdu Free Books catalogue load

Date: 2026-11-17 (work 04:00–04:45 UTC; 09:00–09:45 PKT). Server: http://localhost:9000
(local only — NOT published, per the user's decision of 2026-11-17).

## What was asked
Load the Urdu Free Books catalogue from the backup file the user supplied
(Drive file `urdu-free-books-website.zip`, 159 MB) into the SAME combined
Libredesk knowledge base, Urdu Free Books inbox (id 2). Record exactly what
was loaded so later top-up files can be added without duplicates. Resolve
honestly the count discrepancy: books.json parses as 108,521 entries while
the zip's own summary.md says 36,120.

## Result at a glance
- **108,518 Urdu Free Books loaded as 174 help-centre articles** (54
  categories, max 800 books each — never individual snippets).
- Combined system now: **129,230 books in 258 KB articles** — Premium
  14,779 / Best Selling 5,657 / The Unread Library 276 / Urdu Free Books
  108,518. (Plus 1 phase-2 test article = 259 articles in the collection;
  verified in Postgres.)
- Assistant instructions already covered all four sites (restored from
  phase-4f); no instruction change was needed.
- Regression: `phase-2-test.py` **36/36 passed** after the load.
- Urdu Free cross-site tests: **4/9 passed** — the 5 failures are all the
  Gemini embedding quota (below), not wrong answers. No reply invented a
  book, author or link anywhere in this run.

## Source file
- `~/workspace/libredesk/urdufree/urdu-free-books-website.zip` (166,819,056
  bytes; Drive file "urdu-free-books-website.zip", downloaded via the
  re-shared link after the Google sign-in + 2-step verification step).
- Catalogue: `urdu-free-books/catalog-data/books.json` (198,716,362 bytes,
  dated 2026-11-05 15:08), extracted in place. Also extracted for reference:
  `summary.md`, `dedupe-report.md`, `qc-report.md`, `unclassified.json`,
  `quarantine.json`, `CATEGORIES.md` (all dated 2026-10-26).

## The count discrepancy — resolved by counting
| Fact | Count |
|---|---|
| Entries in books.json | **108,521** |
| Unique identifiers | **108,521** (0 duplicate identifiers, 0 missing) |
| Entries with a category / title / details_url / pdf_url | 108,521 (all) |
| Entries with empty author | 49,693 (46% — recorded as "Unknown" in KB entries) |
| Excluded: category `__OWNER_REMOVED__` | **3** (see below) |
| **Books loaded** | **108,518** |

- The zip's `summary.md` (2026-10-26) says "TOTAL books in books.json:
  36,120" and `dedupe-report.md` (same date) says 34,901 after dedupe.
  Those describe an **older build**: books.json itself is dated
  **2026-11-05**, ten days later, from later harvest rounds (source values
  in the file: `bulk3b` 65,854; `harvest` 34,411; `bulkC-in` 4,239;
  `bub-sweep2` 1,628; `nameless-scan` 1,070; others). The file is newer and
  much bigger — the discrepancy is a newer, larger harvest, NOT hidden
  duplicates. Nothing was guessed: every number above was counted from the
  file (`urdufree-analysis.txt`).
- Title-level check: 101,405 distinct normalized titles; 3,511 title groups
  share a title (7,116 extra entries). Largest groups are periodical issues
  (e.g. "Rampur State Gazette" issue numbers, ~40 entries each). These are
  DISTINCT archive.org items (distinct identifiers — different scans/issues
  of the same title), so all were loaded as-is, each with its own link.
  Nothing was dropped on title grounds; the user can order a title-level
  dedupe later if wanted.
- The 12,598 "verified-with-PDF but unclassified" entries from summary.md
  are NOT in this books.json (it has 0 entries without a category); they
  sit in the separate `unclassified.json` (334 KB, extracted) and were NOT
  loaded. If the user wants them, they are a separate top-up.
- 55 distinct categories in the file; the load used 54 (see exclusions).
  Largest: شاعری 11,760; رسائل و جرائد 10,599; حدیث کی کتابیں 9,137;
  عقائد کی کتابیں 7,609; فقہ کی کتابیں 6,559; تراجمِ قرآن و تفاسیر 5,722.
  Full per-category counts are in `urdufree-analysis.txt`.
- Language: اردو 105,810; انگریزی 1,224; عربی 823; English 304; فارسی 120;
  پنجابی 61; Urdu 46; سندھی 30 (plus a few smaller).

## Excluded: 3 `__OWNER_REMOVED__` entries (NOT loaded)
Three entries carry the literal category `__OWNER_REMOVED__` — read as
owner-removed, so they were deliberately NOT loaded:
- `Engineering_Maths-in-Urdu_202006` — "Engineering/Mathematics Text Books in Urdu" (Khalid Khan Yousafzai)
- `20221002_20221002_1708` — "الیکٹریکل ایشنشلز"
- `in.ernet.dli.2015.449590` — "Forty Lessons In Engineering Workshop Practice" (Syed Dildar Hussain)
If the user wants them in after all, they are a 1-article top-up.

## Link pattern + verification (actually opened)
- Link per book: **the file's own `details_url`** — an
  `https://archive.org/details/<...>` link, present for every entry.
- NOT constructed as `archive.org/details/<identifier>`: 1,351 entries have
  composite identifiers (a parent archive.org item + `__suffix`, i.e. one
  book inside a multi-book item, e.g.
  `20221217_20221217_1027__bawarchi-khana-eid-special-2013`). The
  constructed URL **404s** for those (verified twice); the recorded
  `details_url` (the parent item) returns **200**. Using the file's own
  link avoids 1,351 broken links.
- Verified by opening: `pakistani-khane-urdu` → 200, page title "پاکستانی
  کھانے — Pakistani Khane (Urdu)"; `tafheem-ul-quran-vol-1-n_202301` → 200,
  "Tafheem Ul Quran : مولانا مودودیؒ"; `MAARIFULQURAN_FULL_URDU` → 200,
  "MAARIF UL QURAN : Shaykh Mufti Muhammad Shafi (r.a)". Composite id
  `20221217_20221217_1027__bawarchi-khana-eid-special-2013` → 404, parent
  `20221217_20221217_1027` → 200; second composite
  `urdu-books-of-mubashir-husain-rehmani_202412__mafhoom-quran-ai` → 404.

## IMPORTANT: the VM rebooted again and wiped the database
- `/proc/uptime` was ~36 min at 04:00 UTC: the VM rebooted ~03:34 UTC
  2026-11-17 and Postgres came back fresh (only postgres/template0/
  template1 — the `libredesk` database, all 84 KB articles, all inboxes,
  the AI config and the assistant were gone). No database backup existed.
- Recovery done in this session (~15 min): Postgres cluster started, Redis
  started, role + database recreated, `--install` + `--upgrade` re-run,
  System password reset to the same value, Gemini proxy restarted,
  Libredesk server restarted detached (root 200, proxy `/healthz` ok).
- Then, in order: `phase-2-test.py` re-ran **37/37** (base fixtures
  recreated); AI config + assistant re-created from scratch
  (`phase-4g-restore.py`: completion `gemini-3-flash-preview`, embedding
  `gemini-embedding-2` 768 dims, base URL `http://localhost:18080/v1`,
  dummy placeholder key; assistant "Premium Books Assistant" id 1,
  user_id 3 — same ids as before; `phase-4-state.json` rewritten);
  `phase-4f-reload.py` re-loaded the other three sites (**20,712 books /
  84 articles**, same counts as phase-4f; new inbox UUIDs — Urdu Free
  `a507399f-ecb3-47fc-a355-27288cbf8aac`, Best Selling
  `84775d2f-af74-44ae-af7b-aa19b1ccc0d3`, Unread
  `31a1be8c-fe4b-4106-81e4-52000ca6b926`); then this Urdu Free load.
- Consequence for the 13:15 PKT verification cron: it re-runs the phase-4f
  tests, which now run against the freshly reloaded KB — that is fine, but
  it only covers the 5 failed phase-4f tests, NOT the 5 failed phase-4g
  tests below. The 4g tests need their own post-reset re-run
  (`phase-4g-test.py`).
- Standing fragility (unchanged): nothing in this local setup survives a
  VM reboot except files under `~`; after any reboot the database must be
  recreated and everything reloaded from the scripts in
  `~/workspace/libredesk`. A database backup would remove this risk — the
  user has not asked for one.

## Embedding quota — why tests failed and what is pending
- Gemini embedding free tier: 1,000 requests/day per model. Both
  `gemini-embedding-001` and `gemini-embedding-2` were already 429 at the
  start of this session (server log 02:38 UTC: "retry in 5h21m"); the
  embedding-config test in the restore returned 400/429 as expected.
  Reset ~08:00 UTC / **13:00 PKT today (2026-11-17)**.
- Of the 259 articles in the collection, **only 1 is embedded** at the end
  of this session (0 of the 174 new Urdu Free articles; 1 of the 84
  reloaded articles leaked through). All 129,230 books are in the KB as
  articles; the reconcile loop will embed them after the reset. The loader
  did NOT hammer the API: 30 s wait per batch, then moved on.
- Caveat carried over from phase-4f: the embedding input is truncated at
  2,048 tokens per article (server log warning), so for 800-book articles
  the embedding sees only the start of the article. Retrieval of books
  listed late in a long article may be weaker. This was the accepted
  phase-4f approach (max 800/article) and was kept for consistency.

## Cross-site tests (`phase-4g-test.py`, 4/9 passed, 09:40 PKT)
Test books were verified to exist ONLY in the Urdu Free catalogue
(normalized-title check against Premium + Best Selling + Unread):
- "Mukhtalif Mumalik ke Lazeez Khane" (Akhtar Jahan Begum) — خوراک و پکوان
- "Tariq Bin Ziyad" (Baleegh Aldeen Javed) — اسلامی تاریخ
- "Tajdeed Fikriyat Islam" (Allama Muhammad Iqbal) — فلسفہ و منطق
- "Tafseer Ibn Kathir" — verified absent from ALL FOUR catalogues.

- "Mukhtalif Mumalik ke Lazeez Khane": **FAIL (quota)** — reply: *"I am
  sorry, but I could not complete your request at this time. Would you like
  me to connect you with a human agent who can help?"*
- "Tariq Bin Ziyad": **FAIL (quota)** — *"I'm sorry, I couldn't complete
  that request right now. Would you like to speak with a human agent…?"*
- "Tajdeed Fikriyat Islam": **FAIL (quota)** — HTTP 429 *"The AI provider
  is rate limiting requests. Wait a minute and try again."*
- "Tafseer Ibn Kathir" (none): **FAIL (quota)** — HTTP 429; no answer was
  produced, so nothing was invented — but the "not in library" behaviour
  could not be re-verified in this run.
- Widget (Urdu Free inbox visitor asks for "Tariq Bin Ziyad"):
  conversation created (200), assigned to the AI assistant (200), but
  **no AI reply arrived within 120 s** of polling (embedding quota blocks
  retrieval). (The conversation UUID was truncated in the test log, so it
  is not quoted here.)
- Passed: agent login, Urdu Free inbox found, widget conversation created,
  conversation assigned to assistant (4/9).

## Files
- `phase-4g-urdufree-load.py` — loader (resume-safe, batch size 6, ≤800
  books/article, 30 s embed wait per batch)
- `phase-4g-urdufree-load.json` — per-run counts + inbox UUID
- `phase-4g-urdufree-load.log` — full loader log
- `phase-4g-restore.py` — AI config + assistant restore on a fresh DB
- `phase-4f-reload.py` / `phase-4f-reload.log` — reload of the other three
  sites after the reboot (30 s embed wait instead of 120 s)
- `phase-4g-test.py`, `phase-4g-test-books.json`,
  `phase-4g-test-results.json`, `phase-4g-ai-replies.json`
- `urdufree/urdufree-analysis.txt` — full counted analysis of books.json
- `phase-4f-full-load.json` — UPDATED combined totals (129,230 books /
  258 KB articles; urdufree section with source + excluded ids)
- This report: `phase-4g-urdufree-load-report.md`

## Time spent
~45 minutes (DB recovery + AI restore ~15 min; reload of 3 sites ~12 min;
Urdu Free load ~17 min; tests + verification ~5 min). The Urdu Free load
itself (174 articles) took ~17 minutes.

## Still to do / awaiting the user's decision
1. **Post-reset verification** — after ~13:00 PKT today re-run
   `phase-4g-test.py` (5 failed steps) AND `phase-4f-test.py` (5 failed
   steps). The 13:15 PKT cron covers only the phase-4f tests; the phase-4g
   tests need a separate re-run.
2. **The 3 `__OWNER_REMOVED__` books** — confirm they should stay out (or
   say to load them; 1-article top-up).
3. **Later top-up files** — the user said more backup files will follow;
   the loader is resume-safe (skips existing article titles), so top-ups
   load only new books. The `unclassified.json` (12,598 entries, no
   category) was NOT loaded — say if it should be.
4. **Do NOT publish yet** — Libredesk stays local-only (localhost:9000)
   until the user says so (his decision of 2026-11-17).
5. **Consider a database backup** — a second VM reboot wiped everything
   again this morning; a nightly `pg_dump` under `~/workspace` would make
   recovery a restore instead of a full reload. Not done — needs the user's
   word (it is extra work beyond what was asked).

## Post-reset verification — 2026-11-17, 13:15–13:20 PKT (UPDATE)
- Server still running (HTTP 200); **no new reboot, no database wipe** —
  no recovery needed. Urdu Free load intact: 108,518 books / 174 articles
  inside the combined 129,230 books / 258 KB articles.
- **Embedding: 71 of 258 KB articles embedded (187 still pending)** — up
  from 1 this morning, but most embedding requests still return HTTP 429;
  the error says "Embed content requests per day limit exceeded … Please
  retry in 23h48m" (logged 13:11 PKT), i.e. the free-tier daily quota
  window ends ~13:00 PKT **tomorrow (2026-11-18)**. A few requests leak
  through, so the count inches up, but the remaining 187 articles will not
  finish today at this rate.
- **Re-run of `phase-4g-test.py`: 4/9 passed** (unchanged from the morning).
  Passes: login, Urdu Free inbox found, widget conversation created,
  assigned to assistant. All 5 book/widget steps still fail on the quota:
  Tariq Bin Ziyad, Tajdeed Fikriyat Islam and Tafseer Ibn Kathir returned
  HTTP 429 outright; Mukhtalif Mumalik ke Lazeez Khane (whose article,
  خوراک و پکوان id 244, IS embedded) failed with "could not complete your
  request" — the query-time embedding was rate-limited; the widget got no
  AI reply within 120 s. **Nothing was invented** in any reply.
- The three Urdu Free test articles (اسلامی تاریخ part 1 id 173, فلسفہ و منطق
  part 1 id 220) are still unembedded; خوراک و پکوان (id 244) is embedded.
- **Next step: wait for the quota window to end (~13:00 PKT tomorrow,
  2026-11-18), let the reconcile loop embed the remaining 187 articles,
  then re-run both test scripts.** No new schedule was created on this
  run's own initiative — that decision is left to the user, as instructed.

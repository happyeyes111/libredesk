#!/usr/bin/env python3
"""Phase 4g: load the Urdu Free Books catalogue into the SAME combined
Libredesk knowledge base (Urdu Free Books inbox, id 2).

Source: ~/workspace/libredesk/urdufree/urdu-free-books-website.zip (159 MB,
Drive file "urdu-free-books-website.zip") — catalogue
urdu-free-books/catalog-data/books.json (198 MB, dated 2026-11-05).
The user says this is an approximate/near backup; later files will be
top-ups, so this loader is resume-safe (skips existing article titles) and
records exactly what was loaded.

Counts verified by counting (see phase-4g-urdufree-load-report.md):
- 108,521 entries in books.json; ALL have a unique identifier (0 duplicate
  identifiers); ALL have a category, title, details_url and pdf_url.
- The zip's own summary.md (2026-10-26) says 36,120 books — that describes
  an OLDER build. books.json is dated 2026-11-05: a later, much larger
  harvest (sources bulk3b/harvest/bulkC-in/...). The discrepancy is the file
  being newer and bigger, NOT hidden duplicates.
- Title-level: 3,511 normalized-title groups share a title (7,116 extra
  entries) — mostly periodical issues (e.g. Rampur State Gazette issues)
  and alternate scans of the same book. They are DISTINCT archive.org
  items (distinct identifiers), so all are loaded as-is; nothing dropped
  on title grounds.
- 3 entries have category "__OWNER_REMOVED__" — treated as owner-removed
  and NOT loaded (recorded in the report; the user can overrule).
  => LOADED: 108,518 books.

Link per book: the file's own details_url (an archive.org/details/... link,
present for every entry). NOT constructed as archive.org/details/<identifier>:
1,351 entries have composite identifiers (parent item + "__suffix", i.e. one
book inside a multi-book archive.org item); the constructed URL 404s for
them (verified), while the recorded details_url (parent item) returns 200.
Verified by opening sample URLs: 3/3 plain identifiers 200 with the correct
book title; composite id 404 vs parent 200.

Method: same as phase-4f — per-category help-centre articles in the "Books"
collection, max 800 books each, never individual snippets. Batch size 6,
embedding wait 30s per batch (the Gemini free-tier embedding quota is
exhausted until ~08:00 UTC / 13:00 PKT 2026-11-17; the reconcile loop will
embed the rest after the reset — articles are in the KB regardless).
Login password is read at runtime from phase-2-test.py.
"""
import collections
import html
import json
import re
import subprocess
import sys
import time

import requests

BASE = "http://localhost:9000"
BOOKS = "urdufree/urdu-free-books/catalog-data/books.json"
SITE_NAME = "Urdu Free Books"
SITE_URL = "https://urdufreebooks.com/"

with open("phase-2-test.py") as f:
    PASSWORD = re.search(r'"password":\s*"([^"]+)"', f.read()).group(1)

s = requests.Session()
r = s.post(f"{BASE}/api/v1/auth/login", json={"email": "System", "password": PASSWORD})
assert r.status_code == 200, "login failed"
csrf = s.cookies.get("csrf_token", "")
H = {"X-CSRFTOKEN": csrf} if csrf else {}


def psql(sql):
    out = subprocess.run(
        ["su", "postgres", "-c", f"psql -d libredesk -At -c \"{sql}\""],
        capture_output=True, text=True)
    return out.stdout.strip()


def embedded_count(article_ids):
    if not article_ids:
        return 0
    ids = ",".join(str(i) for i in article_ids)
    n = psql(f"SELECT count(*) FROM help_articles WHERE id IN ({ids}) AND embedded_fingerprint <> '';")
    return int(n or 0)


def wait_embedded(article_ids, label, timeout_s=30):
    total = len(article_ids)
    t0 = time.time()
    while time.time() - t0 < timeout_s:
        n = embedded_count(article_ids)
        if n >= total:
            print(f"  [{label}] embedded {n}/{total} ({int(time.time()-t0)}s)", flush=True)
            return True
        time.sleep(10)
    n = embedded_count(article_ids)
    print(f"  [{label}] embedded {n}/{total} after {timeout_s}s (quota may be exhausted — reconcile will finish after reset)", flush=True)
    return False


EXISTING_TITLES = set()


def refresh_existing_titles(col_id):
    out = psql(f"SELECT title FROM help_articles WHERE collection_id = {col_id};")
    for line in out.splitlines():
        if line.strip():
            EXISTING_TITLES.add(line.strip())
    print(f"  existing articles in KB: {len(EXISTING_TITLES)}", flush=True)


def create_article(col_id, title, content):
    r = s.post(f"{BASE}/api/v1/collections/{col_id}/articles", json={
        "title": title, "content": content, "locale": "en-US",
        "status": "published", "ai_enabled": True}, headers=H)
    if r.status_code != 200:
        print(f"  ARTICLE FAIL {title!r}: {r.status_code} {r.text[:200]}", flush=True)
        return None
    return r.json()["data"]["id"]


def load_batches(col_id, groups, title_fmt, entry_fmt, batch_size=6, max_per_article=800):
    chunks = []
    for key, blist in groups:
        for i in range(0, len(blist), max_per_article):
            part = blist[i:i + max_per_article]
            suffix = "" if len(blist) <= max_per_article else f" (part {i // max_per_article + 1})"
            chunks.append((key, part, suffix))
    created, books, ids = 0, 0, []
    skipped, skipped_books = 0, 0
    batch_ids, batch_n = [], 0
    for i, (key, blist, suffix) in enumerate(chunks, 1):
        title = title_fmt(key) + suffix
        if title in EXISTING_TITLES:
            skipped += 1
            skipped_books += len(blist)
            print(f"  skip (exists): {title} ({len(blist)} books)", flush=True)
            continue
        items = "".join(entry_fmt(b) for b in blist)
        content = (f"<p>{title} Each entry gives the book title, author, "
                   f"category, site and its Link.</p><ul>{items}</ul>")
        aid = create_article(col_id, title, content)
        if aid is None:
            continue
        created += 1
        books += len(blist)
        ids.append(aid)
        batch_ids.append(aid)
        batch_n += 1
        print(f"  created {created}: {title} ({len(blist)} books)", flush=True)
        time.sleep(2)
        if batch_n >= batch_size or i == len(chunks):
            wait_embedded(batch_ids, f"batch ending {title}")
            batch_ids, batch_n = [], 0
    if skipped:
        print(f"  skipped {skipped} existing articles ({skipped_books} books)", flush=True)
    return created, books, ids, skipped, skipped_books


# ---------- 1. help centre + Books collection ----------
r = s.get(f"{BASE}/api/v1/help-centers", headers=H)
assert r.status_code == 200
centres = r.json().get("data") or []
hc = next((c for c in centres if "Premium Books Library" in c.get("name", "")), None)
assert hc, f"help centre not found: {[c.get('name') for c in centres]}"
r = s.get(f"{BASE}/api/v1/help-centers/{hc['id']}/collections", headers=H)
cols = r.json().get("data") or []
col = next((c for c in cols if c.get("name") == "Books"), None)
assert col, "Books collection not found"
COL_ID = col["id"]
print(f"help centre {hc['id']}, Books collection {COL_ID}", flush=True)
refresh_existing_titles(COL_ID)

# ---------- 2. Urdu Free Books inbox must exist (created by phase-4f) ----------
r = s.get(f"{BASE}/api/v1/inboxes", headers=H)
existing = {ib.get("name"): ib for ib in (r.json().get("data") or [])}
assert SITE_NAME in existing, f"Urdu Free Books inbox missing: {list(existing)}"
ib = existing[SITE_NAME]
print(f"inbox: {SITE_NAME} id={ib['id']} uuid={ib['uuid']}", flush=True)

# ---------- 3. load + analyse books.json ----------
with open(BOOKS, encoding="utf-8") as f:
    data = json.load(f)
total_entries = len(data)
ids = [e.get("identifier") for e in data]
unique_ids = len(set(i for i in ids if i))
missing_id = sum(1 for i in ids if not i)
assert missing_id == 0, f"{missing_id} entries without identifier"
assert unique_ids == total_entries, f"duplicate identifiers: {total_entries - unique_ids}"

excluded = [e for e in data if e.get("category") == "__OWNER_REMOVED__"]
books = [e for e in data if e.get("category") != "__OWNER_REMOVED__"]
print(f"entries: {total_entries}, unique identifiers: {unique_ids}, "
      f"excluded (__OWNER_REMOVED__): {len(excluded)}, to load: {len(books)}", flush=True)

by_cat = collections.defaultdict(list)
for b in books:
    by_cat[b.get("category") or "دیگر"].append(b)
groups = sorted(by_cat.items(), key=lambda kv: -len(kv[1]))
print(f"categories: {len(groups)}", flush=True)


def entry_u(b):
    return ("<li><strong>{t}</strong> by {a} — Category: {c} — "
            "Site: Urdu Free Books (https://urdufreebooks.com/) — "
            "Link: {d}</li>").format(
                t=html.escape(b.get("title") or "Untitled"),
                a=html.escape(b.get("author") or "Unknown"),
                c=html.escape(b.get("category") or "دیگر"),
                d=html.escape(b.get("details_url") or ""))


created, loaded, ids_new, skipped, skipped_books = load_batches(
    COL_ID, groups,
    lambda k: f"Books — {k} (Urdu Free Books)",
    entry_u, batch_size=6)

emb = embedded_count(ids_new)
emb_all = int(psql(f"SELECT count(*) FROM help_articles WHERE collection_id = {COL_ID} AND embedded_fingerprint <> '';") or 0)
total_articles = int(psql(f"SELECT count(*) FROM help_articles WHERE collection_id = {COL_ID};") or 0)
result = {
    "source_file": BOOKS,
    "total_entries": total_entries,
    "unique_identifiers": unique_ids,
    "missing_identifier": missing_id,
    "excluded_owner_removed": len(excluded),
    "excluded_identifiers": [e.get("identifier") for e in excluded],
    "loaded_books": loaded + skipped_books,
    "articles_created_this_run": created,
    "articles_skipped_existing": skipped,
    "categories": len(groups),
    "embedded_new_articles": emb,
    "embedded_all_collection": emb_all,
    "total_articles_collection": total_articles,
    "inbox": {"id": ib["id"], "uuid": ib["uuid"]},
}
print("RESULT:", json.dumps(result, indent=2, ensure_ascii=False), flush=True)
json.dump(result, open("phase-4g-urdufree-load.json", "w"), indent=2, ensure_ascii=False)
print("DONE" if emb == len(ids_new) else "DONE WITH EMBEDDING GAP — reconcile will finish after quota reset", flush=True)

#!/usr/bin/env python3
"""Phase 4 KB migration: per-book snippets -> per-category help-centre articles.

Why: the Gemini free tier allows 1000 embed_content requests/day PER MODEL.
Libredesk embeds one API request per snippet, so 1200 snippets need 1200
requests — the gemini-embedding-001 quota was exhausted (retry in ~22h)
with 845/1200 embedded. Articles chunk at up to 2000 tokens, so one
article of ~32 books embeds as a single request: 37 category articles
need only ~37 requests, and the same design scales to all four book
websites (4 x ~37 articles, still a few hundred requests).

Steps:
 1. Delete the 1200 per-book snippets (local DB/API work, no Gemini quota).
 2. Switch the embedding provider to gemini-embedding-2 (fresh 1000/day
    quota for that model), dimensions 768. The model change triggers a
    reindex, which by then only covers the pre-existing help articles.
 3. Create one published, AI-enabled help-centre article per category in
    the "Books" collection of the "Premium Books Library Help" centre,
    listing that category's books with title, author, category, site and
    Link (the book's drive link from the live catalogue).
 4. Record counts to phase-4-kb-articles.json.

Source catalogue: the phase-4-books.json snapshot of the live search
index (14,779 entries, fetched 2026-11-16 from
https://premium-books-library.pages.dev/json/search-index.json).
The same 1200-book stratified selection as phase-4-kb-load.py is reused.
Login password is read at runtime from the existing phase-2-test.py.
"""
import collections
import html
import json
import re

import requests

BASE = "http://localhost:9000"
SITE_NAME = "Premium Books Library"
SITE_URL = "https://premium-books-library.pages.dev"
TARGET = 1200
MASKED_KEY = "•" * 10  # keeps the stored (dummy placeholder) key unchanged

with open("phase-2-test.py") as f:
    PASSWORD = re.search(r'"password":\s*"([^"]+)"', f.read()).group(1)

s = requests.Session()
r = s.post(f"{BASE}/api/v1/auth/login", json={"email": "System", "password": PASSWORD})
assert r.status_code == 200, "login failed"
csrf = s.cookies.get("csrf_token", "")
H = {"X-CSRFTOKEN": csrf} if csrf else {}

# --- 1. delete the per-book snippets ---
r = s.get(f"{BASE}/api/v1/ai/snippets", headers=H)
assert r.status_code == 200, f"snippets list failed: {r.text[:200]}"
items = r.json().get("data") or []
print(f"snippets to delete: {len(items)}", flush=True)
deleted = failed_del = 0
for i, it in enumerate(items, 1):
    r = s.delete(f"{BASE}/api/v1/ai/snippets/{it['id']}", headers=H)
    if r.status_code == 200:
        deleted += 1
    else:
        failed_del += 1
        print(f"DELETE FAIL id={it['id']}: {r.status_code} {r.text[:150]}", flush=True)
    if i % 300 == 0:
        print(f"  ... {i}/{len(items)} deleted", flush=True)
print(f"deleted={deleted} failed={failed_del}", flush=True)

# --- 2. switch embedding model to gemini-embedding-2 ---
r = s.put(f"{BASE}/api/v1/ai/config/embedding", json={
    "provider": "openai", "base_url": "http://localhost:18080/v1",
    "api_key": MASKED_KEY, "model": "gemini-embedding-2",
    "max_tokens": 0, "dimensions": 768, "embedding_max_tokens": 2048,
    "instructions": "", "vision": False,
}, headers=H)
print("PUT embedding config (gemini-embedding-2):", r.status_code, r.text[:150])
assert r.status_code == 200

# --- 3. find the help centre + Books collection ---
r = s.get(f"{BASE}/api/v1/help-centers", headers=H)
assert r.status_code == 200, f"help-centers failed: {r.text[:200]}"
centres = r.json().get("data") or []
hc = next((c for c in centres if c.get("name") == "Premium Books Library Help"), None)
assert hc, f"help centre not found: {[c.get('name') for c in centres]}"
r = s.get(f"{BASE}/api/v1/help-centers/{hc['id']}/collections", headers=H)
assert r.status_code == 200, f"collections failed: {r.text[:200]}"
cols = r.json().get("data") or []
col = next((c for c in cols if c.get("name") == "Books"), None)
assert col, f"Books collection not found: {[c.get('name') for c in cols]}"
print(f"help centre {hc['id']}, Books collection {col['id']}", flush=True)

# --- 4. same 1200-book selection, grouped by category ---
with open("phase-4-books.json") as f:
    books = json.load(f)
print(f"catalogue entries: {len(books)}", flush=True)
by_cat = collections.defaultdict(list)
for b in books:
    by_cat[b.get("ce") or "Other"].append(b)
cats = sorted(by_cat, key=lambda c: -len(by_cat[c]))
selected, seen = [], set()
idx = {c: 0 for c in cats}
while len(selected) < TARGET:
    progressed = False
    for c in cats:
        if len(selected) >= TARGET:
            break
        lst, i = by_cat[c], idx[c]
        if i < len(lst):
            b = lst[i]
            idx[c] += 1
            progressed = True
            if b["n"] not in seen:
                seen.add(b["n"])
                selected.append(b)
    if not progressed:
        break
for t in ["The 5 AM Club", "زیرو پوائنٹ (جلد ۲)", "زیرو پوائنٹ ۱"]:
    for b in books:
        if b["t"] == t and b["n"] not in seen:
            seen.add(b["n"])
            selected.append(b)
grouped = collections.defaultdict(list)
for b in selected:
    grouped[b.get("ce") or "Other"].append(b)
print(f"selected {len(selected)} books in {len(grouped)} categories", flush=True)

# --- 5. one article per category ---
created = failed_art = 0
article_ids = []
for cat, blist in sorted(grouped.items()):
    items_html = "".join(
        "<li><strong>{t}</strong> by {a} — Category: {c} — "
        "Site: {sn} ({su}) — Link: {d}</li>".format(
            t=html.escape(b["t"]), a=html.escape(b.get("a") or "Unknown"),
            c=html.escape(cat), sn=SITE_NAME, su=SITE_URL,
            d=html.escape(b.get("d") or ""))
        for b in blist
    )
    content = (
        f"<p>Books in the category <strong>{html.escape(cat)}</strong> from "
        f"{SITE_NAME} ({SITE_URL}). Each entry gives the book title, author, "
        f"category, site and its Link.</p><ul>{items_html}</ul>"
    )
    r = s.post(f"{BASE}/api/v1/collections/{col['id']}/articles", json={
        "title": f"Books — {cat} ({SITE_NAME})",
        "content": content,
        "locale": "en-US",
        "status": "published",
        "ai_enabled": True,
    }, headers=H)
    if r.status_code == 200:
        created += 1
        article_ids.append(r.json()["data"]["id"])
    else:
        failed_art += 1
        print(f"ARTICLE FAIL {cat!r}: {r.status_code} {r.text[:200]}", flush=True)
print(f"RESULT articles_created={created} failed={failed_art} "
      f"books={len(selected)} categories={len(grouped)} "
      f"snippets_deleted={deleted}", flush=True)
with open("phase-4-kb-articles.json", "w") as f:
    json.dump({"books": len(selected), "categories": len(grouped),
               "articles_created": created, "articles_failed": failed_art,
               "article_ids": article_ids, "snippets_deleted": deleted,
               "embedding_model": "gemini-embedding-2",
               "site": SITE_NAME, "site_url": SITE_URL}, f, indent=2)

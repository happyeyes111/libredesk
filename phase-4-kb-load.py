#!/usr/bin/env python3
"""Phase 4 KB load: load a real subset of the Premium Books Library
catalogue into Libredesk as AI knowledge-base snippets.

Source: the live site's own search index
  https://premium-books-library.pages.dev/json/search-index.json
(no local books.json exists on this VM; no titles are invented).
A snapshot is saved to phase-4-books.json.

Selection: 1200 books, stratified round-robin across categories so every
category is represented, plus forced inclusion of the books used by the
end-to-end tests. Each snippet: title = book title; content = title,
author, category and the catalogue download link (all real fields).
Idempotent: titles already present in Libredesk are skipped.

The Libredesk agent login password is read at runtime from the existing
phase-2-test.py; this script writes no new copy of it.
"""
import collections
import json
import re
import sys

import requests

BASE = "http://localhost:9000"
# MULTI-SITE DESIGN (one combined system): each book website gets its own
# Libredesk inbox and its own catalogue load through this same loader; all
# sites share one AI assistant and one knowledge base. Snippets carry the
# site name + site URL + book link so the assistant can tell sites apart
# and give the link with every answer.
# To add a site: append its dict to SITES and run the loader for it.
# SITES STILL MISSING (user was asked for their names/URLs; not supplied
# yet — do NOT invent them): the other three book websites.
SITES = [
    {
        "site_name": "Premium Books Library",
        "site_url": "https://premium-books-library.pages.dev",
        "catalogue_url": "https://premium-books-library.pages.dev/json/search-index.json",
        "inbox_name": "Premium Books Library",
    },
]
SITE = SITES[0]
CATALOGUE_URL = SITE["catalogue_url"]
TARGET = 1200
FORCE_TITLES = ["The 5 AM Club", "زیرو پوائنٹ (جلد ۲)", "زیرو پوائنٹ ۱"]

with open("phase-2-test.py") as f:
    PASSWORD = re.search(r'"password":\s*"([^"]+)"', f.read()).group(1)

s = requests.Session()
r = s.post(f"{BASE}/api/v1/auth/login", json={"email": "System", "password": PASSWORD})
assert r.status_code == 200, "login failed"
csrf = s.cookies.get("csrf_token", "")
H = {"X-CSRFTOKEN": csrf} if csrf else {}

print("fetching catalogue ...", flush=True)
r = requests.get(CATALOGUE_URL, timeout=120)
assert r.status_code == 200, f"catalogue fetch failed: {r.status_code}"
books = r.json()
print(f"catalogue entries: {len(books)}")
with open("phase-4-books.json", "w") as f:
    json.dump(books, f, ensure_ascii=False)

# Stratified round-robin across categories (file order within a category).
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
for t in FORCE_TITLES:
    for b in books:
        if b["t"] == t and b["n"] not in seen:
            seen.add(b["n"])
            selected.append(b)
print(f"selected: {len(selected)} books across {len(by_cat)} categories")

# Existing snippets (skip titles already loaded).
r = s.get(f"{BASE}/api/v1/ai/snippets", headers=H)
assert r.status_code == 200, f"snippets list failed: {r.text[:200]}"
existing_titles = {it["title"] for it in (r.json().get("data") or [])}
print(f"existing snippets: {len(existing_titles)}")

created = skipped = failed = 0
for i, b in enumerate(selected, 1):
    if b["t"] in existing_titles:
        skipped += 1
        continue
    content = (
        f"Book: {b['t']}\nAuthor: {b.get('a') or 'Unknown'}\n"
        f"Category: {b.get('ce') or 'Other'}\n"
        f"Site: {SITE['site_name']} ({SITE['site_url']})\n"
        f"Link: {b.get('d') or ''}"
    )
    r = s.post(f"{BASE}/api/v1/ai/snippets",
               json={"title": b["t"], "content": content, "enabled": True}, headers=H)
    if r.status_code == 200:
        created += 1
    else:
        failed += 1
        print(f"FAIL {b['t']!r}: {r.status_code} {r.text[:200]}", flush=True)
    if i % 200 == 0:
        print(f"  ... {i}/{len(selected)} processed", flush=True)

print(f"RESULT created={created} skipped={skipped} failed={failed} "
      f"total_selected={len(selected)} catalogue={len(books)}")
with open("phase-4-kb.json", "w") as f:
    json.dump({"catalogue_total": len(books), "selected": len(selected),
               "created": created, "skipped": skipped, "failed": failed,
               "categories": len(by_cat),
               "source": CATALOGUE_URL}, f, indent=2)

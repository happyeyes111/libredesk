#!/usr/bin/env python3
"""Phase 4 KB reformat: rewrite every book snippet into the multi-site
format so each entry explicitly carries its site and its book link.

Old format: Book / Author / Category / "Premium Books Library catalogue
            entry. Download: <drive url>"
New format: Book / Author / Category /
            Site: Premium Books Library (https://premium-books-library.pages.dev)
            Link: <drive url>

The drive URL is the book's link on the live site (the site links each
book out to its Google Drive file; there is no per-book detail page URL).
Updating a snippet re-triggers its embedding, so this also re-indexes
the KB on the final content. Idempotent: entries already in the new
format are skipped.

Login password is read at runtime from the existing phase-2-test.py.
"""
import json
import re

import requests

BASE = "http://localhost:9000"
SITE_NAME = "Premium Books Library"
SITE_URL = "https://premium-books-library.pages.dev"

with open("phase-2-test.py") as f:
    PASSWORD = re.search(r'"password":\s*"([^"]+)"', f.read()).group(1)

s = requests.Session()
r = s.post(f"{BASE}/api/v1/auth/login", json={"email": "System", "password": PASSWORD})
assert r.status_code == 200, "login failed"
csrf = s.cookies.get("csrf_token", "")
H = {"X-CSRFTOKEN": csrf} if csrf else {}

r = s.get(f"{BASE}/api/v1/ai/snippets", headers=H)
assert r.status_code == 200, f"snippets list failed: {r.text[:200]}"
items = r.json().get("data") or []
print(f"snippets: {len(items)}")

updated = skipped = failed = 0
for i, it in enumerate(items, 1):
    content = it.get("content") or ""
    if f"Site: {SITE_NAME} ({SITE_URL})" in content and "\nLink: " in content:
        skipped += 1
        continue
    m_title = re.search(r"^Book: (.*)$", content, re.M)
    m_author = re.search(r"^Author: (.*)$", content, re.M)
    m_cat = re.search(r"^Category: (.*)$", content, re.M)
    m_link = re.search(r"Download: (\S+)\s*$", content, re.M) or re.search(r"^Link: (\S+)\s*$", content, re.M)
    if not (m_title and m_author and m_cat and m_link):
        print(f"SKIP unparsable id={it['id']} title={it.get('title')!r}", flush=True)
        failed += 1
        continue
    new_content = (
        f"Book: {m_title.group(1)}\n"
        f"Author: {m_author.group(1)}\n"
        f"Category: {m_cat.group(1)}\n"
        f"Site: {SITE_NAME} ({SITE_URL})\n"
        f"Link: {m_link.group(1)}"
    )
    r = s.put(f"{BASE}/api/v1/ai/snippets/{it['id']}",
              json={"title": it["title"], "content": new_content, "enabled": True},
              headers=H)
    if r.status_code == 200:
        updated += 1
    else:
        failed += 1
        print(f"FAIL id={it['id']}: {r.status_code} {r.text[:200]}", flush=True)
    if i % 200 == 0:
        print(f"  ... {i}/{len(items)} processed", flush=True)

print(f"RESULT updated={updated} skipped={skipped} failed={failed} total={len(items)}")

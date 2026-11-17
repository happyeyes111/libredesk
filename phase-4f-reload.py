#!/usr/bin/env python3
"""Phase 4 full load: ALL books from all four book websites into ONE combined
knowledge base (per-category help-centre articles in the "Books" collection).

Sites and catalogue sources (verified 2026-11-17):
 1. Premium Books Library — https://premium-books-library.pages.dev
    Source: /json/search-index.json (phase-4-books.json snapshot, 14,779 entries).
    Link per book: the Drive link (d). The site has NO per-book page (verified
    in its JS bundle: no /books/ route, no book detail route); the Drive link
    is the site's own book destination.
 2. Urdu Free Books — https://urdufreebooks.com/ — BLOCKED: this VM cannot
    reach it (TLS handshake completes, server returns an empty reply; no
    Wayback snapshot; no local source). NOT loaded. Nothing invented.
 3. Best Selling Books — https://best-selling-books.pages.dev
    Source: catalogue embedded in main.js (5,657 books, title/author/isbn13/
    genre). Link per book: https://openlibrary.org/isbn/<isbn13> (site has
    no per-book page and no outbound book link — verified in main.js).
 4. The Unread Library — https://the-unread-library.pages.dev
    Source: assets/data/books.json (276 books). Link per book: the site's own
    GoodreadsLink (fallback WorldCatLink); the site has no per-book page.

Method: per-category articles (never individual snippets — that exhausted the
embedding quota in Phase 4). Articles are created in small batches and each
batch is verified embedded (help_articles.embedded_fingerprint != '') before
the next batch, to avoid the embedding storm seen in Phase 4.
Also creates the three missing inboxes (Urdu Free Books, Best Selling Books,
The Unread Library) with the same payload shape as phase-2-test.py.
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
SITES = {
    "premium": {"name": "Premium Books Library", "url": "https://premium-books-library.pages.dev"},
    "urdufree": {"name": "Urdu Free Books", "url": "https://urdufreebooks.com/"},
    "bestselling": {"name": "Best Selling Books", "url": "https://best-selling-books.pages.dev"},
    "unread": {"name": "The Unread Library", "url": "https://the-unread-library.pages.dev"},
}

with open("phase-2-test.py") as f:
    PASSWORD = re.search(r'"password":\s*"([^"]+)"', f.read()).group(1)

s = requests.Session()
r = s.post(f"{BASE}/api/v1/auth/login", json={"email": "System", "password": PASSWORD})
assert r.status_code == 200, "login failed"
csrf = s.cookies.get("csrf_token", "")
H = {"X-CSRFTOKEN": csrf} if csrf else {}

# ---------- helpers ----------
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
        print(f"  [{label}] embedded {n}/{total} ({int(time.time()-t0)}s)", flush=True)
        if n >= total:
            return True
        time.sleep(20)
    n = embedded_count(article_ids)
    print(f"  [{label}] TIMEOUT: embedded {n}/{total} after {timeout_s}s", flush=True)
    return False

# Titles already in the KB (resume-safe: a re-run skips articles that exist).
# Read straight from Postgres — there is no API list endpoint for articles.
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
    """groups: list of (key, [book dicts]) in creation order. Large groups are
    split into sub-articles of at most max_per_article books, so no single
    article body grows past ~150KB. Returns (created, books, ids)."""
    # expand groups into article-sized chunks
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
            ok = wait_embedded(batch_ids, f"batch ending {title}")
            if not ok:
                print("  WARNING: batch not fully embedded; continuing to next batch", flush=True)
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

# ---------- 2. create the three missing inboxes ----------
def inbox_payload(site):
    return {"name": site["name"], "channel": "livechat", "enabled": True,
            "config": {"brand_name": site["name"], "website_url": site["url"],
                       "theme": "system", "language": "en-US",
                       "greeting_message": "Assalam-o-Alaikum! Which book are you looking for?",
                       "branding": {"light": {"colors": {"primary": "#1d4ed8"}},
                                    "dark": {"colors": {"primary": "#1d4ed8"}}},
                       "launcher": {"position": "right", "spacing": {"side": 20, "bottom": 20}},
                       "visitors": {"allow_start_conversation": True},
                       "users": {"allow_start_conversation": True},
                       "features": {"emoji": True, "file_upload": False, "transcript": True}}}

r = s.get(f"{BASE}/api/v1/inboxes", headers=H)
existing = {ib.get("name"): ib for ib in (r.json().get("data") or [])}
inboxes = {}
for key in ("urdufree", "bestselling", "unread"):
    site = SITES[key]
    if site["name"] in existing:
        ib = existing[site["name"]]
        inboxes[key] = {"id": ib["id"], "uuid": ib["uuid"]}
        print(f"inbox exists: {site['name']} id={ib['id']} uuid={ib['uuid']}", flush=True)
    else:
        r = s.post(f"{BASE}/api/v1/inboxes", json=inbox_payload(site), headers=H)
        assert r.status_code in (200, 201), f"inbox create failed {site['name']}: {r.status_code} {r.text[:200]}"
        data = r.json().get("data") or r.json()
        inboxes[key] = {"id": data["id"], "uuid": data["uuid"]}
        print(f"inbox created: {site['name']} id={data['id']} uuid={data['uuid']}", flush=True)

# ---------- 3. The Unread Library (smallest — validates the pipeline) ----------
with open("phase-4f-unread-books.json") as f:
    unread = json.load(f)
def flip_author(a):
    a = (a or "").strip()
    if "," in a:
        last, first = a.split(",", 1)
        return f"{first.strip()} {last.strip()}".strip()
    return a
by_decade = collections.defaultdict(list)
for b in unread:
    y = (b.get("PubYear") or "").strip()
    decade = f"{y[:3]}0s" if y.isdigit() and len(y) == 4 else "Unknown year"
    by_decade[decade].append(b)
groups_u = sorted(by_decade.items())
def entry_u(b):
    link = b.get("GoodreadsLink") or b.get("WorldCatLink") or ""
    y = (b.get("PubYear") or "").strip()
    decade = f"{y[:3]}0s" if y.isdigit() and len(y) == 4 else "Unknown year"
    return ("<li><strong>{t}</strong> by {a} ({y}) — Category: {c} — "
            "Site: The Unread Library (https://the-unread-library.pages.dev) — "
            "Link: {d}</li>").format(
                t=html.escape(b["TitleClean"]), a=html.escape(flip_author(b.get("AuthorClean"))),
                y=html.escape(y), c=html.escape(decade), d=html.escape(link))
print("== The Unread Library: 276 books in", len(groups_u), "decade groups ==", flush=True)
cu, bu, idsu, su, sbu = load_batches(COL_ID, groups_u,
    lambda k: f"Books — {k} (The Unread Library)",
    entry_u, batch_size=6)

# ---------- 4. Best Selling Books ----------
with open("phase-4f-bestselling-books.json") as f:
    bs = json.load(f)
by_genre = collections.defaultdict(list)
for b in bs:
    by_genre[b["genre"]].append(b)
groups_b = sorted(by_genre.items(), key=lambda kv: -len(kv[1]))
def entry_b(b):
    return ("<li><strong>{t}</strong> by {a} — Category: {c} — "
            "Site: Best Selling Books (https://best-selling-books.pages.dev) — "
            "Link: https://openlibrary.org/isbn/{isbn}</li>").format(
                t=html.escape(b["title"]), a=html.escape(b["author"]),
                c=html.escape(b["genre"].replace("-", " ").title()),
                isbn=html.escape(b["isbn13"]))
print("== Best Selling Books:", len(bs), "books in", len(groups_b), "genres ==", flush=True)
cb, bb, idsb, sb, sbb = load_batches(COL_ID, groups_b,
    lambda k: f"Books — {k.replace('-', ' ').title()} (Best Selling Books)",
    entry_b, batch_size=6)

# ---------- 5. Premium Books Library (ALL 14,779) ----------
with open("phase-4-books.json") as f:
    prem = json.load(f)
by_cat = collections.defaultdict(list)
for b in prem:
    by_cat[b.get("ce") or "Other"].append(b)
groups_p = sorted(by_cat.items(), key=lambda kv: -len(kv[1]))
def entry_p(b):
    return ("<li><strong>{t}</strong> by {a} — Category: {c} — "
            "Site: Premium Books Library (https://premium-books-library.pages.dev) — "
            "Link: {d}</li>").format(
                t=html.escape(b["t"]), a=html.escape(b.get("a") or "Unknown"),
                c=html.escape(b.get("ce") or "Other"), d=html.escape(b.get("d") or ""))
print("== Premium Books Library:", len(prem), "books in", len(groups_p), "categories ==", flush=True)
cp, bp, idsp, sp, sbp = load_batches(COL_ID, groups_p,
    lambda k: f"Books — {k} (Premium Books Library)",
    entry_p, batch_size=6)

# ---------- summary ----------
total_books = bu + bb + bp + sbu + sbb + sbp
total_articles = cu + cb + cp + su + sb + sp
all_ids = idsu + idsb + idsp
emb = int(psql(f"SELECT count(*) FROM help_articles WHERE collection_id = {COL_ID} AND embedded_fingerprint <> '';") or 0)
result = {
    "unread": {"books": bu + sbu, "articles": cu + su},
    "bestselling": {"books": bb + sbb, "articles": cb + sb},
    "premium": {"books": bp + sbp, "articles": cp + sp},
    "urdufree": {"books": 0, "articles": 0, "blocked": "site unreachable from this VM (empty reply); no catalogue source found"},
    "total_books": total_books,
    "total_articles": total_articles,
    "embedded_articles": emb,
    "inboxes": inboxes,
}
print("RESULT:", json.dumps(result, indent=2), flush=True)
json.dump(result, open("phase-4f-full-load.json", "w"), indent=2)
print("DONE" if emb == total_articles else "DONE WITH EMBEDDING GAP — see result", flush=True)

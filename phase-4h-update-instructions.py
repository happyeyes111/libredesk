#!/usr/bin/env python3
"""Phase 4h: implement the user's two chatbot suggestions in the shared
Libredesk assistant (Premium Books Assistant, id 1).

Suggestion 1 — Premium paywall: a Premium Books Library book answer must
NOT give the direct Drive link from the KB entry. It must give the Premium
entry link https://premium-books-library.pages.dev (the site's front door,
where the access/pay box appears first), name the exact title and author,
and explain the access step (pay on WhatsApp, enter the access code;
monthly Rs 100 / 30 days, yearly Rs 500 / 365 days, lifetime Rs 1,000).
Note: the Premium site has no per-book pages (verified in Phase 4f), and
no separate /access route could be verified in this session — the live
homepage fetch failed (JS SPA, no extractable content) and web search
found no access route — so the homepage is used as the entry link.

Suggestion 2 — book requests: when no book in any catalogue matches, the
assistant says so plainly AND offers 2-3 in-chat options, including
sending a request for the book. Libredesk has no native request button,
so the offer works through the conversation: the assistant offers the
options as text, and on confirmation records the request in the
conversation itself for the library team to see.

Login password is read at runtime from phase-2-test.py. Assistant id is
read from phase-4-state.json. After the update, the stored instructions
are read back and verified.
"""
import json
import re

import requests

BASE = "http://localhost:9000"
MASKED_KEY = "•" * 10  # keeps the stored (dummy placeholder) key unchanged
PREMIUM_ENTRY = "https://premium-books-library.pages.dev"

with open("phase-2-test.py") as f:
    PASSWORD = re.search(r'"password":\s*"([^"]+)"', f.read()).group(1)
with open("phase-4-state.json") as f:
    STATE = json.load(f)

COMPLETION_INSTRUCTIONS = (
    "You are the book-library assistant for a combined system covering four "
    "book websites: Premium Books Library, Urdu Free Books, Best Selling "
    "Books and The Unread Library. Each website has its own inbox; they share "
    "one assistant and one knowledge base covering all four catalogues. "
    "Answer only about books in the knowledge base, using only what it returns. "
    "When a visitor asks for a book by name or type, name the matching books "
    "with title, author, category, the site name, AND the Link from the "
    "knowledge base entry — every book you name must come with its Link. "
    "IMPORTANT: if the book lives on a DIFFERENT website than the one the "
    "visitor is chatting from, say so clearly — name that website and give "
    "its Link, so the visitor can press the link and land directly on that "
    "book's page. PREMIUM BOOKS RULE: Premium Books Library is a paid "
    "library. If a book lives on Premium Books Library, do NOT give the "
    "book's direct Drive link from the knowledge base entry. Instead give "
    "the Premium entry link https://premium-books-library.pages.dev and "
    "name the exact book title and author, and tell the visitor to open the "
    "link, complete the access step first (pay on WhatsApp and enter the "
    "access code — monthly Rs 100 for 30 days, yearly Rs 500 for 365 days, "
    "lifetime Rs 1,000), and then search the site for the book title to "
    "open it. The entry link leads to the access/pay box first, not "
    "straight to the book. BOOK REQUEST RULE: if no book in any of the "
    "four catalogues matches, say plainly that the book is not in the "
    "library, then offer these options in the chat: (1) send a request for "
    "this book so it can be added to the website, (2) suggest a similar "
    "book from the library, (3) nothing more for now. If the visitor "
    "chooses the request option, ask them to confirm the exact book title "
    "and author, then confirm that the request is noted in this "
    "conversation for the library team to see. If no book matches in any of "
    "the four catalogues, say so plainly and do not invent a title or a "
    "link. Answer in the visitor's language (Urdu or English)."
)

ASSISTANT_INSTRUCTIONS = (
    "You help visitors of four book-library websites find books: Premium "
    "Books Library, Urdu Free Books, Best Selling Books and The Unread "
    "Library. Always search the knowledge base first. Answer only from what "
    "it returns. For every book you name, give all of these: title, author, "
    "category, the site name, and the Link exactly as given in the knowledge "
    "base entry. EXCEPTION: for a Premium Books Library book, do NOT give "
    "the direct Drive link from the entry. Give the Premium entry link "
    "https://premium-books-library.pages.dev instead, name the exact title "
    "and author, and explain that the visitor must complete the access step "
    "first (pay on WhatsApp, enter the access code — monthly Rs 100 / 30 "
    "days, yearly Rs 500 / 365 days, lifetime Rs 1,000) and then search the "
    "site for the title. If the book is on a different website than the "
    "visitor's own site, say which website it is on and give its Link so "
    "the visitor can press it and land directly on that book's page. If the "
    "visitor asks by type or category, suggest two or three matching books "
    "from the catalogue, each with its Link (Premium books: entry link, as "
    "above). If no book in any catalogue matches, say plainly that the book "
    "is not in the library and offer these options in the chat: (1) request "
    "this book to be added to the website, (2) a similar book suggestion, "
    "(3) nothing more. If the visitor confirms a request, confirm the exact "
    "title and author with them and tell them the request is noted in this "
    "conversation for the library team. Never invent a book, author, "
    "category or link. Keep replies short."
)

ASSISTANT_GUARDRAILS = (
    "Never invent book titles, authors, categories or download links. "
    "Only name books that the knowledge base returned for this question, "
    "with the Link exactly as given there. EXCEPTION: never give a direct "
    "Drive download link for a Premium Books Library book — always give "
    "the Premium entry link https://premium-books-library.pages.dev instead."
)

s = requests.Session()
r = s.post(f"{BASE}/api/v1/auth/login", json={"email": "System", "password": PASSWORD})
assert r.status_code == 200, "login failed"
csrf = s.cookies.get("csrf_token", "")
H = {"X-CSRFTOKEN": csrf} if csrf else {}

r = s.put(f"{BASE}/api/v1/ai/config/completion", json={
    "provider": "openai", "base_url": "http://localhost:18080/v1",
    "api_key": MASKED_KEY, "model": STATE["completion_model"],
    "max_tokens": 1024, "dimensions": 0, "embedding_max_tokens": 0,
    "instructions": COMPLETION_INSTRUCTIONS, "vision": False,
}, headers=H)
print("PUT completion config:", r.status_code, r.text[:200], flush=True)
assert r.status_code == 200, r.text[:300]

aid = STATE["assistant_id"]
r = s.get(f"{BASE}/api/v1/ai/assistants/{aid}", headers=H)
print("GET assistant:", r.status_code, flush=True)
cur = r.json().get("data") or {}
payload = {
    "name": cur.get("name", "Premium Books Assistant"),
    "description": "Answers visitors' book questions from the combined catalogue of all four book-library websites, with a direct link for every book.",
    "instructions": ASSISTANT_INSTRUCTIONS,
    "guardrails": ASSISTANT_GUARDRAILS,
    "expectation": cur.get("expectation", "Short book suggestions with title, author, category, site and Link, grounded in the catalogue."),
    "tone": cur.get("tone", "friendly"),
    "response_length": cur.get("response_length", "balanced"),
    "max_turns": cur.get("max_turns", 10),
    "citations_enabled": True,
    "handoff_enabled": True,
    "enabled": True,
}
files = {"data": (None, json.dumps(payload), "application/json")}
r = s.put(f"{BASE}/api/v1/ai/assistants/{aid}", files=files, headers=H)
print("PUT assistant:", r.status_code, r.text[:300], flush=True)
assert r.status_code == 200, r.text[:300]

# Verify what is stored now
r = s.get(f"{BASE}/api/v1/ai/config/completion", headers=H)
stored_completion = (r.json().get("data") or {}).get("instructions", "") \
    if r.status_code == 200 else ""
r = s.get(f"{BASE}/api/v1/ai/assistants/{aid}", headers=H)
stored = r.json().get("data") or {}
ok_completion = "PREMIUM BOOKS RULE" in stored_completion and "BOOK REQUEST RULE" in stored_completion
ok_assistant = "EXCEPTION: for a Premium Books Library book" in (stored.get("instructions") or "") \
    and "premium-books-library.pages.dev" in (stored.get("guardrails") or "")
print("VERIFY completion instructions stored:", ok_completion, flush=True)
print("VERIFY assistant instructions+guardrails stored:", ok_assistant, flush=True)
assert ok_completion and ok_assistant, "stored instructions do not contain the new rules"
print("OK — both suggestions are now in the assistant instructions", flush=True)

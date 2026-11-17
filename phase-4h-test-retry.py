#!/usr/bin/env python3
"""Phase 4h retry: the first test run hit Gemini rate limits (HTTP 429 on
3 previews, retrieval failure on the 4th, no widget reply in 120 s).
This retry waits, then runs the same 4 previews spaced 75 s apart, plus a
fresh widget conversation (full UUID saved this time), polling up to 180 s.
Results to phase-4h-test-retry-results.json / phase-4h-ai-replies-retry.json.
"""
import json
import re
import time

import requests

BASE = "http://localhost:9000"
results = []
REPLIES = {}

with open("phase-2-test.py") as f:
    PASSWORD = re.search(r'"password":\s*"([^"]+)"', f.read()).group(1)
with open("phase-4-state.json") as f:
    STATE = json.load(f)
ASSISTANT_ID = STATE["assistant_id"]
ASSISTANT_USER_ID = STATE["assistant_user_id"]


def step(name, ok, detail=""):
    results.append({"step": name, "ok": bool(ok), "detail": str(detail)[:600]})
    print(f"[{'PASS' if ok else 'FAIL'}] {name} :: {str(detail)[:300]}", flush=True)


def data(r):
    try:
        return r.json().get("data", r.json())
    except Exception:
        return {}


s = requests.Session()
r = s.post(f"{BASE}/api/v1/auth/login", json={"email": "System", "password": PASSWORD})
step("agent login (System)", r.status_code == 200, f"{r.status_code}")
csrf = s.cookies.get("csrf_token", "")
H = {"X-CSRFTOKEN": csrf} if csrf else {}


def preview(msg):
    r = s.post(f"{BASE}/api/v1/ai/assistants/{ASSISTANT_ID}/preview",
               json={"message": msg}, headers=H, timeout=120)
    if r.status_code != 200:
        return None, f"HTTP {r.status_code} {r.text[:200]}"
    return data(r), ""


def check(name, key, msg, must, must_not=()):
    reply, err = preview(msg)
    txt = (reply or {}).get("reply", "") if reply else ""
    REPLIES[key] = txt
    ok = all(m in txt for m in must) and all(m not in txt for m in must_not)
    step(name, ok, err or txt[:500])
    print("  REPLY:", txt[:700].replace("\n", " "), flush=True)
    return txt


print("Cooling down 90 s before retrying...", flush=True)
time.sleep(90)

check("retry 1: Premium book -> entry link, no Drive link",
      "premium_paywall",
      "I am looking for the book On Food and Cooking by Harold McGee. Do you have it?",
      ["On Food and Cooking", "Premium Books Library", "premium-books-library.pages.dev"],
      ["drive.google.com"])
time.sleep(75)

check("retry 2: FACES OF FEAR -> Best Selling Books + Open Library link",
      "bs_only",
      "Do you have the book FACES OF FEAR by John Saul?",
      ["FACES OF FEAR", "Best Selling Books", "openlibrary.org/isbn/"])
time.sleep(75)

check("retry 3: Stella in Heaven -> The Unread Library + Goodreads link",
      "unread_only",
      "Do you have the book Stella in Heaven by Art Buchwald?",
      ["Stella in Heaven", "The Unread Library", "goodreads.com"])
time.sleep(75)

check("retry 4: Tafseer Ibn Kathir -> not in library + request options",
      "no_match_request",
      "Do you have the book Tafseer Ibn Kathir?",
      ["not in the library", "request"],
      ["drive.google.com/file"])

# --- widget end-to-end (fresh conversation, full UUID saved) ---
r = s.get(f"{BASE}/api/v1/inboxes", headers=H)
inbox = next((ib for ib in (r.json().get("data") or [])
              if ib.get("name") == "Premium Books Library"), None)
INBOX_UUID = inbox.get("uuid") if inbox else None
step("Premium Books inbox found", bool(INBOX_UUID), INBOX_UUID or "")
if INBOX_UUID:
    w = requests.Session()
    WH = {"X-Libredesk-Inbox-ID": INBOX_UUID}
    r = w.post(f"{BASE}/api/v1/widget/chat/conversations/init", headers=WH,
               json={"message": "Assalam-o-Alaikum, I am looking for the book On Food and Cooking by Harold McGee.",
                     "subject": "Book search"})
    ok = r.status_code in (200, 201)
    step("visitor starts widget conversation (Premium inbox)", ok, f"{r.status_code} {r.text[:200]}")
    if ok:
        d = data(r)
        CONV_UUID = (d.get("conversation") or {}).get("uuid") or d.get("uuid")
        results.append({"step": "widget conversation uuid", "ok": bool(CONV_UUID),
                        "detail": CONV_UUID or ""})
        print("CONV_UUID:", CONV_UUID, flush=True)
        r = s.put(f"{BASE}/api/v1/conversations/{CONV_UUID}/assignee/user",
                  json={"assignee_id": ASSISTANT_USER_ID}, headers=H)
        step("conversation assigned to AI assistant", r.status_code == 200,
             f"{r.status_code} {r.text[:150]}")
        ai_reply = ""
        for _ in range(60):
            time.sleep(3)
            r = s.get(f"{BASE}/api/v1/conversations/{CONV_UUID}/messages", headers=H)
            d = r.json().get("data", {}) if r.status_code == 200 else {}
            msgs = d.get("results", []) if isinstance(d, dict) else d
            for m in msgs:
                if not isinstance(m, dict):
                    continue
                content = re.sub(r"<[^>]+>", " ", m.get("content") or "")
                if m.get("sender_type") == "agent" and "On Food and Cooking" in content:
                    ai_reply = content
                    break
            if ai_reply:
                break
        REPLIES["widget_premium"] = ai_reply
        step("widget: AI gives Premium entry link, no Drive link",
             "On Food and Cooking" in ai_reply
             and "premium-books-library.pages.dev" in ai_reply
             and "drive.google.com" not in ai_reply,
             ai_reply[:500])
        print("  AI REPLY:", ai_reply[:700].replace("\n", " "), flush=True)

passed = sum(1 for x in results if x["ok"])
print(f"\n==== {passed}/{len(results)} steps passed ====", flush=True)
with open("phase-4h-test-retry-results.json", "w") as f:
    json.dump(results, f, indent=2, ensure_ascii=False)
with open("phase-4h-ai-replies-retry.json", "w") as f:
    json.dump(REPLIES, f, indent=2, ensure_ascii=False)

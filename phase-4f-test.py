#!/usr/bin/env python3
"""Phase 4 full load: cross-site assistant tests.

Uses the assistant preview endpoint (no side effects) plus one live widget
conversation in the Premium inbox asking for a Best Selling Books title.

Test books (verified present in exactly one catalogue each):
- "The 5 AM Club" (Robin Sharma) — Premium Books Library only.
- "ODD HOURS" (Dean R Koontz) — Best Selling Books only.
- "Stella in Heaven" (Art Buchwald) — The Unread Library only.
- "Tafseer Ibn Kathir" — in NONE of the four catalogues.

Login password is read at runtime from phase-2-test.py.
Results printed and saved to phase-4f-test-results.json (+ replies).
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
    print(f"[{'PASS' if ok else 'FAIL'}] {name} :: {str(detail)[:300]}")


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
    step(name, ok, err or txt[:400])
    print("  REPLY:", txt[:600].replace("\n", " "))
    return txt


# (b) book only on Best Selling Books — asked as a preview
check("cross-site: ODD HOURS -> Best Selling Books + Open Library link",
      "bs_only",
      "I am looking for the book ODD HOURS by Dean Koontz. Do you have it?",
      ["ODD HOURS", "Best Selling Books", "openlibrary.org/isbn/"])

# (b) book only on The Unread Library
check("cross-site: Stella in Heaven -> The Unread Library + Goodreads link",
      "unread_only",
      "Do you have the book Stella in Heaven by Art Buchwald?",
      ["Stella in Heaven", "The Unread Library", "goodreads.com"])

# (c) book on Premium itself — in an EMBEDDED article (Religion part 1)
check("own-site: The Daily Stoic -> Premium + Drive link",
      "premium_own",
      "I am looking for the book The Daily Stoic by Ryan Holiday. Do you have it?",
      ["Daily Stoic", "Ryan Holiday", "Premium Books Library", "drive.google.com"])

# (c2) canonical Phase 4 book — its article (Self-Help) is NOT embedded yet
# because the Gemini embedding quota is exhausted; recorded as pending.
check("pending-embedding: The 5 AM Club -> Premium + Drive link",
      "premium_pending",
      "I am looking for the book The 5 AM Club. Do you have it?",
      ["5 AM Club", "Robin Sharma", "Premium Books Library", "drive.google.com"])

# (d) book in none of the catalogues
check("no match: Tafseer Ibn Kathir -> says not in library, invents nothing",
      "no_match",
      "Do you have the book Tafseer Ibn Kathir?",
      ["not in the library"],
      ["Ibn Kathir by", "Tafseer Ibn Kathir —", "drive.google.com/book"])

# --- widget end-to-end: Premium inbox visitor asks for a Best Selling book ---
r = s.get(f"{BASE}/api/v1/inboxes", headers=H)
inbox = next((ib for ib in (r.json().get("data") or [])
              if ib.get("name") == "Premium Books Library"), None)
INBOX_UUID = inbox.get("uuid") if inbox else None
step("Premium Books inbox found", bool(INBOX_UUID), INBOX_UUID or "")
if INBOX_UUID:
    w = requests.Session()
    WH = {"X-Libredesk-Inbox-ID": INBOX_UUID}
    r = w.post(f"{BASE}/api/v1/widget/chat/conversations/init", headers=WH,
               json={"message": "Assalam-o-Alaikum, I am looking for the book ODD HOURS by Dean Koontz.",
                     "subject": "Book search"})
    ok = r.status_code in (200, 201)
    step("visitor starts widget conversation (Premium inbox)", ok, f"{r.status_code} {r.text[:200]}")
    if ok:
        d = data(r)
        CONV_UUID = (d.get("conversation") or {}).get("uuid") or d.get("uuid")
        r = s.put(f"{BASE}/api/v1/conversations/{CONV_UUID}/assignee/user",
                  json={"assignee_id": ASSISTANT_USER_ID}, headers=H)
        step("conversation assigned to AI assistant", r.status_code == 200,
             f"{r.status_code} {r.text[:150]}")
        ai_reply = ""
        for _ in range(40):
            time.sleep(3)
            r = s.get(f"{BASE}/api/v1/conversations/{CONV_UUID}/messages", headers=H)
            d = r.json().get("data", {}) if r.status_code == 200 else {}
            msgs = d.get("results", []) if isinstance(d, dict) else d
            for m in msgs:
                if not isinstance(m, dict):
                    continue
                content = re.sub(r"<[^>]+>", " ", m.get("content") or "")
                if m.get("sender_type") == "agent" and "ODD HOURS" in content:
                    ai_reply = content
                    break
            if ai_reply:
                break
        REPLIES["widget_bs"] = ai_reply
        step("widget: AI names Best Selling Books + Open Library link",
             "ODD HOURS" in ai_reply and "Best Selling Books" in ai_reply
             and "openlibrary.org/isbn/" in ai_reply,
             ai_reply[:400])
        print("  AI REPLY:", ai_reply[:600].replace("\n", " "))

passed = sum(1 for x in results if x["ok"])
print(f"\n==== {passed}/{len(results)} steps passed ====")
with open("phase-4f-test-results.json", "w") as f:
    json.dump(results, f, indent=2, ensure_ascii=False)
with open("phase-4f-ai-replies.json", "w") as f:
    json.dump(REPLIES, f, indent=2, ensure_ascii=False)

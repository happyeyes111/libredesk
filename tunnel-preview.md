# Libredesk live preview — tunnel status

**Date:** 2026-11-17 ~16:05 PKT
**Result: NO public preview link could be created.** The Libredesk app itself is fine (http://localhost:9000 returns 200); only the public exposure is blocked by the VM's network setup.

## What was tried
1. **Server check:** Libredesk up, root 200. VM uptime 1h24m at start — no new reboot.
2. **cloudflared installed:** official linux-amd64 binary, version 2026.11.0, at `~/workspace/libredesk/bin/cloudflared`.
3. **Quick tunnel (`cloudflared tunnel --url http://localhost:9000`): FAILED twice.**
   Error: `failed to request quick Tunnel: Post "https://api.trycloudflare.com/tunnel": tls: first record does not look like a TLS handshake`
   Cause: this VM's internet goes through a shared egress proxy (`hatch-egress-proxy:3128`). Cloudflare's edge WAF blocks `api.trycloudflare.com` from that proxy IP: HTTP 403, body "Your request was blocked" (CF-RAY a5be3e8f781e4b76-SEA).
4. **localtunnel (npm, `--port 9000 --subdomain libredesk-preview`): FAILED.** The client started but exited with no URL — `server.localtunnel.me` is unreachable through the proxy (curl 000).
5. **SSH tunnels (localhost.run / serveo): BLOCKED.** Outbound SSH is reset by the egress proxy (`Connection reset by 198.19.0.1 port 3128`).
6. **Direct internet (no proxy): UNAVAILABLE.** `curl --noproxy '*'` fails for every host (000) — all egress must go through the proxy.
7. **Cloudflare API token: ACTIVE** (`cf.py verify` → status active). `api.cloudflare.com` and `region1.argotunnel.com` are reachable with TLS through the proxy — only `api.trycloudflare.com` is WAF-blocked. But `cf.py accounts` returns an empty list, so no account ID is available here, and no Cloudflare zone/domain is on record — a named tunnel needs both an account ID and a DNS zone for a public hostname.

## What would unblock a public link
- **Option A — named Cloudflare tunnel:** needs the user's Cloudflare account ID + a domain/zone in that account + a token with Tunnel/DNS permissions. The current token is Pages-scoped; it may lack Tunnel permissions.
- **Option B — Tailscale Funnel:** the user has a Tailscale connector; Funnel gives a public `https://…ts.net` URL. Needs tailnet join + Funnel enablement; state would need re-auth after each VM reboot.
- **Option C — retry the quick tunnel later:** the WAF block is tied to the shared proxy IP, so it is unlikely to clear on its own.

## Files
- cloudflared binary: `~/workspace/libredesk/bin/cloudflared`
- Logs: `~/workspace/libredesk/tunnel.log`, `tunnel2.log`, `lt.log`

## Restart (if a link is ever established)
- Quick tunnel: `cd ~/workspace/libredesk && ./bin/cloudflared tunnel --url http://localhost:9000`
- The tunnel dies on VM reboot and must be restarted; the URL changes each time (quick tunnels are random).
- The link is public but login still needs the Libredesk System password. Never announce or publish Libredesk — preview only, for the user himself.

#!/bin/bash
# Start/stop/status for the Gemini forwarding proxy (gemini-proxy.py).
# The proxy listens on 127.0.0.1:18080 and forwards Libredesk's AI requests
# to Gemini via the stored custom.gemini credential (surrogate-swapped on
# egress). No API key value is ever stored in this script or its logs.
set -u
cd ~/workspace/libredesk
PIDFILE=phase-4-proxy.pid
LOG=phase-4-proxy.log

start() {
    if [ -f "$PIDFILE" ] && kill -0 "$(cat "$PIDFILE")" 2>/dev/null; then
        echo "proxy already running (PID $(cat "$PIDFILE"))"
        exit 0
    fi
    setsid nohup python3 gemini-proxy.py >> "$LOG" 2>&1 < /dev/null &
    echo $! > "$PIDFILE"
    for _ in $(seq 1 20); do
        if curl -s -o /dev/null http://127.0.0.1:18080/healthz; then
            echo "proxy up (PID $(cat "$PIDFILE"))"
            exit 0
        fi
        sleep 0.5
    done
    echo "proxy did not come up; see $LOG"
    exit 1
}

stop() {
    if [ -f "$PIDFILE" ]; then
        kill "$(cat "$PIDFILE")" 2>/dev/null || true
        rm -f "$PIDFILE"
        echo "proxy stopped"
    else
        echo "proxy not running (no pidfile)"
    fi
}

status() {
    if [ -f "$PIDFILE" ] && kill -0 "$(cat "$PIDFILE")" 2>/dev/null; then
        echo "proxy running (PID $(cat "$PIDFILE"))"
        curl -s http://127.0.0.1:18080/healthz; echo
    else
        echo "proxy not running"
    fi
}

case "${1:-status}" in
    start) start ;;
    stop) stop ;;
    status) status ;;
    *) echo "usage: $0 start|stop|status" ;;
esac

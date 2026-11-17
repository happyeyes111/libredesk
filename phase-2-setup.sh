#!/bin/bash
# Phase 2 setup: Go 1.27.3 + pnpm 11.28.8 + PostgreSQL 16 + Redis 7
# Log: ~/workspace/libredesk/phase-2-setup.log
set -u
TOOLS="$HOME/workspace/tools"
mkdir -p "$TOOLS"
export PATH="$TOOLS/go/bin:$HOME/.local/bin:$PATH"

echo "===== [1] Go 1.27.3 ====="
if [ -x "$TOOLS/go/bin/go" ]; then
  echo "Go already present"
else
  cd "$TOOLS"
  curl -fL -o go1.27.3.linux-amd64.tar.gz https://go.dev/dl/go1.27.3.linux-amd64.tar.gz
  tar -xzf go1.27.3.linux-amd64.tar.gz
  rm -f go1.27.3.linux-amd64.tar.gz
fi
"$TOOLS/go/bin/go" version

echo "===== [2] pnpm 11.28.8 via corepack ====="
export COREPACK_ENABLE_DOWNLOAD_PROMPT=0
corepack enable || true
corepack prepare pnpm@11.28.8 --activate || npm install -g pnpm@11.28.8
pnpm --version
node --version

echo "===== [3] apt: postgresql + redis ====="
export DEBIAN_FRONTEND=noninteractive
apt-get update -qq
apt-get install -y -qq postgresql redis-server openssl
pg_lsclusters || true
redis-server --version
psql --version || true

echo "===== [4] start postgres cluster + redis ====="
pg_ctlcluster 16 main start || pg_ctlcluster 16 main restart || service postgresql start || true
pg_lsclusters
redis-server --daemonize yes --port 6379 --save '' --appendonly no --protected-mode no || true
sleep 2
redis-cli ping || true
su postgres -c "psql -tc \"SELECT version();\"" || true

echo "===== DONE ====="
"$TOOLS/go/bin/go" version
pnpm --version
node --version

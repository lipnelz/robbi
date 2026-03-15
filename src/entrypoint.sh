#!/bin/sh
set -eu

cd /app

if ! git pull origin main; then
    echo "[WARN] git pull failed, starting with local code." >&2
fi

exec python src/main.py

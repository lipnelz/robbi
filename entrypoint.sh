#!/bin/sh
set -e

cd /app

echo "[INFO] Starting Robbi bot..."
echo "[INFO] Attempting to pull latest code from origin/main..."

# Configure git credentials if GIT_TOKEN is set (for CI/CD or secure token storage)
if [ -n "${GIT_TOKEN:-}" ]; then
    echo "[INFO] Using GIT_TOKEN for authentication..."
    git remote set-url origin "https://${GIT_TOKEN}@github.com/lipnelz/robbi.git"
fi

# Try to pull latest changes
if git pull origin main --rebase; then
    echo "[INFO] Successfully pulled latest code from origin/main"
else
    EXIT_CODE=$?
    echo "[WARN] git pull failed with exit code $EXIT_CODE, starting with local code..." >&2
    echo "[WARN] Make sure GitHub credentials are configured (SSH key or GIT_TOKEN env var)" >&2
fi

# Log current state
echo "[INFO] Current commit: $(git rev-parse --short HEAD)"
echo "[INFO] Branch: $(git rev-parse --abbrev-ref HEAD)"
echo "[INFO] Repository: $(git remote get-url origin)"

echo "[INFO] Starting application..."
exec python src/main.py

#!/bin/sh
set -e

cd /app

echo "[INFO] Starting Robbi bot..."
echo "[INFO] Attempting to synchronize with origin/main..."

# Configure git credentials if GIT_TOKEN is set (for CI/CD or secure token storage)
if [ -n "${GIT_TOKEN:-}" ]; then
    echo "[INFO] Using GIT_TOKEN for authentication..."
    git remote set-url origin "https://${GIT_TOKEN}@github.com/lipnelz/robbi.git"
fi

# Fetch latest changes from remote
if git fetch origin main 2>/dev/null; then
    echo "[INFO] Fetched latest commits from origin/main"
    
    # Reset to remote version (handles divergent branches gracefully)
    if git reset --hard origin/main 2>/dev/null; then
        echo "[INFO] Successfully synchronized with origin/main (reset to remote)"
    else
        echo "[WARN] Could not reset to origin/main, trying to continue..." >&2
    fi
else
    echo "[WARN] Could not fetch from origin, using current local code..." >&2
fi

# Clean any leftover uncommitted changes
git clean -fd 2>/dev/null || true

# Log current state
COMMIT=$(git rev-parse --short HEAD 2>/dev/null || echo "unknown")
BRANCH=$(git rev-parse --abbrev-ref HEAD 2>/dev/null || echo "unknown")

echo "[INFO] Current commit: $COMMIT"
echo "[INFO] Branch: $BRANCH"

echo "[INFO] Starting application..."
exec python src/main.py

# Git Pull Configuration for Robbi Bot

## Overview

When the Robbi bot container restarts (via `docker restart robbi-container` or `docker compose up`), the `entrypoint.sh` script automatically executes a `git pull origin main` to fetch the latest code from GitHub.

## How It Works

```
docker restart robbi-container
    ↓
entrypoint.sh executes (inside container)
    ↓
[1] Configure git credentials (if GIT_TOKEN is set)
    ↓
[2] git pull origin main --rebase
    ↓
[3] Log current commit/branch/remote
    ↓
[4] python src/main.py starts (using latest code)
```

## Configuration Options

### Option 1: GitHub Personal Access Token (PAT) - Recommended

**Advantages:**
- Works without SSH setup
- Can set expiration date
- Easy to revoke if compromised
- Works in containerized environment

**Setup:**

1. **Create a PAT on GitHub:**
   - Go to: https://github.com/settings/tokens/new
   - Select scopes: `repo` (full control of private repositories)
   - Copy the token (you won't see it again)

2. **Before starting the bot, set the environment variable:**
   ```bash
   export GIT_TOKEN=ghp_xxxxxxxxxxxxxxxxxxxxxxxxxxxx
   
   # Then start the bot
   docker compose up -d
   ```

3. **Or, add it to your `.env` file:**
   ```bash
   # .env file in the project root
   GIT_TOKEN=ghp_xxxxxxxxxxxxxxxxxxxxxxxxxxxx
   ```
   
   Docker Compose will automatically load it.

4. **Verify it works:**
   ```bash
   docker logs robbi-container | grep -E "git pull|Successfully pulled|branch:"
   ```

### Option 2: SSH Key Setup (Advanced)

**Advantages:**
- More secure (no tokens in environment)
- No expiration management
- Preferred by security experts

**Setup:**

1. **Generate SSH key (if not exists):**
   ```bash
   ssh-keygen -t ed25519 -f ~/.ssh/id_github -C "robbi@local"
   ```

2. **Add to GitHub:**
   - Copy public key: `cat ~/.ssh/id_github.pub`
   - Go to: https://github.com/settings/keys
   - Click "New SSH key" and paste

3. **Configure git to use SSH:**
   ```bash
   git remote set-url origin git@github.com:lipnelz/robbi.git
   ```

4. **Mount SSH key into container** (update docker-compose.yml):
   ```yaml
   volumes:
     - ~/.ssh/id_github:/app/.ssh/id_github:ro
     - ~/.ssh/known_hosts:/app/.ssh/known_hosts:ro
   ```

5. **Configure git inside container** (add to entrypoint.sh):
   ```bash
   export GIT_SSH_COMMAND="ssh -i /app/.ssh/id_github -o StrictHostKeyChecking=no"
   ```

### Option 3: Git Credential Helper (For Development Only)

**Advantages:**
- Interactive, developer-friendly
- Caches credentials locally

**Setup:**

```bash
# On the host machine
git config --global credential.helper cache
git config --global credential.helper 'cache --timeout=3600'

# First git command will prompt for credentials, then cache them
cd /home/lipnel/Git/robbi
git pull  # Enter username and password/token once
```

**Note:** This works on the host but NOT inside the container for automated pulls.

## Testing the Configuration

### Test 1: Verify git pull works manually

```bash
cd /home/lipnel/Git/robbi

# Simulate what entrypoint.sh does
export GIT_TOKEN=ghp_xxxxxxxxxxxxxxxxxxxxxxxxxxxx
git remote set-url origin "https://${GIT_TOKEN}@github.com/lipnelz/robbi.git"
git pull origin main --rebase
```

### Test 2: Check container logs on startup

```bash
# Restart the container and watch logs
docker restart robbi-container
docker logs -f robbi-container

# Look for these lines:
# [INFO] Starting Robbi bot...
# [INFO] Attempting to pull latest code from origin/main...
# [INFO] Successfully pulled latest code from origin/main
# [INFO] Current commit: abc1234
# [INFO] Branch: main
```

### Test 3: Verify latest code is running

```bash
# Make a test commit on a branch
cd /home/lipnel/Git/robbi
git checkout -b test-update
echo "# Test $(date)" >> README.md
git add README.md
git commit -m "test: verify git pull works"
git checkout main
git merge test-update
git push origin main

# Now restart the bot
docker restart robbi-container

# Verify the new code is loaded
docker logs robbi-container | grep "Successfully pulled"
```

## Troubleshooting

### Problem: "git pull failed" warning in logs

**Causes:**
1. GIT_TOKEN not set or invalid
2. GitHub credentials not configured
3. Network connectivity issue
4. Credentials have expired

**Solutions:**

```bash
# Check if GIT_TOKEN is set
docker exec robbi-container env | grep GIT_TOKEN

# Check git remote configuration
docker exec robbi-container git remote -v

# Try manual git pull with verbose output
docker exec robbi-container git pull -v origin main

# Check network connectivity to GitHub
docker exec robbi-container curl -I https://github.com
```

### Problem: "fatal: Authentication failed"

**Cause:** Token is invalid or expired

**Solution:**
1. Generate a new token: https://github.com/settings/tokens/new
2. Update GIT_TOKEN environment variable
3. Restart the container

### Problem: Container starts but code isn't updated

**Cause:** git pull succeeded but container still has old code

**Solution:**
1. Rebuild the container: `docker compose build --no-cache robbi`
2. Restart: `docker compose up -d robbi`
3. Check logs: `docker logs robbi-container`

## Production Considerations

### Security Best Practices

1. **Never commit tokens to git:**
   ```bash
   # Add to .gitignore
   echo ".env" >> .gitignore
   ```

2. **Use environment variables or secrets manager:**
   ```bash
   # Use .env file (git-ignored)
   GIT_TOKEN=ghp_xxxx
   
   # Or use Docker secrets (production)
   docker secret create git_token -
   ```

3. **Rotate tokens regularly:**
   - Set expiration on GitHub PAT
   - Update every 90 days

4. **Use SSH keys for maximum security** (production)
   - No tokens in environment variables
   - Can be revoked per key
   - Better auditability

### Automated CI/CD Integration

If using GitHub Actions or similar CI/CD:

```yaml
# .github/workflows/deploy.yml
name: Deploy Robbi
on:
  push:
    branches: [main]

jobs:
  deploy:
    runs-on: self-hosted
    steps:
      - uses: actions/checkout@v3
      - name: Start Robbi Bot
        env:
          GIT_TOKEN: ${{ secrets.GITHUB_TOKEN }}
        run: docker compose up -d
```

## Commands Reference

```bash
# Start bot (git pull happens automatically)
docker compose up -d

# Restart bot (git pull happens automatically)
docker restart robbi-container

# Check if git pull succeeded
docker logs robbi-container | grep -A2 "Successfully pulled"

# Manually trigger git pull inside container
docker exec robbi-container git pull origin main --rebase

# Show current commit
docker exec robbi-container git rev-parse --short HEAD

# Show current branch
docker exec robbi-container git rev-parse --abbrev-ref HEAD
```

## Summary

| Method | Security | Setup Time | Automation | Recommended For |
|--------|----------|------------|-----------|-----------------|
| PAT in .env | Medium | 5 min | ✅ Yes | Development |
| SSH Key | High | 15 min | ✅ Yes | Production |
| Git Credential | Low | 2 min | ❌ No | Manual only |

**Recommendation:** Use **Personal Access Token (.env file)** for development, **SSH Key** for production.

# 🔒 Security Audit Report - Robbi Telegram Bot

**Date:** 2024-11-07  
**Scope:** Complete Robbi application including source code, dependencies, Docker configuration  
**Severity:** 6 issues identified (2 CRITICAL, 4 HIGH, 2 MEDIUM)  
**Risk Level:** 🔴 **HIGH** - Immediate action required

---

## Executive Summary

The Robbi Telegram bot has **6 security vulnerabilities** that require immediate remediation:

- **2 CRITICAL** vulnerabilities involving hardcoded credentials and token exposure
- **4 HIGH** severity issues related to Docker security, TLS validation, and data exposure
- **2 MEDIUM** issues around error handling and input validation

**Risk Assessment:** An attacker who compromises the application or container gains access to:
- Real Telegram bot token (can control the bot and read all messages)
- Ninja API credentials (can steal cryptocurrency price data / billing)
- Massa wallet credentials and addresses
- Full access to Docker daemon (can escape container, compromise host)

**Recommendation:** Fix critical issues immediately before any production use.

---

## Security Findings Summary

| # | Severity | File | Issue | Lines |
|---|----------|------|-------|-------|
| 1 | 🔴 **CRITICAL** | topology.json | Hardcoded credentials (tokens, keys, passwords) | All |
| 2 | 🔴 **CRITICAL** | entrypoint.sh | GIT_TOKEN exposed in command line / process list | 9-12 |
| 3 | 🟠 **HIGH** | docker-compose.yml | Docker socket mounted without restrictions | 12 |
| 4 | 🟠 **HIGH** | Dockerfile | Container running as root user | None (missing USER) |
| 5 | 🟠 **HIGH** | src/services/http_client.py | No explicit SSL/TLS certificate verification | 17 |
| 6 | 🟠 **HIGH** | src/main.py, topology.json | Telegram token in memory and logs | 137 |
| 7 | 🟡 **MEDIUM** | src/services/docker_manager.py | Information disclosure via error messages | 161 |
| 8 | 🟡 **MEDIUM** | src/handlers/node.py | Missing input validation on container names | Config |

---

## Detailed Findings

### 🔴 CRITICAL Issue #1: Hardcoded Credentials in topology.json

**Severity:** 🔴 CRITICAL | **Confidence:** 10/10

**Location:** `/home/lipnel/Git/robbi/topology.json` (and copied into Docker image)

**Problem:**
Real, working credentials are stored in plaintext:
```json
{
    "telegram_bot_token": "7763237944:AAHOhFVJ4VdyXcX6uyRiPjm3Z8raZsnyHhA",
    "ninja_api_key": "vJlIx82oAkq0xhcVxLPN5g==tqg9i9mMbRaY0mKz",
    "massa_client_password": "5dioeY8H",
    "massa_wallet_address": "AU12s7K5yCmp1QWnezktR5bhBS5XtTdpCsBsgSCVimY4sKmtbmea2"
}
```

**Risk:**
- While in .gitignore locally, the file is **copied into the Docker image** (Dockerfile line 34: `COPY topology.json /app/`)
- Accessible to any process in the container
- Exposed if container is compromised via RCE
- Visible in docker inspect, exec history, or logs
- Real credentials mean attackers can immediately abuse them

**Impact:**
- **Telegram:** Attacker controls bot, reads all user messages, can send commands
- **Ninja API:** Attacker can steal price feed data, drain API quota, cause service disruption
- **Massa Wallet:** Attacker can steal funds, spam network, compromise node

**Fix:**
```bash
# 1. Move to environment variables
export TELEGRAM_BOT_TOKEN="..."
export NINJA_API_KEY="..."
export MASSA_CLIENT_PASSWORD="..."
export MASSA_WALLET_ADDRESS="..."

# 2. Update Python code (src/main.py)
import os
bot_token = os.environ.get('TELEGRAM_BOT_TOKEN')
ninja_key = os.environ.get('NINJA_API_KEY')
massa_password = os.environ.get('MASSA_CLIENT_PASSWORD')

# 3. Remove from Dockerfile
# Remove: COPY topology.json /app/

# 4. Load only node config (no credentials)
with open('/app/topology_template.json') as f:
    config = json.load(f)
```

**Timeline:** 🚨 **IMMEDIATE - Fix before any production deployment**

---

### 🔴 CRITICAL Issue #2: GIT_TOKEN Exposed in Command Line

**Severity:** 🔴 CRITICAL | **Confidence:** 9/10

**Location:** `/home/lipnel/Git/robbi/entrypoint.sh` (lines 9-12)

**Problem:**
```bash
if [ -n "${GIT_TOKEN:-}" ]; then
    echo "[INFO] Using GIT_TOKEN for authentication..."
    git remote set-url origin "https://${GIT_TOKEN}@github.com/lipnelz/robbi.git"
fi
```

The token is embedded in the URL where it:
1. **Appears in process list:** `ps aux | grep git` shows the full URL with token
2. **Stored in shell history:** If command is logged, token persists
3. **Visible in docker logs:** Token shows up in container logs
4. **Exposed in git debug output:** Git may log operations with URL
5. **Survives container inspection:** `docker inspect` might reveal environment

**Risk:**
- Any process with access to the container (or host with docker access) can capture the token
- Token gives full GitHub repository access
- Can push malicious code, create branches, delete repository

**Fix:**
```bash
# WRONG (current):
git remote set-url origin "https://${GIT_TOKEN}@github.com/lipnelz/robbi.git"

# RIGHT (use credential helper):
echo "${GIT_TOKEN}" | git -c credential.helper=store fetch origin main

# OR BETTER (use SSH):
git remote set-url origin git@github.com:lipnelz/robbi.git
# Mount SSH key: volumes: ["~/.ssh/id_rsa:/app/.ssh/id_rsa:ro"]
```

**Timeline:** 🚨 **IMMEDIATE - Rotate current token after fixing**

---

### 🟠 HIGH Issue #3: Docker Socket Mounted Without Restrictions

**Severity:** 🟠 HIGH | **Confidence:** 9/10

**Location:** `/home/lipnel/Git/docker-compose.yml` (line 12)

**Problem:**
```yaml
volumes:
  - /var/run/docker.sock:/var/run/docker.sock
```

This mount allows the container to:
1. Execute ANY Docker command (start, stop, delete containers)
2. Access **all containers** on the host
3. Access the **entire host filesystem** through other containers
4. **Escalate privileges to root** on the host
5. Create containers with host mounts for complete compromise

**Risk:**
Combined with the above vulnerabilities, if attacker compromises the bot (RCE), they gain:
- Full host access via Docker API
- Ability to steal credentials from other containers
- Ability to modify/delete other services
- Ability to persist backdoor (create container at startup)

**Proof of Concept:**
```python
# If bot is compromised with RCE:
import docker
client = docker.from_env()  # Uses /var/run/docker.sock

# 1. List all containers and inspect their volumes
for container in client.containers.list():
    print(container.name, container.attrs['Mounts'])
    # Attacker can now access any mounted volumes

# 2. Start malicious container with host filesystem
container = client.containers.run(
    "ubuntu",
    "/bin/bash",
    volumes={"/": "/host"}
)
# Now can read/write entire host filesystem

# 3. Persist backdoor
client.containers.run(
    "malicious-image",
    restart_policy={"Name": "always"},
    detach=True
)
# Backdoor runs forever
```

**Fix:**
```yaml
# Option 1: Remove if not needed
# (Remove the docker.sock volume mount entirely)

# Option 2: Use docker socket proxy with restricted API
volumes:
  - /var/run/docker.sock:/var/run/docker.sock:ro  # Read-only
security_opt:
  - no-new-privileges:true

# Option 3: Use a restricted proxy (recommended)
# Use something like docker-socket-proxy
services:
  docker-proxy:
    image: tecnativa/docker-socket-proxy
    volumes:
      - /var/run/docker.sock:/var/run/docker.sock
    environment:
      - CONTAINERS=1  # Only allow container access
      - POST=0  # No write access
  
  robbi:
    depends_on:
      - docker-proxy
    volumes:
      - docker-proxy:/var/run/docker.sock  # Use proxy instead
```

**Timeline:** ⚠️ **URGENT - Fix before production**

---

### 🟠 HIGH Issue #4: Container Running as Root

**Severity:** 🟠 HIGH | **Confidence:** 9/10

**Location:** `/home/lipnel/Git/robbi/Dockerfile` (missing USER directive)

**Problem:**
No USER directive in Dockerfile, so Python process runs as **root (uid 0)**.

Combined with Issues #1-3:
- If RCE occurs, attacker has root inside container
- Can modify any file, install backdoors, bypass restrictions
- Can escape container via Docker socket (Issue #3)
- Can escalate to host root

**Fix:**
Add to Dockerfile after pip install:
```dockerfile
# Create non-root user
RUN useradd -m -u 1000 -s /bin/bash robbi && \
    chown -R robbi:robbi /app

# Switch to non-root user
USER robbi

# Default command
ENTRYPOINT ["/app/entrypoint.sh"]
```

Also update entrypoint.sh permissions:
```bash
# Allow robbi user to execute
RUN chmod 755 /app/entrypoint.sh
```

**Timeline:** ⚠️ **URGENT - Critical for preventing privilege escalation**

---

### 🟠 HIGH Issue #5: Missing SSL/TLS Certificate Verification

**Severity:** 🟠 HIGH | **Confidence:** 8/10

**Location:** `/home/lipnel/Git/robbi/src/services/http_client.py` (line 17)

**Problem:**
```python
def safe_request(logger, method: str, url: str, **kwargs) -> dict:
    response = requests.request(method, url, timeout=20, **kwargs)
    # No explicit verify=True
```

While `verify=True` is default in requests library, it's not explicitly enforced. Risk if:
1. Developer passes `verify=False` to disable (can happen)
2. Underlying library changes default
3. Man-in-the-middle attack on local network
4. Compromised DNS/network

This impacts:
- Massa RPC endpoint calls (node status, addresses)
- Ninja API calls (price data)
- Any HTTP operations

**Fix:**
```python
def safe_request(logger, method: str, url: str, **kwargs) -> dict:
    # Enforce certificate verification
    kwargs.setdefault('verify', True)
    
    try:
        response = requests.request(method, url, timeout=20, **kwargs)
        return response.json()
    except Exception as e:
        logger.error(f"Request failed: {e}")
        return {}
```

**Timeline:** ⚠️ **HIGH - Fix before production**

---

### 🟠 HIGH Issue #6: Telegram Token in Memory and Logs

**Severity:** 🟠 HIGH | **Confidence:** 8/10

**Location:** `/home/lipnel/Git/robbi/src/main.py` (line 137), `/home/lipnel/Git/robbi/topology.json`

**Problem:**
Bot token is:
1. Stored in `bot_data` for entire process lifetime
2. Exposed if exception traceback is logged
3. Could appear in debug output of python-telegram-bot library
4. Persists in memory if process is dumped/inspected

**Risk:**
- Memory dump attack reveals token
- Exception traceback exposes token
- Logging library might serialize bot_data

**Fix:**
```python
# WRONG: Storing token in data
application.bot_data['telegram_token'] = token

# RIGHT: Never store credentials in data structures
# Only store token in separate, protected variable
# Never pass to logger or serialize to logs

# Add custom exception handler:
async def error_handler(update, context):
    """Log error but don't expose credentials"""
    logger.error(
        f"Update {update} caused error",
        exc_info=True
    )
    # Don't send token to logs
    # Don't include in error message to users
```

**Timeline:** ⚠️ **HIGH - Implement with credential refactoring**

---

### 🟡 MEDIUM Issue #7: Information Disclosure via Error Messages

**Severity:** 🟡 MEDIUM | **Confidence:** 7/10

**Location:** Multiple files - `docker_manager.py` (line 161), `node.py`, `deployment.py`

**Problem:**
```python
# WRONG: Exposing internal details to users
await query.edit_message_text(text=f"❌ Error: {str(e)}")

# Examples of exposed information:
# "Error: Unable to connect to /var/run/docker.sock: Permission denied"
# "Error: KeyError 'telegram_token' in bot_data"
# "Error: [Errno 2] No such file or directory: '/massa/path...'"
```

Error messages reveal:
- System paths (/var/run, /app, etc.)
- Internal structure (bot_data keys)
- Configuration details
- Environment hints

**Fix:**
```python
try:
    # operation
except Exception as e:
    # Log full details internally
    logger.error(f"Operation failed: {e}", exc_info=True)
    
    # Show generic message to user
    await query.edit_message_text(
        text="❌ Operation failed. Please try again or contact admin."
    )
```

**Timeline:** ⏳ **MEDIUM - Fix during next deployment**

---

### 🟡 MEDIUM Issue #8: Missing Input Validation on Container Names

**Severity:** 🟡 MEDIUM | **Confidence:** 7/10

**Location:** `/home/lipnel/Git/robbi/src/handlers/node.py`, configuration

**Problem:**
Container names loaded from config are used directly:
```python
container = client.containers.get(container_name)
```

If configuration is modified (by attacker with file access), they could:
1. Reference a different container
2. Access containers from other services
3. Trigger operations on critical infrastructure

**Fix:**
```python
ALLOWED_CONTAINERS = {
    'robbi-container': 'robbi',
    'massa-container': 'massa'
}

container_name = ALLOWED_CONTAINERS.get(container_name)
if not container_name:
    raise ValueError(f"Invalid container: {container_name}")

container = client.containers.get(container_name)
```

**Timeline:** ⏳ **MEDIUM - Add during hardening phase**

---

## Recommended Fixes - Priority Order

### 🚨 PHASE 1: IMMEDIATE (Critical - Do First)

**Time Estimate:** 30-60 minutes

1. **Remove hardcoded credentials from topology.json**
   - Create `topology.json` with only node configuration (no credentials)
   - Update all credential loading to use environment variables
   - Test with .env file

2. **Fix GIT_TOKEN exposure**
   - Change entrypoint.sh to use SSH or credential helper
   - Remove token from URL string
   - Update docker-compose.yml to use SSH key instead

**Files to modify:**
- `topology.json` - Remove all credentials
- `src/main.py` - Load from environment variables
- `entrypoint.sh` - Use SSH or safe credential helper
- `docker-compose.yml` - Add SSH key mount, remove GIT_TOKEN

### ⚠️ PHASE 2: URGENT (High - Do Next)

**Time Estimate:** 1-2 hours

3. **Add USER directive to Dockerfile**
   - Create non-root user
   - Fix file permissions
   - Test that app still runs

4. **Restrict Docker socket access**
   - Either remove mount or use restricted proxy
   - Add security options
   - Test Docker operations

5. **Enforce SSL verification**
   - Update http_client.py
   - Add explicit `verify=True`
   - Test all HTTP endpoints

**Files to modify:**
- `Dockerfile` - Add USER directive
- `docker-compose.yml` - Remove/restrict docker.sock, add security_opt
- `src/services/http_client.py` - Add explicit verification

### ✏️ PHASE 3: HARDENING (Medium - Do Before Production)

**Time Estimate:** 1 hour

6. **Sanitize error messages**
   - Update error handlers across app
   - Log full details internally only
   - Show generic messages to users

7. **Add input validation for container names**
   - Create whitelist of allowed containers
   - Validate before use
   - Add assertions

**Files to modify:**
- `src/services/docker_manager.py`
- `src/handlers/node.py`
- `src/handlers/deployment.py`

---

## Implementation Checklist

### Phase 1: Critical Credentials (IMMEDIATE)

- [ ] Create `topology.json` without credentials
- [ ] Update `src/main.py` to load from environment variables
- [ ] Test with `.env` file locally
- [ ] Update `docker-compose.yml` with environment variable setup
- [ ] Update `entrypoint.sh` to use SSH or credential helper
- [ ] Generate new tokens/credentials (old ones were visible in this audit)
- [ ] Test bot starts successfully with new credentials method
- [ ] Commit changes and push to GitHub

### Phase 2: Docker Security (URGENT)

- [ ] Add USER directive to Dockerfile
- [ ] Create non-root user and fix permissions
- [ ] Rebuild Docker image
- [ ] Test application runs as non-root user
- [ ] Remove or restrict Docker socket mount
- [ ] Add security options to docker-compose.yml
- [ ] Test Docker operations still work
- [ ] Restart and verify functionality

### Phase 3: Certificate Verification (URGENT)

- [ ] Update http_client.py to explicitly set verify=True
- [ ] Test all HTTP requests (Massa RPC, Ninja API)
- [ ] Verify no certificates are disabled anywhere
- [ ] Add test for SSL verification

### Phase 4: Error Handling (HARDENING)

- [ ] Update all exception handlers to show generic messages
- [ ] Ensure full error details logged internally
- [ ] Test error scenarios show no sensitive info
- [ ] Review all user-facing error messages

### Phase 5: Input Validation (HARDENING)

- [ ] Add container name whitelist
- [ ] Add validation function
- [ ] Update all container.get() calls to use validation
- [ ] Add unit tests for validation

### Final Verification

- [ ] Run full test suite
- [ ] Manually test all bot commands
- [ ] Verify no credentials in logs
- [ ] Verify non-root execution
- [ ] Verify Docker operations work
- [ ] Get security re-review or internal test

---

## Testing After Fixes

```bash
# Verify environment variables work
export TELEGRAM_BOT_TOKEN="test_token_xxx"
export NINJA_API_KEY="test_key_xxx"
docker compose up

# Check no credentials in logs
docker logs robbi-container | grep -i token
docker logs robbi-container | grep -i password
# Should return nothing

# Verify running as non-root
docker exec robbi-container whoami
# Should return: robbi (not root)

# Verify SSL verification
docker exec robbi-container python -c "import requests; requests.get('https://httpbin.org/get', verify=True)"
# Should succeed without SSL warnings

# Verify error messages don't leak info
# Trigger error and check message
docker logs robbi-container | grep "Error"
# Should show generic messages, not paths/keys
```

---

## Long-term Security Improvements

1. **Secret Management System**
   - Use HashiCorp Vault, AWS Secrets Manager, or similar
   - Rotate credentials automatically
   - Audit credential access

2. **Runtime Security Monitoring**
   - Use Falco or similar to detect suspicious activity
   - Monitor process execution, file access, network connections
   - Alert on policy violations

3. **Container Security Scanning**
   - Use Trivy, Grype, or similar to scan for vulnerabilities
   - Scan base images and all dependencies
   - Integrate into CI/CD pipeline

4. **Network Isolation**
   - Run container on restricted network
   - Limit outbound connections to required endpoints only
   - Use network policies to restrict communication

5. **Regular Audits**
   - Perform security audit quarterly
   - Review dependencies for vulnerabilities
   - Update this report with findings

---

## References & Tools

- **OWASP Top 10:** https://owasp.org/www-project-top-ten/
- **CWE-798 (Hardcoded Credentials):** https://cwe.mitre.org/data/definitions/798.html
- **CWE-522 (Credentials in Logs):** https://cwe.mitre.org/data/definitions/522.html
- **Docker Security Best Practices:** https://docs.docker.com/engine/security/
- **Trivy (Container Scanning):** https://aquasecurity.github.io/trivy/
- **Git Credential Manager:** https://git-scm.com/book/en/v2/Git-Tools-Credential-Storage

---

## Sign-off

**Audit Completed:** 2024-11-07  
**Auditor:** Security Review Agent  
**Status:** 🔴 NOT PRODUCTION READY - Critical fixes required

**Next Steps:**
1. Implement Phase 1 fixes (IMMEDIATE - 30-60 min)
2. Implement Phase 2 fixes (URGENT - 1-2 hours)
3. Implement Phase 3-4 fixes (HARDENING - 1 hour)
4. Request security re-review before production deployment
5. Implement long-term security improvements

---

*This audit was performed on 2024-11-07. All findings are based on code analysis at that date. Please update this report if any findings have been remediated.*

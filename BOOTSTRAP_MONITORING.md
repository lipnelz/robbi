# Bootstrap Monitoring Feature

## Overview

The bootstrap monitoring feature provides real-time visibility into the Massa node's bootstrap progress via the `/status` Telegram command. When the node is starting and connecting to the network, users get detailed information about:

- **Bootstrap state**: whether bootstrap is in progress, complete, or failed
- **Progress percentage**: estimated progress based on server attempts
- **Current server**: which bootstrap server is currently being tried
- **Time information**: elapsed time since bootstrap start and estimated retry delays
- **Error details**: specific error messages from bootstrap server interactions

## How It Works

### Log Parsing

The feature works by parsing the node container's Docker logs for bootstrap-related messages. It looks for patterns like:

```
INFO massa_bootstrap::client: Start bootstrapping from 198.27.74.5:31245
WARN massa_bootstrap::client: Error while bootstrapping: ...
INFO massa_bootstrap::client: Bootstrap from server ... failed. Your node will try to bootstrap from another server in Xm.
INFO massa_bootstrap::client: Successful bootstrap
```

### Progress Calculation

Progress is estimated as:
- **0%**: No bootstrap attempts detected
- **1-99%**: Based on number of server attempts / 9 possible servers
- **100%**: "Successful bootstrap" message found in logs

### State Detection

- **bootstrapping**: Bootstrap is in progress (attempts found, no completion message)
- **complete**: "Successful bootstrap" or "State bootstrap complete" detected
- **failed**: Bootstrap marked as failed (future feature)
- **unknown**: Unable to read logs or parse them

## Usage

### Command

```
/status
```

### Example Output

**While bootstrapping:**
```
🔎 État du nœud Massa
État du conteneur : running
État de santé : unhealthy
⏳ Bootstrap en cours: [▓▓░░░░░░░░] 22%
   Serveur actuel: 198.27.74.5
   Temps écoulé: 5m 30s
   Nouvelle tentative dans: 1m
   ⚠️ Erreur: Signature verification failed...
📡 RPC Massa : ...
```

**After successful bootstrap:**
```
🔎 État du nœud Massa
État du conteneur : running
État de santé : healthy
✅ Bootstrap terminé
📡 RPC Massa : Mode : validateur
```

## Rate Limiting and Retry Logic

Bootstrap servers implement rate limiting:
- Each public IP can bootstrap from a server once every ~12 hours
- If all servers are rate-limited, the node waits ~1 minute between attempts
- The node cycles through servers until one becomes available

This is normal behavior. Users can monitor:
- **Attempt count**: How many servers have been tried
- **Retry timing**: When the next attempt will occur
- **Error messages**: Specific rate-limit or connection errors

## Technical Details

### File Locations

- **Service**: `src/services/bootstrap_monitor.py`
  - `get_bootstrap_status()`: Parse logs and extract status
  - `format_bootstrap_status()`: Format status for user display

- **Handler**: `src/handlers/node_status.py`
  - Integrated into `/status` command
  - Gracefully handles Docker/access errors

- **Tests**: `tests/test_services_bootstrap_monitor.py`
  - 10 unit tests covering parsing, formatting, error cases

### Regex Patterns

Key patterns used:
- Server attempts: `INFO.*bootstrap::client: Start bootstrapping from ([\w.:[\]]+)`
- Retry timing: `will try to bootstrap from another server in (\d+)m`
- Errors: Lines with `WARN` and `bootstrap` keywords
- Completion: `Successful bootstrap` or `State bootstrap complete`

### Error Handling

- **Docker access failure**: Shows "État de bootstrap : inconnu"
- **Empty logs**: Shows unknown state
- **Parse errors**: Logged at debug level, state shows "unknown"
- **Container not running**: Bootstrap info not displayed

## Integration with Node Status

The bootstrap status appears in this order:

1. Container state (running/exited/etc)
2. **Bootstrap status** (only if running)
3. RPC status (node sync/validator mode)

This provides the full picture of node health and progress.

## Future Improvements

### 1. Predictive Time Remaining

When rate-limited, parse error messages to show estimated wait time:
```
⚠️ Rate-limited on this server
Retry available in: 8h 20m
Next server attempt in: 1m
```

### 2. Bootstrap Statistics

Track statistics across restarts:
- Average bootstrap time
- Success rate per server
- Most common errors

### 3. Alerts

Notify user if:
- Bootstrap fails 3x in a row
- Bootstrap takes >30 minutes
- All servers are rate-limited

### 4. Manual Retry Option

Add command to:
- Force restart bootstrap (with ledger clearing)
- Switch to specific server
- Force IP detection and update

## Troubleshooting

### Bootstrap stuck on one server

**Symptom**: Same server keeps appearing for many attempts

**Cause**: Usually server connection issues

**Solution**: Wait for automatic retry rotation (1-2 min)

### All servers rate-limited

**Symptom**: Errors like "Your last bootstrap on this server was X ago..."

**Cause**: Too many bootstrap attempts from this IP

**Solution**: Wait until oldest server's cooldown expires (~12 hours), or restart with different IP

### Bootstrap never completes

**Symptom**: Progress stuck at 50-80% for >30 min

**Cause**: Network connectivity or node configuration issue

**Solution**: 
1. Check node logs: `docker logs massa-container | grep -i error`
2. Verify routable_ip is correct: `docker inspect massa-container | grep routable_ip`
3. Restart node: `/restart` command

## Related Files

- **Configuration**: `massa/start_massa.sh` (auto-IP detection)
- **Node Config**: `massa/massa-node/config/config.toml` (routable_ip)
- **Orchestration**: `docker-compose.yml` (healthcheck endpoint)
- **Documentation**: `README.md`, `FUTURE_IMPROVEMENTS.md`

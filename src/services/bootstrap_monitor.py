"""Monitor Massa node bootstrap progress from container logs."""

import re
from datetime import datetime
from typing import Optional, Dict
import logging


def get_bootstrap_status(container, logger: logging.Logger = None) -> Optional[Dict]:
    """
    Parse bootstrap progress from node container logs.
    
    Returns dict with:
    - state: "bootstrapping" | "complete" | "failed" | "unknown"
    - progress_pct: approximate progress (0-100)
    - current_server: IP of server being tried
    - error: error message if any
    - last_attempt: timestamp of last attempt
    - retry_in_seconds: seconds until next retry
    - time_elapsed: seconds since first bootstrap attempt
    """
    if logger is None:
        logger = logging.getLogger(__name__)
    
    try:
        result = container.logs(stdout=True, stderr=True, follow=False).decode('utf-8')
    except Exception as e:
        logger.error(f"Failed to read container logs: {e}")
        return {"state": "unknown", "error": str(e)}
    
    lines = result.split('\n')
    
    # Patterns to find
    bootstrap_start = re.search(r'(\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2})', result)
    bootstrap_complete = re.search(r'INFO.*bootstrap::client: Successful bootstrap', result)
    state_bootstrap_complete = re.search(r'INFO.*bootstrap::client: State bootstrap complete', result)
    
    # Find all bootstrap attempts (to count progress)
    attempts = re.findall(r'INFO.*bootstrap::client: Start bootstrapping from ([\w.:[\]]+)', result)
    
    # Find last error from recent lines with better pattern
    last_error = None
    for line in reversed(lines[-100:]):
        # Match WARN/ERROR lines with error details
        if 'WARN' in line and 'bootstrap' in line:
            # Extract error message after colon
            if 'Error' in line or 'error' in line:
                # Try to find error description
                parts = line.split(': ')
                if len(parts) >= 3:
                    last_error = parts[-1].strip()
                elif len(parts) >= 2:
                    last_error = parts[-1].strip()
                break
    
    # Find retry time more accurately
    retry_seconds = None
    for line in reversed(lines[-50:]):
        if 'will try to bootstrap from another server in' in line:
            time_match = re.search(r'in (\d+)m', line)
            if time_match:
                retry_seconds = int(time_match.group(1)) * 60
            break
    
    # Determine state
    if bootstrap_complete or state_bootstrap_complete:
        state = "complete"
        progress_pct = 100
    elif len(attempts) > 0:
        state = "bootstrapping"
        # Rough estimate: ~1 min per server, up to 9 servers
        progress_pct = min(100, int((len(attempts) / 9) * 100))
    else:
        state = "unknown"
        progress_pct = 0
    
    current_server = None
    if attempts:
        current_server = attempts[-1]
    
    # Calculate elapsed time if bootstrap_start found
    time_elapsed = None
    if bootstrap_start:
        try:
            start_time = datetime.fromisoformat(bootstrap_start.group(1) + '+00:00')
            now = datetime.now(start_time.tzinfo)
            time_elapsed = int((now - start_time).total_seconds())
        except Exception as e:
            logger.debug(f"Could not parse bootstrap start time: {e}")
    
    return {
        "state": state,
        "progress_pct": progress_pct,
        "current_server": current_server,
        "attempt_count": len(attempts),
        "error": last_error,
        "retry_in_seconds": retry_seconds,
        "time_elapsed": time_elapsed,
    }


def format_bootstrap_status(bootstrap_info: Optional[Dict]) -> str:
    """Format bootstrap status for display."""
    if not bootstrap_info:
        return "⏳ État de bootstrap : inconnu"
    
    state = bootstrap_info.get("state", "unknown")
    
    if state == "complete":
        return "✅ Bootstrap terminé"
    
    elif state == "bootstrapping":
        lines = []
        progress = bootstrap_info.get("progress_pct", 0)
        attempt = bootstrap_info.get("attempt_count", 0)
        
        # Progress bar
        filled = int(progress / 10)
        bar = "▓" * filled + "░" * (10 - filled)
        lines.append(f"⏳ Bootstrap en cours: [{bar}] {progress}%")
        
        # Current server
        server = bootstrap_info.get("current_server")
        if server:
            lines.append(f"   Serveur actuel: {server}")
        
        # Time elapsed
        elapsed = bootstrap_info.get("time_elapsed")
        if elapsed:
            minutes = elapsed // 60
            seconds = elapsed % 60
            lines.append(f"   Temps écoulé: {minutes}m {seconds}s")
        
        # Retry info
        retry_sec = bootstrap_info.get("retry_in_seconds")
        if retry_sec:
            minutes = retry_sec // 60
            lines.append(f"   Nouvelle tentative dans: {minutes}m")
        
        # Last error (if any)
        error = bootstrap_info.get("error")
        if error:
            # Truncate long errors
            if len(error) > 60:
                error = error[:57] + "..."
            lines.append(f"   ⚠️ Erreur: {error}")
        
        return "\n".join(lines)
    
    elif state == "failed":
        return "❌ Bootstrap échoué - vérifier les logs"
    
    else:
        return "❓ État de bootstrap inconnu"

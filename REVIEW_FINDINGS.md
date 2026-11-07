# Robbi Bot - Code Review & Improvements

## Critical Issues

### 1. **File Descriptor Leak in disable_prints()** ⚠️ HIGH
**File:** src/main.py:42-44
**Problem:** The devnull file handle is never closed, causing a file descriptor leak at startup.
```python
# Current (leaks FD):
def disable_prints():
    devnull = open(os.devnull, 'w')
    sys.stdout = devnull
    sys.stderr = devnull
```

**Fix:** Store reference for cleanup or use a different approach:
```python
# Option A: Store for cleanup (requires __del__ or atexit handler)
# Option B: Use logging exclusively instead of suppressing prints
# Option C: Use subprocess redirection
```

---

### 2. **Race Condition in balance_history Write** ⚠️ HIGH
**File:** src/handlers/scheduler.py:250-260
**Problem:** The `periodic_node_ping()` function writes to balance_history without lock protection in some code paths. APScheduler can run overlapping jobs if execution exceeds interval, causing concurrent writes to JSON file → data corruption.

**Evidence:**
```python
# If lock exists, it's used:
if lock:
    with lock:
        balance_history[current_time_key] = [final_balance, final_roll_count, cycles, ok_counts, nok_counts, active_rolls]
else:
    # But this else path doesn't use lock → race condition!
    balance_history[current_time_key] = ...
```

**Fix:**
- Add `coalesce=True` to APScheduler job config to skip overlapping runs
- Remove else path or always acquire lock
- Add file-level locking with fcntl/msvcrt around JSON writes

---

### 3. **Incorrect Node Status Logic** ⚠️ MEDIUM-HIGH
**File:** src/handlers/scheduler.py:194
**Problem:** Logic `node_is_up = not (any(data[4]) or data[1] == 0)` marks node as DOWN if ANY historical NOK count > 0. This is too aggressive — validation failures happen in normal operation.

**Current behavior:** One validation failure in the past → node marked DOWN indefinitely
**Expected behavior:** Node DOWN only if recent failures or roll_count actually 0

**Fix:** Check only recent failures or use a threshold:
```python
# Option 1: Check only the last/most recent entries
recent_noks = data[4][-10:] if len(data[4]) >= 10 else data[4]
node_is_up = not (any(recent_noks) or data[1] == 0)

# Option 2: Require multiple consecutive failures
nok_threshold = sum(data[4][-5:]) > 3  # 3+ failures in last 5 cycles
node_is_up = not (nok_threshold or data[1] == 0)
```

---

## Important Issues

### 4. **Unhandled Exception in Scheduler Loop** ⚠️ MEDIUM
**File:** src/handlers/scheduler.py:110-115
**Problem:** When `loop.run_until_complete()` is called and exception occurs, it's not caught or logged.

**Fix:**
```python
try:
    logging.info("Event loop not running, using run_until_complete.")
    loop.run_until_complete(coroutine(application))
except Exception as e:
    logging.error(f"Unhandled exception in coroutine: {e}", exc_info=True)
```

---

### 5. **Missing Configuration Validation** ⚠️ MEDIUM
**File:** src/main.py:85-96
**Problem:** `ninja_key` loaded without null check, but required for `/btc` command. Missing config keys cause crashes.

**Fix:**
```python
REQUIRED_CONFIG = ['admin_id', 'massa_node_address']
OPTIONAL_CONFIG = {
    'ninja_api_key': None,
    'massa_node_rpc_url': DEFAULT_MASSA_RPC_URL,
    # ...
}

for key in REQUIRED_CONFIG:
    if key not in config:
        raise ValueError(f"Missing required config key: {key}")

for key, default in OPTIONAL_CONFIG.items():
    config.setdefault(key, default)
```

---

### 6. **Matplotlib Memory Leak** ⚠️ MEDIUM
**File:** src/services/plotting.py
**Problem:** While figures are closed, matplotlib's internal figure registry can grow over long-running bot uptime, causing slow memory growth.

**Fix:**
```python
# At module initialization:
import matplotlib
matplotlib.use('Agg')  # Non-interactive backend
plt.close('all')  # Clear any residual figures

# In finally blocks, also:
plt.close('all')  # Clear all accumulated figures
```

---

## Code Quality Issues

### 7. **Inconsistent Error Handling Pattern** ⚠️ MINOR-MEDIUM
**Files:** Multiple handlers (price.py, node.py, system.py)
**Problem:** Some handlers silently fail with `await query.edit_message_text("Error...")`, others raise. Inconsistent patterns make debugging harder.

**Fix:** Standardize error handling:
```python
async def safe_handler_wrapper(handler_func):
    try:
        return await handler_func()
    except ConfigError as e:
        logging.error(f"Config error: {e}")
        # Notify user politely
    except Exception as e:
        logging.exception(f"Unexpected error in {handler_func.__name__}")
        # Notify user
```

---

### 8. **Hardcoded Values & Magic Numbers** ⚠️ MINOR
**Files:** Multiple
**Examples:**
- Timeouts: `30s`, `5s`, `60s` scattered throughout
- Limits: `500` entries in history, `12` item batch size
- Ports: `33034`, `33035`, `33036` (now fixed in config)

**Fix:** Move to config.toml or constants.py:
```python
# constants.py
HEALTH_CHECK_TIMEOUT = 5  # seconds
RPC_REQUEST_TIMEOUT = 30
BALANCE_HISTORY_MAX_ENTRIES = 500
```

---

### 9. **Async/Await Consistency** ⚠️ MINOR
**File:** src/handlers/scheduler.py line 252+
**Problem:** Mix of direct calls and `asyncio.to_thread()` without clear pattern. Some I/O operations aren't awaited.

**Fix:** Document when to use threads vs. native async:
```python
# I/O operations that can block: use asyncio.to_thread()
result = await asyncio.to_thread(json.load, f)

# Network ops (requests): convert to async with aiohttp
response = await self.http_client.post(url, json=data)
```

---

### 10. **Missing Context Manager Usage** ⚠️ MINOR
**File:** src/services/http_client.py
**Problem:** Some file/connection operations don't use context managers.

**Example:**
```python
# Risky:
f = open(filename, 'r')
data = json.load(f)
f.close()  # Never reached if exception occurs

# Safe:
with open(filename, 'r') as f:
    data = json.load(f)
```

---

## Summary Table

| # | Issue | Severity | File | Impact |
|---|-------|----------|------|--------|
| 1 | File descriptor leak | 🔴 HIGH | main.py:42 | Resource exhaustion over time |
| 2 | Race condition (balance_history) | 🔴 HIGH | scheduler.py:250 | Data corruption |
| 3 | Wrong node status logic | 🟠 MEDIUM-HIGH | scheduler.py:194 | False down alerts |
| 4 | Unhandled exception in loop | 🟠 MEDIUM | scheduler.py:110 | Silent failures |
| 5 | Missing config validation | 🟠 MEDIUM | main.py:95 | Crash on missing config |
| 6 | Matplotlib memory leak | 🟠 MEDIUM | plotting.py | Slow OOM over days |
| 7 | Inconsistent error handling | 🟡 MINOR-MEDIUM | handlers/* | Debugging difficulty |
| 8 | Hardcoded values | 🟡 MINOR | Multiple | Low maintainability |
| 9 | Async/await inconsistency | 🟡 MINOR | scheduler.py | Unpredictable performance |
| 10 | Missing context managers | 🟡 MINOR | services/* | Potential leaks |


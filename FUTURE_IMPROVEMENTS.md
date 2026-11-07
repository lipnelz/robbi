# Robbi Bot - Future Improvements (Lower Priority)

## Phase 2: Code Quality & Maintainability

### 1. Extract Hardcoded Values to Constants
**Priority:** Medium | **Effort:** Low
**Files:** Multiple
**Action:** Create `src/constants.py` and move:
- Timeouts (5s, 30s, 60s)
- Batch sizes (500 entries, 12 items)
- File paths (topology.json, *.json files)
- Port numbers (now in config, but good to validate)

**Before:**
```python
if "timed out" in error_message:  # Magic string
    timeout_val = 5000  # Magic number
```

**After:**
```python
from constants import TIMEOUT_ERROR_KEYWORD, RPC_TIMEOUT_MS

if TIMEOUT_ERROR_KEYWORD in error_message:
    await asyncio.sleep(RPC_TIMEOUT_MS / 1000)
```

---

### 2. Standardize Error Handling Across Handlers
**Priority:** Medium | **Effort:** Medium
**Files:** handlers/price.py, handlers/node.py, handlers/system.py

**Goal:** Create a decorator or context manager for consistent error handling

**Example:**
```python
@handle_handler_error(alert_user=True, notify_admin=True)
async def btc(update, context):
    # Code that might fail
    return result
```

---

### 3. Move I/O Operations to Async
**Priority:** Medium | **Effort:** High
**Files:** services/http_client.py, services/history.py

**Current:** Using `asyncio.to_thread()` for sync I/O
**Target:** Use `aiohttp` for network calls, `aiofiles` for file I/O

**Benefit:** Better concurrency, no thread pool overhead

---

### 4. Add Structured Logging
**Priority:** Low | **Effort:** Low
**Current:** Using standard logging with string formatting
**Target:** Use `structlog` for JSON logging with context

**Example:**
```python
logger.info("node_status", node_id="N12LurM...", is_up=True, cycles=5546300)
```

---

### 5. Add Metrics Export
**Priority:** Low | **Effort:** Medium
**Action:** Export Prometheus metrics endpoint (`/metrics`)
- Node uptime
- RPC latency histogram
- Balance change rate
- Command invocation counts

---

### 6. Add Type Hints Throughout
**Priority:** Low | **Effort:** Low-Medium
**Current:** Partial type hints
**Target:** Full coverage with mypy checking

**Example:**
```python
async def periodic_node_ping(application: Application) -> None:
    balance_history: Dict[str, List[Any]] = load_balance_history()
    data: Optional[Tuple[float, int, List[int], ...]] = await get_data(...)
```

---

### 7. Add Integration Tests for Docker Operations
**Priority:** Medium | **Effort:** High
**Files:** tests/test_handlers_docker*.py
**Goal:** Test actual Docker operations (not mocked) in a test container

---

## Phase 3: Features & UX

### 8. Add Multi-User Support
**Current:** Single admin_id
**Target:** Multiple admin users with different permission levels
- Admin: full control
- Monitor: read-only (status, balance history)
- User: node info only

---

### 9. Add Telegram Webhook Mode
**Current:** Polling (long-running, higher latency)
**Target:** Webhook (immediate, lower resource usage)

**Requirement:** HTTPS endpoint + certificate management

---

### 10. Add Automated Rollback on Node Restart Failure
**Current:** User must manually diagnose and retry
**Target:** Automatic retry with exponential backoff + alert after N failures

**Logic:**
```python
retry_count = 0
while retry_count < 3:
    try:
        await docker_restart(...)
        break
    except Exception as e:
        retry_count += 1
        await asyncio.sleep(2 ** retry_count)  # Exponential backoff
        if retry_count >= 3:
            notify_admin("Automatic restart failed 3x")
```

---

## Phase 4: Deployment & Operations

### 11. Add Health Check Endpoint
**Priority:** Low | **Effort:** Low
**Action:** Add `/health` endpoint that returns bot status
```json
{
  "status": "healthy",
  "node_reachable": true,
  "uptime_seconds": 86400,
  "last_ping": "2026-11-07T13:50:00Z"
}
```

---

### 12. Add Graceful Shutdown
**Current:** Bot stops immediately
**Target:** Drain pending messages, save state, close connections gracefully

---

### 13. Add Configuration Hot-Reload
**Priority:** Low | **Effort:** Medium
**Action:** Allow updating config without restarting bot
- Watch `topology.json` for changes
- Reload on change
- Alert admin on errors

---

## Maintenance

### 14. Document Architecture & Flows
- Data flow diagrams
- Handler state machines
- Scheduler timing
- Error recovery procedures

### 15. Add Development Guidelines
- Code style guide
- Testing expectations (coverage > 80%)
- PR review checklist
- Release process

---

## Summary Table

| # | Task | Priority | Effort | Impact |
|---|------|----------|--------|--------|
| 1 | Extract constants | 🟡 Medium | 🟢 Low | Maintainability |
| 2 | Standardize error handling | 🟡 Medium | 🟡 Medium | Debugging |
| 3 | Async I/O | 🟡 Medium | 🔴 High | Performance |
| 4 | Structured logging | ⚪ Low | 🟢 Low | Observability |
| 5 | Metrics export | ⚪ Low | 🟡 Medium | Monitoring |
| 6 | Type hints | ⚪ Low | 🟢 Low | Reliability |
| 7 | Integration tests | 🟡 Medium | 🔴 High | Quality |
| 8 | Multi-user support | 🟡 Medium | 🟡 Medium | Features |
| 9 | Webhook mode | ⚪ Low | 🔴 High | Operations |
| 10 | Automatic retry | 🟡 Medium | 🟡 Medium | Reliability |
| 11 | Health endpoint | ⚪ Low | 🟢 Low | Ops |
| 12 | Graceful shutdown | ⚪ Low | 🟡 Medium | Reliability |
| 13 | Config hot-reload | ⚪ Low | 🟡 Medium | Operations |
| 14 | Architecture docs | ⚪ Low | 🟡 Medium | Knowledge |
| 15 | Dev guidelines | ⚪ Low | 🟢 Low | Collaboration |


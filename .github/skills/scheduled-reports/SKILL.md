# Skill: Automatic Scheduled Reports

## Description

This skill manages periodic checks of the Massa node and automatic status report delivery. A job runs every 60 minutes to check the node status, record a balance snapshot, and send a detailed report at scheduled hours.

## Triggers

- **Periodic ping**: every 60 minutes (APScheduler, `interval`)
- **Automatic reports**: at 7am, 12pm, and 9pm if the node is active

---

## Sub-skills

### 1. Scheduler Initialization (`run_async_func`)

- Creates or reuses the `asyncio` event loop (compatible with environments where a loop is already running)
- Initializes a `BackgroundScheduler` (APScheduler)
- Removes any stale job with the same ID (`JOB_SCHED_NAME`)
- Registers `periodic_node_ping` with a 60-minute interval
- Starts the scheduler if not already running

### 2. Async/Sync Bridge (`run_coroutine_in_loop`)

- Allows executing an `asyncio` coroutine from a synchronous thread (the scheduler's thread)
- If the loop is active: uses `asyncio.run_coroutine_threadsafe()` (thread-safe)
- If the loop is inactive: uses `loop.run_until_complete()`
- Unhandled exceptions in the coroutine are logged via an `add_done_callback` callback

### 3. Periodic Node Ping (`periodic_node_ping`)

#### 3a. Status Check
- Calls `get_addresses(logger, massa_node_address)` to query the node
- On error:
  - Timeout → sends a dedicated `TIMEOUT_NAME` image to all authorized users
  - Other error → sends an error image `TIMEOUT_FIRE_NAME`
  - Early return without recording a snapshot

#### 3b. Node State Determination
- The node is considered **inactive** if:
  - at least one `nok_count` is non-zero, **OR**
  - `final_roll_count == 0`
- Immediate alert (`NODE_IS_DOWN`) sent to all users if the node is inactive

#### 3c. Snapshot Recording
- Calls `get_system_stats(logger)` to collect CPU temperature and RAM
- Creates the time key with `make_time_key(now)`
- Builds the entry with `build_balance_entry(balance, system_stats)`
- Writes to `balance_history` using `balance_lock` (thread-safe) and saves to disk

### 4. Status Report at Scheduled Hours (7am, 12pm, 9pm)

Sent only if the node is active (`node_is_up == True`) and `balance_history` is not empty.

#### Report Composition

| Section | Content |
|---------|---------|
| **Indicator** | `NODE_IS_UP` |
| **Balance comparison** | First balance since midnight (or 24h window) vs current balance |
| **Variation** | Amount and percentage with 📈/📉 indicator |
| **Average temperature** | CPU average over 24h sliding window (if data available) |
| **24h history** | Formatted list of all entries from the last 24 hours |

#### Balance Reference Logic

1. Priority: first record **since midnight** (`filter_since_midnight`)
2. Fallback: first entry from the **24h sliding window** (`filter_last_24h`)
3. Last resort: balance of 0 if no data available

#### Variation Calculation
```
balance_change = current_balance - reference_balance_24h
change_percent = (balance_change / reference_balance_24h) * 100
```

### 5. User Broadcasting

- Iterates over `allowed_user_ids` (set stored in `application.bot_data`)
- Uses `application.bot.send_message(chat_id=user_id, text=...)` for each authorized user
- For errors with images: uses `application.bot.send_photo()` with file opening

## Related Files

| File | Role |
|------|------|
| `src/handlers/scheduler.py` | Scheduler, periodic ping, automatic reports |
| `src/services/massa_rpc.py` | Node JSON-RPC queries |
| `src/services/history.py` | Snapshots, 24h filtering, entry formatting |
| `src/services/system_monitor.py` | CPU/RAM statistics for snapshots |
| `src/main.py` | Calls `run_async_func()` at bot startup |

## Required Configuration

| `topology.json` Key | Description |
|---------------------|-------------|
| `massa_node_address` | Massa address for JSON-RPC requests |
| `user_white_list` | List of users to notify |

## Constants (`config.py`)

| Constant | Value | Description |
|----------|-------|-------------|
| `JOB_SCHED_NAME` | `"node_ping_job"` | APScheduler job identifier |
| `NODE_IS_UP` | `"✅ Node is up"` | Active node status message |
| `NODE_IS_DOWN` | `"❌ Node is down"` | Inactive node alert message |
| `TIMEOUT_NAME` | `"timeout.png"` | Timeout image |
| `TIMEOUT_FIRE_NAME` | `"timeout_fire.png"` | Critical error image |

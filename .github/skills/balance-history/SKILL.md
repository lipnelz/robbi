# Skill: Balance History

## Description

This skill manages the persistence, visualization, and clearing of Massa balance history. It includes two interactive commands: `/hist` to view the history as charts and text, and `/flush` to clear logs and/or history.

## Commands

```
/hist
/flush
```

---

## Sub-skills

### 1. JSON History Persistence (`services/history.py`)

- History is stored in `config/balance_history.json` (mounted Docker volume)
- **`save_balance_history(balance_history)`** — serializes and writes the dict as JSON
- **`make_time_key(dt=None)`** — generates a time key in `YYYY/MM/DD-HH:MM` format
- **`build_balance_entry(balance, system_stats)`** — builds a dict entry containing:
  - `balance` — MAS balance (float)
  - `temperature` — average CPU temperature (float or `null`)
  - `ram_percent` — RAM usage percentage (float or `null`)
- All writes to `balance_history` are protected by a `threading.Lock` (`balance_lock` in `bot_data`)

### 2. History Filtering

- **`filter_last_24h(balance_history)`** — returns entries from the last 24 hours (sliding window)
- **`filter_since_midnight(balance_history)`** — returns entries since midnight of the current day
- **`get_entry_balance(entry)`** — extracts the balance from an entry (compatible with old and new formats)
- **`get_entry_temperature(entry)`** — extracts the temperature from an entry (returns `None` if absent)
- **`format_history_entry(timestamp, entry)`** — formats a history line: `HH:MM | balance MAS | temp°C | ram%`

### 3. `/hist` Command — Chart and Summary

#### Step 1: Confirmation Menu
- Displays a message with an inline keyboard:
  - **Graph only** → generates charts only
  - **Graph + Text** → generates charts and also sends a text summary
  - **Cancel** → cancels and ends the conversation

#### Step 2: Chart Generation
- **`create_balance_history_plot(balance_history)`** — matplotlib chart of balance over time (`balance_history.png`)
- **`create_resources_plot(balance_history)`** — matplotlib chart of CPU temperature and RAM (`resources_plot.png`)
- Both images are sent as responses then deleted with `safe_delete_file()`

#### Step 3 (optional): Text Summary
- Lists all history entries formatted by `format_history_entry()`
- Handles the 4096-character Telegram message limit (splits into multiple messages if necessary)

### 4. `/flush` Command — Log Clearing

#### Step 1: Confirmation Menu
- Displays an inline keyboard:
  - **Logs only** → deletes only `bot_activity.log`
  - **Logs + History** → deletes the log AND clears `balance_history.json`
  - **Cancel** → cancels without deleting anything

#### Step 2: Clearing Execution
- Deletes the `bot_activity.log` file (path: `config/LOG_FILE_NAME`)
- If "Logs + History" selected: clears `balance_history` in memory and on disk, then recreates an empty JSON file

### 5. Time Key Formats (Backward Compatibility)

- Current format: `YYYY/MM/DD-HH:MM` (e.g. `2024/03/15-14:30`)
- Legacy format: `DD/MM-HH:MM` (e.g. `15/03-14:30`) — still readable by filters for older data

## Related Files

| File | Role |
|------|------|
| `src/handlers/node.py` | `/hist` and `/flush` handlers (ConversationHandler) |
| `src/services/history.py` | Persistence, filtering, and formatting of history |
| `src/services/plotting.py` | Balance and resources chart generation |
| `src/handlers/common.py` | `safe_delete_file()`, `cb_auth_required` |

## Generated Files

| File | Description | Lifecycle |
|------|-------------|-----------|
| `config/balance_history.json` | Timestamped balance snapshots | Persistent (Docker volume) |
| `balance_history.png` | Balance chart | Temporary, deleted after sending |
| `resources_plot.png` | CPU / RAM chart | Temporary, deleted after sending |
| `bot_activity.log` | Bot activity log | Persistent, clearable via `/flush` |

## Error Handling

- Empty history → informational message without chart
- Chart generation failure → error message
- Missing log file → error silently ignored

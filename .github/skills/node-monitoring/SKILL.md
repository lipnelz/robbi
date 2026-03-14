# Skill: Massa Node Monitoring

## Description

This skill provides real-time monitoring of the Massa blockchain node via the `/node` command. It queries the node's JSON-RPC API, displays a text summary, and generates a validation chart.

## Command

```
/node
```

## Sub-skills

### 1. JSON-RPC Query

- Calls `get_addresses(logger, massa_node_address)` from `services/massa_rpc.py`
- Sends a POST request to the Massa node's JSON-RPC endpoint
- Handles network errors (timeout, connection refused) and returns a `{"error": "..."}` dict on failure

### 2. Node Data Extraction

- Function `extract_address_data(json_data)` in `handlers/node.py`
- Extracts from the JSON response:
  - `final_balance` — current wallet balance (MAS)
  - `final_roll_count` — number of rolls held
  - `cycles` — list of recent validation cycles
  - `ok_counts` — number of successful validations per cycle
  - `nok_counts` — number of failed validations per cycle
  - `active_rolls` — active rolls per cycle
- Returns `None` if the node is unreachable or data is invalid

### 3. Text Status Display

- Composes and sends a summary text message:
  ```
  Node status:
  Final Balance: <balance>
  Final Roll Count: <rolls>
  OK Counts: [...]
  NOK Counts: [...]
  Active Rolls: [...]
  ```

### 4. Balance Snapshot Recording

- Calls `make_time_key()` to timestamp the entry in `YYYY/MM/DD-HH:MM` format
- Calls `build_balance_entry(balance, system_stats)` to build an entry containing:
  - the balance
  - average CPU temperature
  - RAM usage
- Writes to `balance_history` (protected by a `threading.Lock`) then saves via `save_balance_history()`

### 5. Validation Chart Generation

- Calls `create_png_plot(cycles, ok_counts, nok_counts, active_rolls)` from `services/plotting.py`
- Generates a matplotlib chart (`plot.png`) showing OK/NOK/ActiveRolls per cycle
- Sends the image as a response, then deletes it with `safe_delete_file()`

## Related Files

| File | Role |
|------|------|
| `src/handlers/node.py` | `/node` handler, data extraction |
| `src/services/massa_rpc.py` | Massa JSON-RPC call |
| `src/services/plotting.py` | Validation chart generation |
| `src/services/history.py` | Timestamped balance snapshot |
| `src/services/system_monitor.py` | System statistics for the snapshot |

## Required Configuration

| `topology.json` Key | Description |
|---------------------|-------------|
| `massa_node_address` | Massa wallet address for monitoring |

## Error Handling

- Timeout or unreachable node → error image sent to the user
- Invalid data → text error message
- Chart generation failure → error message without image

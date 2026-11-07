# Skill: Massa Node Monitoring

## Description

This skill provides real-time monitoring of the Massa blockchain node via `/node` and `/status`. `/node` reports wallet and validation data with a chart; `/status` combines Docker container state, healthcheck, JSON-RPC availability, peer/cycle/slot details, and recent activity.

## Command

```
/node
/status
```

`/massa_version` affiche la version `MASSA_VERSION` et accepte une nouvelle version, par exemple `/massa_version MAIN.5.2`. La commande met à jour le Dockerfile du contexte de build partagé; le nœud actif n'est pas remplacé automatiquement. Appliquer le changement ensuite sur l'hôte avec `docker-compose up -d --build massa`.

`/status` reports whether the Docker container is stopped, restarting, running, or still undergoing its healthcheck. A running process with unavailable RPC is reported as starting or having a problem, rather than as operational.

## Sub-skills

### 1. JSON-RPC Query

- Calls `get_addresses(logger, massa_node_address, massa_node_rpc_url)` from `services/massa_rpc.py`
- Uses the local Massa node JSON-RPC service by default (`http://massa:33034/api/v2` in Docker Compose), rather than the public mainnet endpoint
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
| `massa_node_rpc_url` | Massa node JSON-RPC URL; defaults to `http://massa:33036/api/v2` on the Docker Compose network |

## Error Handling

- Timeout or unreachable node → error image sent to the user
- Invalid data → text error message
- Chart generation failure → error message without image

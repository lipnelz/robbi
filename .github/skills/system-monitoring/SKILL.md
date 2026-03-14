# Skill: System Monitoring

## Description

This skill exposes three commands to monitor the health of the machine hosting the bot and the Massa node: `/hi` for a greeting with version info, `/temperature` for detailed system metrics, and `/perf` for node performance (RPC latency and uptime).

## Commands

```
/hi
/temperature
/perf
```

---

## Sub-skills

### 1. Greeting — `/hi`

- Sends a welcome message with the current bot version:
  ```
  Hey dude! (version: a1b2c3d)
  ```
- Retrieves the short hash of the current git commit via `subprocess.check_output(['git', 'rev-parse', '--short', 'HEAD'])`
- On git command failure → displays `unknown` as version
- Sends a mascot image (`BUDDY_FILE_NAME` defined in `config.py`)

---

### 2. System Statistics — `/temperature`

#### Data Collection (`services/system_monitor.py`)
- Calls `get_system_stats(logger)` which uses the `psutil` library
- Returns a dict containing:

| Key | Type | Description |
|-----|------|-------------|
| `temperature_details` | list | Per-sensor details: `sensor`, `label`, `current` (°C) |
| `temperature_avg` | float | Average CPU temperature (°C) |
| `cpu_percent` | float | Overall CPU usage (%) |
| `cpu_cores` | list | Per-core usage: `core`, `percent` |
| `ram_percent` | float | RAM usage (%) |
| `ram_available_gb` | float | Available RAM (GB) |
| `ram_total_gb` | float | Total RAM (GB) |

> **Note**: `temperature_details` and `temperature_avg` are only available on Linux (via `psutil.sensors_temperatures()`). On systems without sensors, these keys are absent.

#### Bot Response Format
```
🌡️ System Status
-----------
🌡️ Temperatures:
  coretemp Physical id 0: 45.0°C
  coretemp Core 0: 43.0°C
  ...
  Average: 44.5°C
-----------
CPU Usage Global: 12.3%
-----------
CPU Cores:
  Core 0: 10.5%
  Core 1: 14.1%
  ...
-----------
RAM Usage: 67.2%
RAM Available: 5.2 GB / 15.6 GB
```

---

### 3. Node Performance — `/perf`

#### 3a. RPC Latency (`services/massa_rpc.py`)
- Calls `measure_rpc_latency(logger, massa_node_address)`
- Performs a minimal JSON-RPC request and measures the response time
- Returns `{"latency_ms": 42}` or `{"error": "..."}` on failure

#### 3b. Uptime Calculation (24h)
- Function `_calculate_uptime(balance_history)` in `handlers/system.py`
- Counts `balance_history` entries present within the last 24-hour window
- Assumption: 1 entry per hour = 24 entries → 100% uptime
- `uptime = min((entries_24h / 24) * 100, 100.0)`, rounded to 1 decimal place

#### 3c. Time Key Parsing
- Function `_is_recent(key, cutoff, now)` — supports two formats:
  - Current format: `YYYY/MM/DD-HH:MM`
  - Legacy format: `DD/MM-HH:MM` (backward compatibility with older data)
- If the reconstructed date appears to be in the future (due to missing year), shifts back one year

#### Bot Response Format
```
⚡ Node Performance
-----------
RPC Latency: 42 ms
Uptime (24h): 95.8%
```

---

## Related Files

| File | Role |
|------|------|
| `src/handlers/system.py` | `/hi`, `/temperature`, `/perf` handlers, uptime calculation |
| `src/services/system_monitor.py` | System metrics collection via psutil |
| `src/services/massa_rpc.py` | RPC latency measurement |
| `src/config.py` | `BUDDY_FILE_NAME` constant |

## Required Configuration

| `topology.json` Key | Description |
|---------------------|-------------|
| `massa_node_address` | Massa address for RPC latency measurement |

## Error Handling

- `get_system_stats` failure → error message with details
- `measure_rpc_latency` failure → error message with details
- Missing temperature sensors → temperature section omitted from message

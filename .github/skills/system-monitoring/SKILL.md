# Skill: System Monitoring

## Description

This skill exposes three commands: `/hi` for a greeting with version info, `/temperature` for container-visible system metrics, and `/perf` for node RPC latency and observed availability.

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
- Metrics reflect what is visible from inside the bot container and are not guaranteed to represent the Docker host. Temperature sensors may be unavailable.
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
🌡️ Container-Visible System Status
-----------
🌡️ Temperatures:
  coretemp Physical id 0: 45.0°C
  coretemp Core 0: 43.0°C
  ...
  Average: 44.5°C
-----------
Container-Visible CPU Usage: 12.3%
-----------
CPU Cores:
  Core 0: 10.5%
  Core 1: 14.1%
  ...
-----------
Container-Visible RAM Usage: 67.2%
RAM Available: 5.2 GB / 15.6 GB
```

---

### 3. Node Performance — `/perf`

#### 3a. RPC Latency (`services/massa_rpc.py`)
- Calls `measure_rpc_latency(logger, massa_node_address, massa_node_rpc_url)`
- Performs a minimal JSON-RPC request and measures the response time
- Returns `{"latency_ms": 42}` or `{"error": "..."}` on failure

#### 3b. Observed Availability (24h)
- Function `_calculate_observed_availability(node_status_history)` in `handlers/system.py`
- Calculates the percentage of successful scheduled checks recorded in the last 24 hours
- Failed RPC checks and checks where the node reports failed validations are recorded as unavailable
- This is sampled availability, not continuous uptime between the hourly checks

#### Bot Response Format
```
⚡ Node Performance
-----------
RPC Latency: 42 ms
Observed availability (24h): 95.8% (23/24 successful checks)
```

---

## Related Files

| File | Role |
|------|------|
| `src/handlers/system.py` | `/hi`, `/temperature`, `/perf` handlers, observed availability calculation |
| `src/services/system_monitor.py` | System metrics collection via psutil |
| `src/services/node_status.py` | Persistent results of scheduled node checks |
| `src/services/massa_rpc.py` | RPC latency measurement |
| `src/config.py` | `BUDDY_FILE_NAME` constant |

## Required Configuration

| `topology.json` Key | Description |
|---------------------|-------------|
| `massa_node_address` | Massa address for RPC latency measurement |
| `massa_node_rpc_url` | Massa node JSON-RPC URL; defaults to `http://massa:33035` on the Docker Compose network |

## Error Handling

- `get_system_stats` failure → error message with details
- `measure_rpc_latency` failure → error message with details
- Missing temperature sensors → temperature section omitted from message

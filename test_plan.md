# Test Plan — Robbi Bot

## Overview

This document describes every unit test in the `tests/` suite, organized by file and test class. The suite targets **≥ 90% code coverage** across all modules in `src/` and is fully runnable in CI with no external network calls, no real Docker socket, and no real filesystem writes (outside of `tmp_path`).

**Overall results:** 295 tests passing · 99.83% coverage · 0 CodeQL alerts.

---

## Infrastructure

### `pytest.ini`

| Setting | Value | Purpose |
|---|---|---|
| `pythonpath` | `src` | Makes `import config`, `import handlers.*`, etc. work without package prefixes |
| `asyncio_mode` | `auto` | All `async def test_*` functions are collected and awaited automatically |
| `testpaths` | `tests` | Restricts pytest discovery to the `tests/` directory |

### `.github/workflows/tests.yml`

Runs on every `push` and `pull_request` on all branches. Steps:

1. Check out code (`actions/checkout@v4`)
2. Set up Python 3.12 (`actions/setup-python@v5`)
3. Install `pytest`, `pytest-asyncio`, `pytest-cov`, and all application requirements from `requirements.txt`
4. Run `pytest --cov=src --cov-report=term-missing --cov-fail-under=90`

The workflow fails if coverage drops below 90%.

---

## `tests/conftest.py` — Shared Fixtures

All handler tests share the fixtures defined here. The file also forces the `Agg` (non-interactive) matplotlib backend at import time so plotting tests do not attempt to open a GUI window in headless CI.

| Fixture | Description |
|---|---|
| `mock_update` | `MagicMock` simulating a `telegram.Update` for user ID `123`. `message.reply_text` and `message.reply_photo` are `AsyncMock`. |
| `mock_context` | `MagicMock` simulating `telegram.ext.CallbackContext` with a full `bot_data` dict: `allowed_user_ids={'123'}`, `massa_node_address`, `ninja_key`, empty `balance_history`, and a real `threading.Lock` for `balance_lock`. |
| `authorized_update_context` | Tuple `(mock_update, mock_context)` — user `123` is in the whitelist. |
| `unauthorized_update_context` | Tuple `(update_999, mock_context)` — user `999` is **not** in the whitelist. |

---

## `tests/test_config.py` — `src/config.py`

**Coverage: 100%**

Tests that all module-level constants have the correct Python type and value. No logic is exercised; these tests act as regression guards for accidental constant renames or value changes.

| Test | What is verified |
|---|---|
| `test_scheduler_constant` | `JOB_SCHED_NAME` is a `str` equal to `'periodic_node_ping'` |
| `test_log_file_name` | `LOG_FILE_NAME` is a `str` equal to `'bot_activity.log'` |
| `test_conversation_state_integers` | All 10 `*_STATE` constants are `int` and all values are distinct |
| `test_conversation_state_values` | Each state has its specific expected integer value (1–10) |
| `test_media_file_names` | `BUDDY_FILE_NAME`, `PAT_FILE_NAME`, `BTC_CRY_NAME`, `MAS_CRY_NAME`, `TIMEOUT_NAME`, `TIMEOUT_FIRE_NAME` are non-empty strings |
| `test_node_status_messages` | `NODE_IS_DOWN` contains "down", `NODE_IS_UP` contains "up" |
| `test_commands_list_structure` | `COMMANDS_LIST` is a list of dicts, each with `id` (int), `cmd_txt` (str), `cmd_desc` (str) |
| `test_commands_list_has_expected_commands` | All 9 expected command names (`hi`, `node`, `btc`, `mas`, `hist`, `flush`, `temperature`, `perf`, `docker`) are present |

---

## `tests/test_services_history.py` — `src/services/history.py`

**Coverage: 100%**

### `TestGetEntryBalance`

| Test | Scenario |
|---|---|
| `test_dict_format_with_balance_key` | `{"balance": 42.5}` → returns `42.5` |
| `test_dict_format_missing_balance_key_returns_zero` | `{"other": 1}` → returns `0.0` (key absent, default) |
| `test_dict_format_zero_balance` | `{"balance": 0.0}` → returns `0.0` |
| `test_legacy_string_format` | `"Balance: 99.75"` → returns `99.75` |
| `test_legacy_string_bad_format_returns_zero` | `"no colon here"` → `IndexError` caught, returns `0.0` |
| `test_legacy_string_non_numeric_returns_zero` | `"Balance: abc"` → `ValueError` caught, returns `0.0` |
| `test_empty_string_returns_zero` | `""` → `IndexError` caught, returns `0.0` |
| `test_integer_value_via_dict` | `{"balance": 10}` → returns `10.0` (int cast to float) |

### `TestGetEntryTemperature`

| Test | Scenario |
|---|---|
| `test_dict_with_temperature_avg` | `{"temperature_avg": 55.3}` → `55.3` |
| `test_dict_without_temperature_avg` | Key absent → `None` |
| `test_string_input_returns_none` | Legacy string → `None` (not a dict) |
| `test_dict_with_none_temperature` | `{"temperature_avg": None}` → `None` |

### `TestGetEntryRam`

| Test | Scenario |
|---|---|
| `test_dict_with_ram_percent` | `{"ram_percent": 72.4}` → `72.4` |
| `test_dict_without_ram_percent` | Key absent → `None` |
| `test_string_input_returns_none` | Legacy string → `None` |
| `test_dict_with_none_ram` | `{"ram_percent": None}` → `None` |

### `TestLoadBalanceHistory`

Uses `tmp_path` and patches `services.history.BALANCE_HISTORY_FILE` to isolate from the real filesystem.

| Test | Scenario |
|---|---|
| `test_loads_valid_json_file` | Writes a valid JSON file, asserts that the exact dict is returned |
| `test_returns_empty_dict_for_missing_file` | File does not exist → `{}` |
| `test_returns_empty_dict_for_corrupt_json` | File contains malformed JSON → `json.JSONDecodeError` caught → `{}` |
| `test_returns_empty_dict_on_ioerror` | `open()` raises `IOError` → caught → `{}` |

### `TestSaveBalanceHistory`

| Test | Scenario |
|---|---|
| `test_creates_directory_and_writes_file` | Target inside a non-existent subdirectory → `os.makedirs` creates it |
| `test_writes_correct_json` | Written JSON round-trips back to the original dict |
| `test_handles_ioerror_gracefully` | `open()` raises `IOError` → caught, no exception propagates |
| `test_empty_dict_saved` | Empty dict `{}` is written and readable back |

### `TestFilterSinceMidnight`

| Test | Scenario |
|---|---|
| `test_empty_dict_returns_empty` | `{}` → `{}` |
| `test_entries_before_midnight_filtered_out` | Entry from 25 hours ago → excluded |
| `test_entries_after_midnight_kept` | Entry at 00:30 today → included |
| `test_legacy_format_kept_if_today` | `DD/MM-HH:MM` key for today → parsed and included |
| `test_invalid_format_skipped` | `"not-a-date"` → `ValueError` swallowed, excluded |
| `test_result_is_sorted_chronologically` | Multiple entries → returned in ascending datetime order |

### `TestFilterLast24h`

| Test | Scenario |
|---|---|
| `test_empty_dict_returns_empty` | `{}` → `{}` |
| `test_entries_older_than_24h_removed` | Entry from 25 hours ago → excluded |
| `test_recent_entry_kept` | Entry from 1 hour ago → included |
| `test_one_per_hour_dedup` | Two entries in the same hour → only the latest (minute 50) is kept |
| `test_max_24_entries` | 30 entries spread over 30 distinct hours → at most 24 returned |
| `test_legacy_format_parsed` | `DD/MM-HH:MM` from 2 hours ago → included |
| `test_invalid_format_skipped` | `"not-a-date"` → swallowed, excluded |
| `test_result_sorted_chronologically` | Entries returned in ascending datetime order |

---

## `tests/test_services_http_client.py` — `src/services/http_client.py`

**Coverage: 100%**

All tests patch `services.http_client.requests.request` to avoid real network calls.

### `TestSafeRequest`

| Test | Scenario |
|---|---|
| `test_200_ok_returns_json` | `status_code=200` → returns parsed JSON; verifies `requests.request` called with correct args |
| `test_non_200_returns_error_dict` | `status_code=404` → `{"error": ...}` returned; `logger.error` called |
| `test_timeout_returns_error_dict` | `requests.Timeout` raised → `{"error": "... timed out ..."}` |
| `test_connection_error_returns_error_dict` | `requests.ConnectionError` raised → `{"error": "connection ..."}` |
| `test_request_exception_returns_error_dict` | `requests.RequestException("boom")` → `{"error": "Unexpected error: boom"}` |
| `test_none_logger_uses_root_logger` | `logger=None` on success path → root logger is substituted, no crash |
| `test_none_logger_on_error_path` | `logger=None` on non-200 path → no `AttributeError` |
| `test_post_method_forwarded` | `method='post'` → forwarded to `requests.request` |
| `test_kwargs_forwarded_to_request` | `headers=...` kwarg → forwarded unchanged |

---

## `tests/test_services_massa_rpc.py` — `src/services/massa_rpc.py`

**Coverage: 100%**

### `TestGetAddresses`

| Test | Scenario |
|---|---|
| `test_calls_safe_request_with_correct_post_body` | Asserts method is `'post'`, URL is `https://mainnet.massa.net/api/v2`, JSON-RPC method is `get_addresses`, address appears in `params` |
| `test_returns_error_dict_on_failure` | `safe_request` returns `{"error": "timeout"}` → passed through |

### `TestMeasureRpcLatency`

| Test | Scenario |
|---|---|
| `test_happy_path_returns_latency_and_ok_status` | `time.time` mocked to return `1000.0` then `1000.5` → `latency_ms ≈ 500.0`, `status="ok"` |
| `test_when_get_addresses_returns_error` | `get_addresses` returns an error dict → `latency_ms` still present, `"error"` key added |
| `test_when_exception_thrown` | `get_addresses` raises `RuntimeError` → `{"error": "boom"}` returned; `logger.error` called |
| `test_none_logger_uses_root_logger` | `logger=None` on success path → no crash |
| `test_none_logger_on_exception` | `logger=None` on exception path → no crash |

---

## `tests/test_services_price_api.py` — `src/services/price_api.py`

**Coverage: 100%**

All tests patch `services.price_api.safe_request`.

### `TestGetBitcoinPrice`

| Test | Scenario |
|---|---|
| `test_calls_safe_request_with_correct_url_and_headers` | URL contains `bitcoin`, `X-Api-Key` header equals the passed key |
| `test_returns_error_on_failure` | Error dict from `safe_request` → passed through |

### `TestGetMasInstant`

| Test | Scenario |
|---|---|
| `test_calls_safe_request_with_correct_url` | URL contains `MASUSDT`, method is `'get'` |
| `test_returns_error_on_failure` | Error dict passed through |

### `TestGetMasDaily`

| Test | Scenario |
|---|---|
| `test_calls_safe_request_with_correct_url` | URL contains `MASUSDT` and `24hr` |
| `test_returns_error_on_failure` | Error dict passed through |

---

## `tests/test_services_system_monitor.py` — `src/services/system_monitor.py`

**Coverage: 100%**

`psutil` is injected via `patch.dict('sys.modules', {'psutil': mock_psutil})` to avoid real hardware reads.

### `TestGetSystemStats`

| Test | Scenario |
|---|---|
| `test_happy_path_returns_cpu_and_ram` | CPU per-core `[25, 30]` → `cpu_percent ≈ 27.5`; 2 temperature sensors; `temperature_avg` computed |
| `test_no_temperature_sensors_returns_stats_without_temp` | `sensors_temperatures()` returns `{}` → `temperature_avg` and `temperature_details` absent |
| `test_psutil_no_sensors_temperatures_attribute` | `psutil` spec excludes `sensors_temperatures` → `hasattr` guard skips temperature block |
| `test_psutil_not_installed_returns_error` | `sys.modules['psutil'] = None` → `ImportError` → `{"error": "psutil ..."}` |
| `test_none_logger_uses_root_logger` | `logger=None` → root logger substituted, no crash |
| `test_none_logger_when_psutil_missing` | `logger=None` + psutil absent → no `AttributeError` |
| `test_exception_in_main_block_returns_error_dict` | `cpu_percent` raises `RuntimeError` → `{"error": "..."}` returned |
| `test_temperature_collection_exception_logged_as_warning` | `sensors_temperatures()` raises `OSError` → `logger.warning` called, stats still returned |
| `test_sensor_with_empty_label_uses_fallback` | Empty `entry.label` → label becomes `"Sensor 0"` |
| `test_cpu_per_core_empty_returns_zero_overall` | `cpu_percent` returns `[]` → `cpu_overall = 0` |

---

## `tests/test_services_docker_manager.py` — `src/services/docker_manager.py`

**Coverage: 100%**

`_get_docker_client` is patched so no Docker daemon is required.

### `TestGetDockerClient`

| Test | Scenario |
|---|---|
| `test_calls_docker_from_env` | `docker.from_env()` called once; returned client is propagated |

### `TestStartDockerNode`

| Test | Scenario |
|---|---|
| `test_happy_path_returns_ok_status` | Container found, `start()` called → `{"status": "ok", "message": "...massa-node..."}` |
| `test_exception_returns_error_status` | `_get_docker_client` raises → `{"status": "error", "message": "...no docker..."}` |
| `test_none_logger_uses_root_logger` | `logger=None` on success path → no crash |

### `TestStopDockerNode`

| Test | Scenario |
|---|---|
| `test_happy_path_returns_ok_status` | `stop(timeout=30)` called → `{"status": "ok"}` |
| `test_exception_returns_error_status` | Exception → `{"status": "error"}` |
| `test_none_logger_uses_root_logger` | `logger=None` → no crash |

### `TestExecMassaClient`

| Test | Scenario |
|---|---|
| `test_success_exit_code_zero` | `exec_run` returns `(0, b"wallet info\n")` → `{"status": "ok", "output": "wallet info"}` |
| `test_failure_exit_code_nonzero` | `exec_run` returns `(1, b"error occurred")` → `{"status": "error", "message": "...error occurred..."}` |
| `test_exception_returns_error` | `_get_docker_client` raises → `{"status": "error"}` |
| `test_none_logger_uses_root_logger` | `logger=None` on success path → no crash |
| `test_exec_run_called_with_correct_command` | `exec_run` first call builds `['./massa-client', '-p', 'mypass', '-a', 'wallet_info', 'extra']` |

---

## `tests/test_services_plotting.py` — `src/services/plotting.py`

**Coverage: 100%**

Tests use `monkeypatch.chdir(tmp_path)` so plots are written to a temporary directory. The `Agg` backend (set in `conftest.py`) prevents GUI windows.

### `TestCreatePngPlot`

| Test | Scenario |
|---|---|
| `test_creates_and_returns_filename` | Full pipeline with real matplotlib → `plot.png` created on disk |
| `test_closes_figure_on_success` | `plt.close(fig)` called exactly once after a successful plot |
| `test_closes_figure_on_exception` | If `plt.plot` raises, `plt.close(fig)` is still called (finally block) |

### `TestCreateResourcesPlot`

| Test | Scenario |
|---|---|
| `test_empty_dict_returns_empty_string` | `{}` → `""` (early return) |
| `test_no_temp_or_ram_data_returns_empty_string` | Legacy string entries have no temperature/RAM → `""` |
| `test_temperature_only_returns_filename` | Dict entries with only `temperature_avg` → `resources_history.png` created |
| `test_ram_only_returns_filename` | Dict entries with only `ram_percent` → file created |
| `test_both_temperature_and_ram_returns_filename` | Both fields present → dual-axis plot created |
| `test_closes_figure_on_success` | `plt.close(fig)` called after successful plot |

### `TestCreateBalanceHistoryPlot`

| Test | Scenario |
|---|---|
| `test_empty_dict_returns_empty_string` | `{}` → `""` |
| `test_with_data_returns_filename` | Dict with two entries → `balance_history.png` created on disk |
| `test_closes_figure_on_success` | `plt.close(fig)` called once |
| `test_with_legacy_string_values` | `"Balance: 200.0"` strings → `get_entry_balance` parses them, plot produced |

---

## `tests/test_handlers_common.py` — `src/handlers/common.py`

**Coverage: 100%**

### `TestAuthRequired`

| Test | Scenario |
|---|---|
| `test_allows_authorized_user` | User ID `123` is in `allowed_user_ids` → wrapped function executes |
| `test_blocks_unauthorized_user` | User ID `999` is not in the set → wrapped function is skipped; `reply_text` called with "not authorized" |
| `test_decorator_preserves_function_name` | `functools.wraps` in effect → `__name__` of decorated function is preserved |

### `TestHandleApiError`

| Test | Scenario |
|---|---|
| `test_returns_false_when_no_error_key` | `{"price": "50000"}` → returns `False`; `reply_photo` not called |
| `test_handles_timeout_error_sends_timeout_image` | `"timed out"` in message → `reply_photo` called with `TIMEOUT_NAME` path |
| `test_handles_other_error_sends_fire_image` | Generic error → `reply_photo` called with `TIMEOUT_FIRE_NAME` path |
| `test_returns_true_for_any_error` | Any dict with `"error"` key → returns `True` |

---

## `tests/test_handlers_node.py` — `src/handlers/node.py` (core handlers)

**Coverage: 100% combined with `test_handlers_node_docker.py`**

### `TestExtractAddressData`

| Test | Scenario |
|---|---|
| `test_valid_json_returns_tuple` | Full valid JSON → `(balance, roll_count, cycles, ok_counts, nok_counts, active_rolls)` |
| `test_no_result_key_returns_none` | `{}` → `None` |
| `test_empty_result_list_returns_none` | `{"result": []}` → `None` |
| `test_error_dict_returns_none` | `{"error": "timeout"}` → `None` |

### `TestNodeHandler`

| Test | Scenario |
|---|---|
| `test_happy_path_sends_reply_text_and_photo` | All services mocked; balance recorded; `reply_text` called |
| `test_api_error_triggers_handle_api_error` | `get_addresses` returns an error dict; `handle_api_error` mock returns `True` → handler exits early |
| `test_extract_address_data_returns_none` | `get_addresses` returns `{"result": []}` → "unreachable or no data" sent |
| `test_unauthorized_user_blocked` | User `999` → `get_addresses` never called |
| `test_exception_sends_error_and_photo` | `get_addresses` raises → "Arf" text + `PAT_FILE_NAME` photo sent |

### `TestFlushHandler`

| Test | Scenario |
|---|---|
| `test_unauthorized_user_returns_end` | User `999` → `ConversationHandler.END` returned |
| `test_log_file_does_not_exist_returns_end` | `os.path.exists` returns `False` → `END` returned |
| `test_authorized_with_log_file_returns_flush_confirm_state` | File exists → inline keyboard shown; `FLUSH_CONFIRM_STATE` returned |

### `TestFlushConfirmYes`

| Test | Scenario |
|---|---|
| `test_authorized_clears_log_and_history` | `open` mocked; `save_balance_history` mocked; `balance_history` cleared in-place |
| `test_unauthorized_returns_end` | User `999` → `END` returned; `query.answer` called with alert |

### `TestFlushConfirmNo`

| Test | Scenario |
|---|---|
| `test_authorized_clears_log_only` | Log file truncated; `balance_history` dict **unchanged** |
| `test_unauthorized_returns_end` | User `999` → `END` returned |

### `TestHistHandler`

| Test | Scenario |
|---|---|
| `test_unauthorized_user_returns_end` | User `999` → `END` returned |
| `test_empty_balance_history_returns_end` | Empty history → "No balance history available" sent; `END` |
| `test_happy_path_returns_hist_confirm_state` | Fake PNG files created; plot functions mocked → `HIST_CONFIRM_STATE` |
| `test_plot_creation_error_returns_end` | `create_balance_history_plot` raises → `END` |
| `test_image_not_created_returns_end` | Plot returns `""` → `END` |

---

## `tests/test_handlers_node_docker.py` — `src/handlers/node.py` (Docker & hist-confirm)

**Coverage: 100% (combined)**

### `TestDockerHandler`

| Test | Scenario |
|---|---|
| `test_authorized_shows_docker_menu` | User `123` → inline keyboard sent; `DOCKER_MENU_STATE` returned |
| `test_unauthorized_returns_end` | User `999` → `ConversationHandler.END` |

### `TestDockerStartStop`

| Test | Scenario |
|---|---|
| `test_docker_start_authorized` | Authorized callback → `DOCKER_START_CONFIRM_STATE` |
| `test_docker_start_unauthorized` | Unauthorized callback → `END` |
| `test_docker_stop_authorized` | Authorized callback → `DOCKER_STOP_CONFIRM_STATE` |
| `test_docker_stop_unauthorized` | Unauthorized callback → `END` |

### `TestDockerStartStopConfirm`

| Test | Scenario |
|---|---|
| `test_start_confirm_happy_path` | `start_docker_node` returns ok → message edited; `END` |
| `test_start_confirm_error_status` | Returns error status → message edited with error; `END` |
| `test_start_confirm_no_container_name` | Missing `docker_container_name` key → error message; `END` |

Plus analogous tests for `docker_stop_confirm`, `docker_cancel`, `docker_massa`, and all massa-client sub-commands (`massa_wallet_info`, `massa_buy_rolls_ask`, `massa_buy_rolls_input`, `massa_buy_rolls_confirm`, `massa_sell_rolls_ask`, `massa_sell_rolls_input`, `massa_sell_rolls_confirm`, `massa_back`) covering authorization, happy paths, error returns, and cancel flows.

Also covers `hist_confirm_yes` and `hist_confirm_no`:

| Test | Scenario |
|---|---|
| `test_hist_confirm_yes_authorized` | Sends text summary from history; `END` |
| `test_hist_confirm_yes_unauthorized` | User `999` → `END` |
| `test_hist_confirm_no_authorized` | Cancels gracefully; `END` |
| `test_hist_confirm_no_unauthorized` | User `999` → `END` |

---

## `tests/test_handlers_price.py` — `src/handlers/price.py`

**Coverage: 100%**

### `TestBtcHandler`

| Test | Scenario |
|---|---|
| `test_happy_path_sends_formatted_price` | All BTC fields present → formatted string with price sent |
| `test_api_error_calls_handle_api_error` | Error dict → `handle_api_error` mock called; `reply_text` not called |
| `test_exception_sends_error_messages` | `get_bitcoin_price` raises → "Nooooo" + `BTC_CRY_NAME` photo sent |
| `test_unauthorized_user_blocked` | User `999` → `get_bitcoin_price` never called |
| `test_malformed_data_triggers_exception_handler` | `"price": "not-a-float"` → `float()` raises → exception handler sends "Nooooo" |

### `TestMasHandler`

| Test | Scenario |
|---|---|
| `test_happy_path_sends_formatted_string` | Both API calls succeed → formatted string with symbol and price sent |
| `test_api_error_from_instant_price` | Instant price returns error → `handle_api_error` called |
| `test_api_error_from_daily_price` | Daily price returns error → `handle_api_error` called |
| `test_exception_sends_error_and_photo` | `get_mas_instant` raises → "Nooooo" + `MAS_CRY_NAME` photo sent |
| `test_unauthorized_user_blocked` | User `999` → `get_mas_instant` never called |

---

## `tests/test_handlers_system.py` — `src/handlers/system.py`

**Coverage: 100%**

### `TestGetGitCommitHash`

| Test | Scenario |
|---|---|
| `test_success_returns_short_hash` | `subprocess.check_output` returns `'abc1234\n'` → strips to `'abc1234'` |
| `test_failure_returns_unknown` | Exception raised → returns `'unknown'` |

### `TestHiHandler`

| Test | Scenario |
|---|---|
| `test_sends_greeting_and_photo` | Commit hash `'abc1234'` appears in reply text; photo sent |
| `test_unauthorized_user_blocked` | User `999` → photo never sent |

### `TestTemperatureHandler`

| Test | Scenario |
|---|---|
| `test_happy_path_sends_formatted_stats` | Full stats dict → text contains "CPU Usage" and "RAM Usage" |
| `test_temperature_details_included` | `temperature_details` present → text contains "Temperatures" and `55.0` |
| `test_stats_without_temperature_details` | Keys absent → no crash; CPU stats still formatted |
| `test_error_in_stats_sends_error_message` | `{"error": "psutil not installed"}` → "Error" in reply |
| `test_exception_sends_error_message` | `get_system_stats` raises → "Error" in reply |
| `test_unauthorized_user_blocked` | User `999` → `get_system_stats` never called |

### `TestCalculateUptime`

| Test | Scenario |
|---|---|
| `test_empty_history_returns_zero` | `{}` → `0.0` |
| `test_full_24_entries_returns_100` | 24 entries each 1 hour apart → `100.0` |
| `test_12_entries_returns_50` | 12 entries → `≈ 50.0%` |
| `test_capped_at_100` | 30 entries → result ≤ 100.0 |
| `test_old_entries_ignored` | Entry from 48 hours ago → `0.0` |

### `TestIsRecent`

| Test | Scenario |
|---|---|
| `test_new_format_in_range_returns_true` | Entry 1h ago, cutoff 24h ago → `True` |
| `test_new_format_out_of_range_returns_false` | Entry 25h ago → `False` |
| `test_legacy_format_in_range` | `DD/MM-HH:MM` format 2h ago → `True` |
| `test_invalid_format_returns_false` | `"not-a-date"` → `False` |

### `TestPerfHandler`

| Test | Scenario |
|---|---|
| `test_happy_path_sends_formatted_string` | `latency_ms=123.4` → text contains `123.4` and "Uptime" |
| `test_rpc_error_sends_error_message` | Error dict → text contains "Error" |
| `test_exception_sends_error_message` | `measure_rpc_latency` raises → "Error retrieving performance stats" sent |
| `test_unauthorized_user_blocked` | User `999` → `measure_rpc_latency` never called |

---

## `tests/test_handlers_scheduler.py` — `src/handlers/scheduler.py` (periodic ping & coroutine runner)

**Coverage: 99%** (line 239 is dead code: `balance_history` always has ≥ 1 entry before the `else` branch)

### `TestPeriodicNodePing`

| Test | Scenario |
|---|---|
| `test_happy_path_node_up` | Valid RPC response, no NOK counts → `send_message` not called with "down" |
| `test_node_down_sends_node_is_down` | `final_roll_count=0`, `nok_count=5` → `NODE_IS_DOWN` sent to all users |
| `test_api_error_timeout_sends_photo` | `"Request timed out."` in error → `send_photo` called with timeout image |
| `test_api_error_other_sends_photo` | Generic error → `send_photo` called with fire image |
| `test_extract_address_data_returns_none_sends_ping_failed` | `{"result": []}` → "Ping failed, invalid data" sent |
| `test_at_report_hour_sends_detailed_report` | `datetime.now()` mocked to 07:00 → detailed report sent |
| `test_exception_is_handled_gracefully` | `get_addresses` raises → no exception escapes |
| `test_no_lock_in_bot_data` | `balance_lock` absent → history updated via direct assignment |
| `test_photo_send_ioerror_is_handled` | `open()` raises `FileNotFoundError` when sending error photo → no exception |

### `TestRunCoroutineInLoop`

| Test | Scenario |
|---|---|
| `test_with_running_loop_uses_run_coroutine_threadsafe` | `loop.is_running()` → `asyncio.run_coroutine_threadsafe` called; `add_done_callback` registered |
| `test_with_idle_loop_uses_run_until_complete` | Loop not running → `loop.run_until_complete` called |
| `test_with_exception_logs_error` | `run_until_complete` raises → caught and logged, no re-raise |
| `test_done_callback_logs_exception` | Callback invoked with a future that has an exception → logged, no crash |
| `test_done_callback_no_exception` | Callback invoked with a clean future → silent |

---

## `tests/test_handlers_scheduler_extra.py` — `src/handlers/scheduler.py` (`run_async_func` + report hours)

### `TestRunAsyncFunc`

| Test | Scenario |
|---|---|
| `test_run_async_func_creates_new_event_loop_when_none_running` | `get_running_loop` raises `RuntimeError` → new loop created; job added; scheduler started |
| `test_run_async_func_reuses_existing_loop` | Existing loop returned → no new loop created; job still added |
| `test_run_async_func_removes_existing_job` | Stale job found via `get_job` → `remove_job` called first; scheduler already running so `start()` skipped |
| `test_run_async_func_handles_exception` | `new_event_loop` raises `OSError` → caught and logged, no re-raise |

### `TestPeriodicNodePingReportHours`

| Test | Scenario |
|---|---|
| `test_report_at_hour_12_with_empty_balance_history` | Hour 12, empty history → `NODE_IS_UP` sent |
| `test_report_at_hour_21_with_history` | Hour 21, history with temp entry → detailed report with temperature line sent |
| `test_non_report_hour_sends_no_message_when_node_up` | Hour 3, node up → no `send_message` |

---

## `tests/test_jrequests.py` — `src/jrequests.py`

**Coverage: 100%**

Verifies the backward-compatibility re-export facade.

| Test | Scenario |
|---|---|
| `test_get_addresses_is_callable` | Symbol is callable |
| `test_measure_rpc_latency_is_callable` | Symbol is callable |
| `test_get_bitcoin_price_is_callable` | Symbol is callable |
| `test_get_mas_instant_is_callable` | Symbol is callable |
| `test_get_mas_daily_is_callable` | Symbol is callable |
| `test_get_system_stats_is_callable` | Symbol is callable |
| `test_start_docker_node_is_callable` | Symbol is callable |
| `test_stop_docker_node_is_callable` | Symbol is callable |
| `test_exec_massa_client_is_callable` | Symbol is callable |
| `test_all_symbols_are_functions` | All 9 symbols verified callable in a loop |
| `test_get_addresses_points_to_massa_rpc` | `jrequests.get_addresses is services.massa_rpc.get_addresses` |
| `test_get_bitcoin_price_points_to_price_api` | Identity check against `services.price_api` |
| `test_get_system_stats_points_to_system_monitor` | Identity check against `services.system_monitor` |
| `test_start_docker_node_points_to_docker_manager` | Identity check against `services.docker_manager` |

---

## `tests/test_main.py` — `src/main.py`

**Coverage: 99%** (line 193, `if __name__ == '__main__':`, is unreachable during imports)

### `TestDisablePrints`

| Test | Scenario |
|---|---|
| `test_redirects_stdout_stderr` | After `disable_prints()`, `sys.stdout` and `sys.stderr` are replaced with `os.devnull` streams |

### `TestPostInit`

| Test | Scenario |
|---|---|
| `test_registers_commands_with_telegram` | `set_my_commands` called once with a non-empty list |
| `test_commands_have_correct_structure` | Each element is a `telegram.BotCommand` instance |

### `TestErrorHandler`

| Test | Scenario |
|---|---|
| `test_logs_error` | `context.error` set to an exception → `error_handler` completes without raising |

### `TestMainFunction`

| Test | Scenario |
|---|---|
| `test_missing_topology_returns_early` | `open()` raises `FileNotFoundError` → returns without starting the bot |
| `test_corrupt_topology_returns_early` | File contains invalid JSON → returns without starting |
| `test_missing_bot_token_returns_early` | `telegram_bot_token` key absent → returns without starting |

---

## `tests/test_coverage_gaps.py` — Targeted gap coverage

Covers specific edge-case branches in `handlers/node.py` and `handlers/scheduler.py` that are not exercised by the main test files.

### `TestNodeHandlerImagePaths`

| Test | Scenario |
|---|---|
| `test_image_exists_and_sent_successfully` | `create_png_plot` returns a path to an actual file; `reply_photo` called |
| `test_image_open_raises_oserror` | `open()` raises `OSError` for the plot file → error message sent instead of photo |

### `TestNodeHandlerNoImage`

| Test | Scenario |
|---|---|
| `test_image_file_not_created_sends_error` | `os.path.exists` returns `False` → "Image file was not created" sent |

### `TestNodeHandlerCleanup`

| Test | Scenario |
|---|---|
| `test_cleanup_removes_image_file` | Plot file exists after handler → `os.remove` called in finally block |
| `test_cleanup_ioerror_is_logged` | `os.remove` raises → error logged, no crash |

### Additional scheduler and flush tests covering IOError in `flush_confirm_yes/no`, temperature-only entries in the scheduler report, and entries with no temperature field.

---

## `tests/test_final_gaps.py` — Year-rollback edge cases

### `TestHistoryLegacyYearRollback`

Covers the `dt = dt.replace(year=current_year - 1)` branches in both `filter_since_midnight` and `filter_last_24h`. These are triggered when a legacy `DD/MM-HH:MM` key, when assigned the current year, would be more than 1 hour in the future (e.g. a Dec 31 entry processed on Jan 1).

| Test | Scenario |
|---|---|
| `test_filter_since_midnight_legacy_year_rollback` | Dec 31 23:00 key on Jan 1 00:30 → year rolled back to previous year; entry is before midnight → filtered out |
| `test_filter_last_24h_legacy_year_rollback` | Dec 31 12:00 key on Jan 1 01:00 → rolled back to Dec 31 of previous year; 13h ago → included |
| `test_filter_since_midnight_legacy_year_rollback_recent` | Dec 31 23:00 on Jan 1 02:00 → rolled back; still before midnight → filtered out |

### `TestIsRecentLegacyYearRollback`

| Test | Scenario |
|---|---|
| `test_legacy_key_in_future_gets_rolled_back` | Legacy key that with current year is in the future → rolled back; checked against cutoff |

---

## Mocking Strategy Summary

| External dependency | How it is mocked |
|---|---|
| Telegram `Update` / `Context` | `MagicMock` / `AsyncMock` via `conftest.py` fixtures |
| `requests.request` | `patch('services.http_client.requests.request', ...)` |
| `psutil` | `patch.dict('sys.modules', {'psutil': mock_psutil})` |
| Docker SDK | `patch('services.docker_manager._get_docker_client', ...)` |
| matplotlib GUI | `matplotlib.use('Agg')` in `conftest.py`; `patch('services.plotting.plt', ...)` for figure-close assertions |
| Filesystem | `tmp_path` + `patch('services.history.BALANCE_HISTORY_FILE', ...)` for history; `monkeypatch.chdir(tmp_path)` for plots |
| `subprocess.check_output` | `patch('handlers.system.subprocess.check_output', ...)` |
| `datetime.now()` | `patch('handlers.scheduler.datetime')` with `mock_dt.now.return_value = ...` |
| APScheduler | `patch('handlers.scheduler.BackgroundScheduler', ...)` |
| `asyncio` event loop | `patch('handlers.scheduler.asyncio.get_running_loop', ...)` / `asyncio.new_event_loop` |

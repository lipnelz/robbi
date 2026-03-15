"""Tests for src/main.py – testable functions excluding actual bot startup."""
import json
import os
import sys
import pytest
from unittest.mock import AsyncMock, MagicMock, patch, mock_open


# We import specific functions, not the whole module (which would trigger top-level config.py side effects)
import main as main_module


class TestDisablePrints:
    def test_redirects_stdout_stderr(self):
        original_stdout = sys.stdout
        original_stderr = sys.stderr
        try:
            main_module.disable_prints()
            assert sys.stdout is not sys.__stdout__
            assert sys.stderr is not sys.__stderr__
        finally:
            sys.stdout = original_stdout
            sys.stderr = original_stderr


class TestPostInit:
    async def test_registers_commands_with_telegram(self):
        mock_app = MagicMock()
        mock_app.bot = AsyncMock()
        mock_app.bot.set_my_commands = AsyncMock()
        await main_module.post_init(mock_app)
        mock_app.bot.set_my_commands.assert_called_once()
        commands = mock_app.bot.set_my_commands.call_args[0][0]
        assert len(commands) > 0

    async def test_commands_have_correct_structure(self):
        from telegram import BotCommand
        mock_app = MagicMock()
        mock_app.bot = AsyncMock()
        mock_app.bot.set_my_commands = AsyncMock()
        await main_module.post_init(mock_app)
        commands = mock_app.bot.set_my_commands.call_args[0][0]
        for cmd in commands:
            assert isinstance(cmd, BotCommand)


class TestErrorHandler:
    async def test_logs_error(self):
        update = MagicMock()
        context = MagicMock()
        context.error = Exception("something went wrong")
        # Must not raise
        await main_module.error_handler(update, context)


class TestMainFunction:
    def _topology(self):
        return {
            "telegram_bot_token": "fake-token",
            "user_white_list": {"admin": 12345},
            "massa_node_address": "AU1test",
            "ninja_api_key": "ninja123",
            "node_container_name": "massa-node",
            "massa_client_password": "pass",
            "massa_wallet_address": "AU1wallet",
            "massa_buy_rolls_fee": 0.01,
        }

    def test_missing_topology_returns_early(self, tmp_path):
        with patch('builtins.open', side_effect=FileNotFoundError("no file")):
            # Must return without raising
            main_module.main()

    def test_corrupt_topology_returns_early(self):
        with patch('builtins.open', mock_open(read_data="{invalid json")):
            main_module.main()

    def test_missing_bot_token_returns_early(self):
        config = self._topology()
        del config['telegram_bot_token']
        with patch('builtins.open', mock_open(read_data=json.dumps(config))):
            main_module.main()

    def test_missing_admin_returns_early(self):
        config = self._topology()
        config['user_white_list'] = {}
        with patch('builtins.open', mock_open(read_data=json.dumps(config))):
            main_module.main()

    def _run_main_mocked(self, addresses_result):
        """Helper that runs main() with everything mocked; returns the mock application."""
        config = self._topology()
        mock_app_builder = MagicMock()
        mock_app = MagicMock()
        mock_app.bot_data = {}
        mock_app_builder.token.return_value = mock_app_builder
        mock_app_builder.post_init.return_value = mock_app_builder
        mock_app_builder.request.return_value = mock_app_builder
        mock_app_builder.build.return_value = mock_app

        with patch('builtins.open', mock_open(read_data=json.dumps(config))), \
             patch('main.get_addresses', return_value=addresses_result), \
             patch('main.load_balance_history', return_value={}), \
             patch('main.Application.builder', return_value=mock_app_builder), \
             patch('main.run_async_func'):
            main_module.main()

        return mock_app

    def test_full_main_with_mocked_application(self):
        """Test main() with all dependencies mocked to avoid real network calls."""
        mock_app = self._run_main_mocked({"result": []})
        # run_polling must have been called on the application
        mock_app.run_polling.assert_called_once()

    def test_main_with_api_error_timeout(self):
        """Test main() when initial node check returns a timeout error."""
        # Must not raise; run_polling is still called
        mock_app = self._run_main_mocked({"error": "Request timed out."})
        mock_app.run_polling.assert_called_once()

    def test_main_with_api_error_other(self):
        """Test main() when initial node check returns a non-timeout error."""
        mock_app = self._run_main_mocked({"error": "Connection refused"})
        mock_app.run_polling.assert_called_once()

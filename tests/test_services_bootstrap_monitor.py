"""Test bootstrap_monitor service."""

import unittest
from unittest.mock import MagicMock
from services.bootstrap_monitor import get_bootstrap_status, format_bootstrap_status


class TestBootstrapMonitor(unittest.TestCase):
    """Test bootstrap monitoring."""

    def test_format_bootstrap_complete(self):
        """Test formatting complete bootstrap."""
        bootstrap_info = {
            "state": "complete",
            "progress_pct": 100,
            "current_server": None,
            "attempt_count": 5,
            "error": None,
            "retry_in_seconds": None,
            "time_elapsed": 300,
        }
        result = format_bootstrap_status(bootstrap_info)
        self.assertIn("✅ Bootstrap terminé", result)

    def test_format_bootstrap_in_progress(self):
        """Test formatting in-progress bootstrap."""
        bootstrap_info = {
            "state": "bootstrapping",
            "progress_pct": 44,
            "current_server": "198.27.74.5",
            "attempt_count": 4,
            "error": None,
            "retry_in_seconds": 60,
            "time_elapsed": 180,
        }
        result = format_bootstrap_status(bootstrap_info)
        self.assertIn("⏳ Bootstrap en cours", result)
        self.assertIn("198.27.74.5", result)
        self.assertIn("3m", result)  # 180 seconds = 3m

    def test_format_bootstrap_with_error(self):
        """Test formatting bootstrap with error."""
        bootstrap_info = {
            "state": "bootstrapping",
            "progress_pct": 22,
            "current_server": "158.69.23.120",
            "attempt_count": 2,
            "error": "Connection refused (os error 111)",
            "retry_in_seconds": 60,
            "time_elapsed": 120,
        }
        result = format_bootstrap_status(bootstrap_info)
        self.assertIn("⚠️ Erreur", result)
        self.assertIn("Connection refused", result)

    def test_format_bootstrap_none_state(self):
        """Test formatting unknown state."""
        result = format_bootstrap_status(None)
        self.assertIn("inconnu", result)

    def test_format_bootstrap_failed(self):
        """Test formatting failed state."""
        bootstrap_info = {
            "state": "failed",
            "progress_pct": 0,
            "current_server": None,
            "attempt_count": 0,
            "error": "All servers exhausted",
            "retry_in_seconds": None,
            "time_elapsed": None,
        }
        result = format_bootstrap_status(bootstrap_info)
        self.assertIn("❌ Bootstrap échoué", result)

    def test_get_bootstrap_status_parsing(self):
        """Test bootstrap log parsing."""
        # Mock container with sample logs
        mock_container = MagicMock()
        mock_container.logs.return_value = b"""2026-11-07T13:57:55.100637Z  INFO massa_bootstrap::client: Start bootstrapping from 198.27.74.5:31245
2026-11-07T13:57:55.618057Z  WARN massa_bootstrap::client: Error while bootstrapping: `massa_signature` error Signature error : Signature verification failed: signature error: Verification equation was not satisfied
2026-11-07T13:57:55.618299Z  INFO massa_bootstrap::client: Bootstrap from server 198.27.74.5:31245 failed. Your node will try to bootstrap from another server in 1m.
2026-11-07T13:58:55.618617Z  INFO massa_bootstrap::client: Start bootstrapping from 158.69.23.120:31245
2026-11-07T13:58:55.721593Z  WARN massa_bootstrap::client: Error while connecting to bootstrap server: Bootstrap IO error: Connection refused (os error 111)
2026-11-07T13:58:55.721623Z  INFO massa_bootstrap::client: Bootstrap from server 158.69.23.120:31245 failed. Your node will try to bootstrap from another server in 1m.
"""
        
        result = get_bootstrap_status(mock_container)
        
        self.assertEqual(result["state"], "bootstrapping")
        self.assertEqual(result["attempt_count"], 2)
        self.assertEqual(result["current_server"], "158.69.23.120:31245")
        self.assertEqual(result["retry_in_seconds"], 60)
        self.assertEqual(result["error"], "Connection refused (os error 111)")

    def test_get_bootstrap_status_complete(self):
        """Test bootstrap completion parsing."""
        mock_container = MagicMock()
        mock_container.logs.return_value = b"""2026-11-07T13:57:55.100637Z  INFO massa_bootstrap::client: Start bootstrapping from 198.27.74.5:31245
2026-11-07T14:10:00.000000Z  INFO massa_bootstrap::client: Successful bootstrap
"""
        
        result = get_bootstrap_status(mock_container)
        self.assertEqual(result["state"], "complete")
        self.assertEqual(result["progress_pct"], 100)

    def test_get_bootstrap_status_no_logs(self):
        """Test with empty logs."""
        mock_container = MagicMock()
        mock_container.logs.return_value = b""
        
        result = get_bootstrap_status(mock_container)
        self.assertEqual(result["state"], "unknown")
        self.assertEqual(result["attempt_count"], 0)

    def test_get_bootstrap_status_docker_error(self):
        """Test Docker error handling."""
        mock_container = MagicMock()
        mock_container.logs.side_effect = Exception("Docker error")
        
        result = get_bootstrap_status(mock_container)
        self.assertEqual(result["state"], "unknown")
        self.assertIn("Docker error", result["error"])


if __name__ == '__main__':
    unittest.main()

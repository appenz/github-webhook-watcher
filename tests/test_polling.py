"""Tests for polling functionality."""

import os
from unittest.mock import patch, AsyncMock, MagicMock
import pytest
import logging

from webhookclient.main import main, run_poller

@pytest.mark.asyncio
async def test_run_poller_uses_polling_interval():
    """Test that run_poller uses the configured polling interval."""
    # Mock dependencies
    logger = MagicMock(spec=logging.Logger)
    session = AsyncMock()
    session.get.return_value.__aenter__.return_value.status = 200
    session.get.return_value.__aenter__.return_value.json.return_value = {
        "data": [], "iterator": "", "done": True
    }
    
    with patch("aiohttp.ClientSession", return_value=session):
        with patch("asyncio.sleep", AsyncMock()) as mock_sleep:
            # Run for one iteration then raise to exit
            mock_sleep.side_effect = KeyboardInterrupt()
            
            # Test with custom interval
            with pytest.raises(KeyboardInterrupt):
                await run_poller("http://test", "key", logger, poll_interval=45)
            
            # Verify sleep was called with correct interval
            mock_sleep.assert_called_once_with(45)

def test_main_default_polling_interval():
    """Test that main uses default polling interval when not configured."""
    with patch.dict(os.environ, {
        "SVIX_ENDPOINT_URL": "http://test",
        "SVIX_API_KEY": "key"
    }):
        with patch("webhookclient.main.run_poller") as mock_run_poller:
            with patch("logging.getLogger"):
                main()
                # Verify run_poller was called with default interval
                mock_run_poller.assert_called_once()
                assert mock_run_poller.call_args.kwargs["poll_interval"] == 30

def test_main_custom_polling_interval():
    """Test that main uses custom polling interval when configured."""
    with patch.dict(os.environ, {
        "SVIX_ENDPOINT_URL": "http://test",
        "SVIX_API_KEY": "key",
        "SVIX_POLLING_INTERVAL": "45"
    }):
        with patch("webhookclient.main.run_poller") as mock_run_poller:
            with patch("logging.getLogger"):
                main()
                # Verify run_poller was called with custom interval
                mock_run_poller.assert_called_once()
                assert mock_run_poller.call_args.kwargs["poll_interval"] == 45

def test_main_invalid_polling_interval():
    """Test that main handles invalid polling interval."""
    with patch.dict(os.environ, {
        "SVIX_ENDPOINT_URL": "http://test",
        "SVIX_API_KEY": "key",
        "SVIX_POLLING_INTERVAL": "invalid"
    }):
        with patch("logging.getLogger") as mock_logger:
            main()
            # Verify error was logged
            mock_logger.return_value.error.assert_called_with(
                "Invalid SVIX_POLLING_INTERVAL: invalid literal for int() with base 10: 'invalid'"
            )

def test_main_negative_polling_interval():
    """Test that main handles negative polling interval."""
    with patch.dict(os.environ, {
        "SVIX_ENDPOINT_URL": "http://test",
        "SVIX_API_KEY": "key",
        "SVIX_POLLING_INTERVAL": "-30"
    }):
        with patch("logging.getLogger") as mock_logger:
            main()
            # Verify error was logged
            mock_logger.return_value.error.assert_called_with(
                "Invalid SVIX_POLLING_INTERVAL: Polling interval must be positive"
            )

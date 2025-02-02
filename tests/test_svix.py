"""Tests for Svix message consumer functionality."""

import os
from unittest.mock import MagicMock, patch

import pytest
from svix.api import MessageAttempt, Svix

from intra_deploy import deploy, process_webhook_payload, poll_messages, main

@pytest.fixture
def mock_env_vars(monkeypatch):
    """Set up mock environment variables."""
    monkeypatch.setenv("WEBHOOK_URL", "test_endpoint")
    monkeypatch.setenv("WEBHOOK_SECRET", "test_secret")

@pytest.fixture
def mock_svix():
    """Create a mock Svix client."""
    mock = MagicMock(spec=Svix)
    mock.message_attempt = MagicMock()
    mock.message_attempt.list_attempt_by_endpoint = MagicMock()
    return mock

@pytest.fixture
def mock_message():
    """Create a mock Svix message."""
    message = MagicMock(spec=MessageAttempt)
    message.payload = {}
    message.msg = MagicMock()
    message.msg.id = "msg_test"
    return message

def test_process_webhook_payload_master(mock_message):
    """Test processing a master branch push."""
    mock_message.payload = {"ref": "refs/heads/master"}
    
    with patch("intra_deploy.main.deploy") as mock_deploy:
        process_webhook_payload(mock_message)
        mock_deploy.assert_called_once()

def test_process_webhook_payload_main(mock_message):
    """Test processing a main branch push."""
    mock_message.payload = {"ref": "refs/heads/main"}
    
    with patch("intra_deploy.main.deploy") as mock_deploy:
        process_webhook_payload(mock_message)
        mock_deploy.assert_called_once()

def test_process_webhook_payload_other(mock_message):
    """Test processing a push to another branch."""
    mock_message.payload = {"ref": "refs/heads/feature"}
    
    with patch("intra_deploy.main.deploy") as mock_deploy:
        process_webhook_payload(mock_message)
        mock_deploy.assert_not_called()

def test_poll_messages_success(mock_svix, mock_message):
    """Test successful message polling."""
    mock_svix.message_attempt.list_attempt_by_endpoint.return_value = [mock_message]
    mock_message.payload = {"ref": "refs/heads/master"}
    
    with patch("intra_deploy.deploy") as mock_deploy:
        with patch("time.sleep") as mock_sleep:
            poll_messages(mock_svix, "test_endpoint", max_iterations=1)
            mock_deploy.assert_called_once()
            mock_sleep.assert_called_once_with(1)

def test_poll_messages_api_error(mock_svix):
    """Test API error handling."""
    mock_svix.message_attempt.list_attempt_by_endpoint.side_effect = Exception("API Error")
    
    with patch("time.sleep") as mock_sleep:
        intra_deploy.main.poll_messages(mock_svix, "test_endpoint", max_iterations=1)
        mock_sleep.assert_called_once_with(2)  # Should backoff to 2 seconds

def test_main_success(mock_env_vars):
    """Test successful main function execution."""
    with patch("svix.api.Svix") as mock_svix_class:
        with patch("intra_deploy.main.poll_messages") as mock_poll:
            intra_deploy.main.main(max_iterations=1)
            mock_svix_class.assert_called_once_with(os.getenv("WEBHOOK_SECRET"))
            mock_poll.assert_called_once()

def test_main_missing_env(monkeypatch):
    """Test main function with missing environment variables."""
    monkeypatch.delenv("WEBHOOK_URL", raising=False)
    monkeypatch.delenv("WEBHOOK_SECRET", raising=False)
    
    with patch("svix.api.Svix") as mock_svix_class:
        main()
        mock_svix_class.assert_not_called()

def test_main_svix_error(mock_env_vars):
    """Test main function with Svix initialization error."""
    with patch("svix.api.Svix") as mock_svix_class:
        mock_svix_class.side_effect = Exception("Svix error")
        with patch("sys.exit") as mock_exit:
            main()
            mock_exit.assert_called_once_with(1)

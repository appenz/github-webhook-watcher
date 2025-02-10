"""Tests for webhook handling functionality."""

import json
from unittest.mock import patch

import pytest
from svix.webhooks import WebhookVerificationError

from webhookclient.main import process_webhook_payload, verify_webhook

def test_process_webhook_payload_master_push():
    """Test that a push to master triggers deploy."""
    payload = {"ref": "refs/heads/master"}
    headers = {"x-github-event": "push"}
    with patch("webhookclient.main.deploy") as mock_deploy:
        process_webhook_payload(payload, headers)
        mock_deploy.assert_called_once()

def test_process_webhook_payload_other_branch():
    """Test that a push to another branch doesn't trigger deploy."""
    payload = {"ref": "refs/heads/feature"}
    headers = {"x-github-event": "push"}
    with patch("webhookclient.main.deploy") as mock_deploy:
        process_webhook_payload(payload, headers)
        mock_deploy.assert_not_called()

def test_verify_webhook_valid():
    """Test webhook verification with valid signature."""
    import base64
    secret = base64.b64encode(b"test_secret").decode()
    payload = {"test": "data"}
    payload_bytes = json.dumps(payload).encode()
    
    # Create valid headers using svix
    import time
    from svix.webhooks import Webhook
    wh = Webhook(secret)
    from datetime import datetime, timezone
    timestamp = datetime.now(timezone.utc)
    msg_id = "msg_test"
    signature = wh.sign(msg_id=msg_id, timestamp=timestamp, data=payload_bytes.decode())
    headers = {
        "svix-id": msg_id,
        "svix-timestamp": str(int(timestamp.timestamp())),
        "svix-signature": signature
    }
    
    result = verify_webhook(payload_bytes, headers, secret)
    assert result == payload

def test_verify_webhook_invalid():
    """Test webhook verification with invalid signature."""
    import base64
    secret = base64.b64encode(b"test_secret").decode()
    payload = {"test": "data"}
    payload_bytes = json.dumps(payload).encode()
    
    # Create invalid headers
    headers = {"svix-signature": "invalid_signature"}
    
    with pytest.raises(WebhookVerificationError):
        verify_webhook(payload_bytes, headers, secret)

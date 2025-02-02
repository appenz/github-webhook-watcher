"""Main entry point for intra-deploy webhook watcher."""

import json
import logging
import os
from pathlib import Path
from typing import Any

from svix.webhooks import Webhook, WebhookVerificationError

def setup_logging() -> None:
    """Configure logging to write to ~/Library/Logs/intra-deploy/intra-deploy.log."""
    log_dir = Path.home() / "Library/Logs/intra-deploy"
    log_dir.mkdir(parents=True, exist_ok=True)
    log_file = log_dir / "intra-deploy.log"
    
    logging.basicConfig(
        level=logging.INFO,
        format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
        handlers=[
            logging.FileHandler(log_file),
            logging.StreamHandler()  # Also log to console
        ]
    )

def deploy() -> None:
    """Empty deploy function to be implemented later."""
    logging.info("Deploy function called (empty implementation)")

def process_webhook_payload(payload: dict[str, Any]) -> None:
    """Process the GitHub webhook payload and trigger deploy if needed."""
    # Check if this is a push to master/main branch
    if (
        payload.get("ref") == "refs/heads/master" 
        or payload.get("ref") == "refs/heads/main"
    ):
        logging.info("Push to master/main branch detected, triggering deploy")
        deploy()
    else:
        logging.info(f"Ignoring push to {payload.get('ref')}")

def verify_webhook(
    payload: bytes, 
    headers: dict[str, str], 
    webhook_secret: str
) -> dict[str, Any]:
    """Verify the webhook signature and return the decoded payload."""
    wh = Webhook(webhook_secret)
    try:
        return wh.verify(payload, headers)
    except WebhookVerificationError as e:
        logging.error(f"Webhook verification failed: {e}")
        raise

def main() -> None:
    """Main entry point for the webhook watcher."""
    setup_logging()
    logger = logging.getLogger(__name__)
    
    # Get configuration from environment
    webhook_url = os.getenv("WEBHOOK_URL")
    webhook_secret = os.getenv("WEBHOOK_SECRET")
    
    if not webhook_url or not webhook_secret:
        logger.error("WEBHOOK_URL and WEBHOOK_SECRET must be set in environment")
        return
    
    logger.info(f"Starting webhook watcher for URL: {webhook_url}")
    
    # TODO: Implement webhook listening using svix
    # This would typically involve setting up a server to listen for webhook requests
    # For now, this is a placeholder as the exact implementation depends on how
    # we want to handle the incoming webhooks (e.g., using FastAPI, Flask, etc.)
    
if __name__ == "__main__":
    main()

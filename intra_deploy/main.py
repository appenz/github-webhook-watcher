"""Main entry point for intra-deploy webhook watcher."""

import json
import logging
import os
from pathlib import Path
from typing import Any

from svix.api import Svix, SvixAsync
from svix.webhooks import Webhook, WebhookVerificationError
import asyncio

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

async def listen_for_messages(svix: SvixAsync, logger: logging.Logger) -> None:
    """Listen for messages from Svix message queue.
    
    Args:
        svix: Initialized Svix client
        logger: Logger instance for output
    """
    try:
        async for msg in svix.message.listen_to_app_messages():
            try:
                # Process the message payload
                payload = msg.payload
                logger.info(f"Received message: {msg.event_type}")
                process_webhook_payload(payload)
            except Exception as e:
                logger.error(f"Error processing message: {e}")
    except Exception as e:
        logger.error(f"Error in message listener: {e}")
        raise

async def async_main() -> None:
    """Async main entry point for the webhook watcher."""
    setup_logging()
    logger = logging.getLogger(__name__)
    
    # Get configuration from environment
    svix_api_key = os.getenv("SVIX_API_KEY")
    
    if not svix_api_key:
        logger.error("SVIX_API_KEY must be set in environment")
        return
    
    logger.info("Starting Svix message listener")
    
    # Initialize Svix client
    svix = SvixAsync(svix_api_key)
    
    try:
        await listen_for_messages(svix, logger)
    except KeyboardInterrupt:
        logger.info("Shutting down...")
    finally:
        await svix.close()

def main() -> None:
    """Main entry point that runs the async loop."""
    asyncio.run(async_main())

if __name__ == "__main__":
    main()

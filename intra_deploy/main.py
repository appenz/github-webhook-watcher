"""Main entry point for intra-deploy webhook watcher using Svix message consumer."""

import logging
import os
import signal
import sys
import time
from pathlib import Path
from typing import Any, NoReturn, Optional

from svix.api import Svix, SvixOptions, MessageAttempt, MessageIn
from svix.exceptions import HttpError as ApiException

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

def process_webhook_payload(message: MessageAttempt) -> None:
    """Process the GitHub webhook payload from Svix message and trigger deploy if needed.
    
    Args:
        message: Svix message attempt containing the GitHub webhook payload
    """
    logger = logging.getLogger(__name__)
    payload = message.payload

    # Check if this is a push to master/main branch
    if (
        payload.get("ref") == "refs/heads/master" 
        or payload.get("ref") == "refs/heads/main"
    ):
        logger.info("Push to master/main branch detected, triggering deploy")
        deploy()
    else:
        logger.info(f"Ignoring push to {payload.get('ref')}")

def handle_signal(signum: int, _: Any) -> NoReturn:
    """Handle system signals gracefully.
    
    Args:
        signum: Signal number received
        _: Frame object (unused)
    """
    logger = logging.getLogger(__name__)
    logger.info(f"Received signal {signum}, shutting down...")
    sys.exit(0)

def poll_messages(svix: Svix, endpoint_id: str, max_iterations: int = None) -> None:
    """Poll for messages from Svix with exponential backoff.
    
    Args:
        svix: Svix client instance
        endpoint_id: ID of the endpoint to poll messages from
        max_iterations: Maximum number of polling iterations (for testing)
    """
    logger = logging.getLogger(__name__)
    base_delay = 1  # Start with 1 second delay
    max_delay = 60  # Maximum delay between retries in seconds
    current_delay = base_delay
    iterations = 0

    while max_iterations is None or iterations < max_iterations:
        iterations += 1
        try:
            # List message attempts for the endpoint
            # We only care about recent messages, so limit to last 100
            iterator = svix.message_attempt.list_attempt_by_endpoint(
                endpoint_id,
                limit=100,
                status="success"  # Only get successfully delivered messages
            )

            for msg in iterator:
                try:
                    process_webhook_payload(msg)
                    # Reset delay on successful processing
                    current_delay = base_delay
                except Exception as e:
                    logger.error(f"Error processing message {msg.id}: {e}")

            # Small delay between polling to avoid hammering the API
            time.sleep(current_delay)

        except ApiException as e:
            logger.error(f"Svix API error: {e}")
            # Implement exponential backoff
            current_delay = min(current_delay * 2, max_delay)
            time.sleep(current_delay)
            continue

        except Exception as e:
            logger.error(f"Unexpected error while polling messages: {e}")
            current_delay = min(current_delay * 2, max_delay)
            time.sleep(current_delay)
            continue

def main(max_iterations: int = None) -> None:
    """Main entry point for the webhook watcher.
    
    Args:
        max_iterations: Maximum number of polling iterations (for testing)
    """
    setup_logging()
    logger = logging.getLogger(__name__)
    
    # Get configuration from environment
    webhook_url = os.getenv("WEBHOOK_URL")  # Using as endpoint ID
    webhook_secret = os.getenv("WEBHOOK_SECRET")  # Using as Svix API key
    
    if not webhook_url or not webhook_secret:
        logger.error("WEBHOOK_URL and WEBHOOK_SECRET must be set in environment")
        return
    
    logger.info(f"Starting Svix message consumer for endpoint: {webhook_url}")
    
    # Set up signal handlers for graceful shutdown
    signal.signal(signal.SIGINT, handle_signal)
    signal.signal(signal.SIGTERM, handle_signal)
    
    try:
        # Initialize Svix client
        svix = Svix(webhook_secret)
        
        # Log ready state
        logger.info("Svix client initialized and ready to consume messages")
        
        # Start polling for messages
        poll_messages(svix, webhook_url, max_iterations=max_iterations)
        
    except Exception as e:
        logger.error(f"Error in Svix message consumer: {e}")
        sys.exit(1)

if __name__ == "__main__":
    main()

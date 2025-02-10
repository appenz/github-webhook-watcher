"""Main entry point for intra-deploy webhook watcher."""

import asyncio
import json
import logging
import os
import signal
import sys
from pathlib import Path
from typing import Any, Optional

import aiohttp
from svix.webhooks import Webhook, WebhookVerificationError

def setup_logging() -> None:
    """Configure logging to write to ~/Library/Logs/webhook_client.log."""
    log_dir = Path.home() / "Library/Logs"
    log_dir.mkdir(parents=True, exist_ok=True)
    log_file = log_dir / "webhook_client.log"
    
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

def process_webhook_payload(payload: dict[str, Any], headers: dict[str, Any]) -> None:
    """Process the GitHub webhook payload and trigger deploy if needed."""

    # Insert custom logic here.

    event = headers.get("x-github-event")
    repo = payload.get("repository", {}).get("full_name")
    branch = payload.get("ref")

    print(f"Received event: {event} for repo: {repo} on branch: {branch}")

    # In case of a push to main or master branch, trigger a deploy.
    if event == "push" and (branch == "refs/heads/master" or branch == "refs/heads/main"):
        logging.info(f"Push to master detected, triggering deploy.")
        deploy()
 

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

async def poll_messages(
    session: aiohttp.ClientSession,
    endpoint_url: str,
    api_key: str,
    logger: logging.Logger,
    iterator: Optional[str] = None
) -> tuple[list[dict[str, Any]], str, bool]:
    """Poll for messages from Svix endpoint.
    
    Args:
        session: aiohttp client session
        endpoint_url: Svix polling endpoint URL
        api_key: Svix API key
        logger: Logger instance
        iterator: Optional iterator from previous poll
        
    Returns:
        Tuple of (messages, next_iterator, done)
    """
    headers = {
        "Authorization": f"Bearer {api_key}",
        "Content-Type": "application/json",
        "Accept": "application/json"
    }
    
    url = endpoint_url
    if iterator:
        url = f"{endpoint_url}?iterator={iterator}"
        
    try:
        async with session.get(url, headers=headers) as response:
            if response.status != 200:
                logger.error(f"Failed to poll messages: {response.status}")
                return [], "", True
                
            data = await response.json()
            # Parse json data and print it
            #print(json.dumps(data, indent=4))
            return data.get("data", []), data.get("iterator", ""), data.get("done", True)
            
    except Exception as e:
        logger.error(f"Error polling messages: {e}")
        return [], "", True

async def process_messages(
    messages: list[dict[str, Any]],
    logger: logging.Logger
) -> None:
    """Process a batch of messages from Svix.
    
    Args:
        messages: List of message payloads
        logger: Logger instance
    """
    for msg in messages:
        try:
            payload = msg.get("payload", {})
            headers = msg.get("headers", {})
            logger.info(f"Processing message: {msg.get('id')}")
            process_webhook_payload(payload, headers)
        except Exception as e:
            logger.error(f"Error processing message {msg.get('id')}: {e}")

async def run_poller(
    endpoint_url: str,
    api_key: str,
    logger: logging.Logger,
    poll_interval: int = 30
) -> None:
    """Run the polling loop.
    
    Args:
        endpoint_url: Svix polling endpoint URL
        api_key: Svix API key
        logger: Logger instance
        poll_interval: Seconds to wait between polls
    """
    iterator: Optional[str] = None
    
    async with aiohttp.ClientSession() as session:
        while True:
            messages, next_iterator, done = await poll_messages(session, endpoint_url, api_key, logger, iterator)
            if messages:
                await process_messages(messages, logger)
                
            iterator = next_iterator    
            await asyncio.sleep(poll_interval)

def handle_shutdown(signum: int, frame: Any) -> None:
    """Handle shutdown signals gracefully."""
    logger = logging.getLogger(__name__)
    logger.info(f"Received signal {signum}, shutting down...")
    sys.exit(0)

def main() -> None:
    """Main entry point for the webhook watcher."""
    setup_logging()
    logger = logging.getLogger(__name__)
    
    # Get configuration from environment
    endpoint_url = os.getenv("SVIX_ENDPOINT_URL")
    api_key = os.getenv("SVIX_API_KEY")
    
    if not endpoint_url or not api_key:
        logger.error("SVIX_ENDPOINT_URL and SVIX_API_KEY must be set in environment")
        return

    # Get optional polling interval
    try:
        poll_interval = int(os.getenv("SVIX_POLLING_INTERVAL", "30"))
        if poll_interval <= 0:
            raise ValueError("Polling interval must be positive")
    except ValueError as e:
        logger.error(f"Invalid SVIX_POLLING_INTERVAL: {e}")
        return
    
    logger.info(f"Starting Svix poller for endpoint: {endpoint_url} with {poll_interval}s interval")
    
    # Setup signal handlers for graceful shutdown
    signal.signal(signal.SIGINT, handle_shutdown)
    signal.signal(signal.SIGTERM, handle_shutdown)
    
    try:
        asyncio.run(run_poller(endpoint_url, api_key, logger, poll_interval=poll_interval))
    except KeyboardInterrupt:
        logger.info("Shutting down...")
    except Exception as e:
        logger.error(f"Fatal error: {e}")
        sys.exit(1)

if __name__ == "__main__":
    main()

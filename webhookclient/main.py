import asyncio
import json
import logging
import os
import signal
import sys
import subprocess
from pathlib import Path
from typing import Any, Optional
import argparse

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

def update_local() -> None:
    """Update a GitHub repository locally by cloning or pulling changes."""
    logger = logging.getLogger(__name__)
    
    github_repo = os.getenv("GITHUB_REPO")
    
    # Get local directory from environment or use default
    local_base = os.getenv("LOCAL_DIRECTORY")
    if not local_base:
        local_base = str(Path.home() / "deployments")
    
    # Create base directory if it doesn't exist
    base_path = Path(local_base).expanduser()
    base_path.mkdir(parents=True, exist_ok=True)
    
    # Extract repo name from full repo path
    repo_name = github_repo.split('/')[-1]
    repo_path = base_path / repo_name
    repo_url = f"https://github.com/{github_repo}.git"
    
    try:
        if not repo_path.exists():
            # Clone the repository if it doesn't exist
            logger.info(f"Cloning repository {github_repo} to {repo_path}")
            result = subprocess.run(
                ["git", "clone", repo_url],
                cwd=str(base_path),
                capture_output=True,
                text=True,
                check=True
            )
            logger.info(f"Clone successful: {result.stdout.strip()}")
        else:
            # Pull latest changes if repository exists
            logger.info(f"Updating {github_repo} in {repo_path}")
            
            # First fetch the latest changes
            subprocess.run(
                ["git", "fetch", "origin"],
                cwd=str(repo_path),
                capture_output=True,
                text=True,
                check=True
            )
            
            # Then reset to match the remote branch
            try:
                # Get current branch
                current_branch = subprocess.check_output(
                    ["git", "rev-parse", "--abbrev-ref", "HEAD"],
                    cwd=str(repo_path),
                    universal_newlines=True
                ).strip()
                
                # Reset to match the remote branch but keep untracked files
                reset_cmd = ["git", "reset", "--hard", f"origin/{current_branch}"]
                result = subprocess.run(
                    reset_cmd,
                    cwd=str(repo_path),
                    capture_output=True,
                    text=True,
                    check=True
                )
                logger.info(f"Update successful: {result.stdout.strip()}")
            except subprocess.CalledProcessError as e:
                logger.error(f"Git reset failed: {e.stderr.strip()}")
                raise
            
    except subprocess.CalledProcessError as e:
        error_msg = f"Git operation failed: {e.stderr.strip()}"
        logger.error(error_msg)
        raise RuntimeError(error_msg) from e
    except Exception as e:
        error_msg = f"Unexpected error during update: {str(e)}"
        logger.error(error_msg)
        raise RuntimeError(error_msg) from e

def process_webhook_payload(payload: dict[str, Any], headers: dict[str, Any]) -> None:
    """Process the GitHub webhook payload and trigger update if needed."""
    args = parse_args()  # Get command line arguments
    logger = logging.getLogger(__name__)

    event = headers.get("x-github-event")
    repo = payload.get("repository", {}).get("full_name")
    branch = payload.get("ref")

    logger.info(f"Received event: {event} for repo: {repo} on branch: {branch}")

    # Handle update option
    if args.update:
        if event == "push" and (branch == "refs/heads/master" or branch == "refs/heads/main"):
            logger.info(f"Push to main/master detected, triggering update")
            update_local()
            if args.deploy:
                deploy_project()
        else:
            # For any webhook event, check if project needs to be restarted
            if args.deploy:
                check_and_restart_if_needed()

    check_and_restart_if_needed()

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
    """Poll for messages from Svix endpoint and return (messages, iterator, done)."""
    headers = {
        "Authorization": f"Bearer {api_key}",
        "Content-Type": "application/json",
        "Accept": "application/json"
    }
    
    url = endpoint_url
    if iterator:
        url = f"{endpoint_url}?iterator={iterator}"
        
    try:
        async with await session.get(url, headers=headers) as response:
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
    """Process a batch of webhook messages from Svix."""
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
    """Run the polling loop to continually check for new webhook messages."""
    iterator: Optional[str] = None
    args = parse_args()
    
    async with aiohttp.ClientSession() as session:
        while True:
            messages, next_iterator, done = await poll_messages(session, endpoint_url, api_key, logger, iterator)
            if messages:
                await process_messages(messages, logger)
            
            # Check project health on every poll cycle if in deploy mode
            if args.deploy:
                check_and_restart_if_needed()
                
            iterator = next_iterator    
            await asyncio.sleep(poll_interval)

def handle_shutdown(signum: int, frame: Any) -> None:
    """Handle shutdown signals gracefully and stop any running project."""
    logger = logging.getLogger(__name__)
    logger.info(f"Received signal {signum}, shutting down...")
    
    # Check if we're in deploy mode (GREPCOMMAND is set)
    if os.getenv("GREPCOMMAND"):
        logger.info("Stopping any running project before exit")
        try:
            stop_project()
        except Exception as e:
            logger.error(f"Error stopping project during shutdown: {e}")
    
    sys.exit(0)

def install_launch_agent() -> None:
    """Install webhookclient as a macOS launch agent."""
    logger = logging.getLogger(__name__)
    
    try:
        # Get paths
        working_dir = os.path.abspath(os.getcwd())
        script_path = os.path.join(working_dir, "webhookclient/main.py")
        env_file_path = os.path.join(working_dir, ".env")
        log_dir = os.path.expanduser("~/Library/Logs")
        template_path = Path("templates/net.appenzeller.webhookclient.plist")
        
        # Find uv path
        try:
            uv_path = subprocess.run(
                ["which", "uv"],
                capture_output=True,
                text=True,
                check=True
            ).stdout.strip()
        except subprocess.CalledProcessError:
            logger.error("Could not find 'uv' in PATH")
            print("Error: 'uv' command not found. Please ensure uv is installed.")
            sys.exit(1)
        
        # Load template
        with open(template_path, "r") as f:
            plist_content = f.read()
        
        # Replace placeholders
        plist_content = plist_content.replace("{{UV_PATH}}", uv_path)
        plist_content = plist_content.replace("{{ENV_FILE_PATH}}", env_file_path)
        plist_content = plist_content.replace("{{SCRIPT_PATH}}", script_path)
        plist_content = plist_content.replace("{{WORKING_DIR}}", working_dir)
        plist_content = plist_content.replace("{{LOG_DIR}}", log_dir)
        
        # Create launch agents directory if it doesn't exist
        launch_agents_dir = Path.home() / "Library/LaunchAgents"
        launch_agents_dir.mkdir(parents=True, exist_ok=True)
        
        # Write the plist file
        plist_path = launch_agents_dir / "net.appenzeller.webhookclient.plist"
        with open(plist_path, "w") as f:
            f.write(plist_content)
        
        logger.info(f"Created launch agent plist at {plist_path}")
        
        # Load the launch agent
        subprocess.run(
            ["launchctl", "load", str(plist_path)],
            check=True,
            capture_output=True,
            text=True
        )
        
        logger.info("Successfully loaded webhook client launch agent")
        print("Webhookclient installed as launch agent and started")
        
    except Exception as e:
        logger.error(f"Failed to install launch agent: {e}")
        print(f"Error installing launch agent: {e}")
        sys.exit(1)

def uninstall_launch_agent() -> None:
    """Uninstall webhookclient launch agent."""
    logger = logging.getLogger(__name__)
    
    try:
        plist_path = Path.home() / "Library/LaunchAgents" / "net.appenzeller.webhookclient.plist"
        
        # Check if the plist file exists
        if not plist_path.exists():
            logger.warning(f"Launch agent plist not found at {plist_path}")
            print("No webhookclient launch agent found to uninstall")
            return
        
        # Unload the launch agent
        subprocess.run(
            ["launchctl", "unload", str(plist_path)],
            check=True,
            capture_output=True,
            text=True
        )
        
        # Remove the plist file
        plist_path.unlink()
        
        logger.info("Successfully uninstalled webhook client launch agent")
        print("Webhookclient launch agent uninstalled")
        
    except Exception as e:
        logger.error(f"Failed to uninstall launch agent: {e}")
        print(f"Error uninstalling launch agent: {e}")
        sys.exit(1)

def parse_args() -> argparse.Namespace:
    """Parse command line arguments."""
    parser = argparse.ArgumentParser(
        description="GitHub WebHook Client that watches and processes GitHub webhooks via Svix"
    )
    parser.add_argument(
        "--update",
        action="store_true",
        help="Watch for pushes to main branch and update local repo"
    )
    parser.add_argument(
        "--deploy",
        action="store_true",
        help="Perform a separate deployment step after local update"
    )
    parser.add_argument(
        "--install",
        action="store_true",
        help="Install webhookclient as a macOS launch agent"
    )
    parser.add_argument(
        "--uninstall",
        action="store_true",
        help="Uninstall webhookclient launch agent"
    )
    return parser.parse_args()

def check_project() -> bool:
    """Check if the project is already running and return True if found."""
    logger = logging.getLogger(__name__)
    grep_command = os.getenv("GREPCOMMAND")
    
    try:
        # Use pgrep command to find processes matching the grep pattern
        result = subprocess.run(
            ["pgrep", "-f", grep_command],
            capture_output=True,
            text=True
        )
        
        # If exit code is 0, process exists
        if result.returncode == 0:
            logger.info(f"Project matching '{grep_command}' is already running")
            return True
        else:
            logger.info(f"No processes matching '{grep_command}' are running")
            return False
    except Exception as e:
        logger.error(f"Error checking if project is running: {e}")
        return False

def start_project() -> None:
    """Start the project if not already running, with output to log file."""
    logger = logging.getLogger(__name__)
    
    # Don't start if already running
    if check_project():
        logger.info("Project already running, not starting again")
        return
    
    github_repo = os.getenv("GITHUB_REPO")
    run_command = os.getenv("RUNCOMMAND")
    grep_command = os.getenv("GREPCOMMAND")
    additional_path = os.getenv("ADDITIONAL_PATH")
    
    project_name = github_repo.split('/')[-1]
    
    # Get local directory from environment or use default
    local_base = os.getenv("LOCAL_DIRECTORY")
    if not local_base:
        local_base = str(Path.home() / "deployments")
    
    # Path to the project directory
    project_path = Path(local_base).expanduser() / project_name
    
    # Create logs directory if it doesn't exist
    logs_dir = Path.home() / "Library/Logs"
    logs_dir.mkdir(parents=True, exist_ok=True)
    log_file = logs_dir / f"{project_name}.log"
    
    try:
        logger.info(f"Starting project with command: {run_command}")
        logger.info(f"Project will be identifiable with pattern: {grep_command}")
        
        # Start the process in the background, redirecting output to log file
        with open(log_file, "a") as f:
            env = os.environ.copy()
            if additional_path:
                env["PATH"] = f"{additional_path}:{env['PATH']}"
            process = subprocess.Popen(
                run_command,
                shell=True,
                cwd=str(project_path),
                stdout=f,
                stderr=subprocess.STDOUT,
                start_new_session=True,  # This creates a new process group
                env=env
            )
        
        logger.info(f"Project started with PID {process.pid}, logs at {log_file}")
    except Exception as e:
        logger.error(f"Error starting project: {e}")

def stop_project() -> None:
    """Stop all running processes matching the GREPCOMMAND pattern."""
    logger = logging.getLogger(__name__)
    grep_command = os.getenv("GREPCOMMAND")
    
    try:
        # Find process IDs matching the grep pattern
        result = subprocess.run(
            ["pgrep", "-f", grep_command],
            capture_output=True,
            text=True
        )
        
        if result.returncode == 0:
            # Get process IDs
            pids = result.stdout.strip().split('\n')
            logger.info(f"Found {len(pids)} processes matching '{grep_command}'")
            
            # Kill each process
            for pid in pids:
                kill_result = subprocess.run(
                    ["kill", "-15", pid],  # SIGTERM
                    capture_output=True,
                    text=True
                )
                
                if kill_result.returncode == 0:
                    logger.info(f"Successfully terminated process {pid}")
                else:
                    logger.warning(f"Failed to terminate process {pid}: {kill_result.stderr}")
        else:
            logger.info(f"No running processes found matching '{grep_command}'")
    except Exception as e:
        logger.error(f"Error stopping project: {e}")

def deploy_project() -> None:
    """Deploy the project by stopping any existing instance and starting a new one."""
    logger = logging.getLogger(__name__)
    logger.info("Starting deployment process")
    
    # First stop any existing instances
    stop_project()
    
    # Then start a new instance
    start_project()

def check_and_restart_if_needed() -> None:
    """Check if the project should be running but has stopped, and restart if needed."""
    logger = logging.getLogger(__name__)
    
    # Only perform this check if deploy mode is enabled
    if not os.getenv("GREPCOMMAND") or not os.getenv("RUNCOMMAND"):
        return
    
    # Check if the project is running
    if not check_project():
        logger.warning("Project should be running but has stopped, restarting...")
        start_project()
    else:
        logger.info("Project health check: running")

def update_repository():
    """
    Update the repository by fetching latest changes and resetting to match remote.
    This overwrites local changes but preserves untracked files.
    """
    try:
        # Get current branch
        current_branch = subprocess.check_output(
            ["git", "rev-parse", "--abbrev-ref", "HEAD"],
            universal_newlines=True
        ).strip()
        
        # Fetch the latest changes
        subprocess.run(["git", "fetch"], check=True)
        
        # Reset to match the remote branch but keep untracked files
        reset_cmd = ["git", "reset", "--hard", f"origin/{current_branch}"]
        subprocess.run(reset_cmd, check=True)
        
        print(f"Repository updated successfully, local changes overwritten, untracked files preserved.")
        return True
    except subprocess.SubprocessError as e:
        print(f"Error updating repository: {e}")
        return False

def main() -> None:
    """Main entry point for the webhook watcher."""
    setup_logging()
    logger = logging.getLogger(__name__)
    
    # Parse command line arguments
    args = parse_args()
    
    # Handle install/uninstall options first
    if args.install:
        # Update repository before installation
        update_repository()
        install_launch_agent()
        return
    
    if args.uninstall:
        uninstall_launch_agent()
        return
    
    # Regular execution continues...

    # Get configuration from environment
    endpoint_url = os.getenv("SVIX_ENDPOINT_URL")
    api_key = os.getenv("SVIX_API_KEY")
    
    if not endpoint_url or not api_key:
        logger.error("SVIX_ENDPOINT_URL and SVIX_API_KEY must be set in environment")
        return

    # Check for RUNCOMMAND and GREPCOMMAND if --deploy is specified
    if args.deploy:
        if not os.getenv("RUNCOMMAND"):
            logger.error("RUNCOMMAND environment variable must be set when using --deploy")
            return
        if not os.getenv("GREPCOMMAND"):
            logger.error("GREPCOMMAND environment variable must be set when using --deploy")
            return

    # Validate environment variables if --update is used
    if args.update:
        if not os.getenv("GITHUB_REPO"):
            logger.error("GITHUB_REPO environment variable must be set when using --update")
            return
        # Do initial update
        try:
            logger.info("Performing initial update...")
            update_local()
            if args.deploy:
                deploy_project()
        except Exception as e:
            logger.error(f"Initial update failed: {e}")
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

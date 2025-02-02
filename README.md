# intra-deploy
Deploy and auto-update local software from a GitHub repo. Works from inside a firewall by using svix.

## Setup

1. Copy `.env.example` to `.env` and fill in your svix webhook URL and secret
2. Install dependencies:
   ```bash
   uv venv
   . .venv/bin/activate
   uv pip install -e .
   ```

## Usage

Simply run:
```bash
uv run -m intra_deploy
```

The tool will:
1. Watch for GitHub webhook events at the configured svix webhook URL
2. Verify webhook signatures using the configured secret
3. When a push to master/main branch is detected, trigger the deploy function
4. Log all activity to `~/Library/Logs/intra-deploy/intra-deploy.log`

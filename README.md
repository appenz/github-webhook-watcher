# GitHub WebHook Client

Local python script that watches the GitHub WebHooks sent by a GitHub repo. It uses [Svix](www.swix.com) as the endpoint for the WebHooks and then subscribes to them via a Svix Polling Endpoint. This ensures no webhook is missed. It also means that this tool works from behind a firewall.

By default, it will receive messages and print them. You can also use it to trigger actions. The built-in actions include updating a local copy of the repo and deploying the application. All activity is logged to `~/Library/Logs/webhook_client.log`. Additionally, the client can monitor the application and restart it if it stops unexpectedly when run with the `--deploy` option.

It can also install itself as a macOS launch agent, which will run it in the background and monitor the application, i.e. acting as a watchdog.

The script requires a Svix account, and should work with the free tier of Svix for small repos.

## Setup

First, you need to set up Svix:
- Create a Svix account.
- Create an Ingest URL on Svix.
- Create a Svix Polling Endpoint for the ingest URL.
- Configure GitHub to send webhooks to the Svix Ingest URL.

Next, make sure you have uv installed.

Required environment variables:
- SVIX_ENDPOINT - The Svix polling endpoint  
- SVIX_ENDPOINT_API_KEY - The API key for the Svix endpoint

Optional environment variables:
- GITHUB_REPO - The GitHub repot to deploy locally. Required if `--update` or `--watchdog` is used.
- LOCAL_DIRECTORY - The local path to where the repo is located. Default is `~/deployments/
- SVIX_POLLING_INTERVAL - The interval for the Svix polling endpoint. Default is 30 seconds.
- RUNCOMMAND - The command to run the local repo. Required if `--watchdog` is used.
- GREPCOMMAND - The command to check if the application is running. Required if `--watchdog` is used.

## Usage

Make sure you have uv installed. Then run:
```
uv run webhookclient/main.py [options]
```

## Command Line Arguments
- `--update` - Watch for pushes to the main branch and update the local repo
- `--deploy` - If the repo is updated, update the local repo and restart the application
- `--install` - Install webhookclient as a macOS launch agent, i.e. it will --update and --deploy automatically
- `--uninstall` - Uninstall webhookclient launch agent
- `--help` - Show a short help message and exit


## Auto-restart Functionality

When run with the `--deploy` option, the webhook client will:

1. Automatically update the repository when changes are pushed to main/master
2. Deploy/restart the application after updates
3. Continuously monitor the application and restart it if it stops unexpectedly

## Running as a Background Service

On macOS, you can install the webhook client as a launch agent:

1. Make sure your `.env` file is properly configured
2. Run `python webhookclient/main.py --install`

This will:
- Create a launch agent plist file in `~/Library/LaunchAgents/`
- Configure it to run with your current environment settings
- Load the service immediately

To stop and remove the service, run:
```bash
python webhookclient/main.py --uninstall
```



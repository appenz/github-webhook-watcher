# GitHub WebHook Client

Local python script that watches the GitHubs sent by a GitHub repo. It uses [Svix](www.swix.com) as the endpoint for the WebHooks and then subscribes to them via a Svix Polling Endpoint. This ensures no webhook is missed. It also means that this tool works from behind a firewall.

By default, it will receive messages and print them. You can also use it to trigger actions. The only built-in action is updating a local copy of the repo. All activity is logged to `~/Library/Logs/webhook_client.log`

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
- GITHUB_REPO - The GitHub repo to watch

Optional environment variables:
- LOCAL_REPO - The local path where the repo will be cloned
- LOCAL_EXECUTABLE - The local executable to run after updating the repo, it will be run in the local repo directory
- SVIX_POLLING_INTERVAL - The interval for the Svix polling endpoint. Default is 30 seconds.

## Command Line Arguments

- `-update` - Watch for pushes to the main branch and update the local repo
- `-runlocal` - Run the local executable after updating the repo
- `-help` - Show a short help message and exit

## Usage

Make sure you have uv installed. Then run:
```
uv run -m webhookclient

```


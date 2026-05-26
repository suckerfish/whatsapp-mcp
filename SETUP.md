# Deployment Setup Guide

This guide covers deploying the Dockerized whatsapp-mcp stack on Unraid via the Compose plugin and connecting it to MetaMCP.

## Prerequisites

- Unraid with the **Compose Manager** plugin installed
- Docker images pulled from GHCR (public, no auth needed):
  - `ghcr.io/suckerfish/whatsapp-mcp-bridge:latest`
  - `ghcr.io/suckerfish/whatsapp-mcp-server:latest`

## 1. First-time setup on Unraid

### Create appdata directory

```bash
mkdir -p /mnt/user/appdata/whatsapp-mcp
```

### Deploy via Compose plugin

Copy `docker/docker-compose.yml` into the Compose plugin (or paste the contents). Leave `WHATSAPP_BRIDGE_TOKEN` blank for now. Start the stack.

### Pair your WhatsApp account (QR scan)

The bridge needs to pair with WhatsApp once via a QR code displayed in the terminal.

**Option A — Unraid console button:**
In the Unraid Docker tab, click the console icon next to the `whatsapp-bridge` container. The QR code should already be printing to stdout on first start — check `docker logs whatsapp-bridge` first. If the bridge is already running but unconnected, the QR appears in logs automatically.

**Option B — exec into the container:**
```bash
docker exec -it whatsapp-bridge sh
```
The binary runs as the container entrypoint, so the QR is in the container logs, not an interactive shell. Just read the logs:
```bash
docker logs -f whatsapp-bridge
```

Scan the QR code with your phone: **WhatsApp → Settings → Linked Devices → Link a Device**.

### Optional: request full message history

To pull your full message history at pair time (requires a fresh pair):
1. Stop the stack
2. Delete `whatsapp.db` from `/mnt/user/appdata/whatsapp-mcp/`
3. Modify the bridge service entrypoint in `docker-compose.yml` to add the flag:
   ```yaml
   command: ["--full-history-pair"]
   ```
4. Start the stack and scan the QR again
5. Remove the `command` override after pairing completes

## 2. Copy the bridge token

After the first successful start, the bridge writes a 256-bit auth token to:
```
/mnt/user/appdata/whatsapp-mcp/.bridge-token
```

Read it:
```bash
cat /mnt/user/appdata/whatsapp-mcp/.bridge-token
```

Edit the Compose stack in Unraid and paste the token into the `WHATSAPP_BRIDGE_TOKEN` env var for the `whatsapp-mcp-server` service:
```yaml
WHATSAPP_BRIDGE_TOKEN: "paste-token-here"
```

Restart the `whatsapp-mcp-server` container. From this point forward the MCP server authenticates to the bridge automatically.

## 3. Register with MetaMCP

MetaMCP runs on your `ampere` VPS and is connected to Unraid via Tailscale.

1. Find Unraid's Tailscale IP:
   ```bash
   tailscale status | grep vault  # or whatever your Unraid hostname is
   ```

2. In the MetaMCP admin UI, add a new MCP server:
   - **Transport**: HTTP / Streamable-HTTP
   - **URL**: `http://<UNRAID_TAILSCALE_IP>:8765`
   - **Name**: `whatsapp`

3. Save and verify the connection — MetaMCP should list the whatsapp tools (list_chats, list_messages, send_message, etc.).

## 4. Verify everything works

```bash
# Bridge is connected to WhatsApp
docker logs whatsapp-bridge | grep -i "connected\|authenticated"

# MCP server is reachable
curl http://<UNRAID_TAILSCALE_IP>:8765/health

# Messages are being stored
ls -la /mnt/user/appdata/whatsapp-mcp/messages.db
```

## Updating

Images are rebuilt automatically by GitHub Actions on every push to `main`. To pull the latest images on Unraid:

```bash
docker compose -f /path/to/docker-compose.yml pull
docker compose -f /path/to/docker-compose.yml up -d
```

Or use the Compose plugin's "Pull and recreate" button.

## Upstream sync

A GitHub Actions workflow runs daily at 06:00 UTC to merge changes from `verygoodplugins/whatsapp-mcp` into this fork. If a merge conflict occurs, a GitHub issue is automatically opened so you can resolve it manually.

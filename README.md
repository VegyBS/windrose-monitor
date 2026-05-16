# Windrose Server Monitor

A comprehensive monitoring system for Windrose servers hosted on Pterodactyl. Automatically manages player tracking, CPU performance profiles, and sends Discord notifications.

## Quick Overview

This project provides:

1. **Player Monitoring** - Tracks when players join/leave by parsing server logs via Pterodactyl API
2. **CPU Profile Management** - Automatically switches CPU to performance mode when players are online, and balanced mode when the server is empty
3. **Discord Integration** - Sends real-time notifications to your Discord server when players join/leave
4. **State Management** - Maintains player state in JSON for reliability and debugging

## Quick Start

### Clone the Repository

```bash
git clone https://github.com/yourusername/windrose-monitor.git
cd windrose-monitor
```

### On Your Ubuntu Server

1. **Run the installation script**:
   ```bash
   sudo bash install.sh
   ```

2. **Configure with your credentials**:
   ```bash
   sudo nano /etc/windrose-monitor/config.json
   ```
   - Add your Pterodactyl API token and server ID
   - Add your Discord webhook URL

3. **Start the service**:
   ```bash
   sudo systemctl start windrose-monitor
   ```

4. **Check logs**:
   ```bash
   sudo journalctl -u windrose-monitor -f
   ```

## Security & Configuration

**Important**: This repository is safely configured for sharing on GitHub:

- ✅ `config.example.json` - Shared on GitHub (placeholder values only)
- ⚠️ `config.json` - Your actual config (in `.gitignore`, never committed)
- ✅ `.gitignore` - Prevents accidental credential commits

When you clone this repository:
```bash
# The installer will copy the example config
sudo bash install.sh

# Then you edit it with your real credentials
sudo nano /etc/windrose-monitor/config.json
```

Your real API tokens and webhook URLs stay private and never go to GitHub.

## Configuration

The `config.json` file contains all settings:

```json
{
  "pterodactyl": {
    "api_url": "https://your-panel.com",
    "api_token": "YOUR_TOKEN",
    "server_id": "server-uuid"
  },
  "discord": {
    "webhook_url": "https://discord.com/api/webhooks/..."
  },
  "monitoring": {
    "check_interval_seconds": 20
  },
  "cpu_profile": {
    "enabled": true,
    "performance_profile": "performance",
    "balanced_profile": "balance_power"
  }
}
```

## How It Works

```
1. Every 20 seconds (configurable):
   ├─ Fetch latest logs from Pterodactyl API
   ├─ Parse Reserved Accounts section for current players
   ├─ Compare with previous state
   ├─ Send Discord notifications for changes
   ├─ Adjust CPU profile based on player count
   └─ Save updated state
```

## Requirements

- Python 3.7+
- Ubuntu/Linux server
- Pterodactyl panel access
- Discord webhook
- Root/sudo access (for CPU frequency scaling)

## Monitoring Features

- ✅ Real-time player join/leave detection
- ✅ Player count tracking
- ✅ Automatic CPU performance tuning
- ✅ Discord webhook notifications
- ✅ JSON state persistence
- ✅ Automatic error recovery
- ✅ Comprehensive logging
- ✅ Unit tests with mocked APIs
- ✅ Automated testing via GitHub Actions

## Typical Discord Output

```
🎮 Player Joined: PlayerName
📊 Player Count: 1 (was 0)
👋 Player Left: PlayerName
📊 Player Count: 0 (was 1)
```

## Support & Troubleshooting

See [SETUP.md](SETUP.md) for detailed troubleshooting steps including:
- API connection issues
- Discord webhook problems
- CPU frequency scaling issues
- Permission errors

## License

MIT License - Feel free to modify and use for your server monitoring needs.

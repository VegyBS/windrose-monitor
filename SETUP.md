# Windrose Server Monitor - Setup Guide

A Python-based monitoring system for your Windrose server that:
- Tracks player joins/leaves
- Dynamically adjusts CPU profiles (performance when players online, balanced when empty)
- Sends Discord notifications for player events
- Maintains player state using JSON storage

## Prerequisites

- Ubuntu server with Python 3.7+
- Pterodactyl panel API access (admin token)
- Discord webhook URL for notifications
- Root/sudo access for CPU frequency scaling

## Installation Steps

### 1. Create Service User

```bash
sudo useradd -r -s /bin/false windrose-monitor
sudo mkdir -p /var/lib/windrose-monitor
sudo mkdir -p /etc/windrose-monitor
sudo chown windrose-monitor:windrose-monitor /var/lib/windrose-monitor
```

### 2. Install the Monitor

```bash
# Clone or download the repository
cd /opt
sudo git clone <repository-url> windrose-monitor
cd windrose-monitor

# Install Python dependencies
sudo pip3 install -r requirements.txt

# Create symlink to executable
sudo ln -s /opt/windrose-monitor/windrose_monitor.py /usr/local/bin/windrose-monitor
sudo chmod +x /usr/local/bin/windrose-monitor
```

### 3. Configure the Monitor

Copy the example configuration and customize it:

```bash
sudo cp config.example.json /etc/windrose-monitor/config.json
sudo nano /etc/windrose-monitor/config.json
```

Update these required fields in your `config.json`:

```json
{
  "pterodactyl": {
    "api_url": "https://your-pterodactyl-panel.com",
    "api_token": "YOUR_PTERODACTYL_API_TOKEN",
    "server_id": "your-server-uuid"
  },
  "discord": {
    "webhook_url": "https://discord.com/api/webhooks/YOUR_WEBHOOK_ID/YOUR_WEBHOOK_TOKEN"
  },
  "monitoring": {
    "check_interval_seconds": 20
  },
  "cpu_profile": {
    "enabled": true
  }
}
```

**Note**: The `config.json` file is excluded from version control (see `.gitignore`). Only `config.example.json` is committed to the repository.

**Getting your Pterodactyl API Token:**
1. Go to your Pterodactyl panel
2. Click your avatar → Account Settings
3. Go to "API Credentials"
4. Create new API token with appropriate permissions

**Getting your Discord Webhook:**
1. Go to your Discord server settings
2. Select a channel → Webhooks
3. Create new webhook
4. Copy the webhook URL

### 4. Configure CPU Frequency Scaling (sudo permissions)

The monitor needs sudo access to change CPU profiles without a password. Add this to sudoers:

```bash
sudo visudo
```

Add this line at the end:

```
windrose-monitor ALL=(ALL) NOPASSWD:/usr/bin/tee /sys/devices/system/cpu/cpu*/cpufreq/energy_performance_preference
```

### 5. Install Systemd Service

```bash
sudo cp windrose-monitor.service /etc/systemd/system/
sudo systemctl daemon-reload
sudo systemctl enable windrose-monitor
sudo systemctl start windrose-monitor
```

### 6. Verify Installation

Check if the service is running:

```bash
sudo systemctl status windrose-monitor
```

View logs:

```bash
# Systemd journal
sudo journalctl -u windrose-monitor -f

# Or from log file
sudo tail -f /var/log/windrose-monitor.log
```

## Configuration Reference

### CPU Profiles

- `performance` - Maximum CPU frequency (best for active servers)
- `balance_power` - Balanced power/performance (default for idle servers)

If your CPU doesn't support energy_performance_preference, you can use:
- `cpufreq-set` command (requires cpufrequtils)
- `powertop --auto-tune` (requires powertop)

### Monitoring Patterns

The monitor looks for these log patterns:
- **Reserved Accounts**: Players currently online
- **Disconnected Accounts**: Players who have left

### State File

State is stored in `/var/lib/windrose-monitor/state.json` and includes:
- Current player list
- Player count
- Last update timestamp
- Current CPU profile

## Troubleshooting

### Monitor not starting
```bash
sudo systemctl status windrose-monitor
sudo journalctl -u windrose-monitor -n 50
```

### API connection failed
- Verify Pterodactyl API token is valid and has correct permissions
- Check firewall allows connection to Pterodactyl panel
- Verify server ID is correct

### Discord messages not sending
- Check webhook URL is correct and not expired
- Verify Discord webhook still exists in channel settings
- Check network connectivity to Discord API

### CPU profile not changing
```bash
# Test CPU frequency path
cat /sys/devices/system/cpu/cpu0/cpufreq/energy_performance_preference

# Manually test change
echo "performance" | sudo tee /sys/devices/system/cpu/cpu0/cpufreq/energy_performance_preference
```

### Permission denied errors
- Verify windrose-monitor user has write permissions to `/var/lib/windrose-monitor`
- Check sudoers configuration for tee command
- Ensure service runs as windrose-monitor user

## Uninstalling

```bash
sudo systemctl stop windrose-monitor
sudo systemctl disable windrose-monitor
sudo rm /etc/systemd/system/windrose-monitor.service
sudo systemctl daemon-reload
sudo userdel windrose-monitor
sudo rm -rf /opt/windrose-monitor /etc/windrose-monitor /var/lib/windrose-monitor
```

## Logs and Monitoring

Monitor the service in real-time:

```bash
sudo journalctl -u windrose-monitor -f
```

## Features

✅ Real-time player join/leave detection
✅ Automatic CPU profile management
✅ Discord webhook notifications
✅ JSON-based state persistence
✅ Systemd integration
✅ Comprehensive logging
✅ Error recovery with automatic restart

## Future Enhancements

- [ ] Support for multiple servers
- [ ] Web dashboard for monitoring
- [ ] Database support for historical tracking
- [ ] Custom notification templates
- [ ] Telegram/Slack integration
- [ ] Player statistics/analytics

# Windrose Monitor - Quick Reference

## Common Tasks

### Viewing Logs

```bash
# Real-time logs
sudo journalctl -u windrose-monitor -f

# Last 50 lines
sudo journalctl -u windrose-monitor -n 50

# Logs from the last hour
sudo journalctl -u windrose-monitor --since "1 hour ago"

# Specific error level
sudo journalctl -u windrose-monitor -p err
```

### Service Management

```bash
# Start the service
sudo systemctl start windrose-monitor

# Stop the service
sudo systemctl stop windrose-monitor

# Restart the service
sudo systemctl restart windrose-monitor

# Check status
sudo systemctl status windrose-monitor

# Enable on boot (automatic)
sudo systemctl enable windrose-monitor

# Disable on boot
sudo systemctl disable windrose-monitor
```

### Configuration

```bash
# Edit configuration
sudo nano /etc/windrose-monitor/config.json

# Validate JSON
python3 -m json.tool /etc/windrose-monitor/config.json

# Apply changes (restart service)
sudo systemctl restart windrose-monitor
```

### Testing & Debugging

```bash
# Test configuration
python3 test_config.py

# Run monitor in foreground (for testing)
sudo python3 windrose_monitor.py

# Manually test Discord webhook
curl -X POST -H 'Content-Type: application/json' \
  -d '{"content":"Test"}' \
  YOUR_WEBHOOK_URL

# Check Pterodactyl API
curl -H "Authorization: Bearer YOUR_TOKEN" \
  https://your-panel.com/api/client/servers/SERVER_ID/logs
```

### State & Monitoring

```bash
# View current state
sudo cat /var/lib/windrose-monitor/state.json

# View CPU profiles
cat /sys/devices/system/cpu/cpu0/cpufreq/energy_performance_preference

# Manually set CPU to performance
echo "performance" | sudo tee /sys/devices/system/cpu/cpu*/cpufreq/energy_performance_preference

# Check sudoers configuration
sudo cat /etc/sudoers.d/windrose-monitor
```

### Troubleshooting

```bash
# Check file permissions
ls -la /var/lib/windrose-monitor/
ls -la /etc/windrose-monitor/

# Check service user
id windrose-monitor

# Check Python installation
python3 --version
pip3 list | grep requests

# Check API connectivity
ping your-pterodactyl-panel.com

# Check Discord webhook URL
echo $WEBHOOK_URL  # if you saved it as env var
```

### Updating

```bash
# Stop service
sudo systemctl stop windrose-monitor

# Update files
git pull  # or manually copy updated files

# Update dependencies
sudo pip3 install -r requirements.txt --upgrade

# Restart
sudo systemctl start windrose-monitor

# Verify
sudo systemctl status windrose-monitor
```

## Configuration Keys

### Pterodactyl Settings
- `api_url`: Your Pterodactyl panel URL (https://panel.example.com)
- `api_token`: API token from panel settings
- `server_id`: Server UUID from panel

### Discord Settings
- `webhook_url`: Discord channel webhook URL

### Monitoring Settings
- `check_interval_seconds`: How often to check for changes (default: 20)
- `reserved_accounts_header`: Log line marker for player list (usually "Reserved Accounts")

### CPU Profile Settings
- `enabled`: true/false to enable CPU profile switching
- `performance_profile`: Profile name when players online (usually "performance")
- `balanced_profile`: Profile name when idle (usually "balance_power")
- `cpu_freq_path`: Path to CPU frequency scaling (leave default unless custom)

## Directory Structure

```
/opt/windrose-monitor/          # Installation directory
├── windrose_monitor.py          # Main script
├── config.json                  # Configuration template
├── requirements.txt             # Python dependencies
├── windrose-monitor.service     # Systemd service
├── install.sh                   # Installation script
├── test_config.py               # Configuration tester
├── README.md                    # Main documentation
├── SETUP.md                     # Detailed setup guide
└── QUICKREF.md                  # This file

/etc/windrose-monitor/           # Configuration (runtime)
└── config.json                  # Your actual configuration

/var/lib/windrose-monitor/       # State (runtime)
└── state.json                   # Current player state

/var/log/                        # Logs (if not using journald)
└── windrose-monitor.log

/etc/systemd/system/             # Service files
└── windrose-monitor.service
```

## Performance Tuning

### Lower CPU Usage
- Increase `check_interval_seconds` to 30 or 60

### Faster Detection
- Decrease `check_interval_seconds` to 10

### Reduce Disk I/O
- Save config.json and state.json to RAM disk:
  ```bash
  sudo mount -t tmpfs -o size=10M tmpfs /var/lib/windrose-monitor
  ```

## Integration with Other Tools

### Prometheus Monitoring
Add this to export player count:
```python
# In a separate script with prometheus_client
from prometheus_client import Gauge
players = Gauge('windrose_players', 'Current player count')
# Update gauge on each check
```

### Grafana Dashboard
Create dashboard showing:
- Player count over time
- Join/leave events timeline
- CPU profile changes
- Error rate

### Alerting
Combine with AlertManager to alert on:
- Service down (no updates in 5 minutes)
- High error rate
- Server crashes (player count spike)

## Security Notes

- Keep API token and webhook URL private
- Don't commit config.json to version control
- Use strong file permissions (config.json is 600)
- Monitor sudoers changes
- Consider using secrets management (Vault, SecretsManager)

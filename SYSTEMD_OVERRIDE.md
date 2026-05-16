# Windrose Monitor - Systemd Override Examples

## Custom Service Configuration

If you need to customize the systemd service, create an override file:

```bash
sudo systemctl edit windrose-monitor
```

This opens an editor where you can add customizations.

## Common Customizations

### Run as a Different User

```ini
[Service]
User=your-username
Group=your-group
```

### Set Custom Environment Variables

```ini
[Service]
Environment="LOG_LEVEL=DEBUG"
Environment="CONFIG_PATH=/custom/path/config.json"
```

### Custom Log Output

```ini
[Service]
StandardOutput=file:/var/log/windrose-monitor.log
StandardError=file:/var/log/windrose-monitor.err
```

### Resource Limits

```ini
[Service]
# Limit CPU usage to 1 core
CPUQuota=100%
CPUAccounting=yes

# Limit memory to 256MB
MemoryLimit=256M
MemoryAccounting=yes

# Limit I/O bandwidth
IOAccounting=yes
IOReadBandwidthMax=/dev/sda1 10M
IOWriteBandwidthMax=/dev/sda1 5M
```

### Network Isolation

```ini
[Service]
RestrictAddressFamilies=AF_UNIX AF_INET AF_INET6
PrivateNetwork=false
NoNewPrivileges=true
```

### Auto-restart Behavior

```ini
[Service]
# Restart immediately on failure
Restart=always
RestartSec=5

# Don't restart if stopped manually
RestartForceExitStatus=0

# Restart only on specific exit codes
RestartForceExitStatus=1 2
```

### Dependency Management

```ini
[Unit]
# Start after network is available
After=network-online.target
Wants=network-online.target

# Start before shutdown
Before=shutdown.target

# Require another service to be running
BindsTo=docker.service
```

### Advanced Logging

```ini
[Service]
SyslogIdentifier=windrose-monitor
SyslogFacility=daemon
SyslogLevel=info
```

## Checking Your Configuration

After editing, verify the complete unit file:

```bash
systemctl cat windrose-monitor
```

Check for any errors:

```bash
systemctl status windrose-monitor
journalctl -u windrose-monitor -n 20
```

## Important Notes

- Override files are stored in `/etc/systemd/system/windrose-monitor.service.d/override.conf`
- Always reload after changes: `sudo systemctl daemon-reload`
- Test changes with: `sudo systemctl restart windrose-monitor`
- Use `systemctl status` to verify the service is running
- Use `journalctl` to see logs with your custom configuration

## Example: Production Configuration

For a production deployment, you might create this override:

```ini
[Unit]
After=network-online.target docker.service
Wants=network-online.target
BindsTo=docker.service

[Service]
# Resource limits
CPUQuota=100%
MemoryLimit=512M

# Restart behavior
Restart=always
RestartSec=10
StartLimitInterval=300s
StartLimitBurst=5

# Security
NoNewPrivileges=true
PrivateTmp=true
ProtectSystem=strict
ProtectHome=yes
ReadWritePaths=/var/lib/windrose-monitor /var/log

# Logging
StandardOutput=journal
StandardError=journal
SyslogIdentifier=windrose-monitor
```

Apply it with:
```bash
sudo systemctl edit windrose-monitor
# Paste the above content
# Save and exit

sudo systemctl daemon-reload
sudo systemctl restart windrose-monitor
```

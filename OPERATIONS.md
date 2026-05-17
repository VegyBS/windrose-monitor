# Windrose Monitor Operations Guide 🧭⚙️

This guide explains how to **run**, **maintain**, **observe**, and **troubleshoot** the Windrose Server Monitor in a real operational environment.  
It is written for day‑to‑day operators, SREs, and administrators who need to keep the service healthy and predictable.

---

## 1. Service Lifecycle 🔄

### Start the service
sudo systemctl start windrose-monitor

### Stop the service
sudo systemctl stop windrose-monitor

### Restart the service
sudo systemctl restart windrose-monitor

### Enable on boot
sudo systemctl enable windrose-monitor

### Check status
sudo systemctl status windrose-monitor

### Reload after config changes
sudo systemctl restart windrose-monitor

The monitor does not support systemctl reload because it maintains WebSocket state; restart is required.

---

## 2. Observability & Monitoring 📊

### View logs (live)
sudo journalctl -u windrose-monitor -f

### View recent logs
sudo journalctl -u windrose-monitor --since "1 hour ago"

### Log patterns to expect

Normal:
- WebSocket authenticated  
- Player join/leave events  
- CPU profile changes  
- Reconnect attempts after idle timeouts  

Warnings:
- Temporary WebSocket disconnects  
- Discord webhook rate limits  
- Slow sysfs writes  

Critical:
- Authentication failures  
- Reconnect loops with no success  
- Missing sysfs paths  
- Corrupted state.json  

### Check current state
sudo cat /var/lib/windrose-monitor/state.json

This file contains:
- active players  
- last known CPU profile  
- timestamps  
- last Discord notification  

---

## 3. Failure Modes & Recovery 🛠️

### WebSocket disconnect loop
Symptoms:
- Repeated reconnect attempts  
- No player updates  

Actions:
- Check Pterodactyl panel availability  
- Restart Wings  
- Restart the monitor  

### Token authentication failure
Symptoms:
- auth failed messages  
- no console output events  

Actions:
- Regenerate Pterodactyl Client API Token  
- Update .env  
- Restart the monitor  

### Discord webhook failure
Symptoms:
- No join/leave notifications  
- Errors in logs  

Actions:
- Regenerate webhook  
- Update .env  
- Check network connectivity  

### CPU profile stuck
Symptoms:
- Always in performance mode  
- Never switches back to balanced  

Actions:
- Check sysfs permissions  
- Ensure systemd unit includes ReadWritePaths  
- Restart the monitor  

### Corrupted state.json
Symptoms:
- JSON decode errors  
- Missing player events  

Actions:
- Delete state.json  
- Restart the monitor  
- Monitor will recreate it  

---

## 4. Operational Runbooks 📘

### Players not detected
1. Check WebSocket logs  
2. Verify server ID in .env  
3. Confirm Wings is running  
4. Restart the monitor  

### CPU scaling not working
1. Check sysfs path exists  
2. Verify systemd ReadWritePaths  
3. Ensure CPU_PROFILE_ENABLED=true  
4. Restart the monitor  

### Discord notifications stopped
1. Test webhook manually  
2. Check logs for rate limits  
3. Replace webhook if needed  
4. Restart the monitor  

### Monitor won’t start
1. Check syntax in .env  
2. Check config.json formatting  
3. Run systemctl status  
4. Inspect logs for Python errors  

---

## 5. Maintenance Tasks 🧹

### Rotate logs
Logs are handled by journald.  
To clear old logs:

sudo journalctl --vacuum-time=7d

### Update dependencies
From the repo directory:

git pull  
sudo bash install.sh  
sudo systemctl restart windrose-monitor

### Clean old state
If needed:

sudo rm /var/lib/windrose-monitor/state.json  
sudo systemctl restart windrose-monitor

### Verify systemd sandboxing
Check:

- ProtectSystem  
- ProtectHome  
- RestrictSUIDSGID  
- MemoryDenyWriteExecute  
- ReadWritePaths  

---

## 6. Performance Tuning ⚡

### Adjust check interval
CHECK_INTERVAL_SECONDS in .env controls how often:

- logs are parsed  
- player changes are detected  
- CPU scaling is evaluated  

Lower values = faster response, higher CPU usage  
Higher values = slower response, lower CPU usage  

Recommended: 20 seconds

### Tune reconnect behaviour
If your panel is unstable, increase reconnect backoff in the code.

### Reduce Discord noise
Disable player count messages if needed.

---

## 7. Security Operations 🔐

### Rotate API tokens
1. Generate new token in Pterodactyl  
2. Update .env  
3. Restart the monitor  

### Rotate Discord webhook
1. Create new webhook  
2. Update .env  
3. Restart the monitor  

### Validate systemd hardening
Ensure the service still includes:

- ProtectSystem=strict  
- ProtectHome=true  
- RestrictSUIDSGID=true  
- MemoryDenyWriteExecute=true  
- ReadWritePaths=/sys/devices/system/cpu  

### Check for privilege drift
Ensure the windrose-monitor user has no unexpected permissions.

---

## 8. Backup & Restore 💾

### Backup
Save:

- /etc/windrose-monitor/.env  
- /etc/windrose-monitor/config.json  
- /var/lib/windrose-monitor/state.json  

### Restore
Copy files back into place and restart:

sudo systemctl restart windrose-monitor

---

## 9. Upgrade Process ⬆️

### Safe upgrade steps
1. Stop the service  
2. Pull latest code  
3. Re-run install.sh  
4. Restart the service  
5. Check logs  
6. Verify CPU scaling  
7. Verify Discord notifications  

### Rollback
If needed:

- Restore previous commit  
- Restore backup config  
- Restart the service  

---

## 10. Operational Architecture Diagram 🗺️

Windrose Server  
↓  
Wings WebSocket  
↓  
Windrose Monitor  
↓  
State File  
↓  
CPU sysfs  
↓  
Discord Webhook

This is the full data flow the monitor depends on.

---

## 11. Summary 🎉

This guide provides everything needed to operate the Windrose Monitor reliably:

- Service lifecycle  
- Observability  
- Failure recovery  
- Runbooks  
- Maintenance  
- Security  
- Upgrades  

Use this document when running the monitor in production or diagnosing issues.


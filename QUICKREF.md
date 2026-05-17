# Windrose Monitor Quick Reference Guide ⚡📘

A fast, at‑a‑glance reference for installing, running, and maintaining the Windrose Server Monitor.
Use this when you need answers quickly without reading full documentation.

---

## 1. Essential Commands 🧩

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

### View logs (live)
sudo journalctl -u windrose-monitor -f

### View state file
sudo cat /var/lib/windrose-monitor/state.json

---

## 2. Installation Summary 🛠️

### Clone and install
git clone https://github.com/yourusername/windrose-monitor.git
cd windrose-monitor
sudo bash install.sh

Installer creates:

- windrose-monitor user
- /var/lib/windrose-monitor
- /etc/windrose-monitor
- /var/log/windrose-monitor
- Python virtual environment
- systemd service

---

## 3. Configuration Files 🔧

### Main configuration (.env)
Location:
/etc/windrose-monitor/.env

Required values:

PTERODACTYL_API_URL=...
PTERODACTYL_API_TOKEN=...
PTERODACTYL_SERVER_ID=...
DISCORD_WEBHOOK_URL=...
CHECK_INTERVAL_SECONDS=20
CPU_PROFILE_ENABLED=true

### Optional fallback (config.json)
Location:
/etc/windrose-monitor/config.json

Precedence order:

1. .env
2. config.json
3. defaults

---

## 4. What the Monitor Does 🎮

### Player tracking
- Reads Connected, Reserved, Disconnected sections
- Detects joins and leaves
- Updates state.json

### CPU scaling
- Players online → performance mode
- No players → balanced mode

### Discord notifications
- Join
- Leave
- Player count changes

### WebSocket behaviour
- Authenticates
- Streams console output
- Reconnects automatically
- Handles token expiry

---

## 5. Troubleshooting 🧹

### No Discord messages
Check DISCORD_WEBHOOK_URL.

### CPU profile not changing
Ensure systemd unit includes:
ReadWritePaths=/sys/devices/system/cpu

### WebSocket not connecting
Verify:
- API URL
- API token
- Server ID

### ^M characters in files
Use LF line endings in your editor.

---

## 6. Updating the Monitor 🔁

From the repo directory:

git pull
sudo systemctl restart windrose-monitor

If dependencies changed:

sudo bash install.sh

---

## 7. Useful Paths 📁

Monitor install directory:
/var/lib/windrose-monitor

Configuration:
/etc/windrose-monitor

Logs:
/var/log/windrose-monitor

Systemd unit:
/etc/systemd/system/windrose-monitor.service

---

## 8. Test Suite 🧪

Run all tests:

python -m unittest discover -s . -p 'test_*.py' -v

Covers:

- Player parsing
- Join/leave detection
- WebSocket behaviour
- CPU scaling
- Config precedence
- Discord formatting

---

## 9. Quick Checklist ✔️

- .env configured
- systemd service enabled
- WebSocket authenticates
- Discord messages working
- CPU scaling toggles correctly
- state.json updates
- Logs show no repeated errors

---

## 10. Need More Detail? 📘

See:

- SETUP.md for installation
- TESTING.md for full test coverage
- README.md for complete documentation

This QuickRef is designed for fast lookup during development, debugging, or deployment.

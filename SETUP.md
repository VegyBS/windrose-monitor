# Windrose Monitor Setup Guide ⚙️🚀

This guide walks you through installing, configuring, and running the Windrose Server Monitor on a Linux host (Ubuntu recommended).
It assumes you develop on Windows but deploy to a Unix system.

---

## 1. Requirements 📦

Make sure your server has:

- Ubuntu 20.04 or later
- Python 3.10 or newer
- Systemd (default on Ubuntu)
- Pterodactyl Wings running your Windrose server
- A Pterodactyl Client API Token
- Internet access for Discord webhooks

---

## 2. Directory layout 📁

The monitor uses:

- /var/lib/windrose-monitor → runtime files, venv, state
- /etc/windrose-monitor → configuration files
- /var/log/windrose-monitor → log output
- /etc/systemd/system/windrose-monitor.service → systemd unit

You do not need to create these manually; the installer will.

---

## 3. Installation 🛠️

On your Linux server:

1. Clone the repository

   git clone https://github.com/yourusername/windrose-monitor.git
   cd windrose-monitor

2. Run the installer

   sudo bash install.sh

The installer will:

- Create the windrose-monitor user
- Create required directories
- Create a Python virtual environment
- Install Python dependencies into the venv
- Install the systemd service
- Copy .env.example to /etc/windrose-monitor/.env if missing
- Copy config.example.json to /etc/windrose-monitor/config.json if missing

---

## 4. Configuration 🔧

### 4.1 .env (primary configuration)

Edit the environment file:

sudo nano /etc/windrose-monitor/.env

Set at least:

PTERODACTYL_API_URL=https://panel.example.com
PTERODACTYL_API_TOKEN=your-client-api-token
PTERODACTYL_SERVER_ID=your-server-uuid
DISCORD_WEBHOOK_URL=https://discord.com/api/webhooks/...
CHECK_INTERVAL_SECONDS=20

### 4.2 config.json (optional fallback)

If you want JSON-based defaults, edit:

sudo nano /etc/windrose-monitor/config.json

The .env file always takes precedence over config.json.

Configuration precedence:

1. .env
2. config.json
3. Built-in defaults

---

## 5. Starting the service 🔌

Enable and start:

sudo systemctl enable windrose-monitor
sudo systemctl start windrose-monitor

Check status:

sudo systemctl status windrose-monitor

---

## 6. Logs and state 📊

Follow logs:

sudo journalctl -u windrose-monitor -f

Or use the log file:

sudo tail -f /var/log/windrose-monitor/windrose-monitor.log

View current state:

sudo cat /var/lib/windrose-monitor/state.json

---

## 7. Updating the monitor 🔁

From the repo directory:

git pull
sudo systemctl restart windrose-monitor

If dependencies changed, rerun:

sudo bash install.sh

---

## 8. Testing the installation 🧪

From the project directory:

python -m unittest discover -s . -p 'test_*.py' -v

Tests cover:

- Player parsing
- WebSocket behaviour
- Discord formatting
- Config precedence

---

## 9. Common issues 🧹

### 9.1 WebSocket auth failures

Check:

- PTERODACTYL_API_URL
- PTERODACTYL_API_TOKEN
- PTERODACTYL_SERVER_ID

---

## 10. Setup complete 🎉

At this point, the Windrose Server Monitor should be:

- Running under systemd
- Tracking players via WebSocket
- Sending Discord notifications

You can now refine behaviour, add metrics, or extend documentation as needed.

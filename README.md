# Windrose Server Monitor 🎮🛠️

A real‑time monitoring daemon for Windrose servers hosted on Pterodactyl.

It provides:

- 🎮 Live player tracking via Pterodactyl WebSocket console streaming
- 👥 Join/leave detection using Connected + Reserved + Disconnected accounts
- ⚡ Automatic CPU performance scaling (performance when players online, balanced when empty)
- 🔔 Discord notifications for joins, leaves, and player count changes
- 🔒 Hardened systemd service with direct sysfs writes (no sudo required)
- 💾 Persistent state tracking for reliable behaviour across restarts

---

## 🚀 Features

### 🔌 Real‑time WebSocket monitoring

The monitor connects directly to the Pterodactyl Wings WebSocket and receives:

- console output events
- auth success
- JWT expiry events
- live log lines

This eliminates the need for the legacy /logs HTTP endpoint.

---

### 👥 Accurate player detection

Windrose exposes three sections:

- Connected Accounts → fully online
- Reserved Accounts → loading/transitioning
- Disconnected Accounts → recently left

The monitor:

- Parses all three sections
- Treats Connected ∪ Reserved as “currently active”
- Detects “left” players as those previously active but no longer present

---

### ⚡ CPU profile automation (no sudo required)

The systemd service grants write access to:

/sys/devices/system/cpu

The monitor writes directly to:

/sys/devices/system/cpu/cpu*/cpufreq/energy_performance_preference

No sudo, no tee, no sudoers file.
Systemd’s ReadWritePaths controls exactly what the service can modify.

---

### 🔔 Discord notifications

The monitor sends Discord messages for:

- Player joined
- Player left
- Player count changed

Example output:

🎮 Player Joined: PlayerName
📊 Player Count: 1 (was 0)
👋 Player Left: PlayerName
📊 Player Count: 0 (was 1)

---

### 🔒 Hardened systemd service

The service unit includes:

- ProtectSystem=strict
- ProtectHome=true
- RestrictSUIDSGID=true
- MemoryDenyWriteExecute=true
- SystemCallFilter=@system-service
- ReadWritePaths=/sys/devices/system/cpu
- NoNewPrivileges=no (required for sysfs writes)

This keeps the monitor tightly sandboxed while still allowing CPU profile control.

---

## 📦 Installation

Clone the repository and run the installer:

sudo bash install.sh

The installer:

- Creates the windrose-monitor service user
- Creates /var/lib/windrose-monitor and /etc/windrose-monitor
- Sets up a Python virtual environment
- Installs Python dependencies
- Installs the systemd service
- Copies .env.example → /etc/windrose-monitor/.env
- Copies config.example.json → /etc/windrose-monitor/config.json

---

## ⚙ Configuration

### Primary configuration: .env

Edit:

sudo nano /etc/windrose-monitor/.env

Required:

PTERODACTYL_API_URL=https://panel.example.com
PTERODACTYL_API_TOKEN=your-client-api-token
PTERODACTYL_SERVER_ID=your-server-uuid
DISCORD_WEBHOOK_URL=https://discord.com/api/webhooks/...
CHECK_INTERVAL_SECONDS=20
CPU_PROFILE_ENABLED=true

### Fallback configuration: config.json

If .env is missing or incomplete, the monitor can fall back to config.json.

Configuration precedence:

1. .env
2. config.json
3. Built‑in defaults

---

## 🖥 Running & Logs

Start:

sudo systemctl start windrose-monitor

Enable on boot:

sudo systemctl enable windrose-monitor

Status:

sudo systemctl status windrose-monitor

Logs:

sudo journalctl -u windrose-monitor -f

State file:

/var/lib/windrose-monitor/state.json

---

## 🌐 WebSocket behaviour

The monitor:

1. Requests a temporary WebSocket token
2. Connects to the Wings WebSocket endpoint
3. Sends an auth event
4. Receives console output events
5. Buffers log lines in memory
6. Parses player sections
7. Detects stale sockets
8. Reconnects automatically

If WebSocket is unavailable, it can fall back to the legacy /logs endpoint (if enabled).

---

## 🧪 Testing

Run all tests:

python -m unittest discover -s . -p 'test_*.py' -v

Tests cover:

- Player list parsing
- Player state detection
- CPU profile logic
- Config precedence
- Discord formatting
- WebSocket behaviour (mocked)

---

## 🔐 Security

- Runs as dedicated windrose-monitor user
- No sudo usage
- No setuid binaries
- Direct sysfs writes controlled via systemd
- Secrets stored in /etc/windrose-monitor/.env
- Systemd hardening enabled

---

## 📁 Directory Layout

/var/lib/windrose-monitor/
  ├── windrose-monitor.py
  ├── venv/
  └── state.json

/etc/windrose-monitor/
  ├── .env
  └── config.json

/var/log/windrose-monitor/
  └── windrose-monitor.log

/etc/systemd/system/
  └── windrose-monitor.service

---

## 📄 License

MIT License

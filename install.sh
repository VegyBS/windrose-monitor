#!/bin/bash
# Windrose Monitor Installation Script
# Run this on your Ubuntu server: sudo bash install.sh

set -e

echo "╔════════════════════════════════════════════════════════════╗"
echo "║      Windrose Server Monitor - Installation Script         ║"
echo "╚════════════════════════════════════════════════════════════╝"
echo ""

# --- Root check --------------------------------------------------------------
if [ "$EUID" -ne 0 ]; then 
    echo "❌ This script must be run with sudo"
    exit 1
fi

# --- Detect installed Python versions ----------------------------------------
echo "Detecting installed Python versions..."
AVAILABLE_PYTHONS=()

for VER in 3.12 3.13 3.14; do
    if command -v python$VER >/dev/null 2>&1; then
        AVAILABLE_PYTHONS+=("$VER")
    fi
done

if [ ${#AVAILABLE_PYTHONS[@]} -eq 0 ]; then
    echo "❌ No supported Python versions (3.12, 3.13, 3.14) are installed."
    echo "   Install one with: sudo apt install python3.12"
    exit 1
fi

echo "Available Python versions:"
i=1
for VER in "${AVAILABLE_PYTHONS[@]}"; do
    echo "  $i) Python $VER"
    ((i++))
done

read -p "Select Python version to use [1]: " CHOICE
CHOICE=${CHOICE:-1}

PYTHON_VERSION=${AVAILABLE_PYTHONS[$((CHOICE-1))]}

if [ -z "$PYTHON_VERSION" ]; then
    echo "❌ Invalid selection"
    exit 1
fi

PYTHON_BIN="python$PYTHON_VERSION"
VENV_PKG="python$PYTHON_VERSION-venv"

echo "✓ Selected Python version: $PYTHON_BIN"
echo ""

# --- Ensure pythonX.Y-venv is installed --------------------------------------
echo "Checking for $VENV_PKG..."
if ! dpkg -s "$VENV_PKG" >/dev/null 2>&1; then
    echo "Installing $VENV_PKG..."
    apt update
    apt install -y "$VENV_PKG"
    echo "✓ $VENV_PKG installed"
else
    echo "✓ $VENV_PKG already installed"
fi
echo ""

# --- Create service user -----------------------------------------------------
echo "Creating service user..."
if id "windrose-monitor" &>/dev/null; then
    echo "  ℹ User windrose-monitor already exists"
else
    useradd -r -s /bin/false windrose-monitor
    echo "  ✓ Created windrose-monitor user"
fi

# --- Create directories -------------------------------------------------------
echo "Creating required directories..."
mkdir -p /var/lib/windrose-monitor
mkdir -p /etc/windrose-monitor
mkdir -p /var/log/windrose-monitor
mkdir -p /opt/windrose-monitor

chown windrose-monitor:windrose-monitor /var/lib/windrose-monitor
chmod 750 /var/lib/windrose-monitor

chown windrose-monitor:windrose-monitor /var/log/windrose-monitor
chmod 750 /var/log/windrose-monitor

echo "  ✓ Directories created and configured"
echo ""

# --- Create venv + install dependencies --------------------------------------
echo "Creating Python virtual environment using $PYTHON_BIN..."
$PYTHON_BIN -m venv /var/lib/windrose-monitor/venv

echo "Installing Python dependencies..."
source /var/lib/windrose-monitor/venv/bin/activate
pip install --upgrade pip
pip install -r requirements.txt
deactivate

# Fix ownership so the service user can run the venv
chown -R windrose-monitor:windrose-monitor /var/lib/windrose-monitor/venv

echo "  ✓ Virtual environment created and dependencies installed"
echo ""

# --- Copy application script ---------------------------------------------------
echo "Installing application script..."
SCRIPT_DIR="$( cd "$( dirname "${BASH_SOURCE[0]}" )" && pwd )"

# Copy script to /opt/windrose-monitor/
cp "$SCRIPT_DIR/windrose_monitor.py" /opt/windrose-monitor/windrose_monitor.py
chmod +x /opt/windrose-monitor/windrose_monitor.py
chown windrose-monitor:windrose-monitor /opt/windrose-monitor/windrose_monitor.py

echo "  ✓ Application script installed at /opt/windrose-monitor/windrose_monitor.py"
echo ""

# --- Configuration files ------------------------------------------------------
echo "Setting up configuration..."

if [ -f /etc/windrose-monitor/.env ]; then
    echo "  ℹ .env file already exists"
else
    cp "$SCRIPT_DIR/.env.example" /etc/windrose-monitor/.env
    chmod 600 /etc/windrose-monitor/.env
    chown windrose-monitor:windrose-monitor /etc/windrose-monitor/.env
    echo "  ✓ .env file created"
fi

if [ -f /etc/windrose-monitor/config.json ]; then
    echo "  ℹ config.json already exists"
else
    cp "$SCRIPT_DIR/config.example.json" /etc/windrose-monitor/config.json
    chmod 600 /etc/windrose-monitor/config.json
    chown windrose-monitor:windrose-monitor /etc/windrose-monitor/config.json
    echo "  ✓ config.json created (optional fallback)"
fi
echo ""

# --- Sudoers for CPU scaling --------------------------------------------------
echo "Configuring sudo permissions for CPU frequency scaling..."
SUDOERS_FILE="/etc/sudoers.d/windrose-monitor"

if [ -f "$SUDOERS_FILE" ]; then
    echo "  ℹ Sudoers file already exists"
else
    cat > "$SUDOERS_FILE" << 'EOF'
# Allow windrose-monitor to change CPU frequency without password
windrose-monitor ALL=(ALL) NOPASSWD:/usr/bin/tee /sys/devices/system/cpu/cpu*/cpufreq/energy_performance_preference
EOF
    chmod 440 "$SUDOERS_FILE"
    echo "  ✓ Sudoers file created"
fi
echo ""

# --- Install systemd service --------------------------------------------------
echo "Installing systemd service..."
cp "$SCRIPT_DIR/windrose-monitor.service" /etc/systemd/system/windrose-monitor.service

# Update ExecStart to use the selected Python version's venv
sed -i "s|ExecStart=.*|ExecStart=/var/lib/windrose-monitor/venv/bin/python /opt/windrose-monitor/windrose_monitor.py|" /etc/systemd/system/windrose-monitor.service

systemctl daemon-reload
systemctl enable windrose-monitor

echo "  ✓ Systemd service installed and enabled"
echo ""

# --- Verify installation -------------------------------------------------------
echo "Verifying installation..."

if [ -x /opt/windrose-monitor/windrose_monitor.py ]; then
    echo "  ✓ Script is executable"
else
    echo "  ❌ Script is not executable"
    exit 1
fi

if [ -x /var/lib/windrose-monitor/venv/bin/python ]; then
    echo "  ✓ Virtual environment Python is executable"
else
    echo "  ❌ Virtual environment Python is not executable"
    exit 1
fi

if [ -f /etc/windrose-monitor/.env ]; then
    echo "  ✓ Configuration file exists"
else
    echo "  ❌ Configuration file missing"
    exit 1
fi

echo ""

# --- Final message ------------------------------------------------------------
echo "╔════════════════════════════════════════════════════════════╗"
echo "║              Installation Complete! 🎉                     ║"
echo "╚════════════════════════════════════════════════════════════╝"
echo ""
echo "Next steps:"
echo ""
echo "1. Edit your configuration:"
echo "   sudo nano /etc/windrose-monitor/.env"
echo ""
echo "   Required variables:"
echo "   - PTERODACTYL_API_URL"
echo "   - PTERODACTYL_API_TOKEN"
echo "   - PTERODACTYL_SERVER_ID"
echo "   - DISCORD_WEBHOOK_URL"
echo ""
echo "2. Start the service:"
echo "   sudo systemctl start windrose-monitor"
echo ""
echo "3. Check status:"
echo "   sudo systemctl status windrose-monitor"
echo ""
echo "4. View logs (with timestamps):"
echo "   sudo tail -f /var/log/windrose-monitor/windrose-monitor.log"
echo ""
echo "5. Or use journalctl:"
echo "   sudo journalctl -u windrose-monitor -f"
echo ""
echo "For troubleshooting, see QUICKREF.md"
echo ""
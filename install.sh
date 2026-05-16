#!/bin/bash
# Windrose Monitor Installation Script
# Run this on your Ubuntu server: sudo bash install.sh

set -e

echo "╔════════════════════════════════════════════════════════════╗"
echo "║      Windrose Server Monitor - Installation Script         ║"
echo "╚════════════════════════════════════════════════════════════╝"
echo ""

# Check if running as root
if [ "$EUID" -ne 0 ]; then 
    echo "❌ This script must be run with sudo"
    exit 1
fi

# Check Python installation
if ! command -v python3 &> /dev/null; then
    echo "❌ Python 3 is not installed"
    exit 1
fi

echo "✓ Python 3 found: $(python3 --version)"
echo ""

# Create service user
echo "Creating service user..."
if id "windrose-monitor" &>/dev/null; then
    echo "  ℹ User windrose-monitor already exists"
else
    useradd -r -s /bin/false windrose-monitor
    echo "  ✓ Created windrose-monitor user"
fi

# Create directories
echo "Creating required directories..."
mkdir -p /var/lib/windrose-monitor
mkdir -p /etc/windrose-monitor
mkdir -p /var/log
chown windrose-monitor:windrose-monitor /var/lib/windrose-monitor
chmod 750 /var/lib/windrose-monitor
echo "  ✓ Directories created and configured"

#Create venv and install dependencies
echo "Creating Python virtual environment..."
python3 -m venv /var/lib/windrose-monitor/venv
source /var/lib/windrose-monitor/venv/bin/activate
pip install --upgrade pip
echo ""
echo "Installing Python dependencies..."w
pip install -r requirements.txt
deactivate
echo "  ✓ Virtual environment created and dependencies installed"

# Copy configuration template
echo ""
echo "Setting up configuration..."

# Setup .env file (recommended)
if [ -f /etc/windrose-monitor/.env ]; then
    echo "  ℹ .env file already exists at /etc/windrose-monitor/.env"
else
    cp .env.example /etc/windrose-monitor/.env
    chmod 600 /etc/windrose-monitor/.env
    chown windrose-monitor:windrose-monitor /etc/windrose-monitor/.env
    echo "  ✓ .env file created from .env.example"
    echo "  ⚠  You MUST edit /etc/windrose-monitor/.env with your settings:"
    echo "     - PTERODACTYL_API_URL"
    echo "     - PTERODACTYL_API_TOKEN"
    echo "     - PTERODACTYL_SERVER_ID"
    echo "     - DISCORD_WEBHOOK_URL"
fi

# Also support config.json for backwards compatibility
if [ -f /etc/windrose-monitor/config.json ]; then
    echo "  ℹ config.json already exists (will be used as fallback)"
else
    cp config.example.json /etc/windrose-monitor/config.json
    chmod 600 /etc/windrose-monitor/config.json
    chown windrose-monitor:windrose-monitor /etc/windrose-monitor/config.json
    echo "  ℹ config.json created (optional, .env is preferred)"
fi

# Create symlink
echo ""
echo "Installing executable..."
SCRIPT_DIR="$( cd "$( dirname "${BASH_SOURCE[0]}" )" && pwd )"
ln -sf "$SCRIPT_DIR/windrose_monitor.py" /usr/local/bin/windrose-monitor
chmod +x /usr/local/bin/windrose-monitor
echo "  ✓ Executable installed at /usr/local/bin/windrose-monitor"

# Setup sudoers for CPU frequency scaling
echo ""
echo "Configuring sudo permissions for CPU frequency scaling..."
SUDOERS_FILE="/etc/sudoers.d/windrose-monitor"
if [ -f "$SUDOERS_FILE" ]; then
    echo "  ℹ Sudoers file already configured"
else
    cat > "$SUDOERS_FILE" << 'EOF'
# Allow windrose-monitor to change CPU frequency without password
windrose-monitor ALL=(ALL) NOPASSWD:/usr/bin/tee /sys/devices/system/cpu/cpu*/cpufreq/energy_performance_preference
EOF
    chmod 440 "$SUDOERS_FILE"
    echo "  ✓ Sudoers file created"
fi

# Install systemd service
echo ""
echo "Installing systemd service..."
cp windrose-monitor.service /etc/systemd/system/
systemctl daemon-reload
systemctl enable windrose-monitor
echo "  ✓ Systemd service installed and enabled"

echo ""
echo "╔════════════════════════════════════════════════════════════╗"
echo "║              Installation Complete! 🎉                     ║"
echo "╚════════════════════════════════════════════════════════════╝"
echo ""
echo "Next steps:"
echo ""
echo "1. ⚠️  IMPORTANT: Edit your configuration file:"
echo "   sudo nano /etc/windrose-monitor/config.json"
echo ""
echo "   You need to add:"
echo "   - Your Pterodactyl API URL and token"
echo "   - Your Discord webhook URL"
echo "   - Your server UUID"
echo ""
echo "2. Verify the configuration is valid:"
echo "   python3 -m json.tool /etc/windrose-monitor/config.json"
echo ""
echo "3. Start the service:"
echo "   sudo systemctl start windrose-monitor"
echo ""
echo "4. Check if it's running:"
echo "   sudo systemctl status windrose-monitor"
echo ""
echo "5. View logs in real-time:"
echo "   sudo journalctl -u windrose-monitor -f"
echo ""
echo "For detailed setup instructions, see SETUP.md"
echo ""

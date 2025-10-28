#!/bin/bash
# Install Discord Bot as systemd service

set -e  # Exit on error

echo "=========================================="
echo "Discord Bot Service Installer"
echo "=========================================="
echo ""

# Get the current directory (where the bot is)
BOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
VENV_PATH="$BOT_DIR/.venv311"
PYTHON_PATH="$VENV_PATH/bin/python"
SERVICE_NAME="discordbot"
SERVICE_FILE="/etc/systemd/system/$SERVICE_NAME.service"

# Check if running as root
if [ "$EUID" -ne 0 ]; then
    echo "This script needs sudo privileges to install the systemd service."
    echo "Please run: sudo bash install_service.sh"
    exit 1
fi

# Get the actual user (even if running with sudo)
if [ -n "$SUDO_USER" ]; then
    ACTUAL_USER="$SUDO_USER"
else
    ACTUAL_USER="$(whoami)"
fi

echo "Bot directory: $BOT_DIR"
echo "Python path: $PYTHON_PATH"
echo "Service user: $ACTUAL_USER"
echo ""

# Check if virtual environment exists
if [ ! -f "$PYTHON_PATH" ]; then
    echo "ERROR: Virtual environment not found at $VENV_PATH"
    echo "Please run: python3 -m venv .venv311"
    exit 1
fi

# Check if .env file exists
if [ ! -f "$BOT_DIR/.env" ]; then
    echo "WARNING: .env file not found!"
    echo "Please create .env file with your configuration before starting the service."
    read -p "Continue anyway? (y/n) " -n 1 -r
    echo
    if [[ ! $REPLY =~ ^[Yy]$ ]]; then
        exit 1
    fi
fi

# Create systemd service file
echo "Creating systemd service file..."
cat > "$SERVICE_FILE" <<EOF
[Unit]
Description=Discord AI Bot with Ollama
After=network.target ollama.service
Wants=ollama.service

[Service]
Type=simple
User=$ACTUAL_USER
WorkingDirectory=$BOT_DIR
Environment="PATH=$VENV_PATH/bin:/usr/local/bin:/usr/bin:/bin"
ExecStart=$PYTHON_PATH main.py
Restart=on-failure
RestartSec=10
StandardOutput=journal
StandardError=journal

# Security settings
NoNewPrivileges=true
PrivateTmp=true

[Install]
WantedBy=multi-user.target
EOF

echo "Service file created at: $SERVICE_FILE"
echo ""

# Reload systemd
echo "Reloading systemd daemon..."
systemctl daemon-reload

# Enable service
echo "Enabling service to start on boot..."
systemctl enable "$SERVICE_NAME"

echo ""
echo "=========================================="
echo "Installation Complete!"
echo "=========================================="
echo ""
echo "Service Commands:"
echo "  Start:   sudo systemctl start $SERVICE_NAME"
echo "  Stop:    sudo systemctl stop $SERVICE_NAME"
echo "  Restart: sudo systemctl restart $SERVICE_NAME"
echo "  Status:  sudo systemctl status $SERVICE_NAME"
echo "  Logs:    sudo journalctl -u $SERVICE_NAME -f"
echo ""
echo "To start the bot now, run:"
echo "  sudo systemctl start $SERVICE_NAME"
echo ""

#!/bin/bash
# Install Discord Bot as systemd service

set -e  # Exit on error

echo "=========================================="
echo "Discord Bot Service Installer"
echo "=========================================="
echo ""

# Get the current directory (where the bot is)
BOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
VENV_PATH="$BOT_DIR/.venv"
SERVICE_NAME="discordbot"
SERVICE_FILE="/etc/systemd/system/$SERVICE_NAME.service"

# Check for uv
if ! command -v uv &> /dev/null; then
    echo "ERROR: uv is not installed"
    echo "Install with: curl -LsSf https://astral.sh/uv/install.sh | sh"
    exit 1
fi
UV_PATH="$(which uv)"

# Check for old installations and offer cleanup
OLD_VENVS=()
for old_venv in ".venv311" ".venv312" "venv"; do
    if [ -d "$BOT_DIR/$old_venv" ]; then
        OLD_VENVS+=("$old_venv")
    fi
done

if [ ${#OLD_VENVS[@]} -gt 0 ]; then
    echo "=========================================="
    echo "Old Installation Detected"
    echo "=========================================="
    echo ""
    echo "Found old virtual environment(s):"
    for venv in "${OLD_VENVS[@]}"; do
        echo "  - $venv"
    done
    echo ""
    echo "This project now uses 'uv' for dependency management."
    echo "Old virtual environments are no longer needed."
    echo ""
    read -p "Remove old virtual environments? (y/n) " -n 1 -r
    echo
    if [[ $REPLY =~ ^[Yy]$ ]]; then
        for venv in "${OLD_VENVS[@]}"; do
            echo "Removing $venv..."
            rm -rf "$BOT_DIR/$venv"
        done
        echo "Old environments removed."
    fi
    echo ""
fi

# Check for old requirements.txt based installs
if [ -f "$BOT_DIR/requirements.txt" ]; then
    echo "Note: Found requirements.txt - this project now uses pyproject.toml with uv."
    echo "You can safely remove requirements.txt if you're fully migrated to uv."
    echo ""
fi

# Check if existing service uses old setup
if [ -f "$SERVICE_FILE" ]; then
    if grep -q "venv311\|venv312" "$SERVICE_FILE"; then
        echo "=========================================="
        echo "Existing Service Upgrade"
        echo "=========================================="
        echo ""
        echo "Existing service uses old venv setup."
        echo "This installer will upgrade it to use uv."
        echo ""
        read -p "Continue with upgrade? (y/n) " -n 1 -r
        echo
        if [[ ! $REPLY =~ ^[Yy]$ ]]; then
            exit 1
        fi
        echo ""
    fi
fi

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
echo "uv path: $UV_PATH"
echo "Service user: $ACTUAL_USER"
echo ""

# Check if virtual environment exists (created by uv sync)
if [ ! -d "$VENV_PATH" ]; then
    echo "Virtual environment not found. Running 'uv sync' to create it..."
    echo ""
    cd "$BOT_DIR"
    sudo -u "$ACTUAL_USER" uv sync
    if [ $? -ne 0 ]; then
        echo "ERROR: Failed to create virtual environment with uv sync"
        exit 1
    fi
    echo ""
    echo "Dependencies installed successfully."
    echo ""
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
Environment="PATH=/usr/local/bin:/usr/bin:/bin"
ExecStart=$UV_PATH run python main.py
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

#!/bin/bash
# Uninstall Discord Bot systemd service

set -e  # Exit on error

SERVICE_NAME="discordbot"
SERVICE_FILE="/etc/systemd/system/$SERVICE_NAME.service"

echo "=========================================="
echo "Discord Bot Service Uninstaller"
echo "=========================================="
echo ""

# Check if running as root
if [ "$EUID" -ne 0 ]; then
    echo "This script needs sudo privileges to uninstall the systemd service."
    echo "Please run: sudo bash uninstall_service.sh"
    exit 1
fi

# Check if service exists
if [ ! -f "$SERVICE_FILE" ]; then
    echo "Service not found at: $SERVICE_FILE"
    echo "Nothing to uninstall."
    exit 0
fi

# Stop service if running
echo "Stopping service..."
systemctl stop "$SERVICE_NAME" 2>/dev/null || true

# Disable service
echo "Disabling service..."
systemctl disable "$SERVICE_NAME" 2>/dev/null || true

# Remove service file
echo "Removing service file..."
rm -f "$SERVICE_FILE"

# Reload systemd
echo "Reloading systemd daemon..."
systemctl daemon-reload
systemctl reset-failed 2>/dev/null || true

echo ""
echo "=========================================="
echo "Uninstallation Complete!"
echo "=========================================="
echo ""
echo "The bot service has been removed."
echo "Your bot code and data are still intact."
echo ""

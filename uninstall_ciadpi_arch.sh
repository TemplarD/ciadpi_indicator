#!/bin/bash

# CIADPI Uninstaller for Arch Linux

set -e

RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m'

echo -e "${RED}━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━${NC}"
echo -e "${RED}    CIADPI Uninstaller for Arch Linux${NC}"
echo -e "${RED}━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━${NC}"

# Stop and disable service
echo -e "\n${YELLOW}🛑 Stopping CIADPI service...${NC}"
systemctl --user stop ciadpi.service 2>/dev/null || true
systemctl --user disable ciadpi.service 2>/dev/null || true

# Remove service file
rm -f ~/.config/systemd/user/ciadpi.service

# Remove autostart
rm -f ~/.config/autostart/ciadpi-indicator.desktop

# Remove binaries and scripts
echo -e "${YELLOW}🗑️  Removing CIADPI files...${NC}"
rm -f ~/.local/bin/ciadpi_advanced_tray.py
rm -f ~/.local/bin/ciadpi_autosearch.py
rm -f ~/.local/bin/ciadpi_param_generator.py
rm -f ~/.local/bin/ciadpi_whitelist.py
rm -f ~/.local/bin/ciadpi_launcher.sh
rm -f ~/.local/bin/diagnose_ciadpi.py
rm -f ~/.local/bin/byedpi

# Remove config directory
rm -rf ~/.config/ciadpi

# Optionally remove byedpi source
read -p "Remove byedpi source directory (~/byedpi)? (y/N): " -n 1 -r
echo
if [[ $REPLY =~ ^[Yy]$ ]]; then
    rm -rf ~/byedpi
    echo -e "${GREEN}✓ Removed byedpi source${NC}"
fi

# Reload systemd
systemctl --user daemon-reload

echo -e "\n${GREEN}✅ CIADPI has been completely removed from your system${NC}"
echo -e "${GREEN}━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━${NC}"
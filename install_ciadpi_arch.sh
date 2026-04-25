#!/bin/bash

# CIADPI Complete Solution Installer for Arch Linux
# Adapted from TemplarD/ciadpi_indicator

set -e

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m' # No Color

echo -e "${GREEN}━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━${NC}"
echo -e "${GREEN}    CIADPI Complete Solution Installer for Arch Linux${NC}"
echo -e "${GREEN}━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━${NC}"

# Check if running as root
if [ "$EUID" -eq 0 ]; then 
   echo -e "${RED}Please do not run as root (use regular user with sudo)${NC}"
   exit 1
fi

# Check if systemd is running
if ! systemctl list-units --type=service &>/dev/null; then
    echo -e "${RED}Systemd not detected. This script requires systemd.${NC}"
    exit 1
fi

echo -e "\n${YELLOW}📦 Installing dependencies for Arch Linux...${NC}"

# Install required packages for Arch
sudo pacman -S --noconfirm --needed \
    python \
    python-pip \
    python-gobject \
    gtk3 \
    libappindicator-gtk3 \
    git \
    base-devel \
    wget \
    curl \
    net-tools \
    make \
    gcc

# Install Python packages via pip
echo -e "\n${YELLOW}🐍 Installing Python packages...${NC}"
pip install --user requests

# Check for yay (AUR helper)
if ! command -v yay &> /dev/null && ! command -v paru &> /dev/null; then
    echo -e "${YELLOW}⚠️  No AUR helper found. Installing yay...${NC}"
    cd /tmp
    git clone https://aur.archlinux.org/yay.git
    cd yay
    makepkg -si --noconfirm
    cd ..
    rm -rf yay
fi

# Install systemd-resolvconf from AUR (optional but recommended)
if ! systemctl is-active --quiet systemd-resolved; then
    echo -e "\n${YELLOW}🔧 Installing systemd-resolved...${NC}"
    if command -v yay &> /dev/null; then
        yay -S --noconfirm systemd-resolvconf
    else
        paru -S --noconfirm systemd-resolvconf
    fi
    sudo systemctl enable systemd-resolved
    sudo systemctl start systemd-resolved
fi

# Create directories
echo -e "\n${YELLOW}📁 Creating directories...${NC}"
mkdir -p ~/.local/bin
mkdir -p ~/.config/ciadpi
mkdir -p ~/.config/autostart

# Clone and compile byedpi
echo -e "\n${YELLOW}🔨 Building byedpi from source...${NC}"
if [ -d ~/byedpi ]; then
    echo -e "${YELLOW}byedpi directory exists, updating...${NC}"
    cd ~/byedpi
    git pull
else
    cd ~
    git clone https://github.com/hufrea/byedpi.git
    cd byedpi
fi

make
if [ -f ./byedpi ]; then
    cp byedpi ~/.local/bin/
    echo -e "${GREEN}✓ byedpi built and installed successfully${NC}"
else
    echo -e "${RED}Failed to build byedpi${NC}"
    exit 1
fi

# Download CIADPI files from GitHub
echo -e "\n${YELLOW}📥 Downloading CIADPI files...${NC}"
cd /tmp
git clone https://github.com/TemplarD/ciadpi_indicator.git
cd ciadpi_indicator

# Copy main files
cp ciadpi_advanced_tray.py ~/.local/bin/
cp ciadpi_autosearch.py ~/.local/bin/
cp ciadpi_param_generator.py ~/.local/bin/
cp ciadpi_whitelist.py ~/.local/bin/
cp ciadpi_launcher.sh ~/.local/bin/
cp diagnose_ciadpi.py ~/.local/bin/

# Make scripts executable
chmod +x ~/.local/bin/*.py
chmod +x ~/.local/bin/*.sh

# Create systemd service file (adapted for Arch)
echo -e "\n${YELLOW}⚙️  Creating systemd service...${NC}"
cat > ~/.config/systemd/user/ciadpi.service << 'EOF'
[Unit]
Description=CIADPI - DPI Bypass Service for Arch Linux
After=network.target

[Service]
Type=simple
ExecStart=%h/.local/bin/ciadpi_launcher.sh
Restart=on-failure
RestartSec=5
Environment="PATH=/usr/bin:/usr/local/bin:%h/.local/bin"

[Install]
WantedBy=default.target
EOF

# Create launcher script content
cat > ~/.local/bin/ciadpi_launcher.sh << 'EOF'
#!/bin/bash
# CIADPI Launcher for Arch Linux

# Start byedpi with default parameters
~/.local/bin/byedpi --pidfile /tmp/byedpi.pid --port 1080 --ip 127.0.0.1 --http --https --mixhost "*.cloudflare.com" --mixhost "*.google.com" --mixhost "*.youtube.com"

# Keep the script running
while kill -0 $(cat /tmp/byedpi.pid 2>/dev/null) 2>/dev/null; do
    sleep 1
done
EOF

chmod +x ~/.local/bin/ciadpi_launcher.sh

# Create autostart entry
echo -e "\n${YELLOW}🚀 Setting up autostart...${NC}"
cat > ~/.config/autostart/ciadpi-indicator.desktop << EOF
[Desktop Entry]
Type=Application
Name=CIADPI Indicator
Exec=python %h/.local/bin/ciadpi_advanced_tray.py
Icon=network-wired
Comment=DPI Bypass System Tray Indicator
X-GNOME-Autostart-enabled=true
EOF

# Create config.json if it doesn't exist
if [ ! -f ~/.config/ciadpi/config.json ]; then
    cat > ~/.config/ciadpi/config.json << 'EOF'
{
  "proxy_enabled": true,
  "proxy_mode": "manual",
  "proxy_host": "127.0.0.1",
  "proxy_port": "1080",
  "auto_disable_proxy": true,
  "we_changed_proxy": false
}
EOF
fi

# Enable and start user service
echo -e "\n${YELLOW}🔄 Enabling and starting CIADPI service...${NC}"
systemctl --user daemon-reload
systemctl --user enable ciadpi.service
systemctl --user start ciadpi.service

echo -e "\n${GREEN}━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━${NC}"
echo -e "${GREEN}✅ CIADPI has been successfully installed on Arch Linux!${NC}"
echo -e "${GREEN}━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━${NC}"
echo -e "\n${YELLOW}📌 Next steps:${NC}"
echo -e "  1. ${GREEN}Log out and log back in${NC} to see the system tray indicator"
echo -e "  2. Or run manually: ${GREEN}python ~/.local/bin/ciadpi_advanced_tray.py${NC}"
echo -e "  3. Check service status: ${GREEN}systemctl --user status ciadpi.service${NC}"
echo -e "\n${YELLOW}🔧 Proxy Configuration:${NC}"
echo -e "  • HTTP/HTTPS Proxy: ${GREEN}127.0.0.1:1080${NC}"
echo -e "  • For browsers: Set manual proxy to 127.0.0.1 port 1080"
echo -e "\n${YELLOW}🛟 Help & Diagnostics:${NC}"
echo -e "  • Run diagnostics: ${GREEN}python ~/.local/bin/diagnose_ciadpi.py${NC}"
echo -e "  • View service logs: ${GREEN}journalctl --user -u ciadpi.service -f${NC}"
echo -e "\n${YELLOW}🗑️  To uninstall:${NC}"
echo -e "  • Stop service: ${GREEN}systemctl --user stop ciadpi.service${NC}"
echo -e "  • Disable service: ${GREEN}systemctl --user disable ciadpi.service${NC}"
echo -e "  • Remove files: ${GREEN}rm -rf ~/.local/bin/ciadpi* ~/.config/ciadpi ~/byedpi${NC}"
echo -e "${GREEN}━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━${NC}"
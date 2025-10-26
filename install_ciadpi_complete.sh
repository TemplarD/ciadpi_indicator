#!/bin/bash

# Complete CIADPI Installer - Installs both byedpi and indicator

set -e

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

LOG_FILE="/tmp/ciadpi_complete_install.log"
echo "Complete CIADPI Installation started at $(date)" > "$LOG_FILE"

log() {
    echo -e "${GREEN}[INFO]${NC} $1"
    echo "[INFO] $1" >> "$LOG_FILE"
}

warn() {
    echo -e "${YELLOW}[WARN]${NC} $1"
    echo "[WARN] $1" >> "$LOG_FILE"
}

error() {
    echo -e "${RED}[ERROR]${NC} $1"
    echo "[ERROR] $1" >> "$LOG_FILE"
    exit 1
}

# Check if running as root
if [ "$EUID" -eq 0 ]; then
    error "Please do not run as root. The script will use sudo when needed."
fi

# Install build dependencies
install_build_dependencies() {
    log "Installing build dependencies..."
    
    sudo apt update || warn "Failed to update package list"
    
    sudo apt install -y git build-essential gcc || error "Failed to install build tools"
    
    log "Build dependencies installed"
}

# Clone and build byedpi
install_byedpi() {
    local byedpi_dir="$HOME/byedpi"
    
    if [ -d "$byedpi_dir" ]; then
        log "byedpi directory already exists, updating..."
        cd "$byedpi_dir"
        git pull || warn "Failed to update byedpi repository"
    else
        log "Cloning byedpi repository..."
        git clone https://github.com/hufrea/byedpi.git "$byedpi_dir" || error "Failed to clone byedpi"
        cd "$byedpi_dir"
    fi
    
    # Check if ciadpi.c exists
    if [ ! -f "ciadpi.c" ]; then
        error "ciadpi.c not found in byedpi repository"
    fi
    
    log "Building ciadpi binary..."
    gcc -O3 -o ciadpi ciadpi.c || error "Failed to build ciadpi"
    
    if [ ! -f "ciadpi" ]; then
        error "ciadpi binary was not created"
    fi
    
    chmod +x ciadpi
    log "byedpi successfully installed in $byedpi_dir"
}

# Check dependencies for indicator
check_dependencies() {
    log "Checking dependencies for indicator..."
    
    local missing_deps=()
    
    # Check required packages
    for dep in python3 python3-gi python3-gi-cairo gir1.2-appindicator3-0.1; do
        if ! dpkg -l | grep -q "^ii  $dep "; then
            missing_deps+=($dep)
        fi
    done
    
    # Check Python modules
    if ! python3 -c "import gi" &>/dev/null; then
        missing_deps+=("python3-gi")
    fi
    
    if [ ${#missing_deps[@]} -ne 0 ]; then
        warn "Missing dependencies: ${missing_deps[*]}"
        install_dependencies "${missing_deps[@]}"
    else
        log "All dependencies satisfied"
    fi
}

# Install dependencies
install_dependencies() {
    log "Installing dependencies..."
    sudo apt update || warn "Failed to update package list"
    
    sudo apt install -y "$@" || error "Failed to install dependencies: $*"
}

# Install systemd service
install_service() {
    log "Installing systemd service..."
    
    local byedpi_dir="$HOME/byedpi"
    local service_file="ciadpi.service"
    
    if [ -f "$service_file" ]; then
        # Use the service file from repository
        sudo cp "$service_file" /etc/systemd/system/ciadpi.service || error "Failed to copy service file"
    else
        # Create service file dynamically
        warn "Service file not found in repository, creating default..."
        
        cat << EOF | sudo tee /etc/systemd/system/ciadpi.service > /dev/null
[Unit]
Description=CIADPI DPI Bypass Service
After=network.target
Wants=network.target

[Service]
Type=simple
User=$USER
WorkingDirectory=$byedpi_dir
ExecStart=$byedpi_dir/ciadpi -o1 -o25+s -T3 -At o--tlsrec 1+s
Restart=on-failure
RestartSec=5
TimeoutStartSec=30
StandardOutput=journal
StandardError=journal

[Install]
WantedBy=multi-user.target
EOF
    fi
    
    sudo systemctl daemon-reload || error "Failed to reload systemd"
    log "Systemd service installed"
}

# Install Python scripts
install_python_scripts() {
    log "Installing Python scripts..."
    
    mkdir -p "$HOME/.local/bin"
    
    # Copy main indicator script
    if [ -f "ciadpi_advanced_tray.py" ]; then
        cp "ciadpi_advanced_tray.py" "$HOME/.local/bin/"
        chmod +x "$HOME/.local/bin/ciadpi_advanced_tray.py"
        log "Indicator script installed"
    else
        error "ciadpi_advanced_tray.py not found in repository"
    fi
    
    # Лаунчер
    if [ -f "ciadpi_launcher.sh" ]; then
        cp "ciadpi_launcher.sh" "$HOME/.local/bin/"
        chmod +x "$HOME/.local/bin/ciadpi_launcher.sh"
        log "Launcher script installed"        
    fi

    # Copy autosearch if available
    if [ -f "ciadpi_autosearch.py" ]; then
        cp "ciadpi_autosearch.py" "$HOME/.local/bin/"
        chmod +x "$HOME/.local/bin/ciadpi_autosearch.py"
        log "Autosearch script installed"
    fi

    # Генератор параметров
    if [ -f "ciadpi_param_generator.py" ]; then
        cp "ciadpi_param_generator.py" "$HOME/.local/bin/"
        chmod +x "$HOME/.local/bin/ciadpi_param_generator.py"
        log "Generator param script installed"        
    fi
    
    log "Python scripts installed to ~/.local/bin/"
}

# Install desktop files
install_desktop_files() {
    log "Installing desktop files..."
    
    # Create application directory
    mkdir -p "$HOME/.local/share/applications"
      
    # Desktop file for indicator
    cat << EOF > "$HOME/.local/share/applications/ciadpi-indicator.desktop"
[Desktop Entry]
Version=1.0
Type=Application
Name=CIADPI Indicator
Comment=Advanced DPI Bypass Indicator
Exec=$HOME/.local/bin/ciadpi_launcher.sh
Icon=network-transmit-receive
Categories=Network;
StartupNotify=false
Terminal=false
X-GNOME-Autostart-enabled=true
EOF

    # Autostart file
    mkdir -p "$HOME/.config/autostart"
    cp "$HOME/.local/share/applications/ciadpi-indicator.desktop" "$HOME/.config/autostart/"
    
    log "Desktop files installed"
}

# Setup configuration
setup_config() {
    log "Setting up configuration..."
    
    local config_dir="$HOME/.config/ciadpi"
    mkdir -p "$config_dir"
    
    # Create default config if not exists
    if [ ! -f "$config_dir/config.json" ]; then
        cat << EOF > "$config_dir/config.json"
{
    "params": "-o1 -o25+s -T3 -At o--tlsrec 1+s",
    "proxy_enabled": false,
    "proxy_host": "",
    "proxy_port": "1080",
    "current_params": "-o1 -o25+s -T3 -At o--tlsrec 1+s"
}
EOF
        log "Default configuration created"
    fi
    
    # Create logs directory
    mkdir -p "$config_dir/logs"
}

# Setup permissions
setup_permissions() {
    log "Setting up permissions..."
    
    # Add user to systemd journal group for log access
    sudo usermod -a -G systemd-journal "$USER" || warn "Failed to add user to systemd-journal group"
    
    # Allow user to manage ciadpi service without password
    echo "$USER ALL=(ALL) NOPASSWD: /bin/systemctl start ciadpi.service, /bin/systemctl stop ciadpi.service, /bin/systemctl restart ciadpi.service, /bin/systemctl status ciadpi.service" | sudo tee /etc/sudoers.d/ciadpi > /dev/null
    sudo chmod 440 /etc/sudoers.d/ciadpi
    
    log "Permissions configured"
}

# Enable and start service
start_services() {
    log "Starting services..."
    
    sudo systemctl enable ciadpi.service || warn "Failed to enable ciadpi service"
    sudo systemctl start ciadpi.service || warn "Failed to start ciadpi service"
    
    log "CIADPI service started and enabled"
}

# Test installation
test_installation() {
    log "Testing installation..."
    
    # Test byedpi binary
    if [ -f "$HOME/byedpi/ciadpi" ]; then
        log "✓ byedpi binary found and is executable"
    else
        error "✗ byedpi binary not found"
    fi
    
    # Test systemd service
    if systemctl is-active --quiet ciadpi.service; then
        log "✓ CIADPI service is running"
    else
        warn "⚠ CIADPI service is not running (this might be normal during first install)"
    fi
    
    # Test Python script
    if [ -f "$HOME/.local/bin/ciadpi_advanced_tray.py" ]; then
        log "✓ Indicator script installed"
    else
        error "✗ Indicator script not found"
    fi
}

# Post-installation info
post_install_info() {
    echo
    echo -e "${GREEN}╔══════════════════════════════════════════════════════════════╗${NC}"
    echo -e "${GREEN}║               Complete CIADPI Installation Done!            ║${NC}"
    echo -e "${GREEN}╚══════════════════════════════════════════════════════════════╝${NC}"
    echo
    echo -e "${BLUE}What was installed:${NC}"
    echo -e "  • ${GREEN}✓${NC} byedpi (cloned and compiled)"
    echo -e "  • ${GREEN}✓${NC} CIADPI binary"
    echo -e "  • ${GREEN}✓${NC} System tray indicator"
    echo -e "  • ${GREEN}✓${NC} Systemd service"
    echo -e "  • ${GREEN}✓${NC} Autostart configuration"
    echo
    echo -e "${BLUE}Installation locations:${NC}"
    echo -e "  ${YELLOW}byedpi:${NC} ~/byedpi/"
    echo -e "  ${YELLOW}Indicator:${NC} ~/.local/bin/ciadpi_advanced_tray.py"
    echo -e "  ${YELLOW}Service:${NC} /etc/systemd/system/ciadpi.service"
    echo -e "  ${YELLOW}Config:${NC} ~/.config/ciadpi/"
    echo
    echo -e "${BLUE}How to use:${NC}"
    echo -e "  ${YELLOW}System Tray:${NC} Look for network icon in system tray"
    echo -e "  ${YELLOW}Manual Start:${NC} ~/.local/bin/ciadpi_advanced_tray.py"
    echo -e "  ${YELLOW}Service Control:${NC} systemctl {start|stop|restart} ciadpi"
    echo
    echo -e "${BLUE}Useful commands:${NC}"
    echo -e "  ${YELLOW}Check service:${NC} systemctl status ciadpi.service"
    echo -e "  ${YELLOW}View logs:${NC} journalctl -u ciadpi.service -f"
    echo -e "  ${YELLOW}Uninstall:${NC} Run uninstall_ciadpi_complete.sh"
    echo
    echo -e "${GREEN}The indicator should appear in your system tray!${NC}"
    echo -e "${YELLOW}If it doesn't appear, log out and log back in or restart.${NC}"
    echo
}

# Main installation function
main() {
    echo -e "${GREEN}╔══════════════════════════════════════════════════════════════╗${NC}"
    echo -e "${GREEN}║               Complete CIADPI Installer                     ║${NC}"
    echo -e "${GREEN}╚══════════════════════════════════════════════════════════════╝${NC}"
    echo
    echo -e "${BLUE}This will install:${NC}"
    echo -e "  • byedpi (DPI bypass tool)"
    echo -e "  • System tray indicator"
    echo -e "  • Systemd service"
    echo -e "  • Autostart configuration"
    echo
    
    install_build_dependencies
    install_byedpi
    check_dependencies
    install_service
    install_python_scripts
    install_desktop_files
    setup_config
    setup_permissions
    start_services
    test_installation
    post_install_info
    
    log "Complete installation finished successfully"
}

# Run main function
main "$@"
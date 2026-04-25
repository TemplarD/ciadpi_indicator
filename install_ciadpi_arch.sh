#!/bin/bash

# CIADPI Complete Solution Installer for Arch Linux
# Full featured version - equivalent to original Ubuntu installer
# WITHOUT system update (no pacman -Syu)

set -e

# Colors
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m'
BOLD='\033[1m'

# Global variables
INSTALL_LOG=""
BACKUP_DIR=""
DESKTOP_ENV=""
SERVICE_NAME="ciadpi.service"
USER_SERVICE_DIR="$HOME/.config/systemd/user"

# Logging functions
log_info() {
    echo -e "$(date '+%Y-%m-%d %H:%M:%S') ${GREEN}[INFO]${NC} $1" | tee -a "$INSTALL_LOG"
}

log_warn() {
    echo -e "$(date '+%Y-%m-%d %H:%M:%S') ${YELLOW}[WARN]${NC} $1" | tee -a "$INSTALL_LOG"
}

log_error() {
    echo -e "$(date '+%Y-%m-%d %H:%M:%S') ${RED}[ERROR]${NC} $1" | tee -a "$INSTALL_LOG"
}

log_step() {
    echo -e "\n${BLUE}━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━${NC}" | tee -a "$INSTALL_LOG"
    echo -e "${BLUE}▶ $1${NC}" | tee -a "$INSTALL_LOG"
    echo -e "${BLUE}━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━${NC}" | tee -a "$INSTALL_LOG"
}

# Error handler
on_error() {
    log_error "Installation failed at line $1"
    log_error "Exit code: $2"
    log_info "Run uninstall script to clean up"
    exit 1
}
trap 'on_error $LINENO $?' ERR

# Check if running as root
if [ "$EUID" -eq 0 ]; then
    echo -e "${RED}Please do not run as root${NC}"
    exit 1
fi

# Check systemd
if ! command -v systemctl &>/dev/null; then
    echo -e "${RED}Systemd not found. This script requires systemd.${NC}"
    exit 1
fi

# Initialize installation
echo -e "${GREEN}━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━${NC}"
echo -e "${GREEN}    CIADPI Complete Solution Installer for Arch Linux${NC}"
echo -e "${GREEN}━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━${NC}"
echo ""

# Create log directory
mkdir -p "$HOME/.config/ciadpi/logs"
INSTALL_LOG="$HOME/.config/ciadpi/logs/install_$(date +%Y%m%d_%H%M%S).log"
log_info "Installation log: $INSTALL_LOG"

# Backup function
backup_file() {
    local file="$1"
    if [ -f "$file" ]; then
        local backup_name="${file}.backup_$(date +%Y%m%d_%H%M%S)"
        cp "$file" "$backup_name"
        log_info "Backed up: $file -> $backup_name"
        echo "$backup_name"
    fi
}

# Restore function
restore_backup() {
    local backup="$1"
    local original="${backup%.backup_*}"
    if [ -f "$backup" ]; then
        cp "$backup" "$original"
        log_info "Restored: $backup -> $original"
    fi
}

# Detect desktop environment
detect_desktop_environment() {
    if [ -n "$XDG_CURRENT_DESKTOP" ]; then
        case "$XDG_CURRENT_DESKTOP" in
            *GNOME*) echo "gnome" ;;
            *KDE*) echo "kde" ;;
            *XFCE*) echo "xfce" ;;
            *Cinnamon*) echo "cinnamon" ;;
            *MATE*) echo "mate" ;;
            *) echo "other" ;;
        esac
    elif [ -n "$DESKTOP_SESSION" ]; then
        case "$DESKTOP_SESSION" in
            gnome*) echo "gnome" ;;
            kde*) echo "kde" ;;
            xfce*) echo "xfce" ;;
            cinnamon*) echo "cinnamon" ;;
            mate*) echo "mate" ;;
            *) echo "other" ;;
        esac
    else
        echo "unknown"
    fi
}

# Check if package is installed
is_package_installed() {
    pacman -Q "$1" &>/dev/null
}

# Install package if not present
install_package_if_needed() {
    local pkg="$1"
    if ! is_package_installed "$pkg"; then
        log_info "Installing: $pkg"
        sudo pacman -S --noconfirm --needed "$pkg"
    else
        log_info "Already installed: $pkg"
    fi
}

# Check AppIndicator support
check_appindicator_support() {
    log_step "Checking AppIndicator support"
    
    if [ "$DESKTOP_ENV" = "gnome" ]; then
        if ! is_package_installed "gnome-shell-extensions"; then
            log_warn "GNOME Extensions not fully installed"
            log_info "You may need AppIndicator extension for GNOME"
        fi
    elif [ "$DESKTOP_ENV" = "kde" ]; then
        log_info "KDE Plasma has native AppIndicator support"
    elif [ "$DESKTOP_ENV" = "xfce" ]; then
        if ! is_package_installed "xfce4-indicator-plugin"; then
            log_warn "xfce4-indicator-plugin not installed"
            log_info "Install it for tray icon support: sudo pacman -S xfce4-indicator-plugin"
        fi
    fi
}

# Main installation
main() {
    # Step 1: Detect environment
    log_step "Step 1/15: System detection"
    
    DESKTOP_ENV=$(detect_desktop_environment)
    log_info "Desktop environment: $DESKTOP_ENV"
    log_info "User: $USER"
    log_info "Home: $HOME"
    log_info "Architecture: $(uname -m)"
    
    # Step 2: Create backup directory
    log_step "Step 2/15: Creating backup directory"
    
    BACKUP_DIR="$HOME/.config/ciadpi/backups/$(date +%Y%m%d_%H%M%S)"
    mkdir -p "$BACKUP_DIR"
    log_info "Backup directory: $BACKUP_DIR"
    
    # Step 3: Backup existing configurations
    log_step "Step 3/15: Backing up existing configurations"
    
    if [ -f "$HOME/.config/ciadpi/config.json" ]; then
        backup_file "$HOME/.config/ciadpi/config.json" > "$BACKUP_DIR/config.json.backup.path"
        log_info "Backed up config.json"
    fi
    
    if [ -f "$HOME/.config/ciadpi/byedpi_params.conf" ]; then
        backup_file "$HOME/.config/ciadpi/byedpi_params.conf" > "$BACKUP_DIR/params.conf.backup.path"
        log_info "Backed up byedpi_params.conf"
    fi
    
    # Step 4: Install system dependencies
    log_step "Step 4/15: Installing system dependencies"
    
    DEPENDENCIES=(
        "git"
        "base-devel"
        "python"
        "python-pip"
        "python-gobject"
        "gtk3"
        "libappindicator-gtk3"
        "wget"
        "curl"
        "make"
        "gcc"
        "net-tools"
        "python-pipx"
    )
    
    for dep in "${DEPENDENCIES[@]}"; do
        install_package_if_needed "$dep"
    done
    
    # Step 5: Install Python requests
    log_step "Step 5/15: Installing Python requests"
    
    if pip install --user --break-system-packages requests &>/dev/null; then
        log_info "requests installed successfully"
    else
        log_error "Failed to install requests"
        exit 1
    fi
    
    # Verify requests
    if python -c "import requests" 2>/dev/null; then
        log_info "requests module verified"
    else
        log_error "requests module not working"
        exit 1
    fi
    
    # Step 6: Create directory structure
    log_step "Step 6/15: Creating directory structure"
    
    mkdir -p "$HOME/.local/bin"
    mkdir -p "$HOME/.config/ciadpi"
    mkdir -p "$HOME/.config/autostart"
    mkdir -p "$USER_SERVICE_DIR"
    mkdir -p "$HOME/.local/share/applications"
    mkdir -p "$HOME/.config/ciadpi/whitelist"
    log_info "Directory structure created"
    
    # Step 7: Build byedpi
    log_step "Step 7/15: Building byedpi from source"
    
    cd "$HOME"
    if [ -d "$HOME/byedpi" ]; then
        log_info "byedpi directory exists, updating..."
        cd byedpi
        git pull 2>&1 | tee -a "$INSTALL_LOG"
    else
        log_info "Cloning byedpi repository..."
        git clone https://github.com/hufrea/byedpi.git 2>&1 | tee -a "$INSTALL_LOG"
        cd byedpi
    fi
    
    log_info "Compiling byedpi..."
    make clean 2>/dev/null || true
    make 2>&1 | tee -a "$INSTALL_LOG"
    
    if [ -f ./ciadpi ]; then
        cp ciadpi "$HOME/.local/bin/byedpi"
        chmod +x "$HOME/.local/bin/byedpi"
        log_info "byedpi installed to ~/.local/bin/byedpi"
    elif [ -f ./byedpi ]; then
        cp byedpi "$HOME/.local/bin/byedpi"
        chmod +x "$HOME/.local/bin/byedpi"
        log_info "byedpi installed to ~/.local/bin/byedpi"
    else
        log_error "Failed to build byedpi - binary not found"
        exit 1
    fi
    cd "$HOME"
    
    # Step 8: Download CIADPI indicator
    log_step "Step 8/15: Downloading CIADPI indicator files"
    
    rm -rf /tmp/ciadpi_src
    git clone --depth 1 https://github.com/TemplarD/ciadpi_indicator.git /tmp/ciadpi_src 2>&1 | tee -a "$INSTALL_LOG"
    
    INDICATOR_FILES=(
        "ciadpi_advanced_tray.py"
        "ciadpi_autosearch.py"
        "ciadpi_param_generator.py"
        "ciadpi_whitelist.py"
        "ciadpi_launcher.sh"
        "diagnose_ciadpi.py"
    )
    
    for file in "${INDICATOR_FILES[@]}"; do
        if [ -f "/tmp/ciadpi_src/$file" ]; then
            cp "/tmp/ciadpi_src/$file" "$HOME/.local/bin/"
            chmod +x "$HOME/.local/bin/$file"
            log_info "Installed: $file"
        else
            log_warn "Missing: $file"
        fi
    done
    rm -rf /tmp/ciadpi_src
    
    # Step 9: Create systemd service
    log_step "Step 9/15: Creating systemd service"
    
    cat > "$USER_SERVICE_DIR/ciadpi.service" << 'EOF'
[Unit]
Description=CIADPI - DPI Bypass Service for Arch Linux
Documentation=https://github.com/TemplarD/ciadpi_indicator
After=network.target

[Service]
Type=simple
ExecStart=%h/.local/bin/ciadpi_launcher.sh
Restart=on-failure
RestartSec=5
StandardOutput=journal
StandardError=journal
SyslogIdentifier=ciadpi
Environment="PATH=/usr/bin:/usr/local/bin:%h/.local/bin"

[Install]
WantedBy=default.target
EOF
    
    log_info "Service file created: $USER_SERVICE_DIR/ciadpi.service"
    
    # Step 10: Create launcher script
    log_step "Step 10/15: Creating launcher script"
    
    cat > "$HOME/.local/bin/ciadpi_launcher.sh" << 'EOF'
#!/bin/bash
# CIADPI Launcher for Arch Linux

CONFIG_FILE="$HOME/.config/ciadpi/byedpi_params.conf"
PID_FILE="/tmp/byedpi.pid"

# Load parameters from config
if [ -f "$CONFIG_FILE" ]; then
    PARAMS=$(cat "$CONFIG_FILE")
else
    # Default parameters
    PARAMS="--port 1080 --ip 127.0.0.1 --http --https"
fi

# Start byedpi
~/.local/bin/byedpi $PARAMS --pidfile "$PID_FILE"

# Keep running while byedpi is alive
while kill -0 $(cat "$PID_FILE" 2>/dev/null) 2>/dev/null; do
    sleep 2
done
EOF
    
    chmod +x "$HOME/.local/bin/ciadpi_launcher.sh"
    log_info "Launcher script created"
    
    # Step 11: Setup autostart
    log_step "Step 11/15: Setting up autostart"
    
    cat > "$HOME/.config/autostart/ciadpi-indicator.desktop" << EOF
[Desktop Entry]
Type=Application
Name=CIADPI Indicator
Comment=DPI Bypass System Tray Indicator
Exec=python $HOME/.local/bin/ciadpi_advanced_tray.py
Icon=network-wired
Terminal=false
StartupNotify=false
X-GNOME-Autostart-enabled=true
EOF
    
    cat > "$HOME/.local/share/applications/ciadpi-indicator.desktop" << EOF
[Desktop Entry]
Type=Application
Name=CIADPI Indicator
Comment=DPI Bypass System Tray Indicator
Exec=python $HOME/.local/bin/ciadpi_advanced_tray.py
Icon=network-wired
Terminal=false
Categories=Network;
EOF
    
    log_info "Autostart entries created for $DESKTOP_ENV"
    
    # Step 12: Create configuration
    log_step "Step 12/15: Creating configuration files"
    
    cat > "$HOME/.config/ciadpi/config.json" << 'EOF'
{
    "version": "1.0",
    "proxy_enabled": true,
    "proxy_mode": "manual",
    "proxy_host": "127.0.0.1",
    "proxy_port": "1080",
    "auto_disable_proxy": true,
    "we_changed_proxy": false,
    "whitelist_enabled": false,
    "whitelist_domains": [],
    "install_date": "INSTALL_DATE_PLACEHOLDER",
    "installer_version": "2.0-arch"
}
EOF
    
    # Replace placeholder with actual date
    sed -i "s/INSTALL_DATE_PLACEHOLDER/$(date -Iseconds)/" "$HOME/.config/ciadpi/config.json"
    
    cat > "$HOME/.config/ciadpi/byedpi_params.conf" << 'EOF'
--port 1080 --ip 127.0.0.1 --http --https
EOF
    
    touch "$HOME/.config/ciadpi/whitelist.txt"
    log_info "Configuration files created"
    
    # Step 13: Check AppIndicator support
    log_step "Step 13/15: Checking AppIndicator support"
    check_appindicator_support
    
    # Step 14: Start service
    log_step "Step 14/15: Starting CIADPI service"
    
    systemctl --user daemon-reload
    systemctl --user enable "$SERVICE_NAME"
    systemctl --user start "$SERVICE_NAME"
    
    sleep 3
    
    if systemctl --user is-active "$SERVICE_NAME" &>/dev/null; then
        log_info "CIADPI service is running"
    else
        log_warn "Service may not be running"
        systemctl --user status "$SERVICE_NAME" --no-pager 2>&1 | tee -a "$INSTALL_LOG"
    fi
    
    # Step 15: Create diagnostic tools
    log_step "Step 15/15: Creating diagnostic tools"
    
    cat > "$HOME/.local/bin/ciadpi-diagnose" << 'EOF'
#!/bin/bash
# CIADPI Diagnostic Tool

echo "=== CIADPI Diagnostic Report ==="
echo "Date: $(date)"
echo "User: $USER"
echo "Desktop: $XDG_CURRENT_DESKTOP"
echo ""
echo "=== Service Status ==="
systemctl --user status ciadpi.service --no-pager
echo ""
echo "=== Byedpi Process ==="
ps aux | grep -E "(byedpi|ciadpi)" | grep -v grep
echo ""
echo "=== Proxy Configuration ==="
cat ~/.config/ciadpi/config.json 2>/dev/null || echo "No config found"
echo ""
echo "=== Byedpi Parameters ==="
cat ~/.config/ciadpi/byedpi_params.conf 2>/dev/null || echo "No params file"
echo ""
echo "=== Service Logs (last 20 lines) ==="
journalctl --user -u ciadpi.service -n 20 --no-pager
echo ""
echo "=== Installation Logs ==="
ls -la ~/.config/ciadpi/logs/ 2>/dev/null || echo "No logs found"
echo ""
echo "=== Network Check ==="
echo "Proxy configured: 127.0.0.1:1080"
echo "Testing connection..."
curl -s --proxy http://127.0.0.1:1080 --connect-timeout 2 https://httpbin.org/ip 2>/dev/null && echo "Proxy works!" || echo "Proxy not responding"
EOF
    
    chmod +x "$HOME/.local/bin/ciadpi-diagnose"
    log_info "Diagnostic tool created: ~/.local/bin/ciadpi-diagnose"
    
    # Final output
    echo ""
    echo -e "${GREEN}━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━${NC}"
    echo -e "${GREEN}✅ CIADPI INSTALLATION COMPLETE${NC}"
    echo -e "${GREEN}━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━${NC}"
    echo ""
    echo -e "${BOLD}📊 Installation Summary:${NC}"
    echo -e "  • Desktop Environment: $DESKTOP_ENV"
    echo -e "  • Service Status: $(systemctl --user is-active "$SERVICE_NAME" 2>/dev/null || echo 'unknown')"
    echo -e "  • Install Log: $INSTALL_LOG"
    echo -e "  • Backup Dir: $BACKUP_DIR"
    echo ""
    echo -e "${BOLD}📌 Quick Commands:${NC}"
    echo -e "  ${GREEN}▶ Start indicator:${NC}   python ~/.local/bin/ciadpi_advanced_tray.py"
    echo -e "  ${GREEN}▶ Service status:${NC}    systemctl --user status ciadpi.service"
    echo -e "  ${GREEN}▶ Stop service:${NC}       systemctl --user stop ciadpi.service"
    echo -e "  ${GREEN}▶ View logs:${NC}          journalctl --user -u ciadpi.service -f"
    echo -e "  ${GREEN}▶ Diagnostics:${NC}        ~/.local/bin/ciadpi-diagnose"
    echo ""
    echo -e "${BOLD}🔧 Proxy Configuration:${NC}"
    echo -e "  • Proxy address: ${GREEN}127.0.0.1:1080${NC}"
    echo -e "  • Leave HOST field ${GREEN}EMPTY${NC} in browser proxy settings"
    echo -e "  • For Firefox: Settings → Network → Manual proxy configuration"
    echo ""
    echo -e "${BOLD}🖥️  Desktop Environment Tips:${NC}"
    
    if [ "$DESKTOP_ENV" = "gnome" ]; then
        echo -e "  • Install AppIndicator extension for GNOME"
        echo -e "  • Extension: gnome-shell-extension-appindicator"
    elif [ "$DESKTOP_ENV" = "xfce" ]; then
        echo -e "  • Install: sudo pacman -S xfce4-indicator-plugin"
    fi
    
    echo ""
    echo -e "${YELLOW}⚠️  IMPORTANT: You need to log out and log back in for the tray icon to appear${NC}"
    echo -e "${GREEN}━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━${NC}"
    
    # Write to log that installation completed successfully
    log_info "Installation completed successfully"
}

# Run main function
main "$@"
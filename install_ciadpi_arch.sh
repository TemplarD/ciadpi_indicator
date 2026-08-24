#!/bin/bash

# CIADPI Complete Solution Installer for Arch Linux
# v2.1 - Совместим с трей-индикатором (системный сервис ciadpi.service + ~/byedpi/ciadpi)
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

# Logging functions
log_info() {
    echo -e "$(date '+%Y-%m-%d %H:%M:%S') ${GREEN}[INFO]${NC} $1" | tee -a "$INSTALL_LOG"
}

log_warn() {
    echo -e "$(date '+%Y-%m-%d %H:%M:%S') ${YELLOW}[WARN]${NC} $1" | tee -a "$INSTALL_LOG"
}

log_error() {
    echo -e "$(date '+%Y-%m-%d %H:%M:%S') ${RED}[ERROR]${NC} $1" | tee -a "$INSTALL_LOG"
    exit 1
}

log_step() {
    echo -e "\n${BLUE}━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━${NC}" | tee -a "$INSTALL_LOG"
    echo -e "${BLUE}▶ $1${NC}" | tee -a "$INSTALL_LOG"
    echo -e "${BLUE}━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━${NC}" | tee -a "$INSTALL_LOG"
}

# Error handler
on_error() {
    log_error "Installation failed at line $1 (exit code: $2). Run uninstall script to clean up."
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

# Create log directory (лог живёт в logs/, удаляется только по согласию деинсталлятора)
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
    
    # libappindicator-gtk3 даёт typelib AppIndicator3; на новых системах ayatana-вариант
    if python -c "
import gi
gi.require_version('Gtk', '3.0')
try:
    gi.require_version('AppIndicator3', '0.1')
except (ValueError, ImportError):
    gi.require_version('AyatanaAppIndicator3', '0.1')
" 2>/dev/null; then
        log_info "AppIndicator typelib OK"
    else
        log_warn "AppIndicator typelib недоступен"
        log_info "Устанавливаем libappindicator-gtk3..."
        install_package_if_needed "libappindicator-gtk3" || true
        # Повторная проверка после установки
        if python -c "
import gi
try:
    gi.require_version('AppIndicator3', '0.1')
except (ValueError, ImportError):
    gi.require_version('AyatanaAppIndicator3', '0.1')
" 2>/dev/null; then
            log_info "AppIndicator typelib OK (после установки)"
        else
            log_warn "Индикатор будет работать через Gtk.StatusIcon fallback"
        fi
    fi
    
    if [ "$DESKTOP_ENV" = "gnome" ]; then
        log_info "Для GNOME может понадобиться расширение AppIndicator"
    elif [ "$DESKTOP_ENV" = "kde" ]; then
        log_info "KDE Plasma имеет нативную поддержку AppIndicator"
    elif [ "$DESKTOP_ENV" = "xfce" ]; then
        is_package_installed "xfce4-indicator-plugin" || \
            log_info "Для трея в XFCE установите: sudo pacman -S xfce4-panel-appindicator или xfce4-indicator-plugin"
    fi
}

# Get current params from existing config (или default)
get_current_params() {
    local config_file="$HOME/.config/ciadpi/config.json"
    local default_params="-o1 -o25+s -T3 -At o--tlsrec 1+s"
    
    if [ -f "$config_file" ]; then
        python3 -c "
import json
try:
    with open('$config_file') as f:
        cfg = json.load(f)
    print(cfg.get('current_params') or cfg.get('params') or '$default_params')
except Exception:
    print('$default_params')
" 2>/dev/null || echo "$default_params"
    else
        echo "$default_params"
    fi
}

# Main installation
main() {
    # Step 1: Detect environment
    log_step "Step 1/12: System detection"
    
    DESKTOP_ENV=$(detect_desktop_environment)
    log_info "Desktop environment: $DESKTOP_ENV"
    log_info "User: $USER"
    log_info "Home: $HOME"
    log_info "Architecture: $(uname -m)"
    
    # Step 2: Create backup directory
    log_step "Step 2/12: Creating backup directory"
    
    BACKUP_DIR="$HOME/.config/ciadpi/backups/$(date +%Y%m%d_%H%M%S)"
    mkdir -p "$BACKUP_DIR"
    log_info "Backup directory: $BACKUP_DIR"
    
    # Step 3: Backup existing configurations
    log_step "Step 3/12: Backing up existing configurations"
    
    if [ -f "$HOME/.config/ciadpi/config.json" ]; then
        cp "$HOME/.config/ciadpi/config.json" "$BACKUP_DIR/config.json.backup"
        log_info "Backed up config.json"
    fi
    
    # Step 4: Install system dependencies
    log_step "Step 4/12: Installing system dependencies"
    
    DEPENDENCIES=(
        "git"
        "base-devel"
        "python"
        "python-gobject"
        "gtk3"
        "libappindicator-gtk3"
        "curl"
    )
    
    for dep in "${DEPENDENCIES[@]}"; do
        install_package_if_needed "$dep"
    done
    
    # Step 5: Create directory structure
    log_step "Step 5/12: Creating directory structure"
    
    mkdir -p "$HOME/.local/bin"
    mkdir -p "$HOME/.config/ciadpi/logs"
    mkdir -p "$HOME/.config/autostart"
    mkdir -p "$HOME/.local/share/applications"
    log_info "Directory structure created"
    
    # Step 6: Build byedpi -> ~/byedpi/ciadpi (как ожидает индикатор)
    log_step "Step 6/12: Building byedpi from source"
    
    cd "$HOME"
    if [ -d "$HOME/byedpi" ]; then
        log_info "byedpi directory exists, updating..."
        git -C "$HOME/byedpi" pull 2>&1 | tee -a "$INSTALL_LOG"
    else
        log_info "Cloning byedpi repository..."
        git clone https://github.com/hufrea/byedpi.git "$HOME/byedpi" 2>&1 | tee -a "$INSTALL_LOG"
    fi
    
    log_info "Compiling byedpi..."
    make -C "$HOME/byedpi" clean 2>/dev/null || true
    make -C "$HOME/byedpi" 2>&1 | tee -a "$INSTALL_LOG"
    
    if [ ! -x "$HOME/byedpi/ciadpi" ]; then
        log_error "Failed to build byedpi - ~/byedpi/ciadpi not found"
    fi
    log_info "byedpi built: $HOME/byedpi/ciadpi"
    
    # Step 7: Install indicator files
    log_step "Step 7/12: Installing CIADPI indicator files"
    
    INDICATOR_FILES=(
        "ciadpi_advanced_tray.py"
        "ciadpi_strategy_search.py"
        "ciadpi_autosearch.py"
        "ciadpi_param_generator.py"
        "ciadpi_whitelist.py"
        "ciadpi_launcher.sh"
        "diagnose_ciadpi.py"
    )
    
    # Локальные файлы если запущено из репозитория, иначе качаем с GitHub
    if [ -f "ciadpi_advanced_tray.py" ]; then
        log_info "Local installation detected"
        SRC_DIR="$(pwd)"
        for file in "${INDICATOR_FILES[@]}"; do
            if [ -f "$SRC_DIR/$file" ]; then
                cp "$SRC_DIR/$file" "$HOME/.local/bin/"
                chmod +x "$HOME/.local/bin/$file"
                log_info "Installed: $file"
            else
                log_warn "Missing in local dir: $file"
            fi
        done
    else
        log_info "Downloading from GitHub..."
        rm -rf /tmp/ciadpi_src
        git clone --depth 1 https://github.com/TemplarD/ciadpi_indicator.git /tmp/ciadpi_src 2>&1 | tee -a "$INSTALL_LOG"
        
        for file in "${INDICATOR_FILES[@]}"; do
            if [ -f "/tmp/ciadpi_src/$file" ]; then
                cp "/tmp/ciadpi_src/$file" "$HOME/.local/bin/"
                chmod +x "$HOME/.local/bin/$file"
                log_info "Installed: $file"
            else
                log_warn "Missing in repo: $file"
            fi
        done
        rm -rf /tmp/ciadpi_src
    fi
    
    # Step 8: Create systemd SYSTEM service (требование трей-индикатора)
    log_step "Step 8/12: Creating systemd service"
    
    CURRENT_PARAMS=$(get_current_params)
    sudo tee /etc/systemd/system/ciadpi.service > /dev/null << EOF
[Unit]
Description=CIADPI DPI Bypass Service
Documentation=https://github.com/TemplarD/ciadpi_indicator
After=network.target
Wants=network.target

[Service]
Type=simple
User=$USER
WorkingDirectory=$HOME/byedpi
ExecStart=$HOME/byedpi/ciadpi $CURRENT_PARAMS
Restart=on-failure
RestartSec=5
TimeoutStartSec=30

[Install]
WantedBy=multi-user.target
EOF
    
    log_info "Service file created: /etc/systemd/system/ciadpi.service"
    sudo systemctl daemon-reload
    
    # Step 9: Setup autostart
    log_step "Step 9/12: Setting up autostart"
    
    cat > "$HOME/.local/share/applications/ciadpi-indicator.desktop" << EOF
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
    
    cp "$HOME/.local/share/applications/ciadpi-indicator.desktop" "$HOME/.config/autostart/"
    log_info "Autostart entries created for $DESKTOP_ENV"
    
    # Step 10: Create configuration
    log_step "Step 10/12: Creating configuration files"
    
    # Не перезаписываем существующий конфиг пользователя
    if [ ! -f "$HOME/.config/ciadpi/config.json" ]; then
        cat > "$HOME/.config/ciadpi/config.json" << EOF
{
    "params": "$CURRENT_PARAMS",
    "current_params": "$CURRENT_PARAMS",
    "proxy_enabled": false,
    "proxy_mode": "manual",
    "proxy_host": "",
    "proxy_port": "1080",
    "auto_disable_proxy": true,
    "we_changed_proxy": false,
    "install_date": "$(date -Iseconds)",
    "installer_version": "2.1-arch"
}
EOF
        log_info "Configuration created with params: $CURRENT_PARAMS"
    else
        log_info "Existing config.json preserved"
        # Обновляем params в существующем конфиге если их нет
        python3 - << 'PYEOF'
import json
import os
cfg_path = os.path.expanduser('~/.config/ciadpi/config.json')
try:
    with open(cfg_path) as f:
        cfg = json.load(f)
    changed = False
    if not cfg.get('params'):
        cfg['params'] = cfg.get('current_params', '-o1 -o25+s -T3 -At o--tlsrec 1+s')
        changed = True
    if not cfg.get('current_params'):
        cfg['current_params'] = cfg['params']
        changed = True
    if changed:
        with open(cfg_path, 'w') as f:
            json.dump(cfg, f, indent=2, ensure_ascii=False)
        print('config updated')
except Exception as e:
    print(f'warn: {e}')
PYEOF
    fi
    
    # Step 11: Setup permissions + start service
    log_step "Step 11/12: Configuring permissions and starting service"
    
    local systemctl_bin
    systemctl_bin=$(command -v systemctl || echo "/usr/bin/systemctl")
    
    echo "$USER ALL=(ALL) NOPASSWD: ${systemctl_bin} start ciadpi.service, ${systemctl_bin} stop ciadpi.service, ${systemctl_bin} restart ciadpi.service, ${systemctl_bin} status ciadpi.service, ${systemctl_bin} enable ciadpi.service, ${systemctl_bin} disable ciadpi.service, ${systemctl_bin} daemon-reload" | sudo tee /etc/sudoers.d/ciadpi > /dev/null
    sudo chmod 440 /etc/sudoers.d/ciadpi
    sudo visudo -c -f /etc/sudoers.d/ciadpi &>/dev/null && log_info "sudoers OK (${systemctl_bin})" || {
        sudo rm -f /etc/sudoers.d/ciadpi
        log_warn "sudoers невалиден, удалён"
    }
    
    sudo systemctl enable ciadpi.service || log_warn "Failed to enable service"
    sudo systemctl start ciadpi.service || log_warn "Failed to start service"
    
    sleep 3
    if systemctl is-active --quiet ciadpi.service; then
        log_info "✓ CIADPI service is running"
    else
        log_warn "Service may not be running: systemctl status ciadpi.service"
    fi
    
    # Step 12: Check AppIndicator support
    log_step "Step 12/12: Checking AppIndicator support"
    check_appindicator_support
    
    # Diagnostic tool
    cat > "$HOME/.local/bin/ciadpi-diagnose" << 'EOF'
#!/bin/bash
# CIADPI Diagnostic Tool
echo "=== CIADPI Diagnostic Report ==="
echo "Date: $(date)"
echo "User: $USER"
echo ""
echo "=== Service Status ==="
systemctl status ciadpi.service --no-pager || true
echo ""
echo "=== Byedpi Process ==="
ps aux | grep -E "(byedpi|ciadpi)" | grep -v grep || true
echo ""
echo "=== Proxy Configuration ==="
cat ~/.config/ciadpi/config.json 2>/dev/null || echo "No config found"
echo ""
echo "=== Service Logs (last 20 lines) ==="
journalctl -u ciadpi.service -n 20 --no-pager || true
echo ""
echo "=== Network Check ==="
echo "Testing proxy 127.0.0.1:1080..."
curl -s --proxy http://127.0.0.1:1080 --connect-timeout 3 https://www.google.com/generate_204 >/dev/null 2>&1 && echo "Proxy works!" || echo "Proxy not responding"
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
    echo -e "  • Service Status: $(systemctl is-active ciadpi.service 2>/dev/null || echo 'unknown')"
    echo -e "  • Params: $CURRENT_PARAMS"
    echo -e "  • Install Log: $INSTALL_LOG"
    echo ""
    echo -e "${BOLD}📌 Quick Commands:${NC}"
    echo -e "  ${GREEN}▶ Start indicator:${NC}   ~/.local/bin/ciadpi_launcher.sh"
    echo -e "  ${GREEN}▶ Service status:${NC}    systemctl status ciadpi.service"
    echo -e "  ${GREEN}▶ View logs:${NC}         journalctl -u ciadpi.service -f"
    echo -e "  ${GREEN}▶ Diagnostics:${NC}       ~/.local/bin/ciadpi-diagnose"
    echo ""
    echo -e "${BOLD}🔧 Proxy Configuration:${NC}"
    echo -e "  • Proxy address: ${GREEN}127.0.0.1:1080${NC}"
    echo -e "  • Leave HOST field ${GREEN}EMPTY${NC} in browser proxy settings"
    echo ""
    echo -e "${YELLOW}⚠️  IMPORTANT: You need to log out and log back in for the tray icon to appear${NC}"
    echo -e "${GREEN}━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━${NC}"
    
    log_info "Installation completed successfully"
}

# Run main function
main "$@"

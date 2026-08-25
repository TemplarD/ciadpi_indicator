#!/bin/bash

# Complete CIADPI Installer v1.2.5
# Installs both byedpi and indicator with smart local/remote detection

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

# Detect Debian version and AppIndicator package availability
# Debian 13 (trixie) удалил gir1.2-appindicator3-0.1 — нужен ayatana-вариант
detect_appindicator_package() {
    local version_id=""
    if [ -f /etc/os-release ]; then
        # shellcheck disable=SC1091
        version_id=$(. /etc/os-release && echo "${VERSION_ID:-}")
    fi
    
    case "$version_id" in
        12|13|14|trixie|bookworm)
            echo "gir1.2-ayatanaappindicator3-0.1 libayatana-appindicator3-1"
            ;;
        *)
            # Старые выпуски и Ubuntu: классический пакет, с fallback на ayatana
            if apt-cache show gir1.2-appindicator3-0.1 &>/dev/null; then
                echo "gir1.2-appindicator3-0.1"
            else
                echo "gir1.2-ayatanaappindicator3-0.1 libayatana-appindicator3-1"
            fi
            ;;
    esac
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
    
    # Check if main.c exists
    if [ ! -f "main.c" ]; then
        error "main.c not found in byedpi repository"
    fi
    
    log "Building ciadpi binary..."
    # Используем Makefile если есть
    if [ -f "Makefile" ]; then
        make || error "Failed to build ciadpi with make"
    else
        # Резервный вариант - компилируем все C файлы
        gcc -O3 -o ciadpi *.c -lpthread || error "Failed to build ciadpi"
    fi
    
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
    
    # AppIndicator пакет зависит от версии дистрибутива (Debian 13+: ayatana)
    APPINDICATOR_PKGS=$(detect_appindicator_package)
    
    local required_pkgs=(python3 python3-gi python3-gi-cairo $APPINDICATOR_PKGS)
    
    for dep in "${required_pkgs[@]}"; do
        if ! dpkg -l | grep -q "^ii  $dep "; then
            missing_deps+=("$dep")
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
    
    # Проверяем что typelib AppIndicator реально доступен для Python
    if ! python3 -c "
import gi
gi.require_version('Gtk', '3.0')
try:
    gi.require_version('AppIndicator3', '0.1')
except (ValueError, ImportError):
    try:
        gi.require_version('AyatanaAppIndicator3', '0.1')
    except Exception:
        raise SystemExit(1)
" &>/dev/null; then
        warn "AppIndicator typelib недоступен — индикатор будет использовать Gtk.StatusIcon fallback"
    else
        log "AppIndicator typelib OK"
    fi
}

# Install dependencies
install_dependencies() {
    log "Installing dependencies..."
    sudo apt update || warn "Failed to update package list"
    
    sudo apt install -y "$@" || error "Failed to install dependencies: $*"
}

# Функция для получения текущих параметров
get_current_params() {
    local config_file="$HOME/.config/ciadpi/config.json"
    local default_params="-o1 -o25+s -T3 -At o--tlsrec 1+s"
    
    if [ -f "$config_file" ]; then
        local params_from_config=$(python3 -c "
import json
try:
    with open('$config_file', 'r') as f:
        config = json.load(f)
    print(config.get('current_params', '$default_params'))
except:
    print('$default_params')
")
        echo "$params_from_config"
    else
        echo "$default_params"
    fi
}

# Функция для создания service файла с нуля
create_service_file_from_scratch() {
    local byedpi_dir="$HOME/byedpi"
    local current_params=$(get_current_params)
    
    cat << EOF | sudo tee /etc/systemd/system/ciadpi.service > /dev/null
[Unit]
Description=CIADPI DPI Bypass Service
After=network.target
Wants=network.target

[Service]
Type=simple
User=$USER
WorkingDirectory=$byedpi_dir
ExecStart=$byedpi_dir/ciadpi $current_params
Restart=on-failure
RestartSec=5
TimeoutStartSec=30

[Install]
WantedBy=multi-user.target
EOF
}

# Функция для добавления ExecStart в существующий файл
add_dynamic_execstart() {
    local byedpi_dir="$HOME/byedpi"
    local current_params=$(get_current_params)
    
    # Добавляем/обновляем ExecStart в секции [Service]
    if grep -q "ExecStart=" /etc/systemd/system/ciadpi.service; then
        # Обновляем существующий ExecStart
        sudo sed -i "s|ExecStart=.*|ExecStart=$byedpi_dir/ciadpi $current_params|" /etc/systemd/system/ciadpi.service
    else
        # Добавляем ExecStart после [Service]
        sudo sed -i "/\[Service\]/a ExecStart=$byedpi_dir/ciadpi $current_params" /etc/systemd/system/ciadpi.service
    fi
    
    # Добавляем/обновляем User и WorkingDirectory
    if ! grep -q "User=" /etc/systemd/system/ciadpi.service; then
        sudo sed -i "/\[Service\]/a User=$USER" /etc/systemd/system/ciadpi.service
    fi
    if ! grep -q "WorkingDirectory=" /etc/systemd/system/ciadpi.service; then
        sudo sed -i "/\[Service\]/a WorkingDirectory=$byedpi_dir" /etc/systemd/system/ciadpi.service
    fi
}

# Install systemd service
install_service() {
    log "Installing systemd service..."
    
    local byedpi_dir="$HOME/byedpi"
    local service_file="ciadpi.service"
    
    # Умная логика: локальная vs удаленная установка
    if [ -f "$service_file" ]; then
        # ЛОКАЛЬНАЯ установка - используем локальный файл
        log "Local installation detected, using local service file"
        sudo cp "$service_file" /etc/systemd/system/ciadpi.service
        
        # Динамически добавляем ExecStart с правильными параметрами
        add_dynamic_execstart
        
    else
        # УДАЛЕННАЯ установка - создаем файл с нуля
        log "Remote installation detected, creating service file from scratch"
        create_service_file_from_scratch
    fi
    
    sudo systemctl daemon-reload || error "Failed to reload systemd"
    log "Systemd service installed"
}

# Install Python scripts
install_python_scripts() {
    log "Installing Python scripts..."
    
    mkdir -p "$HOME/.local/bin"
    
    # Умная логика: локальная vs удаленная установка
    if [ -f "ciadpi_advanced_tray.py" ]; then
        # ЛОКАЛЬНАЯ установка - файлы есть в текущей директории
        log "Local installation detected, copying local files..."
        
        cp "ciadpi_advanced_tray.py" "$HOME/.local/bin/"
        chmod +x "$HOME/.local/bin/ciadpi_advanced_tray.py"
        
        [ -f "ciadpi_launcher.sh" ] && cp "ciadpi_launcher.sh" "$HOME/.local/bin/" && chmod +x "$HOME/.local/bin/ciadpi_launcher.sh"
        [ -f "ciadpi_autosearch.py" ] && cp "ciadpi_autosearch.py" "$HOME/.local/bin/"
        [ -f "ciadpi_param_generator.py" ] && cp "ciadpi_param_generator.py" "$HOME/.local/bin/"
        [ -f "ciadpi_whitelist.py" ] && cp "ciadpi_whitelist.py" "$HOME/.local/bin/"
        [ -f "ciadpi_strategy_search.py" ] && cp "ciadpi_strategy_search.py" "$HOME/.local/bin/"
        [ -f "ciadpi_i18n.py" ] && cp "ciadpi_i18n.py" "$HOME/.local/bin/"          # Локализация RU/EN
        [ -f "ciadpi_params_spec.py" ] && cp "ciadpi_params_spec.py" "$HOME/.local/bin/"  # Конструктор параметров
        
    else
        # УДАЛЕННАЯ установка - скачиваем с GitHub
        log "Remote installation detected, downloading from GitHub..."
        
        BASE_URL="https://raw.githubusercontent.com/templard/ciadpi_indicator/master"
        
        wget -q -O "$HOME/.local/bin/ciadpi_advanced_tray.py" "$BASE_URL/ciadpi_advanced_tray.py"
        chmod +x "$HOME/.local/bin/ciadpi_advanced_tray.py"
        
        wget -q -O "$HOME/.local/bin/ciadpi_launcher.sh" "$BASE_URL/ciadpi_launcher.sh"
        chmod +x "$HOME/.local/bin/ciadpi_launcher.sh"
        
        wget -q -O "$HOME/.local/bin/ciadpi_autosearch.py" "$BASE_URL/ciadpi_autosearch.py" 2>/dev/null || warn "Autosearch script not available"
        wget -q -O "$HOME/.local/bin/ciadpi_param_generator.py" "$BASE_URL/ciadpi_param_generator.py" 2>/dev/null || warn "Param generator script not available"
        wget -q -O "$HOME/.local/bin/ciadpi_whitelist.py" "$BASE_URL/ciadpi_whitelist.py" 2>/dev/null || warn "Whitelist script not available"  # ДОБАВЛЕНО
        wget -q -O "$HOME/.local/bin/ciadpi_strategy_search.py" "$BASE_URL/ciadpi_strategy_search.py" 2>/dev/null || warn "Strategy search script not available"
        wget -q -O "$HOME/.local/bin/ciadpi_i18n.py" "$BASE_URL/ciadpi_i18n.py" 2>/dev/null || warn "i18n module not available"
        wget -q -O "$HOME/.local/bin/ciadpi_params_spec.py" "$BASE_URL/ciadpi_params_spec.py" 2>/dev/null || warn "Params spec module not available"
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

    # Create whitelist if not exists
    if [ ! -f "$config_dir/whitelist.json" ]; then
        cat << EOF > "$config_dir/whitelist.json"
{
    "enabled": false,
    "domains": [
        "localhost",
        "127.0.0.1", 
        "*.local",
        "192.168.1.1"
    ],
    "ips": [
        "192.168.1.0/24",
        "10.0.0.0/8"
    ],
    "bypass_proxy": true,
    "bypass_dpi": false,
    "description": "Белый список для исключения ресурсов из проксирования"
}
EOF
        log "Default whitelist created"
    fi    
}

# Setup permissions (одноразовый запрос пароля при установке)
setup_permissions() {
    log "Setting up permissions..."
    
    # Add user to systemd journal group for log access
    sudo usermod -a -G systemd-journal "$USER" || warn "Failed to add user to systemd-journal group"
    
    # Полная настройка беспарольного управления: sudoers + polkit
    # ciadpi_privileges.sh сам определяет путь systemctl и валидирует sudoers
    local priv_script=""
    if [ -f "ciadpi_privileges.sh" ]; then
        priv_script="$(pwd)/ciadpi_privileges.sh"
    elif [ -f "$HOME/.local/bin/ciadpi_privileges.sh" ]; then
        priv_script="$HOME/.local/bin/ciadpi_privileges.sh"
    else
        # Удалённая установка: скачиваем скрипт настройки
        wget -q -O /tmp/ciadpi_privileges.sh \
            "https://raw.githubusercontent.com/TemplarD/ciadpi_indicator/master/ciadpi_privileges.sh" \
            && priv_script="/tmp/ciadpi_privileges.sh"
    fi
    
    if [ -n "$priv_script" ] && [ -f "$priv_script" ]; then
        chmod +x "$priv_script" 2>/dev/null || true
        if sudo -E bash "$priv_script"; then
            log "Passwordless service management configured"
            return 0
        fi
        warn "ciadpi_privileges.sh failed, falling back to minimal sudoers rule"
    fi
    
    # Fallback: минимальное правило как раньше
    local systemctl_bin
    systemctl_bin=$(command -v systemctl || echo "/usr/bin/systemctl")
    
    echo "$USER ALL=(ALL) NOPASSWD: ${systemctl_bin} start ciadpi.service, ${systemctl_bin} stop ciadpi.service, ${systemctl_bin} restart ciadpi.service, ${systemctl_bin} status ciadpi.service, ${systemctl_bin} enable ciadpi.service, ${systemctl_bin} disable ciadpi.service, ${systemctl_bin} daemon-reload" | sudo tee /etc/sudoers.d/ciadpi > /dev/null
    sudo chmod 440 /etc/sudoers.d/ciadpi
    
    if ! sudo visudo -c -f /etc/sudoers.d/ciadpi &>/dev/null; then
        warn "sudoers файл невалиден — удаляем во избежание блокировки"
        sudo rm -f /etc/sudoers.d/ciadpi
    fi
    
    log "Permissions configured (fallback mode)"
}

# Install privileges script for later re-use by the indicator
install_privileges_script() {
    if [ -f "ciadpi_privileges.sh" ]; then
        cp "ciadpi_privileges.sh" "$HOME/.local/bin/"
        chmod +x "$HOME/.local/bin/ciadpi_privileges.sh"
        log "Privileges script installed to ~/.local/bin/"
    fi
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
    local context="remote"
    if [ -f "install_ciadpi_complete.sh" ]; then
        context="local"
    fi
    
    echo
    echo -e "${GREEN}╔══════════════════════════════════════════════════════════════╗${NC}"
    echo -e "${GREEN}║                Complete CIADPI Installation Done!            ║${NC}"
    echo -e "${GREEN}╚══════════════════════════════════════════════════════════════╝${NC}"
    echo
    echo -e "${BLUE}What was installed:${NC}"
    echo -e "  • ${GREEN}✓${NC} byedpi (cloned and compiled)"
    echo -e "  • ${GREEN}✓${NC} CIADPI binary"
    echo -e "  • ${GREEN}✓${NC} System tray indicator"
    echo -e "  • ${GREEN}✓${NC} Systemd service"
    echo -e "  • ${GREEN}✓${NC} Autostart configuration"
    echo
    
    if [ "$context" = "local" ]; then
        echo -e "${BLUE}Исходные файлы остались в:${NC}"
        echo -e "  $(pwd)"
        echo
        echo -e "${YELLOW}Для удаления запустите:${NC}"
        echo -e "  ./uninstall_ciadpi_complete.sh"
    else
        echo -e "${YELLOW}Для удаления:${NC}"
        echo -e "  wget -O uninstall_ciadpi.sh https://raw.githubusercontent.com/templard/ciadpi_indicator/master/uninstall_ciadpi_complete.sh"
        echo -e "  chmod +x uninstall_ciadpi.sh"
        echo -e "  ./uninstall_ciadpi.sh"
    fi
    
    echo
    echo -e "${BLUE}How to use:${NC}"
    echo -e "  ${YELLOW}System Tray:${NC} Look for network icon in system tray"
    echo -e "  ${YELLOW}Manual Start:${NC} ~/.local/bin/ciadpi_advanced_tray.py"
    echo -e "  ${YELLOW}Service Control:${NC} systemctl {start|stop|restart} ciadpi"
    echo
    echo -e "${GREEN}The indicator should appear in your system tray!${NC}"
    echo -e "${YELLOW}If it doesn't appear, log out and log back in or restart.${NC}"
    echo
}

# Main installation function
main() {
    echo -e "${GREEN}╔══════════════════════════════════════════════════════════════╗${NC}"
    echo -e "${GREEN}║                Complete CIADPI Installer                     ║${NC}"
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
    install_privileges_script
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
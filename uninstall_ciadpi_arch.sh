#!/bin/bash

# CIADPI Complete Uninstaller for Arch Linux
# v2.1 - Удаляет установку, сделанную install_ciadpi_arch.sh v2.1+
#        (системный сервис + ~/byedpi/ciadpi), а также следы старых версий.

set -u

RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m'
BOLD='\033[1m'

# Global variables
UNINSTALL_LOG=""
BACKUP_DIR=""

# Logging functions
log_info() {
    echo -e "$(date '+%Y-%m-%d %H:%M:%S') ${GREEN}[INFO]${NC} $1" | tee -a "$UNINSTALL_LOG"
}

log_warn() {
    echo -e "$(date '+%Y-%m-%d %H:%M:%S') ${YELLOW}[WARN]${NC} $1" | tee -a "$UNINSTALL_LOG"
}

log_error() {
    echo -e "$(date '+%Y-%m-%d %H:%M:%S') ${RED}[ERROR]${NC} $1" | tee -a "$UNINSTALL_LOG"
}

log_step() {
    echo -e "\n${YELLOW}━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━${NC}" | tee -a "$UNINSTALL_LOG"
    echo -e "${YELLOW}▶ $1${NC}" | tee -a "$UNINSTALL_LOG"
    echo -e "${YELLOW}━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━${NC}" | tee -a "$UNINSTALL_LOG"
}

# Check if running as root
if [ "$EUID" -eq 0 ]; then
    echo -e "${RED}Please do not run as root${NC}"
    exit 1
fi

# Лог живёт в /tmp — НЕ внутри ~/.config/ciadpi, который будем удалять.
mkdir -p /tmp/ciadpi_uninstall_logs
UNINSTALL_LOG="/tmp/ciadpi_uninstall_logs/uninstall_$(date +%Y%m%d_%H%M%S).log"

echo -e "${RED}━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━${NC}"
echo -e "${RED}    CIADPI Complete Uninstaller for Arch Linux${NC}"
echo -e "${RED}━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━${NC}"
echo ""
log_info "Uninstall log: $UNINSTALL_LOG"

# Confirmation
echo -e "${YELLOW}WARNING: This will completely remove CIADPI and all configurations.${NC}"
read -r -p "Are you sure you want to continue? (y/N): " REPLY
echo ""
if [[ ! $REPLY =~ ^[Yy]$ ]]; then
    log_info "Uninstall cancelled by user"
    exit 0
fi

# Backup of config is created OUTSIDE ~/.config/ciadpi so it survives the cleanup
BACKUP_DIR="$HOME/.config/ciadpi_backup_pre_uninstall_$(date +%Y%m%d_%H%M%S)"
if [ -d "$HOME/.config/ciadpi" ]; then
    mkdir -p "$BACKUP_DIR"
    cp -r "$HOME/.config/ciadpi/." "$BACKUP_DIR/" 2>/dev/null || true
    log_info "Configuration backed up to: $BACKUP_DIR"
fi

# Step 1: Stop all processes (осторожно: не убиваем сами себя через совпадение подстроки)
log_step "Step 1/8: Stopping CIADPI processes"

pkill -f "ciadpi_advanced_tray.py" 2>/dev/null && log_info "✓ indicator stopped" || log_info "indicator not running"
pkill -f "byedpi/ciadpi" 2>/dev/null && log_info "✓ byedpi/ciadpi stopped" || log_info "ciadpi binary not running"

# Step 2: Stop and disable SYSTEMD service (system-level, как в v2.1)
log_step "Step 2/8: Stopping systemd service"

if systemctl is-active --quiet ciadpi.service 2>/dev/null; then
    sudo systemctl stop ciadpi.service && log_info "✓ Service stopped"
else
    log_info "System service not active"
fi

if systemctl is-enabled --quiet ciadpi.service 2>/dev/null; then
    sudo systemctl disable ciadpi.service && log_info "✓ Service disabled"
else
    log_info "System service not enabled"
fi

# Также чистим user-сервис от старых версий (<2.1)
if systemctl --user is-active --quiet ciadpi.service 2>/dev/null; then
    systemctl --user stop ciadpi.service && log_info "✓ Legacy user service stopped"
fi
if [ -f "$HOME/.config/systemd/user/ciadpi.service" ]; then
    systemctl --user disable ciadpi.service 2>/dev/null || true
    rm -f "$HOME/.config/systemd/user/ciadpi.service"
    systemctl --user daemon-reload 2>/dev/null || true
    log_info "✓ Legacy user service file removed"
fi

# Step 3: Remove system files
log_step "Step 3/8: Removing system files"

sudo rm -f /etc/systemd/system/ciadpi.service && log_info "✓ System service file removed"
sudo rm -rf /etc/systemd/system/ciadpi.service.d 2>/dev/null || true
sudo rm -f /etc/sudoers.d/ciadpi && log_info "✓ sudoers rules removed"
sudo systemctl daemon-reload && log_info "✓ systemd reloaded"

# Step 4: Remove autostart entries
log_step "Step 4/8: Removing autostart entries"

rm -f "$HOME/.config/autostart/ciadpi-indicator.desktop"
rm -f "$HOME/.local/share/applications/ciadpi-indicator.desktop"
log_info "✓ Autostart and desktop entries removed"

# Step 5: Remove binaries and scripts
log_step "Step 5/8: Removing binaries and scripts"

find "$HOME/.local/bin" -maxdepth 1 \( -name "*ciadpi*" -o -name "byedpi" \) -type f -delete 2>/dev/null || true
log_info "✓ Scripts and binaries removed from ~/.local/bin/"

# Step 6: Remove configuration (with confirmation)
log_step "Step 6/8: Removing configuration files"

if [ -d "$HOME/.config/ciadpi" ]; then
    read -r -p "Remove ALL configuration including history/logs? (y/N): " REPLY_CFG
    echo ""
    if [[ $REPLY_CFG =~ ^[Yy]$ ]]; then
        rm -rf "$HOME/.config/ciadpi"
        log_info "✓ Configuration directory removed"
    else
        # Удаляем всё кроме backups и logs
        find "$HOME/.config/ciadpi" -maxdepth 1 ! -name "ciadpi" ! -name "backups" ! -name "logs" -exec rm -rf {} + 2>/dev/null || true
        log_info "Configuration cleaned, backups/logs preserved in ~/.config/ciadpi/"
    fi
else
    log_info "Configuration directory not found"
fi

# Step 7: Remove byedpi source (with confirmation)
log_step "Step 7/8: Removing byedpi source"

if [ -d "$HOME/byedpi" ]; then
    read -r -p "Remove byedpi source from ~/byedpi? (y/N): " REPLY_BPD
    echo ""
    if [[ $REPLY_BPD =~ ^[Yy]$ ]]; then
        rm -rf "$HOME/byedpi"
        log_info "✓ byedpi source removed"
    else
        log_info "byedpi source kept at ~/byedpi"
    fi
else
    log_info "byedpi source not found"
fi

# Step 8: Final cleanup
log_step "Step 8/8: Final cleanup"

# Optional system package removal
read -r -p "Remove helper packages installed by CIADPI (libappindicator-gtk3 и др.)? (y/N): " REPLY_PKGS
echo ""
if [[ $REPLY_PKGS =~ ^[Yy]$ ]]; then
    log_info "Removing packages..."
    sudo pacman -Rs --noconfirm libappindicator-gtk3 2>/dev/null && \
        log_info "✓ Packages removed" || \
        log_warn "Some packages could not be removed (may be required by other software)"
fi

# Update desktop database
command -v update-desktop-database &>/dev/null && \
    update-desktop-database "$HOME/.local/share/applications/" 2>/dev/null || true

# Final output
echo ""
echo -e "${GREEN}━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━${NC}"
echo -e "${GREEN}✅ CIADPI UNINSTALL COMPLETE${NC}"
echo -e "${GREEN}━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━${NC}"
echo ""
echo -e "${BOLD}📊 Uninstall Summary:${NC}"
echo -e "  • Config backup: $BACKUP_DIR (kept safe outside ciadpi dir)"
echo -e "  • Uninstall log: $UNINSTALL_LOG"
echo ""
echo -e "${BOLD}📌 Next Steps:${NC}"
echo -e "  • Restart your desktop session for complete cleanup"
echo -e "  • To reinstall: ./install_ciadpi_arch.sh"
echo -e "  • To restore config backup:"
echo -e "      mkdir -p ~/.config/ciadpi && cp -r $BACKUP_DIR/* ~/.config/ciadpi/"
echo ""
echo -e "${GREEN}━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━${NC}"

log_info "Uninstall completed successfully"

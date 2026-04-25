#!/bin/bash

# CIADPI Complete Uninstaller for Arch Linux
# Full featured version - equivalent to original Ubuntu uninstaller

set -e

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

# Create log directory
mkdir -p "$HOME/.config/ciadpi/logs"
UNINSTALL_LOG="$HOME/.config/ciadpi/logs/uninstall_$(date +%Y%m%d_%H%M%S).log"

echo -e "${RED}━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━${NC}"
echo -e "${RED}    CIADPI Complete Uninstaller for Arch Linux${NC}"
echo -e "${RED}━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━${NC}"
echo ""
log_info "Uninstall log: $UNINSTALL_LOG"

# Confirmation
echo -e "${YELLOW}WARNING: This will completely remove CIADPI and all configurations.${NC}"
read -p "Are you sure you want to continue? (y/N): " -n 1 -r
echo ""
if [[ ! $REPLY =~ ^[Yy]$ ]]; then
    log_info "Uninstall cancelled by user"
    exit 0
fi

# Create backup of current config before removal
BACKUP_DIR="$HOME/.config/ciadpi/backups/pre_uninstall_$(date +%Y%m%d_%H%M%S)"
mkdir -p "$BACKUP_DIR"
log_info "Creating backup before uninstall: $BACKUP_DIR"

if [ -d "$HOME/.config/ciadpi" ]; then
    cp -r "$HOME/.config/ciadpi" "$BACKUP_DIR/" 2>/dev/null || true
    log_info "Configuration backed up"
fi

# Step 1: Stop all processes
log_step "Step 1/10: Stopping CIADPI processes"

log_info "Stopping byedpi process..."
pkill -f "byedpi" 2>/dev/null && log_info "✓ byedpi stopped" || log_info "byedpi not running"

log_info "Stopping indicator..."
pkill -f "ciadpi_advanced_tray" 2>/dev/null && log_info "✓ indicator stopped" || log_info "indicator not running"

log_info "Stopping launcher..."
pkill -f "ciadpi_launcher" 2>/dev/null && log_info "✓ launcher stopped" || log_info "launcher not running"

# Step 2: Stop and disable systemd service
log_step "Step 2/10: Stopping systemd service"

if systemctl --user is-active ciadpi.service &>/dev/null; then
    systemctl --user stop ciadpi.service
    log_info "✓ Service stopped"
else
    log_info "Service not active"
fi

if systemctl --user is-enabled ciadpi.service &>/dev/null; then
    systemctl --user disable ciadpi.service
    log_info "✓ Service disabled"
else
    log_info "Service not enabled"
fi

# Step 3: Remove systemd service file
log_step "Step 3/10: Removing systemd service"

SERVICE_FILE="$HOME/.config/systemd/user/ciadpi.service"
if [ -f "$SERVICE_FILE" ]; then
    rm -f "$SERVICE_FILE"
    log_info "✓ Service file removed"
else
    log_info "Service file not found"
fi

# Step 4: Remove autostart entries
log_step "Step 4/10: Removing autostart entries"

AUTOSTART_FILES=(
    "$HOME/.config/autostart/ciadpi-indicator.desktop"
    "$HOME/.local/share/applications/ciadpi-indicator.desktop"
    "$HOME/.config/autostart/ciadpi*.desktop"
)

for file in "${AUTOSTART_FILES[@]}"; do
    if ls $file 2>/dev/null; then
        rm -f $file
        log_info "✓ Removed: $file"
    fi
done

# Step 5: Remove binaries and scripts
log_step "Step 5/10: Removing binaries and scripts"

BINARIES=(
    "$HOME/.local/bin/ciadpi_advanced_tray.py"
    "$HOME/.local/bin/ciadpi_autosearch.py"
    "$HOME/.local/bin/ciadpi_param_generator.py"
    "$HOME/.local/bin/ciadpi_whitelist.py"
    "$HOME/.local/bin/ciadpi_launcher.sh"
    "$HOME/.local/bin/diagnose_ciadpi.py"
    "$HOME/.local/bin/ciadpi-diagnose"
    "$HOME/.local/bin/byedpi"
    "$HOME/.local/bin/ciadpi"
)

for bin in "${BINARIES[@]}"; do
    if [ -f "$bin" ]; then
        rm -f "$bin"
        log_info "✓ Removed: $(basename $bin)"
    fi
done

# Also remove any other ciadpi related files
find "$HOME/.local/bin" -name "*ciadpi*" -type f -delete 2>/dev/null || true

# Step 6: Remove configuration files
log_step "Step 6/10: Removing configuration files"

if [ -d "$HOME/.config/ciadpi" ]; then
    rm -rf "$HOME/.config/ciadpi"
    log_info "✓ Configuration directory removed"
else
    log_info "Configuration directory not found"
fi

# Step 7: Remove byedpi source
log_step "Step 7/10: Removing byedpi source"

if [ -d "$HOME/byedpi" ]; then
    rm -rf "$HOME/byedpi"
    log_info "✓ byedpi source removed"
else
    log_info "byedpi source not found"
fi

# Step 8: Remove Python packages (optional)
log_step "Step 8/10: Python package cleanup"

read -p "Remove Python 'requests' package? (y/N): " -n 1 -r
echo ""
if [[ $REPLY =~ ^[Yy]$ ]]; then
    log_info "Removing requests..."
    pip uninstall --user --break-system-packages requests -y 2>/dev/null && \
        log_info "✓ requests removed" || \
        log_warn "Could not remove requests (may not be installed)"
fi

# Step 9: Remove system packages (optional)
log_step "Step 9/10: System package cleanup"

echo -e "${YELLOW}The following packages were installed by CIADPI:${NC}"
echo "  • git"
echo "  • base-devel"
echo "  • python-pip"
echo "  • python-gobject"
echo "  • gtk3"
echo "  • libappindicator-gtk3"
echo "  • net-tools"
echo "  • python-pipx"
echo ""
read -p "Remove these system packages? (y/N): " -n 1 -r
echo ""

if [[ $REPLY =~ ^[Yy]$ ]]; then
    log_info "Removing system packages..."
    sudo pacman -Rs --noconfirm git base-devel python-pip python-gobject gtk3 libappindicator-gtk3 net-tools python-pipx 2>/dev/null && \
        log_info "✓ System packages removed" || \
        log_warn "Some packages could not be removed (may be required by other software)"
fi

# Step 10: Clean up and finalize
log_step "Step 10/10: Final cleanup"

# Reload systemd
systemctl --user daemon-reload
log_info "✓ Systemd reloaded"

# Update desktop database
if command -v update-desktop-database &>/dev/null; then
    update-desktop-database "$HOME/.local/share/applications/" 2>/dev/null || true
    log_info "✓ Desktop database updated"
fi

# Remove empty directories
rmdir "$HOME/.config/systemd/user" 2>/dev/null || true
rmdir "$HOME/.config/autostart" 2>/dev/null || true
rmdir "$HOME/.config" 2>/dev/null || true

# List backup location
if [ -d "$BACKUP_DIR" ]; then
    log_info "Backup saved at: $BACKUP_DIR"
fi

# Final output
echo ""
echo -e "${GREEN}━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━${NC}"
echo -e "${GREEN}✅ CIADPI UNINSTALL COMPLETE${NC}"
echo -e "${GREEN}━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━${NC}"
echo ""
echo -e "${BOLD}📊 Uninstall Summary:${NC}"
echo -e "  • Backup created: $BACKUP_DIR"
echo -e "  • Uninstall log: $UNINSTALL_LOG"
echo ""
echo -e "${BOLD}📌 Next Steps:${NC}"
echo -e "  • Restart your desktop session for complete cleanup"
echo -e "  • To reinstall: ./install_ciadpi_arch.sh"
echo -e "  • To restore backup: cp -r $BACKUP_DIR/* ~/.config/"
echo ""
echo -e "${YELLOW}To restore from backup:${NC}"
echo -e "  cp -r $BACKUP_DIR/ciadpi ~/.config/"
echo ""
echo -e "${GREEN}━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━${NC}"

log_info "Uninstall completed successfully"
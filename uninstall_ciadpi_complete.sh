#!/bin/bash

# Complete CIADPI Uninstaller v1.1.0
# Удаляет только УСТАНОВЛЕННЫЕ копии, не трогает исходные файлы
# Работает как локально так и удаленно

set -e

RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m'

LOG_FILE="/tmp/ciadpi_uninstall.log"
echo "CIADPI Uninstallation started at $(date)" > "$LOG_FILE"

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

# Проверяем контекст - локальный или удаленный запуск
check_context() {
    if [ -f "uninstall_ciadpi_complete.sh" ]; then
        echo "local"
    else
        echo "remote"
    fi
}

# Получаем информацию для удаленного режима
get_remote_info() {
    log "Получаем информацию об установке..."
    
    # Проверяем что установлено
    local installed_files=()
    
    [ -f "$HOME/.local/bin/ciadpi_advanced_tray.py" ] && installed_files+=("indicator")
    [ -f "/etc/systemd/system/ciadpi.service" ] && installed_files+=("service")
    [ -d "$HOME/byedpi" ] && installed_files+=("byedpi")
    [ -d "$HOME/.config/ciadpi" ] && installed_files+=("config")
    
    if [ ${#installed_files[@]} -eq 0 ]; then
        error "CIADPI не установлен или уже удален"
    fi
    
    echo "Установленные компоненты: ${installed_files[*]}"
}

confirm_uninstall() {
    echo -e "${YELLOW}╔══════════════════════════════════════════════════════════════╗${NC}"
    echo -e "${YELLOW}║                  Complete CIADPI Uninstaller                 ║${NC}"
    echo -e "${YELLOW}╚══════════════════════════════════════════════════════════════╝${NC}"
    echo
    echo -e "${YELLOW}Внимание: Этот скрипт удалит CIADPI с вашей системы${NC}"
    echo -e "${YELLOW}Удаляются только установленные файлы, исходные остаются${NC}"
    echo
    
    local context=$(check_context)
    if [ "$context" = "remote" ]; then
        get_remote_info
    fi
    
    echo -e "${RED}Будут удалены:${NC}"
    echo -e "  • Системный сервис ciadpi.service"
    echo -e "  • Индикатор в системном трее"
    echo -e "  • Файлы автозагрузки"
    echo -e "  • Права sudo для управления сервисом"
    echo
    
    read -p "Продолжить удаление? (y/N): " -n 1 -r
    echo
    if [[ ! $REPLY =~ ^[Yy]$ ]]; then
        echo "Удаление отменено."
        exit 0
    fi
}

stop_services() {
    log "Останавливаем сервисы..."
    
    # Останавливаем индикатор если запущен
    pkill -f "ciadpi_advanced_tray.py" 2>/dev/null && log "Индикатор остановлен" || warn "Индикатор не запущен"
    
    # Останавливаем systemd сервис
    if systemctl is-active --quiet ciadpi.service 2>/dev/null; then
        sudo systemctl stop ciadpi.service || warn "Не удалось остановить сервис"
        log "Сервис остановлен"
    fi
    
    sudo systemctl disable ciadpi.service 2>/dev/null || warn "Не удалось отключить сервис"
    sudo systemctl reset-failed ciadpi.service 2>/dev/null || true
}

remove_system_files() {
    log "Удаляем системные файлы..."
    
    # Удаляем systemd сервис и override директорию
    sudo rm -f /etc/systemd/system/ciadpi.service
    sudo rm -rf /etc/systemd/system/ciadpi.service.d 2>/dev/null
    
    # Удаляем права sudo
    sudo rm -f /etc/sudoers.d/ciadpi
    
    # Перезагружаем systemd
    sudo systemctl daemon-reload
    sudo systemctl reset-failed 2>/dev/null || true
    
    log "Системные файлы удалены"
}

remove_user_files() {
    log "Удаляем пользовательские файлы..."
    
    # Удаляем скрипты из ~/.local/bin/
    local scripts=(
        "ciadpi_advanced_tray.py"
        "ciadpi_launcher.sh" 
        "ciadpi_autosearch.py"
        "ciadpi_param_generator.py"
    )
    
    for script in "${scripts[@]}"; do
        if [ -f "$HOME/.local/bin/$script" ]; then
            rm -f "$HOME/.local/bin/$script"
            log "Удален: $script"
        fi
    done
    
    # Удаляем desktop файлы
    rm -f "$HOME/.local/share/applications/ciadpi-indicator.desktop"
    rm -f "$HOME/.config/autostart/ciadpi-indicator.desktop"
    
    log "Пользовательские файлы удалены"
}

cleanup_optional() {
    echo
    echo -e "${YELLOW}Дополнительная очистка:${NC}"
    
    # byedpi
    if [ -d "$HOME/byedpi" ]; then
        read -p "Удалить byedpi из ~/byedpi/? (y/N): " -n 1 -r
        echo
        if [[ $REPLY =~ ^[Yy]$ ]]; then
            rm -rf "$HOME/byedpi"
            log "byedpi удален"
        else
            log "byedpi оставлен в ~/byedpi/"
        fi
    fi
    
    # Конфиги
    if [ -d "$HOME/.config/ciadpi" ]; then
        read -p "Удалить конфигурацию из ~/.config/ciadpi/? (y/N): " -n 1 -r
        echo
        if [[ $REPLY =~ ^[Yy]$ ]]; then
            rm -rf "$HOME/.config/ciadpi"
            log "Конфигурация удалена"
        else
            log "Конфигурация оставлена в ~/.config/ciadpi/"
        fi
    fi
    
    # Логи
    if [ -d "$HOME/.config/ciadpi/logs" ]; then
        read -p "Удалить логи из ~/.config/ciadpi/logs/? (y/N): " -n 1 -r
        echo
        if [[ $REPLY =~ ^[Yy]$ ]]; then
            rm -rf "$HOME/.config/ciadpi/logs"
            log "Логи удалены"
        fi
    fi
}

post_uninstall_info() {
    local context=$(check_context)
    
    echo
    echo -e "${GREEN}╔══════════════════════════════════════════════════════════════╗${NC}"
    echo -e "${GREEN}║                     Удаление завершено!                      ║${NC}"
    echo -e "${GREEN}╚══════════════════════════════════════════════════════════════╝${NC}"
    echo
    
    if [ "$context" = "local" ]; then
        echo -e "${BLUE}Исходные файлы остались в текущей директории:${NC}"
        echo -e "  $(pwd)"
        echo
        echo -e "${YELLOW}Для повторной установки запустите:${NC}"
        echo -e "  ./install_ciadpi_complete.sh"
    else
        echo -e "${YELLOW}Для повторной установки:${NC}"
        echo -e "  wget -O install_ciadpi.sh https://raw.githubusercontent.com/templard/ciadpi_indicator/master/install_ciadpi_complete.sh"
        echo -e "  chmod +x install_ciadpi.sh"
        echo -e "  ./install_ciadpi.sh"
    fi
    
    echo
    echo -e "${BLUE}Рекомендации:${NC}"
    echo -e "  • Перезапустите систему для полной очистки"
    echo -e "  • Проверьте что в системном трее нет значка CIADPI"
    echo
}

main() {
    confirm_uninstall
    
    stop_services
    remove_system_files
    remove_user_files
    cleanup_optional
    post_uninstall_info
    
    log "Uninstallation completed successfully"
}

# Проверяем что не запущены как root
if [ "$EUID" -eq 0 ]; then
    error "Please do not run as root. The script will use sudo when needed."
fi

main "$@"
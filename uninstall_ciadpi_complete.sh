#!/bin/bash

# Complete CIADPI Uninstaller
# Удаляет только УСТАНОВЛЕННЫЕ копии, не трогает исходные файлы

set -e

RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m'

log() {
    echo -e "${GREEN}[INFO]${NC} $1"
}

confirm_uninstall() {
    echo -e "${YELLOW}Внимание: Этот скрипт удалит CIADPI с вашей системы${NC}"
    echo -e "${YELLOW}Удаляются только установленные файлы, исходные остаются${NC}"
    read -p "Продолжить удаление? (y/N): " -n 1 -r
    echo
    if [[ ! $REPLY =~ ^[Yy]$ ]]; then
        echo "Удаление отменено."
        exit 0
    fi
}

main() {
    echo -e "${RED}╔══════════════════════════════════════════════════════════════╗${NC}"
    echo -e "${RED}║                  Complete CIADPI Uninstaller                 ║${NC}"
    echo -e "${RED}╚══════════════════════════════════════════════════════════════╝${NC}"
    
    confirm_uninstall
    
    log "Останавливаем сервисы..."
    sudo systemctl stop ciadpi.service || true
    sudo systemctl disable ciadpi.service || true
    
    log "Удаляем системные файлы..."
    sudo rm -f /etc/systemd/system/ciadpi.service
    sudo rm -f /etc/sudoers.d/ciadpi
    sudo systemctl daemon-reload
    
    log "Удаляем пользовательские файлы..."
    # Удаляем только УСТАНОВЛЕННЫЕ копии из ~/.local/bin/
    rm -f "$HOME/.local/bin/ciadpi_advanced_tray.py"
    rm -f "$HOME/.local/bin/ciadpi_launcher.sh"
    rm -f "$HOME/.local/bin/ciadpi_autosearch.py"
    rm -f "$HOME/.local/bin/ciadpi_param_generator.py"
    
    # Удаляем desktop файлы
    rm -f "$HOME/.local/share/applications/ciadpi-indicator.desktop"
    rm -f "$HOME/.config/autostart/ciadpi-indicator.desktop"
    
    echo
    echo -e "${YELLOW}Что вы хотите удалить?${NC}"
    echo "1) Удалить только конфигурацию (оставить byedpi)"
    echo "2) Удалить конфигурацию и byedpi (полное удаление)"
    read -p "Выберите опцию (1/2): " -n 1 -r
    echo
    
    if [[ $REPLY =~ ^[2]$ ]]; then
        log "Удаляем byedpi..."
        rm -rf "$HOME/byedpi"
        log "byedpi удален"
    else
        log "byedpi оставлен в ~/byedpi/"
    fi
    
    read -p "Удалить файлы конфигурации в ~/.config/ciadpi? (y/N): " -n 1 -r
    echo
    if [[ $REPLY =~ ^[Yy]$ ]]; then
        rm -rf "$HOME/.config/ciadpi"
        log "Конфигурация удалена"
    else
        log "Конфигурация оставлена в ~/.config/ciadpi/"
    fi
    
    echo
    echo -e "${GREEN}Удаление завершено!${NC}"
    echo
    echo -e "${BLUE}Исходные файлы установки остались в текущей директории:${NC}"
    echo -e "  $(pwd)"
    echo
    echo -e "${YELLOW}Для повторной установки запустите:${NC}"
    echo -e "  ./install_ciadpi_complete.sh"
    echo
}

main "$@"
#!/bin/bash

# CIADPI Indicator Launcher
# Запускает системный трей индикатор с правильными переменными окружения

set -e

# Устанавливаем переменные окружения для GUI
export DISPLAY=${DISPLAY:-:0}
export XAUTHORITY=${XAUTHORITY:-$HOME/.Xauthority}
export DBUS_SESSION_BUS_ADDRESS=${DBUS_SESSION_BUS_ADDRESS:-unix:path=/run/user/$(id -u)/bus}

# Логирование
LOG_DIR="$HOME/.config/ciadpi/logs"
mkdir -p "$LOG_DIR"
LAUNCH_LOG="$LOG_DIR/launcher.log"

log() {
    echo "[$(date '+%Y-%m-%d %H:%M:%S')] $1" >> "$LAUNCH_LOG"
}

# Проверяем наличие индикатора
INDICATOR_SCRIPT="$HOME/.local/bin/ciadpi_advanced_tray.py"

if [ ! -f "$INDICATOR_SCRIPT" ]; then
    log "ERROR: Indicator script not found: $INDICATOR_SCRIPT"
    exit 1
fi

# Проверяем права выполнения
if [ ! -x "$INDICATOR_SCRIPT" ]; then
    log "WARNING: Indicator script not executable, fixing..."
    chmod +x "$INDICATOR_SCRIPT"
fi

# Проверяем, не запущен ли уже индикатор
if pgrep -f "ciadpi_advanced_tray.py" > /dev/null; then
    log "INFO: Indicator already running, exiting"
    exit 0
fi

# Ждем загрузки рабочего стола
sleep 5

log "Starting CIADPI indicator..."

# Запускаем индикатор
exec python3 "$INDICATOR_SCRIPT" >> "$LOG_DIR/indicator.log" 2>&1

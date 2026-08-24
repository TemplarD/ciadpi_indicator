#!/bin/bash
# Одноразовая настройка беспарольного управления CIADPI.
# Вызывается установщиком автоматически (пароль спрашивается ТОЛЬКО здесь,
# один раз при установке) или вручную/из индикатора:
#   pkexec env CIADPI_USER="$USER" bash ~/.local/bin/ciadpi_privileges.sh
# Пользователя можно передать аргументом: ciadpi_privileges.sh <username>
set -e

TARGET_USER="${1:-${CIADPI_USER:-${SUDO_USER:-$USER}}}"

# При запуске через pkexec $USER = root; берём реального владельца процесса
# индикатора, если пользователь не указан явно
if [ "$TARGET_USER" = "root" ]; then
    # Кто запустил pkexec (реальный юзер за терминалом/сессией)
    for candidate in $(ls /run/user/ 2>/dev/null | grep -E '^[0-9]+$'); do
        [ "$candidate" = "0" ] && continue
        TARGET_USER=$(id -un "$candidate" 2>/dev/null) && break
    done
fi

if [ -z "$TARGET_USER" ] || [ "$TARGET_USER" = "root" ]; then
    echo "ОШИБКА: не удалось определить целевого пользователя." >&2
    echo "Запустите: pkexec env CIADPI_USER=<имя> bash $0" >&2
    exit 1
fi

echo "==> Настройка беспарольного управления CIADPI для: $TARGET_USER"

SYSTEMCTL_BIN="$(command -v systemctl || echo /usr/bin/systemctl)"

# --- 1) sudoers: все команды, которые использует трей-индикатор ---
SUDOERS_FILE=/etc/sudoers.d/ciadpi

cat > "$SUDOERS_FILE" <<EOF
${TARGET_USER} ALL=(root) NOPASSWD: ${SYSTEMCTL_BIN} start ciadpi.service, ${SYSTEMCTL_BIN} stop ciadpi.service, ${SYSTEMCTL_BIN} restart ciadpi.service, ${SYSTEMCTL_BIN} status ciadpi.service, ${SYSTEMCTL_BIN} show ciadpi.service, ${SYSTEMCTL_BIN} is-active ciadpi.service, ${SYSTEMCTL_BIN} enable ciadpi.service, ${SYSTEMCTL_BIN} disable ciadpi.service, ${SYSTEMCTL_BIN} daemon-reload
${TARGET_USER} ALL=(root) NOPASSWD: /usr/bin/tee /etc/systemd/system/ciadpi.service
${TARGET_USER} ALL=(root) NOPASSWD: /usr/bin/rm -rf /etc/systemd/system/ciadpi.service.d
EOF

# Дублируем для старого пути /bin/systemctl (старые дистрибутивы)
if [ -x /bin/systemctl ] && [ "$(readlink -f /bin/systemctl)" != "$(readlink -f "$SYSTEMCTL_BIN")" ]; then
cat >> "$SUDOERS_FILE" <<EOF
${TARGET_USER} ALL=(root) NOPASSWD: /bin/systemctl start ciadpi.service, /bin/systemctl stop ciadpi.service, /bin/systemctl restart ciadpi.service, /bin/systemctl status ciadpi.service, /bin/systemctl is-active ciadpi.service, /bin/systemctl show ciadpi.service, /bin/systemctl enable ciadpi.service, /bin/systemctl disable ciadpi.service, /bin/systemctl daemon-reload
EOF
fi

chmod 440 "$SUDOERS_FILE"

if visudo -c -f "$SUDOERS_FILE" >/dev/null 2>&1; then
    echo "✅ sudoers OK: $SUDOERS_FILE"
else
    echo "❌ sudoers невалиден — выполняю откат" >&2
    rm -f "$SUDOERS_FILE"
    exit 1
fi

# --- 2) polkit-правило: прямые вызовы systemctl без пароля (только ciadpi.service) ---
POLKIT_RULES_DIR=""
for d in /etc/polkit-1/rules.d /usr/share/polkit-1/rules.d; do
    if [ -d "$d" ]; then POLKIT_RULES_DIR="$d"; break; fi
done

if [ -n "$POLKIT_RULES_DIR" ]; then
cat > "$POLKIT_RULES_DIR/49-ciadpi-indicator.rules" <<EOF
// Allow ${TARGET_USER} to manage ciadpi.service without password
polkit.addRule(function(action, subject) {
    if (action.id == "org.freedesktop.systemd1.manage-units" &&
        subject.user == "${TARGET_USER}" &&
        action.lookup("unit") == "ciadpi.service") {
        return polkit.Result.YES;
    }
});
EOF
chmod 644 "$POLKIT_RULES_DIR/49-ciadpi-indicator.rules"
echo "✅ polkit-правило установлено ($POLKIT_RULES_DIR)"
else
    echo "⚠️ polkit rules.d не найден — пропускаю (sudoers-правила достаточно)"
fi

echo "🎉 Готово! Индикатор больше не будет запрашивать пароль (пользователь: $TARGET_USER)."

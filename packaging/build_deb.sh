#!/bin/bash
# Сборка .deb пакета ciadpi-indicator.
# Использование: ./build_deb.sh [версия]
# Результат: dist/ciadpi-indicator_<версия>_all.deb

set -e
VERSION="${1:-1.5.0}"
PKGNAME="ciadpi-indicator"
ROOT="$(cd "$(dirname "$0")/.." && pwd)"
BUILD="$(mktemp -d /tmp/ciadpi-deb.XXXXXX)"
DIST="$ROOT/dist"
ARCH="all"

echo "==> Сборка $PKGNAME $VERSION"

# ---------- Структура пакета ----------
mkdir -p "$BUILD/DEBIAN"
mkdir -p "$BUILD/usr/bin"
mkdir -p "$BUILD/usr/lib/$PKGNAME"
mkdir -p "$BUILD/usr/share/applications"
mkdir -p "$BUILD/usr/share/doc/$PKGNAME"
mkdir -p "$BUILD/usr/share/licenses/$PKGNAME"
mkdir -p "$BUILD/usr/lib/systemd/system"   # только документационный юнит не ставим сюда; юнит создаёт postinst

# ---------- Файлы индикатора ----------
for f in \
    ciadpi_advanced_tray.py \
    ciadpi_i18n.py \
    ciadpi_params_spec.py \
    ciadpi_texts.py \
    ciadpi_strategy_search.py \
    ciadpi_autosearch.py \
    ciadpi_param_generator.py \
    ciadpi_whitelist.py \
    diagnose_ciadpi.py
do
    if [ -f "$ROOT/$f" ]; then
        install -m644 "$ROOT/$f" "$BUILD/usr/lib/$PKGNAME/"
    else
        echo "⚠️ пропущен (не найден): $f"
    fi
done

install -m755 "$ROOT/ciadpi_launcher.sh"  "$BUILD/usr/bin/ciadpi-indicator-launcher"
install -m755 "$ROOT/ciadpi_privileges.sh" "$BUILD/usr/bin/ciadpi-privileges-setup"
install -m755 "$ROOT/diagnose_ciadpi.py"   "$BUILD/usr/bin/ciadpi-diagnose-py" 2>/dev/null || true

# Лаунчер в пакете должен запускать модули из /usr/lib
cat > "$BUILD/usr/bin/ciadpi-indicator" <<'EOF'
#!/bin/bash
# CIADPI Indicator launcher (package version)
export PYTHONPATH="/usr/lib/ciadpi-indicator${PYTHONPATH:+:$PYTHONPATH}"
exec python3 /usr/lib/ciadpi-indicator/ciadpi_advanced_tray.py "$@"
EOF
chmod +x "$BUILD/usr/bin/ciadpi-indicator"

# Исправляем путь к лаунчеру в desktop-записи
sed -i 's|ciadpi_launcher.sh|ciadpi-indicator|g' "$BUILD/usr/bin/ciadpi-indicator-launcher" 2>/dev/null || true

# ---------- Desktop ----------
cat > "$BUILD/usr/share/applications/ciadpi-indicator.desktop" <<EOF
[Desktop Entry]
Version=1.0
Type=Application
Name=CIADPI Indicator
Comment=DPI Bypass System Tray Indicator / Индикатор обхода DPI
Exec=/usr/bin/ciadpi-indicator
Icon=network-transmit-receive
Categories=Network;
StartupNotify=false
Terminal=false
X-GNOME-Autostart-enabled=true
EOF

# ---------- Документация и лицензия ----------
install -m644 "$ROOT/README.md" "$BUILD/usr/share/doc/$PKGNAME/" 2>/dev/null || true
[ -f "$ROOT/LICENSE" ] && gzip -9c "$ROOT/LICENSE" > "$BUILD/usr/share/doc/$PKGNAME/changelog.gz" 2>/dev/null || true
cp "$ROOT/LICENSE" "$BUILD/usr/share/licenses/$PKGNAME/LICENSE" 2>/dev/null || true

# ---------- control ----------
cat > "$BUILD/DEBIAN/control" <<EOF
Package: $PKGNAME
Version: $VERSION
Section: net
Priority: optional
Architecture: $ARCH
Depends: python3, python3-gi, python3-gi-cairo, gir1.2-gtk-3.0, curl, systemd
Recommends: gir1.2-appindicator3-0.1 | gir1.2-ayatanaappindicator3-0.1, policykit-1
Suggests: byedpi | ciadpi-byedpi
Conflicts: ciadpi-indicator-script
Installed-Size: $(du -sk "$BUILD/usr" | cut -f1)
Maintainer: Templard <templard@users.noreply.github.com>
Homepage: https://github.com/TemplarD/ciadpi_indicator
Description: System tray indicator for CIADPI/byedpi DPI bypass
 Complete GUI management for the byedpi (ciadpi) DPI bypass tool:
 service start/stop, parameter builder, brute-force strategy search,
 proxy management with local-only mode, RU/EN localization,
 passwordless privilege setup, and built-in byedpi updater.
EOF

# ---------- postinst: сервис, права, автозапуск ----------
cat > "$BUILD/DEBIAN/postinst" <<'POSTINST'
#!/bin/bash
set -e

REAL_USER="${SUDO_USER:-$(logname 2>/dev/null || echo '')}"

if [ -z "$REAL_USER" ] || [ "$REAL_USER" = "root" ]; then
    echo "postinst: не удалось определить пользователя — пропускаю per-user настройку."
    echo "Запустите позже: sudo -E bash /usr/bin/ciadpi-privileges-setup"
else
    USER_HOME=$(getent passwd "$REAL_USER" | cut -d: -f6)

    # 1) Бинарник ciadpi: если нет ни ~/byedpi, ни пакета — подтягиваем СВЕЖИЙ из git
    if ! sudo -u "$REAL_USER" test -x "$USER_HOME/byedpi/ciadpi" 2>/dev/null && \
       [ ! -x /usr/bin/ciadpi ]; then
        echo "postinst: подтягиваем свежий byedpi для $REAL_USER..."
        sudo -u "$REAL_USER" bash -c '
            set -e
            if [ -d ~/byedpi ]; then git -C ~/byedpi pull --ff-only || true
            else git clone https://github.com/hufrea/byedpi.git ~/byedpi; fi
            make -C ~/byedpi clean >/dev/null 2>&1 || true
            make -C ~/byedpi'
    fi

    # 2) systemd unit с путём реального пользователя
    CIADPI_BIN=""
    for cand in "$USER_HOME/byedpi/ciadpi" /usr/bin/ciadpi; do
        [ -x "$cand" ] && CIADPI_BIN="$cand" && break
    done
    if [ -z "$CIADPI_BIN" ]; then
        echo "postinst: бинарник ciadpi не найден, сервис не создан." >&2
        exit 0
    fi

    PARAMS="-o1 -o25+s -T3 -At o--tlsrec 1+s"
    cat > /etc/systemd/system/ciadpi.service <<UNIT
[Unit]
Description=CIADPI DPI Bypass Service
After=network.target
Wants=network.target

[Service]
Type=simple
User=$REAL_USER
WorkingDirectory=$(dirname "$CIADPI_BIN")
ExecStart=$CIADPI_BIN $PARAMS
Restart=on-failure
RestartSec=5
TimeoutStartSec=30

[Install]
WantedBy=multi-user.target
UNIT

    systemctl daemon-reload
    systemctl enable ciadpi.service 2>/dev/null || true

    # 3) Беспарольные права (один запрос пароля уже позади — мы внутри dpkg)
    SUDO_USER="$REAL_USER" bash /usr/bin/ciadpi-privileges-setup || \
        echo "postinst: предупреждение — настройка прав не удалась, запустите вручную."

    # 4) Автозапуск индикатора пользователю
    AUTO_DIR="/home/$REAL_USER/.config/autostart"
    mkdir -p "$AUTO_DIR"
    cp /usr/share/applications/ciadpi-indicator.desktop "$AUTO_DIR/"
    chown -R "$REAL_USER:$REAL_USER" "/home/$REAL_USER/.config"

    echo "postinst: готово. Индикатор: меню приложений или 'ciadpi-indicator'."
fi
POSTINST
chmod +x "$BUILD/DEBIAN/postinst"

# ---------- prerm ----------
cat > "$BUILD/DEBIAN/prerm" <<'PRERM'
#!/bin/bash
set -e
if [ "$1" = "remove" ] || [ "$1" = "purge" ]; then
    systemctl stop ciadpi.service 2>/dev/null || true
    systemctl disable ciadpi.service 2>/dev/null || true
    pkill -f "ciadpi_advanced_tray.py" 2>/dev/null || true
fi
PRERM
chmod +x "$BUILD/DEBIAN/prerm"

# ---------- postrm ----------
cat > "$BUILD/DEBIAN/postrm" <<'POSTRM'
#!/bin/bash
set -e
if [ "$1" = "purge" ]; then
    rm -f /etc/systemd/system/ciadpi.service
    rm -rf /etc/systemd/system/ciadpi.service.d
    rm -f /etc/sudoers.d/ciadpi
    rm -f /etc/polkit-1/rules.d/49-ciadpi-indicator.rules
    systemctl daemon-reload 2>/dev/null || true
    REAL_USER="${SUDO_USER:-}"
    if [ -n "$REAL_USER" ]; then
        rm -f "/home/$REAL_USER/.config/autostart/ciadpi-indicator.desktop"
        rm -f "/home/$REAL_USER/.local/share/applications/ciadpi-indicator.desktop"
    fi
fi
POSTRM
chmod +x "$BUILD/DEBIAN/postrm"

# ---------- Права и сборка ----------
# (владелец уже текущий пользователь; dpkg-deb --root-owner-group
#  сделает файлы root:root внутри пакета)
find "$BUILD" -type d -exec chmod 755 {} +
find "$BUILD" -type f -exec chmod 644 {} +
chmod 755 "$BUILD/DEBIAN"/{postinst,prerm,postrm}
chmod 755 "$BUILD/usr/bin/"* 2>/dev/null || true

mkdir -p "$DIST"
DEB="$DIST/${PKGNAME}_${VERSION}_${ARCH}.deb"
dpkg-deb --build --root-owner-group "$BUILD" "$DEB"

echo "✅ Собран: $DEB"
dpkg-deb --info "$DEB" | head -20
rm -rf "$BUILD"

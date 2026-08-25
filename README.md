### CIADPI Complete Solution

![GitHub](https://img.shields.io/badge/platform-linux-blue)
![GitHub](https://img.shields.io/badge/ubuntu-20.04%2B-orange)
![GitHub](https://img.shields.io/badge/debian-11%20%7C%2012%20%7C%2013-green)
![GitHub](https://img.shields.io/badge/arch%20linux-supported-1793D1)
![License](https://img.shields.io/badge/License-MIT-blue.svg) 

Complete DPI bypass solution with system tray indicator. Includes byedpi and management interface.

#### Features

- 🛡️ **byedpi** - DPI bypass core (using [hufrea/byedpi](https://github.com/hufrea/byedpi))
- 🖥️ **System Tray** - Easy management
- ⚡ **No auto-start on launch** - the indicator never starts the service by itself; you control it
- 🔔 **Notification settings** - disable all or per-category notifications (RU/EN)
- 🌐 **RU/EN localization** - switch language in Application settings
- 🎛️ **Parameter Builder** - tweak every ciadpi option with sliders/fields, tooltips, and a live parameter string (in addition to the string input)
- 🧪 **Strategy Search** - Brute-force search of optimal bypass parameters
- ⬆️ **byedpi Update** - Update the core without reinstalling
- 🔌 **Proxy modes** - System-wide, PAC, or **Local-only** mode that never touches system proxy settings (point specific apps at the port yourself)
- 🚀 **Auto-Start** - Optional; the indicator can start with the system, but **never starts the service by itself** — service autostart is managed separately via systemd (`sudo systemctl enable/disable ciadpi.service`)

#### Supported Systems

- Ubuntu 20.04+
- Debian 11 / 12 / **13 (trixie)** — uses ayatana appindicator on new releases
- Linux Mint 20+
- **Arch Linux / Manjaro** — dedicated installer
- Other systemd-based distributions

## 📦 Installation

### Option 1: Packages (recommended)

Prebuilt packages install the indicator system-wide (`/usr/lib/ciadpi-indicator`, `/usr/bin/ciadpi-indicator`), create and enable the `ciadpi.service`, set up passwordless privileges, and register the desktop entry — all in one step.

**Debian / Ubuntu / Mint (.deb):**

```bash
# Скачать последний релиз со страницы Releases и установить:
sudo apt install ./ciadpi-indicator_1.5.0_all.deb
```

Сборка из исходников этого репозитория:

```bash
git clone https://github.com/TemplarD/ciadpi_indicator.git
cd ciadpi_indicator/packaging
./build_deb.sh            # → dist/ciadpi-indicator_1.5.0_all.deb
sudo apt install ../dist/ciadpi-indicator_1.5.0_all.deb
```

**Arch Linux / Manjaro (PKGBUILD):**

```bash
git clone https://github.com/TemplarD/ciadpi_indicator.git
cd ciadpi_indicator/packaging
makepkg -si               # соберёт и установит пакет
```

Удаление пакета: `sudo apt remove ciadpi-indicator` (Debian) или `sudo pacman -R ciadpi-indicator` (Arch). При `purge`/`-R` убираются и сервис с правами.

### Option 2: Script installation

Скриптовая установка ставит всё в домашнюю директорию (`~/.local/bin`, `~/byedpi`) — обновляться можно прямо из трея. Пакетная — в системные каталоги, обновление через менеджер пакетов.

#### Debian / Ubuntu / Mint


```bash
wget -O install_ciadpi.sh https://raw.githubusercontent.com/templard/ciadpi_indicator/master/install_ciadpi_complete.sh
chmod +x install_ciadpi.sh
./install_ciadpi.sh
```

### Arch Linux / Manjaro

```bash
git clone https://github.com/templard/ciadpi_indicator.git
cd ciadpi_indicator
./install_ciadpi_arch.sh
```

The Arch installer builds byedpi into `~/byedpi/ciadpi` and creates a **system**
`ciadpi.service` — exactly what the tray indicator expects, so all tray functions work out of the box.

## 🗑️ Uninstallation

**Package install:** `sudo apt remove ciadpi-indicator` / `sudo pacman -R ciadpi-indicator`
(add `purge` / `-Rns` to also remove the service unit, sudoers and polkit rules).

### Script installation

#### Ubuntu / Debian / Mint

```bash
wget -O uninstall_ciadpi.sh https://raw.githubusercontent.com/templard/ciadpi_indicator/master/uninstall_ciadpi_complete.sh
chmod +x uninstall_ciadpi.sh
./uninstall_ciadpi.sh
```

### Arch Linux / Manjaro

```bash
cd ciadpi_indicator   # если есть локальная копия
./uninstall_ciadpi_arch.sh
```

Both uninstallers ask before removing `~/byedpi` and configs; a config backup is kept outside the removed directory.

#### About byedpi

This solution uses **[byedpi](https://github.com/hufrea/byedpi)** as the core DPI bypass engine. byedpi is automatically downloaded and compiled during installation (or pulled as a dependency with the package install).

byedpi features:
- Multiple obfuscation methods
- TLS/HTTP packet modification  
- Transparent proxy support
- Cross-platform compatibility

## What Gets Installed

- **byedpi** in ~/byedpi/ (cloned and compiled from [hufrea/byedpi](https://github.com/hufrea/byedpi))
- **System tray indicator** in ~/.local/bin/
- **Systemd service** for automatic management
- **Desktop integration** with autostart
- **sudoers rules** for passwordless service control (validated via visudo)

#### Usage

After installation, the CIADPI indicator will auto-start. Look for the network icon in your system tray.

### Manual Control
```bash
# Start indicator manually
~/.local/bin/ciadpi_advanced_tray.py

# Control service
systemctl start ciadpi.service
systemctl stop ciadpi.service  
systemctl status ciadpi.service
```

## 🧪 Strategy Search (перебор параметров)

New in v1.3: menu item **«Поиск стратегии»** in the tray menu runs a brute-force
search over parameter combinations:

1. Each candidate starts as a **separate ciadpi instance on a test port** (default 1081) — your working service is not touched.
2. Availability of chosen URLs is checked through the test proxy with curl.
3. Progress bar + live log show every tested combination and per-URL results.
4. The best (fastest successful) set can be applied to the service with one button.

CLI mode is also available:

```bash
python3 ~/.local/bin/ciadpi_strategy_search.py --max-tests 20 --port 1081 --url https://example.com
```

Results history: `~/.config/ciadpi/strategy_history.json`

## ⬆️ Updating byedpi without reinstalling

Tray menu → **«Обновить byedpi»**:

1. Checks that `~/byedpi` is a git checkout of hufrea/byedpi
2. Backs up the current binary to `~/byedpi/ciadpi.bak`
3. `git pull --ff-only` + `make clean && make`
4. Restarts the service with your existing parameters
5. If the new build fails to start — automatic rollback to the backup

No root reinstall needed: everything happens inside your home directory.

#### Enhanced Proxy Management

For applications to use the DPI bypass, you need to configure proxy settings:

**Option 1: System-wide proxy (recommended)**
- Open CIADPI indicator → Proxy Settings
- Set mode to "Manual"
- Leave host field **empty**
- Set port to 1080

**Option 2: Browser proxy**
- Firefox: Settings → Network Settings → Manual proxy configuration
- Chrome: Use --proxy-server=127.0.0.1:1080 launch flag
- Set HTTP/HTTPS proxy to 127.0.0.1:1080
- Try with host field **empty**, only port, if not working

**Option 3: Environment variables**
```
export http_proxy=http://127.0.0.1:1080
export https_proxy=http://127.0.0.1:1080
```

## 🔧 Proxy Modes:

- **Manual Proxy**: Set specific host and port (empty host = port-only configuration)
- **Automatic (PAC)**: Use Proxy Auto-Configuration URL
- **Disabled**: No proxy

## 💾 Configuration Persistence:

All proxy settings are stored in `~/.config/ciadpi/config.json`:
```json
{
  "params": "-o1 -o25+s -T3 -At o--tlsrec 1+s",
  "proxy_enabled": true,
  "proxy_mode": "manual",
  "proxy_host": "",
  "proxy_port": "1080",
  "auto_disable_proxy": true,
  "we_changed_proxy": false
}
```

Parameters are saved to config **before** the service restart, so they are never lost even if the restart fails.

## 🛡️ Whitelist Support:

- Exclude specific domains/IPs from proxy routing
- Supports exact domains (`example.com`) and wildcards (`*.example.com`)
- CIDR notation for IP ranges (`192.168.1.0/24`)

## Usage Tips:
For Mobile Users: Enable "Auto-disable proxy" to automatically restore internet when stopping the service
For Always-On Users: Disable "Auto-disable proxy" to maintain proxy settings permanently
For Development: Use whitelist to exclude local domains from proxy routing

## 🎯 Key Features:

- **Automatic Proxy Application** - Applies your proxy settings from config on program startup
- **Smart State Tracking** - Remembers if proxy settings were changed by the application
- **Auto-Restore Option** - Optional automatic restoration of original system proxy when service stops
- **Settings Persistence** - All proxy configurations survive application restarts
- **Parameter Validation** - Input is validated against real ciadpi options (incl. glued values like `-T3`) before applying
- **pkexec fallback** - If sudo is unavailable, the indicator asks for the password via the GUI polkit agent

## 🔑 Passwordless service control

The indicator needs root only for `systemctl` actions on `ciadpi.service`.
To stop password prompts:

- **During installation** — both installers run `ciadpi_privileges.sh` once;
  you enter the password a single time and never again.
- **Any time later** — tray menu → **«🔑 Права доступа»** → one password prompt.

What it configures (nothing broader):
- `/etc/sudoers.d/ciadpi` — NOPASSWD for systemctl actions on `ciadpi.service`
  only, plus writing the unit file via `tee` and removing its override dir
- polkit rule allowing the user to manage `ciadpi.service` without a password

Both are validated (`visudo -c`) and removed by the uninstallers.

#### Troubleshooting

**Service not starting?**
```bash
sudo systemctl status ciadpi.service
journalctl -u ciadpi.service -f
```

**Indicator not appearing?**
- Log out and log back in
- Or restart your system  
- Check if AppIndicator is supported on your desktop (on Debian 13+ the ayatana package is used automatically)
- The indicator falls back to Gtk.StatusIcon when AppIndicator is missing

**Proxy not working?**
- Verify CIADPI service is running: systemctl status ciadpi.service
- Check proxy settings in browser/system
- Try using empty host field in proxy settings
- Run diagnostics: `~/.local/bin/ciadpi-diagnose`

### Repository Structure

```
ciadpi_indicator/
├── README.md
├── LICENSE
├── ciadpi_advanced_tray.py      # tray indicator (GTK3/AppIndicator)
├── ciadpi_strategy_search.py    # brute-force strategy search
├── ciadpi_i18n.py               # RU/EN localization
├── ciadpi_params_spec.py        # parameter definitions for the builder
├── ciadpi_autosearch.py
├── ciadpi_param_generator.py
├── ciadpi_whitelist.py
├── diagnose_ciadpi.py
├── install_ciadpi_complete.sh   # installer for Debian-based
├── uninstall_ciadpi_complete.sh # uninstaller for Debian-based
├── install_ciadpi_arch.sh       # installer for Arch Linux
├── uninstall_ciadpi_arch.sh     # uninstaller for Arch Linux
├── ciadpi.service               # systemd unit template
└── assets/
    └── (screenshots, etc.)
```

## Credits

- **byedpi** - Core DPI bypass engine: [hufrea/byedpi](https://github.com/hufrea/byedpi)
- **CIADPI Indicator** - System tray management interface

#### License

MIT License

# CIADPI Complete Solution

![GitHub](https://img.shields.io/badge/platform-linux-blue)
![GitHub](https://img.shields.io/badge/ubuntu-20.04%2B-orange)

Complete DPI bypass solution with system tray indicator. Includes byedpi and management interface.

## Features

- 🛡️ **byedpi** - DPI bypass core
- 🖥️ **System Tray** - Easy management
- ⚡ **One-Click Control** - Start/stop service
- 🔧 **Parameter Management** - Customize connection
- 🔌 **Proxy Configuration** - System-wide proxy
- 🚀 **Auto-Start** - Starts with system

## Quick Install

```bash
wget -O install_ciadpi.sh https://raw.githubusercontent.com/templard/ciadpi_indicator/master/install_ciadpi_complete.sh
chmod +x install_ciadpi.sh
./install_ciadpi.sh
```

## What Gets Installed
byedpi in ~/byedpi/ (cloned and compiled)

System tray indicator in ~/.local/bin/

Systemd service for automatic management

Desktop integration with autostart

## Quick Uninstall
```bash
wget -O uninstall_ciadpi.sh https://raw.githubusercontent.com/templard/ciadpi_indicator/master/uninstall_ciadpi_complete.sh
chmod +x uninstall_ciadpi.sh
./uninstall_ciadpi.sh
```

## Usage
After installation, the CIADPI indicator will auto-start. Look for the network icon in your system tray.

## Manual Control

```bash
# Start indicator manually
~/.local/bin/ciadpi_advanced_tray.py

# Control service
systemctl start ciadpi.service
systemctl stop ciadpi.service
systemctl status ciadpi.service

# Uninstall
./uninstall_ciadpi_complete.sh
```

## Supported Systems
Ubuntu 20.04+

Debian 11+

Linux Mint 20+

Other systemd-based distributions

## License
MIT License

## 5. Структура репозитория:
```
ciadpi-complete/
├── README.md
├── install_ciadpi_complete.sh
├── uninstall_ciadpi_complete.sh
├── ciadpi.service
├── ciadpi_advanced_tray.py
├── ciadpi_autosearch.py
├── ciadpi_param_generator.py
├── ciadpi_launcher.sh
└── assets/
    └── (screenshots, etc.)
```

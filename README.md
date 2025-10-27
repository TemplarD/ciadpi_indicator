### CIADPI Complete Solution

![GitHub](https://img.shields.io/badge/platform-linux-blue)
![GitHub](https://img.shields.io/badge/ubuntu-20.04%2B-orange)

Complete DPI bypass solution with system tray indicator. Includes byedpi and management interface.

#### Features

- 🛡️ **byedpi** - DPI bypass core (using [hufrea/byedpi](https://github.com/hufrea/byedpi))
- 🖥️ **System Tray** - Easy management
- ⚡ **One-Click Control** - Start/stop service
- 🔧 **Parameter Management** - Customize connection
- 🔌 **Proxy Configuration** - System-wide proxy
- 🚀 **Auto-Start** - Starts with system

#### Quick Install

```bash
wget -O install_ciadpi.sh https://raw.githubusercontent.com/templard/ciadpi_indicator/master/install_ciadpi_complete.sh
chmod +x install_ciadpi.sh
./install_ciadpi.sh
```

#### Quick Uninstall

```bash
wget -O uninstall_ciadpi.sh https://raw.githubusercontent.com/templard/ciadpi_indicator/master/uninstall_ciadpi_complete.sh
chmod +x uninstall_ciadpi.sh
./uninstall_ciadpi.sh
```

#### About byedpi

This solution uses **[byedpi](https://github.com/hufrea/byedpi)** as the core DPI bypass engine. byedpi is automatically downloaded and compiled during installation.

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
  "proxy_enabled": true,
  "proxy_mode": "manual",
  "proxy_host": "127.0.0.1",
  "proxy_port": "1080",
  "auto_disable_proxy": true,
  "we_changed_proxy": true
}
```

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

#### Supported Systems

- Ubuntu 20.04+
- Debian 11+ 
- Linux Mint 20+
- Other systemd-based distributions

#### Troubleshooting

**Service not starting?**
```bash
sudo systemctl status ciadpi.service
journalctl -u ciadpi.service -f
```

**Indicator not appearing?**
- Log out and log back in
- Or restart your system  
- Check if AppIndicator is supported on your desktop

**Proxy not working?**
- Verify CIADPI service is running: systemctl status ciadpi.service
- Check proxy settings in browser/system
- Try using empty host field in proxy settings

#### License

MIT License

#### Repository Structure

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

## Credits

- **byedpi** - Core DPI bypass engine: [hufrea/byedpi](https://github.com/hufrea/byedpi)
- **CIADPI Indicator** - System tray management interface
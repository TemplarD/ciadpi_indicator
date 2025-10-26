#!/usr/bin/env python3

import gi
import re
import subprocess
import threading
import time
import os
import json
import shutil
from pathlib import Path
from datetime import datetime

gi.require_version('Gtk', '3.0')
gi.require_version('AppIndicator3', '0.1')
from gi.repository import Gtk, AppIndicator3, GLib

# Отладочная информация
DEBUG_LOG = Path.home() / '.config' / 'ciadpi' / 'indicator_debug.log'

def log_debug(message):
    """Запись отладочной информации"""
    timestamp = time.strftime("%Y-%m-%d %H:%M:%S")
    with open(DEBUG_LOG, 'a', encoding='utf-8') as f:
        f.write(f"[{timestamp}] {message}\n")
    print(f"DEBUG: {message}")

# Проверяем переменные окружения
log_debug("=== Starting CIADPI Indicator ===")
log_debug(f"DISPLAY: {os.environ.get('DISPLAY')}")
log_debug(f"DBUS_SESSION_BUS_ADDRESS: {os.environ.get('DBUS_SESSION_BUS_ADDRESS')}")
log_debug(f"XAUTHORITY: {os.environ.get('XAUTHORITY')}")
log_debug(f"USER: {os.environ.get('USER')}")
log_debug(f"PWD: {os.environ.get('PWD', os.getcwd())}")

# Попытка восстановить переменные если они отсутствуют
if not os.environ.get('DBUS_SESSION_BUS_ADDRESS'):
    dbus_path = f"/run/user/{os.getuid()}/bus"
    if os.path.exists(dbus_path):
        os.environ['DBUS_SESSION_BUS_ADDRESS'] = f"unix:path={dbus_path}"
        log_debug(f"Restored DBUS_SESSION_BUS_ADDRESS: {os.environ['DBUS_SESSION_BUS_ADDRESS']}")

if not os.environ.get('XAUTHORITY'):
    xauth_path = Path.home() / '.Xauthority'
    if xauth_path.exists():
        os.environ['XAUTHORITY'] = str(xauth_path)
        log_debug(f"Restored XAUTHORITY: {os.environ['XAUTHORITY']}")

# Попытка импорта модуля автопоиска
try:
    import sys
    sys.path.append(str(Path.home() / '.local' / 'bin'))
    from ciadpi_autosearch import CIAutoSearch
    AUTOSEARCH_AVAILABLE = True
except ImportError as e:
    print(f"Модуль автопоиска не доступен: {e}")
    AUTOSEARCH_AVAILABLE = False
    CIAutoSearch = None

class AdvancedTrayIndicator:
    def __init__(self):
        log_debug("Initializing AdvancedTrayIndicator...")
        
        self.app = 'ciadpi_advanced_indicator'
        self.config_file = Path.home() / '.config' / 'ciadpi' / 'config.json'
        self.service_file = Path('/etc/systemd/system/ciadpi.service')
        self.default_params = "-o1 -o25+s -T3 -At o--tlsrec 1+s"
        self.current_params = self.load_config()

        # Проверяем текущие настройки прокси
        GLib.timeout_add(5000, self.check_current_proxy)  # Через 3 секунды после запуска   

        self.autosearcher = None
        self.is_searching = False
        # Инициализация автопоиска
        # if AUTOSEARCH_AVAILABLE:
        #     self.autosearcher = CIAutoSearch()
        #     self.is_searching = False
        # else:
        #     self.autosearcher = None
        
        # Отложенная инициализация индикатора
        self.indicator = None
        GLib.timeout_add(2000, self.initialize_indicator)  # 2 секунды задержки
        
        # Запускаем проверку статуса
        GLib.timeout_add_seconds(3, self.update_status)
        log_debug("AdvancedTrayIndicator initialization completed")

    def initialize_indicator(self):
        """Отложенная инициализация индикатора"""
        try:
            log_debug("Creating AppIndicator3...")
            
            self.indicator = AppIndicator3.Indicator.new(
                self.app, 
                "network-transmit-receive-symbolic",
                AppIndicator3.IndicatorCategory.APPLICATION_STATUS
            )
            
            self.indicator.set_status(AppIndicator3.IndicatorStatus.ACTIVE)
            self.indicator.set_menu(self.create_menu())
            
            # Устанавливаем всплывающие подсказки
            self.update_tooltip()
            
            log_debug("AppIndicator3 created successfully")
            
        except Exception as e:
            log_debug(f"Error creating AppIndicator3: {e}")
            # Fallback на Gtk.StatusIcon
            self.setup_fallback_indicator()
        
        return False  # Останавливаем таймер

    def setup_fallback_indicator(self):
        """Резервный вариант с Gtk.StatusIcon"""
        try:
            log_debug("Setting up Gtk.StatusIcon fallback...")
            self.status_icon = Gtk.StatusIcon()
            self.status_icon.set_from_icon_name("network-transmit-receive-symbolic")
            self.status_icon.set_tooltip_text("CIADPI Indicator")
            self.status_icon.connect("popup-menu", self.on_right_click)
            self.status_icon.connect("activate", self.on_left_click)
            self.status_icon.set_visible(True)
            log_debug("Gtk.StatusIcon setup completed")
        except Exception as e:
            log_debug(f"Error setting up Gtk.StatusIcon: {e}")

    def on_right_click(self, icon, button, time):
        """Правый клик для Gtk.StatusIcon"""
        menu = self.create_menu()
        menu.show_all()
        menu.popup(None, None, None, None, button, time)

    def on_left_click(self, icon):
        """Левый клик для Gtk.StatusIcon"""
        self.show_quick_status()

    def show_quick_status(self):
        """Быстрый статус по левому клику"""
        try:
            result = subprocess.run(
                ['systemctl', 'is-active', 'ciadpi.service'],
                capture_output=True, text=True, timeout=2
            )
            status = "🟢 Запущен" if result.stdout.strip() == 'active' else "🔴 Остановлен"
            self.show_notification("Статус CIADPI", status)
        except Exception as e:
            self.show_notification("Ошибка", f"Не удалось проверить статус: {e}")

    def load_config(self):
        """Загрузка конфигурации из файла"""
        default_config = {
            "params": self.default_params,
            "proxy_enabled": False,
            "proxy_host": "127.0.0.1",
            "proxy_port": "1080",
            "current_params": self.default_params
        }
        
        try:
            self.config_file.parent.mkdir(exist_ok=True)
            if self.config_file.exists():
                with open(self.config_file, 'r', encoding='utf-8') as f:
                    config = json.load(f)
                    # Проверяем, что все необходимые поля есть
                    for key in default_config:
                        if key not in config:
                            config[key] = default_config[key]
                    return config
        except Exception as e:
            print(f"Ошибка загрузки конфига: {e}")
            
        return default_config

    def save_config(self):
        """Сохранение конфигурации в файл"""
        try:
            with open(self.config_file, 'w', encoding='utf-8') as f:
                json.dump(self.current_params, f, indent=2, ensure_ascii=False)
        except Exception as e:
            print(f"Ошибка сохранения конфига: {e}")

    def update_tooltip(self):
        """Обновление всплывающей подсказки"""
        if hasattr(self, 'indicator') and self.indicator:
            current_params = self.get_current_service_params()
            tooltip_text = f"CIADPI - {current_params}" if current_params else "CIADPI Indicator"
            self.indicator.set_title(tooltip_text)

    def get_current_service_params(self):
        """Получение текущих параметров из systemd сервиса"""
        try:
            result = subprocess.run(
                ['systemctl', 'show', 'ciadpi.service', '--property=ExecStart', '--no-pager'],
                capture_output=True, text=True, timeout=5
            )
            if result.returncode == 0:
                output = result.stdout.strip()
                if 'argv[]=' in output:
                    parts = output.split('argv[]=')
                    if len(parts) > 1:
                        args = parts[1].split(';')[0].split()
                        if len(args) > 1:
                            return ' '.join(args[1:])
            return self.default_params
        except:
            return self.default_params

    def update_service_params(self, new_params):
        """Обновление параметров в systemd сервисе"""
        try:
            print(f"🔄 Обновление параметров: {new_params}")
            
            # Останавливаем сервис
            subprocess.run(['sudo', 'systemctl', 'stop', 'ciadpi.service'], 
                          check=False, timeout=10)
            
            # Создаем временный override файл
            override_dir = Path('/etc/systemd/system/ciadpi.service.d')
            override_file = override_dir / 'override.conf'
            
            # Создаем директорию если нет
            subprocess.run(['sudo', 'mkdir', '-p', str(override_dir)])
            
            # Создаем override конфиг
            override_content = f"""[Service]
ExecStart=
ExecStart=/home/templard/byedpi/ciadpi {new_params}
Restart=always
RestartSec=5
"""
            
            # Записываем временный файл
            temp_file = Path('/tmp/ciadpi_override.conf')
            with open(temp_file, 'w', encoding='utf-8') as f:
                f.write(override_content)
            
            # Копируем с правами root
            subprocess.run(['sudo', 'cp', str(temp_file), str(override_file)])
            subprocess.run(['sudo', 'systemctl', 'daemon-reload'])
            
            # Обновляем конфиг
            self.current_params["current_params"] = new_params
            self.current_params["params"] = new_params
            self.save_config()
            
            # Запускаем сервис
            subprocess.run(['sudo', 'systemctl', 'start', 'ciadpi.service'])
            
            print("✅ Параметры успешно обновлены")
            return True
            
        except Exception as e:
            print(f"❌ Общая ошибка: {e}")
            # Пытаемся восстановить сервис
            try:
                subprocess.run(['sudo', 'systemctl', 'daemon-reload'])
                subprocess.run(['sudo', 'systemctl', 'start', 'ciadpi.service'])
            except:
                pass
            return False

    def create_menu(self):
        menu = Gtk.Menu()
        
        # Статус
        self.status_item = Gtk.MenuItem(label="🔄 Проверка статуса...")
        menu.append(self.status_item)
        
        menu.append(Gtk.SeparatorMenuItem())
        
        # Управление сервисом
        start_item = Gtk.MenuItem(label="▶️ Запустить сервис")
        start_item.connect("activate", self.start_service)
        menu.append(start_item)
        
        stop_item = Gtk.MenuItem(label="⏹️ Остановить сервис")
        stop_item.connect("activate", self.stop_service)
        menu.append(stop_item)
        
        restart_item = Gtk.MenuItem(label="🔄 Перезапустить сервис")
        restart_item.connect("activate", self.restart_service)
        menu.append(restart_item)
        
        menu.append(Gtk.SeparatorMenuItem())
        
        # Настройки
        settings_item = Gtk.MenuItem(label="⚙️ Настройки параметров")
        settings_item.connect("activate", self.show_settings)
        menu.append(settings_item)
        
        proxy_item = Gtk.MenuItem(label="🔌 Настройки прокси")
        proxy_item.connect("activate", self.show_proxy_settings)
        menu.append(proxy_item)
        
        menu.append(Gtk.SeparatorMenuItem())
        
        # Автопоиск и история
        if self.autosearcher:
            autosearch_item = Gtk.MenuItem(label="🔍 Автопоиск параметров")
            autosearch_item.connect("activate", self.show_autosearch_dialog)
            menu.append(autosearch_item)
            
            history_item = Gtk.MenuItem(label="📊 История тестирования")
            history_item.connect("activate", self.show_history)
            menu.append(history_item)
            
            menu.append(Gtk.SeparatorMenuItem())
        
        # Логи
        logs_item = Gtk.MenuItem(label="📋 Показать логи")
        logs_item.connect("activate", self.show_logs)
        menu.append(logs_item)
        
        menu.append(Gtk.SeparatorMenuItem())
        
        # Справка
        help_item = Gtk.MenuItem(label="❓ Справка по параметрам")
        help_item.connect("activate", self.show_help)
        menu.append(help_item)
        
        about_item = Gtk.MenuItem(label="ℹ️ О программе")
        about_item.connect("activate", self.show_about)
        menu.append(about_item)
        
        menu.append(Gtk.SeparatorMenuItem())
        
        # Выход
        exit_item = Gtk.MenuItem(label="🚪 Выход")
        exit_item.connect("activate", self.exit_app)
        menu.append(exit_item)
        
        menu.show_all()
        return menu

    def update_status(self):
        try:
            result = subprocess.run(
                ['systemctl', 'is-active', 'ciadpi.service'],
                capture_output=True, text=True, timeout=2
            )
            status = result.stdout.strip()
            
            current_params = self.get_current_service_params()
            status_text = "Запущен" if status == 'active' else "Остановлен"
            
            if hasattr(self, 'indicator') and self.indicator:
                if status == 'active':
                    self.indicator.set_icon_full("network-transmit-receive-symbolic", "CIADPI запущен")
                    self.status_item.set_label(f"✅ CIADPI {status_text}")
                else:
                    self.indicator.set_icon_full("network-offline-symbolic", "CIADPI остановлен")
                    self.status_item.set_label(f"❌ CIADPI {status_text}")
                
                # Обновляем подсказку
                self.update_tooltip()
            elif hasattr(self, 'status_icon'):
                # Для Gtk.StatusIcon
                if status == 'active':
                    self.status_icon.set_from_icon_name("network-transmit-receive-symbolic")
                    self.status_icon.set_tooltip_text(f"CIADPI {status_text}")
                else:
                    self.status_icon.set_from_icon_name("network-offline-symbolic")
                    self.status_icon.set_tooltip_text(f"CIADPI {status_text}")
                
        except Exception as e:
            if hasattr(self, 'status_item'):
                self.status_item.set_label("⚠️ Ошибка проверки статуса")
            
        return True
    
    def sync_proxy_settings(self):
        """Синхронизация настроек прокси с системой"""
        try:
            current_system = self.get_system_proxy_settings()
            current_config = self.current_params
            
            # Если настройки отличаются, применяем системные
            if (current_config.get("proxy_mode") != current_system.get('mode') or
                current_config.get("proxy_host") != current_system.get('http_host')):
                
                print("🔄 Синхронизация настроек прокси...")
                self.current_params["proxy_mode"] = current_system.get('mode', 'none')
                self.current_params["proxy_enabled"] = current_system.get('mode') != 'none'
                self.current_params["proxy_host"] = current_system.get('http_host', '127.0.0.1')
                self.current_params["proxy_port"] = current_system.get('http_port', '1080')
                self.save_config()
                
        except Exception as e:
            print(f"❌ Ошибка синхронизации прокси: {e}")
        
        return False  # Останавливаем таймер    
    

    def show_proxy_settings(self, widget):
        """Диалог настроек прокси"""
        # Сначала получаем текущие системные настройки
        current_settings = self.get_system_proxy_settings()
        
        dialog = Gtk.Dialog(title="Настройки системного прокси", flags=0)
        dialog.add_buttons(Gtk.STOCK_CANCEL, Gtk.ResponseType.CANCEL,
                        Gtk.STOCK_OK, Gtk.ResponseType.OK)
        dialog.set_default_size(500, 350)

        content_area = dialog.get_content_area()
        
        box = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=10)
        box.set_margin_top(10)
        box.set_margin_bottom(10)
        box.set_margin_start(10)
        box.set_margin_end(10)
        
        # Режим прокси
        mode_label = Gtk.Label(label="Режим прокси:")
        mode_combo = Gtk.ComboBoxText()
        mode_combo.append_text("Автоматический (PAC)")
        mode_combo.append_text("Ручной") 
        mode_combo.append_text("Выключен")
        
        # Устанавливаем текущий режим
        current_mode = current_settings.get('mode', 'none')
        if current_mode == 'auto':
            mode_combo.set_active(0)
        elif current_mode == 'manual':
            mode_combo.set_active(1)
        else:
            mode_combo.set_active(2)
        
        # Настройки ручного прокси
        manual_frame = Gtk.Frame(label="Ручные настройки прокси")
        manual_box = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=5)
        manual_box.set_margin_top(5)
        manual_box.set_margin_bottom(5)
        manual_box.set_margin_start(5)
        manual_box.set_margin_end(5)
        
        # Хост
        host_label = Gtk.Label(label="Хост прокси (оставьте ПУСТЫМ для использования только порта):")
        host_entry = Gtk.Entry()
        host_entry.set_placeholder_text("ПУСТОЕ значение - только порт")
        current_host = current_settings.get('http_host', '')
        # Показываем именно то, что сохранено (может быть пустой строкой)
        host_entry.set_text(current_host)
        
        # Порт
        port_label = Gtk.Label(label="Порт прокси:")
        port_entry = Gtk.Entry()
        port_entry.set_text(current_settings.get('http_port', '1080'))
        
        # Примеры форматов
        examples_label = Gtk.Label(label="Важно:\n• Пустое поле хоста = только порт\n• 127.0.0.1 = хост + порт")
        examples_label.set_sensitive(False)
        
        manual_box.pack_start(host_label, False, False, 0)
        manual_box.pack_start(host_entry, False, False, 0)
        manual_box.pack_start(port_label, False, False, 0)
        manual_box.pack_start(port_entry, False, False, 0)
        manual_box.pack_start(examples_label, False, False, 0)
        manual_frame.add(manual_box)
        
        # Информация
        info_label = Gtk.Label(label="Настройки применяются ко всем приложениям")
        info_label.set_sensitive(False)
        
        # Текущий статус
        current_host_display = "ПУСТОЙ (только порт)" if not current_settings.get('http_host') else current_settings.get('http_host')
        current_port_display = current_settings.get('http_port', 'не указан')
        status_label = Gtk.Label(label=f"Текущий режим: {current_settings.get('mode', 'неизвестно')}\nХост: {current_host_display}, Порт: {current_port_display}")
        status_label.set_sensitive(False)
        
        box.pack_start(mode_label, False, False, 0)
        box.pack_start(mode_combo, False, False, 0)
        box.pack_start(manual_frame, False, False, 0)
        box.pack_start(status_label, False, False, 0)
        box.pack_start(info_label, False, False, 0)
        
        content_area.pack_start(box, True, True, 0)
        content_area.show_all()
        
        response = dialog.run()
        
        if response == Gtk.ResponseType.OK:
            mode_index = mode_combo.get_active()
            modes = ['auto', 'manual', 'none']
            selected_mode = modes[mode_index] if mode_index >= 0 else 'none'
            
            # Получаем хост и порт
            proxy_host = host_entry.get_text().strip()
            proxy_port = port_entry.get_text().strip()
            
            # Сохраняем ПУСТОЕ значение если поле пустое
            # Не подставляем никаких значений по умолчанию!
            
            # Валидация порта
            if not proxy_port.isdigit():
                self.show_notification("Ошибка", "Порт должен быть числом")
                dialog.destroy()
                return
            
            # Сохраняем в конфиг (сохраняем ПУСТУЮ строку если поле пустое)
            self.current_params["proxy_enabled"] = selected_mode != 'none'
            self.current_params["proxy_host"] = proxy_host  # Может быть пустой строкой
            self.current_params["proxy_port"] = proxy_port
            self.current_params["proxy_mode"] = selected_mode
            self.save_config()
            
            # Применяем системные настройки
            success = self.apply_system_proxy(selected_mode, proxy_host, proxy_port)
            
            if success:
                # Показываем в уведомлении реальные значения
                display_host = "ПУСТОЙ" if not proxy_host else proxy_host
                self.show_notification("Прокси", f"Прокси {selected_mode} применен\nХост: {display_host}\nПорт: {proxy_port}")
            else:
                self.show_notification("Ошибка", "Не удалось применить настройки прокси")
        
        dialog.destroy()

    def get_system_proxy_settings(self):
        """Получение текущих системных настроек прокси"""
        log_debug("show_proxy_settings called")  # Добавьте эту строку

        settings = {
            'mode': 'none',
            'http_host': '127.0.0.1',
            'http_port': '1080'
        }
        
        try:
            # Получаем режим прокси
            result = subprocess.run([
                'gsettings', 'get', 'org.gnome.system.proxy', 'mode'
            ], capture_output=True, text=True, check=False)
            
            if result.returncode == 0:
                mode = result.stdout.strip().strip("'")
                settings['mode'] = mode
                
                if mode == 'manual':
                    # Получаем HTTP настройки
                    host_result = subprocess.run([
                        'gsettings', 'get', 'org.gnome.system.proxy.http', 'host'
                    ], capture_output=True, text=True, check=False)
                    port_result = subprocess.run([
                        'gsettings', 'get', 'org.gnome.system.proxy.http', 'port'
                    ], capture_output=True, text=True, check=False)
                    
                    if host_result.returncode == 0:
                        settings['http_host'] = host_result.stdout.strip().strip("'")
                    if port_result.returncode == 0:
                        settings['http_port'] = port_result.stdout.strip()
                        
        except Exception as e:
            print(f"❌ Ошибка получения настроек прокси: {e}")
        
        return settings    

    def apply_system_proxy(self, mode, host, port):
        """Применение системных настроек прокси через NetworkManager"""
        try:
            # Метод 1: Через gsettings (для GNOME приложений)
            subprocess.run([
                'gsettings', 'set', 'org.gnome.system.proxy', 'mode', mode
            ], check=False)
            
            if mode == 'manual':
                # Используем ПУСТОЕ значение если host пустой
                # Некоторые системы могут работать с пустым хостом
                effective_host = host  # Может быть пустой строкой!
                
                # Настраиваем HTTP
                subprocess.run([
                    'gsettings', 'set', 'org.gnome.system.proxy.http', 'host', effective_host
                ], check=False)
                subprocess.run([
                    'gsettings', 'set', 'org.gnome.system.proxy.http', 'port', port
                ], check=False)
                
                # Настраиваем HTTPS
                subprocess.run([
                    'gsettings', 'set', 'org.gnome.system.proxy.https', 'host', effective_host
                ], check=False)
                subprocess.run([
                    'gsettings', 'set', 'org.gnome.system.proxy.https', 'port', port
                ], check=False)
                
                # Настраиваем FTP
                subprocess.run([
                    'gsettings', 'set', 'org.gnome.system.proxy.ftp', 'host', effective_host
                ], check=False)
                subprocess.run([
                    'gsettings', 'set', 'org.gnome.system.proxy.ftp', 'port', port
                ], check=False)
                
                # Используем одинаковые настройки для всех протоколов
                subprocess.run([
                    'gsettings', 'set', 'org.gnome.system.proxy', 'use-same-proxy', 'true'
                ], check=False)
                
            elif mode == 'auto':
                # Для автоматического режима обычно нужен PAC URL
                # Пока оставим пустым
                pass
                
            host_display = "ПУСТОЙ" if not host else host
            print(f"✅ Системный прокси установлен: {mode} Хост: {host_display} Порт: {port}")
            
            # Метод 2: Через Environment (для терминальных приложений)
            self.apply_environment_proxy(mode, host, port)
            
            # Метод 3: Перезапускаем NetworkManager для применения настроек
            self.restart_network_services()
            
            return True
            
        except Exception as e:
            print(f"❌ Ошибка настройки системного прокси: {e}")
            return False
    
    def apply_environment_proxy(self, mode, host, port):
        """Применение прокси через переменные окружения"""
        try:
            if mode == 'manual':
                # Формируем строку прокси - если хост ПУСТОЙ, используем только порт
                if host:
                    proxy_url = f"http://{host}:{port}"
                else:
                    # ПУСТОЙ хост - используем только порт (некоторые приложения так работают)
                    proxy_url = f"http://:{port}"  # Формат с пустым хостом
                
                # Создаем скрипт для применения переменных (для новых терминалов)
                env_file = Path.home() / '.proxy_env'
                with open(env_file, 'w') as f:
                    f.write(f"""export http_proxy={proxy_url}
    export https_proxy={proxy_url}
    export ftp_proxy={proxy_url}
    export HTTP_PROXY={proxy_url}
    export HTTPS_PROXY={proxy_url}
    export FTP_PROXY={proxy_url}
    """)
                print(f"✅ Переменные окружения установлены: {proxy_url}")
            else:
                # Очищаем переменные
                env_file = Path.home() / '.proxy_env'
                if env_file.exists():
                    env_file.unlink()
                print("✅ Переменные окружения очищены")
                
        except Exception as e:
            print(f"⚠️ Ошибка установки переменных окружения: {e}")

    def restart_network_services(self):
        """Перезапуск сетевых служб для применения настроек"""
        try:
            # Перезапускаем NetworkManager
            subprocess.run(['sudo', 'systemctl', 'restart', 'NetworkManager'], 
                          check=False, timeout=10)
            print("✅ NetworkManager перезапущен")
            
            # Перезапускаем systemd-resolved для DNS
            subprocess.run(['sudo', 'systemctl', 'restart', 'systemd-resolved'], 
                          check=False, timeout=5)
            print("✅ systemd-resolved перезапущен")
            
        except Exception as e:
            print(f"⚠️ Ошибка перезапуска сетевых служб: {e}")

    def get_proxy_env(self):
        """Получение переменных окружения для прокси"""
        if self.current_params.get("proxy_enabled", False) and self.current_params.get("proxy_mode") == 'manual':
            host = self.current_params.get("proxy_host", "127.0.0.1")
            port = self.current_params.get("proxy_port", "1080")
            return {
                'http_proxy': f"http://{host}:{port}",
                'https_proxy': f"http://{host}:{port}",
                'HTTP_PROXY': f"http://{host}:{port}",
                'HTTPS_PROXY': f"http://{host}:{port}"
            }
        return {}

    def check_current_proxy(self):
        """Проверка текущих системных настроек прокси"""
        try:
            # Проверяем настройки GNOME
            result = subprocess.run([
                'gsettings', 'get', 'org.gnome.system.proxy', 'mode'
            ], capture_output=True, text=True, check=False)
            
            if result.returncode == 0:
                mode = result.stdout.strip().strip("'")
                if mode == 'manual':
                    # Получаем настройки HTTP прокси
                    host_result = subprocess.run([
                        'gsettings', 'get', 'org.gnome.system.proxy.http', 'host'
                    ], capture_output=True, text=True, check=False)
                    port_result = subprocess.run([
                        'gsettings', 'get', 'org.gnome.system.proxy.http', 'port'
                    ], capture_output=True, text=True, check=False)
                    
                    host = host_result.stdout.strip().strip("'")
                    port = port_result.stdout.strip()
                    
                    # Обновляем конфиг
                    self.current_params["proxy_enabled"] = True
                    self.current_params["proxy_host"] = host
                    self.current_params["proxy_port"] = port
                    self.save_config()
                    
                    print(f"📡 Текущие настройки прокси: {host}:{port}")
                else:
                    self.current_params["proxy_enabled"] = False
                    self.save_config()
                    print("📡 Прокси отключен в системе")
                    
        except Exception as e:
            print(f"❌ Ошибка проверки настроек прокси: {e}")

    def run_command(self, command):
        def run_in_thread():
            try:
                env = os.environ.copy()
                proxy_env = self.get_proxy_env()
                env.update(proxy_env)
                
                result = subprocess.run(
                    ['sudo'] + command.split(),
                    capture_output=True, text=True, timeout=10,
                    env=env
                )
                if result.returncode == 0:
                    self.show_notification("Успех", "Команда выполнена")
                else:
                    self.show_notification("Ошибка", result.stderr)
                time.sleep(1)
                self.update_status()
            except Exception as e:
                self.show_notification("Ошибка", str(e))
        
        threading.Thread(target=run_in_thread, daemon=True).start()

    def start_service(self, widget):
        self.run_command("systemctl start ciadpi.service")

    def stop_service(self, widget):
        self.run_command("systemctl stop ciadpi.service")

    def restart_service(self, widget):
        self.run_command("systemctl restart ciadpi.service")

    def apply_params(self, params):
        """Применение новых параметров"""
        if self.update_service_params(params):
            self.show_notification("Параметры", "Параметры обновлены. Перезапустите сервис.")
            self.restart_service(None)
            self.update_status()
        else:
            self.show_notification("Ошибка", "Не удалось обновить параметры")

    def show_settings(self, widget):
        """Диалог настроек параметров"""
        dialog = Gtk.Dialog(title="Настройки параметров CIADPI", flags=0)
        dialog.add_buttons(Gtk.STOCK_CANCEL, Gtk.ResponseType.CANCEL,
                         Gtk.STOCK_OK, Gtk.ResponseType.OK)
        dialog.set_default_size(600, 150)

        content_area = dialog.get_content_area()
        
        box = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=10)
        box.set_margin_top(10)
        box.set_margin_bottom(10)
        box.set_margin_start(10)
        box.set_margin_end(10)
        
        label = Gtk.Label(label="Параметры запуска CIADPI:")
        entry = Gtk.Entry()
        current_params = self.get_current_service_params()
        entry.set_text(current_params)
        entry.set_width_chars(60)
        
        box.pack_start(label, False, False, 0)
        box.pack_start(entry, False, False, 0)
        
        content_area.pack_start(box, True, True, 0)
        content_area.show_all()
        
        response = dialog.run()
        
        if response == Gtk.ResponseType.OK:
            new_params = entry.get_text().strip()
            if new_params and new_params != current_params:
                self.apply_params(new_params)
        
        dialog.destroy()

    def show_autosearch_dialog(self, widget):
        """Упрощенный диалог автопоиска"""
        if not self.autosearcher:
            self.show_notification("Ошибка", "Модуль автопоиска не доступен")
            return
        
        dialog = Gtk.Dialog(title="Автопоиск параметров", flags=0)
        dialog.add_buttons(Gtk.STOCK_CANCEL, Gtk.ResponseType.CANCEL,
                         "Запуск", Gtk.ResponseType.OK)
        dialog.set_default_size(400, 200)

        content_area = dialog.get_content_area()
        
        box = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=10)
        box.set_margin_top(10)
        box.set_margin_bottom(10)
        box.set_margin_start(10)
        box.set_margin_end(10)
        
        label = Gtk.Label(label="Количество тестов:")
        spin = Gtk.SpinButton.new_with_range(1, 1000, 1)
        spin.set_value(50)
        
        box.pack_start(label, False, False, 0)
        box.pack_start(spin, False, False, 0)
        
        content_area.pack_start(box, True, True, 0)
        content_area.show_all()
        
        response = dialog.run()
        
        if response == Gtk.ResponseType.OK:
            self.run_simple_autosearch(int(spin.get_value()))
        
        dialog.destroy()

    def run_simple_autosearch(self, max_tests):
        """Простой автопоиск"""
        def search_thread():
            try:
                best_params, best_speed = self.autosearcher.find_optimal_params(max_tests, 15)
                if best_params:
                    self.show_notification("Найдены параметры", f"Оптимальные параметры: {best_params}")
                    self.apply_params(best_params)
                else:
                    self.show_notification("Поиск", "Не найдено рабочих параметров")
            except Exception as e:
                self.show_notification("Ошибка", str(e))
        
        threading.Thread(target=search_thread, daemon=True).start()

    def stop_autosearch(self):
        """Остановка автопоиска"""
        if self.autosearcher and hasattr(self, 'is_searching') and self.is_searching:
            self.autosearcher.stop_search()
            self.is_searching = False

    def show_history(self, widget):
        """Показать историю тестирования"""
        if not self.autosearcher:
            self.show_notification("Ошибка", "Модуль истории не доступен")
            return
        
        history = self.autosearcher.get_history(20)
        
        dialog = Gtk.Dialog(title="История тестирования", flags=0)
        dialog.add_buttons(Gtk.STOCK_CLOSE, Gtk.ResponseType.CLOSE)
        dialog.set_default_size(600, 400)
        
        content_area = dialog.get_content_area()
        scroll = Gtk.ScrolledWindow()
        
        # Простой текстовый вывод
        text_view = Gtk.TextView()
        text_view.set_editable(False)
        text_view.set_wrap_mode(Gtk.WrapMode.WORD)
        
        buffer = text_view.get_buffer()
        text = "История тестирования:\n\n"
        
        for item in history:
            status = "✅" if item.get("success", False) else "❌"
            text += f"{status} {item['params']}\n"
        
        buffer.set_text(text)
        scroll.add(text_view)
        content_area.pack_start(scroll, True, True, 0)
        content_area.show_all()
        
        dialog.run()
        dialog.destroy()

    def show_logs(self, widget):
        try:
            subprocess.Popen([
                'gnome-terminal', '--', 
                'bash', '-c', 
                'echo "Логи сервиса ciadpi:"; '
                'journalctl -u ciadpi.service -n 50 --no-pager; '
                'echo ""; '
                'read -p "Нажмите Enter для выхода"'
            ])
        except:
            try:
                subprocess.Popen([
                    'xterm', '-e',
                    'echo "Логи сервиса ciadpi:"; '
                    'journalctl -u ciadpi.service -n 50 --no-pager; '
                    'echo ""; '
                    'read -p "Нажмите Enter для выхода"'
                ])
            except:
                self.show_notification("Ошибка", "Не удалось открыть терминал")

    def show_help(self, widget):
        """Окно справки по параметрам"""
        help_text = "Справка по параметрам CIADPI\n\nИспользуйте настройки для изменения параметров запуска."
        
        dialog = Gtk.Dialog(title="Справка", flags=0)
        dialog.add_buttons(Gtk.STOCK_OK, Gtk.ResponseType.OK)
        dialog.set_default_size(400, 300)
        
        content_area = dialog.get_content_area()
        scroll = Gtk.ScrolledWindow()
        
        text_view = Gtk.TextView()
        text_view.set_editable(False)
        text_view.set_wrap_mode(Gtk.WrapMode.WORD)
        
        buffer = text_view.get_buffer()
        buffer.set_text(help_text)
        
        scroll.add(text_view)
        content_area.pack_start(scroll, True, True, 0)
        content_area.show_all()
        
        dialog.run()
        dialog.destroy()

    def show_about(self, widget):
        """Окно 'О программе'"""
        about_text = "CIADPI Advanced Indicator\n\nУправление сервисом обхода DPI"
        
        dialog = Gtk.Dialog(title="О программе", flags=0)
        dialog.add_buttons(Gtk.STOCK_OK, Gtk.ResponseType.OK)
        dialog.set_default_size(300, 200)
        
        content_area = dialog.get_content_area()
        
        label = Gtk.Label(label=about_text)
        content_area.pack_start(label, True, True, 0)
        content_area.show_all()
        
        dialog.run()
        dialog.destroy()

    def show_notification(self, title, message):
        try:
            subprocess.Popen(['notify-send', '-t', '5000', title, message])
        except:
            pass

    def exit_app(self, widget):
        if hasattr(self, 'is_searching') and self.is_searching:
            self.stop_autosearch()
        Gtk.main_quit()

if __name__ == "__main__":
    # Запускаем как демон
    import signal
    signal.signal(signal.SIGINT, signal.SIG_DFL)
    
    indicator = AdvancedTrayIndicator()
    Gtk.main()

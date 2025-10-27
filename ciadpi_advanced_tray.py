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
from typing import Tuple, List, Dict

gi.require_version('Gtk', '3.0')
gi.require_version('AppIndicator3', '0.1')
from gi.repository import Gtk, Gdk, AppIndicator3, GLib

try:
    import sys
    sys.path.append(str(Path.home() / '.local' / 'bin'))
    from ciadpi_whitelist import WhitelistManager
    WHITELIST_AVAILABLE = True
    print("✅ Модуль белого списка загружен")
except ImportError as e:
    print(f"❌ Модуль белого списка не доступен: {e}")
    WHITELIST_AVAILABLE = False
    WhitelistManager = None    

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
        self.whitelist_file = Path.home() / '.config' / 'ciadpi' / 'whitelist.json'
        self.whitelist = self.load_whitelist()

        # УПРОЩЕННЫЕ НАСТРОЙКИ ПРОКСИ
        self.original_system_proxy = None  # Настройки которые были в системе ДО нас
        self.we_changed_proxy = False      # Флаг что мы меняли прокси

        if WHITELIST_AVAILABLE:
            self.whitelist_manager = WhitelistManager()
        else:
            self.whitelist_manager = None        

        # ОДИН таймер для проверки прокси
        GLib.timeout_add(5000, self.check_current_proxy)

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
        GLib.timeout_add(2000, self.initialize_indicator)
        
        # ОДИН таймер для проверки статуса
        GLib.timeout_add_seconds(3, self.update_status)
        
        # ОДИН таймер для восстановления наших настроек при запуске
        GLib.timeout_add(3000, self.restore_our_proxy_on_startup)
        
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
            "current_params": self.default_params,
            "auto_disable_proxy": False,
            "we_changed_proxy": False
        }
        
        try:
            self.config_file.parent.mkdir(exist_ok=True)
            if self.config_file.exists():
                with open(self.config_file, 'r', encoding='utf-8') as f:
                    config = json.load(f)
                    for key in default_config:
                        if key not in config:
                            config[key] = default_config[key]
                    
                    # ВОССТАНАВЛИВАЕМ ФЛАГ ИЗ КОНФИГА
                    self.we_changed_proxy = config.get("we_changed_proxy", False)
                    print(f"🔍 ЗАГРУЖЕН КОНФИГ: we_changed_proxy = {self.we_changed_proxy}")
                    return config
        except Exception as e:
            print(f"Ошибка загрузки конфига: {e}")
            
        return default_config

    def save_config(self):
        """Сохранение конфигурации в файл"""
        try:
            # СОХРАНЯЕМ ФЛАГ В КОНФИГ
            self.current_params["we_changed_proxy"] = self.we_changed_proxy
            
            with open(self.config_file, 'w', encoding='utf-8') as f:
                json.dump(self.current_params, f, indent=2, ensure_ascii=False)
            
            print(f"💾 КОНФИГ СОХРАНЕН: we_changed_proxy = {self.we_changed_proxy}")
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
        """Обновление параметров в systemd сервисе - УНИВЕРСАЛЬНАЯ ВЕРСИЯ"""
        try:
            print(f"🔄 Обновление параметров: {new_params}")
            
            # Получаем данные пользователя динамически
            username = os.environ.get('USER')
            home_dir = Path.home()
            byedpi_dir = home_dir / 'byedpi'
            ciadpi_binary = byedpi_dir / 'ciadpi'
            
            # Проверяем что бинарник существует
            if not ciadpi_binary.exists():
                error_msg = f"Бинарник ciadpi не найден: {ciadpi_binary}"
                print(f"❌ {error_msg}")
                self.show_notification("Ошибка", error_msg)
                return False
            
            # Останавливаем сервис
            print("⏹️ Останавливаем сервис...")
            stop_result = subprocess.run(
                ['sudo', 'systemctl', 'stop', 'ciadpi.service'], 
                capture_output=True, text=True, timeout=10
            )
            
            if stop_result.returncode != 0:
                print(f"⚠️ Предупреждение при остановке: {stop_result.stderr}")
            
            time.sleep(2)
            
            # Удаляем override директорию если есть (избегаем конфликтов)
            override_dir = Path('/etc/systemd/system/ciadpi.service.d')
            if override_dir.exists():
                subprocess.run(['sudo', 'rm', '-rf', str(override_dir)], check=False)
                print("🗑️ Удалена override директория")
            
            # Создаем service файл с динамическими путями
            service_content = f"""[Unit]
    Description=CIADPI DPI Bypass Service
    After=network.target
    Wants=network.target

    [Service]
    Type=simple
    User={username}
    WorkingDirectory={byedpi_dir}
    ExecStart={ciadpi_binary} {new_params}
    Restart=on-failure
    RestartSec=5
    TimeoutStartSec=30

    [Install]
    WantedBy=multi-user.target
    """
            
            # Записываем временный файл
            temp_file = Path('/tmp/ciadpi_temp.service')
            with open(temp_file, 'w', encoding='utf-8') as f:
                f.write(service_content)
            
            # Копируем с правами root
            print("📝 Обновляем service файл...")
            copy_result = subprocess.run(
                ['sudo', 'cp', str(temp_file), '/etc/systemd/system/ciadpi.service'],
                capture_output=True, text=True, check=True
            )
            
            subprocess.run(['sudo', 'systemctl', 'daemon-reload'], check=True)
            
            # Обновляем конфиг
            self.current_params["current_params"] = new_params
            self.current_params["params"] = new_params
            self.save_config()
            
            # Запускаем сервис
            print("▶️ Запускаем сервис...")
            start_result = subprocess.run(
                ['sudo', 'systemctl', 'start', 'ciadpi.service'],
                capture_output=True, text=True, check=True
            )
            
            # Проверяем статус
            time.sleep(3)
            status_result = subprocess.run(
                ['systemctl', 'is-active', 'ciadpi.service'],
                capture_output=True, text=True
            )
            
            if status_result.stdout.strip() == 'active':
                print("✅ Параметры успешно обновлены")
                self.show_notification("Успех", "Параметры обновлены и сервис запущен")
                return True
            else:
                # Если сервис не запустился, показываем ошибку
                error_msg = "Сервис не запустился после обновления параметров"
                print(f"❌ {error_msg}")
                
                # Получаем последние логи для диагностики
                log_result = subprocess.run(
                    ['journalctl', '-u', 'ciadpi.service', '-n', '10', '--no-pager'],
                    capture_output=True, text=True
                )
                print("Последние логи сервиса:")
                print(log_result.stdout)
                
                self.show_notification("Ошибка", f"{error_msg}\nПроверьте логи")
                return False
            
        except subprocess.CalledProcessError as e:
            error_msg = f"Ошибка выполнения команды: {e}\nStderr: {e.stderr}"
            print(f"❌ {error_msg}")
            self.show_notification("Ошибка", "Не удалось выполнить системную команду")
            return False
            
        except Exception as e:
            error_msg = f"Общая ошибка: {e}"
            print(f"❌ {error_msg}")
            self.show_notification("Ошибка", f"Не удалось обновить параметры: {e}")
            return False
        
    # Методы для работы с белым списком:
    def load_whitelist(self):
        """Загрузка белого списка"""
        default_whitelist = {
            "enabled": False,
            "domains": [
                "localhost",
                "127.0.0.1",
                "192.168.1.1",
                "*.local"
            ],
            "ips": [
                "192.168.1.0/24",
                "10.0.0.0/8"
            ],
            "bypass_proxy": True,
            "bypass_dpi": False
        }
        
        try:
            self.whitelist_file.parent.mkdir(exist_ok=True)
            if self.whitelist_file.exists():
                with open(self.whitelist_file, 'r', encoding='utf-8') as f:
                    whitelist = json.load(f)
                    # Проверяем что все необходимые поля есть
                    for key in default_whitelist:
                        if key not in whitelist:
                            whitelist[key] = default_whitelist[key]
                    return whitelist
        except Exception as e:
            print(f"Ошибка загрузки белого списка: {e}")
            
        return default_whitelist

    def save_whitelist(self):
        """Сохранение белого списка"""
        try:
            with open(self.whitelist_file, 'w', encoding='utf-8') as f:
                json.dump(self.whitelist, f, indent=2, ensure_ascii=False)
            return True
        except Exception as e:
            print(f"Ошибка сохранения белого списка: {e}")
            return False

    def is_whitelisted(self, host):
        """Проверка находится ли хост в белом списке"""
        if not self.whitelist.get("enabled", False):
            return False
        
        # Проверка точного совпадения домена
        if host in self.whitelist.get("domains", []):
            return True
        
        # Проверка по маске домена
        for domain_pattern in self.whitelist.get("domains", []):
            if domain_pattern.startswith('*.'):
                pattern = domain_pattern[2:]
                if host.endswith(pattern) or host == pattern:
                    return True
        
        # TODO: Добавить проверку IP и CIDR при необходимости
        return False

    def show_whitelist_dialog(self, widget=None):
        ###
        print("DEBUG: show_whitelist_dialog called")
        try:        
            ###
            """Диалог управления белым списком"""
            dialog = Gtk.Dialog(title="Управление белым списком", flags=0)
            dialog.add_buttons(Gtk.STOCK_CANCEL, Gtk.ResponseType.CANCEL,
                            Gtk.STOCK_OK, Gtk.ResponseType.OK)
            dialog.set_default_size(600, 500)

            content_area = dialog.get_content_area()
            
            box = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=10)
            box.set_margin_top(10)
            box.set_margin_bottom(10)
            box.set_margin_start(10)
            box.set_margin_end(10)
            
            # Включение белого списка
            enable_check = Gtk.CheckButton(label="Включить белый список")
            enable_check.set_active(self.whitelist.get("enabled", False))
            
            # Настройки исключений
            exceptions_frame = Gtk.Frame(label="Исключения из проксирования")
            exceptions_box = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=5)
            exceptions_box.set_margin_top(5)
            exceptions_box.set_margin_bottom(5)
            exceptions_box.set_margin_start(5)
            exceptions_box.set_margin_end(5)
            
            bypass_proxy_check = Gtk.CheckButton(label="Исключить из проксирования")
            bypass_proxy_check.set_active(self.whitelist.get("bypass_proxy", True))
            
            bypass_dpi_check = Gtk.CheckButton(label="Исключить из DPI обхода")
            bypass_dpi_check.set_active(self.whitelist.get("bypass_dpi", False))
            bypass_dpi_check.set_sensitive(False)  # Пока не реализовано
            
            exceptions_box.pack_start(bypass_proxy_check, False, False, 0)
            exceptions_box.pack_start(bypass_dpi_check, False, False, 0)
            exceptions_frame.add(exceptions_box)
            
            # Домены
            domains_frame = Gtk.Frame(label="Домены и хосты (по одному на строку)")
            domains_scroll = Gtk.ScrolledWindow()
            domains_scroll.set_min_content_height(150)
            
            domains_text_view = Gtk.TextView()
            domains_text_view.set_wrap_mode(Gtk.WrapMode.WORD)
            domains_buffer = domains_text_view.get_buffer()
            
            # Загружаем текущие домены
            domains_text = "\n".join(self.whitelist.get("domains", []))
            domains_buffer.set_text(domains_text)
            
            domains_scroll.add(domains_text_view)
            domains_frame.add(domains_scroll)
            
            # IP-адреса
            ips_frame = Gtk.Frame(label="IP-адреса и сети CIDR (по одному на строку)")
            ips_scroll = Gtk.ScrolledWindow()
            ips_scroll.set_min_content_height(100)
            
            ips_text_view = Gtk.TextView()
            ips_text_view.set_wrap_mode(Gtk.WrapMode.WORD)
            ips_buffer = ips_text_view.get_buffer()
            
            # Загружаем текущие IP
            ips_text = "\n".join(self.whitelist.get("ips", []))
            ips_buffer.set_text(ips_text)
            
            ips_scroll.add(ips_text_view)
            ips_frame.add(ips_scroll)
            
            # Информация
            info_label = Gtk.Label()
            info_label.set_markup(
                "<small>Подсказки:\n"
                "• <tt>example.com</tt> - точное совпадение\n"
                "• <tt>*.example.com</tt> - все поддомены\n" 
                "• <tt>192.168.1.0/24</tt> - подсеть CIDR\n"
                "• <tt>localhost</tt>, <tt>127.0.0.1</tt> - локальные адреса</small>"
            )
            info_label.set_sensitive(False)
            
            box.pack_start(enable_check, False, False, 0)
            box.pack_start(exceptions_frame, False, False, 0)
            box.pack_start(domains_frame, True, True, 0)
            box.pack_start(ips_frame, True, True, 0)
            box.pack_start(info_label, False, False, 0)
            
            content_area.pack_start(box, True, True, 0)
            content_area.show_all()
            
            response = dialog.run()
            
            if response == Gtk.ResponseType.OK:
                # Сохраняем настройки
                self.whitelist["enabled"] = enable_check.get_active()
                self.whitelist["bypass_proxy"] = bypass_proxy_check.get_active()
                self.whitelist["bypass_dpi"] = bypass_dpi_check.get_active()
                
                # Сохраняем домены
                domains_start, domains_end = domains_buffer.get_bounds()
                domains_text = domains_buffer.get_text(domains_start, domains_end, True)
                self.whitelist["domains"] = [
                    domain.strip() for domain in domains_text.split('\n') 
                    if domain.strip()
                ]
                
                # Сохраняем IP
                ips_start, ips_end = ips_buffer.get_bounds()
                ips_text = ips_buffer.get_text(ips_start, ips_end, True)
                self.whitelist["ips"] = [
                    ip.strip() for ip in ips_text.split('\n') 
                    if ip.strip()
                ]
                
                if self.save_whitelist():
                    self.show_notification("Белый список", "Настройки сохранены")
                    
                    # Применяем настройки прокси если белый список включен
                    if self.whitelist["enabled"] and self.whitelist["bypass_proxy"]:
                        self.apply_whitelist_proxy_settings()
                else:
                    self.show_notification("Ошибка", "Не удалось сохранить белый список")
###
        except Exception as e:
            print(f"ERROR in show_whitelist_dialog: {e}")
            import traceback
            traceback.print_exc()
###
        dialog.destroy()

    def apply_whitelist_proxy_settings(self):
        """Применение настроек прокси с учетом белого списка"""
        if not self.whitelist.get("enabled", False) or not self.whitelist.get("bypass_proxy", True):
            return
        
        try:
            # Получаем текущие настройки прокси
            current_settings = self.get_system_proxy_settings()
            
            if current_settings.get('mode') == 'manual':
                # Формируем строку исключений для прокси
                ignore_hosts = self.whitelist.get("domains", []) + self.whitelist.get("ips", [])
                
                if ignore_hosts:
                    # Устанавливаем игнорируемые хосты
                    ignore_string = ",".join(ignore_hosts)
                    subprocess.run([
                        'gsettings', 'set', 'org.gnome.system.proxy', 'ignore-hosts', 
                        f"['{ignore_string}']"
                    ], check=False)
                    
                    log_debug(f"Применен белый список прокси: {ignore_string}")
                    
        except Exception as e:
            print(f"Ошибка применения белого списка прокси: {e}")

    def get_proxy_env_with_whitelist(self):
        """Получение переменных окружения для прокси с учетом белого списка"""
        env_vars = {}
        
        if (self.current_params.get("proxy_enabled", False) and 
            self.current_params.get("proxy_mode") == 'manual' and
            not self.whitelist.get("enabled", False)):
            
            host = self.current_params.get("proxy_host", "127.0.0.1")
            port = self.current_params.get("proxy_port", "1080")
            
            if host:  # Если хост не пустой
                proxy_url = f"http://{host}:{port}"
            else:
                proxy_url = f"http://:{port}"  # Формат с пустым хостом
                
            env_vars = {
                'http_proxy': proxy_url,
                'https_proxy': proxy_url,
                'ftp_proxy': proxy_url,
                'HTTP_PROXY': proxy_url,
                'HTTPS_PROXY': proxy_url,
                'FTP_PROXY': proxy_url,
                'no_proxy': ','.join(self.whitelist.get("domains", []) + self.whitelist.get("ips", [])),
                'NO_PROXY': ','.join(self.whitelist.get("domains", []) + self.whitelist.get("ips", []))
            }
        
        return env_vars      

    # МЕТОД для отключения прокси
    def disable_system_proxy(self):
        """Полное отключение системного прокси с восстановлением оригинальных настроек"""
        try:
            print("🔌 Отключаем системный прокси...")
            
            # Восстанавливаем системные настройки
            success = self.restore_system_proxy_backup()
            
            if success:
                self.we_changed_proxy = False
                self.show_notification("Прокси", "Настройки прокси восстановлены")
            else:
                # Fallback: просто отключаем если восстановление не удалось
                subprocess.run([
                    'gsettings', 'set', 'org.gnome.system.proxy', 'mode', 'none'
                ], check=False)
                self.show_notification("Прокси", "Прокси отключен")
                
            return success
            
        except Exception as e:
            print(f"❌ Ошибка отключения прокси: {e}")
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

        # БЕЛЫЙ СПИСОК
        whitelist_item = Gtk.MenuItem(label="📝 Белый список")
        whitelist_item.connect("activate", self.show_whitelist_dialog)
        menu.append(whitelist_item)        
        
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

        # ЧЕКБОКС для автоматического отключения прокси
        auto_disable_check = Gtk.CheckButton(label="❌ Автоматически отключать прокси при выходе")
        auto_disable_check.set_active(self.current_params.get("auto_disable_proxy", False))
        auto_disable_check.set_tooltip_text("При остановке сервиса прокси будет автоматически отключен в системе")
                
        # Добавляем в UI
        box.pack_start(auto_disable_check, False, False, 0)                
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
            
            proxy_host = host_entry.get_text().strip()
            proxy_port = port_entry.get_text().strip()
            
            if not proxy_port.isdigit():
                self.show_notification("Ошибка", "Порт должен быть числом")
                dialog.destroy()
                return
            
            self.current_params["auto_disable_proxy"] = auto_disable_check.get_active()
            print(f"💾 Сохраняем auto_disable_proxy = {self.current_params['auto_disable_proxy']}")            
            
            # СОХРАНЯЕМ НАШИ НАСТРОЙКИ В КОНФИГ
            self.current_params["proxy_enabled"] = selected_mode != 'none'
            self.current_params["proxy_host"] = proxy_host
            self.current_params["proxy_port"] = proxy_port
            self.current_params["proxy_mode"] = selected_mode
            
            # ⭐ ОБНОВЛЯЕМ И СОХРАНЯЕМ ФЛАГ
            if selected_mode == 'manual' and not self.we_changed_proxy:
                self.we_changed_proxy = True
            elif selected_mode == 'none' and self.we_changed_proxy:
                self.we_changed_proxy = False
                
            self.current_params["we_changed_proxy"] = self.we_changed_proxy
            self.save_config()
            
            # ЕСЛИ МЫ ВКЛЮЧАЕМ ПРОКСИ - СОХРАНЯЕМ СИСТЕМНЫЕ НАСТРОЙКИ
            if selected_mode == 'manual' and not self.we_changed_proxy:
                self.save_system_proxy_backup()
                self.we_changed_proxy = True
                self.save_config()  # ⭐ СОХРАНЯЕМ КОНФИГ С ФЛАГОМ
            
            # ЕСЛИ МЫ ВЫКЛЮЧАЕМ ПРОКСИ - ВОССТАНАВЛИВАЕМ СИСТЕМНЫЕ НАСТРОЙКИ
            elif selected_mode == 'none' and self.we_changed_proxy:
                self.restore_system_proxy_backup()
                self.we_changed_proxy = False
                self.save_config()  # ⭐ СОХРАНЯЕМ КОНФИГ С ФЛАГОМ
            else:
                # Просто применяем настройки
                success = self.apply_system_proxy(selected_mode, proxy_host, proxy_port)
            
            display_host = "ПУСТОЙ" if not proxy_host else proxy_host
            self.show_notification("Прокси", f"Прокси {selected_mode} применен")
        
        dialog.destroy()

    def get_system_proxy_settings(self):
        """Получение текущих системных настроек прокси"""
        settings = {
            'mode': 'none',
            'http_host': '',
            'http_port': '8080',  # дефолтный порт
            'ignore_hosts': '[]'
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
                    
                    # Получаем игнорируемые хосты
                    ignore_result = subprocess.run([
                        'gsettings', 'get', 'org.gnome.system.proxy', 'ignore-hosts'
                    ], capture_output=True, text=True, check=False)
                    
                    if ignore_result.returncode == 0:
                        settings['ignore_hosts'] = ignore_result.stdout.strip()
                        
            elif mode == 'auto':
                # Для автоматического режима можно сохранить PAC URL
                pac_result = subprocess.run([
                    'gsettings', 'get', 'org.gnome.system.proxy', 'autoconfig-url'
                ], capture_output=True, text=True, check=False)
                
                if pac_result.returncode == 0:
                    settings['pac_url'] = pac_result.stdout.strip().strip("'")
                            
        except Exception as e:
            print(f"❌ Ошибка получения настроек прокси: {e}")
        
        return settings

    def apply_system_proxy(self, mode, host, port):
        """Применение системных настроек прокси через NetworkManager"""
        try:
            # Только применяем настройки, не сохраняем оригинальные здесь
            # Оригинальные сохраняются только при первом включении нашего прокси
            
            subprocess.run([
                'gsettings', 'set', 'org.gnome.system.proxy', 'mode', mode
            ], check=False)
            
            if mode == 'manual':
                # Используем ПУСТОЕ значение если host пустой
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
                pass

            # ПРИМЕНЯЕМ БЕЛЫЙ СПИСОК ДЛЯ ИГНОРИРУЕМЫХ ХОСТОВ
            if self.whitelist.get("enabled", False) and self.whitelist.get("bypass_proxy", True):
                ignore_hosts = self.whitelist.get("domains", []) + self.whitelist.get("ips", [])
                if ignore_hosts:
                    ignore_string = "[" + ",".join([f"'{host}'" for host in ignore_hosts]) + "]"
                    subprocess.run([
                        'gsettings', 'set', 'org.gnome.system.proxy', 'ignore-hosts', 
                        ignore_string
                    ], check=False)
                    print(f"✅ Белый список применен: {len(ignore_hosts)} записей")
            else:
                # Очищаем игнорируемые хосты если белый список выключен
                subprocess.run([
                    'gsettings', 'reset', 'org.gnome.system.proxy', 'ignore-hosts'
                ], check=False)            
                
            host_display = "ПУСТОЙ" if not host else host
            print(f"✅ Системный прокси установлен: {mode} Хост: {host_display} Порт: {port}")
            
            # Применяем переменные окружения
            self.apply_environment_proxy(mode, host, port)
            
            # Перезапускаем NetworkManager для применения настроек
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

    # Восстановление переменных окружения
    def restore_original_environment(self):
        """Восстановление оригинальных переменных окружения"""
        try:
            # Удаляем наш файл с настройками прокси
            env_file = Path.home() / '.proxy_env'
            if env_file.exists():
                env_file.unlink()
                print("✅ Удалены наши переменные окружения прокси")
                
            # TODO: Можно добавить восстановление оригинальных переменных окружения
            # если они были сохранены
            
        except Exception as e:
            print(f"⚠️ Ошибка восстановления переменных окружения: {e}")       

    # Четкое сохранение системных настроек
    def save_system_proxy_backup(self):
        """Сохраняет текущие системные настройки как резервную копию"""
        self.original_system_proxy = self.get_system_proxy_settings()
        print("💾 Создана резервная копия системных настроек прокси:")
        print(f"   Режим: {self.original_system_proxy.get('mode')}")
        print(f"   Хост: {self.original_system_proxy.get('http_host')}")
        print(f"   Порт: {self.original_system_proxy.get('http_port')}")

    # Сохранение наших настроек
    def save_our_proxy_settings(self):
        """Сохраняет наши настройки прокси из конфига"""
        self.our_proxy_settings = {
            'mode': self.current_params.get("proxy_mode", "none"),
            'host': self.current_params.get("proxy_host", ""),
            'port': self.current_params.get("proxy_port", "1080"),
            'enabled': self.current_params.get("proxy_enabled", False)
        }
        print("💾 Сохранены наши настройки прокси для восстановления")

    # Восстановление наших настроек при запуске
    def restore_our_proxy_on_startup(self):
        """Восстанавливаем наши настройки прокси при запуске приложения"""
        try:
            # Проверяем статус сервиса
            result = subprocess.run(
                ['systemctl', 'is-active', 'ciadpi.service'],
                capture_output=True, text=True, timeout=2
            )
            service_running = result.stdout.strip() == 'active'
            
            # Если сервис запущен И у нас есть настройки прокси - восстанавливаем
            if (service_running and 
                self.current_params.get("proxy_enabled", False) and 
                self.current_params.get("proxy_mode") == 'manual'):
                
                print("🔄 Восстанавливаем наши настройки прокси при запуске...")
                print(f"🔍 Флаг we_changed_proxy: {self.we_changed_proxy}")
                
                # ⭐ ВОССТАНАВЛИВАЕМ ФЛАГ ЕСЛИ ОН БЫЛ УСТАНОВЛЕН
                if not self.we_changed_proxy:
                    self.we_changed_proxy = True
                    self.save_config()
                    print("💾 Флаг we_changed_proxy восстановлен и сохранен")
                
                host = self.current_params.get("proxy_host", "")
                port = self.current_params.get("proxy_port", "1080")
                
                success = self.apply_system_proxy('manual', host, port)
                
                if success:
                    print("✅ Наши настройки прокси восстановлены при запуске")
                else:
                    print("❌ Не удалось восстановить настройки при запуске")
                    
        except Exception as e:
            print(f"⚠️ Ошибка восстановления настроек при запуске: {e}")
        
        return False  

    # Восстановление системных настроек
    def restore_system_proxy_backup(self):
        """Восстанавливает оригинальные системные настройки"""
        try:
            if not self.original_system_proxy:
                print("ℹ️ Нет резервной копии системных настроек")
                return True
                
            original_mode = self.original_system_proxy.get('mode', 'none')
            original_host = self.original_system_proxy.get('http_host', '')
            original_port = self.original_system_proxy.get('http_port', '1080')
            
            print("🔄 Восстанавливаем системные настройки прокси...")
            
            # Применяем оригинальные настройки
            success = self.apply_system_proxy(original_mode, original_host, original_port)
            
            if success:
                print("✅ Системные настройки прокси восстановлены")
                # Очищаем переменные окружения
                self.restore_original_environment()
            return success
            
        except Exception as e:
            print(f"❌ Ошибка восстановления системных настроек: {e}")
            return False                  

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
        """Запуск сервиса с восстановлением наших настроек"""
        def start_with_proxy_restore():
            try:
                # Запускаем сервис
                result = subprocess.run(
                    ['sudo', 'systemctl', 'start', 'ciadpi.service'],
                    capture_output=True, text=True, timeout=10
                )
                
                if result.returncode == 0:
                    # После запуска сервиса восстанавливаем НАШИ настройки
                    time.sleep(2)
                    
                    if (self.current_params.get("proxy_enabled", False) and 
                        self.current_params.get("proxy_mode") == 'manual'):
                        
                        # ВОССТАНАВЛИВАЕМ ФЛАГ если у нас есть настройки прокси
                        if not self.we_changed_proxy:
                            self.save_system_proxy_backup()
                            self.we_changed_proxy = True
                            self.save_config()  # ⭐ СОХРАНЯЕМ КОНФИГ С ФЛАГОМ
                            print("💾 Флаг we_changed_proxy сохранен в конфиг")
                        
                        host = self.current_params.get("proxy_host", "")
                        port = self.current_params.get("proxy_port", "1080")
                        self.apply_system_proxy('manual', host, port)
                        self.show_notification("Сервис запущен", "Наши настройки прокси применены")
                    else:
                        self.show_notification("Сервис запущен", "Сервис запущен успешно")
                        
                else:
                    self.show_notification("Ошибка", result.stderr)
                    
                time.sleep(1)
                self.update_status()
                
            except Exception as e:
                self.show_notification("Ошибка", str(e))
        
        threading.Thread(target=start_with_proxy_restore, daemon=True).start()

    def stop_service(self, widget):
        """Остановка сервиса с правильным управлением прокси"""
        if self.current_params.get("auto_disable_proxy", False) and self.we_changed_proxy:
            # Автоотключение включено И мы меняли прокси
            def stop_with_proxy_restore():
                try:
                    # Восстанавливаем системные настройки
                    self.restore_system_proxy_backup()
                    
                    # Останавливаем сервис
                    result = subprocess.run(
                        ['sudo', 'systemctl', 'stop', 'ciadpi.service'],
                        capture_output=True, text=True, timeout=10
                    )
                    
                    if result.returncode == 0:
                        self.show_notification("Сервис остановлен", "Системные настройки прокси восстановлены")
                    else:
                        self.show_notification("Ошибка", result.stderr)
                        
                    time.sleep(1)
                    self.update_status()
                    
                except Exception as e:
                    self.show_notification("Ошибка", str(e))
            
            threading.Thread(target=stop_with_proxy_restore, daemon=True).start()
        else:
            # Обычная остановка без изменения прокси
            self.run_command("systemctl stop ciadpi.service")

    def restart_service(self, widget):
        self.run_command("systemctl restart ciadpi.service")

    def validate_params(self, params: str) -> Tuple[bool, str]:
        """Проверка параметров ciadpi с детальными сообщениями об ошибках"""
        if not params.strip():
            return True, ""
        
        # Все допустимые параметры из документации
        valid_params = {
            # Основные
            '-i', '-p', '-D', '-w', '-E', '-c', '-I', '-b', '-g', '-N', '-U', '-F',
            # Автоматический режим  
            '-A', '-L', '-u', '-y', '-T',
            # Протоколы
            '-K',
            # Ограничители
            '-H', '-j', '-V', '-R',
            # Методы обхода
            '-s', '-d', '-o', '-q', '-f', '-r',
            # Модификации
            '-t', '-S', '-O', '-l', '-e', '-n', '-Q', '-M', '-a', '-Y'
        }
        
        # Методы обхода (-o1 до -o25)
        obfuscation_methods = {f'-o{i}' for i in range(1, 26)}
        valid_params.update(obfuscation_methods)
        
        parts = params.split()
        unknown_params = []
        
        i = 0
        while i < len(parts):
            part = parts[i]
            
            # Проверяем основные параметры
            if part in valid_params:
                i += 1
                continue
                
            # Проверяем методы обхода с суффиксами (-o1+s, -o25+m и т.д.)
            if re.match(r'^-o\d+[\+sme]*$', part):
                i += 1
                continue
                
            # Проверяем специальные форматы (1+s, 2+s, o--tlsrec)
            if part in ['1+s', '2+s', '3+s', '-At', 'o--tlsrec']:
                i += 1
                continue
                
            # Параметры со значениями (пропускаем следующую часть)
            if part in ['-i', '-p', '-w', '-c', '-I', '-b', '-g', '-u', '-T', 
                    '-A', '-L', '-K', '-H', '-j', '-V', '-R', '-s', '-d', 
                    '-o', '-q', '-f', '-r', '-t', '-O', '-l', '-e', '-n', '-a']:
                if i + 1 < len(parts):
                    i += 2  # Пропускаем параметр и его значение
                    continue
            
            # Если дошли сюда - параметр неизвестен
            unknown_params.append(part)
            i += 1
        
        if unknown_params:
            error_msg = f"Неизвестные параметры: {', '.join(unknown_params)}\n"
            error_msg += "Используйте только параметры из документации ciadpi"
            return False, error_msg
        
        return True, ""

    def show_settings(self, widget=None):
        ###
        print("DEBUG: show_settings called")
        try:        
###            
            """Диалог настроек параметров"""
            dialog = Gtk.Dialog(title="Настройки параметров CIADPI", flags=0)
            dialog.add_buttons(Gtk.STOCK_CANCEL, Gtk.ResponseType.CANCEL,
                            Gtk.STOCK_OK, Gtk.ResponseType.OK)
            dialog.set_default_size(700, 400)

            content_area = dialog.get_content_area()
            
            main_box = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=10)
            main_box.set_margin_top(10)
            main_box.set_margin_bottom(10)
            main_box.set_margin_start(10)
            main_box.set_margin_end(10)
            
            # Основное поле ввода
            label = Gtk.Label(label="Параметры запуска CIADPI:")
            label.set_xalign(0)
            entry = Gtk.Entry()
            current_params = self.get_current_service_params()
            entry.set_text(current_params)
            entry.set_width_chars(70)
            
            # Фрейм с примерами
            examples_frame = Gtk.Frame()
            examples_frame.set_shadow_type(Gtk.ShadowType.IN)
            
            examples_box = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=5)
            examples_box.set_margin_top(10)
            examples_box.set_margin_bottom(10)
            examples_box.set_margin_start(10)
            examples_box.set_margin_end(10)
            
            examples_title = Gtk.Label()
            examples_title.set_markup("<b>Примеры параметров (кликните для копирования):</b>")
            examples_title.set_xalign(0)
            examples_box.pack_start(examples_title, False, False, 0)
            
            # Список примеров
            examples = [
                "-o1 -o25+s -T3 -At o--tlsrec 1+s",
                "-o2 -o15+s -T2 -At o--tlsrec", 
                "-o1 -o5+s -T1 -At",
                "-o3 -o20+s -T3 -At o--tlsrec 2+s",
                "-o4 -o10+m -T5 -A torst -L 1"
            ]
            
            for example in examples:
                example_box = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=5)
                
                # Поле с примером (выделяемое и копируемое)
                example_entry = Gtk.Entry()
                example_entry.set_text(example)
                example_entry.set_editable(False)
                example_entry.set_can_focus(False)
                example_entry.set_hexpand(True)
                
                # Стиль для поля примера
                example_entry.set_size_request(400, 30)
                example_entry.override_background_color(Gtk.StateFlags.NORMAL, 
                                                    Gdk.RGBA(0.95, 0.95, 0.95, 1.0))
                example_entry.override_color(Gtk.StateFlags.NORMAL, 
                                        Gdk.RGBA(0.2, 0.2, 0.2, 1.0))
                
                # Кнопка копирования
                copy_btn = Gtk.Button.new_from_icon_name("edit-copy-symbolic", Gtk.IconSize.BUTTON)
                copy_btn.set_tooltip_text("Копировать в буфер обмена")
                copy_btn.connect("clicked", self.on_copy_example, example)
                
                # Клик по полю тоже копирует
                example_entry.connect("button-press-event", self.on_example_clicked, example)
                
                example_box.pack_start(example_entry, True, True, 0)
                example_box.pack_start(copy_btn, False, False, 0)
                examples_box.pack_start(example_box, False, False, 0)
            
            examples_frame.add(examples_box)
            
            # Подсказка
            hint_label = Gtk.Label()
            hint_label.set_markup("<small>💡 Параметры проверяются автоматически при сохранении</small>")
            hint_label.set_xalign(0)
            hint_label.set_sensitive(False)
            
            main_box.pack_start(label, False, False, 0)
            main_box.pack_start(entry, False, False, 0)
            main_box.pack_start(examples_frame, True, True, 0)
            main_box.pack_start(hint_label, False, False, 0)
            
            content_area.pack_start(main_box, True, True, 0)
            content_area.show_all()             
###
            response = dialog.run()
            print(f"DEBUG: Dialog response: {response}")
            
            if response == Gtk.ResponseType.OK:
                print("DEBUG: OK clicked")
                new_params = entry.get_text().strip()
                print(f"DEBUG: New params: {new_params}")
                if new_params and new_params != current_params:
                    print("DEBUG: Calling update_service_params")
                    threading.Thread(
                        self.show_notification("Перезапуск...", "Перезапуск сервиса, подождите"),
                        target=self.update_service_params, 
                        args=(new_params,),
                        daemon=True
                    ).start()    

            else:
                print("DEBUG: Cancel or close clicked")
            dialog.destroy()                 
              
                
        except Exception as e:
            print(f"ERROR in show_settings: {e}")
            import traceback
            traceback.print_exc()                    
###            

    def on_copy_example(self, button, example_text):
        """Копирование примера в буфер обмена"""
        clipboard = Gtk.Clipboard.get(Gdk.SELECTION_CLIPBOARD)
        clipboard.set_text(example_text, -1)
        
        # Показываем уведомление
        self.show_notification("Скопировано:", f" {example_text}")

    def on_example_clicked(self, widget, event, example_text):
        """Обработка клика по полю с примером"""
        if event.type == Gdk.EventType.BUTTON_PRESS:
            self.on_copy_example(None, example_text)
            return True
        return False

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
                    self.update_service_params(best_params)
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
        """Выход из приложения с правильным управлением прокси"""
        if self.current_params.get("auto_disable_proxy", False) and self.we_changed_proxy:
            try:
                result = subprocess.run(
                    ['systemctl', 'is-active', 'ciadpi.service'],
                    capture_output=True, text=True, timeout=2
                )
                service_running = result.stdout.strip() == 'active'
                
                if not service_running:
                    # Сервис остановлен - восстанавливаем системные настройки
                    self.restore_system_proxy_backup()
                    # ⚠️ НЕ СБРАСЫВАЕМ ФЛАГ - он сохраняется в конфиге
                    # self.we_changed_proxy = False  # ❌ УБРАТЬ ЭТУ СТРОКУ
                    self.show_notification("Выход", "Системные настройки прокси восстановлены")
                else:
                    print("ℹ️ Сервис запущен - оставляем наши настройки прокси")
                    
            except Exception as e:
                print(f"⚠️ Не удалось проверить статус сервиса: {e}")
        
        if hasattr(self, 'is_searching') and self.is_searching:
            self.stop_autosearch()
            
        Gtk.main_quit()

if __name__ == "__main__":
    # Запускаем как демон
    import signal
    signal.signal(signal.SIGINT, signal.SIG_DFL)
    
    indicator = AdvancedTrayIndicator()
    Gtk.main()

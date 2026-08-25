#!/usr/bin/env python3

import sys
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

# Пути к модулям: папка скрипта + ~/.local/bin (для установленной копии)
sys.path.append(str(Path(__file__).resolve().parent))
sys.path.append(str(Path.home() / '.local' / 'bin'))

try:
    from ciadpi_i18n import t, tr, get_lang, set_lang, save_lang
    I18N_AVAILABLE = True
except ImportError:
    I18N_AVAILABLE = False
    def t(key): return key
    def tr(key_ru): return key_ru
    def get_lang(): return 'ru'
    def set_lang(lang): pass
    def save_lang(): pass

try:
    from ciadpi_texts import HELP_TEXTS, ABOUT_TEXTS
    TEXTS_AVAILABLE = True
except ImportError:
    TEXTS_AVAILABLE = False
    HELP_TEXTS, ABOUT_TEXTS = {}, {}

try:
    from ciadpi_params_spec import CONTROLS, parse_params, get_value, build_params, HELP_SECTIONS
    PARAMS_SPEC_AVAILABLE = True
except ImportError:
    PARAMS_SPEC_AVAILABLE = False
    CONTROLS = []
    def parse_params(s): return {}
    def get_value(d, k): return None
    def build_params(w): return ''
    HELP_SECTIONS = {}

try:
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

        self.original_system_proxy = None  # Настройки которые были в системе ДО нас
        self.we_changed_proxy = False      # Флаг что мы меняли прокси

        # Настройки приложения: уведомления, автозапуск индикатора
        self.app_prefs = self._load_app_prefs()

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

        # применяем настройки прокси из конфига при запуске
        GLib.timeout_add(3000, self.apply_proxy_from_config)        
        
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

    def apply_proxy_from_config(self):
        """Применяем настройки прокси из конфига при запуске программы"""
        try:
            proxy_mode = self.current_params.get("proxy_mode")

            # ⭐ ЛОКАЛЬНЫЙ РЕЖИМ: системные настройки НЕ трогаем
            if self.current_params.get("proxy_enabled", False) and proxy_mode == 'local':
                print("🔌 Локальный прокси-режим: системные настройки не изменяются")
                return False

            if (self.current_params.get("proxy_enabled", False) and
                proxy_mode == 'manual'):

                # ⭐ ЕСЛИ ПРИМЕНЯЕМ НАШИ НАСТРОЙКИ - УСТАНАВЛИВАЕМ ФЛАГ
                if not self.we_changed_proxy:
                    self.save_system_proxy_backup()  # Сохраняем системные настройки
                    self.we_changed_proxy = True
                    self.current_params["we_changed_proxy"] = True
                    self.save_config()
                    print("💾 Установлен флаг we_changed_proxy при применении настроек из конфига")

                host = self.current_params.get("proxy_host", "")
                port = self.current_params.get("proxy_port", "1080")
                self.apply_system_proxy('manual', host, port)

        except Exception as e:
            print(f"⚠️ Ошибка применения настроек прокси из конфига: {e}")

        return False

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

    def _locate_ciadpi(self, username=None):
        """Найти каталог и бинарник ciadpi.

        Приоритет:
          1. ExecStart установленного ciadpi.service (пакетная установка)
          2. ~/byedpi/ciadpi  (скриптовая установка)
          3. /usr/bin/ciadpi  (пакет byedpi/ciadpi-byedpi)
        Возвращает (byedpi_dir|None, binary_path|None).
        """
        # 1) Из текущего юнита
        try:
            r = subprocess.run(
                ['systemctl', 'show', 'ciadpi.service',
                 '--property=ExecStart', '--no-pager'],
                capture_output=True, text=True, timeout=5
            )
            if r.returncode == 0 and 'argv[]=' in r.stdout:
                argv = r.stdout.split('argv[]=')[1].split(';')[0].split()
                if argv:
                    bin_path = Path(argv[0])
                    if bin_path.exists():
                        return bin_path.parent, bin_path
        except Exception:
            pass

        home_dir = Path.home()

        # 2) Скриптовая установка
        script_bin = home_dir / 'byedpi' / 'ciadpi'
        if script_bin.exists():
            return script_bin.parent, script_bin

        # 3) Пакетный бинарник
        for cand in (Path('/usr/bin/ciadpi'), Path('/usr/local/bin/ciadpi')):
            if cand.exists():
                return cand.parent, cand

        return None, None

    def _systemctl(self, *args):
        """Запуск systemctl для ciadpi.service с fallback на pkexec (GUI-пароль).
        Возвращает (ok, stderr)."""
        # 1) Пробуем напрямую (работает при NOPASSWD sudoers или polkit-правиле)
        try:
            r = subprocess.run(['systemctl', *args],
                               capture_output=True, text=True, timeout=15)
            if r.returncode == 0:
                return True, ""
            # Команды чтения (is-active/show/status) не требуют прав:
            # ненулевой код = валидный ответ сервиса, не ошибка доступа
            if args and args[0] in ('is-active', 'show', 'status',
                                    'is-enabled', 'is-failed'):
                return False, r.stdout.strip() or r.stderr.strip()
        except Exception:
            pass
        # 2) sudo без пароля
        try:
            r = subprocess.run(['sudo', '-n', 'systemctl', *args],
                               capture_output=True, text=True, timeout=15)
            if r.returncode == 0:
                return True, ""
        except Exception:
            pass
        # 3) pkexec — спросит пароль через GUI-агент
        try:
            r = subprocess.run(['pkexec', 'systemctl', *args],
                               capture_output=True, text=True, timeout=120)
            if r.returncode == 0:
                return True, ""
        except FileNotFoundError:
            pass
        except subprocess.TimeoutExpired:
            pass

        # 4) Не удалось — предлагаем одноразовую настройку прав
        self._offer_privileges_setup()
        return False, "Требуются права. Настройте беспарольный доступ через меню «🔑 Права доступа»"

    def _offer_privileges_setup(self):
        """Однократно за сессию предлагает настроить беспарольный доступ."""
        if getattr(self, '_privileges_offer_shown', False):
            return
        self._privileges_offer_shown = True
        GLib.idle_add(
            self.show_notification,
            "Требуется настройка",
            "Чтобы не вводить пароль каждый раз: меню → 🔑 Права доступа"
        )

    def show_privileges_dialog(self, widget=None):
        """Диалог одноразовой настройки беспарольного управления сервисом."""
        script_src = Path(__file__).resolve()
        dialog = Gtk.Dialog(title="Права доступа CIADPI", flags=0)
        dialog.add_buttons(Gtk.STOCK_CANCEL, Gtk.ResponseType.CANCEL)
        dialog.set_default_size(560, 300)

        box = dialog.get_content_area()
        vbox = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=10)
        vbox.set_margin_top(12)
        vbox.set_margin_bottom(12)
        vbox.set_margin_start(12)
        vbox.set_margin_end(12)

        info = Gtk.Label()
        info.set_markup(
            "<b>Беспарольное управление сервисом</b>\n\n"
            "Сейчас при изменении параметров система может запрашивать пароль.\n"
            "Одноразовая настройка добавит правила, разрешающие управлять\n"
            "<b>только сервисом ciadpi.service</b> без пароля (sudoers + polkit).\n\n"
            "Пароль будет запрошен <b>один раз</b> — сейчас."
        )
        info.set_xalign(0)
        info.set_line_wrap(True)
        vbox.pack_start(info, False, False, 0)

        btn_apply = Gtk.Button(label="🔑 Настроить (запросит пароль один раз)")
        vbox.pack_start(btn_apply, False, False, 0)

        status = Gtk.Label(label="")
        status.set_xalign(0)
        status.set_line_wrap(True)
        vbox.pack_start(status, False, False, 0)

        box.pack_start(vbox, True, True, 0)
        box.show_all()

        def run_setup(btn):
            btn_apply.set_sensitive(False)
            status.set_text("Выполняется настройка... (смотрите запрос пароля)")

            def work():
                ok, msg = self._setup_privileges(script_src)

                def finish():
                    btn_apply.set_sensitive(True)
                    if ok:
                        status.set_text("✅ Готово! Пароль больше не потребуется.")
                        self.show_notification("Готово", "Беспарольное управление настроено")
                    else:
                        status.set_text(f"❌ Ошибка: {msg}")
                    return False
                GLib.idle_add(finish)

            threading.Thread(target=work, daemon=True).start()

        def on_copy_cmd(btn):
            clipboard = Gtk.Clipboard.get(Gdk.SELECTION_CLIPBOARD)
            clipboard.set_text(
                f'pkexec env CIADPI_USER="$USER" bash '
                f"{script_src.parent / 'ciadpi_privileges.sh'}", -1)
            self.show_notification("Скопировано",
                                   "Команда вставлена в буфер обмена")

        btn_copy = Gtk.Button(label="📋 Скопировать команду для терминала")
        btn_copy.connect("clicked", on_copy_cmd)
        vbox.pack_start(btn_copy, False, False, 0)
        box.show_all()

        btn_apply.connect("clicked", run_setup)
        dialog.connect("response", lambda d, r: d.destroy())
        dialog.show_all()

    def _setup_privileges(self, script_src):
        """Запуск ciadpi_privileges.sh через pkexec. Возвращает (ok, message)."""
        src_script = script_src.parent / 'ciadpi_privileges.sh'
        installed = Path.home() / '.local' / 'bin' / 'ciadpi_privileges.sh'

        # Берём скрипт из ~/.local/bin если он там есть, иначе из папки проекта
        use_script = installed if installed.exists() else src_script

        if not use_script.exists():
            # Скрипта нет нигде — создаём в ~/.local/bin из встроенного шаблона
            installed.parent.mkdir(exist_ok=True)
            try:
                import shutil as _shutil
                _shutil.copy(src_script, installed)
                os.chmod(installed, 0o755)
                use_script = installed
            except Exception:
                pass

        try:
            r = subprocess.run(
                ['pkexec', 'env', f'CIADPI_USER={os.environ.get("USER", "")}',
                 'bash', str(use_script)],
                capture_output=True, text=True, timeout=180
            )
            if r.returncode == 0:
                return True, ""
            err = (r.stderr or '').strip()
            if 'dismissed' in err.lower() or r.returncode == 126:
                return False, "Запрос пароля отменён"
            return False, err or f"код {r.returncode}"
        except FileNotFoundError:
            return False, "pkexec не найден"
        except subprocess.TimeoutExpired:
            return False, "Таймаут выполнения"


    def update_service_params(self, new_params, apply_proxy=True):
        """Обновление параметров в systemd сервисе - УНИВЕРСАЛЬНАЯ ВЕРСИЯ"""
        try:
            print(f"🔄 Обновление параметров: {new_params}")

            # Получаем данные пользователя динамически
            username = os.environ.get('USER')
            home_dir = Path.home()
            byedpi_dir, ciadpi_binary = self._locate_ciadpi(username)

            if not ciadpi_binary:
                error_msg = ("Бинарник ciadpi не найден. Установите byedpi "
                             "(~/byedpi) или пакет ciadpi-byedpi.")
                print(f"❌ {error_msg}")
                self.show_notification("Ошибка", error_msg)
                return False

            # ⭐ СНАЧАЛА запоминаем параметры в конфиг,
            # чтобы они не потерялись даже при сбое перезапуска
            self.current_params["current_params"] = new_params
            self.current_params["params"] = new_params
            self.save_config()
            print("💾 Параметры сохранены в конфиг до перезапуска сервиса")

            # Останавливаем сервис
            print("⏹️ Останавливаем сервис...")
            ok, err = self._systemctl('stop', 'ciadpi.service')

            if not ok:
                print(f"⚠️ Предупреждение при остановке: {err}")

            time.sleep(1)

            # Удаляем override директорию если есть (избегаем конфликтов)
            override_dir = Path('/etc/systemd/system/ciadpi.service.d')
            if override_dir.exists():
                # rm требует root; пробуем через pkexec
                try:
                    subprocess.run(
                        ['pkexec', 'rm', '-rf', str(override_dir)],
                        capture_output=True, text=True, timeout=60
                    )
                    print("🗑️ Удалена override директория")
                except Exception:
                    pass

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

            # Копируем с правами root:
            #  1) sudo tee (покрыт sudoers из ciadpi_privileges.sh — без пароля)
            #  2) прямой cp (если вдруг права уже есть)
            #  3) pkexec cp (запросит пароль через GUI)
            print("📝 Обновляем service файл...")
            copy_ok = False
            for cmd in (
                ['sudo', '-n', 'tee', '/etc/systemd/system/ciadpi.service'],
                ['cp', str(temp_file), '/etc/systemd/system/ciadpi.service'],
                ['pkexec', 'cp', str(temp_file), '/etc/systemd/system/ciadpi.service'],
            ):
                try:
                    if 'tee' in cmd:
                        # содержимое передаём через stdin
                        with open(temp_file, 'rb') as f_in:
                            r = subprocess.run(cmd, stdin=f_in,
                                               capture_output=True, text=True, timeout=90)
                    else:
                        r = subprocess.run(cmd, capture_output=True, text=True, timeout=90)
                    if r.returncode == 0:
                        copy_ok = True
                        break
                except (FileNotFoundError, subprocess.TimeoutExpired):
                    continue

            if not copy_ok:
                self._offer_privileges_setup()
                error_msg = ("Не удалось записать /etc/systemd/system/ciadpi.service "
                             "(нужны права root). Параметры сохранены в конфиг и "
                             "будут применены позже.")
                print(f"❌ {error_msg}")
                self.show_notification("Ошибка", error_msg)
                return False

            # Удаляем override директорию если есть (sudoers покрывает rm -rf этой папки)
            override_dir = Path('/etc/systemd/system/ciadpi.service.d')
            if override_dir.exists():
                try:
                    subprocess.run(
                        ['sudo', '-n', 'rm', '-rf', '/etc/systemd/system/ciadpi.service.d'],
                        capture_output=True, text=True, timeout=30
                    )
                    print("🗑️ Удалена override директория")
                except Exception:
                    pass

            reload_ok, reload_err = self._systemctl('daemon-reload')
            if not reload_ok:
                print(f"⚠️ daemon-reload не выполнен: {reload_err}")

            # Запускаем сервис
            print("▶️ Запускаем сервис...")
            start_ok, start_err = self._systemctl('start', 'ciadpi.service')

            if not start_ok:
                error_msg = f"Не удалось запустить сервис: {start_err}"
                print(f"❌ {error_msg}")
                self.show_notification("Ошибка", error_msg)
                return False

            # Проверяем статус
            time.sleep(3)
            status_result = subprocess.run(
                ['systemctl', 'is-active', 'ciadpi.service'],
                capture_output=True, text=True
            )

            if status_result.stdout.strip() == 'active':
                print("✅ Параметры успешно обновлены")
                # Применяем наши настройки прокси к новому сервису
                if apply_proxy and self.current_params.get("proxy_enabled"):
                    host = self.current_params.get("proxy_host", "")
                    port = self.current_params.get("proxy_port", "1080")
                    try:
                        self.apply_system_proxy('manual', host, port)
                    except Exception as e:
                        print(f"⚠️ Прокси не применён после обновления: {e}")
                self.show_notification(t('notif.success'), t('notif.params_updated'), category='params')
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

    def create_menu(self):
        menu = Gtk.Menu()
        
        # Статус
        self.status_item = Gtk.MenuItem(label=t('menu.status'))
        menu.append(self.status_item)
        
        menu.append(Gtk.SeparatorMenuItem())
        
        # Управление сервисом
        start_item = Gtk.MenuItem(label=t('menu.start'))
        start_item.connect("activate", self.start_service)
        menu.append(start_item)
        
        stop_item = Gtk.MenuItem(label=t('menu.stop'))
        stop_item.connect("activate", self.stop_service)
        menu.append(stop_item)
        
        restart_item = Gtk.MenuItem(label=t('menu.restart'))
        restart_item.connect("activate", self.restart_service)
        menu.append(restart_item)
        
        menu.append(Gtk.SeparatorMenuItem())
        
        # Настройки
        settings_item = Gtk.MenuItem(label=t('menu.settings'))
        settings_item.connect("activate", self.show_settings)
        menu.append(settings_item)

        if PARAMS_SPEC_AVAILABLE:
            builder_item = Gtk.MenuItem(label=t('menu.builder'))
            builder_item.connect("activate", self.show_param_builder)
            menu.append(builder_item)

        proxy_item = Gtk.MenuItem(label=t('menu.proxy'))
        proxy_item.connect("activate", self.show_proxy_settings)
        menu.append(proxy_item)

        # БЕЛЫЙ СПИСОК
        whitelist_item = Gtk.MenuItem(label=t('menu.whitelist'))
        whitelist_item.connect("activate", self.show_whitelist_dialog)
        menu.append(whitelist_item)        
        
        menu.append(Gtk.SeparatorMenuItem())
        
        # Автопоиск и история
        if self.autosearcher:
            autosearch_item = Gtk.MenuItem(label=t('menu.autosearch'))
            autosearch_item.connect("activate", self.show_autosearch_dialog)
            menu.append(autosearch_item)

            history_item = Gtk.MenuItem(label=t('menu.history'))
            history_item.connect("activate", self.show_history)
            menu.append(history_item)

            menu.append(Gtk.SeparatorMenuItem())

        # Поиск стратегии (перебор параметров)
        strategy_item = Gtk.MenuItem(label="🧪 Поиск стратегии (перебор параметров)")
        strategy_item.connect("activate", self.show_strategy_search)
        menu.append(strategy_item)

        # Обновление byedpi без переустановки
        byedpi_update_item = Gtk.MenuItem(label=t('menu.byedpi_update'))
        byedpi_update_item.connect("activate", self.update_byedpi)
        menu.append(byedpi_update_item)

        # Одноразовая настройка беспарольного доступа
        privileges_item = Gtk.MenuItem(label=t('menu.privileges'))
        privileges_item.connect("activate", self.show_privileges_dialog)
        menu.append(privileges_item)

        # Настройки приложения (язык, уведомления, автозапуск)
        app_settings_item = Gtk.MenuItem(label=t('menu.app_settings'))
        app_settings_item.connect("activate", self.show_app_settings)
        menu.append(app_settings_item)
        
        # Логи
        logs_item = Gtk.MenuItem(label=t('menu.logs'))
        logs_item.connect("activate", self.show_logs)
        menu.append(logs_item)
        
        menu.append(Gtk.SeparatorMenuItem())
        
        # Справка
        help_item = Gtk.MenuItem(label=t('menu.help'))
        help_item.connect("activate", self.show_help)
        menu.append(help_item)
        
        about_item = Gtk.MenuItem(label=t('menu.about'))
        about_item.connect("activate", self.show_about)
        menu.append(about_item)
        
        menu.append(Gtk.SeparatorMenuItem())
        
        # Выход
        exit_item = Gtk.MenuItem(label=t('menu.exit'))
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
    

    def show_proxy_settings(self, widget=None):
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
        mode_label = Gtk.Label(label=t('proxy.mode'))
        mode_label.set_xalign(0)
        mode_combo = Gtk.ComboBoxText()
        mode_combo.append_text(t('proxy.mode_pac'))     # 0 auto
        mode_combo.append_text(t('proxy.mode_manual'))  # 1 manual
        mode_combo.append_text(t('proxy.mode_off'))     # 2 none
        mode_combo.append_text(t('proxy.mode_local'))   # 3 local

        # Устанавливаем текущий режим (local из конфига имеет приоритет)
        if self.current_params.get('proxy_mode') == 'local':
            mode_combo.set_active(3)
        else:
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
        info_label = Gtk.Label(label=t('proxy.note_all'))
        info_label.set_sensitive(False)

        # Подсказка для локального режима (видна при выборе "Локальный")
        local_hint_label = Gtk.Label(label=t('proxy.local_hint'))
        local_hint_label.set_sensitive(False)
        local_hint_label.set_xalign(0)
        local_hint_label.set_line_wrap(True)
        
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
        box.pack_start(local_hint_label, False, False, 0)
        box.pack_start(status_label, False, False, 0)
        box.pack_start(info_label, False, False, 0)

        def on_mode_changed(combo):
            is_local = combo.get_active() == 3
            local_hint_label.set_visible(is_local)
            info_label.set_visible(not is_local)
        mode_combo.connect("changed", on_mode_changed)
        on_mode_changed(mode_combo)

        content_area.pack_start(box, True, True, 0)
        content_area.show_all()

        response = dialog.run()

        if response == Gtk.ResponseType.OK:
            mode_index = mode_combo.get_active()
            modes = ['auto', 'manual', 'none', 'local']
            selected_mode = modes[mode_index] if mode_index >= 0 else 'none'

            proxy_host = host_entry.get_text().strip()
            proxy_port = port_entry.get_text().strip()

            if not proxy_port.isdigit():
                self.show_notification(t('notif.error'),
                                       "Порт должен быть числом / Port must be a number")
                dialog.destroy()
                return

            # ⭐ ЛОКАЛЬНЫЙ РЕЖИМ: системные настройки не трогаем вообще
            if selected_mode == 'local':
                # Если раньше меняли системные — возвращаем как было
                if self.we_changed_proxy:
                    self.restore_system_proxy_backup()
                    self.we_changed_proxy = False
                    print("💾 Локальный режим: системные настройки прокси восстановлены")

                self.current_params["proxy_enabled"] = True
                self.current_params["proxy_host"] = proxy_host or "127.0.0.1"
                self.current_params["proxy_port"] = proxy_port
                self.current_params["proxy_mode"] = 'local'
                self.current_params["auto_disable_proxy"] = auto_disable_check.get_active()
                self.current_params["we_changed_proxy"] = False
                self.save_config()

                self.show_notification(
                    t('notif.success') + ": " + t('proxy.mode_local'),
                    f"127.0.0.1:{proxy_port} (системные не изменены)",
                    category='proxy')
                dialog.destroy()
                return

            # ⭐ ПЕРЕХОД ИЗ local В ДРУГОЙ РЕЖИМ — ничего дополнительно не нужно,
            # системные настройки мы не трогали

            # ⭐ ЛОГИКА УПРАВЛЕНИЯ ПРОКСИ (ВСЕ В ОДНОМ МЕСТЕ)
            if selected_mode == 'manual' and not self.we_changed_proxy:
                # ВКЛЮЧАЕМ ПРОКСИ ВПЕРВЫЕ
                self.save_system_proxy_backup()
                self.we_changed_proxy = True
                print("💾 Включен наш прокси, сохранены системные настройки")
                
            elif selected_mode == 'none' and self.we_changed_proxy:
                # ОТКЛЮЧАЕМ ПРОКСИ
                self.restore_system_proxy_backup()
                self.we_changed_proxy = False
                print("💾 Прокси отключен, восстановлены системные настройки")
            
            # ⭐ СОХРАНЕНИЕ В КОНФИГ (ВСЕГО ОДИН РАЗ)
            self.current_params["proxy_enabled"] = selected_mode != 'none'
            self.current_params["proxy_host"] = proxy_host
            self.current_params["proxy_port"] = proxy_port
            self.current_params["proxy_mode"] = selected_mode
            self.current_params["auto_disable_proxy"] = auto_disable_check.get_active()
            self.current_params["we_changed_proxy"] = self.we_changed_proxy
            
            print(f"💾 Сохраняем конфиг: auto_disable_proxy={self.current_params['auto_disable_proxy']}, we_changed_proxy={self.we_changed_proxy}")
            self.save_config()
            
            # ⭐ ПРИМЕНЕНИЕ НАСТРОЕК (ЕСЛИ НЕ БЫЛО ВОССТАНОВЛЕНИЯ)
            if not (selected_mode == 'none' and self.we_changed_proxy):
                # Просто применяем настройки (если не восстанавливали системные)
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
            
            # NetworkManager/systemd-resolved НЕ перезапускаем:
            # gsettings применяются на лету, а рестарт служб рвёт сеть
            # и выглядит как «что-то запускается при старте».
            
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
        """Проверка текущих системных настроек прокси.

        ⭐ В локальном режиме ('local') НЕ перезаписываем наш конфиг
        системным состоянием — иначе локальные настройки теряются."""
        try:
            # Локальный режим: системный прокси нас не интересует
            if self.current_params.get('proxy_mode') == 'local':
                return

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
        """Восстанавливаем наши настройки прокси при запуске приложения.

        Ничего не запускает автоматически: только синхронизирует флаг
        прокси, ЕСЛИ сервис уже работает. Автостарт сервиса отключён."""
        try:
            # Проверяем статус сервиса
            result = subprocess.run(
                ['systemctl', 'is-active', 'ciadpi.service'],
                capture_output=True, text=True, timeout=2
            )
            service_running = result.stdout.strip() == 'active'

            # Если сервис НЕ запущен — ничего не делаем (никакого автостарта)
            if not service_running:
                print("ℹ️ Сервис не запущен — автостарт не выполняется (ручной режим)")
                return False

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
        """Восстанавливает оригинальные системные настройки если включен автоотключение"""
        # ⭐ ПРОВЕРЯЕМ ЧЕКБОКС
        if not self.current_params.get("auto_disable_proxy", False):
            print("ℹ️ Автоотключение выключено - не восстанавливаем системные настройки")
            return False
            
        if not self.we_changed_proxy:
            print("ℹ️ Мы не меняли прокси - нечего восстанавливать")
            return False        
        
        """Восстанавливает оригинальные системные настройки"""     
        try:
            if not self.original_system_proxy:
                print("ℹ️ Нет сохраненных системных настроек, отключаем прокси")
                # Fallback: просто отключаем прокси
                subprocess.run([
                    'gsettings', 'set', 'org.gnome.system.proxy', 'mode', 'none'
                ], check=False)
                return True
                
            original_mode = self.original_system_proxy.get('mode', 'none')
            original_host = self.original_system_proxy.get('http_host', '')
            original_port = self.original_system_proxy.get('http_port', '1080')
            
            print("🔄 Восстанавливаем системные настройки прокси...")
            
            # Применяем оригинальные настройки
            success = self.apply_system_proxy(original_mode, original_host, original_port)
            
            if success:
                # Очищаем переменные окружения                
                print("✅ Системные настройки прокси восстановлены")
            return success
                
        except Exception as e:
            print(f"❌ Ошибка восстановления системных настроек: {e}")
            return False              

    def run_command(self, command):
        """Выполнение systemctl-команды через _systemctl (без запроса пароля)."""
        def run_in_thread():
            try:
                args = command.split()
                if args and args[0] == 'systemctl':
                    args = args[1:]
                ok, err = self._systemctl(*args)
                if ok:
                    self.show_notification(t('notif.success'), t('notif.command_ok'), category='service')
                else:
                    self.show_notification(t('notif.error'), err or "systemctl error", category='service')
                time.sleep(1)
                self.update_status()
            except Exception as e:
                self.show_notification(t('notif.error'), str(e), category='service')
        
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
                        self.show_notification(t('notif.success'), t('notif.service_started_proxy'), category='service')
                    else:
                        self.show_notification(t('notif.success'), t('notif.service_started'), category='service')
                        
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
                    success = self.restore_system_proxy_backup()
                    
                    if success:
                        # ⭐ СБРАСЫВАЕМ ФЛАГ ТОЛЬКО ЕСЛИ УСПЕШНО ВОССТАНОВИЛИ
                        self.we_changed_proxy = False
                        self.current_params["we_changed_proxy"] = False
                        self.save_config()
                        print("💾 Флаг we_changed_proxy сброшен после восстановления системных настроек")
                    
                    # Останавливаем сервис
                    result = subprocess.run(
                        ['sudo', 'systemctl', 'stop', 'ciadpi.service'],
                        capture_output=True, text=True, timeout=10
                    )
                    
                    if result.returncode == 0:
                        self.show_notification(t('notif.service_stopped'), t('proxy.mode_off'), category='service')
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

        # Флаги без значения
        bool_flags = {'-D', '-E', '-N', '-U', '-F', '-S', '-Y'}

        # Флаги, принимающие значение (отдельным токеном или прикреплённо: -T3)
        val_flags = {'-i', '-p', '-w', '-c', '-I', '-b', '-g', '-T', '-A', '-L',
                     '-u', '-y', '-K', '-H', '-j', '-V', '-R', '-s', '-d', '-o',
                     '-q', '-f', '-r', '-t', '-O', '-l', '-e', '-n', '-Q', '-M',
                     '-a', '-x'}

        known_short = bool_flags | val_flags

        # Методы обхода с суффиксами: -o1, -o25+s, -o10+m и т.п.
        obfuscation_re = re.compile(r'^-o\d+([+][a-z]+)*$')
        # Прикреплённые значения-суффиксы: 1+s, 2+m ...
        suffix_value_re = re.compile(r'^\d+([+][a-z]+)?$')

        # Длинные опции из справки ciadpi -h
        known_long = {'--ip', '--port', '--daemon', '--pidfile', '--transparent',
                      '--max-conn', '--no-domain', '--no-udp', '--conn-ip',
                      '--buf-size', '--debug', '--def-ttl', '--tfo', '--timeout',
                      '--auto', '--auto-mode', '--cache-ttl', '--cache-file',
                      '--proto', '--hosts', '--ipset', '--pf', '--round',
                      '--split', '--disorder', '--oob', '--disoob', '--fake',
                      '--ttl', '--md', '--fake-offset', '--fake-data',
                      '--oob-data', '--fake-sni', '--fake-tls-mod', '--mod-http',
                      '--tlsrec', '--tlsminor', '--udp-fake', '--drop-sack'}

        tokens = params.split()
        unknown = []
        i = 0
        while i < len(tokens):
            tok = tokens[i]

            # специальные формы ciadpi
            if tok == 'o--tlsrec' or tok.startswith('o--'):
                i += 1
                continue
            if suffix_value_re.match(tok):
                i += 1
                continue

            if tok in known_short:
                # флаг со значением отдельным токеном?
                if tok in val_flags and i + 1 < len(tokens) \
                        and not tokens[i + 1].startswith('-'):
                    i += 2  # пропускаем флаг и его значение
                else:
                    i += 1
                continue

            if tok in known_long:
                # длинная опция со значением?
                if i + 1 < len(tokens) and not tokens[i + 1].startswith('-'):
                    # --tlsrec и --split могут быть без значения в спецформах,
                    # но обычно со значением; пропускаем значение
                    i += 2
                else:
                    i += 1
                continue

            if tok.startswith('--'):
                # неизвестная длинная опция — ошибка
                unknown.append(tok)
                i += 1
                continue

            if tok.startswith('-'):
                # прикреплённое значение: -T3, -L1, -R2 ...
                if tok[:2] in known_short or obfuscation_re.match(tok):
                    i += 1
                    continue
                unknown.append(tok)
                i += 1
                continue

            # голое значение (torst, ssl_err, имя хоста...) — продолжение значения
            i += 1

        if unknown:
            error_msg = f"Неизвестные параметры: {', '.join(unknown)}\n"
            error_msg += "Используйте только параметры из документации ciadpi"
            return False, error_msg

        return True, ""

    def show_settings(self, widget=None):
        ###
        print("DEBUG: show_settings called")
        try:        
###            
            """Диалог настроек параметров"""
            dialog = Gtk.Dialog(title=t('settings.dialog_title'), flags=0)
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
            label = Gtk.Label(label=t('settings.params_label'))
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
            examples_title.set_markup("<b>" + t('settings.examples') + "</b>")
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
            hint_label.set_markup("<small>" + t('settings.hint') + "</small>")
            hint_label.set_xalign(0)
            hint_label.set_sensitive(False)
            
            main_box.pack_start(label, False, False, 0)
            main_box.pack_start(entry, False, False, 0)
            main_box.pack_start(examples_frame, True, True, 0)
            main_box.pack_start(hint_label, False, False, 0)
            
            content_area.pack_start(main_box, True, True, 0)
            content_area.show_all()

            # Цикл: при ошибке валидации диалог остаётся открытым
            while True:
                response = dialog.run()

                if response != Gtk.ResponseType.OK:
                    break  # Cancel/закрытие — выходим

                new_params = entry.get_text().strip()
                if not new_params or new_params == current_params:
                    break  # Нечего менять — просто закрываем

                # ⭐ Валидация параметров ДО применения
                valid, err_msg = self.validate_params(new_params)
                if not valid:
                    err_dialog = Gtk.MessageDialog(
                        transient_for=dialog, flags=0,
                        message_type=Gtk.MessageType.ERROR,
                        buttons=Gtk.ButtonsType.OK,
                        text=t('settings.validation_error') + "\n" + err_msg
                    )
                    err_dialog.run()
                    err_dialog.destroy()
                    continue  # Диалог остаётся открытым — даём исправить

                self.show_notification("Перезапуск...", "Перезапуск сервиса, подождите")
                threading.Thread(
                    target=self.update_service_params,
                    args=(new_params,),
                    daemon=True
                ).start()
                break

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

    # ================= ПОИСК СТРАТЕГИИ =================

    def show_strategy_search(self, widget=None):
        """Диалог поиска оптимальной стратегии перебором параметров."""
        try:
            from ciadpi_strategy_search import StrategySearcher
        except ImportError as e:
            self.show_notification("Ошибка", f"Модуль поиска стратегии недоступен: {e}")
            return

        # Не даём запустить второй поиск
        if getattr(self, 'strategy_window', None) and self.strategy_window.get_visible():
            self.strategy_window.present()
            return

        searcher = StrategySearcher()

        dialog = Gtk.Dialog(title="Поиск стратегии — перебор параметров", flags=0)
        dialog.add_buttons(Gtk.STOCK_CLOSE, Gtk.ResponseType.CLOSE)
        dialog.set_default_size(760, 560)
        self.strategy_window = dialog

        content_area = dialog.get_content_area()
        main_box = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=8)
        main_box.set_margin_top(10)
        main_box.set_margin_bottom(10)
        main_box.set_margin_start(10)
        main_box.set_margin_end(10)

        # --- Настройки проверки ---
        settings_frame = Gtk.Frame(label="Настройка проверки")
        settings_box = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=6)
        settings_box.set_margin_top(8)
        settings_box.set_margin_bottom(8)
        settings_box.set_margin_start(8)
        settings_box.set_margin_end(8)

        row1 = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=8)
        lbl_tests = Gtk.Label(label="Макс. комбинаций:")
        lbl_tests.set_xalign(0)
        spin_tests = Gtk.SpinButton.new_with_range(1, 200, 1)
        spin_tests.set_value(20)

        lbl_port = Gtk.Label(label="Тестовый порт:")
        spin_port = Gtk.SpinButton.new_with_range(1024, 65535, 1)
        spin_port.set_value(searcher.test_port)
        row1.pack_start(lbl_tests, False, False, 0)
        row1.pack_start(spin_tests, False, False, 0)
        row1.pack_start(Gtk.Separator(orientation=Gtk.Orientation.VERTICAL), False, False, 4)
        row1.pack_start(lbl_port, False, False, 0)
        row1.pack_start(spin_port, False, False, 0)

        row2 = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=8)
        lbl_urls = Gtk.Label(label="URL для проверки:")
        lbl_urls.set_xalign(0)
        urls_entry = Gtk.Entry()
        urls_entry.set_text(" ".join(searcher.default_test_urls))
        urls_entry.set_tooltip_text("URL-адреса через пробел; доступ проверяется через тестовый прокси")
        urls_entry.set_hexpand(True)
        row2.pack_start(lbl_urls, False, False, 0)
        row2.pack_start(urls_entry, True, True, 0)

        settings_box.pack_start(row1, False, False, 0)
        settings_box.pack_start(row2, False, False, 0)
        settings_frame.add(settings_box)

        # --- Прогресс ---
        progress_label = Gtk.Label(label="Готов к поиску")
        progress_label.set_xalign(0)
        progressbar = Gtk.ProgressBar()
        progressbar.set_show_text(True)
        progressbar.set_fraction(0.0)

        # --- Кнопки управления ---
        btn_box = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=8)
        btn_start = Gtk.Button(label="▶️ Запустить поиск")
        btn_stop = Gtk.Button(label="⏹ Остановить")
        btn_stop.set_sensitive(False)
        btn_apply = Gtk.Button(label="✅ Применить лучшие параметры")
        btn_apply.set_sensitive(False)
        btn_box.pack_start(btn_start, False, False, 0)
        btn_box.pack_start(btn_stop, False, False, 0)
        btn_box.pack_end(btn_apply, False, False, 0)

        # --- Журнал хода поиска ---
        log_frame = Gtk.Frame(label="Ход поиска (куда подключаемся и что тестируем)")
        scroll = Gtk.ScrolledWindow()
        scroll.set_vexpand(True)
        text_view = Gtk.TextView()
        text_view.set_editable(False)
        text_view.set_wrap_mode(Gtk.WrapMode.WORD_CHAR)
        text_view.set_monospace(True)
        log_buffer = text_view.get_buffer()
        log_frame.add(scroll)
        scroll.add(text_view)

        main_box.pack_start(settings_frame, False, False, 0)
        main_box.pack_start(progress_label, False, False, 0)
        main_box.pack_start(progressbar, False, False, 0)
        main_box.pack_start(btn_box, False, False, 0)
        main_box.pack_start(log_frame, True, True, 0)

        content_area.pack_start(main_box, True, True, 0)
        content_area.show_all()

        state = {'running': False, 'best_params': None}

        def ui_log(message):
            log_buffer.insert(log_buffer.get_end_iter(), message + "\n")
            # автоскролл вниз
            mark = log_buffer.create_mark(None, log_buffer.get_end_iter(), False)
            text_view.scroll_to_mark(mark, 0.0, True, 0.0, 1.0)

        def ui_set_progress(fraction, text):
            progressbar.set_fraction(min(1.0, fraction))
            progressbar.set_text(text)

        def on_progress(stage, data):
            """Колбэк из фонового потока — планируем обновление GUI."""
            if stage == 'start':
                GLib.idle_add(ui_log, f"▶️ Старт: {data['total']} комбинаций, "
                                      f"тестовый порт {data['port']}, "
                                      f"подключение через 127.0.0.1:{data['port']}")
            elif stage == 'test':
                r = data['result']
                idx = data['index'] + 1

                def update_test(r=r, idx=idx):
                    total_now = max(idx, 1)
                    frac = idx / float(state.get('planned_total', total_now) or total_now)
                    if r['success']:
                        ui_set_progress(frac, f"Тест {idx}: УСПЕХ ({r['urls_ok']}/{r['urls_total']} URL)")
                        ui_log(f"[{idx}] ✅ {r['urls_ok']}/{r['urls_total']} URL, "
                               f"средняя скорость {r['speed']:.2f}с | {r['params']}")
                        for url, ok, code, t in r.get('details', []):
                            mark = "✅" if ok else "❌"
                            ui_log(f"      {mark} {url} → HTTP {code} ({t}с)")
                    else:
                        ui_set_progress(frac, f"Тест {idx}: неудача")
                        err = (r.get('error') or '')[:120]
                        ui_log(f"[{idx}] ❌ {err} | {r['params']}")
                    return False
                GLib.idle_add(update_test)

            elif stage == 'done':
                best = data.get('best')

                def update_done(best=best):
                    if best:
                        state['best_params'] = best
                        btn_apply.set_sensitive(True)
                        ui_log(f"\n🏆 Лучшие параметры: {best}")
                        res = data.get('result') or {}
                        if res:
                            ui_log(f"    Скорость: {res['speed']:.2f}с, "
                                   f"доступно URL: {res['urls_ok']}/{res['urls_total']}")
                    else:
                        ui_log("\n😕 Рабочие параметры не найдены. "
                               "Попробуйте другие URL или увеличьте число комбинаций.")
                    ui_set_progress(1.0, "Поиск завершён")
                    btn_start.set_sensitive(True)
                    btn_stop.set_sensitive(False)
                    state['running'] = False
                    return False
                GLib.idle_add(update_done)

        def on_start(btn):
            if state['running']:
                return
            urls = [u.strip() for u in urls_entry.get_text().split() if u.strip()]
            if not urls:
                ui_log("⚠️ Укажите хотя бы один URL для проверки")
                return
            searcher.test_port = int(spin_port.get_value())
            max_tests = int(spin_tests.get_value())
            state.update({'running': True, 'best_params': None, 'planned_total': max_tests})
            btn_start.set_sensitive(False)
            btn_stop.set_sensitive(True)
            btn_apply.set_sensitive(False)
            log_buffer.set_text("")
            ui_set_progress(0.0, "Запуск...")
            threading.Thread(
                target=searcher.find_optimal_params,
                args=(max_tests, urls, on_progress),
                daemon=True
            ).start()

        def on_stop(btn):
            searcher.stop_search()
            ui_log("⏹ Остановка запрошена...")

        def on_apply(btn):
            params = state.get('best_params')
            if not params:
                return
            dialog.set_sensitive(False)
            self.show_notification("Применение...", "Обновление параметров сервиса")

            def apply_thread():
                success = self.update_service_params(params)
                def finish():
                    dialog.set_sensitive(True)
                    if success:
                        ui_log(f"✅ Параметры применены: {params}")
                        self.show_notification(t('notif.success'), t('notif.best_applied'), category='params')
                    else:
                        ui_log(f"❌ Не удалось применить параметры: {params}")
                    return False
                GLib.idle_add(finish)

            threading.Thread(target=apply_thread, daemon=True).start()

        btn_start.connect("clicked", on_start)
        btn_stop.connect("clicked", on_stop)
        btn_apply.connect("clicked", on_apply)
        dialog.connect("response",
                       lambda d, r: searcher.stop_search() if state['running'] else None)

        dialog.show_all()

    # ================= /ПОИСК СТРАТЕГИИ =================

    # ================= ОБНОВЛЕНИЕ BYEDPI =================

    def update_byedpi(self, widget=None):
        """Обновление byedpi из git-репозитория БЕЗ переустановки программы.

        Логика:
          1. Проверяем что ~/byedpi — git-репозиторий hufrea/byedpi
          2. git pull (права root не нужны)
          3. make clean && make (локальная сборка, root не нужен)
          4. Резервная копия старого бинарника + перезапуск сервиса
        """
        def update_thread():
            byedpi_dir, binary = self._locate_ciadpi(os.environ.get('USER'))
            backup = (byedpi_dir / 'ciadpi.bak') if byedpi_dir else None

            if not byedpi_dir or not binary:
                GLib.idle_add(self.show_notification,
                              t('notif.error'),
                              "byedpi git-каталог не найден (~~/byedpi). "
                              "При пакетной установке обновление выполняется "
                              "через менеджер пакетов.")
                return

            def log(msg):
                print(f"[byedpi-update] {msg}")

            # 1) Проверка репозитория
            remotes = subprocess.run(
                ['git', '-C', str(byedpi_dir), 'remote', 'get-url', 'origin'],
                capture_output=True, text=True, timeout=10
            )
            if remotes.returncode != 0:
                GLib.idle_add(self.show_notification, "Ошибка",
                              "~/byedpi не является git-репозиторием.\n"
                              "Обновление невозможно без переустановки.")
                return
            log(f"remote: {remotes.stdout.strip()}")

            # 2) Текущая версия
            old_hash = subprocess.run(
                ['git', '-C', str(byedpi_dir), 'rev-parse', '--short', 'HEAD'],
                capture_output=True, text=True, timeout=10
            ).stdout.strip()
            log(f"текущая версия: {old_hash}")

            # 3) Резервная копия текущего бинарника (для отката)
            try:
                if binary.exists():
                    import shutil as _shutil
                    _shutil.copy2(binary, backup)
                    log(f"бэкап бинарника: {backup}")
            except Exception as e:
                log(f"⚠️ не удалось сделать бэкап: {e}")

            # 4) Останавливаем сервис перед заменой бинарника
            log("останавливаем сервис...")
            self._systemctl('stop', 'ciadpi.service')

            try:
                # 5) git pull
                log("git pull...")
                pull = subprocess.run(
                    ['git', '-C', str(byedpi_dir), 'pull', '--ff-only'],
                    capture_output=True, text=True, timeout=120
                )
                log(pull.stdout.strip() or pull.stderr.strip())
                if pull.returncode != 0:
                    raise RuntimeError(f"git pull failed: {pull.stderr.strip()[:200]}")

                new_hash = subprocess.run(
                    ['git', '-C', str(byedpi_dir), 'rev-parse', '--short', 'HEAD'],
                    capture_output=True, text=True, timeout=10
                ).stdout.strip()

                if new_hash == old_hash and binary.exists():
                    log("уже последняя версия")
                    GLib.idle_add(self.show_notification, "byedpi",
                                  f"Уже последняя версия ({old_hash})")
                    # всё равно пересобирать не будем — просто запускаем обратно
                    self._systemctl('start', 'ciadpi.service')
                    return

                # 6) Сборка
                log("make clean...")
                subprocess.run(['make', '-C', str(byedpi_dir), 'clean'],
                               capture_output=True, text=True, timeout=60)
                log("компиляция make...")
                build = subprocess.run(
                    ['make', '-C', str(byedpi_dir)],
                    capture_output=True, text=True, timeout=300
                )
                if build.returncode != 0 or not binary.exists():
                    err = (build.stderr or build.stdout or '')[-400:]
                    raise RuntimeError(f"Сборка не удалась: {err}")

                log("сборка успешна ✅")

                # 7) Перезапуск сервиса с прежними параметрами
                log("запускаем сервис...")
                started = self._systemctl('start', 'ciadpi.service')
                time.sleep(3)
                active = subprocess.run(
                    ['systemctl', 'is-active', 'ciadpi.service'],
                    capture_output=True, text=True
                ).stdout.strip() == 'active'

                if active:
                    msg = f"byedpi обновлён: {old_hash} → {new_hash}. Сервис работает."
                    log(msg)
                    GLib.idle_add(self.show_notification, "Обновление завершено", msg)
                else:
                    # Откат на резервную копию если сервис не поднялся
                    log("сервис не запустился — пробуем откатить бинарник")
                    if backup.exists():
                        import shutil as _shutil
                        _shutil.copy(backup, binary)
                    self._systemctl('start', 'ciadpi.service')
                    GLib.idle_add(self.show_notification, "byedpi",
                                  f"Обновлён до {new_hash}, но сервис не стартовал — "
                                  "выполнен откат, проверьте логи")

            except Exception as e:
                log(f"ОШИБКА: {e}")
                # Пытаемся вернуть сервис в рабочее состояние
                self._systemctl('start', 'ciadpi.service')
                GLib.idle_add(self.show_notification, "Ошибка обновления", str(e)[:200])

        threading.Thread(target=update_thread, daemon=True).start()

    # ================= /ОБНОВЛЕНИЕ BYEDPI =================

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

    # ================= КОНСТРУКТОР ПАРАМЕТРОВ =================

    def show_param_builder(self, widget=None):
        """Окно-конструктор: все параметры ciadpi регуляторами + строка."""
        if not PARAMS_SPEC_AVAILABLE:
            self.show_notification(t('notif.error'),
                                   "ciadpi_params_spec.py не найден")
            return

        dialog = Gtk.Dialog(title=t('builder.title'), flags=0)
        dialog.add_buttons(Gtk.STOCK_CLOSE, Gtk.ResponseType.CLOSE,
                           Gtk.STOCK_OK, Gtk.ResponseType.OK)
        dialog.set_default_size(860, 640)

        content = dialog.get_content_area()
        main_vbox = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=8)
        main_vbox.set_margin_top(10); main_vbox.set_margin_bottom(10)
        main_vbox.set_margin_start(10); main_vbox.set_margin_end(10)

        current_str = self.get_current_service_params()
        parsed = parse_params(current_str)

        # --- Строка параметров (синхронизирована с регуляторами) ---
        str_label = Gtk.Label(label=t('builder.current'))
        str_label.set_xalign(0)
        str_entry = Gtk.Entry()
        str_entry.set_text(current_str)
        str_entry.set_width_chars(80)

        hint_label = Gtk.Label(label=t('builder.hint_line'))
        hint_label.set_xalign(0)
        hint_label.get_style_context().add_class('dim-label')

        main_vbox.pack_start(str_label, False, False, 0)
        main_vbox.pack_start(str_entry, False, False, 0)
        main_vbox.pack_start(hint_label, False, False, 0)

        # --- Регуляторы по группам ---
        scrolled = Gtk.ScrolledWindow()
        scrolled.set_vexpand(True)
        controls_box = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=8)

        widgets = {}          # opt -> виджет
        updating = {'lock': False}   # защита от рекурсии

        def collect_values():
            """Собрать строку из всех регуляторов."""
            vals = {}
            for spec in CONTROLS:
                w = widgets.get(spec['opt'])
                if w is None:
                    continue
                kind = spec['kind']
                if kind == 'spin':
                    v = int(w.get_value())
                    vals[spec['opt']] = v if v != 0 or spec['default'] == 0 else None
                    # 0 в spin = "не использовать" для опциональных
                    if spec.get('default') is not None and v == spec['default'] \
                            and spec['opt'] != '-p':
                        pass  # дефолт тоже добавляем явно — безопасно
                    if v == 0 and spec['opt'] in ('-T', '-u', '-a', '-x'):
                        continue  # 0 = выключено, не добавляем
                    if v == 1080 and spec['opt'] == '-p':
                        vals[spec['opt']] = 1080  # порт всегда показываем
                elif kind == 'entry' or kind == 'combo':
                    txt = w.get_text().strip() if kind == 'entry' else \
                        (w.get_active_id() or '')
                    if txt:
                        vals[spec['opt']] = txt
                elif kind == 'check':
                    if w.get_active():
                        vals[spec['opt']] = True
            return vals

        def refresh_string_from_widgets(*_):
            if updating['lock']:
                return
            vals = collect_values()
            new_str = build_params(vals)
            updating['lock'] = True
            str_entry.set_text(new_str)
            updating['lock'] = False

        def refresh_widgets_from_string(*_):
            if updating['lock']:
                return
            parsed_now = parse_params(str_entry.get_text())
            updating['lock'] = True
            for spec in CONTROLS:
                w = widgets.get(spec['opt'])
                if w is None:
                    continue
                val = get_value(parsed_now, spec['opt'])
                kind = spec['kind']
                try:
                    if kind == 'spin':
                        w.set_value(float(val) if val else 0)
                    elif kind == 'entry':
                        w.set_text(val or '')
                        w.set_position(-1)
                    elif kind == 'combo':
                        w.set_active_id(val if val else '')
                    elif kind == 'check':
                        w.set_active(bool(val))
                except Exception:
                    pass
            updating['lock'] = False

        current_group = None
        group_frames = {}

        for spec in CONTROLS:
            gkey = spec['group']
            if gkey not in group_frames:
                frame = Gtk.Frame(label=t(gkey))
                gbox = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=4)
                gbox.set_margin_top(8); gbox.set_margin_bottom(8)
                gbox.set_margin_start(8); gbox.set_margin_end(8)
                frame.add(gbox)
                controls_box.pack_start(frame, False, False, 0)
                group_frames[gkey] = gbox

            row_box = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=8)

            title = Gtk.Label(label=t(spec['key']))
            title.set_xalign(0)
            title.set_size_request(230, -1)
            title.set_tooltip_text(t(spec['key'] + '_h'))
            row_box.pack_start(title, False, False, 0)

            kind = spec['kind']
            opt = spec['opt']
            val = get_value(parsed, opt) if opt != '-oN' else None

            if kind == 'spin':
                lo, hi, step = spec['min'], spec['max'], spec['step']
                w = Gtk.SpinButton.new_with_range(lo, hi, step)
                try:
                    w.set_value(float(val) if val else 0)
                except Exception:
                    w.set_value(0)
                w.set_tooltip_text(t(spec['key'] + '_h'))
                # кнопка «?» — переход к полной справке
                q_btn = Gtk.Button(label='?')
                q_btn.set_size_request(28, 28)
                q_btn.set_tooltip_text('Справка')
                section = HELP_SECTIONS.get(spec['group'], '')
                q_btn.connect("clicked", lambda b, s=section: self._open_help_section(s))
                row_box.pack_start(w, False, False, 0)
                row_box.pack_start(q_btn, False, False, 0)
                w.connect("value-changed", refresh_string_from_widgets)

            elif kind == 'entry':
                w = Gtk.Entry()
                w.set_text(val or '')
                w.set_placeholder_text(spec.get('placeholder', ''))
                w.set_tooltip_text(t(spec['key'] + '_h'))
                w.set_hexpand(True)
                q_btn = Gtk.Button(label='?')
                q_btn.set_size_request(28, 28)
                section = HELP_SECTIONS.get(spec['group'], '')
                q_btn.connect("clicked", lambda b, s=section: self._open_help_section(s))
                row_box.pack_start(w, True, True, 0)
                row_box.pack_start(q_btn, False, False, 0)
                w.connect("changed", refresh_string_from_widgets)

            elif kind == 'combo':
                w = Gtk.ComboBoxText()
                for v_id, v_label in spec['variants']:
                    w.append(v_id, v_label)
                w.set_active_id(val if val else '')
                w.set_tooltip_text(t(spec['key'] + '_h'))
                row_box.pack_start(w, False, False, 0)
                w.connect("changed", refresh_string_from_widgets)

            elif kind == 'check':
                w = Gtk.CheckButton()
                w.set_active(bool(val))
                w.set_tooltip_text(t(spec['key'] + '_h'))
                row_box.pack_start(w, False, False, 0)
                w.connect("toggled", refresh_string_from_widgets)

            widgets[opt] = w
            group_frames[gkey].pack_start(row_box, False, False, 0)

        scrolled.add(controls_box)
        main_vbox.pack_start(scrolled, True, True, 0)

        content.pack_start(main_vbox, True, True, 0)
        content.show_all()

        str_entry.connect("changed", refresh_widgets_from_string)

        response = dialog.run()

        if response == Gtk.ResponseType.OK:
            final_str = str_entry.get_text().strip()
            valid, err_msg = self.validate_params(final_str)
            if valid and final_str and final_str != current_str:
                self.show_notification(t('notif.restart_title'),
                                       t('notif.restarting'))
                threading.Thread(
                    target=self.update_service_params,
                    args=(final_str,),
                    daemon=True
                ).start()
            elif not valid:
                self.show_notification(t('notif.error'), err_msg.split('\n')[0])

        dialog.destroy()

    def _open_help_section(self, section):
        """Открыть полную справку и подсказать нужный раздел."""
        self.show_help(None)
        self.show_notification('❓ ' + t('menu.help'),
                               (t('builder.help_section') + " " + section) if section else '')

    # ================= /КОНСТРУКТОР ПАРАМЕТРОВ =================

    def show_help(self, widget):
        """Окно расширенной справки по параметрам (на языке интерфейса)"""
        lang = get_lang()
        help_text = HELP_TEXTS.get(lang) or HELP_TEXTS.get('ru', '')
        if not help_text:
            help_text = "Справка недоступна / Reference unavailable"


        dialog = Gtk.Dialog(title=t('help.title'), flags=0)
        dialog.add_buttons(Gtk.STOCK_OK, Gtk.ResponseType.OK)
        dialog.set_default_size(600, 500)
        
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
        """Окно «О программе» (на языке интерфейса)"""
        lang = get_lang()
        about_text = ABOUT_TEXTS.get(lang) or ABOUT_TEXTS.get('ru', '')


        dialog = Gtk.Dialog(title=t('about.title'), flags=0)
        dialog.add_buttons(Gtk.STOCK_OK, Gtk.ResponseType.OK)
        dialog.set_default_size(450, 400)
        
        content_area = dialog.get_content_area()
        scroll = Gtk.ScrolledWindow()
        
        text_view = Gtk.TextView()
        text_view.set_editable(False)
        text_view.set_wrap_mode(Gtk.WrapMode.WORD)
        
        buffer = text_view.get_buffer()
        buffer.set_text(about_text)
        
        scroll.add(text_view)
        content_area.pack_start(scroll, True, True, 0)
        content_area.show_all()
        
        dialog.run()
        dialog.destroy()

    def _load_app_prefs(self):
        """Настройки приложения: уведомления, автозапуск."""
        defaults = {
            "notifications_enabled": True,
            "notif_service": True,
            "notif_params": True,
            "notif_proxy": True,
            "autostart_indicator": True,
        }
        prefs_file = Path.home() / '.config' / 'ciadpi' / 'app_prefs.json'
        try:
            if prefs_file.exists():
                with open(prefs_file, 'r', encoding='utf-8') as f:
                    saved = json.load(f)
                defaults.update(saved)
        except Exception as e:
            print(f"⚠️ app_prefs: {e}")
        return defaults

    def _save_app_prefs(self):
        prefs_file = Path.home() / '.config' / 'ciadpi' / 'app_prefs.json'
        try:
            with open(prefs_file, 'w', encoding='utf-8') as f:
                json.dump(self.app_prefs, f, indent=2, ensure_ascii=False)
        except Exception as e:
            print(f"⚠️ Не удалось сохранить app_prefs: {e}")

    def _set_autostart(self, enabled):
        """Включение/отключение автозапуска индикатора."""
        autostart = Path.home() / '.config' / 'autostart' / 'ciadpi-indicator.desktop'
        try:
            if enabled:
                src = Path.home() / '.local' / 'share' / 'applications' / 'ciadpi-indicator.desktop'
                if src.exists():
                    import shutil as _sh
                    autostart.parent.mkdir(exist_ok=True)
                    _sh.copy(src, autostart)
                else:
                    # создаём минимальный desktop-файл
                    launcher = Path.home() / '.local' / 'bin' / 'ciadpi_launcher.sh'
                    autostart.parent.mkdir(exist_ok=True)
                    autostart.write_text(
                        "[Desktop Entry]\nType=Application\nName=CIADPI Indicator\n"
                        f"Exec={launcher}\nIcon=network-transmit-receive\n"
                        "Terminal=false\nX-GNOME-Autostart-enabled=true\n")
            else:
                autostart.unlink(missing_ok=True)
            return True
        except Exception as e:
            print(f"⚠️ autostart: {e}")
            return False

    def show_app_settings(self, widget=None):
        """Диалог настроек приложения: язык, уведомления, автозапуск."""
        dialog = Gtk.Dialog(title=t('app.title'), flags=0)
        dialog.add_buttons(Gtk.STOCK_CLOSE, Gtk.ResponseType.CLOSE)
        dialog.set_default_size(480, 420)

        box = dialog.get_content_area()
        vbox = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=10)
        vbox.set_margin_top(12)
        vbox.set_margin_bottom(12)
        vbox.set_margin_start(12)
        vbox.set_margin_end(12)

        # --- Язык ---
        lang_frame = Gtk.Frame(label=t('app.lang'))
        lang_box = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=6)
        lang_box.set_margin_top(8); lang_box.set_margin_bottom(8)
        lang_box.set_margin_start(8); lang_box.set_margin_end(8)

        lang_combo = Gtk.ComboBoxText()
        lang_combo.append_text(t('app.lang_ru'))   # index 0 = ru
        lang_combo.append_text(t('app.lang_en'))   # index 1 = en
        lang_combo.set_active(0 if get_lang() == 'ru' else 1)

        lang_hint = Gtk.Label(label=t('app.lang_hint'))
        lang_hint.set_xalign(0)
        lang_hint.get_style_context().add_class('dim-label')

        lang_box.pack_start(lang_combo, False, False, 0)
        lang_box.pack_start(lang_hint, False, False, 0)
        lang_frame.add(lang_box)

        # --- Уведомления ---
        notif_frame = Gtk.Frame(label=t('app.notif_group'))
        notif_box = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=6)
        notif_box.set_margin_top(8); notif_box.set_margin_bottom(8)
        notif_box.set_margin_start(8); notif_box.set_margin_end(8)

        chk_notif_all = Gtk.CheckButton(label=t('app.notif_enable'))
        chk_notif_service = Gtk.CheckButton(label=t('app.notif_service'))
        chk_notif_params = Gtk.CheckButton(label=t('app.notif_params'))
        chk_notif_proxy = Gtk.CheckButton(label=t('app.notif_proxy'))

        chk_notif_all.set_active(self.app_prefs.get("notifications_enabled", True))
        chk_notif_service.set_active(self.app_prefs.get("notif_service", True))
        chk_notif_params.set_active(self.app_prefs.get("notif_params", True))
        chk_notif_proxy.set_active(self.app_prefs.get("notif_proxy", True))

        # отступ подчинённых галочек
        for w in (chk_notif_service, chk_notif_params, chk_notif_proxy):
            w.set_margin_start(20)

        def toggle_subcheckboxes(btn):
            for w in (chk_notif_service, chk_notif_params, chk_notif_proxy):
                w.set_sensitive(btn.get_active())
        chk_notif_all.connect("toggled", toggle_subcheckboxes)
        toggle_subcheckboxes(chk_notif_all)

        notif_box.pack_start(chk_notif_all, False, False, 0)
        notif_box.pack_start(chk_notif_service, False, False, 0)
        notif_box.pack_start(chk_notif_params, False, False, 0)
        notif_box.pack_start(chk_notif_proxy, False, False, 0)
        notif_frame.add(notif_box)

        # --- Автозапуск ---
        auto_frame = Gtk.Frame(label=t('app.autostart_group'))
        auto_box = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=6)
        auto_box.set_margin_top(8); auto_box.set_margin_bottom(8)
        auto_box.set_margin_start(8); auto_box.set_margin_end(8)

        chk_autostart = Gtk.CheckButton(label=t('app.autostart_indicator'))
        chk_autostart.set_active(
            (Path.home() / '.config' / 'autostart' / 'ciadpi-indicator.desktop').exists())
        auto_hint = Gtk.Label(label=t('app.autostart_hint'))
        auto_hint.set_xalign(0)
        auto_hint.get_style_context().add_class('dim-label')
        auto_hint.set_line_wrap(True)

        auto_box.pack_start(chk_autostart, False, False, 0)
        auto_box.pack_start(auto_hint, False, False, 0)
        auto_frame.add(auto_box)

        vbox.pack_start(lang_frame, False, False, 0)
        vbox.pack_start(notif_frame, False, False, 0)
        vbox.pack_start(auto_frame, False, False, 0)
        box.pack_start(vbox, True, True, 0)
        box.show_all()

        dialog.run()

        # Сохранение при закрытии
        new_lang = 'ru' if lang_combo.get_active() == 0 else 'en'
        lang_changed = new_lang != get_lang()
        if lang_changed:
            set_lang(new_lang)
            save_lang()

        self.app_prefs["notifications_enabled"] = chk_notif_all.get_active()
        self.app_prefs["notif_service"] = chk_notif_service.get_active()
        self.app_prefs["notif_params"] = chk_notif_params.get_active()
        self.app_prefs["notif_proxy"] = chk_notif_proxy.get_active()
        self.app_prefs["autostart_indicator"] = chk_autostart.get_active()
        self._save_app_prefs()
        self._set_autostart(chk_autostart.get_active())
        dialog.destroy()

        # ⭐ Уведомление о смене языка — на ОБОИХ языках (пользователь
        # мог не понять сообщение на новом языке)
        if lang_changed:
            info = Gtk.MessageDialog(
                transient_for=None, flags=0,
                message_type=Gtk.MessageType.INFO,
                buttons=Gtk.ButtonsType.OK,
                title=t('app.lang_restart_ru_title') + " / " +
                      t('app.lang_restart_en_title'),
                text="🇷🇺 " + t('app.lang_restart')
                     + "\n\n🇬🇧 The language change takes effect after "
                       "restarting the indicator (Exit → launch)."
            )
            info.run()
            info.destroy()

        self.show_notification(t('notif.success'), t('app.saved'))

    def show_notification(self, title, message, category=None):
        """Уведомление с учётом пользовательских фильтров.
        category: 'service' | 'params' | 'proxy' | None (прочее)"""
        # Фильтры уведомлений
        prefs = getattr(self, 'app_prefs', {})
        if not prefs.get("notifications_enabled", True):
            return
        if category == 'service' and not prefs.get("notif_service", True):
            return
        if category == 'params' and not prefs.get("notif_params", True):
            return
        if category == 'proxy' and not prefs.get("notif_proxy", True):
            return

        try:
            subprocess.Popen(['notify-send', '-t', '5000', title, message])
        except:
            pass

    def exit_app(self, widget):
        """Выход из приложения с правильным управлением прокси"""
        print("💾 Выход: сохраняем настройки программы...")
        
        # ⭐ СОХРАНЯЕМ НАСТРОЙКИ ПРОГРАММЫ ПЕРЕД ВЫХОДОМ
        self.current_params["we_changed_proxy"] = self.we_changed_proxy
        self.save_config()
        print(f"💾 Сохранены настройки: we_changed_proxy={self.we_changed_proxy}")
        
        if self.current_params.get("auto_disable_proxy", False) and self.we_changed_proxy:
            try:
                result = subprocess.run(
                    ['systemctl', 'is-active', 'ciadpi.service'],
                    capture_output=True, text=True, timeout=2
                )
                service_running = result.stdout.strip() == 'active'
                
                if not service_running:
                    # Сервис остановлен - восстанавливаем системные настройки
                    print("🔄 Выход: восстанавливаем системные настройки прокси...")
                    success = self.restore_system_proxy_backup()
                    if success:
                        print("✅ Системные настройки восстановлены при выходе")
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

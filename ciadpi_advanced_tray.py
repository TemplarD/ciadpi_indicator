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
    from ciadpi_texts import HELP_TEXTS, ABOUT_TEXTS, HELP_SECTIONS
    TEXTS_AVAILABLE = True
except ImportError:
    TEXTS_AVAILABLE = False
    HELP_TEXTS, ABOUT_TEXTS = {}, {}
    HELP_SECTIONS = {}

# ⭐ v1.9.2 (user: «справка вызывает ошибку»): в ciadpi_params_spec
# HELP_SECTIONS — это ЗАГОЛОВКИ ГРУПП конструктора (builder.group_*),
# а в ciadpi_texts — словарь секций справки {(lang): [(header, body)]}.
# Прежний импорт без алиаса ЗАТИРАЛ словарь справки → show_help падал
# с «Справка недоступна». Импортируем под другим именем.
try:
    from ciadpi_params_spec import (CONTROLS, parse_params, get_value,
                                     build_params,
                                     update_param_in_string)
    from ciadpi_params_spec import HELP_SECTIONS as BUILDER_SECTIONS
    PARAMS_SPEC_AVAILABLE = True
except ImportError:
    PARAMS_SPEC_AVAILABLE = False
    CONTROLS = []
    def parse_params(params_str): return {}
    def get_value(parsed, opt):
        return None
    def build_params(widgets):
        return ''
    def update_param_in_string(params_str, opt, value, group=None):
        return str(params_str)
    BUILDER_SECTIONS = {}

try:
    from ciadpi_whitelist import WhitelistManager
    WHITELIST_AVAILABLE = True
    print("✅ Модуль белого списка загружен")
except ImportError as e:
    print(f"❌ Модуль белого списка не доступен: {e}")
    WHITELIST_AVAILABLE = False
    WhitelistManager = None 

# ⭐ nfqws-движок (zapret): перехват пакетов через NFQUEUE.
# Альтернатива byedpi-SOCKS: работает для ВСЕХ приложений машины
# без настройки прокси, но требует root-сервиса и правил nftables.
try:
    from ciadpi_nfqws import NfqwsManager
    NFQWS_AVAILABLE = True
    print("✅ Модуль nfqws загружен")
except ImportError as e:
    print(f"⚠️ Модуль nfqws не доступен: {e}")
    NFQWS_AVAILABLE = False
    NfqwsManager = None

# ⭐ v2.0: snimod — движок №3 (НАША разработка, нет в byedpi/zapret):
# SNI case-mod. DPI прова ловит подстроку "www.youtube.com" в нижнем
# регистре; фильтр регистрозависим — "WWW.YOUTUBE.COM" проходит, а
# серверу регистр безразличен (RFC 6066). Демон на C переписывает
# регистр SNI на лету через NFQUEUE (qnum 210, таблица ciadpi_snimod).
try:
    from ciadpi_snimod import SnimodManager
    SNIMOD_AVAILABLE = True
    print("✅ Модуль snimod (движок №3) загружен")
except ImportError as e:
    print(f"⚠️ Модуль snimod не доступен: {e}")
    SNIMOD_AVAILABLE = False
    SnimodManager = None

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
        self.default_params = "-T3 -A torst -o1 -o25+s -r 1+s"
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

        # ⭐ nfqws-движок: создаём менеджер, если модуль доступен
        self.nfqws = NfqwsManager() if NFQWS_AVAILABLE else None

        # ⭐ v2.0: snimod — движок №3 (SNI case-mod)
        self.snimod = SnimodManager() if SNIMOD_AVAILABLE else None

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

        # ⭐ boot-флаги: на старте трея приводим enable/disable к движку
        # из конфига (одноразово, в фоне). Лечит «после ребута поднялся
        # не тот движок» — например, когда сессия закончилась до того,
        # как switch_engine успел выставить флаги.
        GLib.timeout_add(4000, self.sync_boot_flags_once)
        
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
            new_menu = self.create_menu()
            self.indicator.set_menu(new_menu)
            self._tray_menu = new_menu  # rebuild_menu заменит именно его
            
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
            status = t('quick.running') if result.stdout.strip() == 'active' else t('quick.stopped')
            self.show_notification(t('quick.status_title'), status)
        except Exception as e:
            self.show_notification(t('notif.error'), f"{t('quick.err')}: {e}")

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
            # СОХРАНЯЕМ ФЛАГ В КОНФИГ (getattr — защиту от вызовов до init)
            self.current_params["we_changed_proxy"] = getattr(self, "we_changed_proxy", False)
            
            with open(self.config_file, 'w', encoding='utf-8') as f:
                json.dump(self.current_params, f, indent=2, ensure_ascii=False)
            
            print(f"💾 КОНФИГ СОХРАНЕН: we_changed_proxy = {self.we_changed_proxy}")
        except Exception as e:
            print(f"Ошибка сохранения конфига: {e}")

    def _unit_boot_ctl(self, unit, enable_it):
        """enable/disable юнита, passwordless-безопасно. Возвращает (ok, err).

        Оба юнита покрыты в sudoers глаголами enable/disable. nfqws-юнит
        ведём через NfqwsManager (цепочка direct→sudo→pkexec), byedpi —
        через self._systemctl (та же цепочка).
        """
        if unit == 'ciadpi-nfqws.service' and self.nfqws:
            return self.nfqws.set_enabled(enable_it)
        verb = 'enable' if enable_it else 'disable'
        return self._systemctl(verb, unit)

    def sync_boot_flags_once(self):
        """Один раз на старте трея: enable/disable юнитов = движку из конфига.

        Читает is-enabled напрямую (systemctl без sudo — чтение прав не
        требует), меняет только при расхождении. Никогда не стартует и не
        останавливает сервисы — только boot-флаги. Если enable/disable
        недоступны (нет sudoers), просто пишет в лог и не мешает работе.
        """
        def worker():
            try:
                def read_enabled(unit):
                    try:
                        r = subprocess.run(
                            ['systemctl', 'is-enabled', unit],
                            capture_output=True, text=True, timeout=5)
                        return (r.stdout or '').strip() == 'enabled'
                    except Exception:
                        return None  # не смогли прочитать — не трогаем

                engine = self.current_params.get('engine', 'byedpi')
                want = {'byedpi': 'ciadpi.service',
                        'nfqws': 'ciadpi-nfqws.service',
                        'snimod': 'ciadpi-snimod.service'}.get(
                            engine, 'ciadpi.service')
                others = [u for u in ('ciadpi.service',
                                      'ciadpi-nfqws.service',
                                      'ciadpi-snimod.service')
                           if u != want]

                have_want = read_enabled(want)
                have_others = {u: read_enabled(u) for u in others}
                if have_want is None and all(v is None for v in have_others.values()):
                    return  # systemctl недоступен — молча выходим

                changed = []
                # сначала включаем нужный; чужие отключаем только если
                # нужный точно включён (иначе ребут останется без обхода)
                want_on = have_want
                if have_want is False:
                    ok, err = self._unit_boot_ctl(want, True)
                    changed.append(('enable', want, ok, err))
                    want_on = ok
                for other, have_o in have_others.items():
                    if have_o and want_on:
                        ok, err = self._unit_boot_ctl(other, False)
                        changed.append(('disable', other, ok, err))

                for verb, unit, ok, err in changed:
                    print(f"{'✅' if ok else '⚠️'} boot-флаг: {verb} {unit}"
                          f"{' — ' + err if not ok and err else ''}")
            except Exception as e:
                print(f"⚠️ sync_boot_flags_once: {e}")

        threading.Thread(target=worker, daemon=True).start()
        return False  # одноразовый таймер

    def apply_proxy_from_config(self):
        """Применяем настройки прокси из конфига при запуске программы.

        ⭐ v1.9.1: при выбранном nfqws системный прокси НЕ применяется
        ВООБЩЕ (NFQUEUE перехватывает все пакеты сам; manual на мёртвом
        byedpi-порту только ломает браузеры). Если конфиг ещё хранит
        включённый прокси с byedpi-времён — сбрасываем настройки в
        'none' и чистим флаг, чтобы хвост не оживал на каждом старте.
        """
        try:
            engine = (self.current_params or {}).get('engine', 'byedpi')
            if engine in ('nfqws', 'snimod'):
                if self.current_params.get("proxy_enabled", False):
                    print("🔌 engine=nfqws: системный прокси не нужен — "
                          "сбрасываем хвост byedpi-настроек")
                    subprocess.run(
                        ['gsettings', 'set', 'org.gnome.system.proxy',
                         'mode', 'none'],
                        capture_output=True, timeout=5)
                    self.current_params["proxy_enabled"] = False
                    self.current_params["we_changed_proxy"] = False
                    self.we_changed_proxy = False
                    self.save_config()
                return False

            proxy_mode = self.current_params.get("proxy_mode")

            # ⭐ ЛОКАЛЬНЫЙ РЕЖИМ: системные настройки НЕ трогаем
            if self.current_params.get("proxy_enabled", False) and proxy_mode == 'local':
                print("🔌 Локальный прокси-режим: системные настройки не изменяются")
                return False

            if (self.current_params.get("proxy_enabled", False) and
                proxy_mode == 'manual'):

                host = self.current_params.get("proxy_host", "")
                port = self.current_params.get("proxy_port", "1080")

                # ⭐ БЭКАП ДО ПРИМЕНЕНИЯ (не после!) — см. save_system_proxy_backup
                if not self.we_changed_proxy:
                    self.save_system_proxy_backup()
                    self.we_changed_proxy = True
                    self.current_params["we_changed_proxy"] = True
                    self.save_config()
                    print("💾 Установлен флаг we_changed_proxy, бэкап снят ДО применения")

                self.apply_system_proxy('manual', host, port)

        except Exception as e:
            print(f"⚠️ Ошибка применения настроек прокси из конфига: {e}")

        return False

    def update_tooltip(self, params_text=None):
        """Обновление всплывающей подсказки.

        ⭐ v2.0.5: НЕ вызывает systemctl в главном GTK-потоке —
        раньше get_current_service_params() с subprocess.run(timeout=5)
        висел в тикере каждые 3с и морозил ВСЕ окна («окно поиска
        виснет, ничего не нажимается»). Текст параметров собирает
        фоновый поток update_status и передаёт сюда готовый.
        params_text=None → ставим дефолт без единого subprocess.
        """
        if hasattr(self, 'indicator') and self.indicator:
            current_params = params_text if params_text is not None \
                else getattr(self, '_cached_params_text', None) or self.default_params
            self._cached_params_text = current_params
            tooltip_text = f"CIADPI - {current_params}" if current_params else "CIADPI Indicator"
            self.indicator.set_title(tooltip_text)

    def get_current_service_params(self):
        """Получение текущих параметров из systemd сервиса.

        ⭐ v2.0.5: ВЫЗЫВАТЬ ТОЛЬКО ИЗ ФОНОВОГО ПОТОКА — subprocess
        с timeout=5 в главном GTK-потоке морозил интерфейс.
        """
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

    # Глаголы, требующие root. Для них НЕЛЬЗЯ звать systemctl напрямую:
    # без sudo polkit рисует GUI-диалог пароля на КАЖДЫЙ вызов — а их в
    # цепочке бывает много (диалоги складываются в очередь и «вешают»
    # сессию). Эти глаголы покрыты passwordless-строками в sudoers
    # (см. ciadpi_privileges.sh), поэтому сразу идём через sudo -n.
    _PRIVILEGED_VERBS = {'start', 'stop', 'restart', 'reload',
                         'enable', 'disable', 'mask', 'unmask',
                         'daemon-reload'}

    def _systemctl(self, *args):
        """Запуск systemctl для ciadpi.service с fallback на pkexec (GUI-пароль).
        Возвращает (ok, stderr)."""
        privileged = bool(args) and args[0] in self._PRIVILEGED_VERBS
        # 1) Прямой вызов — только для чтения (прав не требует, polkit
        #    не трогает). Команды чтения при nonzero-коде возвращают
        #    валидный ответ сервиса, а не ошибку доступа.
        if not privileged:
            try:
                r = subprocess.run(['systemctl', *args],
                                   capture_output=True, text=True, timeout=15)
                if r.returncode == 0:
                    return True, ""
                if args and args[0] in ('is-active', 'show', 'status',
                                        'is-enabled', 'is-failed'):
                    return False, r.stdout.strip() or r.stderr.strip()
            except Exception:
                pass
        # 2) sudo без пароля — главный путь для привилегированных глаголов
        #    (и второй шанс для чтения, если прямой не удался)
        try:
            r = subprocess.run(['sudo', '-n', 'systemctl', *args],
                               capture_output=True, text=True, timeout=15)
            if r.returncode == 0:
                return True, ""
        except Exception:
            pass
        # 3) pkexec — ОДИН диалог пароля, только если sudoers не покрывает
        #    (крайний случай; при настроенных правах сюда не доходим)
        if privileged:
            try:
                r = subprocess.run(['pkexec', 'systemctl', *args],
                                   capture_output=True, text=True, timeout=120)
                if r.returncode == 0:
                    return True, ""
            except (FileNotFoundError, subprocess.TimeoutExpired):
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
        dialog.add_buttons(t('btn.cancel'), Gtk.ResponseType.CANCEL)
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

        btn_apply = Gtk.Button(label=t('priv.apply'))
        vbox.pack_start(btn_apply, False, False, 0)

        status = Gtk.Label(label="")
        status.set_xalign(0)
        status.set_line_wrap(True)
        vbox.pack_start(status, False, False, 0)

        box.pack_start(vbox, True, True, 0)
        box.show_all()

        def run_setup(btn):
            btn_apply.set_sensitive(False)
            status.set_text(t('priv.running'))

            def work():
                ok, msg = self._setup_privileges(script_src)

                def finish():
                    btn_apply.set_sensitive(True)
                    if ok:
                        status.set_text(t('priv.done'))
                        self.show_notification(t('priv.done_notif'), t('priv.done_notif_2'))
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
            self.show_notification(t('priv.copy_notif'),
                                   t('priv.copy_notif_2'))

        btn_copy = Gtk.Button(label=t('priv.copy'))
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


    def _dry_run_params(self, params: str) -> Tuple[bool, str]:
        """Проверка параметров живым бинарником ciadpi без запуска прокси.

        Запускает ciadpi с параметрами на привилегированном порту (-p 1):
        - если парсер параметров отверг значения — получим 'invalid value: -X ...'
          (rc=254) ДО попытки bind — это и есть невалидные параметры;
        - если значения корректны, bind на порт 1 упадёт с
          'bind: Permission denied' (rc=255) — для нас это успех:
          синтаксис принят, сеть не тронута.
        VPN и рабочий прокси не затрагиваются.
        """
        binary = self._locate_ciadpi()[1]
        if not binary:
            return True, ""  # бинарника нет — не блокируем сохранение в конфиг
        try:
            cmd = [str(binary)] + params.split() + ['-i', '127.0.0.1', '-p', '1']
            r = subprocess.run(cmd, capture_output=True, text=True, timeout=5)
            err = (r.stderr or r.stdout).strip()
            first_line = err.splitlines()[0] if err else ""
            # Парсер отверг параметры ДО bind — это ошибка значений
            if 'invalid value' in first_line.lower() \
                    or 'unknown option' in first_line.lower() \
                    or 'usage' in first_line.lower():
                return False, first_line
            # bind: Permission denied = параметры приняты, порт занят правами
            if 'permission denied' in first_line.lower():
                return True, ""
            # что-то другое упало — не блокируем, но и не молчим
            if r.returncode not in (0,):
                print(f"⚠️ dry-run неожиданный результат rc={r.returncode}: {first_line}")
            return True, ""
        except Exception as e:
            return True, f"(проверка пропущена: {e})"

    def update_service_params(self, new_params, apply_proxy=True):
        """Обновление параметров в systemd сервисе - УНИВЕРСАЛЬНАЯ ВЕРСИЯ"""
        try:
            print(f"🔄 Обновление параметров: {new_params}")

            # ⭐ СОХРАНЕНИЕ ПОРТА СЕРВИСА: параметры из «Поиска стратегии»
            # и истории приходят БЕЗ -p (тестируются на 1081). Без этого
            # сервис падал на дефолтный 1080, а системный прокси смотрел
            # на порт из конфига — браузер уходил в пустоту.
            try:
                parsed_new = parse_params(new_params)
                if get_value(parsed_new, '-p') is None:
                    cfg_port = str(self.current_params.get('proxy_port', '') or '').strip()
                    if cfg_port.isdigit():
                        new_params = update_param_in_string(new_params, '-p', int(cfg_port))
                        print(f"🔌 Порт сохранён из конфига: -p {cfg_port}")
            except Exception as e:
                print(f"⚠️ Сохранение порта пропущено: {e}")

            # ⭐ PRE-FLIGHT: синтаксис + живой бинарник, ДО записи в юнит.
            # Невалидные параметры = вечный crash-loop юнита (Restart=on-failure).
            valid, err_msg = self.validate_params(new_params)
            if not valid:
                self.show_notification(t('notif.error'),
                                       err_msg.split('\n')[0], category='params')
                return False
            ok, bin_err = self._dry_run_params(new_params)
            if not ok:
                self.show_notification(
                    t('notif.error'),
                    f"ciadpi отверг параметры: {bin_err}", category='params')
                print(f"❌ dry-run: {bin_err}")
                return False

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
                # ⭐ Применяем системный прокси ТОЛЬКО в manual-режиме
                # (раньше применялся и в local — «система сама включилась
                # ручным» после смены параметров/поиска стратегии) —
                # и с корректным бэкапом исходных настроек ДО apply.
                if (apply_proxy
                        and self.current_params.get("proxy_enabled")
                        and self.current_params.get("proxy_mode") == 'manual'):
                    host = self.current_params.get("proxy_host", "")
                    port = self.current_params.get("proxy_port", "1080")
                    try:
                        # бэкап ДО применения (см. save_system_proxy_backup)
                        if not self.we_changed_proxy:
                            self.save_system_proxy_backup()
                            self.we_changed_proxy = True
                            self.save_config()
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
            dialog = Gtk.Dialog(title=t('wl.title'), flags=0)
            dialog.add_buttons(t('btn.cancel'), Gtk.ResponseType.CANCEL,
                            t('btn.ok'), Gtk.ResponseType.OK)
            dialog.set_default_size(600, 500)

            content_area = dialog.get_content_area()
            
            box = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=10)
            box.set_margin_top(10)
            box.set_margin_bottom(10)
            box.set_margin_start(10)
            box.set_margin_end(10)
            
            # Включение белого списка
            enable_check = Gtk.CheckButton(label=t('wl.enable'))
            enable_check.set_active(self.whitelist.get("enabled", False))
            
            # Настройки исключений
            exceptions_frame = Gtk.Frame(label=t('wl.exceptions'))
            exceptions_box = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=5)
            exceptions_box.set_margin_top(5)
            exceptions_box.set_margin_bottom(5)
            exceptions_box.set_margin_start(5)
            exceptions_box.set_margin_end(5)
            
            bypass_proxy_check = Gtk.CheckButton(label=t('wl.bypass_proxy'))
            bypass_proxy_check.set_active(self.whitelist.get("bypass_proxy", True))
            
            bypass_dpi_check = Gtk.CheckButton(label=t('wl.bypass_dpi'))
            bypass_dpi_check.set_active(self.whitelist.get("bypass_dpi", False))
            # ⭐ v2.0.9: РАБОТАЕТ (раньше «Пока не реализовано»):
            # nfqws — IP белого списка попадают в nft set и НЕ
            # заворачиваются в очередь; snimod и так правит только свои
            # хосты (белый список не нужен); byedpi — см. «исключать из
            # прокси». Изменение применяется при следующем запуске nfqws.
            bypass_dpi_check.set_tooltip_text(
                'nfqws: IP этих адресов/доменов не проходят через десинк\n'
                '(применяется при следующем запуске nfqws).\n'
                'snimod правит только свои хосты — этот флаг на него\n'
                'не влияет.')
            
            exceptions_box.pack_start(bypass_proxy_check, False, False, 0)
            exceptions_box.pack_start(bypass_dpi_check, False, False, 0)
            exceptions_frame.add(exceptions_box)
            
            # Домены
            domains_frame = Gtk.Frame(label=t('wl.domains'))
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
            ips_frame = Gtk.Frame(label=t('wl.ips'))
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
                    self.show_notification(t('wl.title'), t('wl.saved'))
                    
                    # Применяем настройки прокси если белый список включен
                    if self.whitelist["enabled"] and self.whitelist["bypass_proxy"]:
                        self.apply_whitelist_proxy_settings()
                else:
                    self.show_notification(t('notif.error'), t('wl.save_fail'))
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

            # ⭐ ciadpi — SOCKS5-прокси: HTTP CONNECT он не принимает,
            # поэтому переменные окружения обязаны быть socks5://
            # (раньше писался http:// — curl/apt уходили в SOCKS-порт
            # по HTTP-протоколу и падали)
            if host:  # Если хост не пустой
                proxy_url = f"socks5://{host}:{port}"
            else:
                proxy_url = f"socks5://127.0.0.1:{port}"
                
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
        
        # ⭐ Активен ли nfqws: от этого зависит, какие пункты (какого
        # движка) показывать в меню. Вычисляем один раз на сборку меню.
        engine_is_nfqws = (NFQWS_AVAILABLE and self.nfqws
                           and self._active_engine() == 'nfqws')

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

        # ⭐ v2.0.7: ОДНО окно «Настройки режима» (user-проект):
        # вкладки Параметры/Конструктор/Поиск под ВЫБРАННЫЙ режим,
        # строка ввода синхронится с вкладками, дефолт + 4 последних
        # (по режиму). Старые раздельные пункты (Настройки, Конструктор,
        # параметры nfqws/snimod, Поиск стратегии) — выпилены отсюда:
        # всё внутри окна.
        mode_settings_item = Gtk.MenuItem(label='🎛 Настройки режима…')
        mode_settings_item.connect("activate",
                                   self.show_mode_settings)
        menu.append(mode_settings_item)

        # ⭐ v2.0 (user: «должен быть ПЕРЕКЛЮЧАТЕЛЬ — кружочек в
        # овальчике с подписью, не пункт меню с текстом»): в меню
        # AppIndicator свичи невозможны (DBusMenu = только галочка/
        # радио), поэтому пункт «Движки обхода…» открывает окно с
        # НАСТОЯЩИМИ Gtk.Switch — кружочек в овальчике, переключение
        # без закрытия, статус обновляется живьём. Текст пункта
        # показывает текущий выбор.
        engines_item = Gtk.MenuItem(label='⚙ Режимы обхода…')
        engine_names = {'byedpi': 'byedpi (SOCKS)',
                        'nfqws': 'nfqws (NFQUEUE)',
                        'snimod': 'snimod (SNI case-mod)',
                        'bridge': 'DNS-мост (DoT)'}
        eng_now = self._active_engine()
        engines_item.set_label(
            f"⚙ Режимы обхода…  [выбран: "
            f"{engine_names.get(eng_now, eng_now)}]")
        engines_item.set_tooltip_text(
            'Окно с переключателями-свичами: byedpi ↔ nfqws ↔ snimod')
        engines_item.connect("activate", self.show_engines_window)
        menu.append(engines_item)
        # помечаем для синка текста из update_status
        self._engines_item = engines_item
        self._engine_names_map = engine_names

        # Статус выбранного движка отдельной строкой (при NFQUEUE-режимах;
        # при byedpi строки нет — меньше мусора в меню)
        if eng_now in ('nfqws', 'snimod'):
            unit = ('ciadpi-nfqws.service' if eng_now == 'nfqws'
                    else 'ciadpi-snimod.service')
            try:
                r = subprocess.run(
                    ['systemctl', 'is-active', unit],
                    capture_output=True, text=True, timeout=2)
                svc_st = (r.stdout or '').strip() or 'unknown'
            except Exception:
                svc_st = 'unknown'
            svc_item = Gtk.MenuItem(
                label=t('engine.hint_service').format(st=svc_st))
            svc_item.set_sensitive(False)
            menu.append(svc_item)
            # ⭐ v2.0.7: параметры движков (nfqws-строка, snimod-хосты)
            # переехали в «🎛 Настройки режима…» — здесь больше пунктов нет

        proxy_item = Gtk.MenuItem(label=t('menu.proxy'))
        proxy_item.connect("activate", self.show_proxy_settings)
        if not engine_is_nfqws:
            menu.append(proxy_item)

        # ⭐ v2.0.6: ПРОФИЛИ — выбор/создание/удаление наборов настроек
        # для разных сетей (user: «переключаться между профилями»)
        try:
            import ciadpi_profiles  # noqa: F401
            profiles_item = Gtk.MenuItem(label='🗂 Профили…')
            profiles_item.connect("activate", self.show_profiles_dialog)
            menu.append(profiles_item)
        except ImportError:
            pass

        # БЕЛЫЙ СПИСОК (универсален: перечень «своих» хостов, nfqws
        # сейчас его не использует, но он пригодится при расширении)
        whitelist_item = Gtk.MenuItem(label=t('menu.whitelist'))
        whitelist_item.connect("activate", self.show_whitelist_dialog)
        menu.append(whitelist_item)        
        
        menu.append(Gtk.SeparatorMenuItem())

        # ⭐ v2.0.7: автопоиск/история/поиск стратегии переехали
        # в «🎛 Настройки режима…» (вкладка «Поиск стратегии», работает
        # под выбранный режим). Обновление byedpi — общее, остаётся.

        # Обновление byedpi без переустановки — byedpi-пункт
        if not engine_is_nfqws:
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
        """⭐ v2.0.4: тикер НИКОГДА не блокирует GTK.

        Раньше каждые 3с в главном потоке выполнялись ДВА subprocess-
        вызова (systemctl is-active + systemctl show) — во время
        переключения движков systemctl занят job-lock'ом, вызовы висели
        по 2-6 секунд и ВЕСЬ интерфейс трея морозился («трей не
        выключается», «окно виснет»). Теперь: фоновый поток собирает
        статус, idle_add применяет только GTK-обновления. Повторный
        тик во время сбора — пропуск (флаг _status_busy).
        """
        if getattr(self, '_status_busy', False):
            return True
        self._status_busy = True

        def worker():
            try:
                engine = self._active_engine()
                engine_units = {'nfqws': 'ciadpi-nfqws.service',
                                'snimod': 'ciadpi-snimod.service',
                                'bridge': 'ciadpi-dotbridge.service'}
                unit = engine_units.get(engine, 'ciadpi.service')
                try:
                    r = subprocess.run(
                        ['systemctl', 'is-active', unit],
                        capture_output=True, text=True, timeout=3)
                    status = (r.stdout or '').strip() or 'unknown'
                except Exception:
                    status = 'unknown'
                # ⭐ v2.0.5: текст параметров для тултипа собираем ЗДЕСЬ,
                # в фоне — update_tooltip больше не зовёт systemctl сам
                params_text = None
                if engine == 'byedpi':
                    try:
                        params_text = self.get_current_service_params()
                    except Exception:
                        params_text = None
                if engine == 'bridge':
                    status = ('active' if status == 'active' else status)
                GLib.idle_add(self._apply_status_ui, engine, status, params_text)
            finally:
                self._status_busy = False

        threading.Thread(target=worker, daemon=True).start()
        return True

    def _apply_status_ui(self, engine, status, params_text=None):
        """GTK-часть обновления статуса (только главный поток,
        только быстрые операции — ни одного subprocess)."""
        try:
            if status == 'active':
                status_text = (t('status.running_nfqws') if engine == 'nfqws'
                               else ('SNI case-mod: работает'
                                     if engine == 'snimod'
                                     else ('DNS-мост: работает'
                                           if engine == 'bridge'
                                           else t('status.running'))))
                status_label = (
                    t('status.running_s_nfqws') if engine == 'nfqws'
                    else ('SNI case-mod: активен' if engine == 'snimod'
                          else ('DNS-мост: активен' if engine == 'bridge'
                                else t('status.running_s'))))
            else:
                status_text = t('status.stopped')
                status_label = t('status.stopped_s')

            if hasattr(self, 'status_item') and self.status_item:
                self.status_item.set_label(status_label)

            # синк пункта «Движки обхода…» (текст = выбранный движок)
            item = getattr(self, '_engines_item', None)
            names = getattr(self, '_engine_names_map', None) or {}
            if item is not None:
                try:
                    item.set_label(
                        f"⚙ Движки обхода…  [выбран: "
                        f"{names.get(engine, engine)}]")
                except Exception:
                    pass

            if hasattr(self, 'indicator') and self.indicator:
                if status == 'active':
                    self.indicator.set_icon_full(
                        "network-transmit-receive-symbolic",
                        t('status.running_s'))
                else:
                    self.indicator.set_icon_full(
                        "network-offline-symbolic", t('status.stopped_s'))
                self.update_tooltip(params_text)
            elif hasattr(self, 'status_icon') and self.status_icon:
                if status == 'active':
                    self.status_icon.set_from_icon_name(
                        "network-transmit-receive-symbolic")
                else:
                    self.status_icon.set_from_icon_name(
                        "network-offline-symbolic")
                self.status_icon.set_tooltip_text(
                    t('status.running_s') if status == 'active'
                    else t('status.stopped_s'))

        except Exception:
            if hasattr(self, 'status_item') and self.status_item:
                self.status_item.set_label(t('status.error'))
        return False  # одноразовый idle
    
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
        """Диалог настроек прокси.

        Поля заполняются из НАШЕГО конфига (proxy_host/proxy_port/proxy_mode),
        а не из gsettings — иначе в local-режиме системные настройки пусты
        и выглядит, будто ничего не задано. Статус-блок показывает:
        сохранённый режим, хост:порт из конфига, текущее системное состояние
        и флаг мы_меняли_систему.
        """
        # Текущие системные настройки — только для статуса
        current_settings = self.get_system_proxy_settings()

        dialog = Gtk.Dialog(title=t('proxy.title'), flags=0)
        dialog.add_buttons(t('btn.cancel'), Gtk.ResponseType.CANCEL,
                        t('btn.ok'), Gtk.ResponseType.OK)
        dialog.set_default_size(500, 420)

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
        mode_combo.set_tooltip_text(t('proxy.mode_pac_h'))

        # ⭐ Режим берём ИЗ КОНФИГА (что пользователь задал последним),
        # а не из gsettings
        saved_mode = self.current_params.get('proxy_mode', 'none') or 'none'
        if saved_mode == 'auto':
            mode_combo.set_active(0)
        elif saved_mode == 'manual':
            mode_combo.set_active(1)
        elif saved_mode == 'local':
            mode_combo.set_active(3)
        else:
            mode_combo.set_active(2)

        # ⭐ Хост и порт — из конфига; пусто только если юзер не задал
        saved_host = self.current_params.get('proxy_host', '')
        saved_port = str(self.current_params.get('proxy_port', '1080') or '1080')

        # Настройки ручного прокси
        manual_frame = Gtk.Frame(label=t('proxy.manual_frame'))
        manual_box = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=5)
        manual_box.set_margin_top(5)
        manual_box.set_margin_bottom(5)
        manual_box.set_margin_start(5)
        manual_box.set_margin_end(5)
        
        # Хост
        host_label = Gtk.Label(label=t('proxy.host'))
        host_label.set_xalign(0)
        host_entry = Gtk.Entry()
        host_entry.set_placeholder_text(t('proxy.host_ph'))
        host_entry.set_text(saved_host)
        
        # Порт
        port_label = Gtk.Label(label=t('proxy.port'))
        port_label.set_xalign(0)
        port_entry = Gtk.Entry()
        port_entry.set_text(saved_port)
        
        # Примеры форматов
        examples_label = Gtk.Label(label=t('proxy.host_ph'))
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
        info_label.set_xalign(0)

        # Подсказка для локального режима (видна при выборе "Локальный")
        local_hint_label = Gtk.Label(label=t('proxy.local_hint'))
        local_hint_label.set_sensitive(False)
        local_hint_label.set_xalign(0)
        local_hint_label.set_line_wrap(True)
        
        # ⭐ ЖИВОЙ СТАТУС: что задано в конфиге + что в системе сейчас
        mode_names = {
            'auto': t('proxy.mode_pac'), 'manual': t('proxy.mode_manual'),
            'none': t('proxy.mode_off'), 'local': t('proxy.mode_local'),
        }
        cfg_mode_name = mode_names.get(saved_mode, saved_mode or '—')
        cfg_host_disp = saved_host if saved_host else '127.0.0.1'
        sys_mode = current_settings.get('mode', 'none')
        sys_mode_name = mode_names.get(sys_mode, sys_mode or '—')
        sys_host = current_settings.get('http_host', '')
        sys_port = current_settings.get('http_port', '')

        # ⭐ ЖИВАЯ ПРОБА ПОРТА: слушает ли сервис этот порт прямо сейчас
        # (диагностика «прокси применён, но не отвечает»)
        probe_host = saved_host if saved_host else '127.0.0.1'
        try:
            import socket as _socket
            _s = _socket.socket(_socket.AF_INET, _socket.SOCK_STREAM)
            _s.settimeout(0.8)
            port_alive = _s.connect_ex((probe_host, int(saved_port))) == 0
            _s.close()
        except Exception:
            port_alive = False

        status_lines = [
            f"💾 {t('proxy.saved_state')}: {cfg_mode_name}  →  {cfg_host_disp}:{saved_port}",
        ]
        if saved_mode == 'local':
            status_lines.append(f"🖥️ {t('proxy.system_now')}: {sys_mode_name}"
                                + (f" ({sys_host}:{sys_port})" if sys_mode == 'manual' else ""))
            status_lines.append(t('proxy.local_active'))
        elif saved_mode == 'manual':
            if sys_mode == 'manual' and sys_host == saved_host \
                    and sys_port == saved_port:
                status_lines.append("✅ " + t('proxy.applied_ok'))
            else:
                status_lines.append("⚠️ " + t('proxy.not_applied'))
        elif saved_mode == 'none':
            status_lines.append("✅ " + t('proxy.applied_ok'))

        # ⭐ Результат живой пробы — сразу видно, отвечает ли порт
        # (проба = TCP-соединение с host:port; загорается в статус-блоке)
        status_lines.append((t('proxy.probe_ok') if port_alive else t('proxy.probe_fail'))
                            + f"\n   {probe_host}:{saved_port}")
        status_lines.append(t('proxy.type_socks'))

        status_label = Gtk.Label(label="\n".join(status_lines))
        status_label.set_xalign(0)
        status_label.set_line_wrap(True)
        status_label.set_tooltip_text(t('proxy.probe_hint'))
        status_label.get_style_context().add_class('dim-label')

        # ЧЕКБОКС для автоматического отключения прокси
        auto_disable_check = Gtk.CheckButton(label=t('proxy.auto_disable'))
        auto_disable_check.set_active(self.current_params.get("auto_disable_proxy", False))
        auto_disable_check.set_tooltip_text(t('proxy.auto_disable_h'))
                
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
                # Если раньше меняли системные — возвращаем как было.
                # ⭐ Раньше смотрели только флаг в памяти: после перезапуска
                # программы он False (даже если система остаётся нашей),
                # и «залипший» ручной прокси не вычищался. Теперь: если
                # флаг не стоит, но в системе наши значения — тоже откат.
                need_restore = self.we_changed_proxy
                if not need_restore:
                    sys_now = self.get_system_proxy_settings()
                    if (sys_now.get('mode') == 'manual'
                            and sys_now.get('socks_host') in ('127.0.0.1', 'localhost')
                            and sys_now.get('socks_port') == proxy_port):
                        # система указывает на наш SOCKS — это наш след
                        need_restore = True
                        print("🔌 Обнаружен наш прокси в системе без флага — откатываю")
                if need_restore:
                    self.restore_system_proxy_backup()
                    self.we_changed_proxy = False
                    print("💾 Локальный режим: системные настройки прокси восстановлены")

                # ⭐ ЛОКАЛЬНЫЙ РЕЖИМ ТОЖЕ ТРЕБУЕТ ЖИВОГО СЕРВИСА: прокси
                # доступен приложениям только если ciadpi слушает порт.
                # Раньше local можно было включить при остановленном сервисе —
                # «порт указан, а прокси не отвечает».
                if self._ensure_service_running_for_proxy():
                    self._sync_service_port_with_proxy(proxy_port)

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
            restored_original = False
            if selected_mode == 'manual':
                # ВКЛЮЧАЕМ НАШ ПРОКСИ В СИСТЕМЕ.
                # ⭐ Бэкап обязателен: если флаг стоит, но бэкапа нет ни в
                # памяти, ни на диске (остался от старого бага) — снимаем
                # заново, иначе restore потом откатит «в никуда».
                if not self.we_changed_proxy:
                    self.save_system_proxy_backup()
                    self.we_changed_proxy = True
                    print("💾 Включен наш прокси, сохранены системные настройки")
                elif not self.original_system_proxy and \
                        not self._load_system_proxy_backup_from_disk():
                    self.save_system_proxy_backup()
                    print("💾 Флаг был, но бэкапа нет — снят заново")
            
            elif selected_mode == 'none' and self.we_changed_proxy:
                # ОТКЛЮЧАЕМ ПРОКСИ — восстанавливаем оригинал
                self.restore_system_proxy_backup()
                self.we_changed_proxy = False
                restored_original = True
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
        
            # ⭐ ПРИМЕНЕНИЕ НАСТРОЕК
            # Если только что восстановили оригинал — НЕ применяем ничего
            # поверх (иначе затрём восстановленные настройки пользователя).
            # Во всех остальных случаях применяем выбранный режим к системе.
            apply_result = None
            if not restored_original:
                apply_mode = selected_mode if selected_mode in ('manual', 'auto', 'none') else 'none'

                # ⭐ MANUAL/LOCAL: сервис обязан работать и слушать именно
                # этот порт — иначе браузер уходит на мёртвый адрес
                # (баг: сервис без -p слушал 1080, gsettings — 8080).
                if selected_mode in ('manual', 'local'):
                    if self._ensure_service_running_for_proxy():
                        self._sync_service_port_with_proxy(proxy_port)

                # ⭐ AUTO (PAC) без URL = сломанный прокси. GNOME показывает
                # «Автоматический», но PAC пуст — сеть не работает вовсе.
                if apply_mode == 'auto':
                    pac_url = (current_settings.get('pac_url') or '').strip()
                    if not pac_url:
                        print("⚠️ PAC URL пуст — авто-режим сломает сеть, применяю manual")
                        self.show_notification(
                            t('notif.warning'),
                            "PAC URL не задан — применён ручной режим (auto без PAC не работает)",
                            category='proxy')
                        apply_mode = 'manual'

                apply_result = self.apply_system_proxy(apply_mode, proxy_host, proxy_port)

            # ⭐ УВЕДОМЛЕНИЕ С РЕАЛЬНЫМ РЕЗУЛЬТАТОМ
            if restored_original:
                self.show_notification(t('notif.proxy_applied'),
                                       t('proxy.restored_original'), category='proxy')
            elif apply_result:
                self.show_notification(
                    t('notif.proxy_applied'),
                    f"{mode_names.get(selected_mode, selected_mode)} → "
                    f"{proxy_host or '127.0.0.1'}:{proxy_port}",
                    category='proxy')
            else:
                self.show_notification(t('notif.error'),
                                       t('proxy.apply_failed'), category='proxy')

        dialog.destroy()

    def _sync_service_port_with_proxy(self, proxy_port):
        """Синхронизирует порт ciadpi в юните с портом прокси из диалога.

        ⭐ Раньше «Поиск стратегии» применял комбинации БЕЗ -p:
        сервис слушал дефолтный 1080, а системный прокси указывал
        на 127.0.0.1:8080 из конфига — браузер ходил в пустоту.
        Здесь: если в текущих параметрах юнита нет -p (или он другой)
        и юнит запущен — дописываем/меняем -p через update_param_in_string
        и перезапускаем сервис.
        Возвращает True, если сервис уже слушает нужный порт.
        """
        try:
            port = str(proxy_port).strip()
            if not port.isdigit():
                return False

            # Текущая строка параметров юнита
            params_str = self.get_current_service_params() or ''
            parsed = parse_params(params_str)
            cur_port = get_value(parsed, '-p')

            if cur_port and str(cur_port) == port:
                return True  # уже синхронно

            print(f"🔌 Порт сервиса ({cur_port or 'default 1080'}) != порт прокси ({port}) — синхронизирую")
            new_params = update_param_in_string(params_str, '-p', int(port))
            ok = self.update_service_params(new_params, apply_proxy=False)
            if ok:
                print(f"✅ Сервис перезапущен с -p {port}")
            return ok
        except Exception as e:
            print(f"⚠️ Синхронизация порта не удалась: {e}")
            return False

    def _ensure_service_running_for_proxy(self):
        """Для manual/local-режима прокси сервис обязан работать.

        ⭐ Раньше можно было включить системный прокси при остановленном
        сервисе — gsettings указывали на мёртвый порт.
        Возвращает True если сервис active (запущен при необходимости).
        """
        try:
            r = subprocess.run(['systemctl', 'is-active', 'ciadpi.service'],
                               capture_output=True, text=True, timeout=3)
            if r.stdout.strip() == 'active':
                return True
            print("▶️ Прокси-режим требует сервис — запускаю ciadpi.service")
            ok, err = self._systemctl('start', 'ciadpi.service')
            if not ok:
                print(f"❌ Не удалось запустить сервис: {err}")
                self.show_notification(t('notif.error'),
                                       f"ciadpi.service: {err}", category='service')
                return False
            time.sleep(2)
            return True
        except Exception as e:
            print(f"⚠️ Проверка сервиса: {e}")
            return False

    def get_system_proxy_settings(self):
        """Получение текущих системных настроек прокси.

        ⭐ host/port читаем ВСЕГДА (не только при mode='manual'):
        GNOME хранит значения ручных полей и при выключенном прокси.
        Если исходным режимом был none, а мы прочли только дефолты —
        после «восстановления» в полях останутся наши 127.0.0.1:порт.
        """
        settings = {
            'mode': 'none',
            'http_host': '',
            'http_port': '8080',  # дефолтный порт
            'socks_host': '',
            'socks_port': '1080',
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

                # ⭐ Ручные поля читаем при ЛЮБОМ режиме (GNOME их хранит
                # даже в none — туда же они попадают после нашей установки)
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

                # ⭐ SOCKS-поля тоже бэкапим — наш прокси живёт именно там,
                # восстановление обязано вернуть и их
                socks_host_r = subprocess.run([
                    'gsettings', 'get', 'org.gnome.system.proxy.socks', 'host'
                ], capture_output=True, text=True, check=False)
                socks_port_r = subprocess.run([
                    'gsettings', 'get', 'org.gnome.system.proxy.socks', 'port'
                ], capture_output=True, text=True, check=False)
                if socks_host_r.returncode == 0:
                    settings['socks_host'] = socks_host_r.stdout.strip().strip("'")
                if socks_port_r.returncode == 0:
                    settings['socks_port'] = socks_port_r.stdout.strip()

                # Игнорируемые хосты — тоже при любом режиме
                ignore_result = subprocess.run([
                    'gsettings', 'get', 'org.gnome.system.proxy', 'ignore-hosts'
                ], capture_output=True, text=True, check=False)
                if ignore_result.returncode == 0:
                    settings['ignore_hosts'] = ignore_result.stdout.strip()

                if mode == 'auto':
                    # Для автоматического режима можно сохранить PAC URL
                    pac_result = subprocess.run([
                        'gsettings', 'get', 'org.gnome.system.proxy', 'autoconfig-url'
                    ], capture_output=True, text=True, check=False)
                    
                    if pac_result.returncode == 0:
                        settings['pac_url'] = pac_result.stdout.strip().strip("'")
                            
        except Exception as e:
            print(f"❌ Ошибка получения настроек прокси: {e}")
        
        return settings

    def apply_system_proxy(self, mode, host, port, apply_whitelist=True):
        """Применение системных настроек прокси через GNOME (gsettings).

        ⭐ CRITICAL: ciadpi — это SOCKS5-прокси (HTTP CONNECT он НЕ
        принимает: 'ss: invalid version: 0x43'). Раньше адрес писался
        в http/https/ftp-схемы — браузеры честно шли по HTTP-протоколу
        в SOCKS-порт и ломались. Теперь:
          - manual → режим 'manual' + адрес ТОЛЬКО в socks-схему,
            http/https/ftp при этом сбрасываются к заводским;
          - если в системе включён use-same-proxy — отключаем его:
            он заставляет всё идти через http-схему.

        apply_whitelist=False — режим восстановления исходных настроек:
        белый список не вмешивается (иначе он затрёт оригинальный
        ignore-hosts, который restore восстановит следом).
        """
        try:
            # Только применяем настройки, не сохраняем оригинальные здесь
            # Оригинальные сохраняются только при первом включении нашего прокси

            subprocess.run([
                'gsettings', 'set', 'org.gnome.system.proxy', 'mode', mode
            ], check=False)

            if mode == 'manual':
                # ⭐ Пишем в SOCKS-схему — ciadpi говорит по SOCKS5
                subprocess.run([
                    'gsettings', 'set', 'org.gnome.system.proxy.socks', 'host',
                    host if host else '127.0.0.1'
                ], check=False)
                subprocess.run([
                    'gsettings', 'set', 'org.gnome.system.proxy.socks', 'port',
                    str(port)
                ], check=False)

                # HTTP/HTTPS/FTP-схемы НЕ должны указывать на SOCKS-порт:
                # сбрасываем к заводским (иначе браузер пытается HTTP CONNECT
                # в SOCKS-порт и падает)
                for schema in ('http', 'https', 'ftp'):
                    subprocess.run(['gsettings', 'reset',
                                    f'org.gnome.system.proxy.{schema}', 'host'],
                                   check=False)
                    subprocess.run(['gsettings', 'reset',
                                    f'org.gnome.system.proxy.{schema}', 'port'],
                                   check=False)

                # use-same-proxy гоняет трафик через http-схему — выключаем
                subprocess.run([
                    'gsettings', 'set', 'org.gnome.system.proxy', 'use-same-proxy',
                    'false'
                ], check=False)

            elif mode == 'auto':
                # Для автоматического режима обычно нужен PAC URL
                pass

            elif mode == 'none':
                # ⭐ Отключение прокси: вычищаем и ручные поля, иначе
                # в настройках GNOME остаются наши host/port от прошлого
                # manual-применения («не приведено в исходное состояние»).
                for schema in ('http', 'https', 'ftp', 'socks'):
                    subprocess.run(['gsettings', 'reset',
                                    f'org.gnome.system.proxy.{schema}', 'host'],
                                   check=False)
                    subprocess.run(['gsettings', 'reset',
                                    f'org.gnome.system.proxy.{schema}', 'port'],
                                   check=False)

            # ПРИМЕНЯЕМ БЕЛЫЙ СПИСОК ДЛЯ ИГНОРИРУЕМЫХ ХОСТОВ
            if not apply_whitelist:
                # восстановление исходных: ignore-hosts вернёт caller
                pass
            elif self.whitelist.get("enabled", False) and self.whitelist.get("bypass_proxy", True):
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
                # ⭐ ciadpi — SOCKS5: переменные окружения socks5://
                # (curl/apt/wget понимают socks5:// в *_proxy)
                if host:
                    proxy_url = f"socks5://{host}:{port}"
                else:
                    proxy_url = f"socks5://127.0.0.1:{port}"
                
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

        ⭐ ЭТО МОНИТОР, А НЕ СИНХРОНИЗАТОР: конфиг пользователя —
        источник правды. Системное состояние НЕ перезаписывает
        proxy_host/proxy_port/proxy_mode из конфига (это делало
        «прокси потерялся» каждые 5 секунд). Локальный режим вообще
        не смотрит в систему.
        """
        try:
            # Локальный режим: системный прокси нас не интересует
            if self.current_params.get('proxy_mode') == 'local':
                return

            # Только читаем состояние для внутреннего использования
            # (уведомления отслеживания изменений — без записи в конфиг).
            result = subprocess.run([
                'gsettings', 'get', 'org.gnome.system.proxy', 'mode'
            ], capture_output=True, text=True, check=False)

            if result.returncode == 0:
                mode = result.stdout.strip().strip("'")
                if mode == 'manual':
                    host_result = subprocess.run([
                        'gsettings', 'get', 'org.gnome.system.proxy.http', 'host'
                    ], capture_output=True, text=True, check=False)
                    port_result = subprocess.run([
                        'gsettings', 'get', 'org.gnome.system.proxy.http', 'port'
                    ], capture_output=True, text=True, check=False)
                    host = host_result.stdout.strip().strip("'")
                    port = port_result.stdout.strip()
                    print(f"📡 Системный прокси: manual {host}:{port} (конфиг не трогаем)")
                else:
                    print(f"📡 Системный прокси: {mode} (конфиг не трогаем)")

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
        """Сохраняет текущие системные настройки как резервную копию.

        ⭐ Копия пишется и в память, и НА ДИСК (~/.config/ciadpi/proxy_backup.json):
        раньше бэкап жил только в RAM, и после перезапуска индикатора
        «восстановить исходные» было нечем — оставались наши host/port.
        Вызывать СТРОГО ДО apply_system_proxy (иначе в бэкап попадут
        наши же настройки).
        """
        self.original_system_proxy = self.get_system_proxy_settings()
        # маркер: поля host/port захвачены при ЛЮБОМ режиме (v1.6.1+).
        # Старые бэкапы (только manual) не имеют его — при восстановлении
        # их поля нельзя писать вслепую.
        self.original_system_proxy['fields_captured'] = True
        print("💾 Создана резервная копия системных настроек прокси:")
        print(f"   Режим: {self.original_system_proxy.get('mode')}")
        print(f"   Хост: {self.original_system_proxy.get('http_host')}")
        print(f"   Порт: {self.original_system_proxy.get('http_port')}")

        # Персистентная копия на диск
        try:
            backup_file = Path.home() / '.config' / 'ciadpi' / 'proxy_backup.json'
            backup_file.parent.mkdir(parents=True, exist_ok=True)
            with open(backup_file, 'w', encoding='utf-8') as f:
                json.dump(self.original_system_proxy, f, indent=2, ensure_ascii=False)
            print(f"💾 Резервная копия записана на диск: {backup_file}")
        except Exception as e:
            print(f"⚠️ Не удалось записать бэкап на диск: {e}")

    def _load_system_proxy_backup_from_disk(self):
        """Загружает сохранённый на диск бэкап исходных настроек (или None)."""
        try:
            backup_file = Path.home() / '.config' / 'ciadpi' / 'proxy_backup.json'
            if backup_file.exists():
                with open(backup_file, 'r', encoding='utf-8') as f:
                    data = json.load(f)
                    if isinstance(data, dict) and 'mode' in data:
                        return data
        except Exception as e:
            print(f"⚠️ Не удалось прочитать бэкап с диска: {e}")
        return None

    def _clear_system_proxy_backup_on_disk(self):
        """Удаляет дисковый бэкап после успешного восстановления."""
        try:
            backup_file = Path.home() / '.config' / 'ciadpi' / 'proxy_backup.json'
            if backup_file.exists():
                backup_file.unlink()
                print("💾 Дисковый бэкап исходных настроек удалён (восстановление завершено)")
        except Exception as e:
            print(f"⚠️ Не удалось удалить бэкап: {e}")

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

        Ничего не запускает автоматически: только синхронизирует прокси,
        ЕСЛИ сервис уже работает. Автостарт сервиса отключён.
        ⭐ Флаг we_changed_proxy ставим только если реально применили
        настройки к системе (иначе «Выход» откатывал чужие настройки).
        """
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
                # ⭐ НО: если в конфиге manual и прошлый раз мы применяли прокси,
                # флаг остаётся как есть — решает exit_app при остановке сервиса.
                return False

            # Если сервис запущен И у нас есть настройки прокси - восстанавливаем
            if (service_running and 
                self.current_params.get("proxy_enabled", False) and 
                self.current_params.get("proxy_mode") == 'manual'):
                
                print("🔄 Восстанавливаем наши настройки прокси при запуске...")
                print(f"🔍 Флаг we_changed_proxy: {self.we_changed_proxy}")
                
                host = self.current_params.get("proxy_host", "")
                port = self.current_params.get("proxy_port", "1080")

                # ⭐ ПОРТ СЕРВИСА ДОЛЖЕН СОВПАДАТЬ: сервис мог быть
                # перезапущен «Поиском стратегии» без -p (слушает 1080)
                self._sync_service_port_with_proxy(port)

                # ⭐ БЭКАП ИСХОДНЫХ СИСТЕМНЫХ НАСТРОЕК — СТРОГО ДО apply:
                # иначе в копию попадут наши же host/port, и «восстановление»
                # вернёт наш прокси вместо исходного.
                if not self.we_changed_proxy:
                    self.save_system_proxy_backup()
                    self.we_changed_proxy = True
                    self.save_config()
                    print("💾 Бэкап исходных настроек снят ДО применения нашего прокси")

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
        """Восстанавливает ОРИГИНАЛЬНЫЕ системные настройки прокси.

        ⭐ Раньше метод молча выходил, если не включён чекбокс
        «автоотключение» — но вызывается он и из других мест
        (переход в local-режим, выбор «Выключен»), где восстановить
        исходные настройки нужно БЕЗУСЛОВНО: мы меняли систему —
        обязаны вернуть как было.
        ⭐ Бэкап берём из памяти, а если программа перезапускалась —
        с диска (~/.config/ciadpi/proxy_backup.json). Если бэкапа нет
        вообще — не просто ставим mode=none, а вычищаем ВСЕ наши
        следы (host/port в http/https/ftp, ignore-hosts, .proxy_env),
        чтобы в настройках GNOME не оставались наши значения.
        """
        if not self.we_changed_proxy:
            print("ℹ️ Мы не меняли прокси - нечего восстанавливать")
            return False

        try:
            # Бэкап из памяти или с диска (после перезапуска программы)
            backup = self.original_system_proxy
            if not backup:
                backup = self._load_system_proxy_backup_from_disk()
            if not backup:
                # Бэкапа нет: вычищаем наши следы полностью
                print("ℹ️ Нет сохранённых исходных настроек — вычищаем наши следы")
                self.apply_system_proxy('none', '', '0')
                subprocess.run(['gsettings', 'reset',
                                'org.gnome.system.proxy', 'ignore-hosts'],
                               check=False)
                self.restore_original_environment()
                self._clear_system_proxy_backup_on_disk()
                return True

            original_mode = backup.get('mode', 'none')
            fields_captured = backup.get('fields_captured', False)

            # Поля host/port: пишем только из нового бэкапа (fields_captured),
            # старые бэкапы без маркера полей при none-режиме не содержат.
            if fields_captured:
                original_host = backup.get('http_host', '')
                original_port = backup.get('http_port', '8080')
            elif original_mode == 'manual':
                # старый бэкап manual-режима: поля валидны
                original_host = backup.get('http_host', '')
                original_port = backup.get('http_port', '8080')
            else:
                # старый бэкап none/auto без полей — сбрасываем ручные поля
                # к заводским, чтобы не оставить наши значения в GNOME
                original_host = None
                original_port = None

            print("🔄 Восстанавливаем исходные системные настройки прокси...")
            print(f"   Куда: mode={original_mode} host={original_host or '—'} port={original_port}")

            # Применяем оригинальные настройки
            if original_host is None:
                # Исходные поля неизвестны (старый бэкап) — режим ставим,
                # а ручные поля http/https/ftp/socks сбрасываем к заводским,
                # иначе в GNOME останутся наши 127.0.0.1:порт
                subprocess.run(['gsettings', 'set',
                                'org.gnome.system.proxy', 'mode', original_mode],
                               check=False)
                for schema in ('http', 'https', 'ftp', 'socks'):
                    subprocess.run(['gsettings', 'reset',
                                    f'org.gnome.system.proxy.{schema}', 'host'],
                                   check=False)
                    subprocess.run(['gsettings', 'reset',
                                    f'org.gnome.system.proxy.{schema}', 'port'],
                                   check=False)
                success = True
                print("✅ Режим восстановлен, ручные поля сброшены к заводским")
            else:
                success = self.apply_system_proxy(original_mode, original_host, original_port,
                                                  apply_whitelist=False)
                # ⭐ SOCKS-поля восстанавливаем отдельно: apply пишет их
                # только при manual, а исходный режим мог быть любым
                if success and fields_captured:
                    subprocess.run(['gsettings', 'set',
                                    'org.gnome.system.proxy.socks', 'host',
                                    backup.get('socks_host', '')],
                                   check=False)
                    subprocess.run(['gsettings', 'set',
                                    'org.gnome.system.proxy.socks', 'port',
                                    str(backup.get('socks_port', '1080'))],
                                   check=False)
                    print(f"✅ SOCKS-поля восстановлены: "
                          f"{backup.get('socks_host', '')}:{backup.get('socks_port', '1080')}")

            # Восстанавливаем оригинальный ignore-hosts из бэкапа
            original_ignore = backup.get('ignore_hosts')
            if original_ignore is not None:
                subprocess.run(['gsettings', 'set', 'org.gnome.system.proxy',
                                'ignore-hosts', original_ignore],
                               check=False)
                print(f"✅ ignore-hosts восстановлен: {original_ignore}")
            else:
                subprocess.run(['gsettings', 'reset',
                                'org.gnome.system.proxy', 'ignore-hosts'],
                               check=False)

            # Восстанавливаем PAC URL, если был auto-режим
            if original_mode == 'auto' and backup.get('pac_url'):
                subprocess.run(['gsettings', 'set', 'org.gnome.system.proxy',
                                'autoconfig-url', backup['pac_url']],
                               check=False)

            if success:
                self.restore_original_environment()
                self._clear_system_proxy_backup_on_disk()
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
                GLib.idle_add(self.update_status)
            except Exception as e:
                self.show_notification(t('notif.error'), str(e), category='service')
        
        threading.Thread(target=run_in_thread, daemon=True).start()

    def _enginectl_op(self, verb, engine=None):
        """Единая операция запуска/останова/рестарта через бэкенд.

        ⭐ v2.0.6 (user: «не ясно, синхронизированы ли команды из меню
        с окном движков»): теперь и меню, и окно «Режимы обхода»
        ходят в ОДИН бэкенд ciadpi_enginectl — рассинхрон невозможен.
        Все вызовы фоновые (GTK не блокируется), повторный старт
        активного движка = no-op, чужие движки гарантированно гасятся.
        """
        target = engine or self._active_engine()
        managers = {'nfqws': self.nfqws, 'snimod': self.snimod}

        def worker():
            try:
                import ciadpi_enginectl as ec
            except ImportError:
                import sys
                sys.path.insert(0, str(Path(__file__).resolve().parent))
                import ciadpi_enginectl as ec
            if target == 'bridge':
                if verb == 'start':
                    ok, msg = ec.start_bridge()
                elif verb == 'stop':
                    ok, msg = ec.stop_bridge()
                else:
                    ec.stop_bridge()
                    ok, msg = ec.start_bridge()
            else:
                if verb == 'start':
                    ok, msg = ec.start_engine(target, managers)
                elif verb == 'stop':
                    ok, msg = ec.stop_engine(target, managers)
                else:
                    ok, msg = ec.restart_engine(target, managers)
            def done():
                kind = t('notif.success') if ok else t('notif.error')
                self.show_notification(kind, msg, category='service')
                self.update_status()
                self.rebuild_menu()
                return False
            GLib.idle_add(done)
        threading.Thread(target=worker, daemon=True).start()

    def start_service(self, widget):
        """Запуск выбранного движка (единый бэкенд, v2.0.6)."""
        # byedpi-режим с прокси: применяем прокси после старта (прошлое
        # поведение юзера) — прокси-логика остаётся здесь, только для byedpi
        if self._active_engine() == 'byedpi' and \
                self.current_params.get('proxy_enabled') and \
                self.current_params.get('proxy_mode') == 'manual':
            def start_and_proxy():
                self._enginectl_op('start', 'byedpi')
                time.sleep(2.5)
                if not self.we_changed_proxy:
                    self.save_system_proxy_backup()
                    self.we_changed_proxy = True
                    self.save_config()
                host = self.current_params.get('proxy_host', '127.0.0.1')
                port = self.current_params.get('proxy_port', '1080')
                self._sync_service_port_with_proxy(port)
                self.apply_system_proxy('manual', host, port)
            threading.Thread(target=start_and_proxy, daemon=True).start()
            return
        self._enginectl_op('start')

    def stop_service(self, widget):
        """Остановка выбранного движка (единый бэкенд, v2.0.6)."""
        if self._active_engine() == 'byedpi' and self.we_changed_proxy:
            def stop_and_restore():
                if self.restore_system_proxy_backup():
                    self.we_changed_proxy = False
                    self.current_params['we_changed_proxy'] = False
                    self.save_config()
                self._enginectl_op('stop', 'byedpi')
            threading.Thread(target=stop_and_restore, daemon=True).start()
            return
        self._enginectl_op('stop')

    def restart_service(self, widget):
        """Перезапуск выбранного движка (единый бэкенд, v2.0.6)."""
        self._enginectl_op('restart')

    # ---------------- Переключатель движка: byedpi ↔ nfqws ----------------

    def _active_engine(self):
        """Какой режим ВЫБРАН: 'byedpi' | 'nfqws' | 'snimod' | 'bridge'.

        ⭐ v2.0.6.1: bridge_mode=True в конфиге (выбран DNS-мост в
        окне режимов) → главное меню Start/Stop управляет МОСТОМ.
        Липкий выбор из конфига, живость сервиса — отдельный вопрос.
        """
        cfg = self.current_params or {}
        if cfg.get('bridge_mode'):
            return 'bridge'
        engine = cfg.get('engine', 'byedpi')
        if engine == 'nfqws' and not (NFQWS_AVAILABLE and self.nfqws):
            return 'byedpi'  # модуль nfqws недоступен — безопасный fallback
        if engine == 'snimod' and not (SNIMOD_AVAILABLE and self.snimod):
            return 'byedpi'  # snimod недоступен — безопасный fallback
        return engine

    def switch_engine(self, widget, engine):
        """Смена ВЫБРАННОГО движка (вызов из чекбокса меню, фоновый поток).

        ⭐ v1.9.1: переключение = ВЫБОР, НЕ запуск (user: «при выставлении
        второго способа делается автоматический запуск — не надо»).
        Сервисы не стартуем: пользователь поднимет выбранный движок сам
        через «Запустить сервис» (или он поднимется на ребуте — boot-флаги
        выставляются). Взаимоисключаемость сохраняется: чужой движок
        останавливаем, у nfqws снимаются nft-правила.
        При уходе на nfqws системный прокси откатывается ВСЕГДА (если мы
        его меняли — из бэкапа, иначе просто в 'none'): мёртвый manual-
        прокси у NFQUEUE-режима не нужен и ломает браузеры.
        """
        if not getattr(self, '_engine_switching', False):
            self._engine_switching = True
        else:
            return

        def worker():
            try:
                all_engines = ('byedpi', 'nfqws', 'snimod')
                prev = self._active_engine()
                print(f"🔄 Смена выбранного движка: {prev} → {engine} "
                      f"(без автозапуска)")

                # 1) останавливаем ВСЕ чужие движки (взаимоисключаемость)
                for other in all_engines:
                    if other == engine:
                        continue
                    if other == 'byedpi':
                        self._systemctl('stop', 'ciadpi.service')
                    elif other == 'nfqws' and self.nfqws:
                        ok, err = self.nfqws.stop()
                        if not ok:
                            print(f"⚠️ nfqws stop: {err}")
                        if not self.nfqws.rules_active():
                            self.nfqws.remove_rules_fallback()
                    elif other == 'snimod' and self.snimod:
                        ok, err = self.snimod.stop()
                        if not ok:
                            print(f"⚠️ snimod stop: {err}")
                        if not self.snimod.rules_active():
                            self.snimod.remove_rules_fallback()
                # ⭐ откат системного прокси — БЕЗУСЛОВНО при уходе с
                # byedpi: NFQUEUE-движки прокси не используют, а manual
                # на мёртвом порте ломает браузеры
                if engine != 'byedpi':
                    try:
                        if self.we_changed_proxy:
                            self.restore_system_proxy_backup()
                        else:
                            subprocess.run(
                                ['gsettings', 'set',
                                 'org.gnome.system.proxy', 'mode', 'none'],
                                capture_output=True, timeout=5)
                        self.we_changed_proxy = False
                        self.current_params['we_changed_proxy'] = False
                        self.current_params['proxy_enabled'] = False
                        self.save_config()
                        print("🔌 Системный прокси сброшен "
                              "(NFQUEUE-движки прокси не используют)")
                    except Exception as e:
                        print(f"⚠️ откат прокси при смене движка: {e}")

                # 2) валидация перед ВЫБОРОМ
                if engine == 'nfqws':
                    if not self.nfqws:
                        self.show_notification(t('notif.error'),
                                               t('engine.nfqws_unavailable'),
                                               category='service')
                        return
                    if not self.nfqws.is_installed():
                        self.show_notification(
                            t('notif.error'), t('engine.nfqws_not_installed'),
                            category='service')
                        return
                if engine == 'snimod' and self.snimod \
                        and not self.snimod.is_installed():
                    self.show_notification(
                        t('notif.error'),
                        'snimod не собран: сделайте в snimod/ (make)',
                        category='service')
                    return
                # САМ СЕРВИС НЕ ЗАПУСКАЕМ — только выбор

                self.current_params['engine'] = engine
                self.save_config()
                # ⭐ boot-флаги: на загрузке поднимется именно выбранный
                # движок. Порядок безопасный: сначала enable выбранного,
                # при успехе disable остальных.
                want_unit = {'byedpi': 'ciadpi.service',
                             'nfqws': 'ciadpi-nfqws.service',
                             'snimod': 'ciadpi-snimod.service'}[engine]
                ok_e, err_e = self._unit_boot_ctl(want_unit, True)
                if ok_e:
                    for other_unit in ('ciadpi.service',
                                        'ciadpi-nfqws.service',
                                        'ciadpi-snimod.service'):
                        if other_unit != want_unit:
                            ok_d, err_d = self._unit_boot_ctl(other_unit, False)
                            if not ok_d:
                                print(f"⚠️ boot-флаг: disable {other_unit}: "
                                      f"{err_d}")
                else:
                    print(f"⚠️ boot-флаг: enable {want_unit}: {err_e}")
                engine_names = {'byedpi': 'byedpi (SOCKS)',
                                'nfqws': 'nfqws (NFQUEUE)',
                                'snimod': 'snimod (SNI case-mod)'}
                self.show_notification(
                    t('notif.success'),
                    t('engine.selected').format(
                        name=engine_names.get(engine, engine)),
                    category='service')
                GLib.idle_add(self.update_status)
                GLib.idle_add(self.rebuild_menu)
            finally:
                self._engine_switching = False

        threading.Thread(target=worker, daemon=True).start()

    def show_nfqws_settings(self, widget=None):
        """Диалог параметров nfqws-движка (формат zapret, не byedpi!)."""
        if not self.nfqws:
            self.show_notification(t('notif.error'), t('engine.nfqws_unavailable'))
            return

        dialog = Gtk.Dialog(title=t('engine.nfqws_title'), flags=0)
        dialog.add_buttons(t('btn.cancel'), Gtk.ResponseType.CANCEL,
                           t('btn.ok'), Gtk.ResponseType.OK)
        dialog.set_default_size(640, 380)

        content = dialog.get_content_area()
        vbox = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=10)
        vbox.set_margin_top(10); vbox.set_margin_bottom(10)
        vbox.set_margin_start(10); vbox.set_margin_end(10)

        lbl = Gtk.Label(label=t('engine.nfqws_params'))
        lbl.set_xalign(0)
        entry = Gtk.Entry()
        cfg = self.nfqws.load_config()
        entry.set_text(cfg.get('params', self.nfqws.default_params))
        entry.set_width_chars(60)

        hint = Gtk.Label()
        hint.set_markup(f"<small>{t('engine.nfqws_hint')}</small>")
        hint.set_xalign(0)
        hint.set_line_wrap(True)

        # Примеры для zapret-формата
        examples_frame = Gtk.Frame(label=t('settings.examples'))
        ex_box = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=4)
        ex_box.set_margin_top(8); ex_box.set_margin_bottom(8)
        ex_box.set_margin_start(8); ex_box.set_margin_end(8)
        for ex in (
            '--filter-tcp=80,443 --dpi-desync=disorder2 --dpi-desync-split-pos=1',
            '--filter-tcp=443 --dpi-desync=split2 --dpi-desync-split-pos=1 --dpi-desync-fake-tls=/opt/zapret/files/fake/tls_clienthello_www_google_com.bin',
            '--filter-tcp=80,443 --dpi-desync=fake,fake,split2 --dpi-desync-split-pos=1 --dpi-desync-ttl=4',
            '--filter-tcp=443 --dpi-desync=syndata',
        ):
            e = Gtk.Entry(); e.set_text(ex); e.set_editable(False)
            e.set_can_focus(False); e.set_hexpand(True)
            row = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=5)
            row.pack_start(e, True, True, 0)
            cp = Gtk.Button.new_from_icon_name("edit-copy-symbolic",
                                                Gtk.IconSize.BUTTON)
            cp.connect("clicked", self.on_copy_example, ex)
            row.pack_start(cp, False, False, 0)
            ex_box.pack_start(row, False, False, 0)

        info = Gtk.Label()
        ver = self.nfqws.check_binary() or '—'
        info.set_markup(f"<small>nfqws: {ver}</small>")
        info.set_xalign(0)

        vbox.pack_start(lbl, False, False, 0)
        vbox.pack_start(entry, False, False, 0)
        vbox.pack_start(hint, False, False, 0)
        vbox.pack_start(examples_frame, False, False, 0)
        vbox.pack_start(info, False, False, 0)
        content.pack_start(vbox, True, True, 0)
        content.show_all()

        while True:
            response = dialog.run()
            if response != Gtk.ResponseType.OK:
                break
            params = entry.get_text().strip()
            # валидация через сам nfqws (--dry-run)
            try:
                r = subprocess.run(
                    [str(self.nfqws.nfqws_bin), '--dry-run',
                     '--qnum', str(self.nfqws.QNUM),
                     '--dpi-desync-fwmark', self.nfqws.DESYNC_MARK]
                    + params.split(),
                    capture_output=True, text=True, timeout=10)
                if r.returncode != 0:
                    err_d = Gtk.MessageDialog(
                        transient_for=dialog, flags=0,
                        message_type=Gtk.MessageType.ERROR,
                        buttons=Gtk.ButtonsType.OK,
                        text=(r.stderr or r.stdout or '')[-400:])
                    err_d.run(); err_d.destroy()
                    continue
            except Exception as e:
                print(f"⚠️ dry-run nfqws: {e}")

            cfg['params'] = params
            self.nfqws.save_config(cfg)
            # если сервис активен — перезаписываем юнит и рестартуем
            if self.nfqws.is_service_active():
                threading.Thread(target=self.nfqws.write_unit, args=(params,),
                                 daemon=True).start()
            break
        dialog.destroy()

    # ---------------- ⭐ v2.0: окно-переключатель движков ----------------

    def show_mode_settings(self, widget=None):
        """⭐ v2.0.7: ОДНО окно настроек выбранного режима.

        Вкладки Параметры/Конструктор/Поиск — под выбранный режим,
        строка ввода синхронизируется со всеми вкладками. Полный
        код окна — ciadpi_mode_settings.py (ModeSettingsWindow).
        """
        try:
            import ciadpi_mode_settings
        except ImportError:
            import sys
            sys.path.insert(0, str(Path(__file__).resolve().parent))
            import ciadpi_mode_settings
        if getattr(self, '_mode_settings_window', None) is None:
            self._mode_settings_window = \
                ciadpi_mode_settings.ModeSettingsWindow(self)
        # хуки конструкторов для вкладки «Конструктор»
        self._mode_settings_window.param_builder_cb = \
            self._build_full_byedpi_builder
        self._mode_settings_window.nfqws_builder_cb = \
            self._build_nfqws_builder_widget
        self._mode_settings_window.present()

    def _build_byedpi_builder_widget(self):
        """Компактный конструктор byedpi для вкладки «Конструктор».

        Ключевые флаги с живой синхронизацией в params_entry окна
        настроек (on_change-строка = текущая строка параметров).
        """
        try:
            from ciadpi_params_spec import parse_params, \
                update_param_in_string
        except ImportError:
            return None
        return self._build_simple_builder(
            fields=[
                ('-T', 'Тактика (0-9)', 0, 9, 1),
                ('-A', 'Метод десинка (нет/torst/torst2/…)', None, None, None),
                ('-s', 'Смещение сплита', 0, 30, 1),
                ('-r', 'Повторы', 0, 10, 1),
            ],
            parse=parse_params, update=update_param_in_string)

    def _build_nfqws_builder_widget(self):
        """Компактный конструктор nfqws (ключевые десинк-опции)."""
        def parse_nfqws(s):
            out = {}
            for tok in (s or '').split():
                if '=' in tok:
                    k, v = tok.split('=', 1)
                    out[k] = v
                else:
                    out[tok] = True
            return out

        def update_nfqws(s, key, value):
            toks = [t for t in (s or '').split() if not t.startswith(key + '=')]
            if value not in (None, '', False):
                toks.append(f'{key}={value}')
            return ' '.join(toks)

        return self._build_simple_builder(
            fields=[
                ('--dpi-desync', 'Метод десинка (disorder2/fake,split2/…)',
                 None, None, None),
                ('--dpi-desync-split-pos', 'Позиция сплита', 1, 30, 1),
                ('--dpi-desync-split-seqovl', 'Перекрытие seq (split)', 0, 64, 1),
                ('--dpi-desync-ttl', 'TTL фейка', 1, 12, 1),
                ('--dpi-desync-autottl', 'Авто-TTL (1=вкл)', 0, 2, 1),
                ('--dpi-desync-fake-tls', 'Фейк-TLS (1/2=тип)', 0, 2, 1),
                ('--dpi-desync-fooling', 'Фулинг (badsum/md5sig/badseq…)',
                 None, None, None),
            ],
            parse=parse_nfqws, update=update_nfqws)

    def _build_simple_builder(self, fields, parse, update):
        """Простой регулятор-виджет: spin/entry на поле + live-строка."""
        try:
            import ciadpi_mode_settings as _ms
        except ImportError:
            return None
        box = _ms.Gtk.Box(orientation=_ms.Gtk.Orientation.VERTICAL,
                          spacing=6)
        cur = (self._mode_settings_window.params_entry.get_text()
               if getattr(self, '_mode_settings_window', None) else '')
        parsed = parse(cur)

        def on_field_change(key, value):
            try:
                new_str = update(
                    self._mode_settings_window.params_entry.get_text(),
                    key, value)
                self._mode_settings_window.params_entry.set_text(new_str)
            except Exception:
                pass

        for f in fields:
            key, title, lo, hi, step = f
            row = _ms.Gtk.Box(orientation=_ms.Gtk.Orientation.HORIZONTAL,
                              spacing=6)
            lbl = _ms.Gtk.Label(label=title)
            lbl.set_xalign(0)
            row.pack_start(lbl, False, False, 0)
            if lo is None:
                ent = _ms.Gtk.Entry()
                ent.set_text(str(parsed.get(key, '') or ''))
                ent.set_hexpand(True)
                ent.connect('changed',
                            lambda e, k=key: on_field_change(k, e.get_text()))
                row.pack_start(ent, True, True, 0)
            else:
                sp = _ms.Gtk.SpinButton.new_with_range(lo, hi, step)
                try:
                    sp.set_value(float(parsed.get(key) or lo))
                except Exception:
                    sp.set_value(lo)
                sp.connect('value-changed',
                           lambda s, k=key: on_field_change(k, int(s.get_value())))
                row.pack_start(sp, False, False, 0)
            box.pack_start(row, False, False, 2)
        hint = _ms.Gtk.Label()
        hint.set_markup('<small>Изменения сразу пишутся в строку '
                        'параметров сверху окна.</small>')
        hint.set_xalign(0)
        box.pack_start(hint, False, False, 4)
        return box

    def show_engines_window(self, widget=None):
        """«Режимы обхода» — v2.0.6: ЧЁТКОЕ переключение.

        ⭐ user: «кнопка запускает тот что в фокусе, а не тот что
        выбрал; не выключает, а перезапускает; фокус скачет».
        Новая модель:
          * 4 режима-строки с radio-точкой: byedpi / nfqws / snimod /
            мост (dotbridge). Клик по строке = выбор (сразу пишется
            в конфиг, БЕЗ запуска — как юзер просил ранее).
          * «Запустить» / «Остановить» / «Перезапустить» действуют
            на ЯВНО выбранный в окне режим (не на _active_engine).
          * Все операции идут через ciadpi_enginectl — ОДИН бэкенд
            для меню и окна (синхронизированы по определению).
          * Тикер обновляет ТОЛЬКО текст статусов, свичи не трогает.
          * Повторный «Запустить» активного = no-op (не рестарт!).
        """
        # уже открыто? — поднимаем существующее
        existing = getattr(self, '_engines_window', None)
        if existing is not None:
            try:
                existing.present()
                return
            except Exception:
                self._engines_window = None

        try:
            import ciadpi_enginectl as ec
        except ImportError:
            import sys
            sys.path.insert(0, str(Path(__file__).resolve().parent))
            import ciadpi_enginectl as ec

        dialog = Gtk.Dialog(title='Режимы обхода DPI', flags=0)
        dialog.set_default_size(520, 430)
        self._engines_window = dialog
        content = dialog.get_content_area()
        content.set_margin_top(10); content.set_margin_bottom(10)
        content.set_margin_start(12); content.set_margin_end(12)

        modes = [
            ('byedpi', 'byedpi — SOCKS5-прокси',
             'Обходят только приложения с настроенным прокси.\n'
             'Параметры: «Настройки» в меню трея.'),
            ('nfqws', 'nfqws — десинки zapret (NFQUEUE)',
             'Перехват пакетов ВСЕХ приложений: fake/split/disorder.\n'
             'Самый мощный против SNI/IP-фильтров прова.'),
            ('snimod', 'snimod — наш SNI case-mod',
             'Поднимает РЕГИСТР SNI (www.youtube.com →\n'
             'WWW.YOUTUBE.COM). Пров режет по подстроке в нижнем\n'
             'регистре, серверу регистр безразличен (RFC 6066).'),
            ('bridge', 'DNS-мост (DoT) — без движка',
             'Локальный резолвер 127.0.0.1:53 → 1.1.1.1:853 (TLS).\n'
             'Чинит NXDOMAIN-блокировку DNS прова. Совместим с любым\n'
             'движком; отдельно — просто честный DNS.'),
        ]

        box = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=8)
        status_lbl = Gtk.Label()
        status_lbl.set_xalign(0)

        # ЯВНЫЙ выбор в окне (локальная переменная): из конфига,
        # включая bridge_mode (v2.0.6.1 — выбор моста сохраняется)
        state = {'selected': self._active_engine()}

        radio_buttons = {}

        def ui_set_status(text):
            status_lbl.set_markup(f'<small>{text}</small>')

        def on_mode_toggled(btn, name):
            if btn.get_active():
                state['selected'] = name
                ui_set_status(f'Выбран режим: <b>{name}</b> '
                              '(запуск — кнопкой ниже)')
                # ⭐ ФИКС v2.0.9 (user: «при смене режима окно параметров
                # от старого режима остаётся — закрыть, чтобы открыли
                # уже правильное»): гасим окно «Настройки режима», оно
                # строится под режим при открытии.
                try:
                    ms = getattr(self, '_mode_settings_window', None)
                    if ms is not None and ms.dialog is not None:
                        ms.dialog.destroy()
                except Exception:
                    pass
                # выбор сразу в конфиг (без автозапуска — прежнее правило)
                if name == 'bridge':
                    self.current_params['bridge_mode'] = True
                else:
                    self.current_params['bridge_mode'] = False
                    if name != self._active_engine():
                        self.current_params['engine'] = name
                self.save_config()

        for name, title, desc in modes:
            row = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL,
                          spacing=8)
            rb = Gtk.RadioButton.new_with_label_from_widget(
                None if name == 'byedpi' else radio_buttons.get('byedpi'),
                '')
            rb.set_active(state['selected'] == name)
            rb.connect('toggled', on_mode_toggled, name)
            lbl_box = Gtk.Box(orientation=Gtk.Orientation.VERTICAL,
                              spacing=1)
            lbl = Gtk.Label()
            lbl.set_markup(f'<b>{GLib.markup_escape_text(title)}</b>')
            lbl.set_xalign(0)
            hint = Gtk.Label()
            hint.set_markup(
                f'<small>{GLib.markup_escape_text(desc)}</small>')
            hint.set_xalign(0)
            hint.set_line_wrap(True)
            lbl_box.pack_start(lbl, False, False, 0)
            lbl_box.pack_start(hint, False, False, 0)
            # статус режима справа (заполнит тикер)
            st_lbl = Gtk.Label()
            st_lbl.set_markup('<small>…</small>')
            st_lbl.set_valign(Gtk.Align.CENTER)
            row.pack_start(rb, False, False, 0)
            row.pack_start(lbl_box, True, True, 0)
            row.pack_start(st_lbl, False, False, 4)
            # ⭐ ФИКС («выбор не сохраняется»): клика была доступна
            # только маленькая radio-точка; вся остальная строка —
            # мёртвая. EventBox делает КЛИКАБЕЛЬНОЙ ВСЮ строку:
            # и заголовок, и описание.
            ev_row = Gtk.EventBox()
            ev_row.add(row)
            ev_row.connect('button-press-event',
                           lambda w, e, _rb=rb: _rb.set_active(True)
                           or False)
            ev_row.set_tooltip_text('Клик — выбрать этот режим')
            box.pack_start(ev_row, False, False, 2)
            radio_buttons[name] = rb
            # тест-хуки: прямые ссылки на radio и статус-лейблы
            # (GUI-тестам не нужно обходить дерево виджетов)
            if getattr(self, '_mode_radios', None) is None:
                self._mode_radios = {}
            self._mode_radios[name] = rb
            # держим ссылки на статус-лейблы для тикера
            if not hasattr(self, '_mode_status_labels') or \
                    self._mode_status_labels is None:
                self._mode_status_labels = {}
            self._mode_status_labels[name] = st_lbl

        # --- кнопки: действуют на ВЫБРАННЫЙ режим ---
        btn_box = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL,
                          spacing=8)
        btn_start = Gtk.Button(label='▶ Запустить')
        btn_stop = Gtk.Button(label='⏹ Остановить')
        btn_restart = Gtk.Button(label='↻ Перезапустить')
        btn_close = Gtk.Button(label='Закрыть')

        def _busy(on):
            for b in (btn_start, btn_stop, btn_restart):
                b.set_sensitive(not on)

        def _run_op(fn, verb):
            """Запуск операции бэкенда в фоне; GUI не блокируется.

            ⭐ ФИКС: бэкенд возвращает (ok, msg) — раньше результат
            выбрасывался и окно говорило «готово» даже при провале
            («режимы не запускаются совсем»).
            """
            target = state['selected']
            _busy(True)
            ui_set_status(f'⏳ {verb} <b>{target}</b>…')

            def worker():
                try:
                    ok, msg = fn()
                except Exception as e:
                    ok, msg = False, str(e)
                def done():
                    _busy(False)
                    ui_set_status(('✅ ' if ok else '❌ ') +
                                  f'{verb} {target}: ' + (msg or 'готово'))
                    GLib.idle_add(self.update_status)
                    GLib.idle_add(self.rebuild_menu)
                    return False
                GLib.idle_add(done)
            threading.Thread(target=worker, daemon=True).start()

        def on_start(btn):
            target = state['selected']
            if target == 'bridge':
                _run_op(ec.start_bridge, 'запуск')
            else:
                _run_op(lambda: ec.start_engine(target), 'запуск')

        def on_stop(btn):
            target = state['selected']
            if target == 'bridge':
                _run_op(ec.stop_bridge, 'стоп')
            else:
                _run_op(lambda: ec.stop_engine(target), 'стоп')

        def on_restart(btn):
            target = state['selected']
            if target == 'bridge':
                _run_op(lambda: (ec.stop_bridge(), ec.start_bridge())[1],
                        'перезапуск')
            else:
                _run_op(lambda: ec.restart_engine(target), 'перезапуск')

        btn_start.connect('clicked', on_start)
        btn_stop.connect('clicked', on_stop)
        btn_restart.connect('clicked', on_restart)
        btn_close.connect('clicked', lambda b: dialog.response(
            Gtk.ResponseType.CLOSE))
        # тест-хуки: кнопки операции
        self._mode_btns = {'start': btn_start, 'stop': btn_stop,
                           'restart': btn_restart}
        btn_box.pack_start(btn_start, False, False, 0)
        btn_box.pack_start(btn_stop, False, False, 0)
        btn_box.pack_start(btn_restart, False, False, 0)
        btn_box.pack_end(btn_close, False, False, 0)

        box.pack_start(Gtk.Separator(), False, False, 4)
        box.pack_start(status_lbl, False, False, 0)
        box.pack_start(btn_box, False, False, 0)

        content.pack_start(box, True, True, 0)
        content.show_all()

        # тикер: только статусы, ничего не переключает
        def refresh_status():
            labels = getattr(self, '_mode_status_labels', None) or {}
            for name, st_lbl in list(labels.items()):
                def query(n=name, lbl=st_lbl):
                    try:
                        active = ec.is_active(n)
                        if n == 'bridge':
                            pass
                        txt = ('<span foreground="#2e7d32">● активен</span>'
                               if active else
                               '<span foreground="#888">○ остановлен</span>')
                    except Exception:
                        txt = '<small>?</small>'
                    GLib.idle_add(lbl.set_markup,
                                  f'<small>{txt}</small>')
                threading.Thread(target=query, daemon=True).start()
            return True
        refresh_status()
        timer = GLib.timeout_add_seconds(3, refresh_status)

        def on_dialog_destroy(d):
            self._engines_window = None
            self._mode_status_labels = None
            self._mode_radios = None
            self._mode_btns = None
            return False
        dialog.connect('destroy', on_dialog_destroy)

        # ⭐ v2.0.8: НЕМОДАЛЬНОЕ окно. dialog.run() ставил GTK-grab
        # на всё приложение — пока окно режимов открыто, окно
        # «Настройки режима» не реагировало (user: «не можем менять
        # параметры, пока не закроем окно выбора режима»). Теперь
        # show() без захвата — оба окна живут независимо.
        dialog.show_all()
        dialog.connect('delete-event',
                       lambda d, e: (d.destroy(), True)[1])

    def show_profiles_dialog(self, widget=None):
        """⭐ v2.0.6: Профили — сохранение/применение/удаление наборов.

        Профиль = выбранный режим + параметры всех движков + мост +
        настройки прокси. Сценарий: дома включил нужный режим →
        «Сохранить как…» → в кафе «Применить» — машина поднимет
        именно то, что было сохранено.
        """
        try:
            import ciadpi_profiles
        except ImportError:
            import sys
            sys.path.insert(0, str(Path(__file__).resolve().parent))
            import ciadpi_profiles
        pm = ciadpi_profiles.ProfileManager()

        dialog = Gtk.Dialog(title='Профили настроек', flags=0)
        dialog.set_default_size(480, 420)
        content = dialog.get_content_area()
        content.set_margin_top(10); content.set_margin_bottom(10)
        content.set_margin_start(12); content.set_margin_end(12)

        box = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=8)
        status_lbl = Gtk.Label()
        status_lbl.set_xalign(0)

        # список профилей
        store = Gtk.ListStore(str, str)
        list_tree = Gtk.TreeView(model=store)
        list_tree.set_headers_visible(False)
        renderer = Gtk.CellRendererText()
        col = Gtk.TreeViewColumn('Профиль', renderer, text=0)
        list_tree.append_column(col)
        renderer2 = Gtk.CellRendererText()
        renderer2.set_property('foreground', 'gray')
        col2 = Gtk.TreeViewColumn('Инфо', renderer2, text=1)
        list_tree.append_column(col2)
        scroll = Gtk.ScrolledWindow()
        scroll.set_vexpand(True)
        scroll.add(list_tree)
        selection = list_tree.get_selection()

        def refresh_list():
            store.clear()
            active = pm.active_profile()
            for name, meta in pm.list_profiles():
                info = (f"[{meta.get('engine', '?')} · мост:"
                        f"{meta.get('bridge', '?')}]"
                        f"{' ← активный' if name == active else ''}")
                store.append([name, info])
        refresh_list()

        def chosen_name():
            model, tree_iter = selection.get_selected()
            return model[tree_iter][0] if tree_iter else None

        # имя нового профиля
        name_row = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL,
                           spacing=8)
        name_entry = Gtk.Entry()
        name_entry.set_placeholder_text('Имя профиля (напр. «Дом»)')
        btn_save = Gtk.Button(label='💾 Сохранить текущее как…')
        name_row.pack_start(name_entry, True, True, 0)
        name_row.pack_start(btn_save, False, False, 0)

        btn_box = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL,
                          spacing=8)
        btn_apply = Gtk.Button(label='▶ Применить')
        btn_delete = Gtk.Button(label='🗑 Удалить')
        btn_close = Gtk.Button(label='Закрыть')

        def on_save(btn):
            name = name_entry.get_text()
            ok, msg = pm.capture_current(name)
            status_lbl.set_markup(
                f'<small>{"✅" if ok else "❌"} {GLib.markup_escape_text(msg)}</small>')
            if ok:
                name_entry.set_text('')
                refresh_list()

        def on_apply(btn):
            name = chosen_name()
            if not name:
                status_lbl.set_markup('<small>❌ выберите профиль в списке</small>')
                return
            status_lbl.set_markup(
                f'<small>⏳ Применяю «{GLib.markup_escape_text(name)}»…</small>')

            def worker():
                ok, msg = pm.apply_profile(name)
                def done():
                    status_lbl.set_markup(
                        f'<small>{"✅" if ok else "❌"} '
                        f'{GLib.markup_escape_text(msg)}</small>')
                    refresh_list()
                    self.update_status()
                    self.rebuild_menu()
                    return False
                GLib.idle_add(done)
            threading.Thread(target=worker, daemon=True).start()

        def on_delete(btn):
            name = chosen_name()
            if not name:
                status_lbl.set_markup('<small>❌ выберите профиль в списке</small>')
                return
            ok, msg = pm.delete_profile(name)
            status_lbl.set_markup(
                f'<small>{"✅" if ok else "❌"} {GLib.markup_escape_text(msg)}</small>')
            refresh_list()

        btn_save.connect('clicked', on_save)
        btn_apply.connect('clicked', on_apply)
        btn_delete.connect('clicked', on_delete)
        btn_close.connect('clicked', lambda b: dialog.response(
            Gtk.ResponseType.CLOSE))

        btn_box.pack_start(btn_apply, False, False, 0)
        btn_box.pack_start(btn_delete, False, False, 0)
        btn_box.pack_end(btn_close, False, False, 0)

        hint = Gtk.Label()
        hint.set_markup('<small>Профиль хранит: выбранный режим, параметры\n'
                       'byedpi/nfqws/хосты snimod, состояние DNS-моста и\n'
                       'настройки прокси. «Сохранить» снимает снимок ТЕКУЩИХ\n'
                       'настроек; «Применить» поднимает их целиком.</small>')
        hint.set_xalign(0)

        box.pack_start(hint, False, False, 0)
        box.pack_start(scroll, True, True, 0)
        box.pack_start(name_row, False, False, 0)
        box.pack_start(status_lbl, False, False, 0)
        box.pack_start(btn_box, False, False, 0)
        content.pack_start(box, True, True, 0)
        content.show_all()
        # ⭐ v2.0.8: немодально — окно профилей не блокирует другие
        dialog.show_all()
        dialog.connect('delete-event',
                       lambda d, e: (d.destroy(), True)[1])
        # ⭐ v2.0.10 (user: «профили не закрываются по кнопке Закрыть»):
        # немодальный show() не запускает run() → response никто не
        # слушал. Слушаем response вручную → destroy.
        dialog.connect('response',
                       lambda d, r: d.destroy())

    def show_snimod_settings(self, widget=None):
        """Диалог настроек snimod: список хостов для uppercase SNI."""
        if not self.snimod:
            self.show_notification(t('notif.error'),
                                    'snimod-модуль не доступен')
            return
        cfg = self.snimod.load_config()
        hosts = cfg.get('hosts') or self.snimod.default_hosts

        dialog = Gtk.Dialog(title='snimod: хосты SNI case-mod', flags=0)
        dialog.add_buttons(t('btn.cancel'), Gtk.ResponseType.CANCEL,
                           t('btn.ok'), Gtk.ResponseType.OK)
        dialog.set_default_size(420, 300)
        content = dialog.get_content_area()

        box = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=8)
        box.set_margin_top(10); box.set_margin_bottom(10)
        box.set_margin_start(10); box.set_margin_end(10)

        lbl = Gtk.Label()
        lbl.set_markup('<small>По одному хосту в строке. Регистр SNI этих\n'
                       'хостов поднимается на лету (www.youtube.com →\n'
                       'WWW.YOUTUBE.COM). Серверу регистр безразличен,\n'
                       'DPI-подпись прова ломается.</small>')
        lbl.set_xalign(0)
        buf = Gtk.TextBuffer()
        buf.set_text('\n'.join(hosts))
        tv = Gtk.TextView(buffer=buf)
        tv.set_monospace(True)
        scroll = Gtk.ScrolledWindow()
        scroll.set_vexpand(True)
        scroll.add(tv)

        box.pack_start(lbl, False, False, 0)
        box.pack_start(scroll, True, True, 0)
        content.pack_start(box, True, True, 0)
        content.show_all()

        while True:
            response = dialog.run()
            if response != Gtk.ResponseType.OK:
                break
            text = buf.get_text(buf.get_start_iter(),
                                buf.get_end_iter(), False)
            hosts = [h.strip() for h in text.splitlines()
                     if h.strip() and len(h.strip()) <= 253]
            if not hosts:
                continue
            cfg['hosts'] = hosts
            self.snimod.save_config(cfg)
            self.snimod.write_hosts_file(hosts)
            # если сервис активен — переписываем юнит и рестартуем
            if self.snimod.is_service_active():
                threading.Thread(target=self.snimod.write_unit,
                                 daemon=True).start()
                threading.Thread(target=self.snimod.stop, daemon=True).start()
                import time as _t
                threading.Thread(
                    target=lambda: (_t.sleep(1.5),
                                    self.snimod.start()),
                    daemon=True).start()
            break
        dialog.destroy()

    # ---------------- Валидация значений ciadpi ----------------
    # Позиция desync: -?[смещение][:повторы][:шаг] с флагами +s/+h/+n (+e/m/r/s вторым)
    OFFSET_VAL = r'-?\d+(:\d+)?(:\d+)?(\+[shn][emrs]?)?'
    # -L: буквы s,o,n через запятую (0..3 в старых версиях больше не принимаются)
    VAL_PATTERNS = {
        '-L': r'[son](,[son])*',
        # -A: значим первый символ (t,r,s,c,n,p=)
        '-A': r'[trscnp].*',
        '-K': r'[thui](,[thui])*',
        '-M': r'[hdr](,[hdr])*',
        '-Q': r'([ro](,[ro])*|msize=\d+)',
        '-V': r'\d+(-\d+)?',
        '-R': r'\d+(-\d+)?',
        '-T': r'\d+(\.\d+)?(:\d+(\.\d+)?){0,3}',
        '-s': OFFSET_VAL, '-d': OFFSET_VAL, '-o': OFFSET_VAL,
        '-q': OFFSET_VAL, '-f': OFFSET_VAL, '-r': OFFSET_VAL,
        '-O': OFFSET_VAL,
        '-g': r'\d+', '-t': r'\d+', '-m': r'\d+',
        '-p': r'\d+', '-c': r'\d+', '-b': r'\d+',
        '-u': r'\d+', '-a': r'\d+', '-x': r'\d+',
        '-i': r'[a-zA-Z0-9.:]+', '-I': r'[a-zA-Z0-9.:]+',
        '-V': r'\d+(-\d+)?',
    }
    # Флаги, значение которых может начинаться с '-' (позиции: -f -1 из README byedpi)
    OFFSET_FLAGS = {'-s', '-d', '-o', '-q', '-f', '-r', '-O'}

    def _valid_flag_value(self, flag: str, val: str) -> bool:
        """Проверка значения по правилам текущего бинарника ciadpi."""
        pat = self.VAL_PATTERNS.get(flag)
        if pat is None:
            return True  # свободное значение (-n, -l, -H, -j, -e, -w, -y...)
        return re.fullmatch(pat, val) is not None

    def validate_params(self, params: str) -> Tuple[bool, str]:
        """Проверка параметров ciadpi с детальными сообщениями об ошибках.

        Синхронизирована с парсером текущего byedpi (main.c):
        - суффикс позиций: после + ОБЯЗАТЕЛЕН флаг s/h/n, затем опц. e/m/r/s;
        - -L принимает только буквы s, o, n (запятые допустимы);
        - -A значим первым символом (t, r, s, c, n, p=).
        """
        if not params.strip():
            return True, ""

        bool_flags = {'-D', '-E', '-N', '-U', '-F', '-S', '-Y'}

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

            # легаси-мусор из старых версий (позиционные слова, парсер игнорирует)
            if tok == 'o--tlsrec' or tok.startswith('o--'):
                i += 1
                continue
            # голое значение-позиция (1+s, 2+s после легаси-слов)
            if re.match(r'^-?\d+(:\d+)?(:\d+)?(\+[shn][emrs]?)?$', tok):
                i += 1
                continue
            # значения флагов со свободными строками (-H, -j, -l, -n, -e, -A ...)
            if i > 0 and tokens[i - 1] in ('-H', '-j', '-l', '-n', '-e', '-A',
                                           '--hosts', '--ipset', '--fake-data',
                                           '--fake-sni', '--oob-data', '--auto'):
                i += 1
                continue

            if tok in bool_flags:
                i += 1
                continue

            # длинная опция со значением через = (--auto=torst, --tlsrec=1+s)
            if tok.startswith('--') and '=' in tok:
                opt_name = tok.split('=', 1)[0]
                if opt_name in known_long:
                    i += 1
                    continue
                unknown.append(tok)
                i += 1
                continue

            # прикреплённое значение: -T3, -At, -o25+s, -Ls
            m = re.match(r'^(-[A-Za-z])(.+)$', tok)
            if m and m.group(1) not in bool_flags:
                flag, val = m.group(1), m.group(2)
                if flag == '-o' and re.match(r'^\d+$', val):
                    pass  # -oN (числовой метод) = позиция, проверим ниже
                if not self._valid_flag_value(flag, val):
                    unknown.append(tok)
                i += 1
                continue

            # отдельный флаг + значение следующим токеном
            if tok in self.VAL_PATTERNS or tok in ('-w', '-y', '-H', '-j', '-l',
                                                  '-n', '-e', '-C', '-P', '-W'):
                nxt = tokens[i + 1] if i + 1 < len(tokens) else None
                if nxt is None or (nxt.startswith('-') and tok not in self.OFFSET_FLAGS):
                    unknown.append(f"{tok} (нет значения)")
                    i += 1
                    continue
                if not self._valid_flag_value(tok, nxt):
                    unknown.append(f"{tok} {nxt}")
                i += 2
                continue

            if tok in known_long:
                if i + 1 < len(tokens) and not tokens[i + 1].startswith('-'):
                    i += 2
                else:
                    i += 1
                continue

            if tok.startswith('-'):
                unknown.append(tok)
                i += 1
                continue

            # прочее голое значение — продолжение значения предыдущего флага
            i += 1

        if unknown:
            error_msg = f"Недопустимые параметры: {', '.join(unknown)}\n"
            error_msg += ("Правила: после + в позициях обязателен флаг s/h/n "
                          "(+m/+e только вторым); -L принимает s/o/n; "
                          "проверьте документацию ciadpi")
            return False, error_msg

        return True, ""

    def show_settings(self, widget=None):
        ###
        print("DEBUG: show_settings called")
        try:        
###            
            """Диалог настроек параметров"""
            dialog = Gtk.Dialog(title=t('settings.dialog_title'), flags=0)
            dialog.add_buttons(t('btn.cancel'), Gtk.ResponseType.CANCEL,
                            t('btn.ok'), Gtk.ResponseType.OK)
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
            # ⭐ v2.0.6: параметры — из КЭША, не из живого systemctl
            # (subprocess в главном GTK-потоке морозил окно настроек
            # на 2-6с во время job-lock'а — «окно не нажимается»).
            # Кэш обновляет фоновый тикер update_status.
            current_params = getattr(self, '_cached_params_text',
                                     None) or self.default_params
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
            
            # Список примеров (проверены на текущем бинарнике byedpi)
            examples = [
                "-T3 -A torst -o1 -o25+s -r 1+s",
                "-T2 -A torst -o2 -o15+s -r 2+s",
                "-T1 -A torst -o1 -o5+s",
                "-T3 -A torst -o3 -o20+s -r 2+s",
                "-T5 -A torst -o4 -o10+s"
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
        
        dialog = Gtk.Dialog(title=t('auto.title'), flags=0)
        dialog.add_buttons(t('btn.cancel'), Gtk.ResponseType.CANCEL,
                         t('auto.launch'), Gtk.ResponseType.OK)
        dialog.set_default_size(400, 200)

        content_area = dialog.get_content_area()
        
        box = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=10)
        box.set_margin_top(10)
        box.set_margin_bottom(10)
        box.set_margin_start(10)
        box.set_margin_end(10)
        
        label = Gtk.Label(label=t('auto.n_tests'))
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
        
        dialog = Gtk.Dialog(title=t('hist.title'), flags=0)
        dialog.add_buttons(t('btn.close'), Gtk.ResponseType.CLOSE)
        dialog.set_default_size(600, 400)
        
        content_area = dialog.get_content_area()
        scroll = Gtk.ScrolledWindow()
        
        # Простой текстовый вывод
        text_view = Gtk.TextView()
        text_view.set_editable(False)
        text_view.set_wrap_mode(Gtk.WrapMode.WORD)
        
        buffer = text_view.get_buffer()
        text = t('hist.header') + "\n\n"
        
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

        dialog = Gtk.Dialog(title=t('search.title'), flags=0)
        # ⭐ Кнопка Close в action area НЕ нужна: GTK рисует свою
        # «Закрыть» в заголовке окна — раньше их было ДВЕ.
        dialog.set_default_size(760, 560)
        self.strategy_window = dialog

        content_area = dialog.get_content_area()
        main_box = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=8)
        main_box.set_margin_top(10)
        main_box.set_margin_bottom(10)
        main_box.set_margin_start(10)
        main_box.set_margin_end(10)

        # --- Движок поиска: byedpi (тестовый порт) ↔ nfqws (реальный сервис) ---
        row_engine = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=8)
        lbl_engine = Gtk.Label(label=t('search.engine_label'))
        lbl_engine.set_xalign(0)
        combo_engine = Gtk.ComboBoxText()
        combo_engine.append_text(t('search.engine_byedpi'))
        combo_engine.append_text(t('search.engine_nfqws'))
        # активный движок трея — по умолчанию в диалоге
        engine_is_nfqws_now = (NFQWS_AVAILABLE and self.nfqws
                               and self._active_engine() == 'nfqws')
        combo_engine.set_active(1 if engine_is_nfqws_now else 0)
        combo_engine.set_tooltip_text(t('search.engine_hint'))
        row_engine.pack_start(lbl_engine, False, False, 0)
        row_engine.pack_start(combo_engine, False, False, 0)

        # --- Настройки проверки ---
        settings_frame = Gtk.Frame(label=t('search.settings'))
        settings_box = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=6)
        settings_box.set_margin_top(8)
        settings_box.set_margin_bottom(8)
        settings_box.set_margin_start(8)
        settings_box.set_margin_end(8)

        row1 = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=8)
        lbl_tests = Gtk.Label(label=t('search.max_combos'))
        lbl_tests.set_xalign(0)
        spin_tests = Gtk.SpinButton.new_with_range(1, 200, 1)
        spin_tests.set_value(20)

        lbl_port = Gtk.Label(label=t('search.test_port'))
        spin_port = Gtk.SpinButton.new_with_range(1024, 65535, 1)
        spin_port.set_value(searcher.test_port)
        row1.pack_start(lbl_tests, False, False, 0)
        row1.pack_start(spin_tests, False, False, 0)
        row1.pack_start(Gtk.Separator(orientation=Gtk.Orientation.VERTICAL), False, False, 4)
        row1.pack_start(lbl_port, False, False, 0)
        row1.pack_start(spin_port, False, False, 0)

        # ⭐ Режим «до нахождения»: лимит попыток выключается, перебор
        # идёт пока не найдётся рабочая стратегия (или пользователь не
        # нажмёт «Остановить»). Мин. попыток — нижний предел: успех
        # раньше этого числа поиск не завершает.
        chk_until_found = Gtk.CheckButton(label=t('search.until_found'))
        chk_until_found.set_tooltip_text(t('search.until_found_hint'))
        lbl_min_tests = Gtk.Label(label=t('search.min_tests'))
        spin_min_tests = Gtk.SpinButton.new_with_range(1, 200, 1)
        spin_min_tests.set_value(10)
        row_mode = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=8)
        row_mode.pack_start(chk_until_found, False, False, 0)
        row_mode.pack_start(Gtk.Separator(orientation=Gtk.Orientation.VERTICAL), False, False, 4)
        row_mode.pack_start(lbl_min_tests, False, False, 0)
        row_mode.pack_start(spin_min_tests, False, False, 0)

        def on_until_found_toggled(btn):
            limited = not btn.get_active()
            spin_tests.set_sensitive(limited)
            lbl_tests.set_sensitive(limited)
            spin_min_tests.set_sensitive(not limited)
            lbl_min_tests.set_sensitive(not limited)
        chk_until_found.connect("toggled", on_until_found_toggled)
        on_until_found_toggled(chk_until_found)

        row2 = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=8)
        lbl_urls = Gtk.Label(label=t('search.urls_label'))
        lbl_urls.set_xalign(0)
        urls_entry = Gtk.Entry()
        urls_entry.set_text(" ".join(searcher.default_test_urls))
        urls_entry.set_tooltip_text(t('search.url_hint'))
        urls_entry.set_hexpand(True)
        row2.pack_start(lbl_urls, False, False, 0)
        row2.pack_start(urls_entry, True, True, 0)

        settings_box.pack_start(row1, False, False, 0)
        settings_box.pack_start(row_mode, False, False, 0)
        settings_box.pack_start(row2, False, False, 0)
        settings_box.pack_start(row_engine, False, False, 0)
        settings_frame.add(settings_box)

        # --- Прогресс ---
        progress_label = Gtk.Label(label=t('search.ready'))
        progress_label.set_xalign(0)
        progressbar = Gtk.ProgressBar()
        progressbar.set_show_text(True)
        progressbar.set_fraction(0.0)

        # --- Кнопки управления ---
        btn_box = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=8)
        btn_start = Gtk.Button(label=t('search.start'))
        btn_stop = Gtk.Button(label=t('search.stop'))
        btn_stop.set_sensitive(False)
        btn_apply = Gtk.Button(label=t('search.apply_best'))
        btn_apply.set_sensitive(False)
        btn_box.pack_start(btn_start, False, False, 0)
        btn_box.pack_start(btn_stop, False, False, 0)
        btn_box.pack_end(btn_apply, False, False, 0)

        # --- Журнал хода поиска ---
        log_frame = Gtk.Frame(label=t('search.log_frame'))
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
            # ⭐ v2.0.5: кап на размер буфера — за ночь безлимитного
            # поиска лог в TextView разрастался на миллионы строк и
            # каждое append становилось всё медленнее (окно «висло»).
            # Держим последние ~400 строк, старые срезаем.
            try:
                n_lines = log_buffer.get_line_count()
                if n_lines > 500:
                    start_it = log_buffer.get_iter_at_line(
                        max(0, n_lines - 400))
                    end_it = log_buffer.get_end_iter()
                    log_buffer.delete(start_it, end_it)
            except Exception:
                pass
            log_buffer.insert(log_buffer.get_end_iter(), message + "\n")
            # автоскролл вниз
            mark = log_buffer.create_mark(None, log_buffer.get_end_iter(), False)
            text_view.scroll_to_mark(mark, 0.0, True, 0.0, 1.0)

        def ui_set_progress(fraction, text, pulse=False):
            if pulse:
                progressbar.pulse()
            else:
                progressbar.set_fraction(min(1.0, fraction))
            progressbar.set_text(text)

        def _log_test_result(r, idx):
            """Общая строка лога для одного теста (обе ветки update_test)."""
            if r['success']:
                ui_log(f"[{idx}] ✅ {r['urls_ok']}/{r['urls_total']} URL, "
                       f"{t('search.avg_speed')} {r['speed']:.2f}s | {r['params']}")
            elif r['urls_ok'] > 0:
                # частичный доступ: ясно даём понять, что это НЕ успех
                ui_log(f"[{idx}] ⛔ {t('search.partial')}: "
                       f"{r['urls_ok']}/{r['urls_total']} URL | {r['params']}")
            else:
                err = (r.get('error') or '')[:120]
                ui_log(f"[{idx}] ❌ {err} | {r['params']}")
            # ⭐ v1.9.2 (user: «не видно, к КАКИМ адресам прошло, а к каким
            # нет — важен именно список, а не просто 2/3»): расшифровка
            # по каждому URL печатается при ЛЮБОМ исходе — успех, частичном
            # доступе и провале. Раньше детали показывались только при
            # полном успехе, из-за чего «2/3» было бесполезно.
            for url, ok, code, sec in (r.get('details') or []):
                mark = "✅" if ok else "❌"
                ui_log(f"      {mark} {url} → HTTP {code} ({sec}с)")

        def on_progress(stage, data):
            """Колбэк из фонового потока — планируем обновление GUI."""
            if stage == 'start':
                if data.get('unlimited'):
                    start_line = (f"▶️ {t('search.start_log')}: "
                                  f"{t('search.unlimited_mode')} "
                                  f"{t('search.via')} 127.0.0.1:{data['port']}")
                else:
                    start_line = (f"▶️ {t('search.start_log')}: {data['total']} "
                                  f"{t('search.combos')} {data['port']}, "
                                  f"{t('search.via')} 127.0.0.1:{data['port']}")
                GLib.idle_add(ui_log, start_line)
            elif stage == 'test':
                r = data['result']
                idx = data['index'] + 1

                def update_test(r=r, idx=idx):
                    if state.get('unlimited'):
                        # без лимита: пульсация, доля не имеет смысла
                        ui_set_progress(0.0, f"{t('search.test')} {idx}: "
                                     f"{'✅ ' + t('search.ok_urls') if r['success'] else t('search.fail')} "
                                     f"({r['urls_ok']}/{r['urls_total']} URL)",
                                     pulse=True)
                        _log_test_result(r, idx)
                        return False
                    total_now = max(idx, 1)
                    frac = idx / float(state.get('planned_total', total_now) or total_now)
                    if r['success']:
                        ui_set_progress(frac, f"{t('search.test')} {idx}: {t('search.ok_urls')} ({r['urls_ok']}/{r['urls_total']} URL)")
                        # ⭐ v1.9.2: расшифровка по URL теперь печатается
                        # в _log_test_result при любом исходе (общая для
                        # обеих веток update_test) — здесь дубль убран.
                    else:
                        ui_set_progress(frac, f"{t('search.test')} {idx}: {t('search.fail')}")
                    _log_test_result(r, idx)
                    return False
                GLib.idle_add(update_test)

            elif stage == 'done':
                best = data.get('best')

                def update_done(best=best):
                    if best:
                        state['best_params'] = best
                        btn_apply.set_sensitive(True)
                        ui_log(f"\n{t('search.best_found')}: {best}")
                        res = data.get('result') or {}
                        if res:
                            ui_log(f"    {t('search.speed')}: {res['speed']:.2f}s, "
                                   f"{t('search.urls_avail')}: {res['urls_ok']}/{res['urls_total']}")
                    else:
                        ui_log("\n😕 " + t('search.none_found'))
                    ui_set_progress(1.0, t('search.finished'))
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
                ui_log(t('search.need_urls'))
                return
            # ⭐ поисковик — по выбранному движку; nfqws-поиск работает
            # через реальный сервис, порт ему не нужен (прячем строку)
            engine_idx = combo_engine.get_active()
            use_nfqws = engine_idx == 1
            if use_nfqws:
                if not (NFQWS_AVAILABLE and self.nfqws):
                    ui_log(t('engine.nfqws_unavailable'))
                    return
                from ciadpi_strategy_search import NfqwsStrategySearcher
                active_searcher = NfqwsStrategySearcher()
                row1.set_sensitive(False)   # порт не участвует
            else:
                active_searcher = StrategySearcher()
                row1.set_sensitive(True)
                active_searcher.test_port = int(spin_port.get_value())
            state['searcher'] = active_searcher
            state['engine'] = 'nfqws' if use_nfqws else 'byedpi'
            unlimited = chk_until_found.get_active()
            max_tests = 0 if unlimited else int(spin_tests.get_value())
            min_tests = int(spin_min_tests.get_value()) if unlimited else None
            state.update({'running': True, 'best_params': None, 'unlimited': unlimited,
                          'planned_total': max_tests})
            btn_start.set_sensitive(False)
            btn_stop.set_sensitive(True)
            btn_apply.set_sensitive(False)
            log_buffer.set_text("")
            ui_set_progress(0.0, t('search.unlimited_mode') if unlimited else "Запуск...")
            threading.Thread(
                target=active_searcher.find_optimal_params,
                args=(max_tests, urls, on_progress),
                kwargs={'min_tests': min_tests},
                daemon=True
            ).start()

        def on_stop(btn):
            s = state.get('searcher') or searcher
            s.stop_search()
            ui_log(t('search.stop_req'))

        def on_apply(btn):
            params = state.get('best_params')
            if not params:
                return
            dialog.set_sensitive(False)
            self.show_notification(t('search.apply_run'), t('search.apply_run_2'))

            def apply_thread():
                if state.get('engine') == 'nfqws':
                    # ⭐ nfqws: параметры идут в nfqws.json + рестарт
                    # сервиса (формат zapret, НЕ byedpi-юнит)
                    if not self.nfqws:
                        ui_log(t('engine.nfqws_unavailable'))
                        return
                    cfg = self.nfqws.load_config()
                    cfg['params'] = params
                    self.nfqws.save_config(cfg)
                    ok, err = self.nfqws.start(params)
                    success = ok
                    err_msg = err
                else:
                    success = self.update_service_params(params)
                    err_msg = ''
                def finish():
                    dialog.set_sensitive(True)
                    if success:
                        ui_log(f"✅ {t('search.applied')}: {params}")
                        self.show_notification(t('notif.success'), t('notif.best_applied'), category='params')
                    else:
                        msg = f"❌ {t('search.apply_fail')}"
                        if err_msg:
                            msg += f": {err_msg}"
                        ui_log(msg)
                    return False
                GLib.idle_add(finish)

            threading.Thread(target=apply_thread, daemon=True).start()

        btn_start.connect("clicked", on_start)
        btn_stop.connect("clicked", on_stop)
        btn_apply.connect("clicked", on_apply)

        def on_dialog_response(d, response):
            # ⭐ Раньше окно не уничтожалось по «Закрыть» — response лишь
            # останавливал поиск, диалог оставался висеть (модально!).
            try:
                if state['running']:
                    s = state.get('searcher') or searcher
                    s.stop_search()
            finally:
                d.destroy()
                self.strategy_window = None

        dialog.connect("response", on_dialog_response)

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
        """Совместимость-обёртка: полный конструктор во вкладке
        «Настройки режима». Прямой диалог больше не используется —
        открываем окно настроек режима на вкладке Конструктор."""
        self.show_mode_settings()

    def _build_full_byedpi_builder(self):
        """⭐ v2.0.10: ПОЛНЫЙ конструктор byedpi как виджет-вкладка.

        Вычленен из старого диалогового show_param_builder: все
        регуляторы со справками «?», живая синхронизация со строкой
        параметров окна «Настройки режима» (params_entry).
        """
        if not PARAMS_SPEC_AVAILABLE:
            return None
        current_str = None
        ms = getattr(self, '_mode_settings_window', None)
        if ms is not None and getattr(ms, 'params_entry', None) \
                is not None:
            current_str = ms.params_entry.get_text()
        if not current_str:
            current_str = getattr(self, '_cached_params_text', None) \
                or self.default_params
        parsed = parse_params(current_str)
        main_vbox = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=8)
        main_vbox.set_margin_top(10); main_vbox.set_margin_bottom(10)
        main_vbox.set_margin_start(10); main_vbox.set_margin_end(10)

        current_str = getattr(self, '_cached_params_text', None) \
            or self.default_params
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

        def apply_field_change(spec, value):
            """Хирургическая правка одного флага в строке."""
            if updating['lock']:
                return
            updating['lock'] = True
            try:
                cur = str_entry.get_text()
                new = update_param_in_string(cur, spec['opt'], value,
                                            group=spec['group'])
                str_entry.set_text(new)
            finally:
                updating['lock'] = False

        def on_widget_change(spec, w):
            """Собрать значение виджета и применить правку."""
            kind = spec['kind']
            if kind == 'spin':
                v = int(w.get_value())
                value = None if v == 0 and spec.get('default') is None else v
            elif kind == 'combo':
                value = w.get_active_id() or ''
            elif kind == 'check':
                value = True if w.get_active() else None
            else:  # entry
                value = w.get_text().strip() or None
            apply_field_change(spec, value)

        def refresh_widgets_from_string(*_):
            if updating['lock']:
                return
            parsed_now = parse_params(str_entry.get_text())
            updating['lock'] = True
            try:
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
            finally:
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

            key = spec['key']
            detailed = t(key + '_q')  # подробная подсказка «?»
            short = t(key + '_h')     # краткая (на label и виджет)

            title = Gtk.Label(label=t(key))
            title.set_xalign(0)
            title.set_size_request(230, -1)
            title.set_tooltip_text(short)
            row_box.pack_start(title, False, False, 0)

            kind = spec['kind']
            opt = spec['opt']
            val = get_value(parsed, opt)

            # «?» — подробная подсказка по параметру (не открывает справку)
            q_btn = Gtk.Button(label='?')
            q_btn.set_size_request(28, 28)
            q_btn.set_tooltip_text(t('builder.q_tooltip'))
            q_btn.connect("clicked",
                          lambda b, msg=detailed: self._show_param_tip(msg))

            if kind == 'spin':
                lo, hi, step = spec['min'], spec['max'], spec['step']
                w = Gtk.SpinButton.new_with_range(lo, hi, step)
                try:
                    w.set_value(float(val) if val else 0)
                except Exception:
                    w.set_value(0)
                w.set_tooltip_text(short)
                row_box.pack_start(w, False, False, 0)
                row_box.pack_start(q_btn, False, False, 0)
                w.connect("value-changed", lambda _, s=spec: on_widget_change(s, w))

            elif kind == 'entry':
                w = Gtk.Entry()
                w.set_text(val or '')
                w.set_placeholder_text(spec.get('placeholder', ''))
                w.set_tooltip_text(short)
                w.set_hexpand(True)
                row_box.pack_start(w, True, True, 0)
                row_box.pack_start(q_btn, False, False, 0)
                w.connect("changed", lambda _, s=spec: on_widget_change(s, w))

            elif kind == 'combo':
                w = Gtk.ComboBoxText()
                for v_id, v_label in spec['variants']:
                    w.append(v_id, v_label)
                w.set_active_id(val if val else '')
                w.set_tooltip_text(short)
                row_box.pack_start(w, False, False, 0)
                row_box.pack_start(q_btn, False, False, 0)
                w.connect("changed", lambda _, s=spec: on_widget_change(s, w))

            elif kind == 'check':
                w = Gtk.CheckButton()
                w.set_active(bool(val))
                w.set_tooltip_text(short)
                row_box.pack_start(w, False, False, 0)
                row_box.pack_start(q_btn, False, False, 0)
                w.connect("toggled", lambda _, s=spec: on_widget_change(s, w))

            widgets[opt] = w
            group_frames[gkey].pack_start(row_box, False, False, 0)

        scrolled.add(controls_box)
        main_vbox.pack_start(scrolled, True, True, 0)


        str_entry.connect("changed", refresh_widgets_from_string)

        # ⭐ v2.0.10: синхронизация со строкой окна настроек режима —
        # правка любого регулятора обновляет ОБЩУЮ строку ввода
        def _sync_to_mode_window():
            ms2 = getattr(self, '_mode_settings_window', None)
            if ms2 is not None and getattr(ms2, 'params_entry', None) \
                    is not None:
                ms2.params_entry.set_text(str_entry.get_text())
            return True
        str_entry.connect("changed", lambda e: _sync_to_mode_window())
        return main_vbox

    def _show_param_tip(self, message):
        """Диалог подробной подсказки по одному параметру конструктора."""
        dialog = Gtk.Dialog(title=t('builder.tip_title'), flags=0)
        dialog.add_buttons(t('btn.ok'), Gtk.ResponseType.OK)
        dialog.set_default_size(520, 260)

        content = dialog.get_content_area()
        scrolled = Gtk.ScrolledWindow()
        scrolled.set_vexpand(True)
        label = Gtk.Label(label=message)
        label.set_xalign(0)
        label.set_valign(Gtk.Align.START)
        label.set_line_wrap(True)
        label.set_margin_top(10); label.set_margin_bottom(10)
        label.set_margin_start(12); label.set_margin_end(12)
        label.set_selectable(True)
        scrolled.add(label)
        content.pack_start(scrolled, True, True, 0)
        content.show_all()

        dialog.run()
        dialog.destroy()

    # ================= /КОНСТРУКТОР ПАРАМЕТРОВ =================

    def show_help(self, widget):
        """Окно справки: общая часть + сворачиваемые секции по темам.

        ⭐ v1.9.1 (user): раньше — одна простыня текста, где byedpi- и
        nfqws-материал мешались. Теперь Gtk.Expander («▸ заголовок»,
        раскрывается по плюсику в строке): общее описание всегда видно,
        детали каждого движка раскрываются только когда нужны.
        Тексты секций — HELP_SECTIONS в ciadpi_texts.py (ru/en).
        """
        lang = get_lang()
        sections = HELP_SECTIONS.get(lang) or HELP_SECTIONS.get('ru', {})
        if not sections:
            self.show_notification(t('notif.error'), 'Справка недоступна')
            return

        dialog = Gtk.Dialog(title=t('help.title'), flags=0)
        dialog.add_buttons(t('btn.ok'), Gtk.ResponseType.OK)
        dialog.set_default_size(620, 560)

        content_area = dialog.get_content_area()
        scroll = Gtk.ScrolledWindow()
        scroll.set_policy(Gtk.PolicyType.AUTOMATIC, Gtk.PolicyType.AUTOMATIC)
        box = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=6)
        box.set_margin_top(10); box.set_margin_bottom(10)
        box.set_margin_start(10); box.set_margin_end(10)

        for header, body in sections:
            if header is None:
                # None-ключ = общий текст без сворачивания (интро)
                # ⭐ v1.9.2: интро идёт через set_markup — экранируем
                # <>&, иначе голый «&» в тексте роняет Pango (en-текст)
                lbl = Gtk.Label()
                lbl.set_markup(GLib.markup_escape_text(body))
                lbl.set_xalign(0)
                lbl.set_line_wrap(True)
                lbl.set_selectable(True)
                box.pack_start(lbl, False, False, 0)
                continue
            exp = Gtk.Expander(label=GLib.markup_escape_text(header))
            exp.set_use_markup(True)
            # ⭐ v2.0 (user: «в подразделах лишнее место после текста —
            # достаточно выделения пустой строкой сверху/снизу»):
            # TextView имеет собственный минимум высоты (~3 строки) и
            # расширяет секцию даже под однострочный текст. Вместо него —
            # компактный Gtk.Label: высота ровно по тексту, сверху и
            # снизу отступы 6px (аналог пустой строки), wrap включён.
            lbl_body = Gtk.Label()
            lbl_body.set_markup(GLib.markup_escape_text(body))
            lbl_body.set_xalign(0)
            lbl_body.set_line_wrap(True)
            lbl_body.set_selectable(True)
            lbl_body.set_margin_top(6)
            lbl_body.set_margin_bottom(6)
            lbl_body.set_margin_start(8)
            lbl_body.set_margin_end(8)
            exp.add(lbl_body)
            box.pack_start(exp, False, False, 0)

        scroll.add(box)
        content_area.pack_start(scroll, True, True, 0)
        content_area.show_all()
        # ⭐ v2.0.9: справка НЕМОДАЛЬНАЯ (dialog.run() блокировал
        # все окна приложения — user: «осталась модальность у справки»)
        dialog.show_all()
        dialog.connect('delete-event',
                       lambda d, e: (d.destroy(), True)[1])
        # ⭐ v2.0.10 (user: «справка не закрывается по кнопке ОК»):
        # response без run() никто не слушал — слушаем вручную.
        dialog.connect('response',
                       lambda d, r: d.destroy())

    def show_about(self, widget):
        """Окно «О программе» (на языке интерфейса)"""
        lang = get_lang()
        about_text = ABOUT_TEXTS.get(lang) or ABOUT_TEXTS.get('ru', '')


        dialog = Gtk.Dialog(title=t('about.title'), flags=0)
        dialog.add_buttons(t('btn.ok'), Gtk.ResponseType.OK)
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

    def rebuild_menu(self):
        """Пересоздать меню индикатора (например, после смены языка).

        AppIndicator держит ссылку на меню — заменяем целиком,
        старое уничтожаем. Вызывается из show_app_settings,
        когда язык изменился: главное меню переключается сразу,
        без перезапуска индикатора.
        """
        try:
            old_menu = getattr(self, '_tray_menu', None)
            new_menu = self.create_menu()
            if self.indicator:
                self.indicator.set_menu(new_menu)
            self._tray_menu = new_menu
            if old_menu:
                old_menu.destroy()
            # Сразу показываем актуальный статус (созданный create_menu
            # айтем статуса с «Проверка...» перезапишется реальным состоянием)
            self.update_status()
        except Exception as e:
            print(f"⚠️ Не удалось пересобрать меню: {e}")

    def show_app_settings(self, widget=None):
        """Диалог настроек приложения: язык, уведомления, автозапуск."""
        dialog = Gtk.Dialog(title=t('app.title'), flags=0)
        dialog.add_buttons(t('btn.close'), Gtk.ResponseType.CLOSE)
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

        # ⭐ ЯЗЫК ПРИМЕНЯЕТСЯ СРАЗУ: пересобираем меню трея
        if lang_changed:
            self.rebuild_menu()
            # уведомление на ОБОИХ языках (пользователь мог не понять
            # сообщение на новом) — без блокирующего диалога,
            # чтобы «Выход» никогда не зависал из-за скрытого окна
            self.show_notification(
                "🇷🇺 Язык изменён — меню обновлено\n🇬🇧 Language changed — menu updated",
                t('app.lang_now'),
                category=None)

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
        """Выход из приложения с правильным управлением прокси.

        ⭐ Gtk.main_quit() гасит только САМЫЙ ВНУТРЕННИЙ вложенный
        цикл (открытый диалогом .run()). Если при выходе висит
        какой-либо диалог (например, о смене языка — он мог потерять
        фокус и спрятаться за окнами), внешний Gtk.main() продолжал
        жить и трей «не выходил». Поэтому:
        1) вычищаем очередь событий (чтобы pending-диалоги отработали),
        2) вызываем main_quit несколько раз — по разу на каждый
           уровень вложенности,
        3) страховочный таймер добивает процесс через 500 мс.
        """
        # защита от повторного нажатия «Выход»
        if getattr(self, '_exiting', False):
            return
        self._exiting = True

        print("💾 Выход: сохраняем настройки программы...")

        # ⭐ СОХРАНЯЕМ НАСТРОЙКИ ПРОГРАММЫ ПЕРЕД ВЫХОДОМ
        self.current_params["we_changed_proxy"] = self.we_changed_proxy
        self.save_config()
        print(f"💾 Сохранены настройки: we_changed_proxy={self.we_changed_proxy}")

        if self.current_params.get("auto_disable_proxy", False) and self.we_changed_proxy:
            # ⭐ v2.0.6: проверка сервиса — БЕЗ subprocess в главном
            # потоке (висевший systemctl is-active = «выход не работает»).
            # Проверяем дешёво: pkexec/sudo не нужны, is-active быстр,
            # но во время job-lock может висеть — заменяем на попытку
            # через отдельный поток и НЕ ждём её: восстанавливаем
            # прокси сразу (безопасно в любом состоянии сервиса).
            print("🔄 Выход: восстанавливаем системные настройки прокси…")
            success = self.restore_system_proxy_backup()
            if success:
                print("✅ Системные настройки восстановлены при выходе")
            self.show_notification(t('exit.title'), t('exit.restored'))

        if hasattr(self, 'is_searching') and self.is_searching:
            self.stop_autosearch()

        # ⭐ ДОБИВАЕМ ВСЕ ВЛОЖЕННЫЕ ЦИКЛЫ (диалоги .run()) — НО без
        # бесконечного ожидания: тикеры каждые 3с подкидывают новые
        # события, и старый while events_pending() никогда не
        # заканчивался («Выход не работает»). Ограничиваем 20 итераций.
        try:
            for _ in range(20):
                if not Gtk.events_pending():
                    break
                Gtk.main_iteration_do(False)
        except Exception:
            pass
        for _ in range(5):  # по числу возможных уровней вложенности
            Gtk.main_quit()

        # страховка: если что-то всё ещё живо — жёсткий выход через 500 мс
        try:
            GLib.timeout_add(500, lambda: (os._exit(0), False)[1])
        except Exception:
            pass

if __name__ == "__main__":
    # Запускаем как демон
    import signal
    signal.signal(signal.SIGINT, signal.SIG_DFL)
    
    indicator = AdvancedTrayIndicator()
    Gtk.main()

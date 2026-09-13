#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""v2.0.12 GUI-тесты: Избранное (M+/M−) + регресс багфиксов v2.0.11.1.

Проверяем:
 1. Регресс: консоль обновления открывается с 1-го клика (Pango).
 2. Регресс: настройки приложения видимы с 1-го вызова (show_all).
 3. Избранное: раздел заменил «Примеры», стартово = старые примеры.
 4. M+ у текущего параметра — строка попадает наверх списка.
 5. M+ у «Последних» — строка попадает в избранное.
 6. M− — удаляет строку из списка (живая перерисовка).
 7. «→» — стрелочка без надписи + tooltip.
 8. M+ у найденной стратегии (поиск) — активна при результате.
 9. Хранение: config.json params_favorites.<mode>, дубль — наверх.
10. Избранное переживает пересоздание окна (персистентность).
"""
import json
import sys
import types
from pathlib import Path

# изолированный HOME — не трогаем реальный конфиг юзера
import os
import shutil as _sh
if Path('/tmp/ciadpi_fav_test').exists():
    _sh.rmtree('/tmp/ciadpi_fav_test')
os.environ['HOME'] = '/tmp/ciadpi_fav_test'
Path('/tmp/ciadpi_fav_test/.config/ciadpi').mkdir(parents=True,
                                                   exist_ok=True)

sys.path.insert(0, '/home/templard/ciadpi_indicator')

import gi
gi.require_version('Gtk', '3.0')
from gi.repository import Gtk

results = []


def check(name, cond, detail=''):
    results.append((name, bool(cond), detail))
    print(f"{'✅' if cond else '❌'} {name}" + (f" — {detail}" if detail else ''))


# стабы (как в диагностике)
class FakeCP:
    def __init__(self, rc=0, out='', err=''):
        self.returncode = rc
        self.stdout = out
        self.stderr = err


import ciadpi_advanced_tray as tray_mod
import ciadpi_mode_settings as ms_mod
import ciadpi_mode_settings as ms

tray_mod.subprocess = types.SimpleNamespace(
    run=lambda cmd, *a, **k: FakeCP(0, 'fake\n', ''))

sys.modules['ciadpi_enginectl'] = types.SimpleNamespace(
    is_active=lambda n: False,
    stop_engine=lambda n: (True, 'stub'),
    start_engine=lambda n: (True, 'stub'))

import shutil
shutil.copy2 = lambda *a, **k: print('[stub-copy2]')


def make_tray():
    tray = object.__new__(tray_mod.AdvancedTrayIndicator)
    tray.current_params = {'engine': 'byedpi', 'bridge_mode': False}
    tray.app_prefs = {}
    tray.default_params = '-T3 -A torst -o1 -o25+s -r 1+s'
    tray.show_notification = lambda *a, **k: None
    tray.rebuild_menu = lambda: None
    tray._save_app_prefs = lambda: None
    tray._set_autostart = lambda on: True
    tray._systemctl = lambda *a, **k: (True, 'stub')
    tray._locate_ciadpi = lambda user=None: (
        Path('/tmp/fake_byedpi'), Path('/tmp/fake_byedpi/ciadpi'))
    tray._app_settings_window = None
    tray._mode_settings_window = None
    tray._active_engine = lambda: 'byedpi'
    return tray


def cfg_read():
    p = Path('/tmp/ciadpi_fav_test/.config/ciadpi/config.json')
    return json.loads(p.read_text(encoding='utf-8')) if p.exists() else {}


print('=' * 64)
print('v2.0.12 GUI-тесты (Xvfb)')
print('=' * 64)

# ---------- регресс багфиксов v2.0.11.1 ----------
tray = make_tray()
tray._open_update_console('T', 'T')[0].destroy()
check('регресс: _open_update_console не падает (Pango.SCALE)',
      True)
tray.show_app_settings()
w = tray._app_settings_window
check('регресс: настройки видимы с 1-го вызова',
      w is not None and w.get_visible())
w.destroy()
tray._app_settings_window = None

# ---------- окно настроек режима: вкладка Параметры ----------
tray2 = make_tray()
win = ms.ModeSettingsWindow(tray2)
# подменяем show_notification tray-заглушкой уже сделано
win.present()
check('mode-settings: окно построено', win.dialog is not None)

# раздел «Избранное» есть, «Примеры» нет
frames = []
def find_frames(c):
    for ch in c.get_children():
        if isinstance(ch, Gtk.Frame):
            frames.append(ch.get_label() or '')
        elif hasattr(ch, 'get_children'):
            find_frames(ch)
find_frames(win.dialog.get_content_area())
check('favorites: раздел «Избранное» есть',
      any('Избранное' in f for f in frames), f"frames={frames}")
check('favorites: раздел «Примеры» удалён',
      not any(f == 'Примеры' for f in frames))

# стартовое = старые примеры byedpi
fav_cfg = (cfg_read().get('params_favorites') or {}).get('byedpi') or []
from ciadpi_mode_settings import MODE_EXAMPLES
check('favorites: стартово = старые примеры (5 шт)',
      fav_cfg == MODE_EXAMPLES['byedpi'],
      f"n={len(fav_cfg)}")

# M+ у текущего параметра
win.params_entry.set_text('-T9 -A torst -o3 -o7+s -r 2+s')
win._on_fav_add_current('byedpi')
fav_cfg = (cfg_read().get('params_favorites') or {}).get('byedpi') or []
check('favorites: M+ current — строка первой в списке',
      fav_cfg and fav_cfg[0] == '-T9 -A torst -o3 -o7+s -r 2+s')
check('favorites: M+ current — всего 6 (5 дефолтных + 1)',
      len(fav_cfg) == 6, f"n={len(fav_cfg)}")

# живая перерисовка: в списке видна новая строка сверху
entries_in_fav = []
def walk_fav(c):
    for ch in c.get_children():
        if isinstance(ch, Gtk.Entry):
            entries_in_fav.append(ch.get_text())
        elif hasattr(ch, 'get_children'):
            walk_fav(ch)
if win._favorites_vbox is not None:
    walk_fav(win._favorites_vbox)
check('favorites: живая перерисовка — строка сверху в GUI',
      entries_in_fav and entries_in_fav[0] == '-T9 -A torst -o3 -o7+s -r 2+s',
      f"first={entries_in_fav[0][:30] if entries_in_fav else None}…")

# дубль M+ — поднимается наверх, не дублируется
win._on_fav_add_current('byedpi')
fav_cfg = (cfg_read().get('params_favorites') or {}).get('byedpi') or []
check('favorites: дубль M+ — наверх без дублирования',
      len(fav_cfg) == 6 and fav_cfg[0] == '-T9 -A torst -o3 -o7+s -r 2+s')

# M− удаляет
win._on_fav_remove('byedpi', '-T9 -A torst -o3 -o7+s -r 2+s')
fav_cfg = (cfg_read().get('params_favorites') or {}).get('byedpi') or []
check('favorites: M− удаляет строку',
      '-T9 -A torst -o3 -o7+s -r 2+s' not in fav_cfg and len(fav_cfg) == 5)

# кнопки: «→» стрелочка + tooltip; M+/M− квадратные
btns_in_fav = []
def walk_fav_btns(c):
    for ch in c.get_children():
        if isinstance(ch, Gtk.Button):
            btns_in_fav.append((ch.get_label() or '',
                                ch.get_tooltip_text() or ''))
        elif hasattr(ch, 'get_children'):
            walk_fav_btns(ch)
walk_fav_btns(win._favorites_vbox)
arrows = [b for b in btns_in_fav if b[0] == '→']
mminus = [b for b in btns_in_fav if 'M−' in b[0]]
check('favorites: кнопки «→» стрелочкой (5 строк)',
      len(arrows) == 5, f"n={len(arrows)}")
check('favorites: «→» с tooltip без надписи «в строку»',
      arrows and all('параметр' in a[1].lower() for a in arrows),
      f"tip={arrows[0][1] if arrows else None}")
check('favorites: кнопки M− у каждой строки',
      len(mminus) == 5, f"n={len(mminus)}")

# M+ у «Последних»: пуш в recent, потом M+ оттуда
win._push_recent('byedpi', '-T4 -A torst -o9 -o11+s')
win._fill_recent(win._recent_vbox, 'byedpi')
# найдём M+ в блоке «Последние»
recent_btns = []
def walk_recent(c):
    for ch in c.get_children():
        if isinstance(ch, Gtk.Button) and 'M+' in (ch.get_label() or ''):
            recent_btns.append(ch)
        elif hasattr(ch, 'get_children'):
            walk_recent(ch)
walk_recent(win._recent_vbox)
check('favorites: M+ у строк «Последних»',
      len(recent_btns) >= 1, f"n={len(recent_btns)}")
if recent_btns:
    recent_btns[0].clicked()
    fav_cfg = (cfg_read().get('params_favorites') or {}).get('byedpi') or []
    check('favorites: M+ из «Последних» сохраняет в config',
          '-T4 -A torst -o9 -o11+s' in fav_cfg)

# M+ у найденной стратегии: эмулируем результат поиска
win._search_state['best'] = '--filter-tcp=443 --dpi-desync=fake,split2'
win._on_search_fav_add('byedpi')
fav_cfg = (cfg_read().get('params_favorites') or {}).get('byedpi') or []
check('favorites: M+ найденной стратегии — в список',
      '--filter-tcp=443 --dpi-desync=fake,split2' in fav_cfg)

# M+ у дефолта
win._on_fav_add_string('byedpi', ms.MODE_DEFAULTS['byedpi'])
fav_cfg = (cfg_read().get('params_favorites') or {}).get('byedpi') or []
check('favorites: M+ дефолта — наверх',
      fav_cfg[0] == ms.MODE_DEFAULTS['byedpi'])

# персистентность: пересоздание окна — список жив
win.dialog.destroy()
win2 = ms.ModeSettingsWindow(tray2)
win2.present()
fav_after = win2._favorites_for('byedpi')
check('favorites: персистентность (окно пересоздано — список жив)',
      fav_after == fav_cfg, f"n={len(fav_after)}")
# init_defaults НЕ перезаливает удалённое
check('favorites: init_defaults не перезаливает список',
      fav_after == fav_cfg)

# nfqws-режим: свои избранные
win2.dialog.destroy()
tray3 = make_tray()
tray3._active_engine = lambda: 'nfqws'
win3 = ms.ModeSettingsWindow(tray3)
win3.present()
fav_nfqws = (cfg_read().get('params_favorites') or {}).get('nfqws') or []
check('favorites: у nfqws свой стартовый список (5 примеров)',
      fav_nfqws == MODE_EXAMPLES['nfqws'], f"n={len(fav_nfqws)}")
win3.dialog.destroy()

# snimod/bridge: избранного нет (без строковых параметров)
tray4 = make_tray()
tray4._active_engine = lambda: 'snimod'
win4 = ms.ModeSettingsWindow(tray4)
win4.present()
check('favorites: snimod — без дефолтного избранного',
      (cfg_read().get('params_favorites') or {}).get('snimod') == [])
win4.dialog.destroy()

print('=' * 64)
passed = sum(1 for _, ok, _ in results if ok)
print(f'ИТОГ: {passed}/{len(results)} passed')
if passed != len(results):
    sys.exit(1)

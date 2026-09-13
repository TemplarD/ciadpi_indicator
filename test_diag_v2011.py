#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Диагностика багов v2.0.11:
(1) консоль обновления byedpi/zapret не запускается;
(2) «Настройки приложения» открываются только со 2-го раза.
Тестируем РОВНО ту копию, что у юзера: ~/.local/bin (синк v2.0.11).
Все сетевые/системные вызовы застаблены, HOME изолирован."""
import os
import sys
import traceback
from pathlib import Path

os.environ['HOME'] = '/tmp/ciadpi_test_home'
Path('/tmp/ciadpi_test_home/.config/ciadpi').mkdir(parents=True,
                                                  exist_ok=True)

sys.path.insert(0, '/home/templard/ciadpi_indicator')

import gi
gi.require_version('Gtk', '3.0')
from gi.repository import Gtk

import types


# стаб subprocess для tray-модуля
class FakeCP:
    def __init__(self, rc=0, out='', err=''):
        self.returncode = rc
        self.stdout = out
        self.stderr = err


import ciadpi_advanced_tray as tray_mod
print('модуль из:', tray_mod.__file__)

tray_mod.subprocess = types.SimpleNamespace(
    run=lambda cmd, *a, **k: (
        print('[stub-run]', [str(c) for c in cmd][:3]) or
        FakeCP(0, 'fake\n', '')))

# стаб ciadpi_enginectl (чтобы zapret-поток не трогал реальные сервисы)
sys.modules['ciadpi_enginectl'] = types.SimpleNamespace(
    is_active=lambda n: False,
    stop_engine=lambda n: (True, 'stub'),
    start_engine=lambda n: (True, 'stub'))

# стаб shutil.copy2 (чтобы потоки не писали бэкапы в реальные каталоги)
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
    return tray


print('=' * 64)

# ---------- БАГ 2: настройки приложения со 2-го раза ----------
tray = make_tray()
tray.show_app_settings()
w = tray._app_settings_window
vis1 = w.get_visible() if w is not None else 'NO WINDOW'
print(f'BUG2: 1-й вызов: window={w is not None} '
      f'get_visible()={vis1}')
tray.show_app_settings()
vis2 = (tray._app_settings_window.get_visible()
        if tray._app_settings_window else 'NO')
print(f'BUG2: 2-й вызов: get_visible()={vis2}')
if w is not None:
    w.destroy()
    tray._app_settings_window = None

print('=' * 64)

# ---------- БАГ 1: консоль обновления ----------
print('--- Pango доступен? ---')
try:
    from gi.repository import Pango
    print('Pango.Weight.BOLD =', Pango.Weight.BOLD)
    print('Pango.Scale.SMALL =', getattr(Pango.Scale, 'SMALL',
                                          'ОТСУТСТВУЕТ!'))
except Exception:
    traceback.print_exc()

print('--- прямой вызов _open_update_console ---')
try:
    dlg, log, finish = tray._open_update_console('T', 'T')
    print(f'open_console: OK, get_visible()={dlg.get_visible()}')
    dlg.destroy()
except Exception:
    print('!!! ИСКЛЮЧЕНИЕ в _open_update_console:')
    traceback.print_exc()

print('--- update_byedpi (как клик по кнопке) ---')
try:
    tray.update_byedpi(None)
    tops = Gtk.Window.list_toplevels()
    cons = [t for t in tops
            if 'Обновление byedpi' in (t.get_title() or '')]
    print(f'консоль byedpi: toplevels={len(cons)}, '
          f'visible={[t.get_visible() for t in cons]}')
    for t in cons:
        t.destroy()
except Exception:
    print('!!! ИСКЛЮЧЕНИЕ в update_byedpi:')
    traceback.print_exc()

print('--- update_zapret (как клик по кнопке) ---')
try:
    tray.update_zapret(None)
    tops = Gtk.Window.list_toplevels()
    cons = [t for t in tops
            if 'nfqws' in (t.get_title() or '')]
    print(f'консоль nfqws: toplevels={len(cons)}, '
          f'visible={[t.get_visible() for t in cons]}')
    for t in cons:
        t.destroy()
except Exception:
    print('!!! ИСКЛЮЧЕНИЕ в update_zapret:')
    traceback.print_exc()

print('=' * 64)
print('диагностика завершена')

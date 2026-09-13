#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""v2.0.14 — EN-дымовой тест локализации.

Переключаем язык на 'en', строим ВСЕ окна и проверяем, что в
виджетах нет русского текста (кириллицы) — всё переведено.
"""
import json
import sys
import types
from pathlib import Path

import os
import shutil as _sh
if Path('/tmp/ciadpi_l10n_test').exists():
    _sh.rmtree('/tmp/ciadpi_l10n_test')
os.environ['HOME'] = '/tmp/ciadpi_l10n_test'
CFG = Path('/tmp/ciadpi_l10n_test/.config/ciadpi')
CFG.mkdir(parents=True, exist_ok=True)

REPO_ROOT = str(Path(__file__).resolve().parent)
sys.path.insert(0, REPO_ROOT)

import gi
gi.require_version('Gtk', '3.0')
from gi.repository import Gtk

results = []


def check(name, cond, detail=''):
    results.append((name, bool(cond), detail))
    print(f"{'✅' if cond else '❌'} {name}" + (f" — {detail}" if detail else ''))


# стабы движков
sys.modules['ciadpi_enginectl'] = types.SimpleNamespace(
    is_active=lambda n: False,
    stop_engine=lambda n: (True, 'stub'),
    start_engine=lambda n: (True, 'stub'),
    stop_bridge=lambda: (True, 'stub'),
    start_bridge=lambda: (True, 'stub'))

class FakeCP:
    def __init__(self, rc=0, out='', err=''):
        self.returncode = rc
        self.stdout = out
        self.stderr = err

import ciadpi_advanced_tray as tray_mod
import ciadpi_mode_settings as ms
import ciadpi_profiles
import ciadpi_i18n

tray_mod.subprocess = types.SimpleNamespace(
    run=lambda cmd, *a, **k: FakeCP(0, 'fake\n', ''))

# ⭐ EN-режим
ciadpi_i18n.set_lang('en')
ciadpi_i18n.save_lang()

import shutil
shutil.copy2 = lambda *a, **k: None


def make_tray():
    tray = object.__new__(tray_mod.AdvancedTrayIndicator)
    tray.current_params = {'engine': 'byedpi', 'bridge_mode': False}
    tray.app_prefs = {}
    tray.default_params = '-T3 -A torst -o1 -o25+s -r 1+s'
    tray.show_notification = lambda *a, **k: None
    tray.rebuild_menu = lambda: None
    tray.update_status = lambda: None
    tray._save_app_prefs = lambda: None
    tray._set_autostart = lambda on: True
    tray._systemctl = lambda *a, **k: (True, 'stub')
    tray._locate_ciadpi = lambda user=None: (
        Path('/tmp/fake_byedpi'), Path('/tmp/fake_byedpi/ciadpi'))
    tray._app_settings_window = None
    tray._mode_settings_window = None
    tray._help_window = None
    tray._active_engine = lambda: 'byedpi'
    tray.whitelist = {'enabled': False, 'domains': [], 'ips': [],
                      'bypass_proxy': True, 'bypass_dpi': False}
    tray.whitelist_manager = None
    return tray


CYR = re_re = None
import re
CYR = re.compile(r'[а-яА-ЯёЁ]')


def walk_no_russian(name, widget):
    """Собрать кириллицу из label/заголовков/tooltip виджетов."""
    bad = []

    def w(c):
        for ch in (c.get_children() if hasattr(c, 'get_children') else []):
            lbl = ''
            try:
                if isinstance(ch, Gtk.Label):
                    lbl = ch.get_text() or ''
                elif isinstance(ch, Gtk.Button):
                    lbl = ch.get_label() or ''
                elif isinstance(ch, Gtk.Frame):
                    lbl = ch.get_label() or ''
                elif isinstance(ch, Gtk.CheckButton):
                    lbl = ch.get_label() or ''
                elif isinstance(ch, Gtk.RadioButton):
                    lbl = ch.get_label() or ''
                elif isinstance(ch, Gtk.Entry):
                    lbl = ch.get_placeholder_text() or ''
            except Exception:
                pass
            if CYR.search(lbl):
                bad.append(lbl[:60])
            try:
                tip = ch.get_tooltip_text() or ''
                if CYR.search(tip):
                    bad.append('TIP:' + tip[:50])
            except Exception:
                pass
            if hasattr(ch, 'get_children'):
                w(ch)
    w(widget)
    check(name, not bad, f"кириллица: {bad[:4]}" if bad else '')


print('=' * 64)
print('v2.0.14 EN-дымовой тест локализации')
print('=' * 64)

tray = make_tray()

# --- МЕНЮ: пункты (проверяем тексты ключей) ---
for key, must_en in [
    ('menu.mode_settings', 'Mode settings'),
    ('menu.engines', 'Bypass modes'),
    ('menu.profiles', 'Profiles'),
    ('engines.title', 'DPI Bypass Modes'),
    ('profiles.title', 'Settings Profiles'),
    ('ms.title_byedpi', 'byedpi — SOCKS5 proxy'),
    ('ms.favorites', 'Favorites'),
    ('ms.recent', 'Recently used'),
    ('app.update_byedpi', 'Update byedpi'),
    ('app.update_nfqws', 'Update nfqws (zapret)'),
    ('ms.tab_params', 'Parameters'),
    ('ms.tab_builder', 'Builder'),
    ('ms.tab_search', 'Strategy search'),
]:
    val = ciadpi_i18n.t(key)
    check(f"i18n[{key}] EN", must_en in val, val)

# --- ОКНО РЕЖИМОВ ---
tray.show_engines_window()
eng = tray._engines_window
check('engines: титул EN', 'Bypass Modes' in (eng.get_title() or ''),
      eng.get_title())
walk_no_russian('engines: виджеты без кириллицы', eng.get_content_area())
eng.destroy()
tray._engines_window = None

# --- ОКНО ПРОФИЛЕЙ ---
tray.show_profiles_dialog()
# найдём открытый диалог профилей
prof_dlg = [w for w in Gtk.Window.list_toplevels()
            if 'Profiles' in (w.get_title() or '')]
check('profiles: окно открылось', len(prof_dlg) == 1)
if prof_dlg:
    walk_no_russian('profiles: виджеты без кириллицы',
                    prof_dlg[0].get_content_area())
    prof_dlg[0].destroy()

# --- НАСТРОЙКИ ПРИЛОЖЕНИЯ (кнопки обновлений) ---
tray.show_app_settings()
appw = tray._app_settings_window
check('app-settings: титул содержит Settings (EN)',
      'Settings' in (appw.get_title() or '') or
      'Application' in (appw.get_title() or ''),
      appw.get_title())
walk_no_russian('app-settings: виджеты без кириллицы',
                appw.get_content_area())
appw.destroy()
tray._app_settings_window = None

# --- НАСТРОЙКИ РЕЖИМА (byedpi) ---
win = ms.ModeSettingsWindow(tray)
win.present()
check('mode-settings: титул EN', 'Mode settings' in (win.dialog.get_title() or ''),
      win.dialog.get_title())
walk_no_russian('mode-settings(byedpi): без кириллицы',
                win.dialog.get_content_area())
win.dialog.destroy()

# --- НАСТРОЙКИ РЕЖИМА (nfqws: конструктор с подсказками) ---
tray._active_engine = lambda: 'nfqws'
win2 = ms.ModeSettingsWindow(tray)
win2.present()
check('mode-settings(nfqws): титул EN',
      'Mode settings' in (win2.dialog.get_title() or ''))
# конструктор nfqws
w = tray._build_nfqws_builder_widget()
check('nfqws builder: построен', w is not None)
if w is not None:
    walk_no_russian('nfqws-builder: без кириллицы', w)
win2.dialog.destroy()

# --- КОНСОЛЬ ОБНОВЛЕНИЯ ---
dlg, log, finish = tray._open_update_console(
    ciadpi_i18n.t('upd.title_byedpi'), ciadpi_i18n.t('upd.target_byedpi'))
check('update-console: открылась', dlg.get_visible())
walk_no_russian('update-console: без кириллицы', dlg.get_content_area())
dlg.destroy()

# --- профили-модуль: сообщения EN ---
ok, msg = ciadpi_profiles.ProfileManager().capture_current('Test')
check('profiles.capture: сообщение EN',
      ok and 'saved and activated' in msg, msg[:80])
ok2, msg2 = ciadpi_profiles.ProfileManager().delete_profile('Test')
check('profiles.delete: сообщение EN',
      ok2 and 'deleted' in msg2, msg2[:60])
ok3, msg3 = ciadpi_profiles.ProfileManager().capture_current('')
check('profiles.bad_name: сообщение EN',
      not ok3 and '1-32' in msg3, msg3[:60])

# --- RU-обратно: язык возвращаем как был (не трогаем конфиг юзера —
#     тестовый HOME уже изолирован) ---
ciadpi_i18n.set_lang('ru')

print('=' * 64)
passed = sum(1 for _, okc, _ in results if okc)
print(f'ИТОГ: {passed}/{len(results)} passed')
if passed != len(results):
    sys.exit(1)

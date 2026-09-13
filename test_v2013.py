#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""v2.0.13 GUI-тесты: профили = полное состояние со всей памятью.

Проверяем:
 1. apply_profile ПЕРЕКЛЮЧАЕТ выбранный режим (главный баг!).
 2. Память параметров: недавние + избранное — в профиле, применяются.
 3. Параметры каждого движка применяются (byedpi/nfqws/хосты snimod).
 4. Белый список — отдельно у каждого профиля.
 5. Настройки приложения — привязаны к профилю.
 6. Автосинк: изменения памяти пишутся в активный профиль.
 7. Сохранённый профиль становится активным.
"""
import json
import sys
import types
from pathlib import Path

import os
import shutil as _sh
if Path('/tmp/ciadpi_prof_test').exists():
    _sh.rmtree('/tmp/ciadpi_prof_test')
os.environ['HOME'] = '/tmp/ciadpi_prof_test'
CFG = Path('/tmp/ciadpi_prof_test/.config/ciadpi')
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


# --- стабы движков (не трогаем реальные сервисы) ---
sys.modules['ciadpi_enginectl'] = types.SimpleNamespace(
    is_active=lambda n: False,
    stop_engine=lambda n: (True, 'stub stop'),
    start_engine=lambda n: (True, 'stub start'),
    stop_bridge=lambda: (True, 'stub'),
    start_bridge=lambda: (True, 'stub'),
)

import ciadpi_advanced_tray as tray_mod
import ciadpi_profiles
import ciadpi_mode_settings as ms


def rj(p, default=None):
    try:
        d = json.loads(Path(p).read_text(encoding='utf-8'))
        return d if isinstance(d, dict) else (default or {})
    except Exception:
        return default or {}


def make_tray():
    tray = object.__new__(tray_mod.AdvancedTrayIndicator)
    tray.config_file = CFG / 'config.json'
    tray.default_params = '-T3 -A torst -o1 -o25+s -r 1+s'
    tray.current_params = tray.load_config()
    tray.whitelist_file = CFG / 'whitelist.json'
    tray.whitelist = tray.load_whitelist()
    tray.app_prefs = tray._load_app_prefs()
    tray.whitelist_manager = None
    tray.show_notification = lambda *a, **k: None
    tray.rebuild_menu = lambda: None
    tray.update_status = lambda: None
    tray._active_engine = lambda: 'byedpi'
    tray._save_app_prefs = tray_mod.AdvancedTrayIndicator._save_app_prefs.__get__(tray)
    tray._set_autostart = lambda on: True
    return tray


print('=' * 64)
print('v2.0.13 тесты профилей')
print('=' * 64)

# ================= состояние A (Дом) =================
cfgA = {
    'engine': 'nfqws', 'bridge_mode': False,
    'current_params': '-T3 -A torst -o1 -o25+s -r 1+s',
    'params': '-T3 -A torst -o1 -o25+s -r 1+s',
    'params_recent': {'nfqws': ['--A1', '--A2']},
    'params_favorites': {'nfqws': ['--favA']},
}
(CFG / 'config.json').write_text(json.dumps(cfgA), encoding='utf-8')
(CFG / 'nfqws.json').write_text(json.dumps(
    {'params': '--filter-tcp=80,443 --dpi-desync=disorder2'}), encoding='utf-8')
(CFG / 'snimod.json').write_text(json.dumps(
    {'hosts': ['youtube.com', 'github.com']}), encoding='utf-8')
(CFG / 'whitelist.json').write_text(json.dumps(
    {'enabled': True, 'domains': ['A-local'], 'ips': [],
     'bypass_proxy': True, 'bypass_dpi': False}), encoding='utf-8')
(CFG / 'app_prefs.json').write_text(json.dumps(
    {'notifications_enabled': False, 'notif_service': False}), encoding='utf-8')
(CFG / 'ui_language').write_text('ru', encoding='utf-8')

pm = ciadpi_profiles.ProfileManager()
ok, msg = pm.capture_current('Дом')
check('A: сохранение профиля «Дом»', ok, msg)
profA = rj(CFG / 'profiles' / 'Дом.json')
check('A: engine=nfqws в профиле', profA.get('engine') == 'nfqws')
check('A: недавние в профиле', profA.get('params_recent', {}).get(
    'nfqws') == ['--A1', '--A2'])
check('A: избранное в профиле', profA.get('params_favorites', {}).get(
    'nfqws') == ['--favA'])
check('A: белый список в профиле', profA.get('whitelist', {}).get(
    'domains') == ['A-local'])
check('A: настройки приложения в профиле',
      profA.get('app_prefs', {}).get('notifications_enabled') is False)
check('A: параметры nfqws в профиле', profA.get('nfqws_params') ==
      '--filter-tcp=80,443 --dpi-desync=disorder2')

# ================= состояние B (Кафе) =================
cfgB = {
    'engine': 'byedpi', 'bridge_mode': True,
    'current_params': '-T2 -A torst -o2 -o15+s',
    'params_recent': {'byedpi': ['--B1']},
    'params_favorites': {'byedpi': ['--favB']},
}
(CFG / 'config.json').write_text(json.dumps(cfgB), encoding='utf-8')
(CFG / 'whitelist.json').write_text(json.dumps(
    {'enabled': False, 'domains': ['B-cafe'], 'ips': [],
     'bypass_proxy': False, 'bypass_dpi': True}), encoding='utf-8')
(CFG / 'app_prefs.json').write_text(json.dumps(
    {'notifications_enabled': True, 'notif_service': True}), encoding='utf-8')
(CFG / 'ui_language').write_text('en', encoding='utf-8')

ok, msg = pm.capture_current('Кафе')
check('B: сохранение профиля «Кафе»', ok, msg)
check('B: профиль активен после сохранения',
      pm.active_profile() == 'Кафе')

# ================= применяем «Дом» поверх B =================
ok, msg = pm.apply_profile('Дом')
check('apply: применение «Дом» поверх «Кафе»', ok, msg)

cfg_now = rj(CFG / 'config.json')
check('apply: engine ПЕРЕКЛЮЧИЛСЯ на nfqws (главный баг)',
      cfg_now.get('engine') == 'nfqws',
      f"engine={cfg_now.get('engine')}")
check('apply: bridge_mode=False у «Дом»',
      cfg_now.get('bridge_mode') is False)
check('apply: недавние из «Дом»', cfg_now.get('params_recent', {}).get(
    'nfqws') == ['--A1', '--A2'])
check('apply: избранное из «Дом»', cfg_now.get(
    'params_favorites', {}).get('nfqws') == ['--favA'])
wl_now = rj(CFG / 'whitelist.json')
check('apply: белый список «Дом» (A-local)',
      wl_now.get('domains') == ['A-local'])
ap_now = rj(CFG / 'app_prefs.json')
check('apply: настройки приложения «Дом» (notif=off)',
      ap_now.get('notifications_enabled') is False)
check('apply: язык «Дом» (ru)',
      (CFG / 'ui_language').read_text().strip() == 'ru')
check('apply: nfqws-параметры «Дом»',
      rj(CFG / 'nfqws.json').get('params') ==
      '--filter-tcp=80,443 --dpi-desync=disorder2')
check('apply: активный = «Дом»', pm.active_profile() == 'Дом')

# ================= автосинк: применяем параметры =================
# «Дом» активен; юзер меняет параметры nfqws в окне настроек режима
tray = make_tray()
win = ms.ModeSettingsWindow(tray)
win.params_entry = Gtk.Entry()
win._sync_profile(nfqws_params='--filter-tcp=443 NEW')
profA = rj(CFG / 'profiles' / 'Дом.json')
check('автосинк: новые nfqws-параметры в «Дом»',
      profA.get('nfqws_params') == '--filter-tcp=443 NEW')

# недавние через _push_recent (через _save_cfg → sync_active)
win._push_recent('nfqws', '--NEW-RECENT')
profA = rj(CFG / 'profiles' / 'Дом.json')
check('автосинк: недавние обновились в «Дом»',
      '--NEW-RECENT' in (profA.get('params_recent', {}).get(
          'nfqws') or []))
check('автосинк: старые недавние НЕ потерялись',
      '--A1' in (profA.get('params_recent', {}).get('nfqws') or []))

# избранное через _favorite_add
win._favorite_add('nfqws', '--NEW-FAV')
profA = rj(CFG / 'profiles' / 'Дом.json')
check('автосинк: избранное обновилось в «Дом»',
      '--NEW-FAV' in (profA.get('params_favorites', {}).get(
          'nfqws') or []))

# белый список
tray.whitelist = {'enabled': True, 'domains': ['A-NEW'],
                  'ips': [], 'bypass_proxy': True, 'bypass_dpi': False}
tray.save_whitelist()
profA = rj(CFG / 'profiles' / 'Дом.json')
check('автосинк: белый список в «Дом»',
      profA.get('whitelist', {}).get('domains') == ['A-NEW'])

# настройки приложения
tray.app_prefs = {'notifications_enabled': True}
tray._save_app_prefs()
profA = rj(CFG / 'profiles' / 'Дом.json')
check('автосинк: настройки приложения в «Дом»',
      profA.get('app_prefs', {}).get('notifications_enabled') is True)

# ================= применяем «Кафе» — проверка изоляции =================
ok, msg = pm.apply_profile('Кафе')
cfg_now = rj(CFG / 'config.json')
check('изоляция: «Кафе» — engine=byedpi',
      cfg_now.get('engine') == 'byedpi')
check('изоляция: «Кафе» — bridge_mode=True',
      cfg_now.get('bridge_mode') is True)
wl_now = rj(CFG / 'whitelist.json')
check('изоляция: белый список «Кафе» (B-cafe)',
      wl_now.get('domains') == ['B-cafe'])
ap_now = rj(CFG / 'app_prefs.json')
check('изоляция: настройки «Кафе» (notif=on)',
      ap_now.get('notifications_enabled') is True)
check('изоляция: недавние «Кафе»',
      cfg_now.get('params_recent', {}).get('byedpi') == ['--B1'])
check('изоляция: избранное «Кафе»',
      cfg_now.get('params_favorites', {}).get('byedpi') == ['--favB'])

# «Дом» НЕ был повреждён применением «Кафе»
profA = rj(CFG / 'profiles' / 'Дом.json')
check('изоляция: «Дом» не повреждён (nfqws-параметры)',
      profA.get('nfqws_params') == '--filter-tcp=443 NEW')

# старый профиль (v2.0.5, без памяти) — обратная совместимость
old_style = {
    'engine': 'snimod', 'bridge': 'off',
    'byedpi_params': '-T1 -A torst -o1 -o5+s',
    'nfqws_params': '', 'snimod_hosts': ['wikipedia.org'],
    'proxy_enabled': False, 'proxy_mode': 'none',
    'proxy_host': '127.0.0.1', 'proxy_port': '1080',
}
(CFG / 'profiles' / 'Старый.json').write_text(
    json.dumps(old_style), encoding='utf-8')
ok, msg = pm.apply_profile('Старый')
cfg_now = rj(CFG / 'config.json')
check('совместимость: старый профиль без памяти применяется',
      ok and cfg_now.get('engine') == 'snimod')
check('совместимость: старый профиль не затирает память',
      cfg_now.get('params_favorites', {}).get('byedpi') == ['--favB'])

print('=' * 64)
passed = sum(1 for _, ok, _ in results if ok)
print(f'ИТОГ: {passed}/{len(results)} passed')
if passed != len(results):
    sys.exit(1)

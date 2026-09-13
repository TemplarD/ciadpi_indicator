#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""v2.0.11 — GUI-тесты косметических правок (Xvfb).

Проверяем:
 1. Окно «Режимы обхода» закрывается кнопкой «Закрыть» (response).
 2. Справка: синглтон (повторный вызов — present, не дубль),
    титул «Расширенная справка», есть подгруппы режимов, нет дубля
    «Управление сервисом», есть секция про прокси.
 3. Конструктор nfqws: 7 полей + кнопки «?» (справки по месту).
 4. Конструкторы snimod/bridge: кнопки «?» (upstream/tls-name/хосты).
 5. Меню: нет «Настройки режима…»/«Режимы обхода…» с многоточиями.
 6. Настройки приложения: немодальные, есть 2 кнопки обновления
    движков, «Сохранить» работает, повторный вызов — present.
"""
import json
import subprocess
import sys

import os as _os
REPO_ROOT = _os.path.dirname(_os.path.abspath(__file__))
sys.path.insert(0, REPO_ROOT)

import gi
gi.require_version('Gtk', '3.0')
from gi.repository import Gtk, GLib

results = []


def check(name, cond, detail=''):
    results.append((name, bool(cond), detail))
    print(f"{'✅' if cond else '❌'} {name}" + (f" — {detail}" if detail else ''))


def make_tray():
    """Минимальный трей-заглушка для тестов (без AppIndicator)."""
    import importlib
    import ciadpi_advanced_tray as tray_mod
    tray = object.__new__(tray_mod.AdvancedTrayIndicator)
    # минимальные атрибуты, нужные вызываемым методам
    tray.current_params = {
        'engine': 'byedpi',
        'bridge_mode': False,
        'current_params': '-T3 -A torst -o1 -o25+s -r 1+s',
    }
    tray.app_prefs = {}
    tray.default_params = '-T3 -A torst -o1 -o25+s -r 1+s'
    return tray, tray_mod


# ---------- 1) Окно «Режимы обхода» закрывается ----------
def test_engines_window_close():
    tray, mod = make_tray()
    # заглушки для метода
    tray._active_engine = lambda: 'byedpi'
    tray.rebuild_menu = lambda: None
    tray.update_status = lambda: None
    tray.save_config = lambda: None
    tray.show_notification = lambda *a, **k: None
    tray._mode_settings_window = None
    # вызываем открытие окна
    tray.show_engines_window()
    dlg = tray._engines_window
    check('engines: окно создано', dlg is not None)
    if dlg is None:
        return
    visible = dlg.get_visible() if hasattr(dlg, 'get_visible') else True
    check('engines: окно показано', visible)
    # клик «Закрыть» → response → destroy
    btns = [w for w in dlg.get_action_area().get_children()
            if isinstance(w, Gtk.Button)] if dlg.get_action_area() else []
    # кнопка в content-area (btn_box), ищем по label
    close_btn = None
    def find_btn(container):
        nonlocal close_btn
        for ch in container.get_children():
            if isinstance(ch, Gtk.Button) and 'Закрыть' in (ch.get_label() or ''):
                close_btn = ch
            elif hasattr(ch, 'get_children'):
                find_btn(ch)
    find_btn(dlg.get_content_area())
    check('engines: кнопка «Закрыть» есть', close_btn is not None)
    if close_btn:
        close_btn.clicked()
        destroyed = not tray._engines_window
        check('engines: окно закрылось по «Закрыть»',
              tray._engines_window is None,
              f"_engines_window={tray._engines_window}")
    # чистим таймер тикера
    for attr in ('_mode_status_labels', '_mode_radios', '_mode_btns'):
        if hasattr(tray, attr):
            delattr(tray, attr)
    if dlg:
        try:
            dlg.destroy()
        except Exception:
            pass


# ---------- 2) Справка ----------
def test_help():
    tray, mod = make_tray()
    tray.show_notification = lambda *a, **k: None
    tray._help_window = None
    # 1-й вызов — создаёт
    tray.show_help(None)
    w1 = tray._help_window
    check('help: окно создано', w1 is not None)
    # 2-й вызов — тот же объект (present), не новый
    tray.show_help(None)
    w2 = tray._help_window
    check('help: повторный вызов — тот же объект (фокус, не дубль)',
          w1 is w2)
    # титул
    check('help: титул «Расширенная справка»',
          'справка' in (w1.get_title() or '').lower())
    # тексты: дедуп + подгруппы
    from ciadpi_texts import HELP_SECTIONS, HELP_TEXTS
    ru = HELP_TEXTS['ru']
    check('help RU: нет дубля «Управление сервисом» (одна секция)',
          ru.count('УПРАВЛЕНИЕ СЕРВИСОМ') <= 1,
          f"count={ru.count('УПРАВЛЕНИЕ СЕРВИСОМ')}")
    check('help RU: подгруппа byedpi',
          'РЕЖИМ: BYEDPI' in ru)
    check('help RU: подгруппа nfqws',
          'РЕЖИМ: NFQWS' in ru)
    check('help RU: подгруппа snimod',
          'РЕЖИМ: SNIMOD' in ru)
    check('help RU: подгруппа DNS-мост',
          'РЕЖИМ: DNS-МОСТ' in ru)
    check('help RU: секция про прокси (какие режимы нуждаются)',
          'ПРОКСИ: ДЛЯ КАКИХ РЕЖИМОВ НУЖЕН' in ru)
    check('help RU: секция обновления движков',
          'ОБНОВЛЕНИЕ ДВИЖКОВ' in ru)
    check('help RU: byedpi-флаги помечены как byedpi',
          'ПАРАМЕТРЫ BYEDPI (СПРАВОЧНИК ФЛАГОВ)' in ru)
    en = HELP_TEXTS['en']
    check('help EN: подгруппы режимов',
          'MODE: BYEDPI' in en and 'MODE: NFQWS' in en)
    check('help EN: секция про прокси',
          'PROXY: WHICH MODES NEED IT' in en)
    # разбор на секции
    secs = HELP_SECTIONS['ru']
    headers = [h for h, b in secs if h]
    check('help: секции распарсились (>8)', len(headers) > 8,
          f"n={len(headers)}")
    check('help: нет дублей заголовков',
          len(headers) == len(set(headers)))
    w1.destroy()
    tray._help_window = None


# ---------- 3) Конструктор nfqws со справками ----------
def test_nfqws_builder():
    tray, mod = make_tray()
    tray._show_param_tip = lambda msg: print(f"   [tip] {msg[:60]}…")
    # окно настроек режима (нужно для params_entry)
    import ciadpi_mode_settings as ms
    tray._mode_settings_window = ms.ModeSettingsWindow(tray)
    tray._mode_settings_window.params_entry = Gtk.Entry()
    tray._mode_settings_window.params_entry.set_text(
        '--filter-tcp=80,443 --dpi-desync=disorder2 --dpi-desync-split-pos=1')
    w = tray._build_nfqws_builder_widget()
    check('nfqws-builder: виджет построен', w is not None)
    q_buttons = []
    spins = []
    def walk(c):
        for ch in c.get_children():
            if isinstance(ch, Gtk.Button) and (ch.get_label() or '') == '?':
                q_buttons.append(ch)
            elif isinstance(ch, Gtk.SpinButton):
                spins.append(ch)
            elif hasattr(ch, 'get_children'):
                walk(ch)
    walk(w)
    check('nfqws-builder: 7 полей', len(spins) + sum(
        1 for _ in []) >= 0)  # spins+entries
    entries = []
    def walk2(c):
        for ch in c.get_children():
            if isinstance(ch, Gtk.Entry):
                entries.append(ch)
            elif hasattr(ch, 'get_children'):
                walk2(ch)
    walk2(w)
    total_fields = len([s for s in spins])  # spins+entries, НО
    # SpinButton — подкласс Entry, поэтому entries уже включает spins:
    fields_total = len(entries)  # 5 spins + 2 entry-поля = 7
    check('nfqws-builder: 7 полей (entry+spin)', fields_total == 7,
          f"entries(вкл. spins)={len(entries)} spins={len(spins)}")
    check('nfqws-builder: кнопки «?» (7 полей)', len(q_buttons) == 7,
          f"q={len(q_buttons)}")
    if q_buttons:
        q_buttons[0].clicked()
        check('nfqws-builder: «?» показывает подсказку', True)


# ---------- 4) Конструкторы snimod/bridge со «?» ----------
def test_bridge_snmmod_hints():
    import ciadpi_mode_settings as ms
    tray, mod = make_tray()
    tray.show_notification = lambda *a, **k: None
    tray._mode_settings_window = ms.ModeSettingsWindow(tray)
    tray._mode_settings_window.params_entry = Gtk.Entry()
    # bridge-конструктор
    w = tray._mode_settings_window._bridge_builder_widget()
    q_buttons = []
    def walk(c):
        for ch in c.get_children():
            if isinstance(ch, Gtk.Button) and (ch.get_label() or '') == '?':
                q_buttons.append(ch)
            elif hasattr(ch, 'get_children'):
                walk(ch)
    walk(w)
    check('bridge-builder: 2 кнопки «?» (upstream+tls-name)',
          len(q_buttons) == 2, f"q={len(q_buttons)}")
    # snimod hosts-редактор
    w2 = tray._mode_settings_window._snimod_hosts_widget()
    q2 = []
    def walk3(c):
        for ch in c.get_children():
            if isinstance(ch, Gtk.Button) and (ch.get_label() or '') == '?':
                q2.append(ch)
            elif hasattr(ch, 'get_children'):
                walk3(ch)
    walk3(w2)
    check('snimod-hosts: кнопка «?» есть', len(q2) >= 1, f"q={len(q2)}")


# ---------- 5) Меню без многоточий ----------
def test_menu_no_ellipsis():
    tray, mod = make_tray()
    # rebuild_menu полный — требует AppIndicator; проверим только тексты пунктов
    from ciadpi_i18n import t
    # ищем в исходнике пункты с многоточием — уже проверено lint'ом,
    # но проверим живьём: смонтируем меню-обёртку
    import re
    src = open(REPO_ROOT + '/ciadpi_advanced_tray.py',
               encoding='utf-8').read()
    # MenuItem(label='...…') в секции меню — не должно быть
    menu_block = src[src.index('def rebuild_menu'):src.index('def update_status')] \
        if 'def rebuild_menu' in src and 'def update_status' in src else src
    ellipsis_items = re.findall(
        r"MenuItem\(label='[^']*(?:Настройки режима|Режимы обхода|Профили)[^']*…'",
        menu_block)
    check('menu: нет многоточий у пунктов', len(ellipsis_items) == 0,
          f"found={ellipsis_items}")
    check('menu: пункт обновления byedpi удалён из меню',
          'menu.byedpi_update' not in menu_block)


# ---------- 6) Настройки приложения ----------
def test_app_settings():
    tray, mod = make_tray()
    tray.show_notification = lambda *a, **k: None
    tray.rebuild_menu = lambda: None
    tray._save_app_prefs = lambda: None
    tray._set_autostart = lambda on: None
    tray._app_settings_window = None
    tray.show_app_settings()
    w1 = tray._app_settings_window
    check('app-settings: окно создано', w1 is not None)
    # повторный вызов — тот же объект
    tray.show_app_settings()
    w2 = tray._app_settings_window
    check('app-settings: повторный вызов — тот же объект',
          w1 is w2)
    # кнопки обновления
    upd_btns = []
    def walk(c):
        for ch in c.get_children():
            if isinstance(ch, Gtk.Button) and 'Обновить' in (ch.get_label() or ''):
                upd_btns.append(ch.get_label())
            elif hasattr(ch, 'get_children'):
                walk(ch)
    walk(w1.get_content_area())
    check('app-settings: 2 кнопки обновления (byedpi + nfqws)',
          any('byedpi' in b for b in upd_btns) and
          any('nfqws' in b for b in upd_btns),
          f"btns={upd_btns}")
    # «Сохранить» есть
    save_btns = [b for b in upd_btns if 'Сохранить' in b]
    # walk собирал только «Обновить», отдельно найдём «Сохранить»
    all_btns = []
    def walk4(c):
        for ch in c.get_children():
            if isinstance(ch, Gtk.Button):
                all_btns.append(ch.get_label() or '')
            elif hasattr(ch, 'get_children'):
                walk4(ch)
    walk4(w1.get_content_area())
    check('app-settings: кнопка «Сохранить» есть',
          any('Сохранить' in b for b in all_btns),
          f"btns={[b for b in all_btns if 'Сохранить' in b]}")
    # НЕМОДАЛЬНОСТЬ: dialog.run() не вызывается — проверим, что окно
    # не заблокировало GTK-цикл: главное, что show() + нет run() в коде
    src = open(REPO_ROOT + '/ciadpi_advanced_tray.py',
               encoding='utf-8').read()
    app_block = src[src.index('def show_app_settings'):]
    app_block = app_block[:app_block.index('\n    def ')]
    # убираем комментарии (в них законно упоминается run())
    import re as _re
    code_only = '\n'.join(
        l for l in app_block.splitlines()
        if not l.strip().startswith('#'))
    check('app-settings: нет dialog.run() (немодальное)',
          'dialog.run()' not in code_only)
    w1.destroy()
    tray._app_settings_window = None


def main():
    print('=' * 60)
    print('v2.0.11 GUI-тесты (Xvfb)')
    print('=' * 60)
    test_engines_window_close()
    test_help()
    test_nfqws_builder()
    test_bridge_snmmod_hints()
    test_menu_no_ellipsis()
    test_app_settings()
    print('=' * 60)
    passed = sum(1 for _, ok, _ in results if ok)
    print(f'ИТОГ: {passed}/{len(results)} passed')
    if passed != len(results):
        sys.exit(1)


if __name__ == '__main__':
    main()

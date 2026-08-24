#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
CIADPI Indicator — локализация RU/EN.

Использование:
    from ciadpi_i18n import t, set_lang, get_lang
    t('menu.settings')            -> строка на текущем языке
    set_lang('en'); save_lang()   -> переключить и сохранить выбор
"""

import json
from pathlib import Path

_CONFIG_DIR = Path.home() / '.config' / 'ciadpi'
_LANG_FILE = _CONFIG_DIR / 'ui_language'

_STRINGS = {
    # ---- Меню трея ----
    'menu.status':        {'ru': '🔄 Проверка статуса...', 'en': '🔄 Checking status...'},
    'menu.start':         {'ru': '▶️ Запустить сервис', 'en': '▶️ Start service'},
    'menu.stop':          {'ru': '⏹️ Остановить сервис', 'en': '⏹️ Stop service'},
    'menu.restart':       {'ru': '🔄 Перезапустить сервис', 'en': '🔄 Restart service'},
    'menu.settings':      {'ru': '⚙️ Настройки параметров', 'en': '⚙️ Parameter settings'},
    'menu.builder':       {'ru': '🎛️ Конструктор параметров', 'en': '🎛️ Parameter builder'},
    'menu.proxy':         {'ru': '🔌 Настройки прокси', 'en': '🔌 Proxy settings'},
    'menu.whitelist':     {'ru': '📝 Белый список', 'en': '📝 Whitelist'},
    'menu.autosearch':    {'ru': '🔍 Автопоиск параметров', 'en': '🔍 Auto-search parameters'},
    'menu.history':       {'ru': '📊 История тестирования', 'en': '📊 Test history'},
    'menu.strategy':      {'ru': '🧪 Поиск стратегии (перебор параметров)', 'en': '🧪 Strategy search (brute force)'},
    'menu.byedpi_update': {'ru': '⬆️ Обновить byedpi', 'en': '⬆️ Update byedpi'},
    'menu.privileges':    {'ru': '🔑 Права доступа (убрать запрос пароля)', 'en': '🔑 Privileges (disable password prompts)'},
    'menu.app_settings':  {'ru': '🛠️ Настройки приложения', 'en': '🛠️ Application settings'},
    'menu.logs':          {'ru': '📋 Показать логи', 'en': '📋 Show logs'},
    'menu.help':          {'ru': '❓ Справка по параметрам', 'en': '❓ Parameter reference'},
    'menu.about':         {'ru': 'ℹ️ О программе', 'en': 'ℹ️ About'},
    'menu.exit':          {'ru': '🚪 Выход', 'en': '🚪 Exit'},

    # ---- Статус ----
    'status.running':     {'ru': 'Запущен', 'en': 'Running'},
    'status.stopped':     {'ru': 'Остановлен', 'en': 'Stopped'},
    'status.running_s':   {'ru': '✅ CIADPI Запущен', 'en': '✅ CIADPI Running'},
    'status.stopped_s':   {'ru': '❌ CIADPI Остановлен', 'en': '❌ CIADPI Stopped'},
    'status.error':       {'ru': '⚠️ Ошибка проверки статуса', 'en': '⚠️ Status check error'},

    # ---- Уведомления ----
    'notif.success':      {'ru': 'Успех', 'en': 'Success'},
    'notif.error':        {'ru': 'Ошибка', 'en': 'Error'},
    'notif.warning':      {'ru': 'Внимание', 'en': 'Warning'},
    'notif.params_updated':   {'ru': 'Параметры обновлены и сервис запущен', 'en': 'Parameters updated, service running'},
    'notif.restarting':   {'ru': 'Перезапуск сервиса, подождите', 'en': 'Restarting service, please wait'},
    'notif.restart_title': {'ru': 'Перезапуск...', 'en': 'Restarting...'},
    'notif.params_saved': {'ru': 'Параметры сохранены в конфиг до перезапуска сервиса',
                           'en': 'Parameters saved to config before service restart'},
    'notif.service_started':  {'ru': 'Сервис запущен успешно', 'en': 'Service started successfully'},
    'notif.service_stopped':  {'ru': 'Сервис остановлен', 'en': 'Service stopped'},
    'notif.proxy_applied':    {'ru': 'Прокси применен', 'en': 'Proxy applied'},
    'notif.copied':       {'ru': 'Скопировано:', 'en': 'Copied:'},
    'notif.best_applied': {'ru': 'Лучшие параметры применены к сервису', 'en': 'Best parameters applied to service'},
    'notif.updating_byedpi':  {'ru': 'Обновление byedpi...', 'en': 'Updating byedpi...'},
    'notif.setup_privileges': {'ru': 'Настройте беспарольный доступ: меню → 🔑 Права доступа',
                               'en': 'Set up passwordless access: menu → 🔑 Privileges'},

    # ---- Диалог настроек приложения ----
    'app.title':          {'ru': 'Настройки приложения CIADPI', 'en': 'CIADPI Application Settings'},
    'app.lang':           {'ru': 'Язык интерфейса:', 'en': 'Interface language:'},
    'app.lang_ru':        {'ru': 'Русский', 'en': 'Russian'},
    'app.lang_en':        {'ru': 'Английский', 'en': 'English'},
    'app.lang_hint':      {'ru': 'Применится после перезапуска индикатора',
                           'en': 'Applied after indicator restart'},
    'app.notif_group':    {'ru': 'Уведомления', 'en': 'Notifications'},
    'app.notif_enable':   {'ru': 'Показывать уведомления', 'en': 'Show notifications'},
    'app.notif_service':  {'ru': 'Статус сервиса (запуск/остановка)', 'en': 'Service status (start/stop)'},
    'app.notif_params':   {'ru': 'Изменение параметров', 'en': 'Parameter changes'},
    'app.notif_proxy':    {'ru': 'Применение прокси', 'en': 'Proxy changes'},
    'app.autostart_group': {'ru': 'Автозапуск', 'en': 'Autostart'},
    'app.autostart_indicator': {'ru': 'Индикатор при входе в систему', 'en': 'Indicator at login'},
    'app.autostart_hint': {'ru': 'Отключите, если не хотите автостарт индикатора с системой',
                           'en': "Disable if you don't want the indicator to start with the system"},
    'app.saved':          {'ru': 'Настройки сохранены', 'en': 'Settings saved'},

    # ---- Конструктор параметров ----
    'builder.title':      {'ru': 'Конструктор параметров CIADPI', 'en': 'CIADPI Parameter Builder'},
    'builder.current':    {'ru': 'Текущая строка параметров:', 'en': 'Current parameter string:'},
    'builder.hint_line':  {'ru': 'Наведите на регулятор для подсказки; «?» открывает полную справку',
                           'en': "Hover a control for a hint; '?' opens the full reference"},
    'builder.apply':      {'ru': '✅ Применить к сервису', 'en': '✅ Apply to service'},
    'builder.refresh':    {'ru': '↻ Из строки', 'en': '↻ From string'},
    'builder.help_btn':   {'ru': '❓ Полная справка', 'en': '❓ Full reference'},

    'builder.group_main':  {'ru': 'Основные', 'en': 'Main'},
    'builder.group_desync': {'ru': 'Методы обхода (desync)', 'en': 'Desync methods'},
    'builder.group_auto':  {'ru': 'Автоматический режим', 'en': 'Automatic mode'},
    'builder.group_filters': {'ru': 'Фильтры', 'en': 'Filters'},
    'builder.group_fake':  {'ru': 'Fake-пакеты и модификации', 'en': 'Fake packets & modifications'},

    'builder.port':    {'ru': 'Порт прослушивания (-p)', 'en': 'Listen port (-p)'},
    'builder.port_h':  {'ru': 'Порт локального прокси. Должен совпадать с портом в настройках прокси.',
                        'en': 'Local proxy port. Must match the port in proxy settings.'},
    'builder.maxconn': {'ru': 'Макс. соединений (-c)', 'en': 'Max connections (-c)'},
    'builder.maxconn_h': {'ru': 'Лимит одновременных соединений.', 'en': 'Concurrent connection limit.'},
    'builder.bufsize': {'ru': 'Размер буфера (-b)', 'en': 'Buffer size (-b)'},
    'builder.bufsize_h': {'ru': 'Буфер сокета в байтах.', 'en': 'Socket buffer size in bytes.'},
    'builder.debug':   {'ru': 'Уровень отладки (-x)', 'en': 'Debug level (-x)'},
    'builder.debug_h': {'ru': '0 — выключено, 1 — базовые логи, 2 — подробные.',
                        'en': '0 - off, 1 - basic logs, 2 - verbose.'},

    'builder.split':    {'ru': 'Split позиция (-s)', 'en': 'Split position (-s)'},
    'builder.split_h':  {'ru': 'Разделение пакета на позиции. Формат: смещение[:повторы:шаг]+флаги (+s SNI, +h HTTP host). Пусто = не использовать.',
                         'en': 'Packet split at position. Format: offset[:repeats:step]+flags (+s SNI, +h HTTP host). Empty = disabled.'},
    'builder.disorder': {'ru': 'Disorder позиция (-d)', 'en': 'Disorder position (-d)'},
    'builder.disorder_h': {'ru': 'Отправка частей пакета в обратном порядке.',
                           'en': 'Send packet parts in reverse order.'},
    'builder.oob':      {'ru': 'OOB позиция (-o)', 'en': 'OOB position (-o)'},
    'builder.oob_h':    {'ru': 'Разделение и отправка как out-of-band данные.',
                         'en': 'Split and send as out-of-band data.'},
    'builder.oob_n':    {'ru': 'Номер метода обхода (-oN)', 'en': 'Desync method number (-oN)'},
    'builder.oob_n_h':  {'ru': 'Числовой метод обхода 1–25 (например -o1, -o25+s). Можно несколько через пробел.',
                         'en': 'Numeric desync method 1-25 (e.g. -o1, -o25+s). Several allowed, space-separated.'},
    'builder.disoob':   {'ru': 'Dis-OOB позиция (-q)', 'en': 'Dis-OOB position (-q)'},
    'builder.disoob_h': {'ru': 'Обратный порядок + OOB.',
                         'en': 'Reverse order + OOB.'},
    'builder.fake':     {'ru': 'Fake позиция (-f)', 'en': 'Fake position (-f)'},
    'builder.fake_h':   {'ru': 'Отправка поддельного пакета перед настоящим.',
                         'en': 'Send a fake packet before the real one.'},

    'builder.timeout':  {'ru': 'Таймаут авто-режима (-T), сек', 'en': 'Auto-mode timeout (-T), sec'},
    'builder.timeout_h': {'ru': 'Ждать ответа N секунд, затем применить auto-стратегию. 0 = выключено.',
                          'en': 'Wait N seconds for a response, then apply auto strategy. 0 = off.'},
    'builder.auto':     {'ru': 'Auto-триггер (-A)', 'en': 'Auto trigger (-A)'},
    'builder.auto_h':   {'ru': 'Когда применять обход: torst (обрыв), ssl_err (ошибка TLS), redirect, conn, none. Пробел = нет.',
                         'en': 'When to apply desync: torst (reset), ssl_err, redirect, conn, none. Blank = none.'},
    'builder.automode': {'ru': 'Auto-режим (-L)', 'en': 'Auto mode (-L)'},
    'builder.automode_h': {'ru': '0..3 — поведение после срабатывания триггера. Пусто = по умолчанию.',
                           'en': '0..3 - behaviour after trigger fires. Blank = default.'},
    'builder.cachettl': {'ru': 'Кэш TTL (-u), сек', 'en': 'Cache TTL (-u), sec'},
    'builder.cachettl_h': {'ru': 'Сколько хранить подобранные параметры для IP. 0 = выключено.',
                           'en': 'How long to keep per-IP desync params. 0 = off.'},

    'builder.proto':    {'ru': 'Протоколы (-K)', 'en': 'Protocols (-K)'},
    'builder.proto_h':  {'ru': 'Белый список протоколов: t=tls, h=http, u=udp, i=ipv4. Примеры: t; t,h; пусто = все.',
                         'en': 'Protocol whitelist: t=tls, h=http, u=udp, i=ipv4. E.g.: t; t,h; blank = all.'},
    'builder.pf':       {'ru': 'Диапазон портов (-V)', 'en': 'Port range (-V)'},
    'builder.pf_h':     {'ru': 'Применять обход только к этим портам, например 80-443. Пусто = все.',
                         'en': 'Apply desync only to these ports, e.g. 80-443. Blank = all.'},
    'builder.round':    {'ru': 'Round (-R)', 'en': 'Round (-R)'},
    'builder.round_h':  {'ru': 'К какому по счёту запросу применять обход, например 1 или 1-3. Пусто = всегда.',
                         'en': 'Which request number gets desync, e.g. 1 or 1-3. Blank = always.'},

    'builder.ttl':      {'ru': 'TTL fake-пакетов (-t)', 'en': 'Fake packet TTL (-t)'},
    'builder.ttl_h':    {'ru': 'TTL поддельных пакетов (обычно меньше реального TTL, чтобы пакет «умер» у провайдера).',
                         'en': "TTL of fake packets (usually below real TTL so it dies at the ISP)."},
    'builder.tlsrec':   {'ru': 'TLS record позиция (-r)', 'en': 'TLS record position (-r)'},
    'builder.tlsrec_h': {'ru': 'Разбиение TLS record. Спецформа «o--tlsrec N» добавляется вручную в строке.',
                         'en': 'TLS record splitting. The special form "o--tlsrec N" can be typed in the string manually.'},
    'builder.udpfake':  {'ru': 'UDP fake-пакеты (-a)', 'en': 'UDP fakes (-a)'},
    'builder.udpfake_h': {'ru': 'Количество UDP-fake на каждый запрос. 0 = выключено.',
                          'en': 'UDP fake count per request. 0 = off.'},
    'builder.md5sig':   {'ru': 'MD5 сигнатура (-S)', 'en': 'MD5 signature (-S)'},
    'builder.md5sig_h': {'ru': 'Добавлять опцию MD5 Signature к fake-пакетам.',
                         'en': 'Add MD5 Signature option to fake packets.'},
    'builder.dropsack': {'ru': 'Drop SACK (-Y)', 'en': 'Drop SACK (-Y)'},
    'builder.dropsack_h': {'ru': 'Отбрасывать пакеты с расширением SACK.',
                           'en': 'Drop packets carrying the SACK extension.'},
    'builder.modhttp':  {'ru': 'Модификация HTTP (-M)', 'en': 'HTTP modification (-M)'},
    'builder.modhttp_h': {'ru': 'h=hcsmix, d=dcsmix, r=rmspace; можно вместе: h,d',
                          'en': 'h=hcsmix, d=dcsmix, r=rmspace; combinable: h,d'},
    'builder.fakemod':  {'ru': 'Модификация fake TLS (-Q)', 'en': 'Fake TLS modification (-Q)'},
    'builder.fakemod_h': {'ru': 'rand (случайные поля), orig, msize=N. Пусто = без изменений.',
                          'en': 'rand (randomize fields), orig, msize=N. Blank = untouched.'},

    # ---- Прокси ----
    'proxy.title':        {'ru': 'Настройки прокси', 'en': 'Proxy settings'},
    'proxy.mode':         {'ru': 'Режим прокси:', 'en': 'Proxy mode:'},
    'proxy.mode_pac':     {'ru': 'Автоматический (PAC)', 'en': 'Automatic (PAC)'},
    'proxy.mode_manual':  {'ru': 'Ручной', 'en': 'Manual'},
    'proxy.mode_off':     {'ru': 'Выключен', 'en': 'Disabled'},
    'proxy.mode_local':   {'ru': 'Локальный (не трогать системные настройки)', 'en': 'Local (do not touch system settings)'},
    'proxy.manual_frame': {'ru': 'Ручные настройки прокси', 'en': 'Manual proxy settings'},
    'proxy.host':         {'ru': 'Хост прокси (оставьте ПУСТЫМ для использования только порта):',
                           'en': 'Proxy host (leave EMPTY for port-only):'},
    'proxy.host_ph':      {'ru': 'ПУСТОЕ значение - только порт', 'en': 'EMPTY value - port only'},
    'proxy.port':         {'ru': 'Порт прокси:', 'en': 'Proxy port:'},
    'proxy.local_hint':   {'ru': 'Системные настройки не изменяются.\nНастройте нужные приложения вручную на этот порт\n(например Firefox → свой прокси 127.0.0.1:1080).',
                           'en': 'System settings stay untouched.\nPoint specific apps at this port manually\n(e.g. Firefox → its own proxy 127.0.0.1:1080).'},
    'proxy.note_all':     {'ru': 'Настройки применяются ко всем приложениям', 'en': 'Settings apply to all applications'},
    'proxy.auto_disable': {'ru': '❌ Автоматически отключать прокси при выходе',
                           'en': '❌ Automatically disable proxy on exit'},
    'proxy.auto_disable_h': {'ru': 'При остановке сервиса прокси будет автоматически отключен в системе',
                             'en': 'Proxy will be disabled system-wide when the service stops'},
}

_current = None


def _load_choice():
    global _current
    if _current is not None:
        return _current
    try:
        _current = _LANG_FILE.read_text().strip()
    except Exception:
        pass
    if _current not in ('ru', 'en'):
        _current = 'ru'
    return _current


def get_lang():
    return _load_choice()


def set_lang(lang):
    """Переключение языка (без сохранения)."""
    global _current
    if lang in ('ru', 'en'):
        _current = lang


def save_lang():
    """Сохранение выбора языка."""
    try:
        _CONFIG_DIR.mkdir(exist_ok=True)
        _LANG_FILE.write_text(get_lang())
    except Exception as e:
        print(f"⚠️ Не удалось сохранить язык: {e}")


def t(key):
    """Перевод по ключу; при отсутствии ключа возвращаем сам ключ."""
    lang = _load_choice()
    entry = _STRINGS.get(key)
    if entry is None:
        return key
    return entry.get(lang) or entry.get('ru') or key


def tr(key_ru):
    """Обратная совместимость: перевод по русской фразе."""
    lang = _load_choice()
    if lang == 'ru':
        return key_ru
    for entry in _STRINGS.values():
        if entry.get('ru') == key_ru:
            return entry.get('en', key_ru)
    return key_ru

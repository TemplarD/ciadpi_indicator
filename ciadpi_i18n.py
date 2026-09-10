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
    'status.running_nfqws': {'ru': 'nfqws запущен (перехват пакетов активен)', 'en': 'nfqws running (packet interception active)'},
    'status.running_s_nfqws': {'ru': '✅ nfqws Запущен', 'en': '✅ nfqws Running'},
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
    'app.lang_hint':      {'ru': 'Меню переключается сразу, без перезапуска',
                           'en': 'The menu switches instantly, no restart needed'},
    'app.lang_now':       {'ru': 'Меню и диалоги уже на новом языке',
                           'en': 'The menu and dialogs are already in the new language'},
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
    'wl.title':           {'ru': 'Управление белым списком', 'en': 'Whitelist management'},
    'wl.enable':          {'ru': 'Включить белый список', 'en': 'Enable whitelist'},
    'wl.exceptions':      {'ru': 'Исключения из проксирования', 'en': 'Proxy exceptions'},
    'wl.bypass_proxy':    {'ru': 'Исключить из проксирования', 'en': 'Exclude from proxying'},
    'wl.bypass_dpi':      {'ru': 'Исключить из DPI обхода', 'en': 'Exclude from DPI bypass'},
    'wl.domains':         {'ru': 'Домены и хосты (по одному на строку)', 'en': 'Domains and hosts (one per line)'},
    'wl.ips':             {'ru': 'IP-адреса и сети CIDR (по одному на строку)', 'en': 'IP addresses and CIDR networks (one per line)'},
    'wl.saved':           {'ru': 'Настройки сохранены', 'en': 'Settings saved'},
    'wl.save_fail':       {'ru': 'Не удалось сохранить белый список', 'en': 'Failed to save the whitelist'},
    'priv.title':         {'ru': 'Права доступа CIADPI', 'en': 'CIADPI access rights'},
    'priv.apply':         {'ru': '🔑 Настроить (запросит пароль один раз)', 'en': '🔑 Set up (password prompt once)'},
    'priv.copy':          {'ru': '📋 Скопировать команду для терминала', 'en': '📋 Copy the terminal command'},
    'priv.running':       {'ru': 'Выполняется настройка... (смотрите запрос пароля)', 'en': 'Setting up... (watch for the password prompt)'},
    'priv.done':          {'ru': '✅ Готово! Пароль больше не потребуется.', 'en': '✅ Done! No password needed anymore.'},
    'priv.done_notif':    {'ru': 'Готово', 'en': 'Done'},
    'priv.done_notif_2':  {'ru': 'Беспарольное управление настроено', 'en': 'Passwordless management configured'},
    'priv.copy_notif':    {'ru': 'Скопировано', 'en': 'Copied'},
    'priv.copy_notif_2':  {'ru': 'Команда вставлена в буфер обмена', 'en': 'The command is in the clipboard'},
    'quick.status_title': {'ru': 'Статус CIADPI', 'en': 'CIADPI status'},
    'quick.running':      {'ru': '🟢 Запущен', 'en': '🟢 Running'},
    'quick.stopped':      {'ru': '🔴 Остановлен', 'en': '🔴 Stopped'},
    'quick.err':          {'ru': 'Не удалось проверить статус', 'en': 'Failed to check the status'},
    'search.title':       {'ru': 'Поиск стратегии — перебор параметров', 'en': 'Strategy search — brute force'},
    'search.engine_label': {'ru': 'Движок:', 'en': 'Engine:'},
    'search.engine_byedpi': {'ru': 'byedpi (тестовый SOCKS-порт)', 'en': 'byedpi (test SOCKS port)'},
    'search.engine_nfqws': {'ru': 'nfqws (через реальный сервис, все приложения)', 'en': 'nfqws (via real service, all apps)'},
    'search.engine_hint':  {'ru': 'byedpi: тестируется на отдельном порту, интернет не прерывается. nfqws: каждая комбинация включается на реальном сервисе (интернет «мигает» на секунды между тестами); успех = все URL отвечают',
                            'en': 'byedpi: tested on a separate port, no internet interruption. nfqws: each combo runs on the real service (internet blinks for seconds between tests); success = all URLs respond'},
    'search.settings':    {'ru': 'Настройка проверки', 'en': 'Check settings'},
    'search.max_combos':  {'ru': 'Макс. комбинаций:', 'en': 'Max combos:'},
    'search.test_port':   {'ru': 'Тестовый порт:', 'en': 'Test port:'},
    'search.urls_label':  {'ru': 'URL для проверки:', 'en': 'URLs to check:'},
    'search.ready':       {'ru': 'Готов к поиску', 'en': 'Ready to search'},
    'search.start':       {'ru': '▶️ Запустить поиск', 'en': '▶️ Start search'},
    'search.stop':        {'ru': '⏹ Остановить', 'en': '⏹ Stop'},
    'search.apply_best':  {'ru': '✅ Применить лучшие параметры', 'en': '✅ Apply best parameters'},
    'search.log_frame':   {'ru': 'Ход поиска (куда подключаемся и что тестируем)', 'en': 'Search progress (connections and tests)'},
    'search.urls_hint':   {'ru': 'URL-адреса через пробел; доступ проверяется через тестовый прокси',
                           'en': 'URLs space-separated; access checked via the test proxy'},
    'search.start_log':   {'ru': 'Старт', 'en': 'Start'},
    'search.combos':      {'ru': 'комбинаций, тестовый порт', 'en': 'combos, test port'},
    'search.via':         {'ru': 'подключение через', 'en': 'connecting via'},
    'search.test':        {'ru': 'Тест', 'en': 'Test'},
    'search.ok_urls':     {'ru': 'УСПЕХ', 'en': 'SUCCESS'},
    'search.avg_speed':   {'ru': 'средняя скорость', 'en': 'avg speed'},
    'search.fail':        {'ru': 'неудача', 'en': 'failed'},
    'search.best_found':  {'ru': '🏆 Лучшие параметры', 'en': '🏆 Best parameters'},
    'search.speed':       {'ru': 'Скорость', 'en': 'Speed'},
    'search.urls_avail':  {'ru': 'доступно URL', 'en': 'URLs reachable'},
    'search.none_found':  {'ru': 'Рабочие параметры не найдены. Попробуйте другие URL или увеличьте число комбинаций.',
                           'en': 'No working parameters found. Try other URLs or more combos.'},
    'search.finished':    {'ru': 'Поиск завершён', 'en': 'Search finished'},
    'search.apply_run':   {'ru': 'Применение...', 'en': 'Applying...'},
    'search.apply_run_2': {'ru': 'Обновление параметров сервиса', 'en': 'Updating service parameters'},
    'search.applied':     {'ru': 'Параметры применены', 'en': 'Parameters applied'},
    'search.apply_fail':  {'ru': 'Не удалось применить параметры', 'en': 'Failed to apply parameters'},
    'search.need_urls':   {'ru': '⚠️ Укажите хотя бы один URL для проверки', 'en': '⚠️ Provide at least one URL to check'},
    'search.stop_req':    {'ru': '⏹ Остановка запрошена...', 'en': '⏹ Stop requested...'},
    'search.url_hint':    {'ru': 'URL-адреса через пробел; доступ проверяется через тестовый прокси', 'en': 'URLs space-separated; access checked via the test proxy'},
    'search.until_found': {'ru': 'Искать до нахождения (без лимита попыток)', 'en': 'Search until found (no attempt limit)'},
    'search.until_found_hint': {'ru': 'Перебор идёт, пока не найдётся рабочая стратегия. Остановить можно кнопкой или закрытием окна.',
                           'en': 'Keeps trying until a working strategy is found. Stop via the button or by closing the window.'},
    'search.min_tests':   {'ru': 'Мин. попыток до стопа по успеху:', 'en': 'Min attempts before success stops:'},
    'search.unlimited_mode': {'ru': 'режим «до нахождения», лимита нет', 'en': 'until-found mode, no limit'},
    'search.partial':     {'ru': 'частичный доступ (успехом считается ТОЛЬКО все URL — поиск продолжается)', 'en': 'partial access (success requires ALL URLs — search continues)'},
    'engine.menu':        {'ru': 'Движок обхода', 'en': 'Bypass engine'},
    'engine.byedpi':      {'ru': 'byedpi (SOCKS-прокси)', 'en': 'byedpi (SOCKS proxy)'},
    'engine.nfqws':       {'ru': 'nfqws (NFQUEUE, все приложения)', 'en': 'nfqws (NFQUEUE, all apps)'},
    'engine.byedpi_short': {'ru': 'byedpi', 'en': 'byedpi'},
    'engine.nfqws_short': {'ru': 'nfqws', 'en': 'nfqws'},
    'engine.nfqws_on':    {'ru': 'Движок nfqws (галочка = NFQUEUE для всех приложений)',
                           'en': 'nfqws engine (checked = NFQUEUE for all apps)'},
    'engine.switch_hint': {'ru': 'Галочка = nfqws (перехват пакетов всех приложений); снимите — вернётесь на byedpi (SOCKS-прокси). Выбор движка НЕ зависит от того, запущен ли сервис.',
                           'en': 'Checked = nfqws (packet interception for all apps); unchecked = byedpi (SOCKS proxy). The engine choice does not depend on whether the service is running.'},
    'engine.byedpi_only': {'ru': 'Доступно только с движком byedpi (переключите движок)', 'en': 'Available only with the byedpi engine (switch the engine)'},
    'engine.nfqws_no_proxy': {'ru': 'nfqws не использует системный прокси — приложениям он не нужен', 'en': 'nfqws does not use a system proxy — apps do not need one'},
    'engine.hint_state':  {'ru': 'Выбран: {st}', 'en': 'Selected: {st}'},
    'engine.hint_service': {'ru': 'Сервис: {st}', 'en': 'Service: {st}'},
    'engine.now':         {'ru': 'Движок переключён: {name}', 'en': 'Engine switched: {name}'},
    'engine.nfqws_unavailable': {'ru': 'Модуль nfqws недоступен', 'en': 'nfqws module unavailable'},
    'engine.nfqws_not_installed': {'ru': 'nfqws не найден: клонируйте zapret в ~/zapret и соберите (nfq/make)', 'en': 'nfqws not found: clone zapret to ~/zapret and build (nfq/make)'},
    'engine.rules_not_applied': {'ru': 'nft-правила не применились (нет прав? настройте «Права доступа»)', 'en': 'nft rules not applied (no permission? set up "Privileges")'},
    'engine.nfqws_title': {'ru': 'nfqws — параметры движка (формат zapret)', 'en': 'nfqws — engine parameters (zapret format)'},
    'engine.nfqws_params': {'ru': 'Параметры nfqws:', 'en': 'nfqws parameters:'},
    'engine.nfqws_hint':  {'ru': 'Формат zapret (НЕ byedpi!): --filter-tcp=80,443 --dpi-desync=disorder2 … Изменения применяются при следующем запуске nfqws; активный сервис перезапускается автоматически.',
                           'en': 'zapret format (NOT byedpi!): --filter-tcp=80,443 --dpi-desync=disorder2 … Applied on next nfqws start; a running service restarts automatically.'},
    'engine.nfqws_params_menu': {'ru': 'Параметры nfqws…', 'en': 'nfqws parameters…'},
    'auto.title':         {'ru': 'Автопоиск параметров', 'en': 'Auto-search parameters'},
    'auto.n_tests':       {'ru': 'Количество тестов:', 'en': 'Number of tests:'},
    'auto.launch':        {'ru': 'Запуск', 'en': 'Launch'},
    'hist.title':         {'ru': 'История тестирования', 'en': 'Test history'},
    'hist.header':        {'ru': 'История тестирования:', 'en': 'Test history:'},
    'exit.title':         {'ru': 'Выход', 'en': 'Exit'},
    'exit.restored':      {'ru': 'Системные настройки прокси восстановлены', 'en': 'System proxy settings restored'},

    # ---- Конструктор параметров ----
    'builder.title':      {'ru': 'Конструктор параметров CIADPI', 'en': 'CIADPI Parameter Builder'},
    'builder.current':    {'ru': 'Текущая строка параметров:', 'en': 'Current parameter string:'},
    'builder.hint_line':  {'ru': 'Каждое поле правит только свой параметр — остальная строка не меняется. «?» — подробная подсказка.',
                           'en': 'Each field edits only its own parameter — the rest of the string stays intact. "?" shows a detailed hint.'},
    'builder.tip_title':  {'ru': 'Подсказка по параметру', 'en': 'Parameter hint'},
    'builder.q_tooltip':  {'ru': 'Подробная подсказка по этому параметру', 'en': 'Detailed hint for this parameter'},
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
    'builder.port_q':  {'ru': 'Порт, на котором ciadpi принимает SOCKS4/5-подключения.\n'
                        'Firefox/система подключаются к 127.0.0.1:этот_порт.\n\n'
                        '⚠️ Прокси SOCKS, а НЕ HTTP — приложениям нужен\n'
                        'SOCKS5 (в Firefox: «Ручная настройка» → SOCKS-хост).\n\n'
                        'По умолчанию 1080. Должен совпадать с портом,\n'
                        'указанным в настройках прокси индикатора — иначе\n'
                        'система будет стучаться в закрытую дверь.',
                        'en': 'Port where ciadpi accepts SOCKS4/5 connections.\n'
                        'Firefox/the system connect to 127.0.0.1:this_port.\n\n'
                        '⚠️ This is a SOCKS proxy, NOT HTTP — apps need\n'
                        'SOCKS5 (in Firefox: Manual setup → SOCKS host).\n\n'
                        'Default 1080. Must match the port in the proxy\n'
                        'settings of the indicator — otherwise the system\n'
                        'knocks on a closed door.'},
    'builder.maxconn': {'ru': 'Макс. соединений (-c)', 'en': 'Max connections (-c)'},
    'builder.maxconn_h': {'ru': 'Лимит одновременных соединений.', 'en': 'Concurrent connection limit.'},
    'builder.maxconn_q': {'ru': 'Максимальное число ОДНОВРЕМЕННО ОТКРЫТЫХ соединений.\n'
                        'По умолчанию 512 — хватает с запасом.\n\n'
                        'Больше нужно только если через прокси ходит весь\n'
                        'браузер с десятками вкладок и загрузками.\n'
                        'Каждое соединение ≈ несколько КБ памяти.',
                        'en': 'Maximum number of SIMULTANEOUSLY OPEN connections.\n'
                        'Default 512 is plenty.\n\n'
                        'Only raise it if a whole browser with dozens of\n'
                        'tabs goes through the proxy.\n'
                        'Each connection ≈ a few KB of memory.'},
    'builder.bufsize': {'ru': 'Размер буфера (-b)', 'en': 'Buffer size (-b)'},
    'builder.bufsize_h': {'ru': 'Буфер сокета в байтах.', 'en': 'Socket buffer size in bytes.'},
    'builder.bufsize_q': {'ru': 'Размер буфера для обмена данными одного соединения.\n'
                        'По умолчанию 16384 байта (16 КБ) — оптимально.\n\n'
                        'Увеличение (32768, 65536) может ускорить передачу\n'
                        'больших файлов, но ест память × число соединений.\n'
                        'Трогать без необходимости не стоит.',
                        'en': 'Buffer size for one connection data exchange.\n'
                        'Default 16384 bytes (16 KB) is optimal.\n\n'
                        'Raising it (32768, 65536) may speed up large\n'
                        'transfers but costs memory × connection count.\n'
                        'No need to touch it.'},
    'builder.debug':   {'ru': 'Уровень отладки (-x)', 'en': 'Debug level (-x)'},
    'builder.debug_h': {'ru': '0 — выключено, 1 — базовые логи, 2 — подробные.',
                        'en': '0 - off, 1 - basic logs, 2 - verbose.'},
    'builder.debug_q': {'ru': 'Подробность логов сервиса (journalctl -u ciadpi):\n'
                        '• 0 — молчать (по умолчанию)\n'
                        '• 1 — базовые события: соединения, хосты, split-ы\n'
                        '• 2 — максимально подробно: каждый пакет\n\n'
                        'Уровень 2 помогает понять, что именно DPI делает\n'
                        'с конкретным сайтом, но сильно мусорит в журнал.\n'
                        'Включайте временно, при отладке.',
                        'en': 'Service log verbosity (journalctl -u ciadpi):\n'
                        '• 0 — silent (default)\n'
                        '• 1 — basic events: connections, hosts, splits\n'
                        '• 2 — very verbose: every packet\n\n'
                        'Level 2 helps to see what the DPI does to a given\n'
                        'site but floods the journal. Enable temporarily,\n'
                        'for debugging.'},

    'builder.split':    {'ru': 'Split позиция (-s)', 'en': 'Split position (-s)'},
    'builder.split_h':  {'ru': 'Разделение пакета на позиции. Формат: смещение[:повторы:шаг]+флаги. Пусто = не использовать.',
                         'en': 'Packet split at position. Format: offset[:repeats:step]+flags. Empty = disabled.'},
    'builder.split_q':  {'ru': 'SPLIT — разрезает TCP-пакет на части в заданной позиции.\n\n'
                         'Формат позиции: смещение[:повторы[:шаг]]+флаги\n'
                         '• смещение — байт, на котором разрезать пакет\n'
                         '• повторы — сколько раз повторить разрез (1–100)\n'
                         '• шаг — на сколько байт сдвигать каждый следующий разрез\n'
                         '• флаги: +s — считать от SNI (имени сайта в TLS),\n'
                         '  +h — от HTTP-заголовка Host, +n — вставить нуль-байт;\n'
                         '  вторым флагом: +e — от конца, +m — середина, +r — случайно\n\n'
                         'Примеры: 1 (разрез на 1-м байте), 3+s (на 3-м байте SNI),\n'
                         '3:2:2+h (два разреза с шагом 2 от Host).\n\n'
                         'Можно указать несколько позиций через пробел — каждая\n'
                         'станет отдельным -s в строке. DPI не успевает собрать\n'
                         'пакет и пропускает его мимо анализа.',
                         'en': 'SPLIT — cuts the TCP packet into parts at a given position.\n\n'
                         'Position format: offset[:repeats[:step]]+flags\n'
                         '• offset — byte at which to cut the packet\n'
                         '• repeats — how many cuts to make (1–100)\n'
                         '• step — shift each subsequent cut by N bytes\n'
                         '• flags: +s — count from SNI (site name in TLS),\n'
                         '  +h — from HTTP Host header, +n — insert a null byte;\n'
                         '  second flag: +e — from end, +m — middle, +r — random\n\n'
                         'Examples: 1 (cut at byte 1), 3+s (3rd byte of SNI),\n'
                         '3:2:2+h (two cuts, step 2, from Host).\n\n'
                         'Several positions space-separated — each becomes its\n'
                         'own -s in the string. The DPI cannot reassemble the\n'
                         'packet in time and lets it through.'},
    'builder.disorder': {'ru': 'Disorder позиция (-d)', 'en': 'Disorder position (-d)'},
    'builder.disorder_h': {'ru': 'Отправка частей пакета в обратном порядке.',
                           'en': 'Send packet parts in reverse order.'},
    'builder.disorder_q': {'ru': 'DISORDER — как split, но части пакета отправляются\n'
                           'в ОБРАТНОМ порядке. Тот же формат позиций\n'
                           '(смещение[:повторы:шаг]+флаги), те же флаги.\n\n'
                           'Провайдерский DPI получает «хвост раньше головы» и\n'
                           'не может корректно разобрать TLS-заголовок.\n\n'
                           'Пример: 2+h — разрез по Host, части наоборот.\n'
                           'Несколько позиций — через пробел.',
                           'en': 'DISORDER — like split, but packet parts are sent in\n'
                           'REVERSE order. Same position format\n'
                           '(offset[:repeats:step]+flags), same flags.\n\n'
                           'The DPI receives "tail before head" and cannot\n'
                           'parse the TLS header correctly.\n\n'
                           'Example: 2+h — cut at Host, parts reversed.\n'
                           'Multiple positions — space-separated.'},
    'builder.oob':      {'ru': 'OOB позиция (-o)', 'en': 'OOB position (-o)'},
    'builder.oob_h':    {'ru': 'Разделение и отправка как out-of-band данные.',
                         'en': 'Split and send as out-of-band data.'},
    'builder.oob_q':    {'ru': 'OOB — разрезает пакет и отправляет первую часть как\n'
                         '«внеполосные» (out-of-band) TCP-данные. Такие байты\n'
                         'должны игнорироваться при сборке потока, но DPI\n'
                         'нередко съедает их как обычные — и ломает разбор.\n\n'
                         'Формат позиций — как у split. Некоторые провайдеры\n'
                         'ОТБИВАЮТ OOB-пакеты (в логах видно "unreach ip") —\n'
                         'если сайты перестали открываться, уберите OOB-методы\n'
                         'или комбинируйте с -A (авто-режим).\n\n'
                         'Несколько позиций — через пробел.',
                         'en': 'OOB — cuts the packet and sends the first part as\n'
                         'TCP "out-of-band" data. Such bytes must be ignored\n'
                         'when reassembling the stream, but DPIs often swallow\n'
                         'them as regular data — breaking their parsing.\n\n'
                         'Position format is the same as split. Some ISPs\n'
                         'REJECT OOB packets (you will see "unreach ip" in\n'
                         'logs) — if sites stopped opening, remove OOB\n'
                         'methods or combine with -A (auto mode).\n\n'
                         'Multiple positions — space-separated.'},
    'builder.oob_n':    {'ru': 'OOB-методы (-oN)', 'en': 'OOB methods (-oN)'},
    'builder.oob_n_h':  {'ru': 'Список OOB-позиций через пробел (например: 1 25+s).',
                         'en': 'Space-separated OOB positions (e.g.: 1 25+s).'},
    'builder.oob_n_q':  {'ru': 'Сводное поле всех OOB-методов строки.\n'
                         'Каждое число/позиция = один -oN в строке параметров.\n\n'
                         'Пример: вписать "1 25+s" даст "-o1 -o25+s".\n'
                         'Число N — просто позиция разреза в байтах\n'
                         '(1 = разрез на первом байте пакета).\n\n'
                         '⚠️ В текущем byedpi -oN — это ПОВТОРЯЕМЫЙ флаг\n'
                         '«OOB-разрез на позиции N», а НЕ «метод №N из 25».\n'
                         'Суффиксы: +s/+h/+n (первый), +m/+e/+r/+s (второй).\n\n'
                         'Методы ПОСЛЕ -A применяются только при блокировке —\n'
                         'обычные сайты проходят без искажений.',
                         'en': 'Summary field for all OOB methods in the string.\n'
                         'Each number/position = one -oN token.\n\n'
                         'Example: typing "1 25+s" yields "-o1 -o25+s".\n'
                         'The number N is just the byte position to cut at\n'
                         '(1 = cut at the first byte of the packet).\n\n'
                         '⚠️ In current byedpi -oN is a REPEATABLE flag\n'
                         '"OOB cut at position N", NOT "method #N of 25".\n'
                         'Suffixes: +s/+h/+n (first), +m/+e/+r/+s (second).\n\n'
                         'Methods AFTER -A apply only on blocking — regular\n'
                         'sites pass through untouched.'},
    'builder.disoob':   {'ru': 'Dis-OOB позиция (-q)', 'en': 'Dis-OOB position (-q)'},
    'builder.disoob_h': {'ru': 'Обратный порядок + OOB.',
                         'en': 'Reverse order + OOB.'},
    'builder.disoob_q': {'ru': 'DIS-OOB — комбинация disorder и OOB: пакет\n'
                          'разрезается, и части уходят в обратном порядке,\n'
                          'причём первая часть — как out-of-band данные.\n'
                          'Двойное искажение для упрямых DPI.\n\n'
                          'Формат позиций — как у split. Несколько позиций —\n'
                          'через пробел.',
                          'en': 'DIS-OOB — disorder + OOB combined: the packet is\n'
                          'cut and parts go in reverse order, with the first\n'
                          'part sent as out-of-band data. Double distortion\n'
                          'for stubborn DPIs.\n\n'
                          'Position format is the same as split. Multiple\n'
                          'positions — space-separated.'},
    'builder.fake':     {'ru': 'Fake позиция (-f)', 'en': 'Fake position (-f)'},
    'builder.fake_h':   {'ru': 'Отправка поддельного пакета перед настоящим.',
                         'en': 'Send a fake packet before the real one.'},
    'builder.fake_q':   {'ru': 'FAKE — перед настоящим пакетом отправляется\n'
                         'ПОДДЕЛЬНЫЙ (fake) пакет с малым TTL. Подделка\n'
                         '«умирает» на оборудовании провайдера (TTL слишком\n'
                         'мал), но DPI успевает разобрать именно её и\n'
                         'пропускает настоящий пакет.\n\n'
                         'Число = позиция разреза настоящего пакета.\n'
                         'TTL подделки задаётся отдельно (-t), её содержимое\n'
                         'можно кастомизировать (-l, -n, -Q).\n\n'
                         'Несколько позиций — через пробел.',
                         'en': 'FAKE — a fake packet with a low TTL is sent before\n'
                         'the real one. The fake "dies" at the ISP equipment\n'
                         '(TTL too small), but the DPI parses the fake and\n'
                         'lets the real packet through.\n\n'
                         'The number = cut position of the real packet.\n'
                         'Fake TTL is set separately (-t); its content can be\n'
                         'customized (-l, -n, -Q).\n\n'
                         'Multiple positions — space-separated.'},

    'builder.timeout':  {'ru': 'Таймаут авто-режима (-T), сек', 'en': 'Auto-mode timeout (-T), sec'},
    'builder.timeout_h': {'ru': 'Ждать ответа N секунд, затем применить auto-стратегию. 0 = выключено.',
                          'en': 'Wait N seconds for a response, then apply auto strategy. 0 = off.'},
    'builder.timeout_q': {'ru': 'Сколько секунд ждать ответа сайта, прежде чем\n'
                          'решить «похоже, нас блокируют» и применить обход.\n\n'
                          'Работает в паре с -A (триггером). Если ответ пришёл\n'
                          'быстро — соединение чистое, ничего не ломаем.\n'
                          'Если за N секунд тишина или обрыв — включаем методы\n'
                          'обхода и переподключаемся.\n\n'
                          'Типичные значения: 1–3 сек (баланс скорости\n'
                          'и реакции на блокировку). 0 = авто-режим выключен,\n'
                          'методы до -A применяются всегда.',
                          'en': 'How many seconds to wait for the site response\n'
                          'before deciding "looks like blocking" and applying\n'
                          'the bypass.\n\n'
                          'Works together with -A (the trigger). If the answer\n'
                          'arrives quickly — the connection is clean, nothing\n'
                          'is distorted. If silence or a reset within N seconds\n'
                          '— bypass methods kick in and we reconnect.\n\n'
                          'Typical values: 1–3 sec (balance between speed and\n'
                          'blocking reaction). 0 = auto mode off, methods\n'
                          'before -A always apply.'},
    'builder.auto':     {'ru': 'Auto-триггер (-A)', 'en': 'Auto trigger (-A)'},
    'builder.auto_h':   {'ru': 'Когда применять обход: torst, ssl_err, redirect, conn, none.',
                         'en': 'When to apply desync: torst, ssl_err, redirect, conn, none.'},
    'builder.auto_q':   {'ru': 'СОБЫТИЕ, при котором включаются методы обхода:\n'
                         '• torst — соединение сброшено (RST) или таймаут\n'
                         '• ssl_err — ошибка TLS при handshake\n'
                         '• redirect — провайдер подменил ответ redirect-ом\n'
                         '• conn — не удалось установить соединение\n'
                         '• none — не ждать событий, применять всегда\n'
                         '• несколько через запятую: torst,ssl_err\n\n'
                         '⭐ ГЛАВНОЕ: методы обхода, указанные ПОСЛЕ -A,\n'
                         'применяются только при срабатывании триггера!\n'
                         'До -A — безусловно (ломает и обычные сайты).\n'
                         'В этом секрет: -T3 -A torst -o1 — на заблокированных\n'
                         'сработает -o1, на обычных ничего не изменится.',
                         'en': 'The EVENT that triggers the bypass methods:\n'
                         '• torst — connection reset (RST) or timeout\n'
                         '• ssl_err — TLS handshake error\n'
                         '• redirect — ISP replaced the reply with a redirect\n'
                         '• conn — could not establish the connection\n'
                         '• none — wait for nothing, always apply\n'
                         '• several comma-separated: torst,ssl_err\n\n'
                         '⭐ KEY POINT: bypass methods placed AFTER -A apply\n'
                         'only when the trigger fires!\n'
                         'Before -A — unconditionally (breaks normal sites too).\n'
                         'That is the trick: -T3 -A torst -o1 — blocked sites\n'
                         'get -o1, normal ones stay untouched.'},
    'builder.automode': {'ru': 'Auto-режим (-L)', 'en': 'Auto mode (-L)'},
    'builder.automode_h': {'ru': 'Буквы s, o, n через запятую. Пусто = по умолчанию.',
                           'en': 'Letters s, o, n comma-separated. Blank = default.'},
    'builder.automode_q': {'ru': 'Что делать ПОСЛЕ срабатывания триггера (-A):\n'
                           '• s — кешировать подобранные параметры для IP\n'
                           '  (следующие соединения к этому сайту сразу идут\n'
                           '  с рабочим обходом, без повторного перебора)\n'
                           '• o — переподключаться с новым методом при срабатывании\n'
                           '• n — НЕ переподключаться (только пометить)\n\n'
                           'Комбинации через запятую: s,o / s,n / o,n.\n'
                           'Пусто = поведение по умолчанию (без ключа -L).\n\n'
                           '⚠️ Цифры 0..3 из старых версий больше НЕ работают\n'
                           '— текущий byedpi принимает только буквы.',
                           'en': 'What to do AFTER the -A trigger fires:\n'
                           '• s — cache the found working params for the IP\n'
                           '  (next connections to that site immediately use\n'
                           '  the working bypass, no re-search)\n'
                           '• o — reconnect with a new method on trigger\n'
                           '• n — do NOT reconnect (just mark it)\n\n'
                           'Combinations comma-separated: s,o / s,n / o,n.\n'
                           'Blank = default behaviour (no -L key).\n\n'
                           '⚠️ Digits 0..3 from old versions NO LONGER work —\n'
                           'current byedpi accepts letters only.'},
    'builder.cachettl': {'ru': 'Кэш TTL (-u), сек', 'en': 'Cache TTL (-u), sec'},
    'builder.cachettl_h': {'ru': 'Сколько хранить подобранные параметры для IP. 0 = выключено.',
                           'en': 'How long to keep per-IP desync params. 0 = off.'},
    'builder.cachettl_q': {'ru': 'Время жизни записи в кэше: «для этого сайта\n'
                           'работает вот такой обход». Работает вместе с\n'
                           'ключом s авто-режима (-L s).\n\n'
                           'После успешного подбора параметров для IP-адреса\n'
                           'сайта они кэшируются на N секунд — повторные\n'
                           'посещения не тратят время на подбор заново.\n\n'
                           '0 = кэширование выключено.\n'
                           'Сутки = 86400, неделя = 604800.\n'
                           'Кэш можно хранить в файле между запусками (-y).',
                           'en': 'Lifetime of a cache entry: "for this site, this\n'
                           'bypass works". Works together with the s key of\n'
                           'auto mode (-L s).\n\n'
                           'After params are found for a site IP they are cached\n'
                           'for N seconds — repeat visits do not re-search.\n\n'
                           '0 = caching disabled.\n'
                           'A day = 86400, a week = 604800.\n'
                           'The cache can be persisted to a file (-y).'},

    'builder.proto':    {'ru': 'Протоколы (-K)', 'en': 'Protocols (-K)'},
    'builder.proto_h':  {'ru': 'Белый список протоколов: t=tls, h=http, u=udp, i=ipv4.',
                         'en': 'Protocol whitelist: t=tls, h=http, u=udp, i=ipv4.'},
    'builder.proto_q':  {'ru': 'Ограничить обход только указанными протоколами.\n'
                         'Соединения других протоколов пойдут напрямую,\n'
                         'без искажений.\n\n'
                         '• t — TLS (все https-сайты)\n'
                         '• h — HTTP (обычные сайты)\n'
                         '• u — UDP (редко нужно, квик-протоколы)\n'
                         '• i — IPv4-соединения\n\n'
                         'Комбинации через запятую: t,h — только веб.\n'
                         'Пусто = применять ко всем протоколам.',
                         'en': 'Restrict the bypass to the listed protocols only.\n'
                         'Other protocols pass through untouched.\n\n'
                         '• t — TLS (all https sites)\n'
                         '• h — HTTP (plain sites)\n'
                         '• u — UDP (rarely needed, QUIC)\n'
                         '• i — IPv4 connections\n\n'
                         'Combinations comma-separated: t,h — web only.\n'
                         'Blank = apply to all protocols.'},
    'builder.pf':       {'ru': 'Диапазон портов (-V)', 'en': 'Port range (-V)'},
    'builder.pf_h':     {'ru': 'Применять обход только к этим портам.',
                         'en': 'Apply desync only to these ports.'},
    'builder.pf_q':     {'ru': 'Обход применяется только к соединениям на\n'
                         'указанные порты назначения; всё остальное идёт\n'
                         'напрямую.\n\n'
                         'Примеры: 443 — только TLS; 80-443 — весь веб;\n'
                         '80,443 — конкретные порты (через дефис только\n'
                         'диапазон!).\n\n'
                         'Полезно, чтобы не трогать SSH (22), почту и пр.\n'
                         'Пусто = все порты.',
                         'en': 'Bypass applies only to connections to the listed\n'
                         'destination ports; everything else goes direct.\n\n'
                         'Examples: 443 — TLS only; 80-443 — all web;\n'
                         '80,443 — specific ports (dash = range only!).\n\n'
                         'Useful to leave SSH (22), mail etc. untouched.\n'
                         'Blank = all ports.'},
    'builder.round':    {'ru': 'Round (-R)', 'en': 'Round (-R)'},
    'builder.round_h':  {'ru': 'К какому по счёту запросу применять обход.',
                         'en': 'Which request number gets the bypass.'},
    'builder.round_q':  {'ru': 'Обход применяется не к первому запросу, а к N-му\n'
                         'по счёту в соединении. Некоторые DPI анализируют\n'
                         'только первый запрос — тогда обход на поздних\n'
                         'запросах проходит незамеченным.\n\n'
                         'Формат: число или диапазон, напр. 1 или 2-5.\n'
                         'Пусто = применять к каждому запросу.',
                         'en': 'The bypass applies not to the first request but\n'
                         'to the N-th one in the connection. Some DPIs analyze\n'
                         'only the first request — a bypass on later ones\n'
                         'slips through unnoticed.\n\n'
                         'Format: a number or a range, e.g. 1 or 2-5.\n'
                         'Blank = every request.'},

    'builder.ttl':      {'ru': 'TTL fake-пакетов (-t)', 'en': 'Fake packet TTL (-t)'},
    'builder.ttl_h':    {'ru': 'TTL поддельных пакетов.',
                         'en': 'TTL of fake packets.'},
    'builder.ttl_q':    {'ru': 'Time-To-Live поддельных пакетов (-f): через сколько\n'
                         'хопов «умрёт» подделка.\n\n'
                         'Значение должно быть МЕНЬШЕ расстояния до сайта\n'
                         '(обычно 2–8), чтобы пакет погиб на оборудовании\n'
                         'провайдера и до сервера дошёл только настоящий.\n\n'
                         'Слишком большой TTL — подделка дойдёт до сайта\n'
                         'и сломает соединение. Слишком маленький — DPI\n'
                         'успеет её разобрать раньше, чем она умрёт.\n'
                         'По умолчанию 8.',
                         'en': 'Time-To-Live of fake packets (-f): after how many\n'
                         'hops the fake "dies".\n\n'
                         'The value must be SMALLER than the distance to the\n'
                         'site (usually 2–8) so the packet dies on ISP gear\n'
                         'and only the real one reaches the server.\n\n'
                         'Too large a TTL — the fake reaches the site and\n'
                         'breaks the connection. Too small — the DPI parses\n'
                         'it before it dies. Default 8.'},
    'builder.tlsrec':   {'ru': 'TLS record позиция (-r)', 'en': 'TLS record position (-r)'},
    'builder.tlsrec_h': {'ru': 'Разбиение TLS record.',
                         'en': 'TLS record splitting.'},
    'builder.tlsrec_q': {'ru': 'TLSREC — разбивает TLS-запись (ClientHello) на\n'
                         'несколько записей по указанной позиции. DPI,\n'
                         'который ждёт целиком один ClientHello, не может\n'
                         'прочитать SNI из «разрезанного».\n\n'
                         'Формат позиции — как у split (смещение+флаги).\n'
                         'Классика: 1+s — разрез прямо в SNI.\n\n'
                         'Может путать мидлбоксы (некоторые антиспам-системы\n'
                         'не понимают разделённые записи) — используйте\n'
                         'с -A, чтобы бить только заблокированные.\n\n'
                         'Несколько позиций — через пробел.',
                         'en': 'TLSREC — splits the TLS record (ClientHello) into\n'
                         'several records at the given position. A DPI\n'
                         'expecting a single whole ClientHello cannot read\n'
                         'the SNI from a "cut up" one.\n\n'
                         'Position format — same as split (offset+flags).\n'
                         'Classic: 1+s — cut right inside the SNI.\n\n'
                         'May confuse middleboxes (some antispam systems do\n'
                         'not understand split records) — use with -A to hit\n'
                         'only blocked sites.\n\n'
                         'Multiple positions — space-separated.'},
    'builder.udpfake':  {'ru': 'UDP fake-пакеты (-a)', 'en': 'UDP fakes (-a)'},
    'builder.udpfake_h': {'ru': 'Количество UDP-fake на каждый запрос. 0 = выключено.',
                          'en': 'UDP fake count per request. 0 = off.'},
    'builder.udpfake_q': {'ru': 'Сколько поддельных UDP-пакетов отправлять перед\n'
                          'каждым настоящим UDP-запросом (для QUIC/HTTP3).\n'
                          'Аналог fake (-f), но для UDP-протокола.\n\n'
                          '0 = выключено. Обычно 1–3.\n'
                          'Большинство сайтов работает по TCP, поэтому\n'
                          'параметр нужен редко.',
                          'en': 'How many fake UDP packets to send before each\n'
                          'real UDP request (for QUIC/HTTP3).\n'
                          'Analogous to fake (-f) but for UDP.\n\n'
                          '0 = off. Usually 1–3.\n'
                          'Most sites run on TCP, so this is rarely needed.'},
    'builder.md5sig':   {'ru': 'MD5 сигнатура (-S)', 'en': 'MD5 signature (-S)'},
    'builder.md5sig_h': {'ru': 'Добавлять опцию MD5 Signature к fake-пакетам.',
                         'en': 'Add MD5 Signature option to fakes.'},
    'builder.md5sig_q': {'ru': 'Добавляет к fake-пакетам TCP-опцию MD5 Signature.\n'
                         'Часть DPI игнорирует пакеты с этой опцией как\n'
                         '«служебные» — подделка проскакивает глубже в сеть\n'
                         'провайдера, повышая правдоподобие атаки.\n\n'
                         'Работает в паре с -f (fake). Ставить имеет смысл\n'
                         'только когда fake-метод включён.\n'
                         'Совместим не со всеми провайдерами.',
                         'en': 'Adds the TCP MD5 Signature option to fake packets.\n'
                         'Some DPIs ignore packets with this option as\n'
                         '"service" ones — the fake penetrates deeper into\n'
                         'the ISP network, making the attack more convincing.\n\n'
                         'Works together with -f (fake). Only makes sense\n'
                         'when the fake method is enabled.\n'
                         'Not compatible with every ISP.'},
    'builder.dropsack': {'ru': 'Drop SACK (-Y)', 'en': 'Drop SACK (-Y)'},
    'builder.dropsack_h': {'ru': 'Отбрасывать пакеты с SACK.',
                           'en': 'Drop packets with SACK.'},
    'builder.dropsack_q': {'ru': 'Отбрасывать исходящие TCP-пакеты с расширением\n'
                           'SACK (селективные подтверждения).\n\n'
                           'Некоторые DPI используют SACK-пакеты как признак\n'
                           '«нормального» соединения после разрезания —\n'
                           'отбрасывание сбивает их с толку.\n\n'
                           'Осторожно: может ЗАМЕДЛИТЬ соединения на плохих\n'
                           'линиях (без SACK повторная передача идёт\n'
                           'более грубыми блоками).',
                           'en': 'Drop outgoing TCP packets with the SACK extension\n'
                           '(selective acknowledgements).\n\n'
                           'Some DPIs use SACK packets as a sign of a "normal"\n'
                           'connection after splitting — dropping them\n'
                           'confuses such DPIs.\n\n'
                           'Careful: may SLOW DOWN connections on lossy links\n'
                           '(without SACK, retransmission works in cruder\n'
                           'blocks).'},
    'builder.modhttp':  {'ru': 'Модификация HTTP (-M)', 'en': 'HTTP modification (-M)'},
    'builder.modhttp_h': {'ru': 'h=hcsmix, d=dcsmix, r=rmspace.',
                          'en': 'h=hcsmix, d=dcsmix, r=rmspace.'},
    'builder.modhttp_q': {'ru': 'Искажение HTTP-заголовков, чтобы DPI не мог\n'
                          'найти Host в открытом виде:\n'
                          '• h (hcsmix) — изменить регистр символов заголовка\n'
                          '  (Host → hOsT): DPI ищет по точному совпадению\n'
                          '• d (dcsmix) — то же для содержимого/значений\n'
                          '• r (rmspace) — убрать пробелы после двоеточий\n'
                          '  ("Host: site" → "Host:site")\n\n'
                          'Комбинации через запятую: h,d / h,d,r.\n'
                          'По RFC регистр и пробелы не значимы — сайты\n'
                          'работают, DPI — нет.',
                          'en': 'Distorts HTTP headers so the DPI cannot find\n'
                          'the Host in plain form:\n'
                          '• h (hcsmix) — mix the letter case of the header\n'
                          '  (Host → hOsT): DPI matches exact strings\n'
                          '• d (dcsmix) — same for contents/values\n'
                          '• r (rmspace) — remove spaces after colons\n'
                          '  ("Host: site" → "Host:site")\n\n'
                          'Combinations comma-separated: h,d / h,d,r.\n'
                          'Per RFC case and spaces are insignificant — sites\n'
                          'keep working, DPIs do not.'},
    'builder.fakemod':  {'ru': 'Модификация fake TLS (-Q)', 'en': 'Fake TLS modification (-Q)'},
    'builder.fakemod_h': {'ru': 'rand, orig для fake-пакетов.',
                          'en': 'rand, orig for fake packets.'},
    'builder.fakemod_q': {'ru': 'Как изменять fake-пакет, чтобы он выглядел\n'
                          'правдоподобнее для DPI:\n'
                          '• rand — случайные значения полей TLS\n'
                          '  (случайный session id и пр. — каждый пакет\n'
                          '  уникален, DPI не может «запомнить» шаблон)\n'
                          '• orig — скопировать поля из НАСТОЯЩЕГО пакета\n'
                          '  (максимально похоже на реальное соединение)\n'
                          '• msize=N — задать точный размер fake-пакета\n\n'
                          'Работает в паре с -f (fake).',
                          'en': 'How to alter the fake packet so it looks more\n'
                          'convincing to the DPI:\n'
                          '• rand — random TLS field values\n'
                          '  (random session id etc. — each packet unique,\n'
                          '  the DPI cannot "memorize" the template)\n'
                          '• orig — copy fields from the REAL packet\n'
                          '  (as close to a genuine connection as possible)\n'
                          '• msize=N — set the exact fake packet size\n\n'
                          'Works together with -f (fake).'},

    # ---- Прокси ----
    'proxy.title':        {'ru': 'Настройки прокси', 'en': 'Proxy settings'},
    'proxy.mode':         {'ru': 'Режим прокси:', 'en': 'Proxy mode:'},
    'proxy.mode_pac':     {'ru': 'Системный PAC-скрипт (не наш прокси!)', 'en': 'System PAC script (NOT our proxy!)'},
    'proxy.mode_pac_h':   {'ru': 'Режим GNOME «Автоматический»: сеть настраивается PAC-скриптом провайдера.\nЭто НЕ связано с ciadpi. Оставляйте только если ваш провайдер дал PAC URL.',
                           'en': 'GNOME “Automatic” mode: network configured by a provider PAC script.\nNOT related to ciadpi. Use only if your provider gave you a PAC URL.'},
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
    'proxy.saved_state':  {'ru': 'Задано в конфиге', 'en': 'Saved in config'},
    'proxy.type_socks':   {'ru': 'Тип прокси: SOCKS5 (ciadpi/byedpi — не HTTP!)', 'en': 'Proxy type: SOCKS5 (ciadpi/byedpi — not HTTP!)'},
    'proxy.probe_ok':     {'ru': '🟢 Порт отвечает — сервис ciadpi слушает этот адрес', 'en': '🟢 Port responds — the ciadpi service is listening'},
    'proxy.probe_fail':   {'ru': '🔴 Порт НЕ отвечает — сервис не запущен или слушает другой порт', 'en': '🔴 Port does NOT respond — service not running or listening on another port'},
    'proxy.probe_hint':   {'ru': 'Проба — проверка TCP-соединения с host:port: показывает, жив ли прокси прямо сейчас', 'en': 'The probe is a TCP connection test to host:port: shows whether the proxy is alive right now'},
    'proxy.system_now':   {'ru': 'Система сейчас', 'en': 'System now'},
    'proxy.applied_ok':   {'ru': 'Настройки применены, состояние совпадает', 'en': 'Applied, system matches the config'},
    'proxy.not_applied':  {'ru': 'Задано, но в системе ещё не применено (применится при запуске сервиса)', 'en': 'Saved but not applied yet (applied when the service starts)'},
    'proxy.local_active': {'ru': 'Локальный режим активен: системные настройки не меняются, указывайте порт приложениям вручную', 'en': 'Local mode active: system settings untouched, point apps at the port manually'},
    'proxy.apply_failed': {'ru': 'Не удалось применить настройки прокси', 'en': 'Failed to apply proxy settings'},
    'proxy.restored_original': {'ru': 'Исходные системные настройки прокси восстановлены', 'en': 'Original system proxy settings restored'},
    'proxy.auto_disable': {'ru': '❌ Автоматически отключать прокси при выходе', 'en': '❌ Automatically disable proxy on exit'},
    'proxy.auto_disable_h': {'ru': 'При остановке сервиса прокси будет автоматически отключен в системе',
                             'en': 'Proxy will be disabled system-wide when the service stops'},
    # ---- Кнопки диалогов (раньше Gtk.STOCK_*: переводились системной
    #      локалью, а не нашим i18n — «Закрыть/ОК» оставались русскими) ----
    'btn.ok':        {'ru': 'ОК', 'en': 'OK'},
    'btn.cancel':    {'ru': 'Отмена', 'en': 'Cancel'},
    'btn.close':     {'ru': 'Закрыть', 'en': 'Close'},
    'btn.apply':     {'ru': 'Применить', 'en': 'Apply'},

    # ---- Дополнительные ключи (v1.5) ----
    'notif.command_ok':   {'ru': 'Команда выполнена', 'en': 'Command completed'},
    'notif.service_started_proxy': {'ru': 'Сервис запущен, настройки прокси применены',
                                    'en': 'Service started, proxy settings applied'},
    'settings.dialog_title': {'ru': 'Настройки параметров CIADPI', 'en': 'CIADPI Parameter Settings'},
    'settings.params_label': {'ru': 'Параметры запуска CIADPI:', 'en': 'CIADPI launch parameters:'},
    'settings.examples':  {'ru': 'Примеры параметров (кликните для копирования):',
                           'en': 'Parameter examples (click to copy):'},
    'settings.hint':      {'ru': '💡 Параметры проверяются автоматически при сохранении',
                           'en': '💡 Parameters are validated automatically on save'},
    'settings.validation_error': {'ru': 'Ошибка в параметрах:', 'en': 'Parameter error:'},
    'builder.help_section': {'ru': 'Раздел:', 'en': 'Section:'},

    # ---- Справка / О программе / смена языка ----
    'help.title':      {'ru': 'Расширенная справка', 'en': 'Extended Reference'},
    'about.title':     {'ru': 'О программе', 'en': 'About'},
    'app.lang_restart': {'ru': 'Язык изменён. Изменение применится после перезапуска индикатора (Выход → запуск).',
                         'en': 'Language changed. It takes effect after restarting the indicator (Exit → launch).'},
    'app.lang_restart_ru_title': {'ru': 'Язык изменён на русский',
                                  'en': 'Language changed to Russian'},
    'app.lang_restart_en_title': {'ru': 'Language changed to English',
                                  'en': 'Language changed to English'},
}


_current = None


def _load_choice():
    global _current
    if _current is not None:
        return _current
    try:
        _LANG_FILE.parent.mkdir(parents=True, exist_ok=True)
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

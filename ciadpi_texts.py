#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Полные тексты справки и «О программе» на RU и EN."""

HELP_TEXTS = {
    'ru': '''📚 CIADPI Advanced Indicator — Полная справка

    🎯 ОСНОВНЫЕ ВОЗМОЖНОСТИ (полный список):

    • ЧЕТЫРЕ режима обхода: byedpi (SOCKS5), nfqws (десинки
      zapret), snimod (наш SNI case-mod), DNS-мост (DoT)
    • Окно «Режимы обхода»: radio-выбор кликом по всей строке,
      кнопки Запустить/Остановить/Перезапустить выбранного,
      повторный запуск активного — no-op, чужие режимы гасятся
    • «🎛 Настройки режима»: вкладки Параметры (строка+дефолт+
      примеры+4 последних по режиму) / Конструктор (byedpi с
      справками «?», nfqws-десинки, хосты+мост для snimod,
      upstream для моста) / Поиск стратегии под режим
    • 🗂 Профили: снимки «режим+параметры+мост+прокси» под именем,
      применение одним кликом — для разных сетей/мест
    • 🛡️ Белый список: исключение из прокси (byedpi) и из обхода
      DPI (nfqws: nft-set, домены резолвятся автоматически)
    • Поиск стратегии: лимит или «до нахождения», DoH-резолв
      заблокированных хостов, история 200 прогонов
    • Умный прокси: системный/local-only, бэкап и восстановление
      настроек GNOME, автооткат при остановке/выходе
    • Обновление byedpi из git без переустановки
    • RU/EN локализация, настройки уведомлений по категориям
    • Мониторинг статуса в трее, логи, диагностика (CLI:
      ciadpi_enginectl.py / ciadpi_profiles.py / diagnose_ciadpi.py)

    🛠️ Управление сервисом:

    🛠️ Управление сервисом:
    • Запуск/остановка/перезапуск сервиса CIADPI
    • Мониторинг статуса в реальном времени
    • Проверка параметров перед применением (dry-run бинарником)

    🔌 Умное управление прокси:
    • ciadpi — SOCKS4/5-прокси на 127.0.0.1:1080
    • Режимы: системный (manual), локальный (не трогает систему)
    • Резервное копирование и восстановление настроек GNOME
    • Поддержка белого списка доменов

    🎛️ НАСТРОЙКИ РЕЖИМА (v2.0.7+):

    Один пункт меню «🎛 Настройки режима…» — окно с тремя вкладками,
    содержимое строится под ВЫБРАННЫЙ режим:

    • «Параметры» — ручная строка ввода + дефолт + примеры +
      4 ПОСЛЕДНИХ использованных (свои для каждого режима,
      автообновление). Для snimod — редактор списка хостов.
    • «Конструктор» — компактные регуляторы ключевых флагов
      (byedpi: -T/-A/-s/-r; nfqws: desync/-split-pos/ttl; мост:
      upstream DoT-резолвер + TLS-имя). Правки сразу идут в строку.
    • «Поиск стратегии» — перебор параметров под выбранный режим;
      найденное — кнопкой «→ в строку параметров».

    🗂 ПРОФИЛИ (v2.0.6+):

    «Профили…» — снимки настроек для разных сетей: выбранный режим,
    параметры всех движков, состояние DNS-моста, настройки прокси.
    «Сохранить текущее как…» — снимок; «Применить» — поднимает
    сохранённое целиком (гасит лишнее, стартует нужное). Для
    переключения Дом/Кофейня/Работа на ноутбуке.

    ⚡ Оптимизация параметров:
    • Конструктор с подробными подсказками «?» по каждому параметру
    • Поиск стратегии перебором (вкладка «Поиск стратегии»)
    • Готовые проверенные примеры конфигураций
    • История тестирования

    ♾️ ПОИСК «ДО НАХОЖДЕНИЯ» (v1.7+):

    Чекбокс «Искать до нахождения» в диалоге поиска отключает лимит
    попыток. Перебор продолжается, пока какая-нибудь комбинация НЕ
    ОТКРОЕТ ВСЕ указанные URL — частичный доступ (например, google
    работает, youtube нет) успехом НЕ считается, поиск идёт дальше.
    Остановить можно кнопкой «Остановить» или закрытием окна.

    «Мин. попыток» — нижний предел: даже если все URL открылись на
    первой же комбинации, поиск проверит ещё несколько (защита от
    случайного результата), после предела первый же ПОЛНЫЙ успех
    останавливает перебор. Итог — самая быстрая комбинация из
    прошедших все URL.

    Комбинации не кончаются: после известного набора и истории
    генератор выдаёт новые волны (60/120/180…), без повторов.

    🎛️ ЧЕТЫРЕ РЕЖИМА ОБХОДА (v2.0.8):

    «⚙ Режимы обхода…» — окно с radio-строками, выбор кликом по всей
    строке, кнопки ▶ Запустить / ⏹ Остановить / ↻ Перезапустить
    действуют на ВЫБРАННЫЙ режим. Повторный запуск активного —
    no-op (не рестарт). Запуск одного режима гасит остальные.

    • byedpi — SOCKS5-прокси 127.0.0.1. Обходится только трафик,
      явно направленный в прокси. Параметры — «🎛 Настройки режима».

    • nfqws — десинки zapret через NFQUEUE: искажает пакеты ВСЕХ
      приложений (порты 80/443), настройка приложений не нужна.
      Самый мощный против SNI/IP-фильтров прова.

    • snimod — наш движок №3: поднимает РЕГИСТР SNI (www.youtube.com
      → WWW.YOUTUBE.COM). Пров режет по подстроке в нижнем регистре,
      серверу регистр безразличен (RFC 6066). Хосты — «Настройки
      режима» → «Параметры».

    • DNS-мост — локальный DoT-резолвер 127.0.0.1:53 → upstream:853
      (по умолчанию 1.1.1.1; сменить — «Настройки режима» →
      «Конструктор»). Чинит NXDOMAIN-подмену DNS прова. Работает
      сам по себе и вместе с любым движком.

    ⭐ Выбор режима сохраняется и НЕ зависит от того, запущен ли
    сервис. Главное меню «Запустить/Остановить» управляет именно
    выбранным режимом (включая мост). Смена режима не запускает
    его автоматически — стартуйте кнопкой или «Запустить».

    ⭐ Выбор движка НЕ зависит от того, запущен ли сервис: остановленный
    nfqws остаётся выбранным nfqws — меню, «Запустить/Остановить»
    и статус продолжают управлять именно им. «Остановить сервис»
    больше НЕ переключает движок, а «Запустить» поднимает выбранный.
    (В подменю движка две строки: «Выбран: …» и «Сервис: active/inactive».)

    ⭐ Смена движка НЕ запускает его автоматически (v1.9.1): галочка
    меняет только ВЫБОР (и boot-флаги — на перезагрузке поднимется
    именно он). Поднять движок — «Запустить сервис» вручную.
    При уходе на nfqws системный прокси сбрасывается автоматически
    (nfqws прокси не использует, а manual на мёртвом порте ломает
    браузеры).

    Движки взаимоисключающие: nfqws перехватил бы и трафик byedpi
    (двойное искажение ломает соединения). Переключатель сам
    останавливает другой движок и снимает его настройки.

    При активном nfqws пункты, применимые только к byedpi (настройки
    параметров, конструктор, прокси, поиск стратегии), скрыты из меню —
    показываются только пункты активного движка. Параметры nfqws —
    в «Движок обхода → Параметры nfqws»
    (формат zapret: --dpi-desync=…, с примерами и проверкой).

    🔍 ПОИСК СТРАТЕГИИ ДЛЯ ЛЮБОГО ДВИЖКА (v1.9+):
    В диалоге «Поиск стратегии» выберите движок: byedpi тестируется
    на отдельном порту (интернет не прерывается), nfqws — через
    реальный сервис (каждая комбинация включается на ~10 секунд;
    успех = все указанные URL открываются). Для nfqws-режима
    используется формат zapret, найденные параметры применяются
    кнопкой «Применить» прямо в nfqws.json + рестарт сервиса.

    ⭐ ГЛАВНЫЙ ПРИНЦИП РАБОТЫ:

    Параметры ДЕСИНХРОНИЗАЦИИ (обхода), указанные ПОСЛЕ -A,
    применяются ТОЛЬКО при признаках блокировки (сброс соединения,
    таймаут, ошибка TLS). Обычные сайты проходят через прокси
    БЕЗ ИСКАЖЕНИЙ. Поэтому правильный шаблон:

        -T3 -A torst -o1 -o25+s -r 1+s
        └─┬─┘ └──┬───┘ └──────┬──────┘
        таймаут триггер   методы обхода
                      (только при блокировке!)

    Методы, стоящие ДО -A, применяются ко ВСЕМ соединениям
    без разбора и часто ломают незаблокированные сайты.

    📋 ПАРАМЕТРЫ CIADPI (ОСНОВНЫЕ):

    -i IP        IP прослушивания (по умолчанию 0.0.0.0 — все)
    -p PORT      порт локального SOCKS-прокси (по умолчанию 1080)
    -D           демонизация (фоновый режим)
    -w FILE      файл PID
    -E           прозрачный режим прокси
    -c COUNT     лимит одновременных соединений (по умолчанию 512)
    -N           запретить резолвинг доменов
    -U           запретить UDP-ассоциации
    -I IP        IP для исходящих соединений (по умолчанию ::)
    -b SIZE      размер буфера (по умолчанию 16384)
    -x LEVEL     уровень отладки: 0 — нет, 1 — базовый, 2 — подробно
    -g TTL       TTL для всех исходящих соединений
    -F           TCP Fast Open

    АВТОМАТИЧЕСКИЙ РЕЖИМ:
    -T SEC       ждать ответа N сек, затем сработает авто-режим.
                 Формат: сек[:пауза:счётчик:байты]
    -A MODE      ТРИГГЕР: torst (сброс/таймаут), ssl_err (ошибка TLS),
                 redirect (подмена ответа), conn (нет соединения),
                 none (всегда). Несколько через запятую: torst,ssl_err.
                 ⭐ Всё, что ПОСЛЕ -A, применяется только при триггере!
    -L MODE      поведение после триггера — ТОЛЬКО БУКВЫ:
                 s — кешировать рабочие параметры для IP,
                 o — переподключаться при срабатывании,
                 n — не переподключаться.
                 Комбинации через запятую: s,o. Цифры 0..3 не работают!
    -u SEC       TTL кэша подобранных параметров для IP (86400=сутки)
    -y FILE      дамп кэша в файл (-y - в stdout)

    ФИЛЬТРЫ:
    -K LIST      протоколы: t(tls) h(http) u(udp) i(ipv4), пример: t,h
    -H FILE|:STR белый список хостов (файл или :строка)
    -j FILE|:STR белый список IP
    -V RANGE     диапазон портов назначения, например 80-443
    -R N         номер запроса для обхода, например 1 или 1-3

    МЕТОДЫ ОБХОДА (desync) — ПОВТОРЯЕМЫЕ, через пробел:
    Формат позиции: смещение[:повторы[:шаг]]+флаги
    Первый флаг: +s — от SNI, +h — от HTTP Host, +n — нуль-байт.
    Второй (опционально): +e — от конца, +m — середина,
    +r — случайно, +s — от начала.
    -s POS       split — разрезать пакет на позиции
    -d POS       disorder — разрезать и отправить части в обратном порядке
    -o POS       oob — разрезать, первую часть отправить как OOB-данные.
                 ⚠️ -oN это позиция, а НЕ «метод №N»: -o1 -o25+s —
                 два разреза (на 1-м байте и 25-м от SNI)
    -q POS       disoob — обратный порядок + OOB
    -f POS       fake — отправить поддельный пакет перед настоящим
                 (TTL подделки: -t, содержимое: -l, -n, -Q)
    -r POS       tlsrec — разбить TLS-запись (ClientHello) на части.
                 Классика: -r 1+s — разрез внутри SNI

    FAKE-ПАКЕТЫ И МОДИФИКАЦИИ:
    -t TTL       TTL fake-пакетов (по умолчанию 8, обычно 2–8)
    -S           MD5 Signature к fake-пакетам
    -n STR       подмена SNI в fake (? — случайная буква, # — цифра)
    -O POS       смещение начала fake-данных
    -l FILE|:STR кастомные fake-данные
    -Q FLAG      модификация fake TLS: rand, orig, msize=N
    -e CHAR      кастомный OOB-байт
    -M LIST      модификация HTTP: h(hcsmix) d(dcsmix) r(rmspace)
    -m VER       минорная версия TLS
    -a COUNT     количество UDP-fake (по умолчанию 0)
    -Y           отбрасывать пакеты с SACK

    ПРИМЕРЫ РАБОЧИХ КОНФИГУРАЦИЙ (проверены на byedpi):
    • -T3 -A torst -o1 -o25+s -r 1+s   (умолчание: разрезы только
      при блокировке, обычные сайты идут чисто)
    • -T2 -A torst -o2 -o15+s -r 2+s
    • -T1 -A torst -o1 -o5+s

    💡 СОВЕТЫ:
    • Если сайты перестали открываться — проверьте лог: «unreach ip»
      значит провайдер отбивает OOB-пакеты, уберите -oN-методы
    • Конструктор (меню «Конструктор») правит каждый параметр
      отдельно, со справкой «?» по каждому
    • Поиск стратегии подбирает параметры автоматически
    • Белый список исключает домены из проксирования
    • Обновляйте byedpi через меню при выходе новых версий
''',
    'en': '''📚 CIADPI Advanced Indicator — Full Reference

    🎯 CORE FEATURES:

    🛠️ Service control:
    • Start/stop/restart of the CIADPI service
    • Real-time status monitoring
    • Parameter validation before applying (binary dry-run)

    🔌 Smart proxy management:
    • ciadpi is a SOCKS4/5 proxy at 127.0.0.1:1080
    • Modes: system (manual), local (system untouched)
    • Backup and restore of GNOME proxy settings
    • Domain whitelist support

    ⚡ Parameter tuning:
    • Builder with detailed "?" hints for every parameter
    • Brute-force strategy search (menu "Strategy search")
    • Ready-made verified configuration examples
    • Test history

    ♾️ UNTIL-FOUND SEARCH (v1.7+):

    The "Search until found" checkbox removes the attempt limit.
    The search keeps going until a combination opens ALL listed URLs —
    partial access (e.g. google works, youtube does not) does NOT
    count as success and the search continues. Stop it with the
    "Stop" button or by closing the window.

    "Min attempts" is a floor: even if all URLs open on the very
    first combination, a few more are checked (protection against a
    fluke); after the floor the first FULL success stops the search.
    The result is the fastest combination that passed every URL.

    Combinations never run out: after the known set and history the
    generator produces new waves (60/120/180...), no repeats.

    🎛️ FOUR BYPASS MODES (v2.0.8):

    "⚙ Bypass modes…" opens the mode window: radio rows (click
    anywhere on the row), buttons Start/Stop/Restart act on the
    SELECTED mode. Starting one mode stops the others; re-starting
    an active mode is a no-op.

    • byedpi — SOCKS5 proxy on 127.0.0.1; only proxied apps are
      bypassed. Tuning — "🎛 Mode settings".

    • nfqws — zapret desyncs via NFQUEUE: distorts packets of ALL
      applications (ports 80/443), zero app configuration. The most
      powerful against SNI/IP filters.

    • snimod — our engine #3: uppercases the SNI (www.youtube.com →
      WWW.YOUTUBE.COM). Hosts — "Mode settings" → "Parameters".

    • DNS bridge — local DoT resolver 127.0.0.1:53 → upstream:853
      (default 1.1.1.1; change in "Mode settings" → "Builder").
      Fixes provider NXDOMAIN spoofing. Works standalone and
      alongside any engine.

    ⭐ The engine choice does NOT depend on whether the service is
    running: a stopped nfqws remains the selected engine — the menu,
    Start/Stop and the status keep controlling IT. "Stop service" no
    longer switches the engine, and "Start" brings up the selected
    one. (The engine submenu shows two lines: "Selected: ..." and
    "Service: active/inactive".)

    The engines are mutually exclusive: nfqws would also intercept
    byedpi's traffic (double distortion breaks connections). The
    switch stops the other engine and removes its settings itself.

    While nfqws is active, byedpi-only menu items (parameter
    settings, builder, proxy, strategy search) are hidden from
    the menu — only the active engine's items are shown.
    nfqws parameters live in "Bypass engine → nfqws parameters"
    (zapret format: --dpi-desync=..., with examples and validation).

    🔍 STRATEGY SEARCH FOR EITHER ENGINE (v1.9+):
    In the "Strategy search" dialog pick the engine: byedpi is tested
    on a separate port (internet is not interrupted), nfqws — through
    the real service (each combo runs for ~10 seconds; success = all
    listed URLs open). nfqws mode uses the zapret format; found
    parameters are applied by the "Apply" button straight into
    nfqws.json + a service restart.

    ⭐ THE KEY OPERATING PRINCIPLE:

    Desync (bypass) parameters placed AFTER -A apply ONLY when
    blocking is detected (connection reset, timeout, TLS error).
    Regular sites pass through the proxy UNTOUCHED. Hence the
    correct template:

        -T3 -A torst -o1 -o25+s -r 1+s
        └─┬─┘ └──┬───┘ └──────┬──────┘
        timeout trigger   bypass methods
                    (only when blocked!)

    Methods placed BEFORE -A apply to EVERY connection
    indiscriminately and often break unblocked sites.

    📋 CIADPI PARAMETERS (MAIN):

    -i IP        listening IP (default 0.0.0.0 — all)
    -p PORT      local SOCKS proxy port (default 1080)
    -D           daemonize
    -w FILE      PID file
    -E           transparent proxy mode
    -c COUNT     concurrent connection limit (default 512)
    -N           deny domain resolving
    -U           deny UDP associations
    -I IP        outgoing bind IP (default ::)
    -b SIZE      buffer size (default 16384)
    -x LEVEL     debug level: 0 — none, 1 — basic, 2 — verbose
    -g TTL       TTL for all outgoing connections
    -F           TCP Fast Open

    AUTOMATIC MODE:
    -T SEC       wait N seconds for a reply, then auto triggers.
                 Format: sec[:pause:counter:bytes]
    -A MODE      TRIGGER: torst (reset/timeout), ssl_err (TLS error),
                 redirect (replaced reply), conn (no connection),
                 none (always). Several comma-separated: torst,ssl_err.
                 ⭐ Everything AFTER -A applies only on trigger!
    -L MODE      post-trigger behaviour — LETTERS ONLY:
                 s — cache working params for the IP,
                 o — reconnect on trigger,
                 n — do not reconnect.
                 Combinations comma-separated: s,o. Digits 0..3 DO NOT work!
    -u SEC       per-IP cached params TTL (86400 = a day)
    -y FILE      dump cache to a file (-y - to stdout)

    FILTERS:
    -K LIST      protocols: t(tls) h(http) u(udp) i(ipv4), e.g.: t,h
    -H FILE|:STR hosts whitelist (file or :string)
    -j FILE|:STR IP whitelist
    -V RANGE     destination port range, e.g. 80-443
    -R N         request number for the bypass, e.g. 1 or 1-3

    DESYNC METHODS — REPEATABLE, space-separated:
    Position format: offset[:repeats[:step]]+flags
    First flag: +s — from SNI, +h — from HTTP Host, +n — null byte.
    Second (optional): +e — from end, +m — middle,
    +r — random, +s — from start.
    -s POS       split — cut the packet at a position
    -d POS       disorder — cut and send parts in reverse order
    -o POS       oob — cut, send the first part as OOB data.
                 ⚠️ -oN is a position, NOT "method #N": -o1 -o25+s
                 means two cuts (byte 1 and 25 from SNI)
    -q POS       disoob — reverse order + OOB
    -f POS       fake — send a fake packet before the real one
                 (fake TTL: -t, content: -l, -n, -Q)
    -r POS       tlsrec — split the TLS record (ClientHello).
                 Classic: -r 1+s — cut inside the SNI

    FAKE PACKETS & MODIFICATIONS:
    -t TTL       fake packet TTL (default 8, usually 2–8)
    -S           add MD5 Signature to fakes
    -n STR       replace SNI in the fake (? — random letter, # — digit)
    -O POS       fake data start offset
    -l FILE|:STR custom fake data
    -Q FLAG      fake TLS modification: rand, orig, msize=N
    -e CHAR      custom OOB byte
    -M LIST      HTTP modification: h(hcsmix) d(dcsmix) r(rmspace)
    -m VER       TLS minor version
    -a COUNT     UDP fakes count (default 0)
    -Y           drop packets with SACK

    WORKING CONFIGURATION EXAMPLES (verified on byedpi):
    • -T3 -A torst -o1 -o25+s -r 1+s   (default: cuts only on
      blocking, regular sites stay clean)
    • -T2 -A torst -o2 -o15+s -r 2+s
    • -T1 -A torst -o1 -o5+s

    💡 TIPS:
    • If sites stopped opening — check the log: "unreach ip"
      means the ISP rejects OOB packets, remove the -oN methods
    • The Builder menu edits each parameter separately,
      with a "?" reference for each
    • Strategy search picks parameters automatically
    • The whitelist excludes domains from proxying
    • Update byedpi from the menu when new versions come out
''',
}


def _split_help_sections(text, lang):
    """Режет HELP_TEXTS-простыню на (header, body) секции.

    Секция начинается строкой с эмодзи-заголовком в верхнем регистре
    («    🎯 ОСНОВНЫЕ ВОЗМОЖНОСТИ:»). До первой такой строки — интро
    (header=None, показывается раскрытым).
    """
    import re
    # строка начинается с не-буквенного символа (эмодзи) и заканчивается
    # двоеточием — это заголовок секции (Python re не знает \p{So})
    header_re = re.compile(r'^\s*([^\w\s])[^\n]*:\s*$')
    intro, sections, cur_h, cur_b = [], [], None, []
    for line in text.splitlines():
        if header_re.match(line) and not line.strip().startswith('•'):
            if cur_h is not None:
                sections.append((cur_h, '\n'.join(cur_b).strip()))
            cur_h = line.strip()
            cur_b = []
        else:
            (intro if cur_h is None else cur_b).append(line)
    if cur_h is not None:
        sections.append((cur_h, '\n'.join(cur_b).strip()))
    return [(None, '\n'.join(intro).strip())] + sections


# ⭐ v1.9.1: секционная справка — общая часть + Gtk.Expander по темам.
# Строится из HELP_TEXTS автоматически (заголовки с эмодзи = секции).
HELP_SECTIONS = {
    lang: _split_help_sections(HELP_TEXTS[lang], lang)
    for lang in HELP_TEXTS
}


ABOUT_TEXTS = {
    'ru': """🔰 CIADPI Advanced Indicator v2.0.10

    📡 Продвинутый индикатор для управления сервисом обхода DPI

    🌟 ОСНОВНЫЕ ФУНКЦИИ:
    • Автоматизированное управление прокси
    • Оптимизация параметров (конструктор, поиск стратегии)
    • Поиск «до нахождения» — без лимита попыток
    • Двойной движок: byedpi (SOCKS) ↔ nfqws (NFQUEUE)
    • Мониторинг статуса в системном трее
    • Поддержка белого списка
    • Локализация RU/EN

    🛠️ ТЕХНОЛОГИИ:
    • Python 3 + GTK 3
    • AppIndicator3 / Gtk.StatusIcon
    • Интеграция с systemd
    • D-Bus integration

    📊 СИСТЕМНЫЕ ТРЕБОВАНИЯ:
    • Linux с systemd
    • GNOME или совместимая среда рабочего стола
    • Права sudo для управления сервисом (одноразовая настройка)

    🔗 ПРОЕКТ ОСНОВАН НА:
    • byedpi/ciadpi — https://github.com/hufrea/byedpi
    • nfqws (движок десинков) — https://github.com/bol-van/zapret
    • Идейно на лаунчере Zapret для windows с сайта https://topersoft.com
    • Теме на ru форуме Ubuntu по byeDPI (форум цензурный и не юзерфрендли,
      поэтому без ссылки на него соответственно)

    🔗 ЛИЦЕНЗИЯ: MIT License

    💻 РАЗРАБОТЧИК: Templard
""",
    'en': """🔰 CIADPI Advanced Indicator v2.0.10

    📡 Advanced tray indicator for managing a DPI bypass service

    🌟 KEY FEATURES:
    • Automated proxy management
    • Parameter tuning (builder, strategy search)
    • Until-found search — no attempt limit
    • Dual engine: byedpi (SOCKS) ↔ nfqws (NFQUEUE)
    • System tray status monitoring
    • Whitelist support
    • RU/EN localization

    🛠️ TECHNOLOGIES:
    • Python 3 + GTK 3
    • AppIndicator3 / Gtk.StatusIcon
    • systemd service integration
    • D-Bus integration

    📊 SYSTEM REQUIREMENTS:
    • Linux with systemd
    • GNOME or a compatible desktop environment
    • sudo rights for service control (one-time setup)

    🔗 PROJECT BASED ON:
    • byedpi/ciadpi — https://github.com/hufrea/byedpi
    • nfqws (desync engine) — https://github.com/bol-van/zapret
    • Conceptually inspired by the Zapret launcher for Windows (https://topersoft.com)
    • A thread on the Russian Ubuntu forum about byeDPI (the forum is moderated
      and not user-friendly, hence no direct link)

    🔗 LICENSE: MIT License

    💻 DEVELOPER: Templard
"""
}

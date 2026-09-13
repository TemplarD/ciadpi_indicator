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
    • Обновление движков из git (byedpi и nfqws) — кнопками в
      «Настройках приложения», с консольным окном этапов
    • RU/EN локализация, настройки уведомлений по категориям
    • Мониторинг статуса в трее, логи, диагностика (CLI:
      ciadpi_enginectl.py / ciadpi_profiles.py / diagnose_ciadpi.py)

    🛠️ ОБЩЕЕ УПРАВЛЕНИЕ СЕРВИСОМ:
    • Запуск/остановка/перезапуск выбранного режима (меню трея
      и окно «Режимы обхода» — через один бэкенд, без рассинхрона)
    • Мониторинг статуса в реальном времени
    • Проверка параметров перед применением (dry-run бинарником)

    🧩 РЕЖИМ BYEDPI (SOCKS5-прокси):
    • ciadpi — SOCKS4/5-прокси на 127.0.0.1:1080
    • Обходятся только приложения с настроенным прокси (режим
      «системный» настраивает GNOME; local — вручную)
    • Параметры — «🎛 Настройки режима»: строка, конструктор
      со справками «?», поиск стратегии
    • Белый список доменов исключает хосты из проксирования

    ⚡ ПАРАМЕТРЫ BYEDPI: ПОЛНЫЙ СПРАВОЧНИК:
    Полный перечень флагов ciadpi (-T/-A/-L/-s/-d/-o/-q/-f/-r,
    фильтры, fake-пакеты) — см. секцию «📋 ПАРАМЕТРЫ BYEDPI
    (СПРАВОЧНИК ФЛАГОВ)» ниже. Это параметры ИМЕННО byedpi;
    у nfqws — свой формат zapret (см. секцию nfqws).

    🛰️ ПОИСК СТРАТЕГИИ (по режиму):
    • byedpi тестируется на отдельном порту (интернет не
      прерывается), nfqws — через реальный сервис (каждая
      комбинация включается на ~10 секунд)
    • «Искать до нахождения» отключает лимит попыток: перебор
      продолжается, пока какая-нибудь комбинация НЕ ОТКРОЕТ ВСЕ
      указанные URL (частичный доступ успехом не считается)
    • «Мин. попыток» — нижний предел: даже если все URL открылись
      на первой комбинации, поиск проверит ещё несколько
    • Комбинации не кончаются: после известного набора и истории
      генератор выдаёт новые волны (60/120/180…), без повторов
    • Найденное — кнопкой «→ в строку параметров»

    🎛️ НАСТРОЙКИ РЕЖИМА (v2.0.7+):
    Один пункт меню «🎛 Настройки режима» — окно с тремя вкладками,
    содержимое строится под ВЫБРАННЫЙ режим:
    • «Параметры» — ручная строка + дефолт + примеры + 4 последних
      (свои для каждого режима, автообновление). Для snimod —
      редактор списка хостов.
    • «Конструктор» — регуляторы ключевых флагов со справками «?»
      по каждому (byedpi — полный; nfqws — 7 десинк-полей;
      snimod — хосты + мост; мост — upstream DoT).
    • «Поиск стратегии» — перебор параметров под выбранный режим.

    🗂 ПРОФИЛИ (v2.0.6+):
    «Профили» — снимки настроек для разных сетей: выбранный режим,
    параметры всех движков, состояние DNS-моста, настройки прокси.
    «Сохранить текущее как…» — снимок; «Применить» — поднимает
    сохранённое целиком (гасит лишнее, стартует нужное).

    ⚙ РЕЖИМЫ ОБХОДА (ОКНО ПЕРЕКЛЮЧЕНИЯ):
    «⚙ Режимы обхода» — окно с radio-строками, выбор кликом по всей
    строке, кнопки ▶ Запустить / ⏹ Остановить / ↻ Перезапустить
    действуют на ВЫБРАННЫЙ режим. Повторный запуск активного —
    no-op (не рестарт). Запуск одного режима гасит остальные.

    🟢 РЕЖИМ: BYEDPI — ПОДРОБНО:
    byedpi — SOCKS5-прокси 127.0.0.1. Обходится только трафик,
    явно направленный в прокси. Параметры — «🎛 Настройки режима».
    Главный принцип: параметры ДЕСИНХРОНИЗАЦИИ после -A применяются
    ТОЛЬКО при признаках блокировки (сброс, таймаут, ошибка TLS);
    обычные сайты проходят через прокси БЕЗ ИСКАЖЕНИЙ:
        -T3 -A torst -o1 -o25+s -r 1+s
        └─┬─┘ └──┬───┘ └──────┬──────┘
        таймаут триггер   методы обхода
                      (только при блокировке!)
    Методы, стоящие ДО -A, применяются ко ВСЕМ соединениям и часто
    ломают незаблокированные сайты.

    🟠 РЕЖИМ: NFQWS — ПОДРОБНО:
    nfqws — десинки zapret через NFQUEUE: искажает пакеты ВСЕХ
    приложений (порты 80/443), настройка приложений не нужна.
    Самый мощный против SNI/IP-фильтров прова. Параметры — формат
    zapret (--dpi-desync=…, --filter-tcp=…): строка ввода,
    конструктор 7 полей, поиск стратегии. Примеры:
    • --filter-tcp=80,443 --dpi-desync=disorder2 --dpi-desync-split-pos=1
    • --filter-tcp=443 --dpi-desync=multidisorder --dpi-desync-split-pos=midsld+1,midsld-1
    • --filter-tcp=80,443 --dpi-desync=fake,split2 --dpi-desync-fake-tls=1

    🟣 РЕЖИМ: SNIMOD — ПОДРОБНО:
    snimod — наш движок №3: поднимает РЕГИСТР SNI (www.youtube.com
    → WWW.YOUTUBE.COM). Пров режет по подстроке в нижнем регистре,
    серверу регистр безразличен (RFC 6066). Хосты — «Настройки
    режима» → «Параметры» (список, по одному в строке). snimod
    поднимает DNS-мост как свою часть (Wants=).

    🔵 РЕЖИМ: DNS-МОСТ (DoT) — ПОДРОБНО:
    Локальный DoT-резолвер 127.0.0.1:53 → upstream:853 (по
    умолчанию 1.1.1.1; сменить — «Настройки режима» →
    «Конструктор»). Чинит NXDOMAIN-подмену DNS прова. Работает
    сам по себе и вместе с любым движком.

    ⭐ ВЫБОР РЕЖИМА И СЕРВИС:
    Выбор режима НЕ зависит от того, запущен ли сервис: останов
    не сбрасывает выбранный режим, меню продолжает управлять
    именно им. Смена режима НЕ запускает его автоматически —
    стартуйте кнопкой в окне «Режимы обхода» или пунктом меню.
    Движки взаимоисключающие: nfqws перехватил бы и трафик byedpi
    (двойное искажение ломает соединения) — переключение само
    останавливает другой движок и снимает его настройки.

    🔌 ПРОКСИ: ДЛЯ КАКИХ РЕЖИМОВ НУЖЕН:
    • byedpi — прокси ОБЯЗАТЕЛЕН: это SOCKS5-прокси, без
      направления трафика в него обход не работает. Режим
      «системный» прописывает 127.0.0.1:1080 в GNOME (с бэкапом
      и автооткатом), «локальный» — приложения настраиваются
      вручную (браузер: FoxyProxy и т.п.).
    • nfqws — прокси НЕ НУЖЕН: движок перехватывает пакеты всех
      приложений на уровне ядра (NFQUEUE). При уходе на nfqws
      системный прокси сбрасывается автоматически (manual на
      мёртвом порте ломал бы браузеры).
    • snimod — прокси НЕ НУЖЕН: та же механика NFQUEUE, пакеты
      правятся на лету; приложения ни о чём не знают.
    • DNS-мост — прокси НЕ НУЖЕН: правится только DNS-трафик
      (UDP53 → DoT-853), страницы открываются напрямую.
    Белый список исключает домены из проксирования (byedpi).

    ⬆️ ОБНОВЛЕНИЕ ДВИЖКОВ (v2.0.11):
    Две кнопки в «Настройках приложения» — «Обновить byedpi» и
    «Обновить nfqws (запрет)». Каждое обновление открывает
    консольное окно с этапами и командами (git pull → make →
    рестарт), по завершении ждёт нажатия «Закрыть». Откат
    бинарника выполняется автоматически, если сервис не поднялся.

    📋 ПАРАМЕТРЫ BYEDPI (СПРАВОЧНИК ФЛАГОВ):

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
    • Конструктор правит каждый параметр отдельно, со справкой «?»
    • Поиск стратегии подбирает параметры автоматически
    • Обновляйте движки кнопками в «Настройках приложения»
''',
    'en': '''📚 CIADPI Advanced Indicator — Full Reference

    🎯 CORE FEATURES (full list):

    • FOUR bypass modes: byedpi (SOCKS5), nfqws (zapret desyncs),
      snimod (our SNI case-mod), DNS bridge (DoT)
    • Mode window: radio rows (click anywhere), Start/Stop/Restart
      act on the SELECTED mode, re-start of active = no-op
    • Mode settings: Parameters / Builder (with "?" hints) /
      Strategy search — built for the selected mode
    • Profiles: snapshots "mode+params+bridge+proxy" under a name,
      one-click apply for different networks/places
    • Whitelist: exclusion from proxy (byedpi) and from DPI
      bypass (nfqws: nft-set, domains resolved automatically)
    • Strategy search: limited or until-found, DoH resolving,
      200-run history
    • Smart proxy: system/local-only, GNOME backup & restore
    • Engine updates from git (byedpi and nfqws) — buttons in
      Application Settings, with a console window of stages
    • RU/EN localization, per-category notifications
    • Tray status, logs, diagnostics (CLI: ciadpi_enginectl.py)

    🛠️ SERVICE CONTROL (COMMON):
    • Start/stop/restart of the selected mode (tray menu and the
      Mode window go through one backend — never out of sync)
    • Real-time status monitoring
    • Parameter validation before applying (binary dry-run)

    🟢 MODE: BYEDPI — DETAILS:
    byedpi is a SOCKS5 proxy at 127.0.0.1:1080; only proxied apps
    are bypassed. Key principle: desync parameters placed AFTER -A
    apply ONLY when blocking is detected; regular sites pass
    through the proxy untouched:
        -T3 -A torst -o1 -o25+s -r 1+s
        └─┬─┘ └──┬───┘ └──────┬──────┘
        timeout trigger   bypass methods
                    (only when blocked!)
    Methods before -A apply to every connection and often break
    unblocked sites.

    🟠 MODE: NFQWS — DETAILS:
    nfqws — zapret desyncs via NFQUEUE: distorts packets of ALL
    applications (ports 80/443), zero app configuration. The most
    powerful against SNI/IP filters. Parameters use the zapret
    format (--dpi-desync=…, --filter-tcp=…): entry line, 7-field
    builder, strategy search.

    🟣 MODE: SNIMOD — DETAILS:
    Our engine #3: uppercases the SNI (www.youtube.com →
    WWW.YOUTUBE.COM). Hosts — "Mode settings" → "Parameters".
    snimod brings up the DNS bridge as its part (Wants=).

    🔵 MODE: DNS BRIDGE (DoT) — DETAILS:
    Local DoT resolver 127.0.0.1:53 → upstream:853 (default
    1.1.1.1; change in "Mode settings" → "Builder"). Fixes provider
    NXDOMAIN spoofing. Works standalone and alongside any engine.

    ⭐ MODE CHOICE AND SERVICE:
    The mode choice does NOT depend on whether the service runs:
    stopping does not reset the selected mode. Switching does NOT
    auto-start — press Start in the Mode window. Engines are
    mutually exclusive (double distortion breaks connections);
    switching stops the other engine itself.

    🛰️ STRATEGY SEARCH (per mode):
    byedpi is tested on a separate port (internet not interrupted),
    nfqws — through the real service (each combo ~10 seconds).
    "Until found" removes the limit: the search continues until a
    combination opens ALL listed URLs; partial access does not
    count. "Min attempts" is a floor against a fluke. Combinations
    never run out: new waves (60/120/180…) keep coming.

    🧩 MODES WINDOW / PROFILES / WHITELIST:
    • Mode window — radio rows, buttons act on the selected mode
    • Profiles — snapshots for different networks, one-click apply
    • Whitelist excludes domains from proxying (byedpi)

    🔌 PROXY: WHICH MODES NEED IT:
    • byedpi — proxy REQUIRED: it IS a SOCKS5 proxy; without
      directing traffic into it nothing is bypassed. "System" mode
      sets 127.0.0.1:1080 in GNOME (backup + auto-rollback),
      "local" — configure apps manually (browser: FoxyProxy etc.)
    • nfqws — proxy NOT needed: packets are intercepted at the
      kernel level (NFQUEUE). Switching to nfqws resets the
      system proxy automatically.
    • snimod — proxy NOT needed: same NFQUEUE mechanics, packets
      are patched on the fly.
    • DNS bridge — proxy NOT needed: only DNS traffic is fixed
      (UDP53 → DoT-853), pages open directly.

    ⬆️ ENGINE UPDATES (v2.0.11):
    Two buttons in Application Settings — "Update byedpi" and
    "Update nfqws (zapret)". Each opens a console window with
    stages and commands (git pull → make → service restart) and
    waits for "Close" when finished. Binary rollback is automatic
    if the service fails to start.

    📋 BYEDPI PARAMETERS (FLAG REFERENCE):

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
    • The Builder edits each parameter separately, with a "?"
    • Strategy search picks parameters automatically
    • Update the engines with buttons in Application Settings
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
'ru': """🔰 CIADPI Advanced Indicator v2.0.14

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
    'en': """🔰 CIADPI Advanced Indicator v2.0.14

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

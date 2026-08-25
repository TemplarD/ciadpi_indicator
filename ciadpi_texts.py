#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Полные тексты справки и «О программе» на RU и EN."""

HELP_TEXTS = {
    'ru': """📚 CIADPI Advanced Indicator — Полная справка

    🎯 ОСНОВНЫЕ ВОЗМОЖНОСТИ:

    🛠️ Управление сервисом:
    • Запуск/остановка/перезапуск сервиса CIADPI
    • Мониторинг статуса в реальном времени
    • Применение параметров вручную или через поиск стратегии

    🔌 Умное управление прокси:
    • Автоматическая настройка системного прокси
    • Резервное копирование оригинальных настроек
    • Восстановление настроек при остановке
    • Поддержка белого списка доменов
    • Локальный режим без изменения системных настроек

    ⚡ Оптимизация параметров:
    • Встроенная проверка параметров CIADPI
    • Конструктор параметров с регуляторами (меню «Конструктор»)
    • Поиск стратегии перебором (меню «Поиск стратегии»)
    • Готовые примеры конфигураций
    • История тестирования

    📋 ПАРАМЕТРЫ CIADPI (ОСНОВНЫЕ):

    -i IP        целевой IP прослушивания (default 0.0.0.0)
    -p PORT      порт локального прокси (default 1080)
    -D           демонизация (фоновый режим)
    -w FILE      файл PID
    -E           прозрачный режим прокси
    -c COUNT     лимит соединений (default 512)
    -N           запретить резолвинг доменов
    -U           запретить UDP
    -I IP        IP исходящих соединений (default ::)
    -b SIZE      размер буфера (default 16384)
    -x LEVEL     уровень отладки 0/1/2
    -g TTL       TTL для всех исходящих соединений
    -F           TCP Fast Open

    АВТОМАТИЧЕСКИЙ РЕЖИМ:
    -T SEC       таймаут ожидания ответа до срабатывания auto
    -A MODE      триггер: torst, redirect, ssl_err, none, conn
    -L MODE      поведение после триггера: 0..3
    -u SEC       TTL кэша подобранных параметров для IP

    ФИЛЬТРЫ:
    -K LIST      протоколы: t(tls) h(http) u(udp) i(ipv4), пример: t,h
    -H FILE|:STR белый список хостов
    -j FILE|:STR белый список IP
    -V RANGE     диапазон портов, например 80-443
    -R N         номер запроса для применения обхода, например 1 или 1-3

    МЕТОДЫ ОБХОДА (desync):
    -s POS       split — разделение пакета на позиции;
                 формат: смещение[:повторы:шаг]+флаги;
                 флаги: +s(SNI) +h(HTTP host) +n(null) +e(end) +m(middle)
    -d POS       disorder — отправка частей в обратном порядке
    -o POS       OOB — отправка как out-of-band данных
    -q POS       disoob — обратный порядок + OOB
    -f POS       fake — отправка поддельного пакета перед настоящим
    -oN          числовые методы обхода: -o1 … -o25 с суффиксами s/m/e,
                 например: -o1 -o25+s

    FAKE-ПАКЕТЫ И МОДИФИКАЦИИ:
    -t TTL       TTL fake-пакетов (default 8)
    -S           добавлять MD5 Signature к fake-пакетам
    -n STR       подмена SNI в fake (? = случайная буква, # = цифра)
    -O POS       смещение начала fake-данных
    -l FILE|:STR кастомные fake-данные
    -Q FLAG      модификация fake TLS: rand, orig, msize=N
    -e CHAR      кастомный OOB-байт
    -M LIST      модификация HTTP: h(hcsmix) d(dcsmix) r(rmspace), пример: h,d
    -r POS       разбиение TLS record на позиции
    -m VER       минорная версия TLS
    -a COUNT     количество UDP-fake (default 0)
    -Y           отбрасывать пакеты с SACK

    ПРИМЕРЫ РАБОЧИХ КОНФИГУРАЦИЙ:
    • -o1 -o25+s -T3 -At o--tlsrec 1+s
    • -o2 -o15+s -T2 -At o--tlsrec
    • -o3 -o20+s -T3 -At o--tlsrec 2+s

    💡 СОВЕТЫ:
    • Используйте примеры для быстрого старта
    • Включите автоотключение прокси для ноутбуков
    • Настройте белый список для локальных ресурсов
    • Проверяйте логи при возникновении проблем
    • Обновляйте byedpi через меню при выходе новых версий
""",
    'en': """📚 CIADPI Advanced Indicator — Full Reference

    🎯 CORE FEATURES:

    🛠️ Service control:
    • Start/stop/restart of the CIADPI service
    • Real-time status monitoring
    • Apply parameters manually or via strategy search

    🔌 Smart proxy management:
    • Automatic system proxy configuration
    • Backup of original settings
    • Restore on stop
    • Domain whitelist support
    • Local mode without touching system settings

    ⚡ Parameter tuning:
    • Built-in CIADPI parameter validation
    • Parameter builder with controls (Builder menu)
    • Brute-force strategy search (Strategy search menu)
    • Ready-made configuration examples
    • Test history

    📋 CIADPI PARAMETERS (MAIN):

    -i IP        listening IP (default 0.0.0.0)
    -p PORT      local proxy port (default 1080)
    -D           daemonize
    -w FILE      PID file
    -E           transparent proxy mode
    -c COUNT     connection limit (default 512)
    -N           deny domain resolving
    -U           deny UDP
    -I IP        outgoing bind IP (default ::)
    -b SIZE      buffer size (default 16384)
    -x LEVEL     debug level 0/1/2
    -g TTL       TTL for all outgoing connections
    -F           TCP Fast Open

    AUTOMATIC MODE:
    -T SEC       response timeout before auto triggers
    -A MODE      trigger: torst, redirect, ssl_err, none, conn
    -L MODE      post-trigger behaviour: 0..3
    -u SEC       per-IP desync params cache TTL

    FILTERS:
    -K LIST      protocols: t(tls) h(http) u(udp) i(ipv4), e.g.: t,h
    -H FILE|:STR hosts whitelist
    -j FILE|:STR IP whitelist
    -V RANGE     port range, e.g. 80-443
    -R N         request number to apply desync to, e.g. 1 or 1-3

    DESYNC METHODS:
    -s POS       split — split the packet at position;
                 format: offset[:repeats:step]+flags;
                 flags: +s(SNI) +h(HTTP host) +n(null) +e(end) +m(middle)
    -d POS       disorder — send parts in reverse order
    -o POS       OOB — send as out-of-band data
    -q POS       disoob — reverse order + OOB
    -f POS       fake — send a fake packet before the real one
    -oN          numeric desync methods: -o1 … -o25 with s/m/e suffixes,
                 e.g.: -o1 -o25+s

    FAKE PACKETS & MODIFICATIONS:
    -t TTL       fake packet TTL (default 8)
    -S           add MD5 Signature option to fakes
    -n STR       replace SNI in fake (? = random letter, # = random digit)
    -O POS       fake data start offset
    -l FILE|:STR custom fake data
    -Q FLAG      fake TLS modification: rand, orig, msize=N
    -e CHAR      custom OOB byte
    -M LIST      HTTP modification: h(hcsmix) d(dcsmix) r(rmspace), e.g.: h,d
    -r POS       TLS record splitting at position
    -m VER       TLS minor version
    -a COUNT     UDP fakes count (default 0)
    -Y           drop packets with SACK extension

    WORKING CONFIGURATION EXAMPLES:
    • -o1 -o25+s -T3 -At o--tlsrec 1+s
    • -o2 -o15+s -T2 -At o--tlsrec
    • -o3 -o20+s -T3 -At o--tlsrec 2+s

    💡 TIPS:
    • Use examples for a quick start
    • Enable proxy auto-disable on laptops
    • Set up a whitelist for local resources
    • Check logs when troubleshooting
    • Update byedpi from the menu when new versions come out
"""
}


ABOUT_TEXTS = {
    'ru': """🔰 CIADPI Advanced Indicator v1.5

    📡 Продвинутый индикатор для управления сервисом обхода DPI

    🌟 ОСНОВНЫЕ ФУНКЦИИ:
    • Автоматизированное управление прокси
    • Оптимизация параметров (конструктор, поиск стратегии)
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
    • Идейно на лаунчере Zapret для windows с сайта https://topersoft.com
    • Теме на ru форуме Ubuntu по byeDPI (форум цензурный и не юзерфрендли,
      поэтому без ссылки на него соответственно)

    🔗 ЛИЦЕНЗИЯ: MIT License

    💻 РАЗРАБОТЧИК: Templard
""",
    'en': """🔰 CIADPI Advanced Indicator v1.5

    📡 Advanced tray indicator for managing a DPI bypass service

    🌟 KEY FEATURES:
    • Automated proxy management
    • Parameter tuning (builder, strategy search)
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
    • Conceptually inspired by the Zapret launcher for Windows (https://topersoft.com)
    • A thread on the Russian Ubuntu forum about byeDPI (the forum is moderated
      and not user-friendly, hence no direct link)

    🔗 LICENSE: MIT License

    💻 DEVELOPER: Templard
"""
}

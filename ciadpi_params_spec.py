#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Описание регулируемых параметров ciadpi для GUI-конструктора.
Каждый элемент: ключ i18n, тип контрола, диапазон, сборка/разбор строки параметров.
"""

import re

# ---------------------------------------------------------------
# Определения контролов.
# kind: 'spin'  — числовой регулятор (min, max, step, default)
#       'entry' — текстовое поле (placeholder)
#       'combo' — выпадающий список (варианты: (значение, подпись))
#       'check' — галочка
# flag: как добавлять в строку ('value' -> '-X VAL', 'bool' -> '-X')
# ---------------------------------------------------------------

CONTROLS = [
    # ---------- Основные ----------
    dict(group='builder.group_main', key='builder.port', opt='-p', kind='spin',
         min=1, max=65535, step=1, default=1080),
    dict(group='builder.group_main', key='builder.maxconn', opt='-c', kind='spin',
         min=1, max=65535, step=16, default=None),   # None = не добавлять
    dict(group='builder.group_main', key='builder.bufsize', opt='-b', kind='spin',
         min=512, max=1048576, step=512, default=None),
    dict(group='builder.group_main', key='builder.debug', opt='-x', kind='spin',
         min=0, max=2, step=1, default=None),

    # ---------- Desync ----------
    dict(group='builder.group_desync', key='builder.oob_n', opt='-oN', kind='entry',
         placeholder='-o1 -o25+s -T3 ...'),
    dict(group='builder.group_desync', key='builder.split', opt='-s', kind='entry',
         placeholder='1+s / 3:2:2+h / пусто'),
    dict(group='builder.group_desync', key='builder.disorder', opt='-d', kind='entry',
         placeholder='1 / 2+s / пусто'),
    dict(group='builder.group_desync', key='builder.oob', opt='-o', kind='entry',
         placeholder='1 / 2+s / пусто'),
    dict(group='builder.group_desync', key='builder.disoob', opt='-q', kind='entry',
         placeholder='1 / пусто'),
    dict(group='builder.group_desync', key='builder.fake', opt='-f', kind='entry',
         placeholder='1 / 3+s / пусто'),

    # ---------- Авто-режим ----------
    dict(group='builder.group_auto', key='builder.timeout', opt='-T', kind='spin',
         min=0, max=60, step=1, default=None),
    dict(group='builder.group_auto', key='builder.auto', opt='-A', kind='combo',
         variants=[('', '—'), ('torst', 'torst'), ('ssl_err', 'ssl_err'),
                   ('redirect', 'redirect'), ('conn', 'conn'), ('none', 'none')]),
    dict(group='builder.group_auto', key='builder.automode', opt='-L', kind='spin',
         min=0, max=3, step=1, default=None),
    dict(group='builder.group_auto', key='builder.cachettl', opt='-u', kind='spin',
         min=0, max=604800, step=100, default=None),

    # ---------- Фильтры ----------
    dict(group='builder.group_filters', key='builder.proto', opt='-K', kind='combo',
         variants=[('', '—'), ('t', 't (tls)'), ('h', 'h (http)'), ('u', 'u (udp)'),
                   ('i', 'i (ipv4)'), ('t,h', 't,h'), ('t,u', 't,u'), ('h,i', 'h,i')]),
    dict(group='builder.group_filters', key='builder.pf', opt='-V', kind='entry',
         placeholder='80-443 / 443 / пусто'),
    dict(group='builder.group_filters', key='builder.round', opt='-R', kind='entry',
         placeholder='1 / 1-3 / пусто'),

    # ---------- Fake и модификации ----------
    dict(group='builder.group_fake', key='builder.ttl', opt='-t', kind='spin',
         min=1, max=255, step=1, default=None),
    dict(group='builder.group_fake', key='builder.tlsrec', opt='-r', kind='entry',
         placeholder='1 / 2+s / пусто'),
    dict(group='builder.group_fake', key='builder.udpfake', opt='-a', kind='spin',
         min=0, max=16, step=1, default=None),
    dict(group='builder.group_fake', key='builder.md5sig', opt='-S', kind='check'),
    dict(group='builder.group_fake', key='builder.dropsack', opt='-Y', kind='check'),
    dict(group='builder.group_fake', key='builder.modhttp', opt='-M', kind='combo',
         variants=[('', '—'), ('h', 'h (hcsmix)'), ('d', 'd (dcsmix)'),
                   ('r', 'r (rmspace)'), ('h,d', 'h,d'), ('h,d,r', 'h,d,r')]),
    dict(group='builder.group_fake', key='builder.fakemod', opt='-Q', kind='combo',
         variants=[('', '—'), ('rand', 'rand'), ('orig', 'orig')]),
]

# Короткая подсказка «?» — куда смотреть в полной справке
HELP_SECTIONS = {
    'builder.group_main':   'ОСНОВНЫЕ ПАРАМЕТРЫ',
    'builder.group_desync': 'МЕТОДЫ ОБХОДА',
    'builder.group_auto':   'АВТОМАТИЧЕСКИЙ РЕЖИМ',
    'builder.group_filters': 'ФИЛЬТРЫ',
    'builder.group_fake':   'FAKE-ПАКЕТЫ И МОДИФИКАЦИИ',
}


def parse_params(params_str):
    """Разбор строки параметров в словарь {opt: значение}.

    Прикреплённые значения (-T3) разворачиваются в отдельные записи.
    Повторяющиеся опции (-o1 -o25+s) собираются в список значений через пробел
    только для -oN; остальные — последнее вхождение.
    """
    if not params_str or not params_str.strip():
        return {}

    bool_flags = {'-D', '-E', '-N', '-U', '-F', '-S', '-Y'}
    val_flags = {'-i', '-p', '-w', '-c', '-I', '-b', '-g', '-T', '-A', '-L',
                 '-u', '-y', '-K', '-H', '-j', '-V', '-R', '-s', '-d', '-o',
                 '-q', '-f', '-r', '-t', '-O', '-l', '-e', '-n', '-Q', '-M',
                 '-a', '-x'}

    result = {}
    tokens = params_str.split()
    i = 0
    while i < len(tokens):
        tok = tokens[i]

        # спецформа o--tlsrec N
        if tok == 'o--tlsrec':
            result.setdefault('o--tlsrec', [])
            if i + 1 < len(tokens):
                result['o--tlsrec'].append(tokens[i + 1])
                i += 2
            else:
                i += 1
            continue

        # прикреплённое значение флага: -T3, -At, -L1, -o25+s
        m = re.match(r'^(-[A-Za-z])(.+)$', tok)
        if m and m.group(1) in val_flags and m.group(2) not in bool_flags:
            result[m.group(1)] = m.group(2)
            i += 1
            continue

        if tok in bool_flags:
            result[tok] = True
            i += 1
            continue

        if tok in val_flags:
            val = tokens[i + 1] if i + 1 < len(tokens) else ''
            result[tok] = [val]
            i += 2 if i + 1 < len(tokens) else 1
            continue

        # неизвестный токен — пропускаем
        i += 1

    return result


def get_value(parsed, opt):
    """Достать значение опции из parsed (список -> строка)."""
    v = parsed.get(opt)
    if v is None:
        return None
    if isinstance(v, list):
        return ' '.join(x for x in v if x)
    return v


def build_params(widgets):
    """Собрать строку параметров из {opt: value_or_None}."""
    parts = []

    oN = widgets.get('-oN')
    if oN:
        parts.append(oN.strip())

    for opt, val in widgets.items():
        if opt == '-oN' or not val:
            continue
        if val is True:
            parts.append(opt)
        else:
            val = str(val).strip()
            if val:
                parts.append(f"{opt} {val}")

    # спецформа o--tlsrec N
    tlsrec_special = widgets.get('o--tlsrec')
    if tlsrec_special:
        parts.append(f"o--tlsrec {tlsrec_special}")

    return ' '.join(parts).strip()

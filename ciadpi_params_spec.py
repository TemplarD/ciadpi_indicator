#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Описание регулируемых параметров ciadpi для GUI-конструктора.
Каждый элемент: ключ i18n, тип контрола, диапазон, сборка/разбор строки параметров.

Семантика синхронизирована с текущим byedpi (main.c):
- -o/-s/-d/-q/-f/-r — ПОВТОРЯЕМЫЕ методы desync (список позиций);
- -A <trig> начинает новую группу: методы ПОСЛЕ -A применяются
  только при срабатывании триггера;
- -L принимает буквы s, o, n (не цифры).
"""

import re

# ---------------------------------------------------------------
# Определения контролов.
# kind: 'spin'  — числовой регулятор (min, max, step, default)
#       'entry' — текстовое поле (placeholder); для repeatable —
#                 список значений через пробел
#       'combo' — выпадающий список (варианты: (значение, подпись))
#       'check' — галочка
# repeatable: True — флаг может встречаться в строке несколько раз
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

    # ---------- Desync (методы — повторяемые списки) ----------
    dict(group='builder.group_desync', key='builder.oob_n', opt='-oN', kind='entry',
         repeatable=True, attached=True,
         placeholder='-o1 -o25+s  (позиции через пробел)'),
    dict(group='builder.group_desync', key='builder.split', opt='-s', kind='entry',
         repeatable=True,
         placeholder='1+s / 3:2:2+h / список через пробел'),
    dict(group='builder.group_desync', key='builder.disorder', opt='-d', kind='entry',
         repeatable=True,
         placeholder='1 / 2+s / список через пробел'),
    dict(group='builder.group_desync', key='builder.disoob', opt='-q', kind='entry',
         repeatable=True,
         placeholder='1+s / список через пробел'),
    dict(group='builder.group_desync', key='builder.fake', opt='-f', kind='entry',
         repeatable=True,
         placeholder='1 / 3+s / список через пробел'),

    # ---------- Авто-режим ----------
    dict(group='builder.group_auto', key='builder.timeout', opt='-T', kind='spin',
         min=0, max=60, step=1, default=None),
    dict(group='builder.group_auto', key='builder.auto', opt='-A', kind='combo',
         separate=True,
         variants=[('', '—'), ('torst', 'torst'), ('ssl_err', 'ssl_err'),
                   ('redirect', 'redirect'), ('conn', 'conn'), ('none', 'none')]),
    dict(group='builder.group_auto', key='builder.automode', opt='-L', kind='combo',
         separate=True,
         variants=[('', '—'), ('s', 's'), ('o', 'o'), ('n', 'n'),
                   ('s,o', 's,o'), ('s,n', 's,n')]),
    dict(group='builder.group_auto', key='builder.cachettl', opt='-u', kind='spin',
         min=0, max=604800, step=100, default=None),

    # ---------- Фильтры ----------
    dict(group='builder.group_filters', key='builder.proto', opt='-K', kind='combo',
         separate=True,
         variants=[('', '—'), ('t', 't (tls)'), ('h', 'h (http)'), ('u', 'u (udp)'),
                   ('i', 'i (ipv4)'), ('t,h', 't,h'), ('t,u', 't,u'), ('h,i', 'h,i')]),
    dict(group='builder.group_filters', key='builder.pf', opt='-V', kind='entry',
         separate=True, placeholder='80-443 / 443 / пусто'),
    dict(group='builder.group_filters', key='builder.round', opt='-R', kind='entry',
         separate=True, placeholder='1 / 1-3 / пусто'),

    # ---------- Fake и модификации ----------
    dict(group='builder.group_fake', key='builder.ttl', opt='-t', kind='spin',
         min=1, max=255, step=1, default=None),
    dict(group='builder.group_fake', key='builder.tlsrec', opt='-r', kind='entry',
         repeatable=True,
         placeholder='1 / 2+s / список через пробел'),
    dict(group='builder.group_fake', key='builder.udpfake', opt='-a', kind='spin',
         min=0, max=16, step=1, default=None),
    dict(group='builder.group_fake', key='builder.md5sig', opt='-S', kind='check'),
    dict(group='builder.group_fake', key='builder.dropsack', opt='-Y', kind='check'),
    dict(group='builder.group_fake', key='builder.modhttp', opt='-M', kind='combo',
         separate=True,
         variants=[('', '—'), ('h', 'h (hcsmix)'), ('d', 'd (dcsmix)'),
                   ('r', 'r (rmspace)'), ('h,d', 'h,d'), ('h,d,r', 'h,d,r')]),
    dict(group='builder.group_fake', key='builder.fakemod', opt='-Q', kind='combo',
         separate=True,
         variants=[('', '—'), ('rand', 'rand'), ('orig', 'orig')]),
]

# Флаги, принимающие значение (для parse/update)
VAL_FLAGS = {'-i', '-p', '-w', '-c', '-I', '-b', '-g', '-T', '-A', '-L',
             '-u', '-y', '-K', '-H', '-j', '-V', '-R', '-s', '-d', '-o',
             '-q', '-f', '-r', '-t', '-O', '-l', '-e', '-n', '-Q', '-M',
             '-a', '-x'}
BOOL_FLAGS = {'-D', '-E', '-N', '-U', '-F', '-S', '-Y'}

# Повторяемые методы desync: в строке встречаются многократно,
# прикреплённая форма (-o25+s) — каноничная
REPEATABLE = {'-s', '-d', '-o', '-q', '-f', '-r'}

# Методы после -A применяются только при триггере; новые методы
# desync вставляем после -A (группа триггера), а не в безусловную группу
DESYNC_GROUPS = {'builder.group_desync', 'builder.group_fake'}

# Спец-поле '-oN' в GUI = все OOB-позиции (-o) строки сразу
OON_FIELD = '-oN'


# Короткая подсказка «?» — куда смотреть в полной справке
HELP_SECTIONS = {
    'builder.group_main':   'ОСНОВНЫЕ ПАРАМЕТРЫ',
    'builder.group_desync': 'МЕТОДЫ ОБХОДА',
    'builder.group_auto':   'АВТОМАТИЧЕСКИЙ РЕЖИМ',
    'builder.group_filters': 'ФИЛЬТРЫ',
    'builder.group_fake':   'FAKE-ПАКЕТЫ И МОДИФИКАЦИИ',
}


def parse_params(params_str):
    """Разбор строки параметров в словарь {opt: значение|список}.

    Повторяемые методы (-s/-d/-o/-q/-f/-r) собираются в СПИСОК всех
    значений (прикреплённые и раздельные); OOB-позиции -oX попадают
    в ключ '-oN'. Остальные флаги: последнее вхождение (список из 1
    элемента для совместимости с get_value).
    """
    if not params_str or not params_str.strip():
        return {}

    result = {}

    def add_single(flag, val):
        result[flag] = [val] if val else ['']

    def add_repeat(flag, val):
        result.setdefault(flag, [])
        if val:
            result[flag].append(val)

    tokens = params_str.split()
    i = 0
    while i < len(tokens):
        tok = tokens[i]

        # легаси-токены старых версий — пропускаем молча
        if tok == 'o--tlsrec' or tok.startswith('o--'):
            i += 1
            continue
        # голое значение-позиция (1+s) — продолжение предыдущего флага
        if re.match(r'^-?\d+(:\d+)?(:\d+)?(\+[shn][emrs]?)?$', tok):
            i += 1
            continue

        if tok in BOOL_FLAGS:
            result[tok] = True
            i += 1
            continue

        # прикреплённое значение: -T3, -At, -o25+s, -L s (нет: -Ls)
        m = re.match(r'^(-[A-Za-z])(.+)$', tok)
        if m and m.group(1) in VAL_FLAGS:
            flag, val = m.group(1), m.group(2)
            if flag in REPEATABLE:
                # -o25+s / -s1+s — метод с прикреплённой позицией
                if flag == '-o':
                    add_repeat(OON_FIELD, val)
                else:
                    add_repeat(flag, val)
            else:
                add_single(flag, val)
            i += 1
            continue

        # раздельный флаг + значение
        if tok in VAL_FLAGS:
            val = tokens[i + 1] if i + 1 < len(tokens) else ''
            # значение не может быть следующим флагом (кроме позиций -f -1)
            if val.startswith('-') and not re.match(r'^-\d', val):
                add_single(tok, '')
                i += 1
                continue
            if tok in REPEATABLE:
                if tok == '-o':
                    add_repeat(OON_FIELD, val)
                else:
                    add_repeat(tok, val)
            else:
                add_single(tok, val)
            i += 2
            continue

        # неизвестный токен — пропускаем (сохранится в строке как есть)
        i += 1

    return result


def get_value(parsed, opt):
    """Достать значение опции из parsed (список -> строка через пробел)."""
    v = parsed.get(opt)
    if v is None:
        return None
    if isinstance(v, list):
        return ' '.join(x for x in v if x)
    return v


def _is_oob_token(tok):
    """Токен вида -o25+s / -o1 (прикреплённая OOB-позиция)."""
    return re.match(r'^-o\d+(:\d+)?(:\d+)?(\+[a-z]+)?$', tok) is not None


def update_param_in_string(params_str, opt, value, group=None):
    """Хирургическая замена ОДНОГО параметра в строке.

    Не трогает остальные токены и их порядок — правка одного поля
    конструктора больше не ломает всю строку.

    opt:   ключ из CONTROLS ('-p', '-T', '-oN', '-A', ...)
    value: None | '' | False — удалить параметр из строки;
           True  — bool-флаг (вставить токен без значения);
           str   — новое значение (список через пробел для repeatable).
    group: группа из spec — определяет точку вставки отсутствующего
           параметра (методы desync — после -A, в группу триггера).
    """
    tokens = params_str.split()

    spec = next((c for c in CONTROLS if c['opt'] == opt), {})
    repeatable = bool(spec.get('repeatable'))
    separate = bool(spec.get('separate'))

    # --- что считаем «нашим» флагом в строке ---
    if opt == OON_FIELD:
        flag = '-o'
        is_mine = _is_oob_token
    else:
        flag = opt
        is_mine = (lambda t, f=flag: t == f)

    # --- найти все вхождения флага, запомнить форму и позицию ---
    occurrences = []   # (index, attached_value|None, separate_value|None)
    i = 0
    while i < len(tokens):
        tok = tokens[i]
        # совпадение: точный токен ИЛИ прикреплённая форма -T3/-At
        attached_m = re.match(r'^(-[A-Za-z])(.+)$', tok)
        is_hit = (tok == flag) or (
            attached_m and attached_m.group(1) == flag
            and not _is_oob_token(tok) if flag != '-o' else False
        ) if opt != OON_FIELD else _is_oob_token(tok)
        if is_hit:
            if opt == OON_FIELD:
                occurrences.append((i, tok[2:], None))
                i += 1
                continue
            # прикреплённая форма -T3/-At?
            if attached_m and attached_m.group(1) == flag and len(tok) > 2:
                occurrences.append((i, tok[2:], None))
                i += 1
                continue
            if repeatable or tok not in VAL_FLAGS:
                occurrences.append((i, None, None))
                i += 1
                continue
            # раздельная форма: значение следующим токеном?
            if i + 1 < len(tokens) and not tokens[i + 1].startswith('-'):
                occurrences.append((i, None, tokens[i + 1]))
                i += 2
                continue
            occurrences.append((i, None, None))
            i += 1
            continue
        i += 1

    # --- значение -> список новых токенов флага ---
    def build_new_tokens(val):
        if val is True:
            return [flag]
        val = str(val).strip()
        if not val:
            return []
        if repeatable:
            out = []
            for piece in val.split():
                if piece.startswith('-o') or piece.startswith('-s') or \
                        piece.startswith('-d') or piece.startswith('-q') or \
                        piece.startswith('-f') or piece.startswith('-r'):
                    out.append(piece)         # юзер вписал готовые токены
                else:
                    out.append(flag + piece)  # прикреплённая форма
            return out
        if separate:
            return [flag, val]
        return [flag + val]                     # прикреплённая: -T3

    # --- удаление/замена ---
    new_tokens = build_new_tokens(value) if value not in (None, '', False) else []

    if occurrences:
        first_idx = occurrences[0][0]
        remove = set()
        for idx, attached, sep_val in occurrences:
            remove.add(idx)
            if sep_val is not None:
                remove.add(idx + 1)
        out = [t for j, t in enumerate(tokens) if j not in remove]
        insert_at = first_idx
        # для repeatable-спецполя: вставляем туда, где был первый токен
        return ' '.join(out[:insert_at] + new_tokens + out[insert_at:]).strip()

    # --- параметра в строке нет: выбираем точку вставки ---
    if not new_tokens:
        return ' '.join(tokens).strip()

    insert_at = None
    if group in DESYNC_GROUPS:
        # методы desync вставляем ПОСЛЕ -A (в группу триггера);
        # -A torst (отдельное значение) — пропускаем и его
        i = 0
        while i < len(tokens):
            tok = tokens[i]
            if tok == '-A':
                if i + 1 < len(tokens) and not tokens[i + 1].startswith('-'):
                    insert_at = i + 2
                else:
                    insert_at = i + 1
                break
            m = re.match(r'^-A(.+)$', tok)
            if m:
                insert_at = i + 1
                break
            i += 1

    if insert_at is None:
        insert_at = len(tokens)

    return ' '.join(tokens[:insert_at] + new_tokens + tokens[insert_at:]).strip()


def build_params(widgets):
    """Собрать строку из {opt: value} (legacy, для совместимости)."""
    parts = []
    for opt, val in widgets.items():
        if not val:
            continue
        if val is True:
            parts.append(opt)
        else:
            parts.append(update_param_in_string('', opt, val))
    return ' '.join(p for p in parts if p).strip()

"""ciadpi_enginectl — единый бэкенд управления движками и DNS-мостом.

⭐ v2.0.5 (user: «кнопка запускает тот что в фокусе, а не тот что
выбрал; не выключает, а перезапускает; синхронизированы ли команды
с меню — путаница»):

Одна точка истины для ВСЕХ точек входа (меню трея, окно «Движки
обхода», профили, CLI). Правила:

  * start_engine(name)   — запускает ИМЕННО name; чужие движки
    гарантированно глушатся (даже если висят с прошлых версий);
    повторный старт уже активного = no-op (НЕ «перезапуск»).
  * stop_engine(name)    — останавливает name (+ его хвосты:
    nft-правила, DNS-мост для snimod).
  * restart_engine(name) — stop + start.
  * Мост (dotbridge) — самостоятельная сущность: start_bridge/
    stop_bridge без привязки к snimod.

Все операции предназначены для вызова ИЗ ФОНОВОГО ПОТОКА (там
живут systemctl/nft). Возвращает (ok, message).
"""
import subprocess
import time
from pathlib import Path

HOME = Path.home()
SYSTEMCTL = '/usr/bin/systemctl'
TEE = '/usr/bin/tee'

UNITS = {
    'byedpi': 'ciadpi.service',
    'nfqws': 'ciadpi-nfqws.service',
    'snimod': 'ciadpi-snimod.service',
    'bridge': 'ciadpi-dotbridge.service',
}

NFT_TABLES = {
    'nfqws': 'ciadpi',
    'snimod': 'ciadpi_snimod',
}


def _run(cmd, timeout=60, **kw):
    """subprocess.run с таймаутом; возвращает (rc, stdout, stderr)."""
    rc: int = 0
    out: str = ''
    err: str = ''
    try:
        r = subprocess.run(cmd, capture_output=True, text=True,
                          timeout=timeout, **kw)
        rc, out, err = r.returncode, (r.stdout or ''), (r.stderr or '')
    except subprocess.TimeoutExpired:
        rc, out, err = 124, '', 'timeout'
    except FileNotFoundError as e:
        rc, out, err = 127, '', str(e)
    except Exception as e:
        rc, out, err = 1, '', str(e)
    return rc, out, err


def _systemctl(*args, timeout=60):
    """systemctl через sudo -n (sudoers-глаголы) с pkexec-fallback."""
    cmds = [['sudo', '-n', SYSTEMCTL, *args],
            ['pkexec', 'systemctl', *args]]
    last = ''
    for cmd in cmds:
        rc, out, err = _run(cmd, timeout=timeout)
        if rc == 0:
            return True, out.strip()
        last = err.strip() or out.strip()
    return False, last


def is_active(name):
    """Активен ли движок/мост прямо сейчас (юзнит-имя или ключ)."""
    unit = UNITS.get(name, name if name.endswith('.service') else None)
    if not unit:
        return False
    rc, out, _err = _run([SYSTEMCTL, 'is-active', unit], timeout=5)
    return rc == 0 and (out or '').strip() == 'active'


def _stop_other_engines(keep):
    """Заглушить все движки, кроме keep (и моста — он общий)."""
    msgs = []
    for eng in ('byedpi', 'nfqws', 'snimod'):
        if eng == keep:
            continue
        unit = UNITS[eng]
        # даже если inactive — stop безвреден и добьёт «зависшие»
        ok, err = _systemctl('stop', unit, timeout=90)
        if not ok and err:
            msgs.append(f'{eng}: {err[:80]}')
        # nft-хвосты чужих NFQUEUE-движков
        table = NFT_TABLES.get(eng)
        if table:
            _run(['sudo', '-n', '/usr/sbin/nft', 'delete', 'table',
                  'inet', table], timeout=15)
    return '; '.join(msgs)


def start_engine(name, managers=None):
    """Запустить ИМЕННО name. Чужие глушатся. Повтор = no-op.

    managers: dict с готовыми {'byedpi': …, 'nfqws': mgr, 'snimod': mgr}
    (трей передаёт свои экземпляры; CLI = None → создаются свои).
    Возвращает (ok, message).
    """
    if name not in ('byedpi', 'nfqws', 'snimod'):
        return False, f'неизвестный движок: {name}'
    if is_active(name):
        return True, f'{name}: уже активен (no-op)'

    # менеджеры движков (по правде нужны только nfqws/snimod:
    # они пишут юнит-файл перед стартом)
    mgr = None
    if managers and name in managers:
        mgr = managers.get(name)
    elif name == 'nfqws':
        try:
            from ciadpi_nfqws import NfqwsManager
            mgr = NfqwsManager()
        except ImportError:
            mgr = None
    elif name == 'snimod':
        try:
            from ciadpi_snimod import SnimodManager
            mgr = SnimodManager()
        except ImportError:
            mgr = None

    # 1) чужие движки — глушим ДО старта (взаимоисключаемость)
    warn = _stop_other_engines(name)

    # 2) старт выбранного
    if name == 'byedpi':
        ok, err = _systemctl('start', UNITS['byedpi'])
    else:
        if mgr is None:
            return False, f'{name}: модуль недоступен'
        if not mgr.is_installed():
            return False, f'{name}: бинарник не собран'
        ok, err = mgr.start()      # пишет юнит, мост (snimod) и т.д.

    if not ok:
        return False, f'{name}: {err or "start failed"} {(";" + warn) if warn else ""}'
    # страховка: не поднялся?
    time.sleep(0.5)
    if not is_active(name):
        time.sleep(1.5)
        if not is_active(name):
            return False, f'{name}: сервис не активен после старта'
    return True, (f'{name}: запущен' + (f' (предупреждения: {warn})' if warn else ''))


def stop_engine(name, managers=None):
    """Остановить name; для snimod гасит и DNS-мост.

    byedpi/nfqws при остановке не трогают мост (он общий ресурс;
    гасится отдельно или вместе со snimod).
    """
    if name not in UNITS:
        return False, f'неизвестный движок: {name}'
    if name == 'bridge':
        return stop_bridge()

    already = not is_active(name)
    # nft-хвосты добьём в любом случае (могли остаться от сбоев)
    unit = UNITS[name]
    ok, err = _systemctl('stop', unit, timeout=90)
    if not ok:
        return False, f'{name}: {err or "stop failed"}'

    table = NFT_TABLES.get(name)
    if table:
        _run(['sudo', '-n', '/usr/sbin/nft', 'delete', 'table',
              'inet', table], timeout=15)
    if name == 'snimod':
        # мост — часть snimod-режима; гасим (порядок: таблица уже снесена)
        stop_bridge()
    if already and is_active(name) is False and ok:
        return True, f'{name}: уже был остановлен (хвосты вычищены)'
    return True, f'{name}: остановлен'


def restart_engine(name, managers=None):
    """Перезапуск = stop (с вычисткой хвостов) + start."""
    if name not in ('byedpi', 'nfqws', 'snimod'):
        return False, f'неизвестный движок: {name}'
    ok, msg = stop_engine(name)
    if not ok:
        # стоп не критичен для рестарта — идём к старту
        pass
    ok2, msg2 = start_engine(name, managers)
    return ok2, f'перезапуск {name}: {msg2}'


def start_bridge():
    """Поднять DNS-мост DoT (127.0.0.1:53 → 1.1.1.1:853) без движков.

    ⭐ v2.0.5 (user: «мосты давай добавим отдельно плюсом режим»):
    мост как САМОСТОЯТЕЛЬНЫЙ режим — чистый DNS без NXDOMAIN-блоки
    прова, движки не трогаем. dns_dnat-цепочка живёт в таблице
    snimod, поэтому для автономного моста создаём таблицу-компаньон
    ciadpi_bridge (только dns_dnat) — сносится при stop_bridge.
    """
    if is_active('bridge'):
        return True, 'мост: уже активен (no-op)'
    # юнит моста уже мог быть создан snimod-менеджером; если нет — создаём
    unit_path = Path('/etc/systemd/system/ciadpi-dotbridge.service')
    if not unit_path.exists():
        try:
            from ciadpi_snimod import SnimodManager
            SnimodManager()._dns_bridge_enable()
        except Exception as e:
            return False, f'мост: юнит недоступен ({e})'
    _systemctl('daemon-reload')
    ok, err = _systemctl('start', UNITS['bridge'])
    if not ok:
        return False, f'мост: {err or "start failed"}'
    time.sleep(0.5)
    if not is_active('bridge'):
        return False, 'мост: сервис не активен после старта'
    # таблица-компаньон с dns_dnat (мост без неё бесполезен — DNS
    # системы идёт мимо 127.0.0.1:53).
    # ⭐ sudoers-трюк: отдельный ciadpi_bridge.nft не покрыт в sudoers
    # у уже установивших; используем ПОКРЫТЫЙ путь ciadpi_snimod.nft,
    # но пишем в него ТОЛЬКО dns_dnat-цепочку (без queue-цепочки —
    # движок №3 в bridge-режиме не работает). Таблица сносится при
    # stop_bridge и пересоздаётся snimod-менеджером при старте
    # движка №3 (ExecStartPre пишет свою полную версию).
    nft_file = Path(HOME / '.config' / 'ciadpi' / 'ciadpi_snimod.nft')
    nft_file.parent.mkdir(parents=True, exist_ok=True)
    nft_file.write_text(
        '# ciadpi bridge-only: dns_dnat без движка (v2.0.5)\n'
        '# Перезапишется полной версией при старте движка snimod.\n'
        'table inet ciadpi_snimod {\n'
        '    chain dns_dnat {\n'
        '        type nat hook output priority -100; policy accept;\n'
        '        ip daddr != 127.0.0.0/8 udp dport 53 counter dnat ip to 127.0.0.1:53\n'
        '    }\n'
        '}\n', encoding='utf-8')
    rc, _out, err = _run(['sudo', '-n', '/usr/sbin/nft', '-f', str(nft_file)],
                      timeout=15)
    if rc != 0:
        stop_bridge()
        return False, f'мост: dns_dnat не применён ({err[:80]})'
    return True, 'мост: активен (DoT + dns_dnat)'


def stop_bridge():
    """Остановить DNS-мост и снести таблицу-компаньон."""
    ok, err = _systemctl('stop', UNITS['bridge'])
    _run(['sudo', '-n', '/usr/sbin/nft', 'delete', 'table',
          'inet', 'ciadpi_snimod'], timeout=15)
    if not ok:
        return False, f'мост: {err or "stop failed"}'
    return True, 'мост: остановлен'


# ---------------- CLI ----------------

if __name__ == '__main__':
    import sys
    if len(sys.argv) < 2:
        print('usage: ciadpi_enginectl.py start|stop|restart|status '
              '[byedpi|nfqws|snimod|bridge]')
        sys.exit(1)
    verb = sys.argv[1]
    if verb == 'status' and len(sys.argv) < 3:
        for k in ('byedpi', 'nfqws', 'snimod', 'bridge'):
            print(f'{k}: {"active" if is_active(k) else "inactive"}')
        sys.exit(0)
    if len(sys.argv) < 3:
        print('usage: ciadpi_enginectl.py start|stop|restart|status '
              '[byedpi|nfqws|snimod|bridge]')
        sys.exit(1)
    target = sys.argv[2]
    if verb == 'start':
        if target == 'bridge':
            fn = lambda: start_bridge()  # noqa: E731
        else:
            fn = lambda _t=target: start_engine(_t)  # noqa: E731
    elif verb == 'stop':
        if target == 'bridge':
            fn = lambda: stop_bridge()  # noqa: E731
        else:
            fn = lambda _t=target: stop_engine(_t)  # noqa: E731
    elif verb == 'restart':
        if target == 'bridge':
            fn = lambda: (stop_bridge(), start_bridge())[1]  # noqa: E731
        else:
            fn = lambda _t=target: restart_engine(_t)  # noqa: E731
    elif verb == 'status':
        for k in ('byedpi', 'nfqws', 'snimod', 'bridge'):
            print(f'{k}: {"active" if is_active(k) else "inactive"}')
        sys.exit(0)
    else:
        print('unknown verb:', verb)
        sys.exit(1)
    ok, msg = fn()
    print(('OK ' if ok else 'FAIL ') + msg)
    sys.exit(0 if ok else 1)

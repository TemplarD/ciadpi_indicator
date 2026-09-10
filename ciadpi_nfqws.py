#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
CIADPI NFQWS Manager — интеграция nfqws (zapret) как второго движка обхода DPI.

Что это:
  byedpi/ciadpi — SOCKS5-прокси: обрабатывает только трафик, явно
  направленный в него (приложение/системный прокси).
  nfqws (проект zapret) — перехватчик пакетов через NFQUEUE: правила
  nftables заворачивают НАЧАЛЬНЫЕ пакеты исходящих TCP-соединений
  (порты 80/443) в очередь, nfqws модифицирует их (desync), и это
  работает для ВСЕХ приложений машины без настройки прокси.

  Движки взаимоисключающие: nfqws обрабатывает и трафик byedpi
  (двойной desync ломает соединения). Переключатель в трее выбирает
  активный движок: byedpi (SOCKS) или nfqws (NFQUEUE).

Архитектура (безопасность):
  * сам nfqws и правила nftables требуют root — сервис
    ciadpi-nfqws.service (systemd, User=templard, но с AmbientCapabilities
    для NFQUEUE-bind) — нет: надёжнее классический root-сервис,
    как у zapret;
  * правила живут в ОТДЕЛЬНОЙ таблице nft `ciadpi` — не трогаем
    таблицу zapret (если юзер её использует) и системные правила;
  * применяется/снимается root-хелпером ciadpi_nfqws_rules.sh
    (sudoers NOPASSWD: только nft -f <файл> для этого скрипта),
    вызовы из трея идут через sudo -n → pkexec fallback;
  * очередь --qnum 200, только hook output (наша машина, не роутер),
    TCP 80,443, connbytes 1:6 (только начало соединения), fwmark
    0x40000000 исключает пакеты, сгенерированные самим nfqws.

Модуль GUI-независим: может использоваться из CLI.

Автор: templard, лицензия MIT.
"""

import json
import os
import subprocess
import time
from pathlib import Path


class NfqwsManager:
    """Управление nfqws-движком: бинарник, сервис, правила nftables."""

    SERVICE = 'ciadpi-nfqws.service'
    UNIT_FILE = Path('/etc/systemd/system/ciadpi-nfqws.service')
    NFT_TABLE = 'ciadpi'          # наша таблица — НЕ zapret
    QNUM = 200                    # номер NFQUEUE
    DESYNC_MARK = '0x40000000'    # марка nfqws-пакетов (анти-цикл)

    # ⭐ Полные пути — sudoers требует ТОЧНОЕ совпадение бинарника.
    # Разрешаем только реальные пути (readlink -f), как в ciadpi_privileges.sh.
    SYSTEMCTL_BIN = '/usr/bin/systemctl'
    TEE_BIN = '/usr/bin/tee'
    NFT_BIN = '/usr/sbin/nft'
    # Fallback-пути для систем, где бинарники живут в /bin и /sbin
    _BIN_FALLBACKS = {
        'SYSTEMCTL_BIN': ['/usr/bin/systemctl', '/bin/systemctl'],
        'TEE_BIN': ['/usr/bin/tee', '/bin/tee'],
        'NFT_BIN': ['/usr/sbin/nft', '/usr/bin/nft'],
    }

    @classmethod
    def _resolve_bin(cls, name):
        """Первый существующий путь из fallback-списка."""
        for p in cls._BIN_FALLBACKS[name]:
            if Path(p).exists():
                return p
        return getattr(cls, name)

    def __init__(self):
        self.home = Path.home()
        self.zapret_dir = self.home / 'zapret'
        self.nfqws_bin = self.zapret_dir / 'nfq' / 'nfqws'
        self.config_dir = self.home / '.config' / 'ciadpi'
        self.nfqws_config = self.config_dir / 'nfqws.json'
        self.rules_script = self.config_dir / 'ciadpi_nfqws_rules.sh'
        self.nft_file = self.config_dir / 'ciadpi_nfqws.nft'

        # Дефолтные desync-параметры nfqws (формат zapret, не byedpi!)
        # - дискретные desync-методы на TLS: split + disorder
        self.default_params = (
            '--filter-tcp=80,443 --dpi-desync=disorder2 '
            '--dpi-desync-split-pos=1'
        )

    # ---------------- Конфиг ----------------

    def load_config(self):
        default = {
            'params': self.default_params,
            'enabled': False,
        }
        try:
            if self.nfqws_config.exists():
                with open(self.nfqws_config, 'r', encoding='utf-8') as f:
                    saved = json.load(f)
                if isinstance(saved, dict):
                    default.update(saved)
        except Exception as e:
            print(f"⚠️ nfqws config: {e}")
        return default

    def save_config(self, cfg):
        try:
            self.config_dir.mkdir(parents=True, exist_ok=True)
            with open(self.nfqws_config, 'w', encoding='utf-8') as f:
                json.dump(cfg, f, indent=2, ensure_ascii=False)
        except Exception as e:
            print(f"⚠️ nfqws config save: {e}")

    # ---------------- Бинарник ----------------

    def is_installed(self):
        """Бинарник nfqws существует и исполняем."""
        return self.nfqws_bin.exists() and os.access(self.nfqws_bin, os.X_OK)

    def check_binary(self):
        """Версия бинарника (строка) или None."""
        try:
            r = subprocess.run([str(self.nfqws_bin), '--version'],
                               capture_output=True, text=True, timeout=5)
            return (r.stdout or r.stderr).strip() or None
        except Exception:
            return None

    # ---------------- Правила nftables ----------------

    _NFT_RULESET = """\
# CIADPI nfqws rules — отдельная таблица, не zapret
# ⭐ ct original packets (НЕ ct bytes!) — счётчик пакетов исходного
#   направления соединения: перехватываем только первые пакеты, где
#   ClientHello. Синтаксис сверен с zapret/common/nft.sh.
table inet {table} {{
    chain output {{
        type filter hook output priority filter; policy accept;
        # TCP 80,443: только первые пакеты соединения, без собственных
        # пакетов nfqws (fwmark) — иначе цикл
        meta l4proto tcp tcp dport {{ 80, 443 }} ct original packets 1-6 meta mark != {mark} counter queue num {qnum} bypass
    }}
}}
"""

    def _write_rules_files(self):
        """Создаёт nft-файл и root-хелпер применения/снятия правил."""
        self.config_dir.mkdir(parents=True, exist_ok=True)
        self.nft_file.write_text(
            self._NFT_RULESET.format(table=self.NFT_TABLE,
                                     qnum=self.QNUM,
                                     mark=self.DESYNC_MARK),
            encoding='utf-8')

        helper = f"""#!/bin/bash
# CIADPI nfqws rules helper — вызывается через sudo (см. ciadpi_privileges.sh)
# Применение: ciadpi_nfqws_rules.sh apply
# Снятие:    ciadpi_nfqws_rules.sh remove
# ⭐ apply ИДЕМПОТЕНТЕН: nft -f при существующей таблице ДОБАВЛЯЕТ цепочки
#   внутрь (не заменяет!) — без delete правила дублировались при каждом
#   рестарте сервиса. Поэтому: сначала сносим таблицу, потом применяем.
set -u
NFT="{self._resolve_bin('NFT_BIN')}"
NFT_FILE="{self.nft_file}"
QNUM={self.QNUM}
TABLE="{self.NFT_TABLE}"

cmd="${{1:-}}"
case "$cmd" in
  apply)
    "$NFT" delete table inet "$TABLE" 2>/dev/null || true
    "$NFT" -f "$NFT_FILE"
    ;;
  remove)
    "$NFT" delete table inet "$TABLE" 2>/dev/null || true
    ;;
  *)
    echo "usage: $0 apply|remove" >&2
    exit 1
    ;;
esac
"""
        self.rules_script.write_text(helper, encoding='utf-8')
        self.rules_script.chmod(0o755)

    # ---------------- Сервис systemd ----------------

    _UNIT_TEMPLATE = """\
[Unit]
Description=CIADPI NFQWS DPI Bypass (zapret nfqws)
After=network.target
Wants=network.target

[Service]
Type=simple
User=root
ExecStartPre={helper} apply
ExecStart={bin} --qnum={qnum} --dpi-desync-fwmark={mark} {params}
ExecStopPost={helper} remove
Restart=on-failure
RestartSec=5
TimeoutStartSec=30

[Install]
WantedBy=multi-user.target
"""

    # Глаголы, требующие root: прямой вызов systemctl без sudo порождает
    # polkit-диалог пароля на каждый вызов (их бывает много — очередь
    # диалогов «вешает» сессию). Покрыты passwordless в sudoers → sudo -n.
    _PRIVILEGED_VERBS = {'start', 'stop', 'restart', 'reload',
                         'enable', 'disable', 'mask', 'unmask',
                         'daemon-reload'}

    def _systemctl(self, *args, timeout=60):
        """systemctl с fallback-цепочкой. Для привилегированных глаголов:
        sudo -n → pkexec (один диалог). Для чтения: direct → sudo -n.
        Read-only verbs (is-active/status/show) возвращают данные даже
        при nonzero exit — это не ошибка."""
        privileged = bool(args) and args[0] in self._PRIVILEGED_VERBS
        if privileged:
            cmds = [
                ['sudo', '-n', self._resolve_bin('SYSTEMCTL_BIN'), *args],
                ['pkexec', 'systemctl', *args],
            ]
        else:
            cmds = [
                ['systemctl', *args],
                ['sudo', '-n', self._resolve_bin('SYSTEMCTL_BIN'), *args],
            ]
        last_err = ''
        for cmd in cmds:
            try:
                r = subprocess.run(cmd, capture_output=True, text=True,
                                   timeout=timeout)
                if r.returncode == 0:
                    return True, (r.stdout or '').strip()
                last_err = (r.stderr or r.stdout or '').strip()
                # is-active=3 (inactive) и прочие query-коды — данные, не провал
                if args[0] in ('is-active', 'status', 'show', 'is-enabled') \
                        and r.stdout:
                    return True, r.stdout.strip()
            except (FileNotFoundError, subprocess.TimeoutExpired) as e:
                last_err = str(e)
                continue
        return False, last_err

    def write_unit(self, params=None):
        """(Пере)создаёт systemd-юнит ciadpi-nfqws.service через sudo tee."""
        if not self.is_installed():
            return False, 'nfqws не установлен (~/zapret/nfq/nfqws)'
        cfg = self.load_config()
        params = params or cfg.get('params') or self.default_params
        self._write_rules_files()

        # dry-run: параметры должны проходить проверку самого nfqws
        try:
            r = subprocess.run(
                [str(self.nfqws_bin), '--dry-run', '--qnum', str(self.QNUM),
                 '--dpi-desync-fwmark', self.DESYNC_MARK] + params.split(),
                capture_output=True, text=True, timeout=10)
            if r.returncode != 0:
                err = (r.stderr or r.stdout or '').strip().splitlines()
                return False, ('nfqws отверг параметры: '
                               + (err[-1] if err else f'rc={r.returncode}'))
        except Exception as e:
            return False, f'dry-run не выполнен: {e}'

        content = self._UNIT_TEMPLATE.format(
            helper=self.rules_script,
            bin=self.nfqws_bin,
            qnum=self.QNUM,
            mark=self.DESYNC_MARK,
            params=params,
        )
        tmp = Path('/tmp/ciadpi_nfqws_temp.service')
        tmp.write_text(content, encoding='utf-8')
        # ⭐ sudo tee идёт ПЕРВЫМ (passwordless по sudoers) и ОБЯЗАТЕЛЬНО
        # с stdin из tmp-файла: без stdin tee наследует EOF и «успешно»
        # пишет ПУСТОЙ юнит (0 байт = masked для systemd!). Проверка
        # `'tee' in cmd` раньше всегда была False (элемент '/usr/bin/tee',
        # не 'tee') — stdin-ветка никогда не включалась.
        # pkexec cp — только крайний fallback: без настроенных прав он
        # рисует polkit-диалог пароля.
        sudo_tee = ['sudo', '-n', self._resolve_bin('TEE_BIN'),
                    str(self.UNIT_FILE)]
        try:
            with open(tmp, 'rb') as f_in:
                r = subprocess.run(sudo_tee, stdin=f_in,
                                   capture_output=True, timeout=90)
            if r.returncode == 0 and self.UNIT_FILE.stat().st_size > 0:
                self._systemctl('daemon-reload')
                return True, ''
            last_err = (r.stderr or b'').decode(errors='replace')[:200]
        except (FileNotFoundError, subprocess.TimeoutExpired) as e:
            last_err = str(e)
        try:
            r = subprocess.run(['pkexec', 'cp', str(tmp), str(self.UNIT_FILE)],
                               capture_output=True, timeout=90)
            if r.returncode == 0 and self.UNIT_FILE.stat().st_size > 0:
                self._systemctl('daemon-reload')
                return True, ''
            last_err = (r.stderr or b'').decode(errors='replace')[:200]
        except (FileNotFoundError, subprocess.TimeoutExpired) as e:
            last_err = str(e)
        return False, ('Не удалось записать юнит-файл (нужны права root): '
                       f'{last_err}. Запустите настройку привилегий.')

    def is_service_active(self):
        ok, out = self._systemctl('is-active', self.SERVICE)
        return ok and (out or '').lower() == 'active'

    def set_enabled(self, enabled: bool):
        """Enable/disable ciadpi-nfqws.service (boot-автозапуск).

        Глаголы enable/disable есть в sudoers (passwordless). is-enabled
        в sudoers НЕ входит, поэтому НЕ читать его через sudo — только
        напрямую (без прав не требует).
        """
        verb = 'enable' if enabled else 'disable'
        return self._systemctl(verb, self.SERVICE)

    def start(self, params=None):
        """Устанавливает юнит (если нужно) и запускает сервис."""
        if not self.is_service_active():
            ok, err = self.write_unit(params)
            if not ok:
                return False, err
        return self._systemctl('start', self.SERVICE)

    def stop(self):
        """Останавливает сервис; правила снимает ExecStopPost."""
        ok, err = self._systemctl('stop', self.SERVICE)
        # страховка: если stop упал или сервис был убит без ExecStopPost,
        # правила могли остаться — снимаем сами
        if self.rules_active():
            self.remove_rules_fallback()
        return ok, err

    def remove_rules_fallback(self):
        """Снятие правил при остановленном/убитом сервисе (страховка)."""
        nft = self._resolve_bin('NFT_BIN')
        for cmd in (['sudo', '-n', nft, 'delete', 'table', 'inet',
                     self.NFT_TABLE],
                    ['pkexec', 'nft', 'delete', 'table', 'inet',
                     self.NFT_TABLE]):
            try:
                r = subprocess.run(cmd, capture_output=True, timeout=30)
                if r.returncode == 0:
                    return True
            except (FileNotFoundError, subprocess.TimeoutExpired):
                continue
        return False

    def rules_active(self):
        """Есть ли наша таблица ciadpi в nft ruleset.

        Непривилегированный `nft list` валится с 'Operation not
        permitted' (ядро скрывает ruleset от обычных юзеров), поэтому
        цепочка: sudo -n nft list (покрыто sudoers) → pkexec.
        """
        nft = self._resolve_bin('NFT_BIN')
        for cmd in (
            ['sudo', '-n', nft, 'list', 'ruleset'],
            ['pkexec', nft, 'list', 'ruleset'],
        ):
            try:
                r = subprocess.run(cmd, capture_output=True, text=True,
                                   timeout=15)
                if r.returncode == 0:
                    return f'table inet {self.NFT_TABLE}' in (r.stdout or '')
            except (FileNotFoundError, subprocess.TimeoutExpired):
                continue
        # все способы упали — считаем правила отсутствующими (fail-safe)
        return False

    # ---------------- CLI ----------------

if __name__ == '__main__':
    import argparse
    parser = argparse.ArgumentParser(description='CIADPI nfqws engine manager')
    parser.add_argument('action', choices=['status', 'start', 'stop',
                                           'install-check'])
    parser.add_argument('--params', default=None,
                        help='Desync-параметры nfqws (формат zapret)')
    args = parser.parse_args()

    m = NfqwsManager()
    if args.action == 'install-check':
        print('installed:', m.is_installed())
        print('version:', m.check_binary() or '—')
        print('service active:', m.is_service_active())
        print('rules active:', m.rules_active())
    elif args.action == 'status':
        print('service:', m.is_service_active() and 'active' or 'inactive')
        print('rules:', m.rules_active() and 'active' or 'inactive')
    elif args.action == 'start':
        ok, err = m.start(args.params)
        print('start:', 'OK' if ok else f'FAIL: {err}')
    elif args.action == 'stop':
        ok, err = m.stop()
        print('stop:', 'OK' if ok else f'FAIL: {err}')

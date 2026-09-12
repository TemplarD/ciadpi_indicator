"""ciadpi_snimod — менеджер движка №3: SNI case-mod (наша разработка).

Идея (нет ни в byedpi, ни в zapret): DPI прова роняет ClientHello по
ПОДСТРОКЕ SNI "www.youtube.com" в нижнем регистре, но фильтр
РЕГИСТРОЗАВИСИМ — "WWW.YOUTUBE.COM" проходит (PoC: TLS handshake +
HTTP 200), а TLS-серверам регистр SNI безразличен (RFC 6066).

Движок = C-демон (snimod/ciadpi_snimod.c, NFQUEUE qnum 210) + nft-таблица
inet ciadpi_snimod (только tcp dport 443, первые пакеты соединения,
fwmark-защита от цикла) + systemd-юнит ciadpi-snimod.service (root).

API совместим с NfqwsManager (load_config/save_config, write_unit,
start/stop, is_service_active, rules_active, set_enabled, is_installed),
поэтому трей подключает его как третий движок с минимальными правками.
"""
import json
import os
import subprocess
from pathlib import Path


class SnimodManager:
    """Управление snimod-движком: бинарник, сервис, правила nftables."""

    SERVICE = 'ciadpi-snimod.service'
    UNIT_FILE = Path('/etc/systemd/system/ciadpi-snimod.service')
    NFT_TABLE = 'ciadpi_snimod'   # своя таблица (не zapret, не ciadpi)
    QNUM = 210                     # отдельный от nfqws номер очереди
    DESYNC_MARK = '0x40000000'     # fwmark своих пакетов (анти-цикл)

    SYSTEMCTL_BIN = '/usr/bin/systemctl'
    TEE_BIN = '/usr/bin/tee'
    NFT_BIN = '/usr/sbin/nft'

    def __init__(self):
        self.home = Path.home()
        repo = Path(__file__).resolve().parent
        # ⭐ v2.0.1: бинарник ищем по списку кандидатов — модуль может
        # работать ИЗ РЕПО (~/ciadpi_indicator/), ИЗ УСТАНОВЛЕННОЙ копии
        # (~/.local/bin/), где рядом лежит snimod/bin/, либо по
        # классическому пути репо в домашней папке. Раньше путь был
        # один (рядом с модулем) — из ~/.local/bin трей всегда писал
        # «не собран», хотя бинарник давно построен в репо.
        candidates = [
            repo / 'snimod' / 'bin' / 'ciadpi_snimod',            # рядом с модулем
            self.home / 'ciadpi_indicator' / 'snimod' / 'bin' / 'ciadpi_snimod',  # репо
            self.home / '.local' / 'bin' / 'snimod' / 'bin' / 'ciadpi_snimod',    # синк-копия
            Path('/usr/lib/ciadpi-indicator/ciadpi_snimod'),     # deb-пакет
        ]
        self.snimod_bin = next((p for p in candidates if p.exists()), candidates[0])
        # ⭐ v2.0.2: DNS-мост DoT — ищем ciadpi_dotbridge.py так же, как бинарник
        bridge_candidates = [
            repo / 'ciadpi_dotbridge.py',
            self.home / 'ciadpi_indicator' / 'ciadpi_dotbridge.py',
            self.home / '.local' / 'bin' / 'ciadpi_dotbridge.py',
            Path('/usr/lib/ciadpi-indicator/ciadpi_dotbridge.py'),
        ]
        self.dotbridge_py = next((p for p in bridge_candidates if p.exists()),
                                 bridge_candidates[0])
        self.config_dir = self.home / '.config' / 'ciadpi'
        self.snimod_config = self.config_dir / 'snimod.json'
        self.hosts_file = self.config_dir / 'snimod_hosts.txt'
        self.rules_script = self.config_dir / 'ciadpi_snimod_rules.sh'
        self.nft_file = self.config_dir / 'ciadpi_snimod.nft'

        # Хосты по умолчанию — то, что блокируется substring-фильтром
        # прова. Пользователь может расширить список в диалоге движка.
        self.default_hosts = [
            'www.youtube.com',
            'youtube.com',
            'm.youtube.com',
            'youtu.be',
            'ytimg.com',
            'googlevideo.com',
        ]

    # ---------------- Конфиг ----------------

    def load_config(self):
        default = {'hosts': list(self.default_hosts), 'enabled': False}
        try:
            if self.snimod_config.exists():
                with open(self.snimod_config, 'r', encoding='utf-8') as f:
                    saved = json.load(f)
                if isinstance(saved, dict):
                    default.update(saved)
        except Exception as e:
            print(f"⚠️ snimod config: {e}")
        return default

    def save_config(self, cfg):
        try:
            self.config_dir.mkdir(parents=True, exist_ok=True)
            with open(self.snimod_config, 'w', encoding='utf-8') as f:
                json.dump(cfg, f, indent=2, ensure_ascii=False)
        except Exception as e:
            print(f"⚠️ snimod config save: {e}")

    def write_hosts_file(self, hosts):
        self.config_dir.mkdir(parents=True, exist_ok=True)
        self.hosts_file.write_text(
            '\n'.join(h.strip() for h in hosts if h.strip()) + '\n',
            encoding='utf-8')

    # ---------------- Бинарник ----------------

    def is_installed(self):
        return self.snimod_bin.exists() and os.access(self.snimod_bin, os.X_OK)

    def check_binary(self):
        """--hosts=/dev/null --debug без root: ожидаем ошибку bind (rc=5)
        — значит бинарник живой и понимает аргументы."""
        try:
            r = subprocess.run(
                [str(self.snimod_bin), '--hosts=/dev/null', '--debug'],
                capture_output=True, text=True, timeout=10)
            out = (r.stdout or '') + (r.stderr or '')
            if 'nfq_bind_pf' in out or 'nfq_open' in out:
                return True, 'ok (нужен root для работы)'
            return False, out.strip()[:200] or f'rc={r.returncode}'
        except Exception as e:
            return False, str(e)

    # ---------------- Правила nft ----------------

    _NFT_RULESET = """\
# CIADPI snimod rules — движок №3 (SNI case-mod)
# Только исходящий TCP 443, только первые пакеты соединения (там
# ClientHello), без собственных пакетов демона (fwmark) — анти-цикл.
table inet {table} {{
    chain output {{
        type filter hook output priority filter; policy accept;
        meta l4proto tcp tcp dport 443 ct original packets 1-6 meta mark != {mark} counter queue num {qnum} bypass
    }}
    # ⭐ v2.0.3: DNS-перехват для dotbridge — пров NXDOMAIN-ит ютуб в
    # UDP53. ВСЕ исходящие DNS (кроме loopback) днатятся на локальный
    # DoT-мост 127.0.0.1:53. resolv.conf трогать не нужно (он часто
    # прибит immutable-флагом VPN-клиентами — Amnezia так делает).
    # Цепочка живёт в НАШЕЙ таблице: сносится вместе со snimod.
    chain dns_dnat {{
        type nat hook output priority -100; policy accept;
        ip daddr != 127.0.0.0/8 udp dport 53 counter dnat ip to 127.0.0.1:53
    }}
}}
"""

    def _write_rules_files(self):
        self.config_dir.mkdir(parents=True, exist_ok=True)
        self.nft_file.write_text(
            self._NFT_RULESET.format(table=self.NFT_TABLE,
                                     qnum=self.QNUM,
                                     mark=self.DESYNC_MARK),
            encoding='utf-8')
        helper = f"""#!/bin/bash
# CIADPI snimod rules helper (sudo; см. ciadpi_privileges.sh)
# Идемпотентно: снос таблицы → применение.
# ⭐ v2.0.5: dns_dnat применяется ТОЛЬКО если на 127.0.0.1:53 кто-то
# слушает (dotbridge). Мёртвый мост + живой dns_dnat = весь DNS
# системы уходит в пустоту (чёрная дыра). Если мост не поднялся —
# цепочку срезаем, обычный DNS прова продолжает работать.
set -u
NFT="/usr/sbin/nft"
NFT_FILE="{self.nft_file}"
TABLE="{self.NFT_TABLE}"
cmd="${{1:-}}"
case "$cmd" in
  apply)
    "$NFT" delete table inet "$TABLE" 2>/dev/null || true
    # ждём до 3с, пока dotbridge забиндит :53 (enable --now
    # возвращается раньше бинда — гонка ExecStartPre vs python)
    ok=0
    for i in 1 2 3 4 5 6; do
        if ss -H -uln 2>/dev/null | grep -qE '127[.]0[.]0[.]1:53([[:space:]]|$)'; then
            ok=1; break
        fi
        sleep 0.5
    done
    if [ "$ok" = 1 ]; then
        "$NFT" -f "$NFT_FILE"
    else
        echo "snimod: dotbridge не слушает :53 — dns_dnat срезаем (анти-дыра)" >&2
        sed -e '/^    chain dns_dnat {{/,/^    }}$/d' "$NFT_FILE" \\
            | "$NFT" -f /dev/stdin
    fi
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

    # ---------------- systemd ----------------

    _UNIT_TEMPLATE = """\
[Unit]
Description=CIADPI Snimod DPI Bypass (SNI case-mod engine)
After=network.target ciadpi-dotbridge.service
Wants=network.target
Wants=ciadpi-dotbridge.service

[Service]
Type=simple
User=root
ExecStartPre={helper} apply
ExecStart={bin} --qnum={qnum} --hosts={hosts} --debug
ExecStopPost={helper} remove
# ⭐ v2.0.5: НЕ рестартим по «failure» — SIGKILL-код 137 считался
# фейлом и systemd САМ поднимал движок после «Остановить».
# Только явный краш без сигнала (код 4-7) — редкость; лучше ручной
# рестарт, чем «зомби-самовключение». TimeoutStopSec=10: с новым
# sigaction-выходом демон умирает мгновенно; 10с — потолок.
Restart=no
TimeoutStopSec=10
TimeoutStartSec=30

[Install]
WantedBy=multi-user.target
"""

    # ⭐ v2.0.2: DNS-мост (DoT) — пров даёт NXDOMAIN на youtube в UDP53,
    # но DoT (853) не блокирует (openssl-проверено). dotbridge слушает
    # 127.0.0.1:53, форвардит на 1.1.1.1:853. Юниты: снапшот resolv.conf
    # делается при старте, откат — при остановке (ExecStopPost).
    DOTBRIDGE_UNIT = """\
[Unit]
Description=CIADPI DoT DNS bridge (127.0.0.1:53 -> 1.1.1.1:853)
After=network.target
Wants=network.target
Before=ciadpi-snimod.service

[Service]
Type=simple
ExecStart=/usr/bin/python3 {bridge}
Restart=on-failure
RestartSec=3

[Install]
WantedBy=multi-user.target
"""
    RESOLV_SNAPSHOT = '/etc/resolv.conf.ciadpi-snapshot'
    RESOLV_BODY = (
        '# ciadpi dotbridge: локальный DoT-резолвер (снапшот оригинала в '
        '/etc/resolv.conf.ciadpi-snapshot)\nnameserver 127.0.0.1\n'
    )

    @staticmethod
    def _resolv_immutable() -> bool:
        """Флаг immutable на resolv.conf (ставит AmneziaVPN и VPN-клиенты)."""
        import subprocess as _sp
        try:
            r = _sp.run(['lsattr', '/etc/resolv.conf'],
                        capture_output=True, text=True, timeout=5)
            return 'i' in (r.stdout or '')[:12]
        except Exception:
            return False

    def _resolv_unimmutable(self):
        import subprocess as _sp
        try:
            return _sp.run(['sudo', '-n', 'chattr', '-i', '/etc/resolv.conf'],
                           capture_output=True, timeout=10).returncode == 0
        except Exception:
            return False

    def _resolv_reimmutable(self):
        import subprocess as _sp
        try:
            return _sp.run(['sudo', '-n', 'chattr', '+i', '/etc/resolv.conf'],
                           capture_output=True, timeout=10).returncode == 0
        except Exception:
            return False

    def _dns_bridge_enable(self):
        """Пишет юнит dotbridge и запускает мост.

        ⭐ v2.0.3: resolv.conf больше НЕ трогаем — DNS перехватывается
        nft-цепочкой dns_dnat в нашей таблице (все исходящие udp/53,
        кроме loopback, днатятся на 127.0.0.1:53). Это надёжнее:
        resolv.conf часто прибит immutable (AmneziaVPN) и правится
        только с chattr, а nft-цепочка живёт и умирает вместе со
        snimod — никаких хвостов в системе.
        """
        import subprocess as _sp
        unit_path = Path('/etc/systemd/system/ciadpi-dotbridge.service')
        content = self.DOTBRIDGE_UNIT.format(bridge=self.dotbridge_py)
        ok_steps = []
        # 1) юнит через sudo tee (покрыт sudoers)
        try:
            tmp = Path('/tmp/ciadpi_dotbridge.service')
            tmp.write_text(content, encoding='utf-8')
            with open(tmp, 'rb') as f_in:
                r = _sp.run(['sudo', '-n', self.TEE_BIN, str(unit_path)],
                            stdin=f_in, capture_output=True, timeout=30)
            ok_steps.append(('unit', r.returncode == 0 and unit_path.stat().st_size > 0))
        except Exception as e:
            ok_steps.append(('unit', False))
            print(f"⚠️ dotbridge unit: {e}")
        # 2) старт моста (только если ещё не активен — повторный enable
        # не должен поднимать ранее остановленный мост)
        try:
            r = _sp.run(['sudo', '-n', self.SYSTEMCTL_BIN, 'daemon-reload'],
                        capture_output=True, timeout=30)
            r_is_active = _sp.run(
                ['systemctl', 'is-active', 'ciadpi-dotbridge.service'],
                capture_output=True, timeout=10)
            already = (r_is_active.stdout or b'').strip() == b'active' \
                if isinstance(r_is_active.stdout, bytes) else \
                (r_is_active.stdout or '').strip() == 'active'
            if already:
                ok_steps.append(('start', True))
            else:
                r = _sp.run(['sudo', '-n', self.SYSTEMCTL_BIN, 'enable', '--now',
                             'ciadpi-dotbridge.service'],
                            capture_output=True, timeout=30)
                ok_steps.append(('start', r.returncode == 0))
        except Exception as e:
            ok_steps.append(('start', False))
            print(f"⚠️ dotbridge start: {e}")
        return all(ok for _, ok in ok_steps), ok_steps

    def _dns_bridge_disable(self):
        """Остановка моста (nft-цепочка dns_dnat снесётся вместе с таблицей
        snimod в ExecStopPost — система вернётся к исходному DNS без хвостов)."""
        import subprocess as _sp
        try:
            _sp.run(['sudo', '-n', self.SYSTEMCTL_BIN, 'disable', '--now',
                     'ciadpi-dotbridge.service'],
                    capture_output=True, timeout=30)
            return True
        except Exception as e:
            print(f"⚠️ dotbridge disable: {e}")
            return False

    _PRIVILEGED_VERBS = {'start', 'stop', 'restart', 'reload',
                         'enable', 'disable', 'mask', 'unmask',
                         'daemon-reload'}

    def _systemctl(self, *args, timeout=60):
        privileged = bool(args) and args[0] in self._PRIVILEGED_VERBS
        if privileged:
            cmds = [
                ['sudo', '-n', self.SYSTEMCTL_BIN, *args],
                ['pkexec', 'systemctl', *args],
            ]
        else:
            cmds = [
                ['systemctl', *args],
                ['sudo', '-n', self.SYSTEMCTL_BIN, *args],
            ]
        last_err = ''
        for cmd in cmds:
            try:
                r = subprocess.run(cmd, capture_output=True, text=True,
                                   timeout=timeout)
                if r.returncode == 0:
                    return True, (r.stdout or '').strip()
                last_err = (r.stderr or r.stdout or '').strip()
                if args[0] in ('is-active', 'status', 'show', 'is-enabled') \
                        and r.stdout:
                    return True, r.stdout.strip()
            except (FileNotFoundError, subprocess.TimeoutExpired) as e:
                last_err = str(e)
                continue
        return False, last_err

    def write_unit(self):
        """(Пере)создаёт юнит ciadpi-snimod.service (sudo tee с проверкой
        размера — пустой юнит = masked)."""
        if not self.is_installed():
            return False, 'snimod не собран (snimod/make)'
        cfg = self.load_config()
        hosts = cfg.get('hosts') or self.default_hosts
        self.write_hosts_file(hosts)
        self._write_rules_files()
        content = self._UNIT_TEMPLATE.format(
            helper=self.rules_script,
            bin=self.snimod_bin,
            qnum=self.QNUM,
            hosts=self.hosts_file,
        )
        tmp = Path('/tmp/ciadpi_snimod_temp.service')
        tmp.write_text(content, encoding='utf-8')
        sudo_tee = ['sudo', '-n', self.TEE_BIN, str(self.UNIT_FILE)]
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
        return False, ('Не удалось записать юнит snimod (нужны права root): '
                       f'{last_err}. Запустите настройку привилегий.')

    def is_service_active(self):
        ok, out = self._systemctl('is-active', self.SERVICE)
        return ok and (out or '').strip() == 'active'

    def set_enabled(self, enabled: bool):
        verb = 'enable' if enabled else 'disable'
        return self._systemctl(verb, self.SERVICE)

    def start(self):
        ok, err = self.write_unit()
        if not ok:
            return False, err
        # ⭐ v2.0.2: DNS-мост поднимается вместе со snimod (DoT против
        # NXDOMAIN-блокировки ютуб-доменов) — но если он не поднялся,
        # движок всё равно стартует (SNI-мод независим).
        try:
            bridge_ok, steps = self._dns_bridge_enable()
            if not bridge_ok:
                print(f"⚠️ dotbridge не полностью: {steps}")
        except Exception as e:
            print(f"⚠️ dotbridge enable: {e}")
        ok, err = self._systemctl('start', self.SERVICE)
        if ok and self.is_service_active():
            return True, ''
        return False, err or 'service did not start'

    def stop(self):
        # ⭐ v2.0.5: ПОРЯДОК ОСТАНОВКИ. Раньше мост гасился ПЕРВЫМ, а
        # сервис (со своим ExecStopPost remove таблицы ciadpi_snimod,
        # где живёт dns_dnat) мог зависнуть на 90с SIGTERM — выходил
        # период, когда dns_dnat жив, а моста уже нет = ЧЁРНАЯ ДЫРА DNS
        # (весь интернет умирал, не только ютуб). Теперь: сначала
        # systemctl stop сервиса (таблица сносится гарантированно),
        # затем мост. Дополнительно: снос таблицы принудительно, если
        # сервис её почему-то не убрал.
        ok, err = self._systemctl('stop', self.SERVICE)
        # страховка: правила могли остаться (сервис не стартовал,
        # ExecStopPost не выполнился) — сносим руками
        try:
            if self.rules_active():
                self.remove_rules_fallback()
        except Exception as e:
            print(f"⚠️ snimod rules fallback: {e}")
        # мост гасим ПОСЛЕДНИМ — к этому моменту dns_dnat уже нет
        try:
            self._dns_bridge_disable()
        except Exception as e:
            print(f"⚠️ dotbridge disable: {e}")
        return ok, err

    def remove_rules_fallback(self):
        try:
            subprocess.run(
                ['sudo', '-n', self.NFT_BIN, 'delete', 'table',
                 'inet', self.NFT_TABLE],
                capture_output=True, timeout=15)
            return True
        except Exception:
            return False

    def rules_active(self):
        """Таблица ciadpi_snimod присутствует в ruleset (через
        sudo -n nft list ruleset — exact-argv в sudoers)."""
        try:
            r = subprocess.run(
                ['sudo', '-n', self.NFT_BIN, 'list', 'ruleset'],
                capture_output=True, text=True, timeout=15)
            return f'table inet {self.NFT_TABLE}' in (r.stdout or '')
        except Exception:
            return False


# ---------------- CLI ----------------

if __name__ == '__main__':
    import sys
    m = SnimodManager()
    cmd = sys.argv[1] if len(sys.argv) > 1 else 'status'
    if cmd == 'status':
        print('binary:', 'OK' if m.is_installed() else 'NOT BUILT (make in snimod/)')
        ok, out = m._systemctl('is-active', m.SERVICE)
        print('service:', out or '?')
        print('rules:', 'active' if m.rules_active() else 'absent')
        print('hosts:', ', '.join(m.load_config().get('hosts', [])[:5]))
    elif cmd == 'start':
        ok, err = m.start()
        print('start:', 'OK' if ok else f'FAIL {err}')
    elif cmd == 'stop':
        ok, err = m.stop()
        print('stop:', 'OK' if ok else f'FAIL {err}')
    elif cmd == 'install-check':
        ok, msg = m.check_binary()
        print('binary check:', 'OK' if ok else f'FAIL {msg}')
    else:
        print('usage: ciadpi_snimod.py status|start|stop|install-check')

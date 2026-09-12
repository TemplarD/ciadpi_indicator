#!/usr/bin/env python3
"""ciadpi_dotbridge — локальный DNS-мост UDP/TCP :53 → DNS-over-TLS :853.

Зачем: пров даёт NXDOMAIN на youtube-домены в обычном DNS (UDP53
перехвачен провом), но DoT (853) не блокирует (проверено openssl).
Стандартный resolved/dnsmasq DoT-клиентом не являются, а systemd-resolved
на этой машине не используется (resolv.conf → 8.8.8.8 напрямую).

Как работает: слушает 127.0.0.1:53 (UDP и TCP), каждый DNS-запрос
оборачивает в TLS-сессию к 1.1.1.1:853 (server name cloudflare-dns.com,
RFC 7858 length-prefixed framing) и возвращает ответ клиенту.

Запуск (из юнита snimod, ExecStartPost):
    sudo python3 ciadpi_dotbridge.py --upstream 1.1.1.1 --port 53
Флаги: --upstream IP (по умолчанию 1.1.1.1), --port N (53),
       --ttl-cache N (сек, кэш ответов, по умолчанию 300), --debug.
"""
import argparse
import socket
import socketserver
import ssl
import sys
import threading
import time
import struct
from pathlib import Path

CACHE = {}          # (wire-bytes-hash) -> (answer, expiry)
CACHE_LOCK = threading.Lock()
UPSTREAM = ('1.1.1.1', 853)
TLS_NAME = 'cloudflare-dns.com'
DEBUG = False
STATS = {'queries': 0, 'dot_ok': 0, 'dot_fail': 0, 'cache_hit': 0}


def log(msg):
    if DEBUG:
        print(f"[dotbridge] {msg}", flush=True)


def dot_query(wire: bytes, timeout=6.0) -> bytes | None:
    """Запрос по DNS-over-TLS (RFC 7858): 2-байтный length-prefix.

    ⭐ v2.0.8: server_hostname настраивается (--tls-name / конфиг) —
    мост умеет работать с любым DoT-провайдером: 1.1.1.1/
    cloudflare-dns.com, 8.8.8.8/dns.google, 9.9.9.9/dns.quad9.
    """
    try:
        raw = socket.create_connection(UPSTREAM, timeout=timeout)
        ctx = ssl.create_default_context()
        with ctx.wrap_socket(raw, server_hostname=TLS_NAME) as tls:
            tls.sendall(struct.pack('>H', len(wire)) + wire)
            hdr = b''
            while len(hdr) < 2:
                chunk = tls.recv(2 - len(hdr))
                if not chunk:
                    return None
                hdr += chunk
            (rlen,) = struct.unpack('>H', hdr)
            answer = b''
            while len(answer) < rlen:
                chunk = tls.recv(rlen - len(answer))
                if not chunk:
                    return None
                answer += chunk
            return answer
    except Exception as e:
        log(f"DoT fail: {e}")
        return None


class UDPHandler(socketserver.BaseRequestHandler):
    def handle(self):
        global CACHE
        data, sock = self.request[0], self.request[1]
        key = data
        now = time.time()
        with CACHE_LOCK:
            hit = CACHE.get(key)
            if hit and hit[1] > now:
                CACHE['hits'] = CACHE.get('hits', 0)
                STATS['cache_hit'] += 1
                sock.sendto(hit[0], self.client_address)
                return
        STATS['queries'] += 1
        answer = dot_query(data)
        if answer:
            STATS['dot_ok'] += 1
            with CACHE_LOCK:
                CACHE[key] = (answer, now + 300)
                if len(CACHE) > 4096:
                    for k in [k for k, v in CACHE.items()
                              if isinstance(v, tuple) and v[1] < now][:1024]:
                        CACHE.pop(k, None)
            sock.sendto(answer, self.client_address)
        else:
            STATS['dot_fail'] += 1


class TCPHandler(socketserver.BaseRequestHandler):
    def handle(self):
        data = self.request
        try:
            hdr = data.recv(2)
            if len(hdr) < 2:
                return
            (rlen,) = struct.unpack('>H', hdr)
            wire = b''
            while len(wire) < rlen:
                chunk = data.recv(rlen - len(wire))
                if not chunk:
                    return
                wire += chunk
            now = time.time()
            with CACHE_LOCK:
                hit = CACHE.get(wire)
                if hit and hit[1] > now:
                    STATS['cache_hit'] += 1
                    data.sendall(struct.pack('>H', len(hit[0])) + hit[0])
                    return
            STATS['queries'] += 1
            answer = dot_query(wire)
            if answer:
                STATS['dot_ok'] += 1
                with CACHE_LOCK:
                    CACHE[wire] = (answer, now + 300)
                data.sendall(struct.pack('>H', len(answer)) + answer)
            else:
                STATS['dot_fail'] += 1
        except Exception as e:
            log(f"tcp handler: {e}")


class ThreadingUDPServer(socketserver.ThreadingUDPServer):
    allow_reuse_address = True


class ThreadingTCPServer(socketserver.ThreadingTCPServer):
    allow_reuse_address = True


def main():
    global UPSTREAM, TLS_NAME, DEBUG
    ap = argparse.ArgumentParser()
    ap.add_argument('--upstream', default='1.1.1.1')
    ap.add_argument('--tls-name', default=None,
                    help='server_hostname TLS (по умолчанию '
                         'cloudflare-dns.com; для 8.8.8.8 — dns.google, '
                         'для 9.9.9.9 — dns.quad9)')
    ap.add_argument('--port', type=int, default=53)
    ap.add_argument('--debug', action='store_true')
    args = ap.parse_args()
    UPSTREAM = (args.upstream, 853)
    # ⭐ v2.0.8: конфиг dotbridge.json имеет приоритет для tls-name,
    # если флаг не задан явно (конструктор окна настроек пишет его)
    if args.tls_name:
        TLS_NAME = args.tls_name
    else:
        try:
            import json as _json
            cfgp = Path.home() / '.config' / 'ciadpi' / 'dotbridge.json'
            cfg = _json.loads(cfgp.read_text(encoding='utf-8'))
            TLS_NAME = cfg.get('tls_name') or TLS_NAME
            if cfg.get('upstream') and args.upstream == '1.1.1.1':
                UPSTREAM = (cfg['upstream'], 853)
        except Exception:
            pass
    DEBUG = args.debug

    udp = ThreadingUDPServer(('127.0.0.1', args.port), UDPHandler)
    tcp = ThreadingTCPServer(('127.0.0.1', args.port), TCPHandler)
    print(f"[dotbridge] DNS-мост 127.0.0.1:{args.port} → "
          f"{UPSTREAM[0]}:853 (DoT, tls={TLS_NAME}) запущен", flush=True)
    threading.Thread(target=tcp.serve_forever, daemon=True).start()
    try:
        udp.serve_forever()
    except KeyboardInterrupt:
        pass


if __name__ == '__main__':
    main()

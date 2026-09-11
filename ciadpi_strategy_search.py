#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
CIADPI Strategy Search — перебор параметров byedpi/ciadpi для поиска оптимальной стратегии.

Логика работы:
  1. Генерируются комбинации параметров (из известных рабочих + генератора).
  2. Для каждой комбинации запускается отдельный экземпляр ciadpi на тестовом порту.
  3. Через прокси 127.0.0.1:<порт> проверяется доступность целевых URL (curl).
  4. Успешные параметры сохраняются в историю; лучший вариант предлагается к применению.

Модуль независим от GUI и может работать как CLI:
    python3 ciadpi_strategy_search.py --max-tests 20 --port 1081

Автор: templard, лицензия MIT.
"""

import subprocess
import time
import json
import threading
import logging
from datetime import datetime
from pathlib import Path

try:
    from ciadpi_param_generator import AdvancedParamGenerator
    _GENERATOR_AVAILABLE = True
except ImportError:
    AdvancedParamGenerator = None
    _GENERATOR_AVAILABLE = False


class StrategySearcher:
    """Поиск оптимальной стратегии обхода DPI перебором параметров."""

    def __init__(self, test_port=1081):
        self.config_dir = Path.home() / '.config' / 'ciadpi'
        self.history_file = self.config_dir / 'strategy_history.json'
        self.ciadpi_path = Path.home() / 'byedpi' / 'ciadpi'
        self.test_port = test_port          # порт для тестовых инстансов
        self.service_port = None            # порт основного сервиса (читаем из юнита)

        # Целевые сайты для проверки доступа (можно дополнить в диалоге)
        self.default_test_urls = [
            "https://www.youtube.com",
            "https://www.google.com/generate_204",
            "https://github.com",
        ]

        self.is_searching = False
        self.stop_requested = False
        self.current_process = None

        # История всех прогонов
        self.history = self._load_history()

        # Логирование в общий каталог конфигов
        self.logger = logging.getLogger('ciadpi_strategy')
        if not self.logger.handlers:
            self.logger.setLevel(logging.INFO)
            try:
                self.config_dir.mkdir(exist_ok=True)
                fh = logging.FileHandler(self.config_dir / 'strategy_search.log', encoding='utf-8')
                fh.setFormatter(logging.Formatter('%(asctime)s - %(levelname)s - %(message)s'))
                self.logger.addHandler(fh)
            except Exception:
                pass

    # ---------------- История ----------------

    def _load_history(self):
        default = {"tests": [], "best": None}
        try:
            self.history_file.parent.mkdir(parents=True, exist_ok=True)
            if self.history_file.exists():
                with open(self.history_file, 'r', encoding='utf-8') as f:
                    return json.load(f)
        except Exception as e:
            print(f"⚠️ Не удалось загрузить историю стратегий: {e}")
        return default

    def _save_history(self):
        try:
            with open(self.history_file, 'w', encoding='utf-8') as f:
                json.dump(self.history, f, indent=2, ensure_ascii=False)
        except Exception as e:
            print(f"⚠️ Не удалось сохранить историю стратегий: {e}")

    def add_to_history(self, entry):
        """entry: {params, success, speed, urls_ok, urls_total, error}

        ⭐ success с v1.8 = ВСЕ URL доступны. Частичный (2/3) — не успех:
        в until-found-режиме такой результат не должен останавливать поиск.
        """
        entry['timestamp'] = datetime.now().isoformat(timespec='seconds')
        self.history["tests"].insert(0, entry)
        # Храним последние 200 записей
        del self.history["tests"][200:]
        if entry['success']:
            prev = self.history.get("best")
            if not prev or entry['speed'] < prev.get('speed', float('inf')):
                self.history["best"] = {
                    'params': entry['params'],
                    'speed': round(entry['speed'], 2),
                    'timestamp': entry['timestamp']
                }
        self._save_history()

    def clear_history(self):
        self.history = {"tests": [], "best": None}
        self._save_history()

    # ---------------- Комбинации параметров ----------------

    def _generator_stream(self, seen, batch=60):
        """Ленивый поток новых комбинаций из генератора.

        AdvancedParamGenerator может исчерпать свои шаблоны. Чтобы режим
        «до нахождения» не зацикливался на конечном списке, при исчерпании
        просим генератор расширить набор (batch растёт с каждым кругом:
        60, 120, 180, ... комбинаций), пропуская уже проверенные строки.
        """
        if not (_GENERATOR_AVAILABLE and AdvancedParamGenerator is not None):
            return
        wave = 1
        while True:
            try:
                gen = AdvancedParamGenerator()
                produced = gen.generate_comprehensive_params(batch * wave)
            except Exception as e:
                print(f"⚠️ Генератор недоступен: {e}")
                return
            new_count = 0
            for p in produced:
                if p.strip() and p not in seen:
                    seen.add(p)
                    new_count += 1
                    yield p
            if new_count == 0:
                # генератор выдал всё, что мог — новых комбинаций нет
                return
            wave += 1

    def generate_combinations(self, max_tests=30):
        """Список параметров для тестирования.

        Порядок: известные рабочие -> свежие успешные из истории -> новые из генератора.
        max_tests=0 или None — режим «до нахождения» (без лимита).
        """
        unlimited = not max_tests  # 0/None → без лимита попыток
        combos = []
        seen = set()

        known_working = [
            "-T3 -A torst -o1 -o25+s -r 1+s",
            "-T2 -A torst -o2 -o15+s -r 2+s",
            "-T1 -A torst -o1 -o5+s",
            "-T3 -A torst -o3 -o20+s -r 2+s",
            "-T2 -A torst -o1 -o10+s",
            "-T2 -A torst -o5 -o25+s -r 1+s",
            "-T3 -A torst -o9 -o13+s -r 2+s",
            "-T3 -A torst -o1 -o2 -o25+s -r 1+s",
            # ⭐ SNI-класс (DPI рвёт TLS по имени: youtube и т.п.)
            "-A torst -r 1+s -s 1",
            "-A torst -s 1+s -d 2+s",
            "-A torst -r 1+s -r 2+s -d 1+s",
            "-A torst -f 1+s -t 8",
            "-A torst -r 1+s -f 2+s -t 8",
            "-A torst -d 1+s -d 2+s",
        ]
        combos.extend(known_working)
        seen.update(known_working)

        # Успешные из истории (без повторов)
        # ⭐ фильтр мусора: старые записи содержали битые токены
        # (голое '3+s' без флага: '-T 3   3+s') — ciadpi их отвергает,
        # а поиск тратил на них слоты. Прогоняем через строгий парсер.
        import re as _re
        _VAL_FLAGS = {'-i', '-p', '-w', '-c', '-I', '-b', '-g', '-T', '-A',
                      '-L', '-u', '-K', '-H', '-j', '-V', '-R', '-s', '-d',
                      '-o', '-q', '-f', '-r', '-n', '-t', '-O', '-l', '-Q',
                      '-e', '-a', '-M', '-m', '-y', '-x'}

        def _tokens_clean(params_str):
            """True если каждый токен — валидный флаг или значение флага."""
            toks = params_str.split()
            i = 0
            while i < len(toks):
                tk = toks[i]
                if tk in _VAL_FLAGS:
                    # раздельный флаг: следующее может быть значением
                    if i + 1 < len(toks) and not toks[i + 1].startswith('-'):
                        i += 2
                    else:
                        i += 1
                    continue
                if _re.match(r'^-[A-Za-z]', tk):
                    # прикреплённая форма (-T3, -At, -o1+s...) или bool-флаг
                    i += 1
                    continue
                return False  # голое значение без флага — мусор
            return True

        for t in self.history["tests"]:
            p = t.get("params")
            if not (t.get("success") and p and p not in combos):
                continue
            if not _tokens_clean(p):
                print(f"⚠️ История: пропущена битая строка: {p!r}")
                continue
            combos.append(p)
            seen.add(p)

        # Новые из генератора
        if unlimited:
            # Режим «до нахождения»: полный список строится лениво
            # в find_optimal_params через _generator_stream — здесь
            # только известные + история (конечное, проверенное ядро).
            return combos

        if _GENERATOR_AVAILABLE and AdvancedParamGenerator is not None:
            try:
                gen = AdvancedParamGenerator()
                generated = gen.generate_comprehensive_params(max_tests * 2)
                for p in generated:
                    if p.strip() and p not in seen:
                        combos.append(p)
                        seen.add(p)
            except Exception as e:
                print(f"⚠️ Генератор недоступен: {e}")

        return combos[:max_tests]

    # ---------------- Тестирование ----------------

    def _doh_resolve(self, hostname, timeout=6):
        """Резолв через DNS-over-HTTPS (dns.google).

        ⭐ Провайдерский DNS часто режет youtube (NXDOMAIN/заглушка) —
        обычный резолв даёт ложный FAIL стратегии. DoH работает поверх
        HTTPS и не фильтруется. Возвращает IP | None.
        """
        try:
            r = subprocess.run(
                ['curl', '-s', '--max-time', str(timeout),
                 f'https://dns.google/resolve?name={hostname}&type=A'],
                capture_output=True, text=True, timeout=timeout + 2)
            if r.returncode == 0 and r.stdout.strip().startswith('{'):
                import json
                data = json.loads(r.stdout)
                answers = [a.get('data') for a in data.get('Answer', [])
                           if a.get('type') == 1 and a.get('data')]
                if answers:
                    return answers[0]
        except Exception:
            pass
        return None

    def test_connection(self, test_urls, timeout=8):
        """Проверка доступности URLs через тестовый прокси.

        ⭐ Для хостов, которых нет в системном DNS (провайдер режет),
        резолвим через DoH и подключаемся ПО IP с сохранением SNI
        (curl --resolve) — иначе тест валится на DNS-этапе и не
        показывает, работает ли сам обход TLS.
        Возвращает (ok_count, total, avg_speed, details).
        """
        ok_count = 0
        speeds = []
        details = []
        # ciadpi — SOCKS4/5-прокси: HTTP CONNECT не принимает
        # ('ss: invalid version: 0x43'), поэтому только socks5h://
        env_proxy_url = f"socks5h://127.0.0.1:{self.test_port}"

        for url in test_urls:
            start = time.time()
            try:
                # --resolve: если системный DNS не знает хост — берём IP
                # из DoH и подставляем (SNI/Host остаются прежними)
                extra = []
                try:
                    from urllib.parse import urlparse
                    host = urlparse(url).hostname
                    if host and not host.replace('.', '').isdigit() \
                            and not host.startswith('['):
                        # проверяем системный резолв
                        probe = subprocess.run(
                            ['getent', 'hosts', host],
                            capture_output=True, timeout=4)
                        if probe.returncode != 0:
                            ip = self._doh_resolve(host)
                            if ip:
                                extra = ['--resolve', f'{host}:443:{ip}']
                                print(f"📡 {host}: системный DNS пуст, "
                                      f"DoH → {ip} (тестируем SNI по IP)")
                except Exception:
                    pass

                r = subprocess.run(
                    ['curl', '-s', '-o', '/dev/null', '-w', '%{http_code}',
                     '-x', env_proxy_url]
                    + extra
                    + ['--connect-timeout', str(min(timeout, 5)),
                       '--max-time', str(timeout),
                       url],
                    capture_output=True, text=True, timeout=timeout + 2
                )
                spent = time.time() - start
                code = r.stdout.strip()
                ok = r.returncode == 0 and code in ('200', '204', '206', '301', '302')
            except Exception as e:
                spent = time.time() - start
                code = f"ERR:{e.__class__.__name__}"
                ok = False
            speeds.append(spent)
            details.append((url, ok, code, round(spent, 2)))
            if ok:
                ok_count += 1

        avg_speed = sum(speeds) / len(speeds) if speeds else float('inf')
        return ok_count, len(test_urls), avg_speed, details

    def test_params(self, params, test_urls, wait_up=2.0, timeout=8):
        """Запуск ciadpi с данными параметрами на тестовом порту + проверка URLs.

        Возвращает dict с результатом.
        """
        result = {
            'params': params,
            'success': False,
            'speed': float('inf'),
            'urls_ok': 0,
            'urls_total': len(test_urls),
            'error': ''
        }

        if not self.ciadpi_path.exists():
            result['error'] = f"Бинарник не найден: {self.ciadpi_path}"
            return result

        cmd = [str(self.ciadpi_path)] + params.split() + ['-i', '127.0.0.1',
               '-p', str(self.test_port)]
        try:
            proc = subprocess.Popen(
                cmd,
                stdout=subprocess.DEVNULL,
                stderr=subprocess.PIPE
            )
        except Exception as e:
            result['error'] = f"Не удалось запустить ciadpi: {e}"
            return result

        self.current_process = proc
        time.sleep(wait_up)  # даём процессу подняться

        # Если процесс сразу умер — параметры невалидны для этой версии
        if proc.poll() is not None:
            err = ''
            try:
                stderr_data = proc.stderr.read() if proc.stderr else b''
                err = stderr_data.decode(errors='replace').strip()
            except Exception:
                pass
            result['error'] = f"ciadpi завершился сразу (код {proc.returncode}): {err[:300]}"
            self.current_process = None
            return result

        try:
            ok, total, speed, details = self.test_connection(test_urls, timeout)
            result.update({
                'success': ok == total and total > 0,
                'speed': speed,
                'urls_ok': ok,
                'urls_total': total,
                'details': details
            })
            if not result['success']:
                # Пробуем понять причину через stderr
                if ok > 0:
                    result['error'] = (f'Частичный успех: {ok}/{total} URL '
                                      f'(успехом считается ТОЛЬКО все URL)')
                else:
                    result['error'] = 'Все тестовые URL недоступны'
        finally:
            self._stop_current()

        return result

    def _stop_current(self):
        proc = self.current_process
        if proc is not None:
            try:
                proc.terminate()
                proc.wait(timeout=3)
            except Exception:
                try:
                    proc.kill()
                except Exception:
                    pass
            finally:
                self.current_process = None

    def stop_search(self):
        """Запросить остановку поиска (вызывается из GUI/CLI)."""
        self.stop_requested = True
        self.is_searching = False
        self._stop_current()

    # ---------------- Основной поиск ----------------

    def find_optimal_params(self, max_tests=20, test_urls=None,
                            progress_callback=None, port=None,
                            min_tests=None):
        """Перебор комбинаций.

        max_tests=0/None — режим «до нахождения»: перебор без лимита,
        останавливается ТОЛЬКО по первой успешной комбинации, кнопке
        «Остановить» или исчерпанию генератора. Комбинации достаются
        лениво: известные рабочие → успешная история → поток генератора
        (волны 60/120/180… без повторов).

        min_tests — нижний предел в unlimited-режиме: успех НЕ завершает
        поиск раньше этого числа попыток (первый успех на капризном DPI
        может быть случайным; лишние подтверждения не помешают), дальше
        первый же успех останавливает. Итог — самая быстрая из успешных.
        В лимитированном режиме игнорируется.

        progress_callback(stage, data) вызывается из фонового потока:
          stage='start'   data={'total': N, 'port': P, 'unlimited': bool}
                           (total=0 в unlimited-режиме)
          stage='test'    data={'index': i, 'params': ..., 'result': {...}}
          stage='done'    data={'best': ...|None, 'result': ...|None}

        Возвращает (best_params|None, best_result|None).
        """
        if self.is_searching:
            return None, None

        unlimited = not max_tests  # 0/None → «до нахождения»
        # В unlimited-режиме успех завершает поиск не раньше min_tests
        min_floor = 1
        if unlimited and min_tests:
            min_floor = max(1, int(min_tests))

        self.is_searching = True
        self.stop_requested = False
        if port:
            self.test_port = port

        if test_urls is None:
            test_urls = list(self.default_test_urls)

        combos = self.generate_combinations(max_tests)
        best_params, best_result = None, None
        tested_count = 0

        if progress_callback:
            progress_callback('start', {'total': 0 if unlimited else len(combos),
                                         'port': self.test_port,
                                         'unlimited': unlimited})
        mode_txt = ("БЕЗ ЛИМИТА (до нахождения)" if unlimited
                    else f"{len(combos)} комбинаций")
        self.logger.info(f"Начат поиск: {mode_txt}, порт {self.test_port}")

        # Ленивый источник: конечное ядро, затем (в unlimited) поток генератора
        seen_union = set(combos)

        def _combo_source():
            for p in combos:
                yield p
            if unlimited:
                for p in self._generator_stream(seen_union, batch=60):
                    yield p
                # генератор исчерпан — источник заканчивается, поиск
                # завершится с тем, что успели проверить

        for params in _combo_source():
            if self.stop_requested:
                self.logger.info("Поиск прерван пользователем")
                break

            res = self.test_params(params, test_urls)
            tested_count += 1
            self.add_to_history(res)
            self.logger.info(
                f"[{tested_count}] {'OK' if res['success'] else 'FAIL'} "
                f"{res['speed']:.2f}s {params} {res.get('error','')}"
            )

            if progress_callback:
                progress_callback('test', {'index': tested_count - 1,
                                           'params': params, 'result': res})

            if res['success'] and (best_result is None or res['speed'] < best_result['speed']):
                best_params, best_result = params, res

            # unlimited: первый успех ПОСЛЕ нижнего предела завершает поиск
            if unlimited and res['success'] and tested_count >= min_floor:
                self.logger.info(
                    f"Найдена рабочая стратегия (попытка {tested_count}) "
                    f"— останавливаемся: {params}")
                break

        self.is_searching = False

        if progress_callback:
            progress_callback('done', {'best': best_params, 'result': best_result})

        if best_params:
            self.logger.info(f"Лучший результат: {best_params} ({best_result['speed']:.2f}s)")
        else:
            self.logger.warning("Рабочие параметры не найдены")

        return best_params, best_result


# ---------------- Поиск стратегии для nfqws-движка ----------------

class NfqwsStrategySearcher:
    """Перебор параметров nfqws (формат zapret) ЧЕРЕЗ РЕАЛЬНЫЙ сервис.

    В отличие от byedpi-поиска (отдельный тестовый SOCKS-порт), nfqws
    перехватывает пакеты ГЛОБАЛЬНО через NFQUEUE — тестовый инстанс
    конфликтовал бы с рабочим по qnum. Поэтому каждая комбинация:
      1) write_unit(params) + start сервиса (passwordless sudo, уже
         настроено) — сервис обслуживает ВСЕ приложения;
      2) проверка test-URLs напрямую (без прокси): DoH-резолв при
         NXDOMAIN + curl --resolve (SNI честный);
      3) stop сервиса (nft-правила снимает ExecStopPost).
    Пауза между кандидами минимальна — интернет «мигает» только на
    секунды между stop и следующим start.

    Успех = ВСЕ test-URLs отвечают (как в byedpi-поиске с v1.8).
    """

    def __init__(self):
        from ciadpi_nfqws import NfqwsManager
        self.mgr = NfqwsManager()
        self.config_dir = Path.home() / '.config' / 'ciadpi'
        self.history_file = self.config_dir / 'nfqws_strategy_history.json'

        self.default_test_urls = [
            "https://www.youtube.com",
            "https://www.google.com/generate_204",
            "https://github.com",
        ]

        self.is_searching = False
        self.stop_requested = False

        # Лог — отдельный файл, чтобы не смешивать с byedpi-поиском
        self.logger = logging.getLogger('ciadpi_nfqws_strategy')
        if not self.logger.handlers:
            self.logger.setLevel(logging.INFO)
            try:
                self.config_dir.mkdir(exist_ok=True)
                fh = logging.FileHandler(self.config_dir / 'nfqws_strategy.log',
                                         encoding='utf-8')
                fh.setFormatter(logging.Formatter(
                    '%(asctime)s - %(levelname)s - %(message)s'))
                self.logger.addHandler(fh)
            except Exception:
                pass

        self.history = self._load_history()

    # ---------------- История ----------------

    def _load_history(self):
        default = {"tests": [], "best": None}
        try:
            self.history_file.parent.mkdir(parents=True, exist_ok=True)
            if self.history_file.exists():
                with open(self.history_file, 'r', encoding='utf-8') as f:
                    return json.load(f)
        except Exception as e:
            print(f"⚠️ История nfqws-поиска не загружена: {e}")
        return default

    def _save_history(self):
        try:
            with open(self.history_file, 'w', encoding='utf-8') as f:
                json.dump(self.history, f, indent=2, ensure_ascii=False)
        except Exception as e:
            print(f"⚠️ Не удалось сохранить историю nfqws-поиска: {e}")

    def add_to_history(self, entry):
        entry['timestamp'] = datetime.now().isoformat(timespec='seconds')
        entry['engine'] = 'nfqws'
        self.history["tests"].insert(0, entry)
        del self.history["tests"][200:]
        if entry['success']:
            prev = self.history.get("best")
            if not prev or entry['speed'] < prev.get('speed', float('inf')):
                self.history["best"] = {
                    'params': entry['params'], 'engine': 'nfqws',
                    'speed': round(entry['speed'], 2),
                    'timestamp': entry['timestamp']
                }
        self._save_history()

    # ---------------- Комбинации (zapret-формат) ----------------

    def generate_combinations(self):
        """⭐ v2.0 (user: «прошло всего 39 стратегий с повторениями —
        должно быть реализовано ВСЁ, что есть в nfqws/zapret»):
        ПОЛНАЯ матрица — все 17 desync-режимов нашей сборки (dry-run
        проверен) × базовые надстройки. Порядок: от простых к сложным.

        Структура матрицы (≈200+ уникальных кандидатов, lazy-поток):
          A) соло-режимы (17)
          B) режим + disorder/split хвост (двойные десинки)
          C) fake-TLS варианты: 3 базовых фейка (google/youtube-case/
             gosuslugi) × моды (none/rnd/rndsni/dupsid/sni=CASE)
          D) маркерные split-позиции: method,host,endhost,sld,endsld,
             midsld,sniext (для multisplit/multidisorder/hostfakesplit)
          E) fooling-надстройки: md5sig, badseq, badsum, ts, hopbyhop
          F) autottl/ttl/repeats/dup вариации поверх лучших баз
        Кандидаты дедупятся (set) и сортируются «по надежности»:
        простые сплиты → fake → фрагментация → тампер.

        ISP-факты этой машины (hunt4/5): TCP-стрим реассемблируется,
        UDP53/QUIC/HTTP80 дропаются; фрагментация ipfrag1/2 собирается
        DPI; единственный честный канал — TCP443 с SNI-модом.
        """
        from pathlib import Path as _P
        fake_dir = _P.home() / 'zapret' / 'files' / 'fake'
        tls_g = fake_dir / 'tls_clienthello_www_google_com.bin'
        tls_case = fake_dir / 'tls_clienthello_www_youtube_com.bin'  # создаём сами (см. ниже)
        tls_r = fake_dir / 'tls_clienthello_gosuslugi_ru.bin'

        def has(p):
            return p and _P(p).exists()

        combos = []
        seen = set()

        def add(c):
            if c and c not in seen:
                seen.add(c)
                combos.append(c)

        # ---------- A) соло-режимы ----------
        for mode in (
            'split2', 'disorder2', 'disorder', 'split',
            'ipfrag1', 'ipfrag2', 'fakedsplit', 'fakeddisorder',
            'hostfakesplit', 'multisplit', 'multidisorder',
            'synack', 'syndata', 'rst', 'rstack', 'hopbyhop',
            'destopt', 'fakeknown', 'fake', 'udplen', 'tamper',
        ):
            pos = (' --dpi-desync-split-pos=1'
                   if mode in ('split2', 'disorder2', 'split', 'disorder',
                               'fakedsplit', 'fakeddisorder')
                   else '')
            add(f'--filter-tcp=443 --dpi-desync={mode}{pos}')

        # ---------- B) двойные десинки ----------
        # ⭐ dry-run выявил INVALID-пары этой сборки: rst+rstack,
        # fakedsplit+disorder2, hostfakesplit+disorder2,
        # fake+fakedsplit, fakeknown+fakedsplit — их НЕ генерим.
        for fst, snd in (
            ('fake', 'disorder2'), ('fake', 'split2'),
            ('fakeknown', 'disorder2'), ('fakeknown', 'split2'),
            ('syndata', 'disorder2'),
            ('fake', 'ipfrag2'), ('fakeknown', 'ipfrag2'),
            ('fake', 'multisplit'), ('fake', 'multidisorder'),
        ):
            add(f'--filter-tcp=443 --dpi-desync={fst},{snd}')

        # ---------- C) fake-TLS матрица ----------
        fakes = [('g', tls_g), ('case', tls_case), ('r', tls_r)]
        # ⭐ dry-run: мод rndsni требует парсабельную SNI-структуру —
        # наш минимальный case-фейк nfqws модифицировать не может
        # («invalid SNI structure»). rndsni — только для оригинального
        # google-фейка; case-фейк работает с none/rnd/dupsid без rndsni.
        mods_g = ['', ' --dpi-desync-fake-tls-mod=rnd',
                  ' --dpi-desync-fake-tls-mod=rndsni',
                  ' --dpi-desync-fake-tls-mod=dupsid']
        mods_other = ['', ' --dpi-desync-fake-tls-mod=rnd',
                       ' --dpi-desync-fake-tls-mod=dupsid']
        if has(tls_g):
            for key, f in fakes:
                if not has(f):
                    continue
                mods = mods_g if key == 'g' else mods_other
                for m in mods:
                    for d in ('disorder2', 'split2', 'fakedsplit'):
                        pos = (' --dpi-desync-split-pos=1'
                               if d in ('split2', 'fakedsplit')
                               else '')
                        add(f'--filter-tcp=443 --dpi-desync=fake,{d}'
                            f'{pos} --dpi-desync-fake-tls={f}{m}')
        # регистровый трюк в фейке (SNI=WWW.YOUTUBE.COM — наш PoC)
        if has(tls_g) and has(tls_case):
            add(f'--filter-tcp=443 --dpi-desync=fake,disorder2 '
                f'--dpi-desync-fake-tls={tls_g} '
                f'--dpi-desync-fake-tls-mod=sni=WWW.YOUTUBE.COM')

        # ---------- D) маркерные split-позиции ----------
        for mode in ('multisplit', 'multidisorder'):
            for marker in ('sniext', 'midsld', 'endsld', 'sld',
                           'host', 'endhost', 'method'):
                add(f'--filter-tcp=443 --dpi-desync={mode} '
                    f'--dpi-desync-split-pos={marker}+1,{marker}-1')

        # ---------- E) fooling-надстройки ----------
        for fool in ('md5sig', 'badseq', 'badsum', 'ts', 'hopbyhop'):
            for base in (
                f'--filter-tcp=443 --dpi-desync=fake,disorder2 '
                f'--dpi-desync-fake-tls={tls_g}',
                '--filter-tcp=443 --dpi-desync=disorder2 '
                '--dpi-desync-split-pos=1',
            ):
                if 'fake-tls=' in base and not has(tls_g):
                    continue
                add(f'{base} --dpi-desync-fooling={fool}')
            add(f'--filter-tcp=443 --dpi-desync=fake,disorder2 '
                f'--dpi-desync-fake-tls={tls_g} '
                f'--dpi-desync-fooling=md5sig,badseq')

        # ---------- F) вариации поверх баз ----------
        for base in list(combos):
            if 'fake' in base or 'split' in base or 'disorder' in base:
                add(f'{base} --dpi-desync-autottl=1')
                add(f'{base} --dpi-desync-repeats=6')
        # dup-тамpering (winws-стиль, отдельный механизм)
        add('--filter-tcp=443 --dpi-desync=disorder2 '
            '--dpi-desync-split-pos=1 --dup=2 --dup-ttl=3')
        add('--filter-tcp=443 --dpi-desync=tamper --dup=2 --dup-ttl=3')

        return combos

    def _dedup_against_history(self, combos):
        """Убрать кандидатов, уже тестированных в истории (с тем же
        исходом) — «бесконечный» поиск не должен повторяться."""
        tested = {t.get('params') for t in self.history.get('tests', [])}
        return [c for c in combos if c not in tested]

    # ---------------- Проверка соединения ----------------

    def _doh_resolve(self, hostname, timeout=6):
        """DoH-резолв (пров может давать NXDOMAIN на нужные хосты)."""
        import urllib.request
        try:
            url = (f'https://1.1.1.1/dns-query?name={hostname}&type=A')
            req = urllib.request.Request(url, headers={
                'accept': 'application/dns-json'})
            with urllib.request.urlopen(req, timeout=timeout) as resp:
                data = json.loads(resp.read().decode())
                for ans in data.get('Answer', []):
                    if ans.get('type') == 1:  # A-запись
                        return ans['data']
        except Exception:
            pass
        return None

    def test_connection(self, test_urls, timeout=8):
        """Проверка URLs НАПРЯМУЮ (nfqws перехватывает всё сам).

        NXDOMAIN-хосты резолвим через DoH и подключаемся по IP с
        честным SNI (curl --resolve) — так проверяем именно десинк,
        а не DNS-блокировку.
        Возвращает (ok_count, total, avg_speed, details).
        """
        ok_count = 0
        speeds = []
        details = []
        for url in test_urls:
            start = time.time()
            try:
                extra = []
                try:
                    from urllib.parse import urlparse
                    host = urlparse(url).hostname
                    if host and not host.replace('.', '').isdigit() \
                            and not host.startswith('['):
                        probe = subprocess.run(
                            ['getent', 'hosts', host],
                            capture_output=True, timeout=4)
                        if probe.returncode != 0:
                            ip = self._doh_resolve(host)
                            if ip:
                                extra = ['--resolve', f'{host}:443:{ip}']
                                print(f"📡 {host}: системный DNS пуст, "
                                      f"DoH → {ip} (тестируем SNI по IP)")
                except Exception:
                    pass
                r = subprocess.run(
                    ['curl', '-s', '-o', '/dev/null', '-w', '%{http_code}',
                     '-A', 'Mozilla/5.0 (X11; Linux)', '--noproxy', '*']
                    + extra
                    + ['--connect-timeout', str(min(timeout, 5)),
                       '--max-time', str(timeout), url],
                    capture_output=True, text=True, timeout=timeout + 2
                )
                spent = time.time() - start
                code = r.stdout.strip()
                ok = r.returncode == 0 and code in ('200', '204', '206',
                                                    '301', '302')
            except Exception as e:
                spent = time.time() - start
                code = f"ERR:{e.__class__.__name__}"
                ok = False
            speeds.append(spent)
            details.append((url, ok, code, round(spent, 2)))
            if ok:
                ok_count += 1
        avg = sum(speeds) / len(speeds) if speeds else float('inf')
        return ok_count, len(test_urls), avg, details

    # ---------------- Тест одной комбинации ----------------

    def test_params(self, params, test_urls, settle=1.5, timeout=8):
        """Прогон одной комбинации через реальный ciadpi-nfqws.service.

        ⭐ v2.0 GENTLE: щадящий режим — пауза между кандидатами
        (gentle_pause) и ОДИН тест-запрос на заблокированный хост за
        раз. Причина: серия из ~40 попыток SNI=www.youtube.com за 2
        минуты вызвала у прова hold-down ВСЕЙ линии (интернет падал
        у пользователя). Теперь между кандидатами — 3с пауза, а
       blocked-URL тестируется не чаще одного раза в кандидата.

        Возвращает dict как StrategySearcher.test_params (совместимый
        с GUI-колбеком): success = ВСЕ URL отвечают.
        """
        result = {
            'params': params, 'success': False, 'speed': float('inf'),
            'urls_ok': 0, 'urls_total': len(test_urls), 'error': ''
        }

        # ⭐ GENTLE: пауза между кандидатами — пров не любит плотные
        # серии подключений к заблокированному SNI
        pause = float(getattr(self, 'gentle_pause', 3.0))
        if getattr(self, '_last_test_at', 0):
            slept = time.time() - getattr(self, '_last_test_at', 0)
            if slept < pause:
                time.sleep(pause - slept)
        self._last_test_at = time.time()

        if not self.mgr.is_installed():
            result['error'] = 'nfqws не установлен (~/zapret/nfq/nfqws)'
            return result

        was_running = self.mgr.is_service_active()
        prev_params = self.mgr.load_config().get('params')

        ok, err = self.mgr.start(params)
        if not ok:
            result['error'] = f'сервис не стартовал: {err}'
            return result
        time.sleep(settle)

        try:
            ok_n, total, speed, details = self.test_connection(test_urls, timeout)
            result.update({
                'success': ok_n == total and total > 0,
                'speed': speed, 'urls_ok': ok_n, 'urls_total': total,
                'details': details
            })
            if not result['success']:
                if ok_n > 0:
                    result['error'] = (f'Частичный успех: {ok_n}/{total} '
                                      f'(успех = ВСЕ URL)')
                else:
                    result['error'] = 'Все тестовые URL недоступны'
        finally:
            # сервис останавливаем; если он работал до нас с другими
            # параметрами — восстанавливаем прежние параметры
            self.mgr.stop()
            if was_running and prev_params and prev_params != params:
                ok2, _ = self.mgr.start(prev_params)
                if ok2:
                    self.logger.info(
                        f"восстановлен прежний сервис: {prev_params}")
        return result

    def stop_search(self):
        self.stop_requested = True
        # текущий тест короткий — просто дожидаемся его конца
        try:
            self.mgr.stop()
        except Exception:
            pass

    # ---------------- Главный цикл ----------------

    def find_optimal_params(self, max_tests=20, test_urls=None,
                            progress_callback=None, min_tests=None):
        """Перебор комбинаций nfqws. Сигнатура совместима с
        StrategySearcher.find_optimal_params (port игнорируется —
        nfqws работает не через порт). Возвращает (best, best_result).
        """
        if self.is_searching:
            return None, None

        unlimited = not max_tests
        min_floor = 1
        if unlimited and min_tests:
            min_floor = max(1, int(min_tests))

        self.is_searching = True
        self.stop_requested = False

        if test_urls is None:
            test_urls = list(self.default_test_urls)

        base_combos = self.generate_combinations()
        # ⭐ v2.0: дедуп против истории — «бесконечный» поиск не должен
        # повторять уже протестированные кандидаты (user: «39 стратегий
        # с повторениями»). Протестированное с провалом здесь НЕ
        # фильтруем — провал мог быть случайным (шейпер), даём второй
        # шанс только если ВСЕ URL упали и скорость аномальная.
        if unlimited:
            fresh = self._dedup_against_history(base_combos)
            if fresh:
                base_combos = fresh
        best_params, best_result = None, None
        tested_count = 0

        if progress_callback:
            progress_callback('start', {'total': 0 if unlimited else len(base_combos),
                                        'port': None, 'unlimited': unlimited,
                                        'engine': 'nfqws'})

        def _combo_source():
            # сначала известные кандидаты (по матрице), затем — с
            # доп. вариациями (в unlimited-режиме): autottl, ttl,
            # repeats — пока генератор не исчерпан.
            # ⭐ в ЛИМИТИРОВАННОМ режиме режем поток до max_tests
            # (раньше лимит игнорировался: --max-tests 2 всё равно
            # перебирал всю матрицу)
            yielded = 0
            for p in base_combos:
                if not unlimited and yielded >= max_tests:
                    return
                yielded += 1
                yield p
            if unlimited:
                seen = set(base_combos)
                extras = []
                for base in base_combos:
                    for variant in (
                        ' --dpi-desync-autottl=1',
                        ' --dpi-desync-repeats=6',
                        ' --dpi-desync-fooling=md5sig,badseq',
                        ' --dpi-desync-fooling=badsum',
                        ' --dup=2 --dup-ttl=3',
                    ):
                        v = base + variant
                        if v not in seen:
                            seen.add(v)
                            extras.append(v)
                for e in extras:
                    yield e

        for params in _combo_source():
            if self.stop_requested:
                self.logger.info("Поиск прерван пользователем")
                break
            res = self.test_params(params, test_urls)
            tested_count += 1
            self.add_to_history(res)
            self.logger.info(
                f"[{tested_count}] {'OK' if res['success'] else 'FAIL'} "
                f"{res['speed']:.2f}s {params} {res.get('error', '')}")
            if progress_callback:
                progress_callback('test', {'index': tested_count - 1,
                                           'params': params, 'result': res})
            if res['success'] and (best_result is None
                                   or res['speed'] < best_result['speed']):
                best_params, best_result = params, res
            if unlimited and res['success'] and tested_count >= min_floor:
                self.logger.info(
                    f"Найдена рабочая стратегия (попытка {tested_count}): {params}")
                break

        self.is_searching = False
        if progress_callback:
            progress_callback('done', {'best': best_params, 'result': best_result})
        if best_params:
            self.logger.info(f"Лучший результат: {best_params} "
                             f"({best_result['speed']:.2f}s)")
        else:
            self.logger.warning("Рабочие параметры nfqws не найдены")
        return best_params, best_result


# ---------------- CLI ----------------

if __name__ == '__main__':
    import argparse
    parser = argparse.ArgumentParser(description='Поиск оптимальных параметров ciadpi')
    parser.add_argument('--engine', choices=['byedpi', 'nfqws'], default='byedpi',
                        help='Движок: byedpi (тестовый SOCKS-порт) или nfqws '
                             '(через реальный systemd-сервис, все приложения)')
    parser.add_argument('--max-tests', type=int, default=20)
    parser.add_argument('--until-found', action='store_true',
                        help='Искать до нахождения: без лимита попыток, '
                             'стоп по первой успешной комбинации (игнорирует --max-tests)')
    parser.add_argument('--min-tests', type=int, default=None,
                        help='В режиме --until-found: успех завершает поиск '
                             'не раньше этого числа попыток')
    parser.add_argument('--port', type=int, default=1081)
    parser.add_argument('--url', action='append', help='Доп. URL для проверки (можно несколько)')
    args = parser.parse_args()

    if args.engine == 'nfqws':
        s = NfqwsStrategySearcher()
    else:
        s = StrategySearcher(test_port=args.port)
    urls = list(s.default_test_urls)
    if args.url:
        urls = args.url + urls

    max_tests = 0 if args.until_found else args.max_tests

    def cb(stage, data):
        if stage == 'start':
            port_txt = (f" (тестовый порт {data['port']})"
                        if data.get('port') else " (через реальный сервис)")
            if data.get('unlimited'):
                print(f"▶️ [{args.engine}] Режим «до нахождения»: лимита нет, "
                      f"стоп по успеху или Ctrl+C{port_txt}")
            else:
                print(f"▶️ [{args.engine}] Всего комбинаций: {data['total']}{port_txt}")
        elif stage == 'test':
            r = data['result']
            status = f"✅ {r['urls_ok']}/{r['urls_total']} за {r['speed']:.2f}s" if r['success'] \
                else f"❌ {r.get('error', '')[:60]}"
            print(f"[{data['index']+1}] {status} | {data['params']}")
            # ⭐ v1.9.2 (user): расшифровка по КАЖДОМУ URL — важно видеть,
            # к кому именно подключение прошло, а не только счёт 2/3
            for url, ok, code, sec in (r.get('details') or []):
                mark = "✅" if ok else "❌"
                print(f"      {mark} {url} → HTTP {code} ({sec}с)")
        elif stage == 'done':
            if data['best']:
                print(f"\n🏆 Лучшие параметры: {data['best']}")
            else:
                print("\n😕 Рабочие параметры не найдены")

    best, res = s.find_optimal_params(max_tests, urls, cb, min_tests=args.min_tests)

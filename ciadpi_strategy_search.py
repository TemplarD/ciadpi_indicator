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
        """entry: {params, success, speed, urls_ok, urls_total, error}"""
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

    def generate_combinations(self, max_tests=30):
        """Список параметров для тестирования.

        Порядок: известные рабочие -> свежие успешные из истории -> новые из генератора.
        """
        combos = []

        known_working = [
            "-o1 -o25+s -T3 -At o--tlsrec 1+s",
            "-o2 -o15+s -T2 -At o--tlsrec",
            "-o1 -o5+s -T1 -At",
            "-o3 -o20+s -T3 -At o--tlsrec 2+s",
            "-o1 -o10+s -T2 -At",
            "-o5 -o25+s -T2 -At o--tlsrec 1+s",
            "-o9 -o13+s -T3 -At o--tlsrec 2+s",
            "-o1 -o2 -o25+s -T3 -At o--tlsrec 1+s",
        ]
        combos.extend(known_working)

        # Успешные из истории (без повторов)
        for t in self.history["tests"]:
            p = t.get("params")
            if t.get("success") and p and p not in combos:
                combos.append(p)

        # Новые из генератора
        if _GENERATOR_AVAILABLE and AdvancedParamGenerator is not None:
            try:
                gen = AdvancedParamGenerator()
                generated = gen.generate_comprehensive_params(max_tests * 2)
                for p in generated:
                    if p.strip() and p not in combos:
                        combos.append(p)
            except Exception as e:
                print(f"⚠️ Генератор недоступен: {e}")

        return combos[:max_tests]

    # ---------------- Тестирование ----------------

    def test_connection(self, test_urls, timeout=8):
        """Проверка доступности URLs через тестовый прокси.
        Возвращает (ok_count, total, avg_speed, details)."""
        ok_count = 0
        speeds = []
        details = []
        env_proxy_url = f"http://127.0.0.1:{self.test_port}"

        for url in test_urls:
            start = time.time()
            try:
                r = subprocess.run(
                    ['curl', '-s', '-o', '/dev/null', '-w', '%{http_code}',
                     '-x', env_proxy_url,
                     '--connect-timeout', str(min(timeout, 5)),
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
                'success': ok > 0,
                'speed': speed,
                'urls_ok': ok,
                'urls_total': total,
                'details': details
            })
            if ok == 0:
                # Пробуем понять причину через stderr
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
                            progress_callback=None, port=None):
        """Перебор комбинаций.

        progress_callback(stage, data) вызывается из фонового потока:
          stage='start'   data={'total': N}
          stage='test'    data={'index': i, 'params': ..., 'result': {...}}
          stage='done'    data={'best': ...|None}

        Возвращает (best_params|None, best_result|None).
        """
        if self.is_searching:
            return None, None

        self.is_searching = True
        self.stop_requested = False
        if port:
            self.test_port = port

        if test_urls is None:
            test_urls = list(self.default_test_urls)

        combos = self.generate_combinations(max_tests)
        best_params, best_result = None, None

        if progress_callback:
            progress_callback('start', {'total': len(combos), 'port': self.test_port})
        self.logger.info(f"Начат поиск: {len(combos)} комбинаций, порт {self.test_port}")

        for i, params in enumerate(combos):
            if self.stop_requested:
                self.logger.info("Поиск прерван пользователем")
                break

            res = self.test_params(params, test_urls)
            self.add_to_history(res)
            self.logger.info(
                f"[{i+1}/{len(combos)}] {'OK' if res['success'] else 'FAIL'} "
                f"{res['speed']:.2f}s {params} {res.get('error','')}"
            )

            if progress_callback:
                progress_callback('test', {'index': i, 'params': params, 'result': res})

            if res['success'] and (best_result is None or res['speed'] < best_result['speed']):
                best_params, best_result = params, res

        self.is_searching = False

        if progress_callback:
            progress_callback('done', {'best': best_params, 'result': best_result})

        if best_params:
            self.logger.info(f"Лучший результат: {best_params} ({best_result['speed']:.2f}s)")
        else:
            self.logger.warning("Рабочие параметры не найдены")

        return best_params, best_result


# ---------------- CLI ----------------

if __name__ == '__main__':
    import argparse
    parser = argparse.ArgumentParser(description='Поиск оптимальных параметров ciadpi')
    parser.add_argument('--max-tests', type=int, default=20)
    parser.add_argument('--port', type=int, default=1081)
    parser.add_argument('--url', action='append', help='Доп. URL для проверки (можно несколько)')
    args = parser.parse_args()

    s = StrategySearcher(test_port=args.port)
    urls = list(s.default_test_urls)
    if args.url:
        urls = args.url + urls

    def cb(stage, data):
        if stage == 'start':
            print(f"▶️ Всего комбинаций: {data['total']} (тестовый порт {data['port']})")
        elif stage == 'test':
            r = data['result']
            status = f"✅ {r['urls_ok']}/{r['urls_total']} за {r['speed']:.2f}s" if r['success'] \
                else f"❌ {r.get('error', '')[:60]}"
            print(f"[{data['index']+1}] {status} | {data['params']}")
        elif stage == 'done':
            if data['best']:
                print(f"\n🏆 Лучшие параметры: {data['best']}")
            else:
                print("\n😕 Рабочие параметры не найдены")

    best, res = s.find_optimal_params(args.max_tests, urls, cb)

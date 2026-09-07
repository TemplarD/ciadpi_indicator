#!/usr/bin/env python3

import subprocess
import time
import json
import threading
import logging
from datetime import datetime
from pathlib import Path

try:
    from ciadpi_whitelist import WhitelistManager
    WHITELIST_AVAILABLE = True
except ImportError:
    WHITELIST_AVAILABLE = False
    WhitelistManager = None

class CIAutoSearch:
    def __init__(self):
        self.history_file = Path.home() / '.config' / 'ciadpi' / 'history' / 'test_history.json'
        self.ciadpi_path = Path.home() / 'byedpi' / 'ciadpi'
        self.test_urls = [
            "https://www.youtube.com",
            "https://www.google.com/generate_204",
            "https://github.com",
            "https://www.wikipedia.org"
        ]
        self.current_test_url = 0
        self.is_searching = False
        self.current_process = None
        # Тестовый порт для локального инстанса (не конфликтует со службой)
        self.test_port = 1081
        self.whitelist_manager = WhitelistManager() if WHITELIST_AVAILABLE else None
        
        # Настройка логирования
        try:
            self.config_dir = Path.home() / '.config' / 'ciadpi'
            self.config_dir.mkdir(exist_ok=True)
        except Exception:
            self.config_dir = Path.home()
        logging.basicConfig(
            level=logging.INFO,
            format='%(asctime)s - %(levelname)s - %(message)s',
            handlers=[
                logging.FileHandler(Path.home() / '.config' / 'ciadpi' / 'autosearch.log'),
                logging.StreamHandler()
            ]
        )
        self.logger = logging.getLogger('ciadpi_autosearch')
        
        self.history = self.load_history()

    def load_history(self):
        """Загрузка истории тестирования"""
        default_history = {"tests": [], "last_tested": None}
        
        try:
            self.history_file.parent.mkdir(exist_ok=True)
            if self.history_file.exists():
                with open(self.history_file, 'r', encoding='utf-8') as f:
                    return json.load(f)
        except Exception as e:
            self.logger.error(f"Ошибка загрузки истории: {e}")
            
        return default_history

    def save_history(self):
        """Сохранение истории"""
        try:
            with open(self.history_file, 'w', encoding='utf-8') as f:
                json.dump(self.history, f, indent=2, ensure_ascii=False)
        except Exception as e:
            self.logger.error(f"Ошибка сохранения истории: {e}")

    def add_to_history(self, params, success=False, speed=0, notes=""):
        """Добавление теста в историю"""
        test_entry = {
            "params": params,
            "timestamp": datetime.now().isoformat(),
            "success": success,
            "speed": speed,
            "notes": notes
        }
        
        # Добавляем в начало списка
        self.history["tests"].insert(0, test_entry)
        
        # Сохраняем только последние 100 тестов
        if len(self.history["tests"]) > 100:
            self.history["tests"] = self.history["tests"][:100]
            
        self.history["last_tested"] = datetime.now().isoformat()
        self.save_history()

    def test_connection(self, timeout=10):
        """Тестирование соединения через локальный SOCKS5-прокси ciadpi.

        ciadpi — SOCKS-прокси, поэтому curl -x socks5h:// (не http://!).
        Возвращает (success, speed, test_url).
        """
        test_url = "https://www.google.com/generate_204"
        try:
            # Пропускаем тестирование если URL в белом списке
            if self.whitelist_manager is not None and \
                    self.whitelist_manager.is_whitelisted(test_url):
                return True, 0.1, test_url

            start_time = time.time()
            result = subprocess.run([
                'curl', '-s', '-o', '/dev/null', '-w', '%{http_code}',
                '-x', f'socks5h://127.0.0.1:{self.test_port}',
                '--connect-timeout', '5', '--max-time', '8',
                '--retry', '2', '--retry-delay', '1',
                test_url
            ], capture_output=True, text=True, timeout=timeout)

            speed = time.time() - start_time
            success = result.returncode == 0 and result.stdout.strip() in ['200', '204', '301', '302']

            return success, speed, test_url

        except subprocess.TimeoutExpired:
            return False, timeout, test_url
        except Exception as e:
            self.logger.error(f"Ошибка тестирования: {e}")
            return False, timeout, test_url

    def test_params(self, params, test_duration=15, progress_callback=None):
        """Тестирование конкретных параметров с выводом информации.

        Запускает ciadpi на тестовом порту 127.0.0.1:1081 и проверяет
        доступность контрольного URL через него (SOCKS5). Системный
        сервис и VPN не затрагиваются.
        """
        if self.is_searching:
            self.logger.warning("Поиск уже выполняется")
            return False, test_duration, "Пропуск (уже выполняется)"

        self.logger.info(f"Тестирование параметров: {params}")

        if progress_callback:
            progress_callback(-1, 0, f"Запуск: {params}")

        try:
            # Запускаем ciadpi с параметрами на тестовом порту
            cmd = [str(self.ciadpi_path)] + params.split() + \
                  ['-i', '127.0.0.1', '-p', str(self.test_port)]
            self.current_process = subprocess.Popen(
                cmd,
                stdout=subprocess.DEVNULL,
                stderr=subprocess.PIPE
            )

            # Даем время на запуск
            time.sleep(3)

            # Если процесс умер сразу — параметры невалидны для этой версии
            if self.current_process.poll() is not None:
                err = ''
                try:
                    if self.current_process.stderr:
                        err = self.current_process.stderr.read().decode(errors='replace').strip()
                except Exception:
                    pass
                notes = f"ciadpi завершился сразу (код {self.current_process.returncode}): {err[:200]}"
                self.logger.warning(notes)
                self.add_to_history(params, False, test_duration, notes)
                if progress_callback:
                    progress_callback(0, 0, notes)
                self.current_process = None
                return False, test_duration, notes

            # Тестируем соединение через тестовый прокси
            success, speed, test_url = self.test_connection(test_duration - 3)

            # Останавливаем процесс
            self.stop_test()

            # Добавляем в историю
            status = "Успешно" if success else "Неудача"
            message = f"{status}: {params}\nТест: {test_url}\nСкорость: {speed:.2f} сек"

            notes = f"{status}, тест: {test_url}, скорость: {speed:.2f} сек"
            self.add_to_history(params, success, speed, notes)

            if progress_callback:
                progress_callback(0, 0, message)

            return success, speed, message

        except Exception as e:
            error_msg = f"Ошибка: {params}\nПричина: {str(e)}"
            self.logger.error(f"Ошибка тестирования параметров {params}: {e}")
            self.add_to_history(params, False, test_duration, f"Ошибка: {str(e)}")
            self.stop_test()

            if progress_callback:
                progress_callback(0, 0, error_msg)

            return False, test_duration, error_msg

    def stop_test(self):
        """Остановка текущего теста"""
        if self.current_process:
            try:
                self.current_process.terminate()
                self.current_process.wait(timeout=5)
            except:
                try:
                    self.current_process.kill()
                except:
                    pass
            finally:
                self.current_process = None

    def stop_search(self):
        """Остановка поиска"""
        self.is_searching = False
        self.stop_test()

    def generate_param_combinations(self):
        """Генерация различных комбинаций параметров"""
        try:           
            from ciadpi_param_generator import AdvancedParamGenerator
            generator = AdvancedParamGenerator()

             # Генерируем новые комбинации
            new_combinations = generator.generate_comprehensive_params(1000)
            
            # Добавляем из истории
            history_combinations = []
            for item in self.history["tests"][:50]:
                if item["params"] not in new_combinations:
                    history_combinations.append(item["params"])
            
            return new_combinations + history_combinations[:20]

        except ImportError:
            # Fallback: базовые комбинации (проверены на текущем byedpi)
            base_combinations = [
                "-T3 -A torst -o1 -o25+s -r 1+s",
                "-T2 -A torst -o2 -o15+s -r 2+s",
                "-T1 -A torst -o1 -o5+s",
                "-T3 -A torst -o3 -o20+s -r 2+s",
                "-T2 -A torst -o1 -o10+s",
                "-T3 -A torst -o4 -o25+s -r 1+s",
                "-T1 -A torst -o2 -o8+s",
                "-T3 -A torst -o1 -o15+s -r 1+s",
                "-T2 -A torst -o3 -o12+s",
                "-T3 -A torst -o1 -o20+s -r 2+s"
            ]
            return base_combinations

    def find_optimal_params(self, max_tests=5, test_duration=15, progress_callback=None):
        """Поиск оптимальных параметров"""
        if self.is_searching:
            self.logger.warning("Поиск уже выполняется")
            return None, None
            
        self.is_searching = True
        self.logger.info(f"Начинаем поиск оптимальных параметров (макс. тестов: {max_tests})")
        
        combinations = self.generate_param_combinations()
        best_params = None
        best_speed = float('inf')
        successful_params = []
        
        for i, params in enumerate(combinations[:max_tests]):
            if not self.is_searching:
                self.logger.info("Поиск прерван пользователем")
                break
                
            if progress_callback:
                progress_callback(i+1, max_tests, params)
            
            self.logger.info(f"Тест {i+1}/{min(max_tests, len(combinations))}: {params}")
            
            success, speed, _ = self.test_params(params, test_duration,
                                                 progress_callback=None)
            
            if success:
                successful_params.append((params, speed))
                if speed < best_speed:
                    best_speed = speed
                    best_params = params
                
                self.logger.info(f"Успех! Скорость: {speed:.2f} сек")
            else:
                self.logger.info("Неудача")
            
            # Небольшая пауза между тестами
            time.sleep(2)
        
        self.is_searching = False
        
        if best_params:
            self.logger.info(f"Лучшие параметры: {best_params} (скорость: {best_speed:.2f} сек)")
            return best_params, best_speed
        else:
            self.logger.warning("Не найдено рабочих параметров")
            return None, None

    def get_history(self, limit=50):
        """Получение истории тестирования"""
        return self.history["tests"][:limit]

    def clear_history(self):
        """Очистка истории"""
        self.history = {"tests": [], "last_tested": None}
        self.save_history()

# Тестирование модуля
if __name__ == "__main__":
    searcher = CIAutoSearch()
    print("Модуль автопоиска загружен успешно")
    print(f"История содержит {len(searcher.get_history())} записей")

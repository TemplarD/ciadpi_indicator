#!/usr/bin/env python3

import subprocess
import time
import json
import threading
import logging
from datetime import datetime
from pathlib import Path

class CIAutoSearch:
    def __init__(self):
        self.history_file = Path.home() / '.config' / 'ciadpi' / 'history' / 'test_history.json'
        self.ciadpi_path = Path.home() / 'byedpi' / 'ciadpi'
        self.test_urls = [
            "https://www.youtube.com",
            "https://www.google.com",
            "https://github.com",
            "https://www.wikipedia.org"
        ]
        self.current_test_url = 0
        self.is_searching = False
        self.current_process = None
        
        # Настройка логирования
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
        """Тестирование соединения с YouTube"""
        try:
            test_url = self.test_urls[self.current_test_url]
            self.current_test_url = (self.current_test_url + 1) % len(self.test_urls)

            start_time = time.time()
            result = subprocess.run([
                'curl', '-s', '-o', '/dev/null', '-w', '%{http_code}',
                '--connect-timeout', '5', '--max-time', '8',
                '--retry', '2', '--retry-delay', '1',
                self.test_url
            ], capture_output=True, text=True, timeout=timeout)
            
            speed = time.time() - start_time
            success = result.returncode == 0 and result.stdout.strip() in ['200', '206', '301', '302']
            
            return success, speed, test_url
            
        except subprocess.TimeoutExpired:
            return False, timeout
        except Exception as e:
            self.logger.error(f"Ошибка тестирования: {e}")
            return False, timeout, test_url

    def test_params(self, params, test_duration=15):
        """Тестирование конкретных параметров с выводом информации"""
        if self.is_searching:
            self.logger.warning("Поиск уже выполняется")
            return False, test_duration, "Пропуск (уже выполняется)"
            
        self.logger.info(f"Тестирование параметров: {params}")

        if progress_callback:
            progress_callback(-1,0, f"Запуск: {params}")
        
        try:
            # Запускаем ciadpi с параметрами
            self.current_process = subprocess.Popen(
                [str(self.ciadpi_path)] + params.split(),
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE
            )
            
            # Даем время на запуск
            time.sleep(3)
            
            # Тестируем соединение
            success, speed = self.test_connection(test_duration - 3)
            
            # Останавливаем процесс
            self.stop_test()
            
            # Добавляем в историю
            status = "Успешно" if success else "Неудача"
            message = f"{status}: {params}\nТест: {test_url}\nСкорость: {speed:.2f} сек"

            # Добавляем в историю
            notes = f"{status}, тест: {test_url}\n, скорость: {speed:.2f} сек"
            self.add_to_history(params, success, speed, notes)
            
            if progress_callback:
                progress_callback(0, 0, message)

            return success, speed, message
            
        except Exception as e:
            error_msg = f"Ошибка: {params}\nПричина: {str(e)}"
            self.logger.error(f"Ошибка тестирования параметров {params}: {e}")
            self.add_to_history(params, False, test_duration, f"Ошибка: {str(e)}")

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
            # Fallback to basic combinations
            base_combinations = [
                "-o1 -o25+s -T3 -At o--tlsrec 1+s",
                "-o2 -o15+s -T2 -At o--tlsrec",
                "-o1 -o5+s -T1 -At",
                "-o3 -o20+s -T3 -At o--tlsrec 2+s",
                "-o1 -o10+s -T2 -At",
                "-o4 -o25+s -T3 -At o--tlsrec",
                "-o2 -o8+s -T1 -At",
                "-o1 -o15+s -T3 -At o--tlsrec 1+s",
                "-o3 -o12+s -T2 -At",
                "-o1 -o20+s -T3 -At o--tlsrec"
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
            
            success, speed = self.test_params(params, test_duration)
            
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

#!/usr/bin/env python3

import random
import re
from typing import List, Dict, Tuple
from pathlib import Path

class AdvancedParamGenerator:
    def __init__(self):
        # Все параметры из документации
        self.all_params = {
            # Основные параметры
            'ip': ['-i 0.0.0.0', '-i 127.0.0.1', ''],
            'port': ['-p 1080', '-p 8080', '-p 9050', ''],
            'daemon': ['-D', ''],
            'pidfile': ['-w /var/run/ciadpi.pid', ''],
            'transparent': ['-E', ''],
            'max_conn': ['-c 512', '-c 1024', '-c 2048', ''],
            'conn_ip': ['-I ::', '-I 0.0.0.0', ''],
            'buf_size': ['-b 16384', '-b 32768', '-b 65536', ''],
            'def_ttl': ['-g 64', '-g 128', '-g 255', ''],
            'no_domain': ['-N', ''],
            'no_udp': ['-U', ''],
            'tfo': ['-F', ''],
            
            # Автоматический режим
            # -L: текущий byedpi принимает буквы s,o,n (не 0..3!)
            'auto': ['-A torst', '-A redirect', '-A ssl_err', '-A none', ''],
            'auto_mode': ['-L s', '-L o', '-L n', '-L s,o', ''],
            'cache_ttl': ['-u 100800', '-u 86400', ''],
            'cache_dump': ['-y -', ''],
            
            # Таймауты и протоколы
            'timeout': ['-T 1', '-T 2', '-T 3', '-T 5', '-T 10'],
            'proto': ['-K t', '-K h', '-K u', '-K i', '-K t,h', '-K t,u', '-K h,i', ''],
            
            # Ограничители
            'hosts': ['', '-H :youtube.com google.com'],
            'ipset': ['', '-j :127.0.0.1'],
            'port_filter': ['', '-V 80-443'],
            'round': ['-R 1', '-R 2', '-R 1-3', ''],
            
            # Методы обхода
            'split': self.generate_split_params(),
            'disorder': self.generate_disorder_params(),
            'oob': self.generate_oob_params(),
            'disoob': self.generate_disoob_params(),
            'fake': self.generate_fake_params(),
            
            # TLS/HTTP модификации
            'ttl': ['-t 8', '-t 16', '-t 32', ''],
            'md5sig': ['-S', ''],
            'fake_offset': ['-O 0+sm', '-O 1+hm', ''],
            'fake_data': ['', '-l :test'],
            'oob_data': ['-e a', '-e b', '-e \\x00', ''],
            'fake_sni': ['', '-n fake.example.com', '-n test?.example.com'],
            'fake_tls_mod': ['-Q r', '-Q o', ''],
            'mod_http': ['-M h', '-M d', '-M r', '-M h,d', '-M h,r', '-M d,r', '-M h,d,r'],
            'tlsrec': self.generate_tlsrec_params(),
            'udp_fake': ['-a 1', '-a 2', '-a 3', ''],
            'drop_sack': ['-Y', '']
        }
        
        # Базовые методы обхода (основной фокус)
        self.obfuscation_methods = [
            '-o1', '-o2', '-o3', '-o4', '-o5', '-o6', '-o7', '-o8', '-o9', '-o10',
            '-o11', '-o12', '-o13', '-o14', '-o15', '-o16', '-o17', '-o18', '-o19',
            '-o20', '-o21', '-o22', '-o23', '-o24', '-o25'
        ]
        
        # Суффиксы для методов (первый флаг после + обязан быть s/h/n;
        # m, e, r — только вторым: +sm, +se, +hr ...)
        self.method_suffixes = ['', '+s', '+h', '+n', '+sm', '+hm', '+se']

        # Известные рабочие комбинации (проверены на текущем бинарнике byedpi)
        self.known_working = [
            "-T3 -A torst -o1 -o25+s -r 1+s",
            "-T2 -A torst -o2 -o15+s -r 2+s",
            "-T1 -A torst -o1 -o5+s",
            "-T3 -A torst -o3 -o20+s -r 2+s",
            "-T3 -A torst -o4 -o25+s -r 1+s"
        ]

    def generate_split_params(self) -> List[str]:
        """Генерация параметров split"""
        params = []
        for offset in range(0, 10):
            for flag in ['+s', '+h', '+n', '+sm', '+hm', '+em', '+se']:
                params.append(f"-s {offset}{flag}")
        return params + ['']

    def generate_disorder_params(self) -> List[str]:
        """Генерация параметров disorder"""
        params = []
        for offset in range(0, 5):
            for flag in ['+s', '+h', '+n', '+sm', '+hm']:
                params.append(f"-d {offset}{flag}")
        return params + ['']

    def generate_oob_params(self) -> List[str]:
        """Генерация параметров oob"""
        return [f"-o {i}+s" for i in range(0, 5)] + ['']

    def generate_disoob_params(self) -> List[str]:
        """Генерация параметров disoob"""
        return [f"-q {i}+h" for i in range(0, 5)] + ['']

    def generate_fake_params(self) -> List[str]:
        """Генерация параметров fake"""
        return [f"-f {i}+s" for i in range(0, 5)] + ['']

    def generate_tlsrec_params(self) -> List[str]:
        """Генерация параметров tlsrec"""
        return [f"-r {i}" for i in range(0, 10)] + ['']

    def generate_comprehensive_params(self, count: int = 15) -> List[str]:
        """Генерация комплексных параметров"""
        combinations = []
        
        # Добавляем известные рабочие комбинации
        combinations.extend(self.known_working)
        
        # Базовые комбинации с методами обхода
        for _ in range(count // 2):
            # Выбираем 2-3 метода обхода
            methods = random.sample(self.obfuscation_methods, random.randint(2, 3))
            methods = [m + random.choice(self.method_suffixes) for m in methods]
            
            # Базовые параметры
            base_params = [
                random.choice(self.all_params['timeout']),
                random.choice(['-At', '']),
                random.choice(self.all_params['tlsrec'])
            ]
            
            # Дополнительные параметры (1-2 случайных)
            additional_params = random.sample([
                random.choice(self.all_params['split']),
                random.choice(self.all_params['disorder']),
                random.choice(self.all_params['fake']),
                random.choice(self.all_params['mod_http']),
                random.choice(['1+s', '2+s', '3+s'])
            ], random.randint(1, 2))
            
            combo = ' '.join(methods + base_params + additional_params)
            combinations.append(combo)
        
        # Комплексные комбинации со всеми параметрами
        for _ in range(count // 3):
            combo_parts = []
            
            # Основные параметры
            combo_parts.extend(random.sample(self.obfuscation_methods, 2))
            combo_parts.append(random.choice(self.all_params['timeout']))
            
            # Сетевые параметры (0-2)
            network_params = random.sample([
                random.choice(self.all_params['max_conn']),
                random.choice(self.all_params['def_ttl']),
                random.choice(self.all_params['tfo'])
            ], random.randint(0, 2))
            combo_parts.extend(network_params)
            
            # Параметры обхода (1-3)
            obfuscation_params = random.sample([
                random.choice(self.all_params['split']),
                random.choice(self.all_params['disorder']),
                random.choice(self.all_params['fake']),
                random.choice(self.all_params['tlsrec'])
            ], random.randint(1, 3))
            combo_parts.extend(obfuscation_params)
            
            # Автоматический режим (50% chance)
            if random.random() > 0.5:
                combo_parts.append(random.choice(self.all_params['auto']))
                combo_parts.append(random.choice(self.all_params['auto_mode']))
            
            combo = ' '.join([p for p in combo_parts if p])
            combinations.append(combo)
        
        # Уникальные комбинации
        unique_combinations = list(set(combinations))
        return unique_combinations[:count]

    def validate_params(self, params: str) -> Tuple[bool, str]:
        """Валидация параметров с детальным выводом ошибок"""
        if not params.strip():
            return True, ""
            
        parts = params.split()
        unknown_params = []
        invalid_values = []
        
        # Все допустимые параметры
        valid_params = set()
        for param_list in self.all_params.values():
            for param in param_list:
                if param:  # Игнорируем пустые строки
                    # Извлекаем имя параметра (первое слово)
                    param_name = param.split()[0] if ' ' in param else param
                    valid_params.add(param_name)
        
        # Добавляем методы обхода
        for method in self.obfuscation_methods:
            valid_params.add(method)
            for suffix in self.method_suffixes:
                if suffix:  # Игнорируем пустой суффикс
                    valid_params.add(method + suffix)
        
        # Добавляем специальные параметры
        valid_params.update(['-At', '1+s', '2+s', '3+s', 'o--tlsrec'])
        
        i = 0
        while i < len(parts):
            part = parts[i]
            
            # Проверяем, является ли часть допустимым параметром
            if part not in valid_params:
                # Проверяем, не является ли это значением предыдущего параметра
                if i > 0 and parts[i-1] in ['-H', '-j', '-l', '-n']:
                    # Эти параметры принимают произвольные значения
                    i += 1
                    continue
                
                # Проверяем специальные форматы
                if (part.startswith('o--tlsrec') or 
                    part in ['1+s', '2+s', '3+s'] or
                    re.match(r'^-o\d+[\+sme]*$', part) or
                    re.match(r'^-\w+ \S+', ' '.join(parts[max(0,i-1):i+1]))):
                    i += 1
                    continue
                
                unknown_params.append(part)
            
            i += 1
        
        if unknown_params:
            error_msg = f"Неизвестные параметры: {', '.join(unknown_params)}\n"
            error_msg += f"Допустимые параметры: {', '.join(sorted(valid_params))}"
            return False, error_msg
        
        return True, ""

    def get_usage_examples(self) -> List[str]:
        """Получить примеры использования для UI (проверены на byedpi)"""
        return [
            "-T3 -A torst -o1 -o25+s -r 1+s",
            "-T2 -A torst -o2 -o15+s -r 2+s",
            "-T1 -A torst -o1 -o5+s",
            "-T3 -A torst -o3 -o20+s -r 2+s",
            "-T5 -A torst -o4 -o10+s",
            "-T2 -A torst -o7 -o18+s -s 5+sm -d 2+h",
            "-T3 -A torst -o1 -o12+s -f 3+s -r 5"
        ]

    def mutate_params(self, base_params: str, intensity: float = 0.3) -> str:
        """Мутация существующих параметров"""
        parts = base_params.split()
        if not parts:
            return base_params
        
        num_mutations = max(1, int(len(parts) * intensity))
        
        for _ in range(num_mutations):
            mutation_type = random.choice(['replace', 'add', 'remove', 'modify'])
            
            if mutation_type == 'replace' and parts:
                idx = random.randint(0, len(parts) - 1)
                if parts[idx].startswith('-o'):
                    parts[idx] = random.choice(self.obfuscation_methods) + random.choice(self.method_suffixes)
                elif parts[idx].startswith('-T'):
                    parts[idx] = random.choice(self.all_params['timeout'])
                elif parts[idx].startswith('-'):
                    # Заменяем любой другой параметр
                    param_type = parts[idx].split()[0] if ' ' in parts[idx] else parts[idx]
                    for key, values in self.all_params.items():
                        if any(param_type in v for v in values):
                            parts[idx] = random.choice(values)
                            break
            
            elif mutation_type == 'add' and len(parts) < 12:
                new_param = random.choice([
                    random.choice(self.obfuscation_methods) + random.choice(self.method_suffixes),
                    random.choice(self.all_params['timeout']),
                    random.choice(self.all_params['split']),
                    random.choice(self.all_params['disorder']),
                    random.choice(['1+s', '2+s', '3+s'])
                ])
                parts.append(new_param)
            
            elif mutation_type == 'remove' and len(parts) > 3:
                idx = random.randint(2, len(parts) - 1)
                parts.pop(idx)
            
            elif mutation_type == 'modify' and parts:
                idx = random.randint(0, len(parts) - 1)
                if '+' in parts[idx]:
                    # Модифицируем суффикс
                    base = parts[idx].split('+')[0]
                    new_suffix = random.choice(self.method_suffixes)
                    parts[idx] = base + new_suffix if new_suffix else base
        
        return ' '.join([p for p in parts if p])

    def generate_from_history(self, history: List[Dict], count: int = 10) -> List[str]:
        """Генерация на основе истории тестирования"""
        new_combinations = []
        
        # Берем успешные параметры из истории
        successful = [item for item in history if item.get('success')]
        unsuccessful = [item for item in history if not item.get('success')]
        
        # Мутируем успешные параметры
        for item in successful[:5]:
            for _ in range(2):
                mutated = self.mutate_params(item['params'])
                if mutated not in new_combinations:
                    new_combinations.append(mutated)
        
        # Пытаемся улучшить неуспешные параметры
        for item in unsuccessful[:3]:
            improved = self.mutate_params(item['params'], intensity=0.5)
            if improved not in new_combinations:
                new_combinations.append(improved)
        
        # Добавляем новые случайные комбинации
        while len(new_combinations) < count:
            new_combo = self.generate_comprehensive_params(1)[0]
            if new_combo not in new_combinations:
                new_combinations.append(new_combo)
        
        return new_combinations[:count]

    def get_param_categories(self) -> Dict[str, List[str]]:
        """Получение параметров по категориям"""
        return {
            'Основные': ['-i', '-p', '-D', '-w', '-E', '-c', '-I', '-b', '-g'],
            'Фильтрация': ['-N', '-U', '-F', '-K', '-H', '-j', '-V', '-R'],
            'Автоматизация': ['-A', '-L', '-u', '-y', '-T'],
            'Методы обхода': ['-s', '-d', '-o', '-q', '-f', '-r'],
            'Модификации': ['-t', '-S', '-O', '-l', '-e', '-n', '-Q', '-M', '-a', '-Y']
        }

# Тестирование генератора
if __name__ == "__main__":
    generator = AdvancedParamGenerator()
    
    print("📊 Сгенерированные комплексные параметры:")
    params = generator.generate_comprehensive_params(10)
    for i, param in enumerate(params, 1):
        print(f"{i:2d}. {param}")
    
    print("\n🔄 Мутированные параметры:")
    base = "-o1 -o25+s -T3 -At o--tlsrec 1+s"
    for i in range(3):
        mutated = generator.mutate_params(base)
        print(f"{i+1}. {mutated}")
    
    print(f"\n📋 Всего доступно параметров: {sum(len(v) for v in generator.all_params.values())}")
    
    print("\n✅ Примеры использования (для UI):")
    examples = generator.get_usage_examples()
    for i, example in enumerate(examples, 1):
        print(f"{i}. {example}")
    
    print("\n🔍 Тест валидации:")
    test_params = ["-o1 -o25+s -T3", "-invalid -o1", "-o1 -unknown_param"]
    for params in test_params:
        is_valid, message = generator.validate_params(params)
        print(f"Параметры: {params}")
        print(f"Результат: {'✅ Valid' if is_valid else '❌ Invalid'}")
        if not is_valid:
            print(f"Ошибка: {message}")
        print()
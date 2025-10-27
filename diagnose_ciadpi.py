#!/usr/bin/env python3

import subprocess
import os
from pathlib import Path

def diagnose_ciadpi():
    print("🔍 Диагностика CIADPI...")
    
    # Проверяем сервис
    print("\n1. Проверка сервиса:")
    try:
        result = subprocess.run(['systemctl', 'status', 'ciadpi.service'], 
                              capture_output=True, text=True)
        print(result.stdout)
    except Exception as e:
        print(f"Ошибка: {e}")
    
    # Проверяем параметры
    print("\n2. Текущие параметры:")
    try:
        result = subprocess.run([
            'systemctl', 'show', 'ciadpi.service', '--property=ExecStart', '--no-pager'
        ], capture_output=True, text=True)
        print(result.stdout)
    except Exception as e:
        print(f"Ошибка: {e}")
    
    # Проверяем файлы конфигурации
    print("\n3. Файлы конфигурации:")
    config_dir = Path.home() / '.config' / 'ciadpi'
    if config_dir.exists():
        for file in config_dir.glob('*'):
            print(f"   {file.name}: {'существует' if file.exists() else 'отсутствует'}")
    
    # Проверяем белый список
    print("\n4. Белый список:")
    whitelist_file = config_dir / 'whitelist.json'
    if whitelist_file.exists():
        import json
        with open(whitelist_file, 'r') as f:
            whitelist = json.load(f)
        print(f"   Включен: {whitelist.get('enabled', False)}")
        print(f"   Домены: {len(whitelist.get('domains', []))}")
        print(f"   IP: {len(whitelist.get('ips', []))}")
    else:
        print("   Файл белого списка не найден")

if __name__ == "__main__":
    diagnose_ciadpi()
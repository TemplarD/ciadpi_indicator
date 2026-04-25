#!/usr/bin/env python3

import subprocess
import os
import json
from pathlib import Path

def run_command(cmd):
    """Выполнить команду и вернуть результат"""
    try:
        result = subprocess.run(cmd, shell=True, capture_output=True, text=True)
        return result.returncode, result.stdout, result.stderr
    except Exception as e:
        return -1, "", str(e)

def diagnose_ciadpi():
    print("🔍 Детальная диагностика CIADPI...")
    
    # 1. Проверяем сервис
    print("\n" + "="*50)
    print("1. СТАТУС СЕРВИСА:")
    print("="*50)
    
    ret, out, err = run_command("systemctl status ciadpi.service")
    print(out)
    if err:
        print("STDERR:", err)
    
    # 2. Проверяем параметры сервиса
    print("\n" + "="*50)
    print("2. ПАРАМЕТРЫ СЕРВИСА:")
    print("="*50)
    
    ret, out, err = run_command("systemctl show ciadpi.service --property=ExecStart --no-pager")
    print("ExecStart:", out)
    
    # 3. Проверяем override директорию
    print("\n" + "="*50)
    print("3. OVERRIDE КОНФИГ:")
    print("="*50)
    
    override_file = "/etc/systemd/system/ciadpi.service.d/override.conf"
    if os.path.exists(override_file):
        ret, out, err = run_command(f"sudo cat {override_file}")
        print("Содержимое override.conf:")
        print(out)
    else:
        print("❌ override.conf не существует!")
    
    # 4. Проверяем файлы конфигурации
    print("\n" + "="*50)
    print("4. ФАЙЛЫ КОНФИГУРАЦИИ:")
    print("="*50)
    
    config_dir = Path.home() / '.config' / 'ciadpi'
    print(f"Директория конфига: {config_dir}")
    
    if config_dir.exists():
        for file in config_dir.glob('*'):
            if file.is_file():
                print(f"\n📄 {file.name}:")
                try:
                    if file.suffix == '.json':
                        with open(file, 'r') as f:
                            content = json.load(f)
                        print(f"   {json.dumps(content, indent=2, ensure_ascii=False)}")
                    else:
                        with open(file, 'r') as f:
                            content = f.read().strip()
                        if content:
                            print(f"   {content}")
                        else:
                            print("   (пустой)")
                except Exception as e:
                    print(f"   Ошибка чтения: {e}")
    else:
        print("❌ Директория конфига не существует!")
    
    # 5. Проверяем бинарник ciadpi
    print("\n" + "="*50)
    print("5. БИНАРНИК CIADPI:")
    print("="*50)
    
    ciadpi_path = Path.home() / 'byedpi' / 'ciadpi'
    print(f"Путь: {ciadpi_path}")
    print(f"Существует: {ciadpi_path.exists()}")
    print(f"Исполняемый: {os.access(ciadpi_path, os.X_OK)}")
    
    if ciadpi_path.exists():
        ret, out, err = run_command(f"file {ciadpi_path}")
        print(f"Тип файла: {out}")
    
    # 6. Проверяем Python скрипты
    print("\n" + "="*50)
    print("6. PYTHON СКРИПТЫ:")
    print("="*50)
    
    scripts_dir = Path.home() / '.local' / 'bin'
    scripts = ['ciadpi_advanced_tray.py', 'ciadpi_whitelist.py', 'ciadpi_autosearch.py']
    
    for script in scripts:
        script_path = scripts_dir / script
        print(f"\n{script}:")
        print(f"  Существует: {script_path.exists()}")
        if script_path.exists():
            print(f"  Исполняемый: {os.access(script_path, os.X_OK)}")
            # Проверяем импорт
            if script == 'ciadpi_whitelist.py':
                ret, out, err = run_command(f"python3 -c 'import sys; sys.path.append(\"{scripts_dir}\"); from ciadpi_whitelist import WhitelistManager; print(\"✅ Импорт успешен\")'")
                print(f"  Импорт: {'✅ Успешно' if ret == 0 else '❌ Ошибка'}")
                if err:
                    print(f"  Ошибка импорта: {err}")
    
    # 7. Проверяем логи
    print("\n" + "="*50)
    print("7. ПОСЛЕДНИЕ ЛОГИ:")
    print("="*50)
    
    ret, out, err = run_command("journalctl -u ciadpi.service -n 10 --no-pager")
    print(out)

if __name__ == "__main__":
    diagnose_ciadpi()
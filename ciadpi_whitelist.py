#!/usr/bin/env python3

import json
import ipaddress
from pathlib import Path
import re

class WhitelistManager:
    def __init__(self, config_path=None):
        if config_path is None:
            config_path = Path.home() / '.config' / 'ciadpi' / 'whitelist.json'
        
        self.config_path = Path(config_path)
        self.whitelist = self.load_whitelist()
    
    def load_whitelist(self):
        """Загрузка белого списка"""
        default_whitelist = {
            "enabled": False,
            "domains": [
                "localhost",
                "127.0.0.1",
                "*.local",
                "192.168.1.1"
            ],
            "ips": [
                "192.168.1.0/24",
                "10.0.0.0/8"
            ],
            "bypass_proxy": True,
            "bypass_dpi": False,
            "description": "Белый список для исключения ресурсов из проксирования"
        }
        
        try:
            self.config_path.parent.mkdir(exist_ok=True)
            if self.config_path.exists():
                with open(self.config_path, 'r', encoding='utf-8') as f:
                    whitelist = json.load(f)
                    # Проверяем что все необходимые поля есть
                    for key in default_whitelist:
                        if key not in whitelist:
                            whitelist[key] = default_whitelist[key]
                    return whitelist
        except Exception as e:
            print(f"Ошибка загрузки белого списка: {e}")
            
        return default_whitelist
    
    def save_whitelist(self):
        """Сохранение белого списка"""
        try:
            with open(self.config_path, 'w', encoding='utf-8') as f:
                json.dump(self.whitelist, f, indent=2, ensure_ascii=False)
            return True
        except Exception as e:
            print(f"Ошибка сохранения белого списка: {e}")
            return False
    
    def is_whitelisted(self, host):
        """Проверка находится ли хост в белом списке"""
        if not self.whitelist.get("enabled", False):
            return False
        
        # Проверка доменов
        if self._is_domain_whitelisted(host):
            return True
        
        # Проверка IP-адресов
        if self._is_ip_whitelisted(host):
            return True
        
        return False
    
    def _is_domain_whitelisted(self, host):
        """Проверка домена в белом списке"""
        domains = self.whitelist.get("domains", [])
        
        # Точное совпадение
        if host in domains:
            return True
        
        # Проверка по маске
        for domain_pattern in domains:
            if domain_pattern.startswith('*.'):
                pattern = domain_pattern[2:]
                if host.endswith('.' + pattern) or host == pattern:
                    return True
        
        return False
    
    def _is_ip_whitelisted(self, host):
        """Проверка IP-адреса в белом списке"""
        try:
            ip = ipaddress.ip_address(host)
        except ValueError:
            return False
        
        ip_ranges = self.whitelist.get("ips", [])
        
        for range_str in ip_ranges:
            try:
                network = ipaddress.ip_network(range_str, strict=False)
                if ip in network:
                    return True
            except ValueError:
                continue
        
        return False
    
    def add_domain(self, domain):
        """Добавление домена в белый список"""
        domains = self.whitelist.get("domains", [])
        if domain not in domains:
            domains.append(domain)
            self.whitelist["domains"] = domains
            return self.save_whitelist()
        return True
    
    def remove_domain(self, domain):
        """Удаление домена из белого списка"""
        domains = self.whitelist.get("domains", [])
        if domain in domains:
            domains.remove(domain)
            self.whitelist["domains"] = domains
            return self.save_whitelist()
        return True
    
    def add_ip_range(self, ip_range):
        """Добавление IP-диапазона в белый список"""
        ips = self.whitelist.get("ips", [])
        if ip_range not in ips:
            ips.append(ip_range)
            self.whitelist["ips"] = ips
            return self.save_whitelist()
        return True
    
    def remove_ip_range(self, ip_range):
        """Удаление IP-диапазона из белого списка"""
        ips = self.whitelist.get("ips", [])
        if ip_range in ips:
            ips.remove(ip_range)
            self.whitelist["ips"] = ips
            return self.save_whitelist()
        return True
    
    def get_ignore_hosts_string(self):
        """Получение строки игнорируемых хостов для системных настроек"""
        if not self.whitelist.get("enabled", False):
            return "[]"
        
        ignore_hosts = self.whitelist.get("domains", []) + self.whitelist.get("ips", [])
        if ignore_hosts:
            return "[" + ",".join([f"'{host}'" for host in ignore_hosts]) + "]"
        return "[]"
    
    def enable(self):
        """Включение белого списка"""
        self.whitelist["enabled"] = True
        return self.save_whitelist()
    
    def disable(self):
        """Выключение белого списка"""
        self.whitelist["enabled"] = False
        return self.save_whitelist()

# Тестирование
if __name__ == "__main__":
    wm = WhitelistManager()
    
    print("Текущий белый список:")
    print(f"Включен: {wm.whitelist['enabled']}")
    print(f"Домены: {wm.whitelist['domains']}")
    print(f"IP-диапазоны: {wm.whitelist['ips']}")
    
    # Тестирование проверок
    test_hosts = ["localhost", "google.com", "192.168.1.100", "10.0.1.5"]
    print("\nТестирование проверок:")
    for host in test_hosts:
        result = wm.is_whitelisted(host)
        print(f"{host}: {'✅ В списке' if result else '❌ Не в списке'}")
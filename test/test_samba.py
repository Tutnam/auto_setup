#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Тестовый скрипт для проверки работы Samba сервера
"""

import subprocess
import sys

def run_command(command):
    """Выполняет команду и возвращает результат"""
    try:
        result = subprocess.run(
            command.split() if isinstance(command, str) else command,
            capture_output=True,
            text=True,
            timeout=10
        )
        return result
    except Exception as e:
        print(f"❌ Ошибка выполнения команды {command}: {e}")
        return None

def test_samba_services():
    """Проверяет статус служб Samba"""
    print("🔍 Проверка статуса служб Samba...")
    
    services = ["smb", "nmb"]
    all_active = True
    
    for service in services:
        result = run_command(f"systemctl is-active {service}")
        if result and result.stdout.strip() == "active":
            print(f"✅ Служба {service}: активна")
        else:
            print(f"❌ Служба {service}: неактивна")
            all_active = False
            
    return all_active

def test_samba_connection():
    """Тестирует подключение к Samba серверу"""
    print("\n🧪 Тестирование подключения к Samba...")
    
    # Получаем IP адрес (используем ip команду для совместимости с Arch Linux)
    result = run_command("ip route get 1.1.1.1")
    ip_address = None
    
    if result and result.returncode == 0:
        # Извлекаем IP адрес из вывода
        try:
            parts = result.stdout.strip().split()
            src_index = parts.index('src')
            if src_index + 1 < len(parts):
                ip_address = parts[src_index + 1]
                print(f"🌐 IP адрес сервера: {ip_address}")
        except (ValueError, IndexError):
            print("⚠️  Не удалось извлечь IP адрес из вывода ip команды")
    
    # Если не удалось получить IP, пробуем hostname -i  
    if not ip_address:
        result2 = run_command("hostname -i")
        if result2 and result2.returncode == 0:
            ip_candidates = result2.stdout.strip().split()
            # Исключаем localhost адреса
            for candidate in ip_candidates:
                if not candidate.startswith('127.'):
                    ip_address = candidate
                    print(f"🌐 IP адрес сервера (из hostname): {ip_address}")
                    break
    
    # Тестируем подключение к IP адресу если он найден
    if ip_address and not ip_address.startswith('127.'):
        print(f"Тестируем подключение к {ip_address}...")
        result = run_command(f"smbclient -L //{ip_address} -N")
        if result and result.returncode == 0:
            print("✅ Samba сервер отвечает на IP адрес!")
            print("📋 Доступные ресурсы:")
            print(result.stdout)
            return True
        else:
            print(f"⚠️  Ошибка подключения к {ip_address}")
                
    # Тестируем подключение к localhost
    print("Тестируем подключение к localhost...")
    result = run_command("smbclient -L //localhost -N")
    if result and result.returncode == 0:
        print("✅ Samba сервер отвечает на localhost!")
        print("📋 Доступные ресурсы:")
        print(result.stdout)
        return True
    else:
        print("❌ Ошибка подключения к localhost")
        if result:
            print(f"Stderr: {result.stderr}")
        return False

def test_samba_config():
    """Проверяет конфигурацию Samba"""
    print("\n⚙️  Проверка конфигурации Samba...")
    
    result = run_command("testparm -s")
    if result and result.returncode == 0:
        print("✅ Конфигурация Samba корректна")
        return True
    else:
        print("❌ Ошибка в конфигурации Samba")
        if result:
            print(f"Ошибка: {result.stderr}")
        return False

def test_firewall():
    """Проверяет настройки файрвола"""
    print("\n🔥 Проверка настроек файрвола...")
    
    result = run_command("ufw status")
    if result and result.returncode == 0:
        print("📋 Статус UFW:")
        print(result.stdout)
        
        # Проверяем Samba порты
        samba_ports = ["139/tcp", "445/tcp", "137", "138"]
        found_rules = 0
        
        for port in samba_ports:
            if port in result.stdout:
                found_rules += 1
                
        if found_rules > 0:
            print(f"✅ Найдено {found_rules} правил для Samba портов")
            return True
        else:
            print("⚠️  Не найдено правил для Samba портов")
            return False
    else:
        print("⚠️  UFW не активен или недоступен")
        return True  # Не критично

def main():
    """Основная функция тестирования"""
    print("🧪 ТЕСТИРОВАНИЕ SAMBA СЕРВЕРА")
    print("=" * 40)
    
    tests = [
        ("Статус служб", test_samba_services),
        ("Конфигурация", test_samba_config),
        ("Подключение", test_samba_connection),
        ("Файрвол", test_firewall)
    ]
    
    passed = 0
    total = len(tests)
    
    for test_name, test_func in tests:
        print(f"\n{'─' * 20}")
        try:
            if test_func():
                passed += 1
                print(f"✅ Тест '{test_name}': ПРОЙДЕН")
            else:
                print(f"❌ Тест '{test_name}': НЕ ПРОЙДЕН")
        except Exception as e:
            print(f"❌ Тест '{test_name}': ОШИБКА - {e}")
    
    print(f"\n{'=' * 40}")
    print(f"🏁 РЕЗУЛЬТАТЫ: {passed}/{total} тестов пройдено")
    
    if passed == total:
        print("🎉 Все тесты пройдены! Samba сервер работает корректно.")
        return 0
    else:
        print("⚠️  Некоторые тесты не пройдены. Проверьте настройки.")
        return 1

if __name__ == "__main__":
    sys.exit(main())

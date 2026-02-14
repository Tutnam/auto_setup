#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Главный скрипт автоматической настройки системы
Выполняет полную автоматизацию:
1. Установка необходимых пакетов (install.py)
2. Настройка Samba сервера (samba_auto_setup.py)
3. Настройка файрвола (firewall.py)

Использование: sudo python3 main.py
"""

import os
import sys
import subprocess
from pathlib import Path

# Добавляем папку code в путь для импорта модулей
sys.path.insert(0, str(Path(__file__).parent / "code"))

try:
    # Импортируем наши модули
    from install import (
        get_username, is_yay_installed,
        install_dependencies, clone_and_build_yay, 
        install_packages_with_yay, install_packages_with_pacman,
        update_packages, YAY_PACKAGES, PACMAN_PACKAGES
    )
    from samba_auto_setup import SambaAutoSetup
except ImportError as e:
    print(f"❌ Ошибка импорта модулей: {e}")
    print("Убедитесь, что файлы install.py и samba_auto_setup.py находятся в папке 'code'")
    sys.exit(1)

class AutoSetupMaster:
    """Главный класс для координации автоматической настройки системы"""
    
    def __init__(self):
        self.username = None
        
    def check_requirements(self):
        """Проверяет системные требования"""
        print("🔍 Проверка системных требований...")
        
        # Проверяем права root
        if os.geteuid() != 0:
            print("❌ Этот скрипт требует прав суперпользователя. Запустите с sudo.")
            sys.exit(1)
            
        # Получаем имя пользователя
        self.username = os.getenv("SUDO_USER")
        if not self.username:
            print("❌ Не удалось определить пользователя. Запустите скрипт через sudo.")
            sys.exit(1)
            
        print(f"✅ Пользователь: {self.username}")
        
        # Проверяем наличие необходимых файлов
        code_dir = Path(__file__).parent / "code"
        required_files = ["install.py", "samba_auto_setup.py"]
        
        for file in required_files:
            if not (code_dir / file).exists():
                print(f"❌ Не найден файл: {code_dir / file}")
                sys.exit(1)
                
        print("✅ Все необходимые файлы найдены")

    def step_1_install_yay(self):
        """Шаг 1: Проверка и установка yay"""
        print("\n" + "="*60)
        print("� ШАГ 1: ПРОВЕРКА И УСТАНОВКА YAY")
        print("="*60)
        
        try:
            if is_yay_installed():
                print("✅ yay уже установлен")
                return True
            
            print("📦 yay не найден. Устанавливаем...")
            install_dependencies()
            clone_and_build_yay(self.username)
            print("✅ yay успешно установлен!")
            return True
            
        except Exception as e:
            print(f"\n❌ Ошибка при установке yay: {e}")
            return False

    def step_2_install_yay_packages(self):
        """Шаг 2: Установка пакетов через yay"""
        print("\n" + "="*60)
        print("📱 ШАГ 2: УСТАНОВКА ПАКЕТОВ ЧЕРЕЗ YAY")
        print("="*60)
        
        try:
            if not YAY_PACKAGES:
                print("ℹ️  Список пакетов yay пуст, пропускаем")
                return True
                
            print(f"Установка {len(YAY_PACKAGES)} пакетов через yay (AUR)...")
            print("⚠️  Некоторые пакеты могут требовать дополнительного времени")
            install_packages_with_yay(self.username, YAY_PACKAGES)
            print("\n✅ Установка пакетов yay завершена!")
            return True
            
        except Exception as e:
            print(f"\n❌ Ошибка при установке пакетов yay: {e}")
            return False

    def step_3_install_pacman_packages(self):
        """Шаг 3: Установка пакетов через pacman"""
        print("\n" + "="*60)
        print("📦 ШАГ 3: УСТАНОВКА ПАКЕТОВ ЧЕРЕЗ PACMAN")
        print("="*60)
        
        try:
            if not PACMAN_PACKAGES:
                print("ℹ️  Список пакетов pacman пуст, пропускаем")
                return True
                
            print(f"Установка {len(PACMAN_PACKAGES)} пакетов через pacman...")
            install_packages_with_pacman(PACMAN_PACKAGES)
            print("✅ Пакеты через pacman успешно установлены!")
            return True
            
        except Exception as e:
            print(f"\n❌ Ошибка при установке пакетов pacman: {e}")
            return False

    def step_4_setup_samba(self):
        """Шаг 4: Настройка Samba сервера"""
        print("\n" + "="*60)
        print("🖥️  ШАГ 4: НАСТРОЙКА SAMBA СЕРВЕРА")
        print("="*60)
        
        try:
            samba_setup = SambaAutoSetup()
            
            print("\n📁 Создание необходимых директорий...")
            if not samba_setup.create_directories():
                print("❌ Ошибка создания директорий")
                return False

            steps = [
                ("Настройка прав доступа", samba_setup.step_1_set_permissions),
                ("Конфигурация smb.conf", samba_setup.step_2_configure_smb),
                ("Добавление пользователя", samba_setup.step_3_add_samba_user),
                ("Управление службами", samba_setup.step_4_manage_services),
                ("Проверка статуса", samba_setup.step_5_check_status),
                ("Тестирование", samba_setup.step_6_test_connection),
                ("Настройка файрвола", samba_setup.step_7_configure_firewall)
            ]

            failed_steps = []
            
            for step_name, step_func in steps:
                print(f"\n{'─'*30}")
                print(f"⚙️  {step_name}...")
                try:
                    result = step_func()
                    if result is False:
                        failed_steps.append(step_name)
                        print(f"❌ Шаг '{step_name}' завершился с ошибкой")
                    else:
                        print(f"✅ Шаг '{step_name}' выполнен успешно")
                except Exception as e:
                    print(f"❌ Критическая ошибка в шаге '{step_name}': {e}")
                    failed_steps.append(step_name)

            if not failed_steps:
                print("\n🎉 Настройка Samba завершена успешно!")
                return True
            else:
                print(f"\n⚠️  Настройка Samba завершена с ошибками в {len(failed_steps)} шагах:")
                for step in failed_steps:
                    print(f"  ❌ {step}")
                return False
                
        except Exception as e:
            print(f"\n❌ Критическая ошибка при настройке Samba: {e}")
            return False

    def run_full_setup(self):
        """Запускает полную автоматическую настройку системы"""
        print("🌟 АВТОМАТИЧЕСКАЯ НАСТРОЙКА СИСТЕМЫ")
        print("="*60)
        print("Этот скрипт выполнит:")
        print("  1️⃣  Проверку и установку yay")
        print("  2️⃣  Установку пакетов через yay")
        print("  3️⃣  Установку пакетов через pacman")
        print("  4️⃣  Настройку Samba сервера")
        print("="*60)
        
        # Проверяем требования
        self.check_requirements()
            
        steps = [
            ("Установка yay", self.step_1_install_yay),
            ("Пакеты yay", self.step_2_install_yay_packages),
            ("Пакеты pacman", self.step_3_install_pacman_packages),
            ("Настройка Samba", self.step_4_setup_samba),
        ]
        
        success_steps = 0
        total_steps = len(steps)
        
        for step_name, step_func in steps:
            if step_func():
                success_steps += 1
            else:
                print(f"⚠️  Продолжаем несмотря на ошибки в шаге '{step_name}'...")
            
        # Финальные итоги
        print("\n" + "="*60)
        print("🏁 ИТОГИ АВТОМАТИЧЕСКОЙ НАСТРОЙКИ")
        print("="*60)
        
        if success_steps == total_steps:
            print("🎉 ВСЕ ШАГИ ВЫПОЛНЕНЫ УСПЕШНО!")
            print("\n📋 Что было настроено:")
            print("  ✅ Установлены все необходимые пакеты")
            print("  ✅ Настроен Samba сервер")
            print("  ✅ Службы запущены и работают")
            print("  ✅ Файрвол настроен")
            print("  ✅ Проведено тестирование")
            
            print("\n🌐 Ваш Samba сервер готов к использованию!")
            print("📂 Доступные общие папки:")
            print("  • shared - /home/boss/Загрузки/")
            print("  • games - /mnt/aee8e7a9-5710-4dbb-bb8e-982c833a085f")  
            print("  • home2 - /mnt/Home2")
            
            print("\n🧪 Для дополнительного тестирования запустите:")
            print("  ./code/test_samba.py")
            
        elif success_steps > 0:
            print(f"⚠️  ЧАСТИЧНЫЙ УСПЕХ ({success_steps}/{total_steps} шагов)")
            print("Некоторые шаги выполнены, но есть ошибки.")
            print("Проверьте логи выше для диагностики проблем.")
            
        else:
            print("❌ НАСТРОЙКА ЗАВЕРШИЛАСЬ С ОШИБКАМИ")
            print("Проверьте логи выше и повторите процесс.")
            
        print("\nПроцесс автоматизации завершён.")
        
        return success_steps == total_steps

def main():
    """Главная функция"""
    setup_master = AutoSetupMaster()
    
    try:
        success = setup_master.run_full_setup()
        sys.exit(0 if success else 1)
        
    except KeyboardInterrupt:
        print("\n\n⚠️  Процесс прерван пользователем")
        sys.exit(1)
        
    except Exception as e:
        print(f"\n❌ Критическая ошибка: {e}")
        sys.exit(1)

if __name__ == "__main__":
    main()

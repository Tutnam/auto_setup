#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Главный скрипт автоматической настройки системы
Выполняет полную автоматизацию:
1. Установка необходимых пакетов (install.py)
2. Настройка Samba сервера (samba_auto_setup.py)

Пароль root запрашивается только один раз в начале!

Использование:
    sudo python3 main.py
    
Или с переменными окружения для автоматизации:
    export SUDO_PASSWORD="your_password"
    export SAMBA_PASSWORD="your_samba_password"
    sudo -E python3 main.py

Поддерживаемые переменные окружения:
    SUDO_PASSWORD или AUTO_SETUP_PASSWORD - для sudo пароля
    SAMBA_PASSWORD или AUTO_SETUP_SAMBA_PASSWORD - для пароля Samba пользователя
"""

import os
import sys
import getpass
import subprocess
import tempfile
import stat
from pathlib import Path

# Добавляем папку code в путь для импорта модулей
sys.path.insert(0, str(Path(__file__).parent / "code"))

try:
    # Импортируем наши модули
    from install import (
        get_password, create_askpass_script, remove_askpass_script,
        run_with_password, get_username, is_yay_installed,
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
        self.sudo_password = None
        self.askpass_script = None
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

    def get_sudo_password(self):
        """Запрашивает пароль sudo один раз в начале или берёт из переменной окружения"""
        print("\n🔐 Для автоматической настройки системы требуются права root")
        print("Пароль будет запрошен только один раз и использован для всех операций:")
        print("  • Установка пакетов")
        print("  • Настройка Samba сервера")
        print("  • Конфигурация системы")
        
        # Проверяем переменную окружения для пароля
        env_password = os.getenv("SUDO_PASSWORD") or os.getenv("AUTO_SETUP_PASSWORD")
        
        if env_password:
            self.sudo_password = env_password
            print("\n✅ Пароль получен из переменной окружения (SUDO_PASSWORD или AUTO_SETUP_PASSWORD)")
        else:
            self.sudo_password = getpass.getpass("\nВведите пароль sudo: ")
        
        # Создаём askpass скрипт для автоматической передачи пароля
        try:
            self.askpass_script = create_askpass_script(self.sudo_password)
            
            # Проверяем валидность пароля
            run_with_password(["true"], self.sudo_password)
            print("✅ Пароль принят. Начинаем автоматическую настройку...")
            return True
            
        except subprocess.CalledProcessError:
            print("❌ Неверный пароль!")
            sys.exit(1)
        except Exception as e:
            print(f"❌ Ошибка при проверке пароля: {e}")
            sys.exit(1)

    def step_1_install_packages(self):
        """Шаг 1: Установка пакетов"""
        print("\n" + "="*60)
        print("🚀 ШАГ 1: УСТАНОВКА ПАКЕТОВ")
        print("="*60)
        
        try:
            # Обновляем пакеты
            print("\n📦 Обновление системных пакетов...")
            update_packages()
            print("✅ Система обновлена")
            
            # Установка yay, если он не установлен
            if not is_yay_installed():
                print("\n🔧 Установка yay (AUR helper)...")
                install_dependencies()
                clone_and_build_yay(self.username, self.askpass_script, self.sudo_password)
                print("✅ yay успешно установлен!")
            else:
                print("\n✅ yay уже установлен")

            # Установка пакетов через yay
            if YAY_PACKAGES:
                print(f"\n📱 Установка {len(YAY_PACKAGES)} пакетов через yay (AUR)...")
                print("⚠️  Некоторые пакеты могут требовать дополнительного времени")
                install_packages_with_yay(self.username, YAY_PACKAGES, self.askpass_script, self.sudo_password)

            # Установка пакетов через pacman
            if PACMAN_PACKAGES:
                print(f"\n📦 Установка {len(PACMAN_PACKAGES)} пакетов через pacman...")
                install_packages_with_pacman(PACMAN_PACKAGES)
                print("✅ Пакеты через pacman успешно установлены!")
                
            print("\n🎉 Установка пакетов завершена!")
            return True
            
        except Exception as e:
            print(f"\n❌ Ошибка при установке пакетов: {e}")
            return False

    def step_2_setup_samba(self):
        """Шаг 2: Настройка Samba сервера"""
        print("\n" + "="*60)
        print("🖥️  ШАГ 2: НАСТРОЙКА SAMBA СЕРВЕРА")
        print("="*60)
        
        try:
            # Создаём экземпляр SambaAutoSetup с предварительно установленным паролем
            samba_setup = SambaAutoSetup()
            samba_setup.sudo_password = self.sudo_password
            
            # Пропускаем запрос пароля в samba_setup
            print("✅ Используем уже введённый пароль sudo")
            
            # Создаём директории
            print("\n📁 Создание необходимых директорий...")
            if not samba_setup.create_directories():
                print("❌ Ошибка создания директорий")
                return False

            # Выполняем все шаги настройки Samba
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

            # Итоги настройки Samba
            if not failed_steps:
                print("\n🎉 Настройка Samba завершена успешно!")
                print("✅ Samba сервер готов к работе")
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
        print("  1️⃣  Установку необходимых пакетов")
        print("  2️⃣  Настройку Samba сервера")
        print("  3️⃣  Тестирование работоспособности")
        print("="*60)
        
        # Проверяем требования
        self.check_requirements()
        
        # Получаем пароль один раз
        if not self.get_sudo_password():
            return False
            
        success_steps = 0
        total_steps = 2
        
        # Шаг 1: Установка пакетов
        if self.step_1_install_packages():
            success_steps += 1
        else:
            print("⚠️  Продолжаем несмотря на ошибки установки пакетов...")
            
        # Шаг 2: Настройка Samba
        if self.step_2_setup_samba():
            success_steps += 1
            
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
            
        print("\n💡 Пароль root был запрошен только один раз!")
        print("Процесс автоматизации завершён.")
        
        return success_steps == total_steps

    def cleanup(self):
        """Очистка временных файлов и паролей"""
        try:
            # Очищаем пароль из памяти
            self.sudo_password = None
            
            # Удаляем временный askpass скрипт
            if self.askpass_script:
                remove_askpass_script(self.askpass_script)
                
        except Exception as e:
            print(f"⚠️  Ошибка при очистке: {e}")

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
        
    finally:
        setup_master.cleanup()

if __name__ == "__main__":
    main()

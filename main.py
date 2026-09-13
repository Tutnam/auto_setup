#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Главный скрипт автоматической настройки системы
Выполняет полную автоматизацию:
1. Установка необходимых пакетов (install.py)
2. Настройка Samba сервера (samba_auto_setup.py)

Запускается с правами root через pkexec или sudo:
    pkexec python3 main.py
    # или
    sudo python3 main.py

Поддерживаемые переменные окружения:
    SAMBA_PASSWORD или AUTO_SETUP_SAMBA_PASSWORD - для пароля Samba пользователя (опционально)
"""

import os
import sys
from pathlib import Path

# Добавляем папку code в путь для импорта модулей
sys.path.insert(0, str(Path(__file__).parent / "code"))

try:
    # Импортируем наши модули
    from install import (
        check_root,
        get_username,
        is_paru_installed,
        install_dependencies,
        install_paru,
        install_packages_with_paru,
        update_system,
        PARU_PACKAGES,
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
        check_root()

        # Получаем имя пользователя
        self.username = get_username()
        print(f"✅ Пользователь: {self.username}")

        # Проверяем наличие необходимых файлов
        code_dir = Path(__file__).parent / "code"
        required_files = ["install.py", "samba_auto_setup.py"]

        for file in required_files:
            if not (code_dir / file).exists():
                print(f"❌ Не найден файл: {code_dir / file}")
                sys.exit(1)

        print("✅ Все необходимые файлы найдены")

    def step_1_install_packages(self):
        """Шаг 1: Установка пакетов"""
        print("\n" + "=" * 60)
        print("🚀 ШАГ 1: УСТАНОВКА ПАКЕТОВ")
        print("=" * 60)

        try:
            # Обновляем пакеты
            print("\n📦 Обновление системных пакетов...")
            update_system()
            print("✅ Система обновлена")

            # Установка paru, если он не установлен
            if not is_paru_installed():
                print("\n🔧 Установка paru (AUR helper)...")
                install_dependencies()
                install_paru(self.username)
                print("✅ paru успешно установлен!")
            else:
                print("\n✅ paru уже установлен")

            # Установка пакетов через paru
            if PARU_PACKAGES:
                print(f"\n📱 Установка {len(PARU_PACKAGES)} пакетов через paru...")
                print("⚠️  Некоторые пакеты могут требовать дополнительного времени")
                install_packages_with_paru(self.username, PARU_PACKAGES)

            print("\n🎉 Установка пакетов завершена!")
            return True

        except Exception as e:
            print(f"\n❌ Ошибка при установке пакетов: {e}")
            return False

    def step_2_setup_samba(self):
        """Шаг 2: Настройка Samba сервера"""
        print("\n" + "=" * 60)
        print("🖥️  ШАГ 2: НАСТРОЙКА SAMBA СЕРВЕРА")
        print("=" * 60)

        try:
            samba_setup = SambaAutoSetup(username=self.username)

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
                print(f"\n{'─' * 30}")
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
        print("\n" + "=" * 60)
        print("🏁 ИТОГИ АВТОМАТИЧЕСКОЙ НАСТРОЙКИ")
        print("=" * 60)

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
            print(f"  • shared - /home/{self.username}/Загрузки/")
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

    def cleanup(self):
        """Очистка временных ресурсов"""
        pass

def main():
    """Главная функция"""
    # Проверка прав root и автоэскалация до создания объекта и вывода баннеров
    check_root()

    setup_master = None
    try:
        setup_master = AutoSetupMaster()
        success = setup_master.run_full_setup()
        sys.exit(0 if success else 1)
        
    except KeyboardInterrupt:
        print("\n\n⚠️  Процесс прерван пользователем")
        sys.exit(130)
        
    except Exception as e:
        print(f"\n❌ Критическая ошибка: {e}")
        sys.exit(1)
        
    finally:
        if setup_master is not None:
            setup_master.cleanup()

if __name__ == "__main__":
    main()

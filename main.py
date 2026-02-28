#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Главный скрипт автоматической настройки системы
Устанавливает все пакеты через paru и настраивает Samba.

Использование:
  sudo python3 main.py                  # полная установка
  sudo python3 main.py --only-packages  # только пакеты
  sudo python3 main.py --only-samba     # только Samba
  sudo python3 main.py --skip-update    # пропустить обновление системы
"""

import os
import sys
import subprocess
import time
import logging
from pathlib import Path
from datetime import datetime

# Добавляем папку code в путь для импорта модулей
sys.path.insert(0, str(Path(__file__).parent / "code"))

try:
    from install import (
        get_username, is_paru_installed, install_paru,
        install_packages, update_system, PACKAGES,
        create_sudoers_rule
    )
    from samba_auto_setup import SambaAutoSetup
except ImportError as e:
    print(f"❌ Ошибка импорта модулей: {e}")
    print("Убедитесь, что файлы install.py и samba_auto_setup.py находятся в папке 'code'")
    sys.exit(1)


def setup_logging():
    """Настраивает логирование в файл"""
    log_dir = Path(__file__).parent / "logs"
    log_dir.mkdir(exist_ok=True)
    
    log_file = log_dir / f"setup_{datetime.now().strftime('%Y%m%d_%H%M%S')}.log"
    
    fmt = logging.Formatter("%(asctime)s [%(levelname)s] %(message)s", datefmt="%H:%M:%S")
    fh = logging.FileHandler(log_file, encoding="utf-8")
    fh.setLevel(logging.DEBUG)
    fh.setFormatter(fmt)
    
    logger = logging.getLogger("auto_setup")
    logger.setLevel(logging.DEBUG)
    logger.addHandler(fh)
    
    print(f"📄 Лог записывается в: {log_file}")
    return logger, log_file


def check_internet():
    """Проверяет наличие интернет-соединения"""
    print("🌐 Проверка интернет-соединения...")
    
    for host, name in [("8.8.8.8", "Google DNS"), ("archlinux.org", "Arch Linux")]:
        try:
            result = subprocess.run(
                ["ping", "-c", "1", "-W", "3", host],
                capture_output=True, timeout=5
            )
            if result.returncode == 0:
                print(f"  ✅ {name} — доступен")
                return True
        except (subprocess.TimeoutExpired, Exception):
            continue
    
    print("❌ Нет интернет-соединения!")
    return False


def format_duration(seconds):
    """Форматирует время в читаемый формат"""
    if seconds < 60:
        return f"{seconds:.0f}с"
    minutes = int(seconds // 60)
    secs = int(seconds % 60)
    if minutes < 60:
        return f"{minutes}м {secs}с"
    hours = int(minutes // 60)
    mins = minutes % 60
    return f"{hours}ч {mins}м {secs}с"


def parse_args(args):
    """Разбирает аргументы командной строки"""
    options = {
        "only_packages": False,
        "only_samba": False,
        "skip_update": False,
    }
    
    for arg in args:
        if arg == "--only-packages":
            options["only_packages"] = True
        elif arg == "--only-samba":
            options["only_samba"] = True
        elif arg == "--skip-update":
            options["skip_update"] = True
        elif arg in ("--help", "-h"):
            print(__doc__)
            sys.exit(0)
    
    return options


class AutoSetupMaster:
    """Главный класс для координации автоматической настройки системы"""
    
    def __init__(self):
        self.username = None
        self.logger = None
        self.log_file = None
        self.step_times = {}
        
    def log(self, message, level="info"):
        """Логирует сообщение в файл"""
        if self.logger:
            getattr(self.logger, level)(message)
    
    def check_requirements(self):
        """Проверяет системные требования"""
        print("🔍 Проверка системных требований...")
        
        if os.geteuid() != 0:
            print("❌ Этот скрипт требует прав суперпользователя. Запустите с sudo.")
            sys.exit(1)
            
        self.username = os.getenv("SUDO_USER")
        if not self.username:
            print("❌ Не удалось определить пользователя. Запустите скрипт через sudo.")
            sys.exit(1)
            
        print(f"✅ Пользователь: {self.username}")
        self.log(f"Пользователь: {self.username}")
        
        create_sudoers_rule(self.username)
        
        code_dir = Path(__file__).parent / "code"
        for file in ["install.py", "samba_auto_setup.py"]:
            if not (code_dir / file).exists():
                print(f"❌ Не найден файл: {code_dir / file}")
                sys.exit(1)
                
        print("✅ Все необходимые файлы найдены")

    def run_step(self, name, func):
        """Выполняет шаг с замером времени и логированием"""
        start = time.time()
        self.log(f"Начало шага: {name}")
        
        try:
            result = func()
            elapsed = time.time() - start
            self.step_times[name] = elapsed
            self.log(f"Шаг '{name}' завершён за {format_duration(elapsed)}, результат: {result}")
            print(f"⏱️  Шаг завершён за {format_duration(elapsed)}")
            return result
        except Exception as e:
            elapsed = time.time() - start
            self.step_times[name] = elapsed
            self.log(f"Ошибка в шаге '{name}': {e}", level="error")
            print(f"❌ Ошибка: {e}")
            return False

    def step_1_setup_paru(self):
        """Шаг 1: Проверка и установка paru"""
        print("\n" + "="*60)
        print("🔧 ШАГ 1: ПРОВЕРКА PARU")
        print("="*60)
        
        try:
            if is_paru_installed():
                print("✅ paru уже установлен")
                return True
            
            print("📦 paru не найден. Устанавливаем...")
            install_paru(self.username)
            print("✅ paru успешно установлен!")
            return True
            
        except Exception as e:
            print(f"\n❌ Ошибка при установке paru: {e}")
            return False

    def step_2_update_system(self):
        """Шаг 2: Обновление системы через paru"""
        print("\n" + "="*60)
        print("� ШАГ 2: ОБНОВЛЕНИЕ СИСТЕМЫ")
        print("="*60)
        
        try:
            update_system(self.username)
            print("✅ Система обновлена!")
            return True
        except Exception as e:
            print(f"\n❌ Ошибка при обновлении: {e}")
            return False

    def step_3_install_packages(self):
        """Шаг 3: Установка всех пакетов через paru"""
        print("\n" + "="*60)
        print("📦 ШАГ 3: УСТАНОВКА ПАКЕТОВ")
        print("="*60)
        
        try:
            if not PACKAGES:
                print("ℹ️  Список пакетов пуст, пропускаем")
                return True
                
            print(f"Всего в списке: {len(PACKAGES)} пакетов")
            install_packages(self.username, PACKAGES)
            print("\n✅ Установка пакетов завершена!")
            return True
            
        except Exception as e:
            print(f"\n❌ Ошибка при установке пакетов: {e}")
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
                        print(f"❌ {step_name} — ошибка")
                    else:
                        print(f"✅ {step_name} — OK")
                except Exception as e:
                    print(f"❌ Критическая ошибка: {step_name}: {e}")
                    failed_steps.append(step_name)

            if not failed_steps:
                print("\n🎉 Настройка Samba завершена успешно!")
                return True
            else:
                print(f"\n⚠️  Ошибки в {len(failed_steps)} шагах:")
                for step in failed_steps:
                    print(f"  ❌ {step}")
                return False
                
        except Exception as e:
            print(f"\n❌ Критическая ошибка при настройке Samba: {e}")
            return False

    def print_time_report(self):
        """Выводит отчёт по времени выполнения шагов"""
        if not self.step_times:
            return
        
        print("\n⏱️  ВРЕМЯ ВЫПОЛНЕНИЯ:")
        total = 0
        for name, elapsed in self.step_times.items():
            print(f"  • {name}: {format_duration(elapsed)}")
            total += elapsed
        print(f"  ─────────────────────────")
        print(f"  🕐 Общее время: {format_duration(total)}")
        self.log(f"Общее время: {format_duration(total)}")

    def run_full_setup(self, options=None):
        """Запускает полную автоматическую настройку системы"""
        if options is None:
            options = {}
        
        # Настраиваем логирование
        self.logger, self.log_file = setup_logging()
        self.log("Начало автоматической настройки системы")
        
        print("🌟 АВТОМАТИЧЕСКАЯ НАСТРОЙКА СИСТЕМЫ")
        print("="*60)
        
        only_packages = options.get("only_packages", False)
        only_samba = options.get("only_samba", False)
        skip_update = options.get("skip_update", False)
        
        if only_packages:
            print("📋 Режим: только установка пакетов")
        elif only_samba:
            print("📋 Режим: только настройка Samba")
        else:
            print("📋 Режим: полная установка")
        
        print("="*60)
        
        # Проверяем требования
        self.check_requirements()
        
        # Проверяем интернет (если будем ставить пакеты)
        if not only_samba:
            if not check_internet():
                self.log("Нет интернет-соединения", level="error")
                return False

        # Формируем список шагов
        steps = []
        
        if not only_samba:
            steps.append(("Проверка paru", self.step_1_setup_paru))
            if not skip_update:
                steps.append(("Обновление системы", self.step_2_update_system))
            steps.append(("Установка пакетов", self.step_3_install_packages))
        
        if not only_packages:
            steps.append(("Настройка Samba", self.step_4_setup_samba))
        
        success_steps = 0
        total_steps = len(steps)
        
        for step_name, step_func in steps:
            if self.run_step(step_name, step_func):
                success_steps += 1
            else:
                print(f"⚠️  Продолжаем несмотря на ошибки в '{step_name}'...")
                self.log(f"Ошибка в '{step_name}', продолжаем", level="warning")
            
        # Финальные итоги
        print("\n" + "="*60)
        print("🏁 ИТОГИ АВТОМАТИЧЕСКОЙ НАСТРОЙКИ")
        print("="*60)
        
        self.print_time_report()
        
        if success_steps == total_steps:
            print("\n🎉 ВСЕ ШАГИ ВЫПОЛНЕНЫ УСПЕШНО!")
            self.log("Все шаги выполнены успешно")
            
            if not only_packages:
                print("\n🌐 Samba сервер готов к использованию!")
                print("📂 Доступные общие папки:")
                print("  • shared - /home/boss/Загрузки/")
                print("  • games - /mnt/aee8e7a9-5710-4dbb-bb8e-982c833a085f")  
                print("  • home2 - /mnt/Home2")
            
        elif success_steps > 0:
            print(f"\n⚠️  ЧАСТИЧНЫЙ УСПЕХ ({success_steps}/{total_steps} шагов)")
            self.log(f"Частичный успех: {success_steps}/{total_steps}")
            
        else:
            print("\n❌ НАСТРОЙКА ЗАВЕРШИЛАСЬ С ОШИБКАМИ")
            self.log("Настройка завершилась с ошибками", level="error")
            
        print(f"\n📄 Полный лог: {self.log_file}")
        return success_steps == total_steps


def main():
    """Главная функция"""
    options = parse_args(sys.argv[1:])
    setup_master = AutoSetupMaster()
    
    try:
        success = setup_master.run_full_setup(options)
        sys.exit(0 if success else 1)
        
    except KeyboardInterrupt:
        print("\n\n⚠️  Процесс прерван пользователем")
        sys.exit(1)
        
    except Exception as e:
        print(f"\n❌ Критическая ошибка: {e}")
        sys.exit(1)

if __name__ == "__main__":
    main()

#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Автоматический скрипт настройки Samba сервера
Автоматизирует все действия из файла samba.py
"""

import subprocess
import getpass
import sys
import os
import time
from pathlib import Path

class SambaAutoSetup:
    def __init__(self):
        self.sudo_password = None
        self.username = None
        
    def get_sudo_password(self):
        """Запрашивает пароль root один раз в начале (только если пароль не установлен)"""
        if self.sudo_password is not None:
            print("✅ Используется предварительно введённый пароль sudo")
            return
            
        print("🔐 Для настройки Samba требуются права root")
        self.sudo_password = getpass.getpass("Введите пароль sudo: ")
        
        # Проверяем валидность пароля
        try:
            result = self.run_sudo_command("whoami")
            if result.returncode != 0:
                print("❌ Неверный пароль!")
                sys.exit(1)
            print("✅ Пароль принят")
        except Exception as e:
            print(f"❌ Ошибка проверки пароля: {e}")
            sys.exit(1)

    def run_sudo_command(self, command, input_text=None):
        """Выполняет команду с sudo, используя сохранённый пароль"""
        if isinstance(command, str):
            cmd = ["sudo", "-S"] + command.split()
        else:
            cmd = ["sudo", "-S"] + command
            
        try:
            if input_text:
                full_input = f"{self.sudo_password}\n{input_text}"
            else:
                full_input = f"{self.sudo_password}\n"
                
            result = subprocess.run(
                cmd,
                input=full_input,
                text=True,
                capture_output=True,
                timeout=30
            )
            return result
        except subprocess.TimeoutExpired:
            print(f"⏰ Команда {' '.join(cmd)} превысила время ожидания")
            return None
        except Exception as e:
            print(f"❌ Ошибка выполнения команды {' '.join(cmd)}: {e}")
            return None

    def run_command(self, command):
        """Выполняет обычную команду без sudo"""
        try:
            result = subprocess.run(
                command.split() if isinstance(command, str) else command,
                capture_output=True,
                text=True,
                timeout=30
            )
            return result
        except Exception as e:
            print(f"❌ Ошибка выполнения команды {command}: {e}")
            return None

    def step_1_set_permissions(self):
        """Шаг 1: Устанавливаем права на директорию samba usershares"""
        print("\n📁 Шаг 1: Настройка прав доступа...")
        
        # Создаём директорию если не существует
        result = self.run_sudo_command("mkdir -p /var/lib/samba/usershares")
        if result and result.returncode == 0:
            print("✅ Директория /var/lib/samba/usershares создана")
        
        # Устанавливаем права
        result = self.run_sudo_command("chmod 1770 /var/lib/samba/usershares")
        if result and result.returncode == 0:
            print("✅ Права 1770 установлены для /var/lib/samba/usershares")
        else:
            print("❌ Ошибка установки прав")
            return False
        return True

    def step_2_configure_smb(self):
        """Шаг 2: Настройка конфигурационного файла smb.conf"""
        print("\n⚙️  Шаг 2: Настройка smb.conf...")
        
        # Создаём резервную копию
        result = self.run_sudo_command("cp /etc/samba/smb.conf /etc/samba/smb.conf.backup")
        if result and result.returncode == 0:
            print("✅ Резервная копия smb.conf создана")

        # Конфигурация Samba
        smb_config = """
[global]
    security = user
    workgroup = WORKGROUP
    server string = Samba
    client min protocol = NT1

    guest account = boss
    map to guest = Bad User
    auth methods = guest, sam_ignoredomain
    create mask = 0775
    directory mask = 0775
    hide dot files = yes

[shared]
    comment = Public Folder
    path = /home/boss/Загрузки/
    browseable = Yes
    guest ok = Yes
    public = yes
    writeable = Yes
    read only = no
    guest ok = yes
    create mask = 0775
    directory mask = 0775
    force create mode = 0775
    force directory mode = 0775

[games]
    comment = Directory anonimus
    path = /mnt/aee8e7a9-5710-4dbb-bb8e-982c833a085f
    browseable = Yes
    guest ok = Yes
    public = yes
    writable = yes
    read only = no
    guest ok = yes
    create mask = 0775
    directory mask = 0775
    force create mode = 0775
    force directory mode = 0775

[home2]
    comment = Directory anonimus
    path = /mnt/Home2
    browseable = Yes
    guest ok = Yes
    public = yes
    writable = yes
    read only = no
    guest ok = yes
    create mask = 0775
    directory mask = 0775
    force create mode = 0775
    force directory mode = 0775
"""

        # Записываем конфигурацию
        try:
            with open("/tmp/smb_config.tmp", "w", encoding="utf-8") as f:
                f.write(smb_config)
            
            result = self.run_sudo_command("cp /tmp/smb_config.tmp /etc/samba/smb.conf")
            if result and result.returncode == 0:
                print("✅ Конфигурация smb.conf обновлена")
                # Удаляем временный файл
                os.remove("/tmp/smb_config.tmp")
                return True
            else:
                print("❌ Ошибка обновления smb.conf")
                return False
        except Exception as e:
            print(f"❌ Ошибка создания конфигурации: {e}")
            return False

    def step_3_add_samba_user(self):
        """Шаг 3: Добавление пользователя в Samba"""
        print("\n👤 Шаг 3: Добавление пользователя в Samba...")
        
        # Получаем имя текущего пользователя
        current_user = os.getenv("USER", "boss")
        
        # Запрашиваем пароль для Samba
        print(f"Добавляем пользователя '{current_user}' в Samba")
        samba_password = getpass.getpass(f"Введите пароль для Samba пользователя {current_user}: ")
        
        # Добавляем пользователя
        result = self.run_sudo_command(f"smbpasswd -a {current_user}", input_text=f"{samba_password}\n{samba_password}\n")
        
        if result and result.returncode == 0:
            print(f"✅ Пользователь {current_user} добавлен в Samba")
            return True
        else:
            print(f"❌ Ошибка добавления пользователя {current_user}")
            if result:
                print(f"Вывод ошибки: {result.stderr}")
            return False

    def step_4_manage_services(self):
        """Шаг 4: Управление службами Samba"""
        print("\n🔄 Шаг 4: Управление службами Samba...")
        
        # Включаем службы
        services = ["smb", "nmb"]
        
        for service in services:
            # Включаем автозапуск
            result = self.run_sudo_command(f"systemctl enable {service}")
            if result and result.returncode == 0:
                print(f"✅ Автозапуск службы {service} включён")
            
            # Запускаем службу
            result = self.run_sudo_command(f"systemctl start {service}")
            if result and result.returncode == 0:
                print(f"✅ Служба {service} запущена")
            else:
                print(f"❌ Ошибка запуска службы {service}")
                
            # Перезапускаем для применения настроек
            result = self.run_sudo_command(f"systemctl restart {service}")
            if result and result.returncode == 0:
                print(f"✅ Служба {service} перезапущена")

        return True

    def step_5_check_status(self):
        """Шаг 5: Проверка статуса служб"""
        print("\n🔍 Шаг 5: Проверка статуса служб...")
        
        services = ["smb", "nmb"]
        active_services = 0
        
        for service in services:
            result = self.run_command(f"systemctl is-active {service}")
            if result and result.stdout.strip() == "active":
                print(f"✅ Служба {service}: активна")
                active_services += 1
            else:
                print(f"❌ Служба {service}: неактивна")
                
            # Показываем статус
            result = self.run_command(f"systemctl status {service} --no-pager -l")
            if result and result.returncode == 0:
                print(f"📋 Статус {service}:")
                print(result.stdout[:300] + "..." if len(result.stdout) > 300 else result.stdout)
                
        # Возвращаем True если все службы активны
        return active_services == len(services)

    def step_6_test_connection(self):
        """Шаг 6: Тестирование подключения"""
        print("\n🧪 Шаг 6: Тестирование Samba...")
        
        try:
            # Получаем IP адрес (используем ip команду для совместимости с Arch Linux)
            result = self.run_command("ip route get 1.1.1.1")
            ip_address = None
            
            if result and result.returncode == 0:
                # Извлекаем IP адрес из вывода: 1.1.1.1 via 192.168.0.1 dev wlan0 src 192.168.0.175
                try:
                    parts = result.stdout.strip().split()
                    src_index = parts.index('src')
                    if src_index + 1 < len(parts):
                        ip_address = parts[src_index + 1]
                        print(f"🌐 IP адрес сервера: {ip_address}")
                except (ValueError, IndexError):
                    print("⚠️  Не удалось извлечь IP адрес из вывода ip команды")
                    
            # Если не удалось получить IP, пробуем альтернативные способы
            if not ip_address:
                print("Пробуем альтернативные способы получения IP...")
                
                # Пробуем hostname -i
                result2 = self.run_command("hostname -i")
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
                result = self.run_command(f"smbclient -L //{ip_address} -N")
                if result and result.returncode == 0:
                    print("✅ Samba сервер отвечает на IP адрес!")
                    print("Доступные ресурсы:")
                    print(result.stdout)
                    return True
                else:
                    print(f"⚠️  Ошибка подключения к {ip_address}")
                    if result:
                        print(f"Код ошибки: {result.returncode}")
                        
            # Пробуем альтернативный способ - тестируем localhost
            print("Тестируем подключение к localhost...")
            result2 = self.run_command("smbclient -L //localhost -N")
            if result2 and result2.returncode == 0:
                print("✅ Samba сервер отвечает на localhost!")
                print("Доступные ресурсы:")
                print(result2.stdout)
                return True
            else:
                print("❌ Ошибка подключения и к localhost")
                if result2:
                    print(f"Код ошибки: {result2.returncode}")
                    print(f"Stderr: {result2.stderr}")
                return False
        except Exception as e:
            print(f"❌ Критическая ошибка при тестировании: {e}")
            return False

    def step_7_configure_firewall(self):
        """Шаг 7: Настройка файрвола (опционально)"""
        print("\n🔥 Шаг 7: Настройка файрвола...")
        
        try:
            # Проверяем наличие UFW
            result = self.run_command("which ufw")
            if result and result.returncode == 0:
                print("UFW найден. Настраиваем правила...")
                
                # Добавляем правила для Samba (убираем правило samba, которое может не работать)
                samba_rules = [
                    ("ufw allow from 192.168.0.0/24", "Разрешить локальную сеть 192.168.0.x"),
                    ("ufw allow from 192.168.1.0/24", "Разрешить локальную сеть 192.168.1.x"), 
                    ("ufw allow from 10.0.0.0/8", "Разрешить локальную сеть 10.x.x.x"),
                    ("ufw allow 139/tcp", "SMB NetBIOS Session Service"),
                    ("ufw allow 445/tcp", "SMB over TCP"),
                    ("ufw allow 137/udp", "NetBIOS Name Service"),
                    ("ufw allow 138/udp", "NetBIOS Datagram Service")
                ]
                
                success_count = 0
                for rule, description in samba_rules:
                    result = self.run_sudo_command(rule)
                    if result and result.returncode == 0:
                        print(f"✅ Правило добавлено: {rule}")
                        success_count += 1
                    else:
                        print(f"⚠️  Не удалось добавить правило: {rule}")
                        if result:
                            print(f"   Причина: {result.stderr.strip()}")
                
                if success_count > 0:
                    print(f"✅ Файрвол настроен для Samba ({success_count}/{len(samba_rules)} правил)")
                    return True
                else:
                    print("❌ Не удалось добавить ни одного правила файрвола")
                    return False
            else:
                print("UFW не найден, пропускаем настройку файрвола")
                return True  # Не ошибка, просто UFW не установлен
        except Exception as e:
            print(f"❌ Ошибка настройки файрвола: {e}")
            return False

    def create_directories(self):
        """Создаём необходимые директории"""
        print("\n📁 Создание директорий...")
        
        directories = [
            "/home/boss/Загрузки",
            "/mnt/Home2"
        ]
        
        success_count = 0
        for directory in directories:
            if not os.path.exists(directory):
                try:
                    result = self.run_sudo_command(f"mkdir -p {directory}")
                    if result and result.returncode == 0:
                        print(f"✅ Директория {directory} создана")
                        
                        # Устанавливаем права
                        result = self.run_sudo_command(f"chown boss:boss {directory}")
                        if result and result.returncode == 0:
                            print(f"✅ Права для {directory} установлены")
                            success_count += 1
                        else:
                            print(f"⚠️  Директория создана, но не удалось установить права для {directory}")
                    else:
                        print(f"❌ Ошибка создания директории {directory}")
                except Exception as e:
                    print(f"❌ Ошибка: {e}")
            else:
                print(f"✅ Директория {directory} уже существует")
                success_count += 1
                
        return success_count == len(directories)

    def run_setup(self):
        """Запускает полную настройку Samba"""
        print("🚀 Автоматическая настройка Samba сервера")
        print("=" * 50)
        
        # Получаем пароль root
        self.get_sudo_password()
        
        # Создаём директории
        if not self.create_directories():
            print("❌ Ошибка создания директорий")
            return
        
        # Выполняем все шаги
        steps = [
            ("Настройка прав доступа", self.step_1_set_permissions),
            ("Конфигурация smb.conf", self.step_2_configure_smb),
            ("Добавление пользователя", self.step_3_add_samba_user),
            ("Управление службами", self.step_4_manage_services),
            ("Проверка статуса", self.step_5_check_status),
            ("Тестирование", self.step_6_test_connection),
            ("Настройка файрвола", self.step_7_configure_firewall)
        ]
        
        failed_steps = []
        
        for step_name, step_func in steps:
            print(f"\n{'='*20}")
            try:
                result = step_func()
                # Если функция вернула False или None, считаем шаг неудачным
                if result is False:
                    failed_steps.append(step_name)
                elif result is None:
                    # Для функций, которые не возвращают булево значение, считаем успехом
                    print(f"✅ Шаг '{step_name}' завершён")
            except Exception as e:
                print(f"❌ Критическая ошибка в шаге '{step_name}': {e}")
                failed_steps.append(step_name)
                
        # Итоги
        print("\n" + "="*50)
        print("🏁 ИТОГИ НАСТРОЙКИ")
        print("="*50)
        
        if not failed_steps:
            print("🎉 Все шаги выполнены успешно!")
            print("✅ Samba сервер готов к работе")
            print("\n📝 Полезная информация:")
            print("• Конфигурация: /etc/samba/smb.conf")
            print("• Резервная копия: /etc/samba/smb.conf.backup")
            print("• Доступные ресурсы: shared, games, home2")
            print("• Для подключения используйте IP адрес сервера")
        else:
            print("⚠️  Некоторые шаги завершились с ошибками:")
            for step in failed_steps:
                print(f"  ❌ {step}")
            print("\nПроверьте логи и повторите неудачные шаги вручную")

if __name__ == "__main__":
    setup = SambaAutoSetup()
    setup.run_setup()

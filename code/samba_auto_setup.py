#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Автоматический скрипт настройки Samba сервера
Запускается с правами root через pkexec или sudo.
"""

import subprocess
import getpass
import sys
import os
import pwd
import time
from pathlib import Path

# Импортируем утилиты проверки root и пользователя
try:
    from install import check_root, get_username
except ImportError:
    from code.install import check_root, get_username


class SambaAutoSetup:
    def __init__(self, username: str | None = None):
        self.username = username

    def run_command(self, command, input_text: str | None = None):
        """Выполняет команду напрямую от root."""
        cmd = command.split() if isinstance(command, str) else command
        try:
            result = subprocess.run(
                cmd,
                input=input_text,
                capture_output=True,
                text=True,
                timeout=30
            )
            return result
        except subprocess.TimeoutExpired:
            cmd_str = ' '.join(cmd) if isinstance(cmd, list) else str(cmd)
            print(f"⏰ Команда {cmd_str} превысила время ожидания")
            return None
        except Exception as e:
            cmd_str = ' '.join(cmd) if isinstance(cmd, list) else str(cmd)
            print(f"❌ Ошибка выполнения команды {cmd_str}: {e}")
            return None

    def run_sudo_command(self, command, input_text: str | None = None):
        """Выполняет привилегированную команду напрямую от root (обратная совместимость)."""
        return self.run_command(command, input_text=input_text)

    def step_1_set_permissions(self):
        """Шаг 1: Устанавливаем права на директорию samba usershares"""
        print("\n📁 Шаг 1: Настройка прав доступа...")
        
        # Создаём директорию если не существует
        result = self.run_command("mkdir -p /var/lib/samba/usershares")
        if result and result.returncode == 0:
            print("✅ Директория /var/lib/samba/usershares создана")
        
        # Устанавливаем права
        result = self.run_command("chmod 1770 /var/lib/samba/usershares")
        if result and result.returncode == 0:
            print("✅ Права 1770 установлены для /var/lib/samba/usershares")
        else:
            print("❌ Ошибка установки прав")
            return False
        return True

    def step_2_configure_smb(self):
        """Шаг 2: Настройка конфигурационного файла smb.conf"""
        print("\n⚙️  Шаг 2: Настройка smb.conf...")
        
        # Получаем имя пользователя для guest account и пути
        username = self.username or get_username()
        try:
            user_info = pwd.getpwnam(username)
            home_dir = user_info.pw_dir
        except KeyError:
            home_dir = f"/home/{username}"
        downloads_path = f"{home_dir}/Загрузки"
        
        # Создаём резервную копию
        if os.path.exists("/etc/samba/smb.conf"):
            result = self.run_command("cp /etc/samba/smb.conf /etc/samba/smb.conf.backup")
            if result and result.returncode == 0:
                print("✅ Резервная копия smb.conf создана")

        smb_config = f"""
[global]
    workgroup = WORKGROUP
    server string = Samba
    server role = standalone server
    security = user
    map to guest = Bad User
    guest account = {username}
    client min protocol = NT1
    server min protocol = NT1
    
    create mask = 0775
    directory mask = 0775
    hide dot files = yes
    unix extensions = no

[shared]
    comment = Public Folder
    path = {downloads_path}/
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

        # Безопасная атомарная запись конфигурации
        tmp_config_path = "/etc/samba/smb.conf.tmp"
        target_config_path = "/etc/samba/smb.conf"
        try:
            os.makedirs("/etc/samba", exist_ok=True)
            with open(tmp_config_path, "w", encoding="utf-8") as f:
                f.write(smb_config)
            os.chmod(tmp_config_path, 0o644)
            os.replace(tmp_config_path, target_config_path)
            print("✅ Конфигурация smb.conf обновлена")
            return True
        except Exception as e:
            if os.path.exists(tmp_config_path):
                try:
                    os.remove(tmp_config_path)
                except OSError:
                    pass
            print(f"❌ Ошибка создания конфигурации smb.conf: {e}")
            return False

    def step_3_add_samba_user(self):
        """Шаг 3: Добавление пользователя в Samba"""
        print("\n👤 Шаг 3: Добавление пользователя в Samba...")
        
        current_user = self.username or get_username()
        
        # Проверяем переменную окружения для пароля Samba
        env_samba_password = os.getenv("SAMBA_PASSWORD") or os.getenv("AUTO_SETUP_SAMBA_PASSWORD")
        
        if env_samba_password:
            samba_password = env_samba_password
            print(f"Добавляем пользователя '{current_user}' в Samba (пароль из переменной окружения)")
        else:
            print(f"Добавляем пользователя '{current_user}' в Samba")
            samba_password = getpass.getpass(f"Введите пароль для Samba пользователя {current_user}: ")
        
        # Добавляем пользователя без sudo-пароля
        result = self.run_command(f"smbpasswd -a {current_user}", input_text=f"{samba_password}\n{samba_password}\n")
        
        if result and result.returncode == 0:
            print(f"✅ Пользователь {current_user} добавлен в Samba")
            return True
        else:
            print(f"❌ Ошибка добавления пользователя {current_user}")
            if result and result.stderr:
                print(f"Вывод ошибки: {result.stderr}")
            return False

    def step_4_manage_services(self):
        """Шаг 4: Управление службами Samba"""
        print("\n🔄 Шаг 4: Управление службами Samba...")
        
        # Включаем службы
        services = ["smb", "nmb"]
        
        for service in services:
            # Включаем автозапуск
            result = self.run_command(f"systemctl enable {service}")
            if result and result.returncode == 0:
                print(f"✅ Автозапуск службы {service} включён")
            
            # Запускаем службу
            result = self.run_command(f"systemctl start {service}")
            if result and result.returncode == 0:
                print(f"✅ Служба {service} запущена")
            else:
                print(f"❌ Ошибка запуска службы {service}")
                
            # Перезапускаем для применения настроек
            result = self.run_command(f"systemctl restart {service}")
            if result and result.returncode == 0:
                print(f"✅ Служба {service} перезапущена")
            else:
                if result:
                    print(f"⚠️  Ошибка перезапуска службы {service}: {result.stderr}")

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
                # Показываем подробности ошибки
                status_result = self.run_command(f"systemctl status {service} --no-pager -l")
                if status_result:
                    print(f"📋 Детали статуса {service}:")
                    print(status_result.stdout[:500] if len(status_result.stdout) > 500 else status_result.stdout)
                    if status_result.stderr:
                        print(f"Ошибки: {status_result.stderr[:200]}")
                
            # Показываем статус для активных служб
            if result and result.stdout.strip() == "active":
                status_result = self.run_command(f"systemctl status {service} --no-pager -l")
                if status_result and status_result.returncode == 0:
                    print(f"📋 Статус {service}:")
                    print(status_result.stdout[:300] + "..." if len(status_result.stdout) > 300 else status_result.stdout)
                
        # Возвращаем True если все службы активны
        return active_services == len(services)

    def step_6_test_connection(self):
        """Шаг 6: Тестирование подключения"""
        print("\n🧪 Шаг 6: Тестирование Samba...")
        
        # Сначала проверяем конфигурацию через testparm
        print("Проверка конфигурации через testparm...")
        result_check = self.run_command("testparm -s")
        if result_check and result_check.returncode == 0:
            print("✅ Конфигурация Samba корректна")
        else:
            print("⚠️  Предупреждения в конфигурации:")
            if result_check:
                print(result_check.stderr[:500] if result_check.stderr else result_check.stdout[:500])
        
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
                    result = self.run_command(rule)
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
        
        # Получаем имя реального пользователя
        username = self.username or get_username()
        try:
            user_info = pwd.getpwnam(username)
            home_dir = user_info.pw_dir
        except KeyError:
            home_dir = f"/home/{username}"
        
        directories = [
            f"{home_dir}/Загрузки",
            "/mnt/Home2"
        ]
        
        success_count = 0
        for directory in directories:
            if not os.path.exists(directory):
                try:
                    result = self.run_command(f"mkdir -p {directory}")
                    if result and result.returncode == 0:
                        print(f"✅ Директория {directory} создана")
                        
                        # Устанавливаем права только для домашних директорий
                        if directory.startswith(home_dir) or directory.startswith("/home/"):
                            result = self.run_command(f"chown {username}:{username} {directory}")
                            if result and result.returncode == 0:
                                print(f"✅ Права для {directory} установлены")
                                success_count += 1
                            else:
                                print(f"⚠️  Директория создана, но не удалось установить права для {directory}")
                        else:
                            success_count += 1
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
        check_root()
        if not self.username:
            self.username = get_username()

        print("🚀 Автоматическая настройка Samba сервера")
        print("=" * 50)
        print(f"👤 Пользователь: {self.username}")
        
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

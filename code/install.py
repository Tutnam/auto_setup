#!/usr/bin/env python3
"""
Автоматический установщик пакетов для Arch Linux
Устанавливает все пакеты через paru (AUR + официальные репозитории)

Возможности:
- Единый менеджер пакетов paru для AUR и official repos
- Пропуск уже установленных пакетов
- Автоматическая обработка зависших процессов (тайм-аут 5 мин)
- Retry механизм для проблемных пакетов (3 попытки)
- Детальные отчёты об установке

Использование: sudo python3 install.py
"""

import os
import subprocess
import sys
import time

# Настройки
RETRY_ATTEMPTS = 3      # Количество попыток для проблемных пакетов
RETRY_DELAY = 2         # Задержка между попытками в секундах
PROCESS_TIMEOUT = 300   # Максимальное время ожидания процесса в секундах (5 минут)

# Единый список пакетов для установки через paru
PACKAGES = [
    # AUR пакеты
    'yandex-music',
    'pycharm',
    'pantum-driver',
    'portproton',
    'google-chrome',
    'yandex-browser',
    'samba-support',
    'antigravity',
    'antigravity-tools-bin',
    'anydesk-bin',
    'syncthing-bin',
    'v2rayn-bin',
    'onlyoffice-bin',
    # Официальные репозитории
    'remmina',
    'kvantum',
    'kmines',
    'obsidian',
    'transmission-qt',
    'chromium',
    'gnome-disk-utility',
    'neofetch',
    'telegram-desktop',
    'steam',
    'samba',
    'vlc',
    'gvfs-dnssd',
]


def check_root():
    if os.geteuid() != 0:
        print("Этот скрипт требует прав суперпользователя. Запустите с sudo.")
        sys.exit(1)


def get_username():
    user = os.getenv("SUDO_USER")
    if not user:
        print("Не удалось определить пользователя. Запустите скрипт через sudo.")
        sys.exit(1)
    return user


def is_package_installed(package):
    """Проверяет, установлен ли пакет в системе"""
    result = subprocess.run(
        ["pacman", "-Q", package],
        capture_output=True, text=True
    )
    return result.returncode == 0


def filter_installed(packages):
    """Возвращает только неустановленные пакеты из списка"""
    to_install = []
    already_installed = []
    for pkg in packages:
        if is_package_installed(pkg):
            already_installed.append(pkg)
        else:
            to_install.append(pkg)
    
    if already_installed:
        print(f"  ⏭️  Уже установлены ({len(already_installed)}): {', '.join(already_installed)}")
    
    return to_install


def is_paru_installed():
    """Проверяет, установлен ли paru"""
    result = subprocess.run(["which", "paru"], capture_output=True)
    return result.returncode == 0


def run_as_user(cmd, user, cwd=None, timeout=None):
    """Запускает команду от имени указанного пользователя с тайм-аутом"""
    if timeout is None:
        timeout = PROCESS_TIMEOUT

    full_cmd = ["sudo", "-u", user, "-H"] + cmd

    try:
        result = subprocess.run(
            full_cmd,
            capture_output=True,
            text=True,
            cwd=cwd,
            timeout=timeout
        )
        if result.returncode != 0:
            print(f"Ошибка выполнения команды: {' '.join(cmd)}")
            print(f"Return code: {result.returncode}")
            if result.stderr:
                print(f"STDERR: {result.stderr}")
            raise subprocess.CalledProcessError(result.returncode, cmd, output=result.stdout, stderr=result.stderr)
        return result.stdout, result.stderr
    except subprocess.TimeoutExpired:
        print(f"⚠️  Команда превысила тайм-аут ({timeout}с): {' '.join(cmd)}")
        raise subprocess.CalledProcessError(-1, cmd, output="", stderr=f"Timeout after {timeout}s")


def install_paru(user):
    """Устанавливает paru из AUR"""
    clone_dir = f"/home/{user}/paru"
    try:
        # Устанавливаем зависимости
        subprocess.run(["pacman", "-S", "--noconfirm", "--needed", "git", "base-devel", "rust"], check=True)
        
        # Клонируем репозиторий paru
        run_as_user(["git", "clone", "https://aur.archlinux.org/paru.git", clone_dir], user=user)

        # Собираем и устанавливаем paru
        run_as_user(["bash", "-c", f"cd {clone_dir} && makepkg -si --noconfirm"], user=user, timeout=600)

        # Удаляем директорию сборки
        subprocess.run(["rm", "-rf", clone_dir], check=True)
    except subprocess.CalledProcessError as e:
        print(f"Ошибка при сборке paru: {e}")
        sys.exit(1)


def update_system(user):
    """Обновляет систему через paru (AUR + official repos)"""
    try:
        run_as_user(["paru", "-Syu", "--noconfirm"], user=user, timeout=600)
    except subprocess.CalledProcessError as e:
        print(f"Ошибка при обновлении системы: {e}")
        raise


def install_packages(user, packages):
    """Устанавливает пакеты через paru"""
    # Фильтруем уже установленные
    packages = filter_installed(packages)
    if not packages:
        print("✅ Все пакеты уже установлены!")
        return
    
    print(f"  📦 Нужно установить: {len(packages)} пакетов")
    
    failed_packages = []
    successful_packages = []

    for package in packages:
        package_installed = False
        pkg_start = time.time()

        for attempt in range(RETRY_ATTEMPTS):
            try:
                if attempt == 0:
                    print(f"Устанавливаем {package}...")
                else:
                    print(f"Повторная попытка {attempt + 1}/{RETRY_ATTEMPTS} для {package}...")

                paru_cmd = [
                    "paru", "-S",
                    "--noconfirm",
                    "--needed",
                    "--skipreview",
                    package
                ]

                # Тайм-аут: 300с первая попытка, 600с повторные
                timeout = PROCESS_TIMEOUT if attempt == 0 else PROCESS_TIMEOUT * 2
                stdout, stderr = run_as_user(paru_cmd, user=user, timeout=timeout)
                elapsed = time.time() - pkg_start
                successful_packages.append(package)
                print(f"✓ {package} установлен успешно ({elapsed:.0f}с)")
                package_installed = True
                break

            except subprocess.CalledProcessError as e:
                if attempt < RETRY_ATTEMPTS - 1:
                    error_msg = ""
                    if hasattr(e, 'stderr') and e.stderr:
                        error_msg = e.stderr[:100]

                    if "Timeout" in str(e.stderr):
                        print(f"  ⏱️  Тайм-аут на попытке {attempt + 1}, попробуем ещё раз...")
                    else:
                        print(f"  Попытка {attempt + 1} не удалась: {error_msg}...")

                    print(f"  Ожидание {RETRY_DELAY} секунд перед повторной попыткой...")
                    time.sleep(RETRY_DELAY)
                else:
                    failed_packages.append(package)
                    print(f"✗ Не удалось установить {package} после {RETRY_ATTEMPTS} попыток")
                    if hasattr(e, 'stderr') and e.stderr:
                        print(f"  Финальная ошибка: {e.stderr[:200]}...")

            except Exception as e:
                if attempt < RETRY_ATTEMPTS - 1:
                    print(f"  Непредвиденная ошибка на попытке {attempt + 1}: {str(e)[:100]}...")
                    time.sleep(RETRY_DELAY)
                else:
                    failed_packages.append(package)
                    print(f"✗ Ошибка при установке {package}: {e}")
                    break

        if not package_installed and package not in failed_packages:
            failed_packages.append(package)

    # Выводим результаты
    if successful_packages:
        print(f"\nУспешно установлено ({len(successful_packages)} пакетов):")
        for pkg in successful_packages:
            print(f"  ✓ {pkg}")

    if failed_packages:
        print(f"\nНе удалось установить ({len(failed_packages)} пакетов):")
        for pkg in failed_packages:
            print(f"  ✗ {pkg}")
        print("\nВозможные причины:")
        print("  - Проблемы с сетью")
        print("  - Пакет недоступен в AUR / репозиториях")
        print("  - Ошибки сборки пакета")

        print(f"\n💡 Для ручной установки неудачных пакетов выполните:")
        for pkg in failed_packages:
            print(f"  paru -S {pkg}")


def main():
    check_root()
    user = get_username()

    try:
        # Проверяем paru
        if not is_paru_installed():
            print("Установка paru...")
            install_paru(user)
            print("paru успешно установлен!")
        else:
            print("paru уже установлен.")

        # Обновляем систему
        print("Обновляем систему через paru...")
        update_system(user)

        # Устанавливаем пакеты
        if PACKAGES:
            print(f"Установка {len(PACKAGES)} пакетов через paru...")
            install_packages(user, PACKAGES)

        print("\n🎉 Все задачи выполнены!")

    except Exception as e:
        print(f"Произошла ошибка: {e}")
        sys.exit(1)


if __name__ == "__main__":
    main()
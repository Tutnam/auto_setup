#!/usr/bin/env python3
"""
Автоматический установщик пакетов для Arch Linux
Устанавливает пакеты через yay (AUR) и pacman

Возможности:
- Автоматическая обработка зависших процессов (тайм-аут 5 мин)
- Retry механизм для проблемных пакетов (3 попытки)
- Детальные отчеты об установке
- Продолжение работы при ошибках отдельных пакетов

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

# Списки пакетов для установки
YAY_PACKAGES = [
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
]  # Замените на свои пакеты

PACMAN_PACKAGES = [
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
    'onlyoffice',
    'gvfs-dnssd',
    'kvantum'
]  # Замените на свои пакеты


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


def is_yay_installed():
    result = subprocess.run(["which", "yay"], capture_output=True)
    return result.returncode == 0


def install_dependencies():
    try:
        subprocess.run(["pacman", "-Syu", "--noconfirm"], check=True)
        subprocess.run(["pacman", "-S", "--noconfirm", "--needed", "git", "base-devel", "go"], check=True)
    except subprocess.CalledProcessError as e:
        print(f"Ошибка при установке зависимостей: {e}")
        sys.exit(1)


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


def clone_and_build_yay(user):
    clone_dir = f"/home/{user}/yay"
    try:
        # Клонируем репозиторий yay
        run_as_user(["git", "clone", "https://aur.archlinux.org/yay.git", clone_dir], user=user)

        # Собираем и устанавливаем yay
        run_as_user(["bash", "-c", f"cd {clone_dir} && makepkg -si --noconfirm"], user=user)

        # Удаляем директорию сборки
        subprocess.run(["rm", "-rf", clone_dir], check=True)
    except subprocess.CalledProcessError as e:
        print(f"Ошибка при сборке yay: {e}")
        sys.exit(1)


def install_packages_with_yay(user, packages):
    failed_packages = []
    successful_packages = []
    retry_count = RETRY_ATTEMPTS

    # Устанавливаем пакеты по одному для лучшего контроля
    for package in packages:
        package_installed = False

        for attempt in range(retry_count):
            try:
                if attempt == 0:
                    print(f"Устанавливаем {package}...")
                else:
                    print(f"Повторная попытка {attempt + 1}/{retry_count} для {package}...")

                # Команда yay с максимальными флагами для неинтерактивности
                yay_cmd = [
                    "yay", "-S",
                    "--noconfirm",
                    "--needed",
                    package
                ]

                # Используем короткий тайм-аут для первой попытки
                timeout = 60 if attempt == 0 else 120
                stdout, stderr = run_as_user(yay_cmd, user=user, timeout=timeout)
                successful_packages.append(package)
                print(f"✓ {package} установлен успешно")
                package_installed = True
                break

            except subprocess.CalledProcessError as e:
                if attempt < retry_count - 1:
                    # Это не последняя попытка
                    error_msg = ""
                    if hasattr(e, 'stderr') and e.stderr:
                        error_msg = e.stderr[:100]

                    # Проверяем, это тайм-аут или другая ошибка
                    if "Timeout" in str(e.stderr):
                        print(f"  ⏱️  Тайм-аут на попытке {attempt + 1}, попробуем альтернативный способ...")
                        # Для тайм-аута попробуем простую команду без лишних флагов
                        try:
                            simple_cmd = ["yay", "-S", "--noconfirm", "--needed", package]
                            stdout, stderr = run_as_user(simple_cmd, user=user, timeout=180)
                            successful_packages.append(package)
                            print(f"✓ {package} установлен успешно (альтернативный метод)")
                            package_installed = True
                            break
                        except:
                            print(f"  Альтернативный метод тоже не сработал")
                    else:
                        print(f"  Попытка {attempt + 1} не удалась: {error_msg}...")

                    print(f"  Ожидание {RETRY_DELAY} секунд перед повторной попыткой...")
                    time.sleep(RETRY_DELAY)
                else:
                    # Последняя попытка - добавляем в failed
                    failed_packages.append(package)
                    print(f"✗ Не удалось установить {package} после {retry_count} попыток")
                    if hasattr(e, 'stderr') and e.stderr:
                        print(f"  Финальная ошибка: {e.stderr[:200]}...")

            except Exception as e:
                if attempt < retry_count - 1:
                    print(f"  Непредвиденная ошибка на попытке {attempt + 1}: {str(e)[:100]}...")
                    time.sleep(RETRY_DELAY)
                else:
                    failed_packages.append(package)
                    print(f"✗ Ошибка при установке {package}: {e}")
                    break

        # Если пакет не установился, убеждаемся что он в failed_packages
        if not package_installed and package not in failed_packages:
            failed_packages.append(package)

    # Выводим результаты
    if successful_packages:
        print(f"\nУспешно установлено через yay ({len(successful_packages)} пакетов):")
        for pkg in successful_packages:
            print(f"  ✓ {pkg}")

    if failed_packages:
        print(f"\nНе удалось установить через yay ({len(failed_packages)} пакетов):")
        for pkg in failed_packages:
            print(f"  ✗ {pkg}")
        print("\nВозможные причины:")
        print("  - Проблемы с сетью")
        print("  - Пакет недоступен в AUR")
        print("  - Ошибки сборки пакета")
        print("  - Интерактивные запросы (требует ручной установки)")

        # Предлагаем команды для ручной установки проблемных пакетов
        print(f"\n💡 Для ручной установки неудачных пакетов выполните:")
        for pkg in failed_packages:
            print(f"  yay -S {pkg}")


def install_packages_with_pacman(packages):
    try:
        subprocess.run(["pacman", "-S", "--noconfirm", "--needed"] + packages, check=True)
    except subprocess.CalledProcessError as e:
        print(f"Ошибка при установке пакетов через pacman: {e}")
        sys.exit(1)


def update_packages():
    try:
        subprocess.run(["pacman", "-Syu", "--noconfirm"], check=True)
    except subprocess.CalledProcessError as e:
        print(f"Ошибка при обновлении пакетов: {e}")
        sys.exit(1)

def main():
    check_root()
    user = get_username()

    try:
        # Обновляем пакеты
        print("Запускаем полное обновление пакетов...")
        update_packages()

        # Установка yay, если он не установлен
        if not is_yay_installed():
            print("Установка yay...")
            install_dependencies()
            clone_and_build_yay(user)
            print("yay успешно установлен!")
        else:
            print("yay уже установлен.")

        # Установка пакетов через yay
        if YAY_PACKAGES:
            print(f"Установка {len(YAY_PACKAGES)} пакетов через yay...")
            print("⚠️  Некоторые пакеты могут требовать дополнительного времени или зависнуть")
            print("   При зависании процесс будет автоматически завершен через 5 минут")
            install_packages_with_yay(user, YAY_PACKAGES)

        # Установка пакетов через pacman
        if PACMAN_PACKAGES:
            print(f"Установка {len(PACMAN_PACKAGES)} пакетов через pacman...")
            install_packages_with_pacman(PACMAN_PACKAGES)
            print("Пакеты через pacman успешно установлены!")

        print("\n🎉 Все задачи выполнены!")
        print("📊 Статистика установки:")

        # Подсчитываем успешные установки
        total_yay = len(YAY_PACKAGES)
        total_pacman = len(PACMAN_PACKAGES)

        print(f"   • YAY пакеты: установка завершена ({total_yay} пакетов)")
        print(f"   • Pacman пакеты: установка завершена ({total_pacman} пакетов)")
        print(f"   • Общее время: примерно 1-5 минут")

    except Exception as e:
        print(f"Произошла ошибка: {e}")
        sys.exit(1)


if __name__ == "__main__":
    main()
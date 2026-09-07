#!/usr/bin/env python3
"""
Автоматический установщик пакетов для Arch Linux
Устанавливает пакеты через paru (AUR и официальные репозитории).
Запускается с правами root через pkexec или sudo.

Возможности:
- Автоматическое определение непривилегированного пользователя (PKEXEC_UID / SUDO_USER)
- Автоматическая установка paru при его отсутствии
- Автоматическая обработка зависших процессов (тайм-аут 5 мин)
- Retry механизм для проблемных пакетов (3 попытки)
- Детальные отчеты об установке
- Продолжение работы при ошибках отдельных пакетов

Использование:
    pkexec python3 install.py
    # или
    sudo python3 install.py
"""

import contextlib
import glob
import os
import pwd
import shutil
import subprocess
import sys
import time
from pathlib import Path

# Настройки
RETRY_ATTEMPTS = 3      # Количество попыток для проблемных пакетов
RETRY_DELAY = 2         # Задержка между попытками в секундах
PROCESS_TIMEOUT = 300   # Максимальное время ожидания процесса в секундах (5 минут)

# Список пакетов для установки через paru (официальные репозитории + AUR)
PARU_PACKAGES = [
    # Браузеры и интернет
    'google-chrome',
    'chromium',
    'yandex-browser',
    'telegram-desktop',
    'transmission-qt',
    'v2raya-bin',

    # Разработка и терминал
    'cursor-bin',
    'visual-studio-code-bin',
    'antigravity-ide',
    'antigravity-cli',
    'pycharm-professional',
    'uv',
    'fastfetch',

    # Мультимедиа и досуг
    'yandex-music',
    'vlc',
    'steam',
    'portprotonqt',
    'aisleriot',
    'kmines',

    # Офис и заметки
    'obsidian',
    'onlyoffice-bin',

    # Система, утилиты и окружение
    'gnome-disk-utility',
    'samba',
    'samba-support',
    'pantum-driver',
    'gvfs-dnssd',
    'kvantum',
    'syncthing-bin',
]


def check_root() -> None:
    """Проверяет запуск с правами суперпользователя."""
    if os.geteuid() != 0:
        print("Этот скрипт требует прав суперпользователя. Запустите через pkexec или sudo.")
        sys.exit(1)


@contextlib.contextmanager
def temporary_pacman_nopasswd(username: str):
    """
    Временно предоставляет пользователю право запускать pacman через sudo без ввода пароля
    для беспрепятственной установки пакетов через paru/AUR.
    Гарантированно удаляет правило после завершения.
    """
    sudoers_file = Path("/etc/sudoers.d/99-auto-setup-paru")
    created = False
    try:
        content = f"{username} ALL=(ALL) NOPASSWD: /usr/bin/pacman\n"
        flags = os.O_WRONLY | os.O_CREAT | os.O_TRUNC
        fd = os.open(str(sudoers_file), flags, 0o440)
        with open(fd, "w", encoding="utf-8") as f:
            f.write(content)
        created = True

        check_res = subprocess.run(["visudo", "-cf", str(sudoers_file)], capture_output=True, text=True)
        if check_res.returncode != 0:
            raise RuntimeError(f"Ошибка валидации sudoers файла: {check_res.stderr.strip()}")

        yield
    finally:
        if created and sudoers_file.exists():
            try:
                sudoers_file.unlink()
            except OSError:
                pass


def run_as_user(
    user: str,
    cmd: list[str],
    cwd: str | Path | None = None,
    timeout: int | None = PROCESS_TIMEOUT,
    input_text: str | None = None
) -> tuple[str, str]:
    """
    Выполняет команду от имени обычного пользователя через sudo -u <user> -H.
    При запуске от root не запрашивает пароль.
    """
    if timeout is None:
        timeout = PROCESS_TIMEOUT

    full_cmd = ["sudo", "-u", user, "-H", "--"] + cmd

    process = subprocess.Popen(
        full_cmd,
        stdin=subprocess.PIPE if input_text is not None else None,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        text=True,
        cwd=str(cwd) if cwd else None
    )

    try:
        stdout, stderr = process.communicate(input=input_text, timeout=timeout)
    except subprocess.TimeoutExpired:
        print(f"⚠️  Команда превысила тайм-аут ({timeout}с): {' '.join(cmd)}")
        print("Принудительно завершаем процесс...")
        process.kill()
        try:
            stdout, stderr = process.communicate(timeout=5)
        except subprocess.TimeoutExpired:
            process.terminate()
            stdout, stderr = process.communicate()

        raise subprocess.CalledProcessError(-1, cmd, output=stdout, stderr=f"Timeout after {timeout}s")

    if process.returncode != 0:
        print(f"Ошибка выполнения команды: {' '.join(cmd)}")
        print(f"Return code: {process.returncode}")
        if stderr:
            print(f"STDERR: {stderr}")
        raise subprocess.CalledProcessError(process.returncode, cmd, output=stdout, stderr=stderr)

    return stdout, stderr


def get_username():
    user = os.getenv("SUDO_USER")
    if not user and os.getenv("PKEXEC_UID"):
        import pwd
        try:
            user = pwd.getpwuid(int(os.getenv("PKEXEC_UID"))).pw_name
        except Exception:
            pass
    if not user or user == "root":
        user = os.getenv("LOGNAME") or os.getenv("USER")
    if not user or user == "root":
        print("Не удалось определить обычного пользователя. Запустите скрипт через sudo или pkexec.")
        sys.exit(1)
    return user


def is_paru_installed():
    result = subprocess.run(["which", "paru"], capture_output=True)
    return result.returncode == 0


def install_dependencies():
    try:
        subprocess.run(["pacman", "-Syu", "--noconfirm"], check=True)
        subprocess.run(["pacman", "-S", "--noconfirm", "--needed", "git", "base-devel"], check=True)
    except subprocess.CalledProcessError as e:
        print(f"Ошибка при установке зависимостей: {e}")
        sys.exit(1)


def install_paru(user: str) -> None:
    """Устанавливает paru из официальных репозиториев (если есть) либо собирает paru-bin из AUR."""
    res = subprocess.run(["pacman", "-S", "--noconfirm", "--needed", "paru"], capture_output=True)
    if res.returncode == 0:
        print("paru успешно установлен через pacman!")
        return

    try:
        user_info = pwd.getpwnam(user)
        home_dir = Path(user_info.pw_dir)
    except KeyError:
        home_dir = Path(f"/home/{user}")

    clone_dir = home_dir / "paru-bin"
    try:
        if clone_dir.exists():
            shutil.rmtree(clone_dir, ignore_errors=True)

        print("Клонирование paru-bin из AUR...")
        run_as_user(user, ["git", "clone", "https://aur.archlinux.org/paru-bin.git", str(clone_dir)])

        print("Сборка paru-bin...")
        run_as_user(user, ["makepkg", "--noconfirm"], cwd=clone_dir)

        pkg_files = list(clone_dir.glob("*.pkg.tar.zst"))
        if not pkg_files:
            raise FileNotFoundError(f"Собранный пакет paru-bin не найден в {clone_dir}")

        print("Установка собранного пакета paru-bin через pacman...")
        subprocess.run(["pacman", "-U", "--noconfirm", str(pkg_files[0])], check=True)
        print("paru успешно собран и установлен!")
    except subprocess.CalledProcessError as e:
        print(f"Ошибка при установке paru: {e}")
        sys.exit(1)
    finally:
        if clone_dir.exists():
            shutil.rmtree(clone_dir, ignore_errors=True)


def install_packages_with_paru(user: str, packages: list[str]) -> None:
    """Устанавливает список пакетов через paru с временным предоставлением NOPASSWD для pacman."""
    failed_packages = []
    successful_packages = []
    retry_count = RETRY_ATTEMPTS

    with temporary_pacman_nopasswd(user):
        for package in packages:
            package_installed = False

            for attempt in range(retry_count):
                try:
                    if attempt == 0:
                        print(f"Устанавливаем {package}...")
                    else:
                        print(f"Повторная попытка {attempt + 1}/{retry_count} для {package}...")

                    # Команда paru с ключами для полной неинтерактивности
                    paru_cmd = [
                        "paru", "-S",
                        "--noconfirm",
                        "--needed",
                        "--skipreview",
                        package
                    ]

                    timeout = 60 if attempt == 0 else 120
                    stdout, stderr = run_as_user(user, paru_cmd, timeout=timeout)
                    successful_packages.append(package)
                    print(f"✓ {package} установлен успешно")
                    package_installed = True
                    break

                except subprocess.CalledProcessError as e:
                    if attempt < retry_count - 1:
                        error_msg = ""
                        if hasattr(e, 'stderr') and e.stderr:
                            error_msg = e.stderr[:100]

                        if "Timeout" in str(getattr(e, 'stderr', '')):
                            print(f"  ⏱️  Тайм-аут на попытке {attempt + 1}, пробуем повторить с увеличенным временем...")
                            try:
                                stdout, stderr = run_as_user(user, paru_cmd, timeout=180)
                                successful_packages.append(package)
                                print(f"✓ {package} установлен успешно")
                                package_installed = True
                                break
                            except Exception:
                                print("  Повторная попытка тоже завершилась ошибкой")
                        else:
                            print(f"  Попытка {attempt + 1} не удалась: {error_msg}...")

                        print(f"  Ожидание {RETRY_DELAY} секунд перед повторной попыткой...")
                        time.sleep(RETRY_DELAY)
                    else:
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

            if not package_installed and package not in failed_packages:
                failed_packages.append(package)

    # Выводим результаты
    if successful_packages:
        print(f"\nУспешно установлено через paru ({len(successful_packages)} пакетов):")
        for pkg in successful_packages:
            print(f"  ✓ {pkg}")

    if failed_packages:
        print(f"\nНе удалось установить через paru ({len(failed_packages)} пакетов):")
        for pkg in failed_packages:
            print(f"  ✗ {pkg}")
        print("\nВозможные причины:")
        print("  - Проблемы с сетью")
        print("  - Пакет недоступен в официальных репозиториях или AUR")
        print("  - Ошибки сборки пакета")
        print("  - Ошибки зависимостей")

        print("\n💡 Для ручной установки неудачных пакетов выполните:")
        for pkg in failed_packages:
            print(f"  paru -S {pkg}")


def update_system() -> None:
    """Обновляет базы пакетов и систему через pacman."""
    try:
        subprocess.run(["pacman", "-Syu", "--noconfirm"], check=True)
    except subprocess.CalledProcessError as e:
        print(f"Ошибка при обновлении системы: {e}")
        sys.exit(1)


# Алиасы для обратной совместимости
PACKAGES = PARU_PACKAGES
update_packages = update_system
install_packages = install_packages_with_paru


def main() -> None:
    """Точка входа автономного запуска install.py."""
    check_root()
    user = get_username()

    try:
        # Обновляем систему перед началом
        print("Запускаем обновление базы пакетов...")
        update_system()

        # Проверка и установка paru при необходимости
        if not is_paru_installed():
            print("paru не обнаружен. Установка paru...")
            install_dependencies()
            install_paru(user)
            print("paru успешно установлен!")
        else:
            print("paru уже установлен.")

        # Установка пакетов через paru
        if PARU_PACKAGES:
            print(f"Установка {len(PARU_PACKAGES)} пакетов через paru...")
            print("⚠️  Некоторые пакеты могут требовать дополнительного времени или компиляции")
            print("   При зависании процесс будет автоматически завершен через 5 минут")
            install_packages_with_paru(user, PARU_PACKAGES)

        print("\n🎉 Все задачи выполнены!")
        print("📊 Статистика установки:")
        print(f"   • Всего пакетов обработано: {len(PARU_PACKAGES)}")

    except subprocess.CalledProcessError as e:
        print(f"Ошибка при выполнении команды: {e}")
        sys.exit(1)
    except Exception as e:
        print(f"Произошла ошибка: {e}")
        sys.exit(1)


if __name__ == "__main__":
    main()
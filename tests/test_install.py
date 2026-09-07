#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Тесты для модуля code/install.py.
Все внешние вызовы (os, subprocess, pwd) замокированы для безопасного тестирования без root.
"""

import os
import subprocess
import sys
import unittest
from pathlib import Path
from unittest.mock import MagicMock, call, mock_open, patch

# Добавляем каталог code в sys.path
sys.path.insert(0, str(Path(__file__).parent.parent / "code"))

import install


class TestCheckRoot(unittest.TestCase):
    """Тестирование проверки прав суперпользователя."""

    @patch("os.geteuid", return_value=0)
    def test_check_root_success(self, mock_geteuid):
        try:
            install.check_root()
        except SystemExit:
            self.fail("check_root() вызвал SystemExit при euid == 0")

    @patch("os.geteuid", return_value=1000)
    @patch("builtins.print")
    def test_check_root_failure(self, mock_print, mock_geteuid):
        with self.assertRaises(SystemExit) as cm:
            install.check_root()
        self.assertEqual(cm.exception.code, 1)
        mock_print.assert_called_with(
            "Этот скрипт требует прав суперпользователя. Запустите через pkexec или sudo."
        )


class TestGetUsername(unittest.TestCase):
    """Тестирование определения реального пользователя (SUDO_USER / PKEXEC_UID / USER)."""

    def test_get_username_from_sudo_user(self):
        with patch.dict(os.environ, {"SUDO_USER": "archuser"}, clear=True):
            user = install.get_username()
            self.assertEqual(user, "archuser")

    @patch("pwd.getpwuid")
    def test_get_username_from_pkexec_uid(self, mock_getpwuid):
        mock_pw = MagicMock()
        mock_pw.pw_name = "pkexec_user"
        mock_getpwuid.return_value = mock_pw

        with patch.dict(os.environ, {"PKEXEC_UID": "1001"}, clear=True):
            user = install.get_username()
            self.assertEqual(user, "pkexec_user")
            mock_getpwuid.assert_called_once_with(1001)

    def test_get_username_from_env_user(self):
        with patch.dict(os.environ, {"USER": "regular_user"}, clear=True):
            user = install.get_username()
            self.assertEqual(user, "regular_user")

    @patch("builtins.print")
    def test_get_username_root_fails(self, mock_print):
        with patch.dict(os.environ, {"USER": "root", "SUDO_USER": "root"}, clear=True):
            with self.assertRaises(SystemExit) as cm:
                install.get_username()
            self.assertEqual(cm.exception.code, 1)


class TestRunAsUser(unittest.TestCase):
    """Тестирование безопасного выполнения команд от имени непривилегированного пользователя."""

    @patch("subprocess.Popen")
    def test_run_as_user_command_structure(self, mock_popen):
        mock_proc = MagicMock()
        mock_proc.communicate.return_value = ("output_ok", "")
        mock_proc.returncode = 0
        mock_popen.return_value = mock_proc

        stdout, stderr = install.run_as_user("testuser", ["whoami"])
        self.assertEqual(stdout, "output_ok")

        mock_popen.assert_called_once()
        cmd_args = mock_popen.call_args[0][0]
        self.assertEqual(cmd_args, ["sudo", "-u", "testuser", "-H", "--", "whoami"])

    @patch("subprocess.Popen")
    def test_run_as_user_called_process_error(self, mock_popen):
        mock_proc = MagicMock()
        mock_proc.communicate.return_value = ("", "command failed")
        mock_proc.returncode = 127
        mock_popen.return_value = mock_proc

        with self.assertRaises(subprocess.CalledProcessError) as cm:
            install.run_as_user("testuser", ["invalid_command"])
        self.assertEqual(cm.exception.returncode, 127)


class TestTemporaryPacmanNopasswd(unittest.TestCase):
    """Тестирование контекстного менеджера предоставления NOPASSWD для pacman."""

    @patch("subprocess.run")
    @patch("builtins.open", new_callable=mock_open)
    @patch("os.open", return_value=10)
    @patch("pathlib.Path.exists", return_value=True)
    @patch("pathlib.Path.unlink")
    def test_temporary_pacman_nopasswd_lifecycle(
        self, mock_unlink, mock_exists, mock_os_open, mock_file, mock_subproc
    ):
        mock_subproc.return_value = MagicMock(returncode=0)

        with install.temporary_pacman_nopasswd("testuser"):
            mock_subproc.assert_called_once_with(
                ["visudo", "-cf", "/etc/sudoers.d/99-auto-setup-paru"],
                capture_output=True,
                text=True,
            )

        mock_unlink.assert_called_once()


class TestInstallParu(unittest.TestCase):
    """Тестирование логики установки paru."""

    @patch("subprocess.run")
    def test_install_paru_via_pacman(self, mock_run):
        mock_run.return_value = MagicMock(returncode=0)
        install.install_paru("testuser")
        mock_run.assert_called_once_with(
            ["pacman", "-S", "--noconfirm", "--needed", "paru"],
            capture_output=True
        )

    @patch("pwd.getpwnam")
    @patch("install.run_as_user")
    @patch("pathlib.Path.glob")
    @patch("pathlib.Path.exists", return_value=False)
    @patch("subprocess.run")
    def test_install_paru_via_aur_build(
        self, mock_run, mock_exists, mock_glob, mock_run_as_user, mock_getpwnam
    ):
        # pacman -S paru возвращает 1
        pacman_res = MagicMock(returncode=1)
        mock_run.side_effect = [pacman_res, MagicMock(returncode=0)]

        mock_pw = MagicMock()
        mock_pw.pw_dir = "/home/testuser"
        mock_getpwnam.return_value = mock_pw

        pkg_mock = Path("/home/testuser/paru-bin/paru-bin-1.0-1-x86_64.pkg.tar.zst")
        mock_glob.return_value = [pkg_mock]

        install.install_paru("testuser")

        # Проверяем, что makepkg вызывается без флага -i
        mock_run_as_user.assert_any_call(
            "testuser",
            ["makepkg", "--noconfirm"],
            cwd=Path("/home/testuser/paru-bin")
        )
        # Проверяем, что установка пакета идет через pacman -U от root
        mock_run.assert_called_with(
            ["pacman", "-U", "--noconfirm", str(pkg_mock)],
            check=True
        )


class TestInstallPackagesWithParu(unittest.TestCase):
    """Тестирование пакетной установки через paru."""

    @patch("install.temporary_pacman_nopasswd")
    @patch("install.run_as_user")
    def test_install_packages_no_sudoflags(self, mock_run_as_user, mock_nopasswd):
        mock_nopasswd.return_value.__enter__.return_value = None
        mock_run_as_user.return_value = ("Success", "")

        install.install_packages_with_paru("testuser", ["fastfetch"])

        mock_run_as_user.assert_called_once()
        cmd = mock_run_as_user.call_args[0][1]
        self.assertEqual(cmd, ["paru", "-S", "--noconfirm", "--needed", "--skipreview", "fastfetch"])
        # Убеждаемся, что флагов --sudoflags и -S нет в команде
        self.assertNotIn("--sudoflags", cmd)


if __name__ == "__main__":
    unittest.main()

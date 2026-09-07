#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Тесты для модуля code/samba_auto_setup.py.
Все вызовы subprocess и файловой системы изолированы моками.
"""

import os
import subprocess
import sys
import unittest
from pathlib import Path
from unittest.mock import MagicMock, call, mock_open, patch

# Добавляем каталог code в sys.path
sys.path.insert(0, str(Path(__file__).parent.parent / "code"))

import samba_auto_setup


class TestSambaAutoSetup(unittest.TestCase):
    """Тестирование класса SambaAutoSetup."""

    def setUp(self):
        self.setup = samba_auto_setup.SambaAutoSetup(username="samba_user")

    def test_init_no_sudo_password_field(self):
        """Проверка отсутствия поля sudo_password и наличия username."""
        self.assertFalse(hasattr(self.setup, "sudo_password"))
        self.assertEqual(self.setup.username, "samba_user")

    @patch("subprocess.run")
    def test_run_command_direct_execution(self, mock_run):
        """Проверка прямого запуска команд без префикса sudo -S."""
        mock_run.return_value = MagicMock(returncode=0, stdout="ok", stderr="")

        res = self.setup.run_command("whoami")
        self.assertIsNotNone(res)

        mock_run.assert_called_once()
        cmd_args = mock_run.call_args[0][0]
        self.assertEqual(cmd_args, ["whoami"])
        self.assertNotIn("sudo", cmd_args)
        self.assertNotIn("-S", cmd_args)

    @patch("subprocess.run")
    def test_run_sudo_command_delegates_to_run_command(self, mock_run):
        """Проверка, что run_sudo_command является алиасом к run_command без sudo."""
        mock_run.return_value = MagicMock(returncode=0, stdout="ok", stderr="")

        self.setup.run_sudo_command(["systemctl", "start", "smb"])
        cmd_args = mock_run.call_args[0][0]
        self.assertEqual(cmd_args, ["systemctl", "start", "smb"])

    @patch.object(samba_auto_setup.SambaAutoSetup, "run_command")
    def test_step_1_set_permissions(self, mock_run_cmd):
        mock_run_cmd.return_value = MagicMock(returncode=0)

        success = self.setup.step_1_set_permissions()
        self.assertTrue(success)
        mock_run_cmd.assert_any_call("mkdir -p /var/lib/samba/usershares")
        mock_run_cmd.assert_any_call("chmod 1770 /var/lib/samba/usershares")

    @patch("pwd.getpwnam")
    @patch("os.replace")
    @patch("os.chmod")
    @patch("os.makedirs")
    @patch("builtins.open", new_callable=mock_open)
    @patch("os.path.exists", return_value=False)
    def test_step_2_configure_smb_atomic(
        self, mock_exists, mock_file, mock_makedirs, mock_chmod, mock_replace, mock_getpwnam
    ):
        mock_pw = MagicMock()
        mock_pw.pw_dir = "/home/samba_user"
        mock_getpwnam.return_value = mock_pw

        success = self.setup.step_2_configure_smb()
        self.assertTrue(success)

        # Проверяем безопасную атомарную замену конфига
        mock_replace.assert_called_once_with("/etc/samba/smb.conf.tmp", "/etc/samba/smb.conf")
        mock_chmod.assert_called_once_with("/etc/samba/smb.conf.tmp", 0o644)

        # Проверяем, что в конфиг попало имя пользователя и правильный путь
        written_content = "".join(call_args[0][0] for call_args in mock_file().write.call_args_list)
        self.assertIn("guest account = samba_user", written_content)
        self.assertIn("path = /home/samba_user/Загрузки/", written_content)

    @patch.object(samba_auto_setup.SambaAutoSetup, "run_command")
    def test_step_3_add_samba_user_with_env(self, mock_run_cmd):
        mock_run_cmd.return_value = MagicMock(returncode=0)

        with patch.dict(os.environ, {"SAMBA_PASSWORD": "secret_samba_pass"}, clear=True):
            success = self.setup.step_3_add_samba_user()
            self.assertTrue(success)

            mock_run_cmd.assert_called_once()
            call_args = mock_run_cmd.call_args
            self.assertEqual(call_args[0][0], "smbpasswd -a samba_user")
            # Проверяем input_text: только пароль Samba дважды, без пароля sudo!
            self.assertEqual(call_args[1]["input_text"], "secret_samba_pass\nsecret_samba_pass\n")

    @patch.object(samba_auto_setup.SambaAutoSetup, "run_command")
    def test_step_4_manage_services(self, mock_run_cmd):
        mock_run_cmd.return_value = MagicMock(returncode=0)

        success = self.setup.step_4_manage_services()
        self.assertTrue(success)

        for service in ["smb", "nmb"]:
            mock_run_cmd.assert_any_call(f"systemctl enable {service}")
            mock_run_cmd.assert_any_call(f"systemctl start {service}")
            mock_run_cmd.assert_any_call(f"systemctl restart {service}")

    @patch.object(samba_auto_setup.SambaAutoSetup, "run_command")
    def test_step_5_check_status_active(self, mock_run_cmd):
        mock_run_cmd.return_value = MagicMock(returncode=0, stdout="active")
        success = self.setup.step_5_check_status()
        self.assertTrue(success)

    @patch("pwd.getpwnam")
    @patch("os.path.exists", return_value=False)
    @patch.object(samba_auto_setup.SambaAutoSetup, "run_command")
    def test_create_directories(self, mock_run_cmd, mock_exists, mock_getpwnam):
        mock_pw = MagicMock()
        mock_pw.pw_dir = "/home/samba_user"
        mock_getpwnam.return_value = mock_pw
        mock_run_cmd.return_value = MagicMock(returncode=0)

        success = self.setup.create_directories()
        self.assertTrue(success)
        mock_run_cmd.assert_any_call("mkdir -p /home/samba_user/Загрузки")
        mock_run_cmd.assert_any_call("chown samba_user:samba_user /home/samba_user/Загрузки")
        mock_run_cmd.assert_any_call("mkdir -p /mnt/Home2")


if __name__ == "__main__":
    unittest.main()

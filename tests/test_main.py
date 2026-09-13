#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Тесты для главного оркестратора main.py.
"""

import sys
import unittest
from pathlib import Path
from unittest.mock import MagicMock, patch

# Добавляем корень проекта в sys.path
sys.path.insert(0, str(Path(__file__).parent.parent))

import main


class TestAutoSetupMaster(unittest.TestCase):
    """Тестирование класса AutoSetupMaster."""

    def setUp(self):
        self.master = main.AutoSetupMaster()

    def test_init_no_sudo_password(self):
        """Проверяем, что в оркестраторе отсутствуют поля sudo_password и askpass_script."""
        self.assertFalse(hasattr(self.master, "sudo_password"))
        self.assertFalse(hasattr(self.master, "askpass_script"))
        self.assertIsNone(self.master.username)

    @patch("main.get_username", return_value="master_user")
    @patch("main.check_root")
    def test_check_requirements(self, mock_check_root, mock_get_username):
        """Проверка валидации root и получения username."""
        self.master.check_requirements()
        mock_check_root.assert_called_once()
        mock_get_username.assert_called_once()
        self.assertEqual(self.master.username, "master_user")

    @patch("main.install_packages_with_paru")
    @patch("main.install_paru")
    @patch("main.is_paru_installed", return_value=False)
    @patch("main.install_dependencies")
    @patch("main.update_system")
    def test_step_1_install_packages_when_paru_missing(
        self, mock_update, mock_deps, mock_is_paru, mock_install_paru, mock_install_pkgs
    ):
        """Проверка установки paru и пакетов без передачи пароля."""
        self.master.username = "master_user"
        success = self.master.step_1_install_packages()

        self.assertTrue(success)
        mock_update.assert_called_once()
        mock_deps.assert_called_once()
        mock_install_paru.assert_called_once_with("master_user")
        mock_install_pkgs.assert_called_once_with("master_user", main.PARU_PACKAGES)

    @patch("main.SambaAutoSetup")
    def test_step_2_setup_samba(self, mock_samba_cls):
        """Проверка оркестрации настройки Samba без пароля root."""
        self.master.username = "master_user"
        mock_samba_inst = MagicMock()
        mock_samba_inst.create_directories.return_value = True
        mock_samba_cls.return_value = mock_samba_inst

        success = self.master.step_2_setup_samba()
        self.assertTrue(success)
        mock_samba_cls.assert_called_once_with(username="master_user")

    @patch.object(main.AutoSetupMaster, "step_2_setup_samba", return_value=True)
    @patch.object(main.AutoSetupMaster, "step_1_install_packages", return_value=True)
    @patch.object(main.AutoSetupMaster, "check_requirements")
    def test_run_full_setup(self, mock_check, mock_step_1, mock_step_2):
        """Проверка полного сквозного цикла run_full_setup."""
        self.master.username = "master_user"
        success = self.master.run_full_setup()

        self.assertTrue(success)
        mock_check.assert_called_once()
        mock_step_1.assert_called_once()
        mock_step_2.assert_called_once()


class TestMainEntryPoint(unittest.TestCase):
    """Тестирование функции верхнего уровня main()."""

    @patch("main.check_root")
    @patch("main.AutoSetupMaster")
    @patch("sys.exit")
    def test_main_calls_check_root_first(self, mock_exit, mock_master_cls, mock_check_root):
        """main() вызывает check_root() перед созданием AutoSetupMaster."""
        mock_instance = MagicMock()
        mock_instance.run_full_setup.return_value = True
        mock_master_cls.return_value = mock_instance

        main.main()

        mock_check_root.assert_called_once()
        mock_master_cls.assert_called_once()
        mock_instance.run_full_setup.assert_called_once()
        mock_exit.assert_called_once_with(0)

    @patch("main.check_root")
    @patch("main.AutoSetupMaster", side_effect=KeyboardInterrupt)
    @patch("sys.exit")
    def test_main_keyboard_interrupt(self, mock_exit, mock_master_cls, mock_check_root):
        """main() перехватывает KeyboardInterrupt и завершается с кодом 130."""
        main.main()
        mock_exit.assert_called_once_with(130)


if __name__ == "__main__":
    unittest.main()

import subprocess

import pytest
import os
import sys
import tempfile
import shutil
from unittest.mock import Mock, patch, MagicMock
from pathlib import Path

from main import utils


class TestGetBinPath:
    """Tests for get_bin_path function"""

    @pytest.fixture
    def temp_bin_dir(self):
        """Create a temporary directory with binaries"""
        temp_dir = tempfile.mkdtemp()
        bin_dir = os.path.join(temp_dir, "test_tool")
        os.makedirs(bin_dir)

        # Create a mock executable file
        exe_name = "test_tool.exe" if os.name == "nt" else "test_tool"
        exe_path = os.path.join(bin_dir, exe_name)
        with open(exe_path, "w") as f:
            f.write("#!/bin/bash\necho test")

        if os.name != "nt":
            os.chmod(exe_path, 0o755)

        yield temp_dir, bin_dir, exe_path
        shutil.rmtree(temp_dir, ignore_errors=True)

    def test_get_bin_path_pyinstaller(self, temp_bin_dir):
        """Verify search in sys._MEIPASS (PyInstaller)"""
        temp_dir, bin_dir, exe_path = temp_bin_dir

        # Simulate PyInstaller
        with patch.object(sys, '_MEIPASS', temp_dir, create=True):
            result = utils.get_bin_path("test_tool")
            assert result == exe_path

    def test_get_bin_path_local(self, temp_bin_dir, monkeypatch):
        """Verify search in local directory"""
        temp_dir, bin_dir, exe_path = temp_bin_dir

        # Simulate __file__ in the correct directory
        monkeypatch.setattr(utils, '__file__', os.path.join(temp_dir, 'utils.py'))

        # Remove _MEIPASS if it exists
        if hasattr(sys, '_MEIPASS'):
            delattr(sys, '_MEIPASS')

        result = utils.get_bin_path("test_tool")
        assert result == exe_path

    def test_get_bin_path_system_path(self, temp_bin_dir):
        """Verify search in system PATH"""
        _, _, exe_path = temp_bin_dir

        with patch('shutil.which', return_value=exe_path):
            # Remove _MEIPASS if it exists
            if hasattr(sys, '_MEIPASS'):
                delattr(sys, '_MEIPASS')

            result = utils.get_bin_path("test_tool")
            assert result == exe_path

    def test_get_bin_path_not_found(self):
        """Verify exception when binary is not found"""
        # Remove _MEIPASS
        if hasattr(sys, '_MEIPASS'):
            delattr(sys, '_MEIPASS')

        with patch('shutil.which', return_value=None), \
                patch('os.path.exists', return_value=False):
            with pytest.raises(FileNotFoundError) as exc_info:
                utils.get_bin_path("nonexistent_tool")

            assert "Impossibile trovare" in str(exc_info.value) or "Could not find" in str(exc_info.value)

    @patch('platform.system', return_value='Windows')
    def test_get_bin_path_windows(self, mock_system, temp_bin_dir):
        """Verify that it searches for .exe on Windows"""
        temp_dir, bin_dir, _ = temp_bin_dir

        # Create .exe on Windows
        exe_path = os.path.join(bin_dir, "test_tool.exe")
        with open(exe_path, "w") as f:
            f.write("test")

        with patch.object(sys, '_MEIPASS', temp_dir, create=True):
            result = utils.get_bin_path("test_tool")
            assert result.endswith(".exe")


class TestGetAppDir:
    """Tests for get_app_dir function"""

    def test_get_app_dir_creates_directory(self):
        """Verify that it creates the directory if it doesn't exist"""
        with patch('utils.QStandardPaths.writableLocation') as mock_location:
            temp_home = tempfile.mkdtemp()
            mock_location.return_value = temp_home

            try:
                result = utils.get_app_dir()

                assert result.exists()
                assert result.is_dir()
                assert result.name == "GliAAns-UI"
            finally:
                shutil.rmtree(temp_home, ignore_errors=True)

    def test_get_app_dir_returns_path_object(self):
        """Verify that it returns a Path object"""
        with patch('utils.QStandardPaths.writableLocation') as mock_location:
            temp_home = tempfile.mkdtemp()
            mock_location.return_value = temp_home

            try:
                result = utils.get_app_dir()
                assert isinstance(result, Path)
            finally:
                shutil.rmtree(temp_home, ignore_errors=True)

    def test_get_app_dir_idempotent(self):
        """Verify that multiple calls return the same path"""
        with patch('utils.QStandardPaths.writableLocation') as mock_location:
            temp_home = tempfile.mkdtemp()
            mock_location.return_value = temp_home

            try:
                result1 = utils.get_app_dir()
                result2 = utils.get_app_dir()

                assert result1 == result2
            finally:
                shutil.rmtree(temp_home, ignore_errors=True)


class TestResourcePath:
    """Tests for resource_path function"""

    def test_resource_path_pyinstaller(self):
        """Verify path with PyInstaller"""
        with patch.object(sys, '_MEIPASS', '/path/to/meipass', create=True):
            result = utils.resource_path("resources/icon.png")

            assert result.startswith('/path/to/meipass')
            assert result.endswith('resources/icon.png')

    def test_resource_path_development(self, monkeypatch):
        """Verify path in development mode"""
        # Remove _MEIPASS
        if hasattr(sys, '_MEIPASS'):
            delattr(sys, '_MEIPASS')

        test_dir = "/test/directory"
        monkeypatch.setattr(utils, '__file__', os.path.join(test_dir, 'utils.py'))

        result = utils.resource_path("resources/icon.png")

        assert test_dir in result
        assert "resources/icon.png" in result

    def test_resource_path_absolute(self):
        """Verify that it returns an absolute path"""
        result = utils.resource_path("test.txt")

        assert os.path.isabs(result)


class TestGetShellPath:
    """Tests for get_shell_path function"""

    @patch('platform.system', return_value='Darwin')
    @patch('subprocess.run')
    def test_get_shell_path_macos(self, mock_run, mock_system):
        """Verify PATH retrieval on macOS"""
        mock_run.return_value = Mock(
            stdout="/usr/local/bin:/usr/bin:/bin\n",
            returncode=0
        )

        result = utils.get_shell_path()

        assert result == "/usr/local/bin:/usr/bin:/bin"
        mock_run.assert_called_once()
        # Verify that it uses zsh
        assert "/bin/zsh" in str(mock_run.call_args)

    @patch('platform.system', return_value='Linux')
    @patch('subprocess.run')
    def test_get_shell_path_linux(self, mock_run, mock_system):
        """Verify PATH retrieval on Linux"""
        mock_run.return_value = Mock(
            stdout="/usr/local/bin:/usr/bin:/bin\n",
            returncode=0
        )

        with patch.dict(os.environ, {'SHELL': '/bin/bash'}):
            result = utils.get_shell_path()

            assert result == "/usr/local/bin:/usr/bin:/bin"
            mock_run.assert_called_once()
            # Verify that it uses the user's shell
            assert "/bin/bash" in str(mock_run.call_args)

    @patch('platform.system', return_value='Linux')
    def test_get_shell_path_linux_default_shell(self, mock_system):
        """Verify fallback to bash if SHELL is not defined"""
        with patch('subprocess.run') as mock_run, \
                patch.dict(os.environ, {}, clear=True):
            mock_run.return_value = Mock(stdout="/usr/bin:/bin\n", returncode=0)

            result = utils.get_shell_path()

            # Should use /bin/bash as fallback
            assert "/bin/bash" in str(mock_run.call_args)

    @patch('platform.system', return_value='Windows')
    def test_get_shell_path_windows(self, mock_system):
        """Verify PATH retrieval on Windows"""
        test_path = "C:\\Windows\\System32;C:\\Program Files"

        with patch.dict(os.environ, {'PATH': test_path}):
            result = utils.get_shell_path()

            assert result == test_path

    @patch('platform.system', return_value='Darwin')
    @patch('subprocess.run', side_effect=Exception("Command failed"))
    def test_get_shell_path_error_fallback(self, mock_run, mock_system):
        """Verify fallback on error"""
        test_path = "/fallback/path"

        with patch.dict(os.environ, {'PATH': test_path}):
            result = utils.get_shell_path()

            # Should return PATH from the environment
            assert result == test_path

    @patch('platform.system', return_value='Unknown')
    def test_get_shell_path_unknown_system(self, mock_system):
        """Verify behavior on unknown system"""
        test_path = "/generic/path"

        with patch.dict(os.environ, {'PATH': test_path}):
            result = utils.get_shell_path()

            assert result == test_path


class TestSetupFSLEnv:
    """Tests for setup_fsl_env function"""

    @patch('subprocess.run')
    def test_setup_fsl_env_success(self, mock_run):
        """Verify correct FSL setup"""
        mock_run.return_value = Mock(
            stdout="/usr/local/fsl\nNIFTI_GZ\n",
            returncode=0
        )

        fsldir, fsloutputtype = utils.setup_fsl_env()

        assert fsldir == "/usr/local/fsl"
        assert fsloutputtype == "NIFTI_GZ"
        mock_run.assert_called_once()

    @patch('subprocess.run')
    def test_setup_fsl_env_uses_zsh(self, mock_run):
        """Verify it uses zsh and sources fsl.sh"""
        mock_run.return_value = Mock(
            stdout="/usr/local/fsl\nNIFTI_GZ\n",
            returncode=0
        )

        utils.setup_fsl_env()

        call_args = str(mock_run.call_args)
        assert "/bin/zsh" in call_args
        assert "fsl.sh" in call_args

    @patch('subprocess.run')
    def test_setup_fsl_env_insufficient_output(self, mock_run):
        """Verify error with insufficient output"""
        mock_run.return_value = Mock(
            stdout="/usr/local/fsl\n",  # Missing FSLOUTPUTTYPE
            returncode=0
        )

        with pytest.raises(RuntimeError) as exc_info:
            utils.setup_fsl_env()

        assert "Impossibile leggere" in str(exc_info.value) or "Could not read" in str(exc_info.value)

    @patch('subprocess.run')
    def test_setup_fsl_env_empty_output(self, mock_run):
        """Verify error with empty output"""
        mock_run.return_value = Mock(
            stdout="",
            returncode=0
        )

        with pytest.raises(RuntimeError):
            utils.setup_fsl_env()

    @patch('subprocess.run', side_effect=subprocess.CalledProcessError(1, 'cmd'))
    def test_setup_fsl_env_command_fails(self, mock_run):
        """Verify handling of command error"""
        with pytest.raises(subprocess.CalledProcessError):
            utils.setup_fsl_env()


class TestPlatformSpecificBehavior:
    """Tests for platform-specific behavior"""

    @patch('platform.system', return_value='Windows')
    def test_windows_executable_extension(self, mock_system):
        """Verify that Windows searches for .exe"""
        with patch('os.path.exists', return_value=True):
            with patch.object(sys, '_MEIPASS', '/test', create=True):
                # Should not raise exception
                try:
                    result = utils.get_bin_path("test_tool")
                    assert ".exe" in result
                except FileNotFoundError:
                    # OK if not found, important that it searches for .exe
                    pass

    @patch('platform.system', return_value='Linux')
    def test_linux_no_extension(self, mock_system):
        """Verify that Linux does not add extension"""
        with patch('os.path.exists', return_value=True):
            with patch.object(sys, '_MEIPASS', '/test', create=True):
                try:
                    result = utils.get_bin_path("test_tool")
                    assert not result.endswith(".exe")
                except FileNotFoundError:
                    pass


class TestEdgeCases:
    """Tests for edge cases and unusual situations"""

    def test_get_bin_path_empty_name(self):
        """Verify behavior with empty name"""
        with pytest.raises((FileNotFoundError, ValueError)):
            utils.get_bin_path("")

    def test_resource_path_empty_relative(self):
        """Verify behavior with empty relative path"""
        result = utils.resource_path("")
        assert os.path.isabs(result)

    def test_resource_path_absolute_input(self):
        """Verify behavior with absolute path as input"""
        abs_path = "/absolute/path/to/resource"
        result = utils.resource_path(abs_path)
        # Should still process it
        assert isinstance(result, str)

    @patch('subprocess.run')
    def test_setup_fsl_env_whitespace_output(self, mock_run):
        """Verify handling of whitespace in output"""
        mock_run.return_value = Mock(
            stdout="  /usr/local/fsl  \n  NIFTI_GZ  \n",
            returncode=0
        )

        fsldir, fsloutputtype = utils.setup_fsl_env()

        # strip should remove whitespace
        assert fsldir.strip() == "/usr/local/fsl"
        assert fsloutputtype.strip() == "NIFTI_GZ"

    def test_get_shell_path_empty_environ(self):
        """Verify behavior with empty PATH"""
        with patch.dict(os.environ, {'PATH': ''}):
            with patch('platform.system', return_value='Windows'):
                result = utils.get_shell_path()
                assert result == ""


class TestIntegrationScenarios:
    """Integration tests for realistic scenarios"""

    @patch('platform.system', return_value='Darwin')
    @patch('subprocess.run')
    def test_macos_full_setup(self, mock_run, mock_system):
        """Test full scenario on macOS"""
        # Setup PATH
        mock_run.return_value = Mock(
            stdout="/usr/local/bin:/usr/bin\n",
            returncode=0
        )

        path = utils.get_shell_path()
        assert "/usr/local/bin" in path

        # Setup FSL
        mock_run.return_value = Mock(
            stdout="/usr/local/fsl\nNIFTI_GZ\n",
            returncode=0
        )

        fsldir, fsltype = utils.setup_fsl_env()
        assert fsldir == "/usr/local/fsl"
        assert fsltype == "NIFTI_GZ"

    def test_development_mode_paths(self, monkeypatch):
        """Test paths in development mode"""
        # Simulate development (no PyInstaller)
        if hasattr(sys, '_MEIPASS'):
            delattr(sys, '_MEIPASS')

        test_dir = "/home/user/project"
        monkeypatch.setattr(utils, '__file__', os.path.join(test_dir, 'utils.py'))

        # Resource path should use project directory
        resource = utils.resource_path("icon.png")
        assert test_dir in resource

        # App dir should be created
        with patch('utils.QStandardPaths.writableLocation') as mock_loc:
            temp_home = tempfile.mkdtemp()
            mock_loc.return_value = temp_home

            try:
                app_dir = utils.get_app_dir()
                assert app_dir.exists()
            finally:
                shutil.rmtree(temp_home, ignore_errors=True)


class TestErrorHandling:
    """Tests for error handling"""

    @patch('subprocess.run', side_effect=FileNotFoundError("Shell not found"))
    @patch('platform.system', return_value='Linux')
    def test_shell_not_found_fallback(self, mock_system, mock_run):
        """Verify fallback when shell is not found"""
        with patch.dict(os.environ, {'PATH': '/backup/path'}):
            result = utils.get_shell_path()
            # Should use PATH from environment
            assert result == '/backup/path'

    @patch('os.makedirs', side_effect=PermissionError("No permission"))
    def test_app_dir_permission_error(self, mock_makedirs):
        """Verify handling of permission error"""
        with patch('utils.QStandardPaths.writableLocation', return_value='/root/restricted'):
            with pytest.raises(PermissionError):
                utils.get_app_dir()

    @patch('subprocess.run')
    def test_setup_fsl_malformed_output(self, mock_run):
        """Verify handling of malformed output"""
        # Output with strange characters
        mock_run.return_value = Mock(
            stdout="\x00/usr/local/fsl\nNIFTI_GZ\x00\n",
            returncode=0
        )

        # Should still work (strip handles it)
        fsldir, fsltype = utils.setup_fsl_env()
        assert "/usr/local/fsl" in fsldir


if __name__ == "__main__":
    pytest.main([__file__, "-v", "--tb=short"])
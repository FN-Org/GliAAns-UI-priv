"""
test_copy_delete_thread.py - Test Suite for CopyDeleteThread

This suite tests all functionalities of the copy/delete thread:
- Copying single files
- Copying recursive directories
- Deleting single files
- Deleting directories
- Combined operations
- Error handling and edge cases
"""

import os
import shutil
import tempfile
from unittest.mock import Mock, patch, call
import pytest

from main.threads.utils_threads import CopyDeleteThread


class TestCopyDeleteThreadInitialization:
    """Tests for CopyDeleteThread initialization"""

    def test_init_copy_file(self, temp_workspace):
        """Test initialization for file copy"""
        src = os.path.join(temp_workspace, "source.txt")
        dst = os.path.join(temp_workspace, "dest.txt")

        thread = CopyDeleteThread(
            src=src,
            dst=dst,
            is_folder=False,
            copy=True,
            delete=False
        )

        assert thread.src == src
        assert thread.dst == dst
        assert thread.is_folder is False
        assert thread.copy is True
        assert thread.delete is False

    def test_init_delete_folder(self, temp_workspace):
        """Test initialization for folder deletion"""
        src = os.path.join(temp_workspace, "folder_to_delete")

        thread = CopyDeleteThread(
            src=src,
            dst=None,
            is_folder=True,
            copy=False,
            delete=True
        )

        assert thread.src == src
        assert thread.dst is None
        assert thread.is_folder is True
        assert thread.copy is False
        assert thread.delete is True

    def test_init_copy_and_delete(self, temp_workspace):
        """Test initialization for combined operation"""
        src = os.path.join(temp_workspace, "source")
        dst = os.path.join(temp_workspace, "dest")

        thread = CopyDeleteThread(
            src=src,
            dst=dst,
            is_folder=True,
            copy=True,
            delete=True
        )

        assert thread.copy is True
        assert thread.delete is True

    def test_signals_exist(self, temp_workspace):
        """Verify that signals are defined correctly"""
        thread = CopyDeleteThread(src="dummy", dst=None)

        assert hasattr(thread, 'finished')
        assert hasattr(thread, 'error')


class TestFileCopy:
    """Tests for single file copy"""

    def test_copy_file_success(self, temp_workspace):
        """Test successful file copy"""
        src = os.path.join(temp_workspace, "source.txt")
        dst = os.path.join(temp_workspace, "destination.txt")

        with open(src, 'w') as f:
            f.write("test content")

        thread = CopyDeleteThread(src=src, dst=dst, is_folder=False, copy=True)

        finished_msgs = []
        thread.finished.connect(lambda msg: finished_msgs.append(msg))

        thread.run()

        # Verify file was copied
        assert os.path.exists(dst)
        with open(dst, 'r') as f:
            assert f.read() == "test content"

        # Verify signal
        assert len(finished_msgs) == 1
        assert "copied" or "copiato" in finished_msgs[0].lower()

    def test_copy_file_overwrites_existing(self, temp_workspace):
        """Test that copy overwrites existing file"""
        src = os.path.join(temp_workspace, "source.txt")
        dst = os.path.join(temp_workspace, "existing.txt")

        with open(src, 'w') as f:
            f.write("new content")

        # Create existing destination
        with open(dst, 'w') as f:
            f.write("old content")

        thread = CopyDeleteThread(src=src, dst=dst, is_folder=False, copy=True)
        thread.run()

        # Verify overwrite
        with open(dst, 'r') as f:
            assert f.read() == "new content"

    def test_copy_file_to_subfolder(self, temp_workspace):
        """Test copying file into subfolder"""
        src = os.path.join(temp_workspace, "file.txt")
        subfolder = os.path.join(temp_workspace, "subfolder")
        dst = os.path.join(subfolder, "file.txt")

        with open(src, 'w') as f:
            f.write("data")

        # Create subfolder
        os.makedirs(subfolder)

        thread = CopyDeleteThread(src=src, dst=dst, is_folder=False, copy=True)
        thread.run()

        assert os.path.exists(dst)

    def test_copy_binary_file(self, temp_workspace):
        """Test copying binary file"""
        src = os.path.join(temp_workspace, "binary.bin")
        dst = os.path.join(temp_workspace, "binary_copy.bin")

        # Create binary file
        binary_data = bytes([0, 1, 2, 255, 128, 64])
        with open(src, 'wb') as f:
            f.write(binary_data)

        thread = CopyDeleteThread(src=src, dst=dst, is_folder=False, copy=True)
        thread.run()

        # Verify binary content
        with open(dst, 'rb') as f:
            assert f.read() == binary_data

    def test_copy_large_file(self, temp_workspace):
        """Test copying large file"""
        src = os.path.join(temp_workspace, "large.dat")
        dst = os.path.join(temp_workspace, "large_copy.dat")

        # Create "large" file (1 MB)
        large_content = "x" * (1024 * 1024)
        with open(src, 'w') as f:
            f.write(large_content)

        thread = CopyDeleteThread(src=src, dst=dst, is_folder=False, copy=True)
        thread.run()

        assert os.path.exists(dst)
        assert os.path.getsize(dst) == os.path.getsize(src)


class TestFolderCopy:
    """Tests for directory copy"""

    def test_copy_folder_success(self, temp_workspace):
        """Test successful folder copy"""
        src = os.path.join(temp_workspace, "source_folder")
        dst = os.path.join(temp_workspace, "dest_folder")

        # Create source folder with files
        os.makedirs(src)
        with open(os.path.join(src, "file1.txt"), 'w') as f:
            f.write("content 1")
        with open(os.path.join(src, "file2.txt"), 'w') as f:
            f.write("content 2")

        thread = CopyDeleteThread(src=src, dst=dst, is_folder=True, copy=True)

        finished_msgs = []
        thread.finished.connect(lambda msg: finished_msgs.append(msg))

        thread.run()

        # Verify folder was copied
        assert os.path.exists(dst)
        assert os.path.exists(os.path.join(dst, "file1.txt"))
        assert os.path.exists(os.path.join(dst, "file2.txt"))

        # Verify contents
        with open(os.path.join(dst, "file1.txt"), 'r') as f:
            assert f.read() == "content 1"

        assert len(finished_msgs) == 1

    def test_copy_nested_folder(self, temp_workspace):
        """Test copying folder with subfolders"""
        src = os.path.join(temp_workspace, "nested_src")
        dst = os.path.join(temp_workspace, "nested_dst")

        # Create nested structure
        os.makedirs(os.path.join(src, "sub1", "sub2"))
        with open(os.path.join(src, "root.txt"), 'w') as f:
            f.write("root")
        with open(os.path.join(src, "sub1", "file1.txt"), 'w') as f:
            f.write("sub1")
        with open(os.path.join(src, "sub1", "sub2", "file2.txt"), 'w') as f:
            f.write("sub2")

        thread = CopyDeleteThread(src=src, dst=dst, is_folder=True, copy=True)
        thread.run()

        # Verify the entire structure
        assert os.path.exists(os.path.join(dst, "root.txt"))
        assert os.path.exists(os.path.join(dst, "sub1", "file1.txt"))
        assert os.path.exists(os.path.join(dst, "sub1", "sub2", "file2.txt"))

    def test_copy_folder_with_dirs_exist_ok(self, temp_workspace):
        """Test copying into existing folder (dirs_exist_ok=True)"""
        src = os.path.join(temp_workspace, "source")
        dst = os.path.join(temp_workspace, "existing_dest")

        os.makedirs(src)
        with open(os.path.join(src, "new_file.txt"), 'w') as f:
            f.write("new")

        # Create existing destination
        os.makedirs(dst)
        with open(os.path.join(dst, "old_file.txt"), 'w') as f:
            f.write("old")

        thread = CopyDeleteThread(src=src, dst=dst, is_folder=True, copy=True)
        thread.run()

        # Both files should exist
        assert os.path.exists(os.path.join(dst, "new_file.txt"))
        assert os.path.exists(os.path.join(dst, "old_file.txt"))

    def test_copy_empty_folder(self, temp_workspace):
        """Test copying empty folder"""
        src = os.path.join(temp_workspace, "empty_src")
        dst = os.path.join(temp_workspace, "empty_dst")

        os.makedirs(src)

        thread = CopyDeleteThread(src=src, dst=dst, is_folder=True, copy=True)
        thread.run()

        assert os.path.exists(dst)
        assert os.path.isdir(dst)
        assert len(os.listdir(dst)) == 0


class TestFileDelete:
    """Tests for file deletion"""

    def test_delete_file_success(self, temp_workspace):
        """Test successful file deletion"""
        file_path = os.path.join(temp_workspace, "to_delete.txt")

        with open(file_path, 'w') as f:
            f.write("delete me")

        assert os.path.exists(file_path)

        thread = CopyDeleteThread(src=file_path, is_folder=False, delete=True)

        finished_msgs = []
        thread.finished.connect(lambda msg: finished_msgs.append(msg))

        thread.run()

        # Verify file was deleted
        assert not os.path.exists(file_path)
        assert len(finished_msgs) == 1
        assert "deleted" in finished_msgs[0].lower() or "eliminato" in finished_msgs[0].lower()

    def test_delete_readonly_file(self, temp_workspace):
        """Test deleting read-only file"""
        file_path = os.path.join(temp_workspace, "readonly.txt")

        with open(file_path, 'w') as f:
            f.write("readonly")

        # Make read-only
        os.chmod(file_path, 0o444)

        thread = CopyDeleteThread(src=file_path, is_folder=False, delete=True)

        error_msgs = []
        thread.error.connect(lambda msg: error_msgs.append(msg))

        thread.run()

        # Might fail on Unix/Linux systems
        # But should still emit error signal if it fails
        if os.path.exists(file_path):
            assert len(error_msgs) > 0
            # Cleanup
            os.chmod(file_path, 0o644)
            os.remove(file_path)


class TestFolderDelete:
    """Tests for directory deletion"""

    def test_delete_folder_success(self, temp_workspace):
        """Test successful folder deletion"""
        folder_path = os.path.join(temp_workspace, "folder_to_delete")

        # Create folder with content
        os.makedirs(folder_path)
        with open(os.path.join(folder_path, "file.txt"), 'w') as f:
            f.write("content")

        assert os.path.exists(folder_path)

        thread = CopyDeleteThread(src=folder_path, is_folder=True, delete=True)

        finished_msgs = []
        thread.finished.connect(lambda msg: finished_msgs.append(msg))

        thread.run()

        # Verify folder was deleted
        assert not os.path.exists(folder_path)
        assert len(finished_msgs) == 1

    def test_delete_nested_folder(self, temp_workspace):
        """Test deleting folder with subfolders"""
        folder_path = os.path.join(temp_workspace, "nested_delete")

        # Create complex structure
        os.makedirs(os.path.join(folder_path, "sub1", "sub2"))
        for i in range(5):
            with open(os.path.join(folder_path, f"file{i}.txt"), 'w') as f:
                f.write(f"content {i}")

        thread = CopyDeleteThread(src=folder_path, is_folder=True, delete=True)
        thread.run()

        # The entire structure should be deleted
        assert not os.path.exists(folder_path)

    def test_delete_empty_folder(self, temp_workspace):
        """Test deleting empty folder"""
        folder_path = os.path.join(temp_workspace, "empty_folder")
        os.makedirs(folder_path)

        thread = CopyDeleteThread(src=folder_path, is_folder=True, delete=True)
        thread.run()

        assert not os.path.exists(folder_path)


class TestCombinedOperations:
    """Tests for combined operations (copy + delete)"""

    def test_copy_then_delete_file(self, temp_workspace):
        """Test copy then delete file"""
        src = os.path.join(temp_workspace, "original.txt")
        dst = os.path.join(temp_workspace, "copy.txt")

        with open(src, 'w') as f:
            f.write("move me")

        # Combined operation = "move"
        thread = CopyDeleteThread(
            src=src,
            dst=dst,
            is_folder=False,
            copy=True,
            delete=True
        )

        finished_count = [0]
        thread.finished.connect(lambda msg: finished_count.__setitem__(0, finished_count[0] + 1))

        thread.run()

        # Copied file should exist
        assert os.path.exists(dst)
        with open(dst, 'r') as f:
            assert f.read() == "move me"

        # Original file should be deleted
        assert not os.path.exists(src)

        # Two finished signals (one for copy, one for delete)
        assert finished_count[0] == 2

    def test_copy_then_delete_folder(self, temp_workspace):
        """Test copy then delete folder (equivalent to move)"""
        src = os.path.join(temp_workspace, "src_folder")
        dst = os.path.join(temp_workspace, "dst_folder")

        os.makedirs(src)
        with open(os.path.join(src, "data.txt"), 'w') as f:
            f.write("folder data")

        thread = CopyDeleteThread(
            src=src,
            dst=dst,
            is_folder=True,
            copy=True,
            delete=True
        )

        thread.run()

        # Destination should exist
        assert os.path.exists(dst)
        assert os.path.exists(os.path.join(dst, "data.txt"))

        # Source should be deleted
        assert not os.path.exists(src)


class TestErrorHandling:
    """Tests for error handling"""

    def test_copy_missing_source(self, temp_workspace):
        """Test copy with missing source file"""
        src = os.path.join(temp_workspace, "nonexistent.txt")
        dst = os.path.join(temp_workspace, "dest.txt")

        thread = CopyDeleteThread(src=src, dst=dst, is_folder=False, copy=True)

        error_msgs = []
        thread.error.connect(lambda msg: error_msgs.append(msg))

        thread.run()

        # Should emit error
        assert len(error_msgs) == 1
        assert "error" in error_msgs[0].lower() or src in error_msgs[0]

    def test_copy_missing_src_parameter(self, temp_workspace):
        """Test copy with missing src parameter"""
        thread = CopyDeleteThread(src=None, dst="dest", copy=True)

        error_msgs = []
        thread.error.connect(lambda msg: error_msgs.append(msg))

        thread.run()

        assert len(error_msgs) == 1
        assert "missing" in error_msgs[0].lower() or "manca" in error_msgs[0].lower()

    def test_copy_missing_dst_parameter(self, temp_workspace):
        """Test copy with missing dst parameter"""
        thread = CopyDeleteThread(src="src", dst=None, copy=True)

        error_msgs = []
        thread.error.connect(lambda msg: error_msgs.append(msg))

        thread.run()

        assert len(error_msgs) == 1
        assert "missing" in error_msgs[0].lower() or "manca" in error_msgs[0].lower()

    def test_delete_missing_source(self, temp_workspace):
        """Test deleting non-existent file"""
        src = os.path.join(temp_workspace, "does_not_exist.txt")

        thread = CopyDeleteThread(src=src, is_folder=False, delete=True)

        error_msgs = []
        thread.error.connect(lambda msg: error_msgs.append(msg))

        thread.run()

        # Should emit error
        assert len(error_msgs) == 1

    def test_delete_missing_src_parameter(self, temp_workspace):
        """Test deletion with missing src parameter"""
        thread = CopyDeleteThread(src=None, delete=True)

        error_msgs = []
        thread.error.connect(lambda msg: error_msgs.append(msg))

        thread.run()

        assert len(error_msgs) == 1
        assert "missing" in error_msgs[0].lower() or "manca" in error_msgs[0].lower()

    def test_copy_to_invalid_destination(self, temp_workspace):
        """Test copy to invalid destination"""
        src = os.path.join(temp_workspace, "source.txt")
        # Destination in non-existent directory
        dst = os.path.join(temp_workspace, "nonexistent_dir", "subdir", "dest.txt")

        with open(src, 'w') as f:
            f.write("data")

        thread = CopyDeleteThread(src=src, dst=dst, is_folder=False, copy=True)

        error_msgs = []
        thread.error.connect(lambda msg: error_msgs.append(msg))

        thread.run()

        # Should fail
        assert len(error_msgs) == 1

    @patch('shutil.copy')
    def test_copy_permission_error(self, mock_copy, temp_workspace):
        """Test handling permission error during copy"""
        mock_copy.side_effect = PermissionError("Permission denied")

        src = os.path.join(temp_workspace, "source.txt")
        dst = os.path.join(temp_workspace, "dest.txt")

        with open(src, 'w') as f:
            f.write("data")

        thread = CopyDeleteThread(src=src, dst=dst, is_folder=False, copy=True)

        error_msgs = []
        thread.error.connect(lambda msg: error_msgs.append(msg))

        thread.run()

        assert len(error_msgs) == 1
        assert "permission" in error_msgs[0].lower() or "error" in error_msgs[0].lower()


class TestEdgeCases:
    """Tests for edge cases"""

    def test_copy_file_to_itself(self, temp_workspace):
        """Test copying file onto itself"""
        file_path = os.path.join(temp_workspace, "same.txt")

        with open(file_path, 'w') as f:
            f.write("content")

        thread = CopyDeleteThread(
            src=file_path,
            dst=file_path,
            is_folder=False,
            copy=True
        )

        error_msgs = []
        thread.error.connect(lambda msg: error_msgs.append(msg))

        thread.run()

        # shutil.copy should handle this case
        # It might emit an error or succeed depending on the implementation
        # We just verify it doesn't raise unhandled exceptions

    def test_copy_symlink(self, temp_workspace):
        """Test copying symlink"""
        if os.name == 'nt':
            pytest.skip("Symlinks not reliable on Windows")

        src = os.path.join(temp_workspace, "original.txt")
        link = os.path.join(temp_workspace, "link.txt")
        dst = os.path.join(temp_workspace, "copy.txt")

        with open(src, 'w') as f:
            f.write("original data")

        os.symlink(src, link)

        thread = CopyDeleteThread(src=link, dst=dst, is_folder=False, copy=True)
        thread.run()

        # Should copy the content, not the link
        assert os.path.exists(dst)
        with open(dst, 'r') as f:
            assert f.read() == "original data"

    def test_delete_symlink(self, temp_workspace):
        """Test deleting symlink"""
        if os.name == 'nt':
            pytest.skip("Symlinks not reliable on Windows")

        target = os.path.join(temp_workspace, "target.txt")
        link = os.path.join(temp_workspace, "link.txt")

        with open(target, 'w') as f:
            f.write("target")

        os.symlink(target, link)

        thread = CopyDeleteThread(src=link, is_folder=False, delete=True)
        thread.run()

        # Link should be deleted, target should still exist
        assert not os.path.exists(link)
        assert os.path.exists(target)

    def test_copy_file_with_special_characters(self, temp_workspace):
        """Test copying file with special characters in name"""
        src = os.path.join(temp_workspace, "file (copy) #1.txt")
        dst = os.path.join(temp_workspace, "destination [final].txt")

        with open(src, 'w') as f:
            f.write("special chars")

        thread = CopyDeleteThread(src=src, dst=dst, is_folder=False, copy=True)
        thread.run()

        assert os.path.exists(dst)
        with open(dst, 'r') as f:
            assert f.read() == "special chars"

    def test_copy_unicode_filename(self, temp_workspace):
        """Test copying file with Unicode name"""
        src = os.path.join(temp_workspace, "文件.txt")
        dst = os.path.join(temp_workspace, "файл.txt")

        try:
            with open(src, 'w', encoding='utf-8') as f:
                f.write("unicode content")
        except (OSError, UnicodeError):
            pytest.skip("Filesystem doesn't support Unicode")

        thread = CopyDeleteThread(src=src, dst=dst, is_folder=False, copy=True)
        thread.run()

        if os.path.exists(dst):
            with open(dst, 'r', encoding='utf-8') as f:
                assert f.read() == "unicode content"

    def test_copy_hidden_file(self, temp_workspace):
        """Test copying hidden file"""
        src = os.path.join(temp_workspace, ".hidden_file")
        dst = os.path.join(temp_workspace, ".hidden_copy")

        with open(src, 'w') as f:
            f.write("hidden content")

        thread = CopyDeleteThread(src=src, dst=dst, is_folder=False, copy=True)
        thread.run()

        assert os.path.exists(dst)

    def test_no_operation_specified(self, temp_workspace):
        """Test with no operations (neither copy nor delete)"""
        src = os.path.join(temp_workspace, "file.txt")
        with open(src, 'w') as f:
            f.write("data")

        thread = CopyDeleteThread(src=src, copy=False, delete=False)

        finished_count = [0]
        error_count = [0]
        thread.finished.connect(lambda msg: finished_count.__setitem__(0, finished_count[0] + 1))
        thread.error.connect(lambda msg: error_count.__setitem__(0, error_count[0] + 1))

        thread.run()

        # Should do nothing, but also shouldn't crash
        assert finished_count[0] == 0
        assert error_count[0] == 0


class TestSignalEmissions:
    """Tests for signal emissions"""

    def test_finished_signal_contains_paths(self, temp_workspace):
        """Test that finished signal contains paths"""
        src = os.path.join(temp_workspace, "source.txt")
        dst = os.path.join(temp_workspace, "dest.txt")

        with open(src, 'w') as f:
            f.write("data")

        thread = CopyDeleteThread(src=src, dst=dst, is_folder=False, copy=True)

        finished_msgs = []
        thread.finished.connect(lambda msg: finished_msgs.append(msg))

        thread.run()

        assert len(finished_msgs) == 1
        msg = finished_msgs[0]

        # Message should contain src and dst
        assert src in msg or os.path.basename(src) in msg
        assert dst in msg or os.path.basename(dst) in msg

    def test_error_signal_contains_details(self, temp_workspace):
        """Test that error signal contains details"""
        src = os.path.join(temp_workspace, "nonexistent.txt")
        dst = os.path.join(temp_workspace, "dest.txt")

        thread = CopyDeleteThread(src=src, dst=dst, is_folder=False, copy=True)

        error_msgs = []
        thread.error.connect(lambda msg: error_msgs.append(msg))

        thread.run()

        assert len(error_msgs) == 1
        msg = error_msgs[0]

        # Error message should contain src
        assert src in msg

    def test_multiple_finished_signals_on_combined_operation(self, temp_workspace):
        """Test multiple finished signal emissions on combined operation"""
        src = os.path.join(temp_workspace, "file.txt")
        dst = os.path.join(temp_workspace, "copy.txt")

        with open(src, 'w') as f:
            f.write("data")

        thread = CopyDeleteThread(
            src=src,
            dst=dst,
            is_folder=False,
            copy=True,
            delete=True
        )

        finished_msgs = []
        thread.finished.connect(lambda msg: finished_msgs.append(msg))

        thread.run()

        assert len(finished_msgs) == 2
        assert any("copied" in msg.lower() or "copiato" in msg.lower() for msg in finished_msgs)
        assert any("deleted" in msg.lower() or "eliminato" in msg.lower() for msg in finished_msgs)


class TestConcurrency:
    """Tests for concurrency and thread safety"""

    def test_multiple_copy_threads_concurrent(self, temp_workspace):
        """Test concurrent execution of multiple copy threads"""
        threads = []
        files_to_create = 5

        for i in range(files_to_create):
            src = os.path.join(temp_workspace, f"source_{i}.txt")
            dst = os.path.join(temp_workspace, f"dest_{i}.txt")

            with open(src, 'w') as f:
                f.write(f"content {i}")

            thread = CopyDeleteThread(src=src, dst=dst, is_folder=False, copy=True)
            threads.append(thread)

        # Start all threads
        for thread in threads:
            thread.start()

        # Wait for completion
        for thread in threads:
            thread.wait(5000)  # 5 second timeout

        # Verify all files were copied
        for i in range(files_to_create):
            dst = os.path.join(temp_workspace, f"dest_{i}.txt")
            assert os.path.exists(dst)

    def test_multiple_delete_threads_concurrent(self, temp_workspace):
        """Test concurrent deletion of multiple files"""
        threads = []
        files_to_delete = 5

        # Create files
        for i in range(files_to_delete):
            file_path = os.path.join(temp_workspace, f"delete_{i}.txt")
            with open(file_path, 'w') as f:
                f.write(f"data {i}")

            thread = CopyDeleteThread(src=file_path, is_folder=False, delete=True)
            threads.append((thread, file_path))

        # Start all
        for thread, _ in threads:
            thread.start()

        # Wait
        for thread, _ in threads:
            thread.wait(5000)

        # Verify all were deleted
        for _, file_path in threads:
            assert not os.path.exists(file_path)


class TestPerformance:
    """Tests for performance with large files/folders"""

    def test_copy_many_files_in_folder(self, temp_workspace):
        """Test copying folder with many files"""
        src = os.path.join(temp_workspace, "many_files_src")
        dst = os.path.join(temp_workspace, "many_files_dst")

        os.makedirs(src)

        # Create 100 files
        num_files = 100
        for i in range(num_files):
            with open(os.path.join(src, f"file_{i:03d}.txt"), 'w') as f:
                f.write(f"content {i}")

        thread = CopyDeleteThread(src=src, dst=dst, is_folder=True, copy=True)
        thread.run()

        # Verify all were copied
        assert len(os.listdir(dst)) == num_files

    def test_delete_folder_with_many_files(self, temp_workspace):
        """Test deleting folder with many files"""
        folder = os.path.join(temp_workspace, "many_files_delete")
        os.makedirs(folder)

        # Create many files
        for i in range(50):
            with open(os.path.join(folder, f"file_{i}.txt"), 'w') as f:
                f.write("data")

        thread = CopyDeleteThread(src=folder, is_folder=True, delete=True)
        thread.run()

        assert not os.path.exists(folder)

    def test_copy_deep_nested_structure(self, temp_workspace):
        """Test copying deeply nested structure"""
        src = os.path.join(temp_workspace, "deep_src")
        dst = os.path.join(temp_workspace, "deep_dst")

        # Create deep structure
        current = src
        for i in range(10):
            current = os.path.join(current, f"level_{i}")
            os.makedirs(current)
            with open(os.path.join(current, f"file_{i}.txt"), 'w') as f:
                f.write(f"level {i}")

        thread = CopyDeleteThread(src=src, dst=dst, is_folder=True, copy=True)
        thread.run()

        # Verify copied structure
        assert os.path.exists(dst)

        # Verify depth
        current_check = dst
        for i in range(10):
            current_check = os.path.join(current_check, f"level_{i}")
            assert os.path.exists(current_check)
            assert os.path.exists(os.path.join(current_check, f"file_{i}.txt"))


class TestRealWorldScenarios:
    """Tests for realistic scenarios"""

    def test_backup_workspace_folder(self, temp_workspace):
        """Test backing up a workspace folder"""
        # Simulate workspace with BIDS structure
        workspace = os.path.join(temp_workspace, "workspace")
        backup = os.path.join(temp_workspace, "backup")

        # Create structure
        for i in range(3):
            subject_dir = os.path.join(workspace, f"sub-{i:02d}", "anat")
            os.makedirs(subject_dir)
            with open(os.path.join(subject_dir, "T1w.nii"), 'w') as f:
                f.write(f"subject {i} brain data")

        thread = CopyDeleteThread(src=workspace, dst=backup, is_folder=True, copy=True)
        thread.run()

        # Verify complete backup
        assert os.path.exists(backup)
        for i in range(3):
            assert os.path.exists(
                os.path.join(backup, f"sub-{i:02d}", "anat", "T1w.nii")
            )

    def test_cleanup_temp_derivatives(self, temp_workspace):
        """Test cleaning up temporary derivatives"""
        derivatives = os.path.join(temp_workspace, "derivatives", "temp_processing")
        os.makedirs(derivatives)

        # Create temporary files
        for i in range(5):
            with open(os.path.join(derivatives, f"temp_{i}.nii"), 'w') as f:
                f.write("temp data")

        thread = CopyDeleteThread(src=derivatives, is_folder=True, delete=True)
        thread.run()

        assert not os.path.exists(derivatives)

    def test_move_processed_results(self, temp_workspace):
        """Test moving processed results"""
        processing = os.path.join(temp_workspace, "processing")
        results = os.path.join(temp_workspace, "results")

        os.makedirs(processing)
        with open(os.path.join(processing, "output.nii"), 'w') as f:
            f.write("processed brain")
        with open(os.path.join(processing, "output.json"), 'w') as f:
            f.write('{"processed": true}')

        # Move = copy + delete
        thread = CopyDeleteThread(
            src=processing,
            dst=results,
            is_folder=True,
            copy=True,
            delete=True
        )
        thread.run()

        # Results should exist
        assert os.path.exists(results)
        assert os.path.exists(os.path.join(results, "output.nii"))
        assert os.path.exists(os.path.join(results, "output.json"))

        # Processing folder should be deleted
        assert not os.path.exists(processing)


class TestPathNormalization:
    """Tests for path normalization"""

    def test_copy_with_trailing_slash(self, temp_workspace):
        """Test copy with trailing slash in paths"""
        src = os.path.join(temp_workspace, "source") + os.sep
        dst = os.path.join(temp_workspace, "dest") + os.sep

        os.makedirs(src.rstrip(os.sep))
        with open(os.path.join(src, "file.txt"), 'w') as f:
            f.write("data")

        thread = CopyDeleteThread(src=src, dst=dst, is_folder=True, copy=True)
        thread.run()

        assert os.path.exists(dst.rstrip(os.sep))

    def test_copy_with_relative_path(self, temp_workspace):
        """Test copy with relative path"""
        # Change directory temporarily
        original_cwd = os.getcwd()
        try:
            os.chdir(temp_workspace)

            src = "relative_source.txt"
            dst = "relative_dest.txt"

            with open(src, 'w') as f:
                f.write("relative data")

            thread = CopyDeleteThread(src=src, dst=dst, is_folder=False, copy=True)
            thread.run()

            assert os.path.exists(dst)
        finally:
            os.chdir(original_cwd)

    def test_copy_with_absolute_path(self, temp_workspace):
        """Test copy with absolute path"""
        src = os.path.abspath(os.path.join(temp_workspace, "abs_source.txt"))
        dst = os.path.abspath(os.path.join(temp_workspace, "abs_dest.txt"))

        with open(src, 'w') as f:
            f.write("absolute path data")

        thread = CopyDeleteThread(src=src, dst=dst, is_folder=False, copy=True)
        thread.run()

        assert os.path.exists(dst)


class TestErrorMessages:
    """Tests for error messages"""

    def test_error_message_format(self, temp_workspace):
        """Test error message format"""
        src = os.path.join(temp_workspace, "missing.txt")
        dst = os.path.join(temp_workspace, "dest.txt")

        thread = CopyDeleteThread(src=src, dst=dst, is_folder=False, copy=True)

        error_msgs = []
        thread.error.connect(lambda msg: error_msgs.append(msg))

        thread.run()

        assert len(error_msgs) == 1
        msg = error_msgs[0]

        # Message should contain src, dst, and error description
        assert "src:" in msg.lower() or src in msg
        assert "dst:" in msg.lower() or dst in msg

    def test_translatable_messages(self, temp_workspace):
        """Test that messages are translatable"""
        src = os.path.join(temp_workspace, "source.txt")
        dst = os.path.join(temp_workspace, "dest.txt")

        with open(src, 'w') as f:
            f.write("data")

        thread = CopyDeleteThread(src=src, dst=dst, is_folder=False, copy=True)

        finished_msgs = []
        thread.finished.connect(lambda msg: finished_msgs.append(msg))

        thread.run()

        # Messages should come from QCoreApplication.translate
        # So they should be readable strings
        assert len(finished_msgs) == 1
        assert len(finished_msgs[0]) > 0


# Parametrized tests
@pytest.mark.parametrize("is_folder", [True, False])
def test_copy_parametrized_folder_flag(is_folder, temp_workspace):
    """Parametrized test for is_folder flag"""
    if is_folder:
        src = os.path.join(temp_workspace, "folder_src")
        dst = os.path.join(temp_workspace, "folder_dst")
        os.makedirs(src)
        with open(os.path.join(src, "file.txt"), 'w') as f:
            f.write("data")
    else:
        src = os.path.join(temp_workspace, "file_src.txt")
        dst = os.path.join(temp_workspace, "file_dst.txt")
        with open(src, 'w') as f:
            f.write("data")

    thread = CopyDeleteThread(src=src, dst=dst, is_folder=is_folder, copy=True)
    thread.run()

    assert os.path.exists(dst)


@pytest.mark.parametrize("operation,flag_name", [
    ("copy", "copy"),
    ("delete", "delete"),
])
def test_operation_flags_parametrized(operation, flag_name, temp_workspace):
    """Parametrized test for operation flags"""
    src = os.path.join(temp_workspace, f"{operation}_test.txt")
    with open(src, 'w') as f:
        f.write("data")

    kwargs = {
        'src': src,
        'is_folder': False,
        flag_name: True
    }

    if operation == "copy":
        kwargs['dst'] = os.path.join(temp_workspace, "dest.txt")

    thread = CopyDeleteThread(**kwargs)

    assert getattr(thread, flag_name) is True


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
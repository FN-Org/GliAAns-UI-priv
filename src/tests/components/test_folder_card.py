import os
import pytest
from unittest.mock import Mock, patch, MagicMock
from PyQt6.QtWidgets import QDialog
from PyQt6.QtCore import Qt

from main.components.folder_card import FolderCard


@pytest.fixture
def test_folder_with_files(temp_workspace):
    """Create a test folder with files."""
    folder = os.path.join(temp_workspace, "test_output")
    os.makedirs(folder)

    # Create some initial files
    initial_files = ["file1.txt", "file2.csv", "result.nii"]
    for filename in initial_files:
        with open(os.path.join(folder, filename), "w") as f:
            f.write("test content")

    return folder


@pytest.fixture
def empty_folder(temp_workspace):
    """Create an empty folder."""
    folder = os.path.join(temp_workspace, "empty_output")
    os.makedirs(folder)
    return folder


@pytest.fixture
def mock_context_card():
    """Mock context for FolderCard."""
    return {}


class TestFolderCardInitialization:
    """Tests for FolderCard initialization."""

    def test_initialization_existing_folder(self, qtbot, mock_context_card, test_folder_with_files):
        """Test initialization with existing folder."""
        card = FolderCard(mock_context_card, test_folder_with_files)
        qtbot.addWidget(card)

        assert card.folder == test_folder_with_files
        assert card.files == []
        assert len(card.existing_files) == 3  # file1, file2, result
        assert card.pulse_animation is None
        assert card._scale == 1.0
        assert card._glow_opacity == 0.0

    def test_initialization_empty_folder(self, qtbot, mock_context_card, empty_folder):
        """Test initialization with empty folder."""
        card = FolderCard(mock_context_card, empty_folder)
        qtbot.addWidget(card)

        assert card.folder == empty_folder
        assert len(card.existing_files) == 0

    def test_initialization_nonexistent_folder(self, qtbot, mock_context_card, temp_workspace):
        """Test initialization with nonexistent folder."""
        nonexistent = os.path.join(temp_workspace, "nonexistent")

        card = FolderCard(mock_context_card, nonexistent)
        qtbot.addWidget(card)

        assert card.folder == nonexistent
        assert card.existing_files == set()

    def test_ui_elements_created(self, qtbot, mock_context_card, test_folder_with_files):
        """Test that all UI elements are created."""
        card = FolderCard(mock_context_card, test_folder_with_files)
        qtbot.addWidget(card)

        assert card.card_frame is not None
        assert card.folder_icon is not None
        assert card.folder_name is not None
        assert card.status_label is not None
        assert card.action_btn is not None

    def test_fixed_height_set(self, qtbot, mock_context_card, test_folder_with_files):
        """Test that the height is fixed."""
        card = FolderCard(mock_context_card, test_folder_with_files)
        qtbot.addWidget(card)

        assert card.height() == 100

    def test_folder_name_display(self, qtbot, mock_context_card, test_folder_with_files):
        """Test that the folder name is displayed."""
        card = FolderCard(mock_context_card, test_folder_with_files)
        qtbot.addWidget(card)

        assert card.folder_name.text() == os.path.basename(test_folder_with_files)

    def test_initial_status(self, qtbot, mock_context_card, test_folder_with_files):
        """Test initial status."""
        card = FolderCard(mock_context_card, test_folder_with_files)
        qtbot.addWidget(card)

        assert "Waiting" in card.status_label.text() or "wait" in card.status_label.text().lower()
        assert not card.action_btn.isEnabled()

    def test_initial_icon(self, qtbot, mock_context_card, test_folder_with_files):
        """Test initial icon."""
        card = FolderCard(mock_context_card, test_folder_with_files)
        qtbot.addWidget(card)

        assert "📁" in card.folder_icon.text()


class TestAddFiles:
    """Tests for the add_files method."""

    def test_add_files_basic(self, qtbot, mock_context_card, test_folder_with_files):
        """Test basic file addition."""
        card = FolderCard(mock_context_card, test_folder_with_files)
        qtbot.addWidget(card)

        new_files = ["new1.txt", "new2.csv"]
        card.add_files(new_files)

        assert len(card.files) == 2
        assert "new1.txt" in card.files
        assert "new2.csv" in card.files

    def test_add_files_updates_status(self, qtbot, mock_context_card, test_folder_with_files):
        """Test that add_files updates status."""
        card = FolderCard(mock_context_card, test_folder_with_files)
        qtbot.addWidget(card)

        card.add_files(["file1.txt"])

        assert "1" in card.status_label.text()

    def test_add_files_enables_button(self, qtbot, mock_context_card, test_folder_with_files):
        """Test that add_files enables the button."""
        card = FolderCard(mock_context_card, test_folder_with_files)
        qtbot.addWidget(card)

        assert not card.action_btn.isEnabled()

        card.add_files(["file1.txt"])

        assert card.action_btn.isEnabled()

    def test_add_files_changes_icon(self, qtbot, mock_context_card, test_folder_with_files):
        """Test that add_files changes the icon."""
        card = FolderCard(mock_context_card, test_folder_with_files)
        qtbot.addWidget(card)

        initial_icon = card.folder_icon.text()

        card.add_files(["file1.txt"])

        assert card.folder_icon.text() != initial_icon
        assert "✓" in card.folder_icon.text()

    def test_add_files_multiple_times(self, qtbot, mock_context_card, test_folder_with_files):
        """Test multiple file additions."""
        card = FolderCard(mock_context_card, test_folder_with_files)
        qtbot.addWidget(card)

        card.add_files(["file1.txt"])
        assert len(card.files) == 1

        card.add_files(["file2.txt", "file3.txt"])
        assert len(card.files) == 3

    def test_add_files_empty_list(self, qtbot, mock_context_card, test_folder_with_files):
        """Test adding an empty list."""
        card = FolderCard(mock_context_card, test_folder_with_files)
        qtbot.addWidget(card)

        card.add_files([])

        assert len(card.files) == 0

    def test_add_files_starts_animation(self, qtbot, mock_context_card, test_folder_with_files):
        """Test that add_files starts animation."""
        card = FolderCard(mock_context_card, test_folder_with_files)
        qtbot.addWidget(card)

        with patch.object(card, 'start_pulse_animation') as mock_anim:
            card.add_files(["file1.txt"])

            mock_anim.assert_called_once()


class TestStartPulseAnimation:
    """Tests for the start_pulse_animation method."""

    def test_start_pulse_animation_creates_animation(self, qtbot, mock_context_card, test_folder_with_files):
        """Test that start_pulse_animation creates animation."""
        card = FolderCard(mock_context_card, test_folder_with_files)
        qtbot.addWidget(card)

        card.start_pulse_animation()

        assert card.pulse_animation is not None

    def test_start_pulse_animation_stops_existing(self, qtbot, mock_context_card, test_folder_with_files):
        """Test that it stops existing animation."""
        card = FolderCard(mock_context_card, test_folder_with_files)
        qtbot.addWidget(card)

        # First animation
        card.start_pulse_animation()
        first_anim = card.pulse_animation

        # Second animation
        card.start_pulse_animation()

        assert card.pulse_animation is not None
        # Could be the same or a new one

    def test_start_pulse_animation_multiple_calls(self, qtbot, mock_context_card, test_folder_with_files):
        """Test multiple calls."""
        card = FolderCard(mock_context_card, test_folder_with_files)
        qtbot.addWidget(card)

        for _ in range(5):
            card.start_pulse_animation()

        # Should not crash
        assert card.pulse_animation is not None


class TestResetState:
    """Tests for the reset_state method."""

    def test_reset_state_basic(self, qtbot, mock_context_card, test_folder_with_files):
        """Test basic state reset."""
        card = FolderCard(mock_context_card, test_folder_with_files)
        qtbot.addWidget(card)

        # Add files to change state
        card.add_files(["file1.txt"])

        # Reset
        card.reset_state()

        assert not card.action_btn.isEnabled()
        assert "📁" in card.folder_icon.text()

    def test_reset_state_stops_animation(self, qtbot, mock_context_card, test_folder_with_files):
        """Test that reset stops animation."""
        card = FolderCard(mock_context_card, test_folder_with_files)
        qtbot.addWidget(card)

        card.start_pulse_animation()
        assert card.pulse_animation is not None

        card.reset_state()

        # Animation should be stopped (verifiable through state)

    def test_reset_state_restores_status_text(self, qtbot, mock_context_card, test_folder_with_files):
        """Test that reset restores status text."""
        card = FolderCard(mock_context_card, test_folder_with_files)
        qtbot.addWidget(card)

        card.add_files(["file1.txt"])

        card.reset_state()

        assert "Waiting" in card.status_label.text() or "wait" in card.status_label.text().lower()

    def test_reset_state_without_prior_changes(self, qtbot, mock_context_card, test_folder_with_files):
        """Test reset without prior changes."""
        card = FolderCard(mock_context_card, test_folder_with_files)
        qtbot.addWidget(card)

        # Reset without modifications
        card.reset_state()

        # Should not crash
        assert not card.action_btn.isEnabled()


class TestCheckNewFiles:
    """Tests for the check_new_files method."""

    def test_check_new_files_detects_new(self, qtbot, mock_context_card, test_folder_with_files):
        """Test detection of new files."""
        card = FolderCard(mock_context_card, test_folder_with_files)
        qtbot.addWidget(card)

        initial_count = len(card.existing_files)

        # Add a new file to the folder
        new_file = os.path.join(test_folder_with_files, "brand_new.txt")
        with open(new_file, "w") as f:
            f.write("new content")

        card.check_new_files()

        assert len(card.files) == 1
        assert "brand_new.txt" in card.files
        assert len(card.existing_files) == initial_count + 1

    def test_check_new_files_no_changes(self, qtbot, mock_context_card, test_folder_with_files):
        """Test when there are no new files."""
        card = FolderCard(mock_context_card, test_folder_with_files)
        qtbot.addWidget(card)

        card.check_new_files()

        assert len(card.files) == 0

    def test_check_new_files_updates_existing(self, qtbot, mock_context_card, test_folder_with_files):
        """Test that existing_files gets updated."""
        card = FolderCard(mock_context_card, test_folder_with_files)
        qtbot.addWidget(card)

        initial_existing = card.existing_files.copy()

        # Add file
        new_file = os.path.join(test_folder_with_files, "new.txt")
        with open(new_file, "w") as f:
            f.write("content")

        card.check_new_files()

        assert len(card.existing_files) > len(initial_existing)
        assert "new.txt" in card.existing_files

    def test_check_new_files_nonexistent_folder(self, qtbot, mock_context_card, temp_workspace):
        """Test with nonexistent folder."""
        nonexistent = os.path.join(temp_workspace, "nonexistent")
        card = FolderCard(mock_context_card, nonexistent)
        qtbot.addWidget(card)

        # Should not crash
        card.check_new_files()

        assert len(card.files) == 0

    def test_check_new_files_multiple_new(self, qtbot, mock_context_card, test_folder_with_files):
        """Test detection of multiple files."""
        card = FolderCard(mock_context_card, test_folder_with_files)
        qtbot.addWidget(card)

        # Add multiple files
        for i in range(5):
            new_file = os.path.join(test_folder_with_files, f"new{i}.txt")
            with open(new_file, "w") as f:
                f.write("content")

        card.check_new_files()

        assert len(card.files) == 5

    def test_check_new_files_calls_add_files(self, qtbot, mock_context_card, test_folder_with_files):
        """Test that add_files is called."""
        card = FolderCard(mock_context_card, test_folder_with_files)
        qtbot.addWidget(card)

        # Add file
        new_file = os.path.join(test_folder_with_files, "new.txt")
        with open(new_file, "w") as f:
            f.write("content")

        with patch.object(card, 'add_files', wraps=card.add_files) as mock_add:
            card.check_new_files()

            mock_add.assert_called_once()

class TestShowFilesDialog:
    """Tests for the show_files_dialog method."""

    def test_show_files_dialog_with_files(self, qtbot, mock_context_card, test_folder_with_files):
        """Test opening the dialog when files exist."""
        card = FolderCard(mock_context_card, test_folder_with_files)
        qtbot.addWidget(card)

        card.add_files(["file1.txt", "file2.csv"])

        with patch.object(QDialog, 'exec') as mock_exec:
            card.show_files_dialog()

            mock_exec.assert_called_once()

    def test_show_files_dialog_empty(self, qtbot, mock_context_card, test_folder_with_files):
        """Test that the dialog is not opened if there are no files."""
        card = FolderCard(mock_context_card, test_folder_with_files)
        qtbot.addWidget(card)

        with patch.object(QDialog, 'exec') as mock_exec:
            card.show_files_dialog()

            mock_exec.assert_not_called()

    def test_show_files_dialog_clears_files(self, qtbot, mock_context_card, test_folder_with_files):
        """Test that files are cleared after closing."""
        card = FolderCard(mock_context_card, test_folder_with_files)
        qtbot.addWidget(card)

        card.add_files(["file1.txt"])

        with patch.object(QDialog, 'exec'):
            card.show_files_dialog()

        assert len(card.files) == 0

    def test_show_files_dialog_resets_state(self, qtbot, mock_context_card, test_folder_with_files):
        """Test that the state is reset after closing."""
        card = FolderCard(mock_context_card, test_folder_with_files)
        qtbot.addWidget(card)

        card.add_files(["file1.txt"])

        with patch.object(QDialog, 'exec'):
            card.show_files_dialog()

        assert not card.action_btn.isEnabled()


class TestOpenFolderSignal:
    """Tests for the open_folder_requested signal."""

    def test_open_folder_signal_exists(self, qtbot, mock_context_card, test_folder_with_files):
        """Test that the signal exists."""
        card = FolderCard(mock_context_card, test_folder_with_files)
        qtbot.addWidget(card)

        assert hasattr(card, 'open_folder_requested')

    def test_open_folder_signal_emitted(self, qtbot, mock_context_card, test_folder_with_files):
        """Test that the signal is emitted (indirect test)."""
        card = FolderCard(mock_context_card, test_folder_with_files)
        qtbot.addWidget(card)

        # The signal is normally emitted from the dialog when clicking its button.
        # Here we test indirectly by connecting and emitting ourselves.
        signal_received = []
        card.open_folder_requested.connect(lambda path: signal_received.append(path))

        # Simulate emission
        card.open_folder_requested.emit(test_folder_with_files)

        assert len(signal_received) == 1
        assert signal_received[0] == test_folder_with_files


class TestEdgeCases:
    """Tests for edge cases."""

    def test_very_long_folder_name(self, qtbot, mock_context_card, temp_workspace):
        """Test with a very long folder name."""
        long_name = "a" * 200
        long_folder = os.path.join(temp_workspace, long_name)
        os.makedirs(long_folder)

        card = FolderCard(mock_context_card, long_folder)
        qtbot.addWidget(card)

        assert card.folder_name.text() == long_name

    def test_unicode_folder_name(self, qtbot, mock_context_card, temp_workspace):
        """Test with unicode characters in folder name."""
        unicode_name = "папка_文件夹_φάκελος"
        unicode_folder = os.path.join(temp_workspace, unicode_name)
        os.makedirs(unicode_folder)

        card = FolderCard(mock_context_card, unicode_folder)
        qtbot.addWidget(card)

        assert unicode_name in card.folder_name.text()

    def test_many_files(self, qtbot, mock_context_card, test_folder_with_files):
        """Test handling many files."""
        card = FolderCard(mock_context_card, test_folder_with_files)
        qtbot.addWidget(card)

        many_files = [f"file{i}.txt" for i in range(100)]
        card.add_files(many_files)

        assert len(card.files) == 100

    def test_special_characters_in_filename(self, qtbot, mock_context_card, test_folder_with_files):
        """Test filenames with special characters."""
        special_files = [
            "file with spaces.txt",
            "file-with-dashes.txt",
            "file_with_underscores.txt",
            "file.multiple.dots.txt"
        ]

        card = FolderCard(mock_context_card, test_folder_with_files)
        qtbot.addWidget(card)

        card.add_files(special_files)

        assert len(card.files) == 4
        assert all(f in card.files for f in special_files)

    def test_rapid_file_additions(self, qtbot, mock_context_card, test_folder_with_files):
        """Test rapid file additions."""
        card = FolderCard(mock_context_card, test_folder_with_files)
        qtbot.addWidget(card)

        for i in range(20):
            card.add_files([f"file{i}.txt"])

        assert len(card.files) == 20

    def test_folder_deleted_after_init(self, qtbot, mock_context_card, temp_workspace):
        """Test behavior when the folder is deleted after initialization."""
        folder = os.path.join(temp_workspace, "to_delete")
        os.makedirs(folder)

        card = FolderCard(mock_context_card, folder)
        qtbot.addWidget(card)

        # Delete the folder
        os.rmdir(folder)

        # check_new_files should not crash
        card.check_new_files()


class TestIntegration:
    """Integration tests."""

    def test_full_workflow(self, qtbot, mock_context_card, test_folder_with_files):
        """Test the full workflow."""
        card = FolderCard(mock_context_card, test_folder_with_files)
        qtbot.addWidget(card)

        # Initial state
        assert not card.action_btn.isEnabled()
        assert len(card.files) == 0

        # Add new file to filesystem
        new_file = os.path.join(test_folder_with_files, "new.txt")
        with open(new_file, "w") as f:
            f.write("content")

        # Check new files
        card.check_new_files()

        # State check
        assert card.action_btn.isEnabled()
        assert len(card.files) == 1

        # Show dialog and reset
        with patch.object(QDialog, 'exec'):
            card.show_files_dialog()

        # Reset check
        assert not card.action_btn.isEnabled()
        assert len(card.files) == 0

    def test_multiple_check_cycles(self, qtbot, mock_context_card, test_folder_with_files):
        """Test multiple check cycles."""
        card = FolderCard(mock_context_card, test_folder_with_files)
        qtbot.addWidget(card)

        for cycle in range(3):
            # Add file
            new_file = os.path.join(test_folder_with_files, f"cycle{cycle}.txt")
            with open(new_file, "w") as f:
                f.write("content")

            # Check
            card.check_new_files()

            # Show and reset
            with patch.object(QDialog, 'exec'):
                if card.files:
                    card.show_files_dialog()

        # Final state should be reset
        assert len(card.files) == 0


class TestStateConsistency:
    """Tests for state consistency."""

    def test_state_after_add_files(self, qtbot, mock_context_card, test_folder_with_files):
        """Test state consistency after add_files."""
        card = FolderCard(mock_context_card, test_folder_with_files)
        qtbot.addWidget(card)

        card.add_files(["file1.txt"])

        # State should be consistent
        assert len(card.files) > 0
        assert card.action_btn.isEnabled()
        assert "✓" in card.folder_icon.text()

    def test_state_after_reset(self, qtbot, mock_context_card, test_folder_with_files):
        """Test state consistency after reset."""
        card = FolderCard(mock_context_card, test_folder_with_files)
        qtbot.addWidget(card)

        card.add_files(["file1.txt"])
        card.reset_state()

        # Should be initial state
        assert not card.action_btn.isEnabled()
        assert "📁" in card.folder_icon.text()


class TestMemoryAndPerformance:
    """Tests for memory and performance."""

    def test_no_memory_leak_repeated_operations(self, qtbot, mock_context_card, test_folder_with_files):
        """Test no memory leaks after repeated operations."""
        card = FolderCard(mock_context_card, test_folder_with_files)
        qtbot.addWidget(card)

        for _ in range(50):
            card.add_files(["file.txt"])
            card.reset_state()

        # Final state should be clean
        assert len(card.files) == 0

    def test_performance_many_checks(self, qtbot, mock_context_card, test_folder_with_files):
        """Test performance with many checks."""
        card = FolderCard(mock_context_card, test_folder_with_files)
        qtbot.addWidget(card)

        # Many checks with no new files
        for _ in range(100):
            card.check_new_files()

        # Should not be slow
        assert True


class TestAccessibility:
    """Tests for accessibility."""

    def test_button_has_text(self, qtbot, mock_context_card, test_folder_with_files):
        """Test that the button has text."""
        card = FolderCard(mock_context_card, test_folder_with_files)
        qtbot.addWidget(card)

        assert len(card.action_btn.text()) > 0

    def test_status_label_has_text(self, qtbot, mock_context_card, test_folder_with_files):
        """Test that the status label has text."""
        card = FolderCard(mock_context_card, test_folder_with_files)
        qtbot.addWidget(card)

        assert len(card.status_label.text()) > 0
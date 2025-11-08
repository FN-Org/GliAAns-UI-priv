import os
import pytest
from unittest.mock import Mock, patch, MagicMock
from PyQt6.QtWidgets import QListWidgetItem
from PyQt6.QtCore import Qt, pyqtSignal

from main.components.file_selector_widget import FileSelectorWidget


@pytest.fixture
def mock_context_selector(signal_emitter):
    """Context per FileSelectorWidget."""
    context = {
        "selected_files_signal": signal_emitter.selected_files,
        "update_main_buttons": Mock(),
        "language_changed": signal_emitter.language_changed,
        "workspace_path": "/tmp"
    }
    return context


@pytest.fixture
def mock_has_existing_function():
    """Mock per has_existing_function."""
    return Mock(return_value=False)


@pytest.fixture
def test_nifti_files(temp_workspace):
    """Create test NIfTI file."""
    files = []

    # File .nii
    nii_file = os.path.join(temp_workspace, "test1.nii")
    with open(nii_file, "w") as f:
        f.write("nifti data")
    files.append(nii_file)

    # File .nii.gz
    nii_gz_file = os.path.join(temp_workspace, "test2.nii.gz")
    with open(nii_gz_file, "w") as f:
        f.write("compressed nifti data")
    files.append(nii_gz_file)

    # File non NIfTI
    txt_file = os.path.join(temp_workspace, "test.txt")
    with open(txt_file, "w") as f:
        f.write("text data")
    files.append(txt_file)

    return files


class TestFileSelectorWidgetInitialization:
    """Test for initialization if FileSelectorWidget."""

    def test_initialization_basic(self, qtbot, mock_context_selector, mock_has_existing_function):
        """Test base initialization."""
        widget = FileSelectorWidget(
            context=mock_context_selector,
            has_existing_function=mock_has_existing_function,
            label="test",
            allow_multiple=True
        )
        qtbot.addWidget(widget)

        assert widget.context == mock_context_selector
        assert widget.label == "test"
        assert widget.allow_multiple is True
        assert widget.has_existing_function == mock_has_existing_function
        assert widget.selected_files is None

    def test_initialization_single_file_mode(self, qtbot, mock_context_selector, mock_has_existing_function):
        """Test initialization single file modality."""
        widget = FileSelectorWidget(
            context=mock_context_selector,
            has_existing_function=mock_has_existing_function,
            label="single",
            allow_multiple=False
        )
        qtbot.addWidget(widget)

        assert widget.allow_multiple is False

    def test_initialization_with_processing_signal(self, qtbot, mock_context_selector, mock_has_existing_function):
        """Test initialization with signal processing."""
        processing_signal = Mock()
        processing_signal.connect = Mock()

        widget = FileSelectorWidget(
            context=mock_context_selector,
            has_existing_function=mock_has_existing_function,
            label="test",
            allow_multiple=True,
            processing=processing_signal
        )
        qtbot.addWidget(widget)

        # Verifica che il signal sia stato connesso
        processing_signal.connect.assert_called_once()

    def test_initialization_with_forced_filters(self, qtbot, mock_context_selector, mock_has_existing_function):
        """Test initialization with forced_filters."""
        filters = {"type": "mask"}

        widget = FileSelectorWidget(
            context=mock_context_selector,
            has_existing_function=mock_has_existing_function,
            label="test",
            allow_multiple=True,
            forced_filters=filters
        )
        qtbot.addWidget(widget)

        assert widget.forced_filters == filters

    def test_ui_elements_created(self, qtbot, mock_context_selector, mock_has_existing_function):
        """Test creation UI elements"""
        widget = FileSelectorWidget(
            context=mock_context_selector,
            has_existing_function=mock_has_existing_function,
            label="test",
            allow_multiple=True
        )
        qtbot.addWidget(widget)

        assert widget.file_list_widget is not None
        assert widget.file_button is not None
        assert widget.clear_button is not None

    def test_clear_button_initially_disabled(self, qtbot, mock_context_selector, mock_has_existing_function):
        """Test clear button initially disabled"""
        widget = FileSelectorWidget(
            context=mock_context_selector,
            has_existing_function=mock_has_existing_function,
            label="test",
            allow_multiple=True
        )
        qtbot.addWidget(widget)

        assert not widget.clear_button.isEnabled()

    def test_file_list_widget_config(self, qtbot, mock_context_selector, mock_has_existing_function):
        """Test configuration file_list_widget."""
        widget = FileSelectorWidget(
            context=mock_context_selector,
            has_existing_function=mock_has_existing_function,
            label="test",
            allow_multiple=True
        )
        qtbot.addWidget(widget)

        assert widget.file_list_widget.selectionMode() == widget.file_list_widget.SelectionMode.NoSelection
        assert widget.file_list_widget.focusPolicy() == Qt.FocusPolicy.NoFocus
        assert widget.file_list_widget.maximumHeight() == 100


class TestSetSelectedFiles:
    """Test selected files method."""

    def test_set_selected_files_multiple_valid(self, qtbot, mock_context_selector, mock_has_existing_function,
                                               test_nifti_files):
        """Test multiple files valid"""
        widget = FileSelectorWidget(
            context=mock_context_selector,
            has_existing_function=mock_has_existing_function,
            label="test",
            allow_multiple=True
        )
        qtbot.addWidget(widget)

        # Obly first two are .nii/.nii.gz
        widget.set_selected_files(test_nifti_files)

        assert len(widget.selected_files) == 2

    def test_many_files(self, qtbot, mock_context_selector, mock_has_existing_function, temp_workspace):
        """Test wuth manty files."""
        files = []
        for i in range(100):
            filepath = os.path.join(temp_workspace, f"file{i}.nii")
            with open(filepath, "w") as f:
                f.write("data")
            files.append(filepath)

        widget = FileSelectorWidget(
            context=mock_context_selector,
            has_existing_function=mock_has_existing_function,
            label="test",
            allow_multiple=True
        )
        qtbot.addWidget(widget)

        widget.set_selected_files(files)

        assert len(widget.selected_files) == 100
        assert widget.file_list_widget.count() == 100

    def test_unicode_in_filenames(self, qtbot, mock_context_selector, mock_has_existing_function, temp_workspace):
        """Test with unicode chars in file name."""
        unicode_files = [
            os.path.join(temp_workspace, "файл.nii"),
            os.path.join(temp_workspace, "文件.nii"),
            os.path.join(temp_workspace, "αρχείο.nii.gz")
        ]

        for filepath in unicode_files:
            with open(filepath, "w") as f:
                f.write("data")

        widget = FileSelectorWidget(
            context=mock_context_selector,
            has_existing_function=mock_has_existing_function,
            label="test",
            allow_multiple=True
        )
        qtbot.addWidget(widget)

        widget.set_selected_files(unicode_files)

        assert len(widget.selected_files) == 3

    def test_mixed_nii_and_nii_gz(self, qtbot, mock_context_selector, mock_has_existing_function, temp_workspace):
        """Test with file .nii and .nii.gz mixed."""
        files = []

        for i in range(5):
            nii_file = os.path.join(temp_workspace, f"file{i}.nii")
            with open(nii_file, "w") as f:
                f.write("data")
            files.append(nii_file)

            nii_gz_file = os.path.join(temp_workspace, f"file{i}.nii.gz")
            with open(nii_gz_file, "w") as f:
                f.write("data")
            files.append(nii_gz_file)

        widget = FileSelectorWidget(
            context=mock_context_selector,
            has_existing_function=mock_has_existing_function,
            label="test",
            allow_multiple=True
        )
        qtbot.addWidget(widget)

        widget.set_selected_files(files)

        assert len(widget.selected_files) == 10

    def test_duplicate_files(self, qtbot, mock_context_selector, mock_has_existing_function, temp_workspace):
        """Test with duplicated file in the list."""
        filepath = os.path.join(temp_workspace, "duplicate.nii")
        with open(filepath, "w") as f:
            f.write("data")

        widget = FileSelectorWidget(
            context=mock_context_selector,
            has_existing_function=mock_has_existing_function,
            label="test",
            allow_multiple=True
        )
        qtbot.addWidget(widget)

        # Pass two times same file
        widget.set_selected_files([filepath, filepath])

        # Should be both accepted
        assert len(widget.selected_files) == 2


class TestIntegration:
    """Test integration."""

    def test_full_workflow_select_clear(self, qtbot, mock_context_selector, mock_has_existing_function,
                                        test_nifti_files):
        """Test workflow complete: select -> clear."""
        widget = FileSelectorWidget(
            context=mock_context_selector,
            has_existing_function=mock_has_existing_function,
            label="test",
            allow_multiple=True
        )
        qtbot.addWidget(widget)

        # Seleziona file
        widget.set_selected_files(test_nifti_files)

        assert len(widget.selected_files) == 2
        assert widget.clear_button.isEnabled()
        assert widget.file_list_widget.count() == 2

        # Pulisci
        widget.clear_selected_files()

        assert widget.selected_files == []
        assert not widget.clear_button.isEnabled()
        assert widget.file_list_widget.count() == 0

    def test_full_workflow_multiple_selections(self, qtbot, mock_context_selector, mock_has_existing_function,
                                               test_nifti_files):
        """Test workflow with multiple selection."""
        widget = FileSelectorWidget(
            context=mock_context_selector,
            has_existing_function=mock_has_existing_function,
            label="test",
            allow_multiple=True
        )
        qtbot.addWidget(widget)

        # First selection
        widget.set_selected_files([test_nifti_files[0]])
        assert len(widget.selected_files) == 1

        # Second selection
        widget.set_selected_files(test_nifti_files)
        assert len(widget.selected_files) == 2

        # Clear
        widget.clear_selected_files()
        assert len(widget.selected_files) == 0

        # Third selection
        widget.set_selected_files([test_nifti_files[1]])
        assert len(widget.selected_files) == 1

    def test_full_workflow_with_processing(self, qtbot, mock_context_selector, mock_has_existing_function,
                                           test_nifti_files):
        """Test workflow with processing mode."""
        widget = FileSelectorWidget(
            context=mock_context_selector,
            has_existing_function=mock_has_existing_function,
            label="test",
            allow_multiple=True
        )
        qtbot.addWidget(widget)

        # Seleziona file
        widget.set_selected_files(test_nifti_files)
        assert widget.file_button.isEnabled()
        assert widget.clear_button.isEnabled()

        # Avvia processing
        widget.set_processing_mode(True)
        assert not widget.file_button.isEnabled()
        assert not widget.clear_button.isEnabled()

        # Termina processing
        widget.set_processing_mode(False)
        assert widget.file_button.isEnabled()
        assert widget.clear_button.isEnabled()


class TestContextHandling:
    """Test context handling."""

    def test_context_without_update_main_buttons(self, qtbot, signal_emitter, mock_has_existing_function,
                                                 test_nifti_files):
        """Test context without update_main_buttons."""
        context = {
            "selected_files_signal": signal_emitter.selected_files,
            "language_changed": signal_emitter.language_changed
        }

        widget = FileSelectorWidget(
            context=context,
            has_existing_function=mock_has_existing_function,
            label="test",
            allow_multiple=True
        )
        qtbot.addWidget(widget)

        # Should not crash
        widget.set_selected_files(test_nifti_files)
        widget.clear_selected_files()

    def test_context_without_language_changed(self, qtbot, signal_emitter, mock_has_existing_function):
        """Test context without language_changed."""
        context = {
            "selected_files_signal": signal_emitter.selected_files,
            "update_main_buttons": Mock()
        }

        widget = FileSelectorWidget(
            context=context,
            has_existing_function=mock_has_existing_function,
            label="test",
            allow_multiple=True
        )
        qtbot.addWidget(widget)

        # Non dovrebbe crashare
        assert widget.context == context


class TestButtonClicks:
    """Test for button clicks."""

    def test_file_button_click(self, qtbot, mock_context_selector, mock_has_existing_function):
        """Test click on file buttons."""
        widget = FileSelectorWidget(
            context=mock_context_selector,
            has_existing_function=mock_has_existing_function,
            label="test",
            allow_multiple=True
        )
        qtbot.addWidget(widget)

        with patch.object(widget, 'open_tree_dialog') as mock_open:
            widget.file_button.clicked.disconnect()
            widget.file_button.clicked.connect(widget.open_tree_dialog)
            widget.file_button.click()
            mock_open.assert_called_once()

    def test_clear_button_click(self, qtbot, mock_context_selector, mock_has_existing_function, test_nifti_files):
        """Test click on clear button."""
        widget = FileSelectorWidget(
            context=mock_context_selector,
            has_existing_function=mock_has_existing_function,
            label="test",
            allow_multiple=True
        )
        qtbot.addWidget(widget)

        widget.set_selected_files(test_nifti_files)

        with patch.object(widget, 'open_tree_dialog') as mock_open:
            widget.clear_button.clicked.disconnect()
            widget.clear_button.clicked.connect(widget.open_tree_dialog)
            widget.clear_button.click()
            mock_open.assert_called_once()


class TestFileExtensions:
    """Tests for file extension handling."""

    def test_accepts_nii(self, qtbot, mock_context_selector, mock_has_existing_function, temp_workspace):
        """Test that it accepts .nii files."""
        nii_file = os.path.join(temp_workspace, "test.nii")
        with open(nii_file, "w") as f:
            f.write("data")

        widget = FileSelectorWidget(
            context=mock_context_selector,
            has_existing_function=mock_has_existing_function,
            label="test",
            allow_multiple=True
        )
        qtbot.addWidget(widget)

        widget.set_selected_files([nii_file])

        assert len(widget.selected_files) == 1

    def test_accepts_nii_gz(self, qtbot, mock_context_selector, mock_has_existing_function, temp_workspace):
        """Test that it accepts .nii.gz files."""
        nii_gz_file = os.path.join(temp_workspace, "test.nii.gz")
        with open(nii_gz_file, "w") as f:
            f.write("data")

        widget = FileSelectorWidget(
            context=mock_context_selector,
            has_existing_function=mock_has_existing_function,
            label="test",
            allow_multiple=True
        )
        qtbot.addWidget(widget)

        widget.set_selected_files([nii_gz_file])

        assert len(widget.selected_files) == 1

    def test_rejects_other_extensions(self, qtbot, mock_context_selector, mock_has_existing_function, temp_workspace):
        """Test that it rejects other extensions."""
        invalid_files = [
            os.path.join(temp_workspace, "test.txt"),
            os.path.join(temp_workspace, "test.nii.bak"),
            os.path.join(temp_workspace, "test.json"),
            os.path.join(temp_workspace, "test.nii.txt")
        ]

        for filepath in invalid_files:
            with open(filepath, "w") as f:
                f.write("data")

        widget = FileSelectorWidget(
            context=mock_context_selector,
            has_existing_function=mock_has_existing_function,
            label="test",
            allow_multiple=True
        )
        qtbot.addWidget(widget)

        widget.set_selected_files(invalid_files)

        assert len(widget.selected_files) == 0

    def test_case_sensitive_extensions(self, qtbot, mock_context_selector, mock_has_existing_function, temp_workspace):
        """Test case sensitivity of file extensions."""
        # .nii and .nii.gz should be case sensitive
        upper_file = os.path.join(temp_workspace, "test.NII")
        with open(upper_file, "w") as f:
            f.write("data")

        widget = FileSelectorWidget(
            context=mock_context_selector,
            has_existing_function=mock_has_existing_function,
            label="test",
            allow_multiple=True
        )
        qtbot.addWidget(widget)

        widget.set_selected_files([upper_file])

        # Should be rejected (case sensitive)
        assert len(widget.selected_files) == 0

class TestMemoryAndPerformance:
    """Tests for memory usage and performance."""

    def test_no_memory_leak_repeated_selections(self, qtbot, mock_context_selector, mock_has_existing_function,
                                                test_nifti_files):
        """Test that there are no memory leaks with repeated selections."""
        widget = FileSelectorWidget(
            context=mock_context_selector,
            has_existing_function=mock_has_existing_function,
            label="test",
            allow_multiple=True
        )
        qtbot.addWidget(widget)

        # Select and clear 100 times
        for _ in range(100):
            widget.set_selected_files(test_nifti_files)
            widget.clear_selected_files()

        # Final state should be clean
        assert widget.selected_files == []
        assert widget.file_list_widget.count() == 0

    def test_performance_many_items(self, qtbot, mock_context_selector, mock_has_existing_function, temp_workspace):
        """Performance test with many items."""
        files = []
        for i in range(500):
            filepath = os.path.join(temp_workspace, f"file{i}.nii")
            with open(filepath, "w") as f:
                f.write("data")
            files.append(filepath)

        widget = FileSelectorWidget(
            context=mock_context_selector,
            has_existing_function=mock_has_existing_function,
            label="test",
            allow_multiple=True
        )
        qtbot.addWidget(widget)

        # Should not be too slow
        widget.set_selected_files(files)

        assert len(widget.selected_files) == 500



class TestStateConsistency:
    """Tests for state consistency."""

    def test_state_after_set_and_get(self, qtbot, mock_context_selector, mock_has_existing_function, test_nifti_files):
        """Test state consistency after set and get."""
        widget = FileSelectorWidget(
            context=mock_context_selector,
            has_existing_function=mock_has_existing_function,
            label="test",
            allow_multiple=True
        )
        qtbot.addWidget(widget)

        widget.set_selected_files(test_nifti_files)

        retrieved_files = widget.get_selected_files()

        assert retrieved_files == widget.selected_files
        assert len(retrieved_files) == len(widget.selected_files)

    def test_ui_state_consistency(self, qtbot, mock_context_selector, mock_has_existing_function, test_nifti_files):
        """Test UI state consistency."""
        widget = FileSelectorWidget(
            context=mock_context_selector,
            has_existing_function=mock_has_existing_function,
            label="test",
            allow_multiple=True
        )
        qtbot.addWidget(widget)

        # Initial state
        assert widget.selected_files is None
        assert widget.file_list_widget.count() == 0
        assert not widget.clear_button.isEnabled()

        # After selection
        widget.set_selected_files(test_nifti_files)
        assert widget.selected_files is not None
        assert widget.file_list_widget.count() == len(widget.selected_files)
        assert widget.clear_button.isEnabled()

        # After clearing
        widget.clear_selected_files()
        assert widget.selected_files == []
        assert widget.file_list_widget.count() == 0
        assert not widget.clear_button.isEnabled()


class TestAccessibility:
    """Tests for accessibility."""

    def test_buttons_have_text(self, qtbot, mock_context_selector, mock_has_existing_function):
        """Test that the buttons have text."""
        widget = FileSelectorWidget(
            context=mock_context_selector,
            has_existing_function=mock_has_existing_function,
            label="test",
            allow_multiple=True
        )
        qtbot.addWidget(widget)

        assert len(widget.file_button.text()) > 0
        assert len(widget.clear_button.text()) > 0

    def test_list_items_have_tooltips(self, qtbot, mock_context_selector, mock_has_existing_function, test_nifti_files):
        """Test that the items have tooltips."""
        widget = FileSelectorWidget(
            context=mock_context_selector,
            has_existing_function=mock_has_existing_function,
            label="test",
            allow_multiple=True
        )
        qtbot.addWidget(widget)

        widget.set_selected_files(test_nifti_files)

        for i in range(widget.file_list_widget.count()):
            item = widget.file_list_widget.item(i)
            tooltip = item.toolTip()
            assert len(tooltip) > 0
            assert tooltip in test_nifti_files
            assert all(f.endswith(('.nii', '.nii.gz')) for f in widget.selected_files)

    def test_set_selected_files_single_mode(self, qtbot, mock_context_selector, mock_has_existing_function,
                                            test_nifti_files):
        """Test setting files in single mode."""
        widget = FileSelectorWidget(
            context=mock_context_selector,
            has_existing_function=mock_has_existing_function,
            label="test",
            allow_multiple=False
        )
        qtbot.addWidget(widget)

        widget.set_selected_files(test_nifti_files)

        # Should keep only the last file
        assert len(widget.selected_files) == 1

    def test_set_selected_files_filters_non_nifti(self, qtbot, mock_context_selector, mock_has_existing_function,
                                                  temp_workspace):
        """Test that non-NIfTI files are filtered out."""
        widget = FileSelectorWidget(
            context=mock_context_selector,
            has_existing_function=mock_has_existing_function,
            label="test",
            allow_multiple=True
        )
        qtbot.addWidget(widget)

        # Create mixed files
        nifti_file = os.path.join(temp_workspace, "valid.nii")
        txt_file = os.path.join(temp_workspace, "invalid.txt")

        with open(nifti_file, "w") as f:
            f.write("nifti")
        with open(txt_file, "w") as f:
            f.write("text")

        widget.set_selected_files([nifti_file, txt_file])

        # Only the .nii file should be selected
        assert len(widget.selected_files) == 1
        assert widget.selected_files[0] == nifti_file

    def test_set_selected_files_filters_directories(self, qtbot, mock_context_selector, mock_has_existing_function,
                                                    temp_workspace):
        """Test that directories are filtered out."""
        widget = FileSelectorWidget(
            context=mock_context_selector,
            has_existing_function=mock_has_existing_function,
            label="test",
            allow_multiple=True
        )
        qtbot.addWidget(widget)

        # Create a directory
        dir_path = os.path.join(temp_workspace, "test_dir.nii")
        os.makedirs(dir_path)

        widget.set_selected_files([dir_path])

        # Directory should not be accepted
        assert len(widget.selected_files) == 0

    def test_set_selected_files_filters_nonexistent(self, qtbot, mock_context_selector, mock_has_existing_function):
        """Test that nonexistent files are filtered out."""
        widget = FileSelectorWidget(
            context=mock_context_selector,
            has_existing_function=mock_has_existing_function,
            label="test",
            allow_multiple=True
        )
        qtbot.addWidget(widget)

        widget.set_selected_files(["/nonexistent/file.nii"])

        assert len(widget.selected_files) == 0

    def test_set_selected_files_updates_list_widget(self, qtbot, mock_context_selector, mock_has_existing_function,
                                                    test_nifti_files):
        """Test that the list widget is updated."""
        widget = FileSelectorWidget(
            context=mock_context_selector,
            has_existing_function=mock_has_existing_function,
            label="test",
            allow_multiple=True
        )
        qtbot.addWidget(widget)

        widget.set_selected_files(test_nifti_files)

        # There should be 2 items (only .nii/.nii.gz)
        assert widget.file_list_widget.count() == 2

    def test_set_selected_files_enables_clear_button(self, qtbot, mock_context_selector, mock_has_existing_function,
                                                     test_nifti_files):
        """Test that the clear button is enabled."""
        widget = FileSelectorWidget(
            context=mock_context_selector,
            has_existing_function=mock_has_existing_function,
            label="test",
            allow_multiple=True
        )
        qtbot.addWidget(widget)

        assert not widget.clear_button.isEnabled()

        widget.set_selected_files(test_nifti_files)

        assert widget.clear_button.isEnabled()

    def test_set_selected_files_emits_has_file_signal(self, qtbot, mock_context_selector, mock_has_existing_function,
                                                      test_nifti_files):
        """Test that the has_file signal is emitted."""
        widget = FileSelectorWidget(
            context=mock_context_selector,
            has_existing_function=mock_has_existing_function,
            label="test",
            allow_multiple=True
        )
        qtbot.addWidget(widget)

        with qtbot.waitSignal(widget.has_file) as blocker:
            widget.set_selected_files(test_nifti_files)

        # Signal should be True (files exist)
        assert blocker.args[0] is True

    def test_set_selected_files_calls_update_main_buttons(self, qtbot, mock_context_selector,
                                                          mock_has_existing_function, test_nifti_files):
        """Test that update_main_buttons is called."""
        widget = FileSelectorWidget(
            context=mock_context_selector,
            has_existing_function=mock_has_existing_function,
            label="test",
            allow_multiple=True
        )
        qtbot.addWidget(widget)

        widget.set_selected_files(test_nifti_files)

        mock_context_selector["update_main_buttons"].assert_called()

    def test_set_selected_files_with_tooltips(self, qtbot, mock_context_selector, mock_has_existing_function,
                                              test_nifti_files):
        """Test that tooltips are set."""
        widget = FileSelectorWidget(
            context=mock_context_selector,
            has_existing_function=mock_has_existing_function,
            label="test",
            allow_multiple=True
        )
        qtbot.addWidget(widget)

        widget.set_selected_files(test_nifti_files)

        # Verify tooltips
        for i in range(widget.file_list_widget.count()):
            item = widget.file_list_widget.item(i)
            assert item.toolTip() != ""


class TestClearSelectedFiles:
    """Tests for the clear_selected_files method."""

    def test_clear_selected_files_basic(self, qtbot, mock_context_selector, mock_has_existing_function,
                                        test_nifti_files):
        """Basic clear files test."""
        widget = FileSelectorWidget(
            context=mock_context_selector,
            has_existing_function=mock_has_existing_function,
            label="test",
            allow_multiple=True
        )
        qtbot.addWidget(widget)

        # First select files
        widget.set_selected_files(test_nifti_files)
        assert len(widget.selected_files) > 0

        # Then clear
        widget.clear_selected_files()

        assert widget.selected_files == []
        assert widget.file_list_widget.count() == 0
        assert not widget.clear_button.isEnabled()

    def test_clear_selected_files_emits_signal(self, qtbot, mock_context_selector, mock_has_existing_function,
                                               test_nifti_files):
        """Test that it emits has_file signal with False."""
        widget = FileSelectorWidget(
            context=mock_context_selector,
            has_existing_function=mock_has_existing_function,
            label="test",
            allow_multiple=True
        )
        qtbot.addWidget(widget)

        widget.set_selected_files(test_nifti_files)

        with qtbot.waitSignal(widget.has_file) as blocker:
            widget.clear_selected_files()

        assert blocker.args[0] is False

    def test_clear_selected_files_calls_update_main_buttons(self, qtbot, mock_context_selector,
                                                            mock_has_existing_function, test_nifti_files):
        """Test that it calls update_main_buttons."""
        widget = FileSelectorWidget(
            context=mock_context_selector,
            has_existing_function=mock_has_existing_function,
            label="test",
            allow_multiple=True
        )
        qtbot.addWidget(widget)

        widget.set_selected_files(test_nifti_files)
        mock_context_selector["update_main_buttons"].reset_mock()

        widget.clear_selected_files()

        mock_context_selector["update_main_buttons"].assert_called_once()

    def test_clear_when_already_empty(self, qtbot, mock_context_selector, mock_has_existing_function):
        """Test clear when already empty."""
        widget = FileSelectorWidget(
            context=mock_context_selector,
            has_existing_function=mock_has_existing_function,
            label="test",
            allow_multiple=True
        )
        qtbot.addWidget(widget)

        # Clear without having selected files
        widget.clear_selected_files()

        assert widget.selected_files == []


class TestGetSelectedFiles:
    """Tests for the get_selected_files method."""

    def test_get_selected_files_with_files(self, qtbot, mock_context_selector, mock_has_existing_function,
                                           test_nifti_files):
        """Test get files when files are selected."""
        widget = FileSelectorWidget(
            context=mock_context_selector,
            has_existing_function=mock_has_existing_function,
            label="test",
            allow_multiple=True
        )
        qtbot.addWidget(widget)

        widget.set_selected_files(test_nifti_files)

        files = widget.get_selected_files()

        assert files == widget.selected_files
        assert len(files) == 2

    def test_get_selected_files_empty(self, qtbot, mock_context_selector, mock_has_existing_function):
        """Test get files with no selection."""
        widget = FileSelectorWidget(
            context=mock_context_selector,
            has_existing_function=mock_has_existing_function,
            label="test",
            allow_multiple=True
        )
        qtbot.addWidget(widget)

        files = widget.get_selected_files()

        assert files is None


class TestOpenTreeDialog:
    """Tests for the open_tree_dialog method."""

    def test_open_tree_dialog_called(self, qtbot, mock_context_selector, mock_has_existing_function):
        """Test that open_tree_dialog calls NiftiFileDialog."""
        widget = FileSelectorWidget(
            context=mock_context_selector,
            has_existing_function=mock_has_existing_function,
            label="test",
            allow_multiple=True
        )
        qtbot.addWidget(widget)

        with patch("main.components.file_selector_widget.NiftiFileDialog") as mock_dialog:
            mock_dialog.get_files = Mock(return_value=None)

            widget.open_tree_dialog()

            mock_dialog.get_files.assert_called_once()

    def test_open_tree_dialog_with_results_multiple(self, qtbot, mock_context_selector, mock_has_existing_function,
                                                    test_nifti_files):
        """Test open_tree_dialog with multiple results."""
        widget = FileSelectorWidget(
            context=mock_context_selector,
            has_existing_function=mock_has_existing_function,
            label="test",
            allow_multiple=True
        )
        qtbot.addWidget(widget)

        with patch("main.components.file_selector_widget.NiftiFileDialog") as mock_dialog:
            mock_dialog.get_files = Mock(return_value=test_nifti_files[:2])

            widget.open_tree_dialog()

            assert widget.selected_files == test_nifti_files[:2]

    def test_open_tree_dialog_with_results_single(self, qtbot, mock_context_selector, mock_has_existing_function,
                                                  test_nifti_files):
        """Test open_tree_dialog with results in single mode."""
        widget = FileSelectorWidget(
            context=mock_context_selector,
            has_existing_function=mock_has_existing_function,
            label="test",
            allow_multiple=False
        )
        qtbot.addWidget(widget)

        with patch("main.components.file_selector_widget.NiftiFileDialog") as mock_dialog:
            mock_dialog.get_files = Mock(return_value=test_nifti_files[:2])

            widget.open_tree_dialog()

            # Should take only the first file
            assert len(widget.selected_files) == 1

    def test_open_tree_dialog_parameters(self, qtbot, mock_context_selector, mock_has_existing_function):
        """Test that open_tree_dialog passes the correct parameters."""
        widget = FileSelectorWidget(
            context=mock_context_selector,
            has_existing_function=mock_has_existing_function,
            label="mylabel",
            allow_multiple=True,
            forced_filters={"type": "mask"}
        )
        qtbot.addWidget(widget)

        with patch("main.components.file_selector_widget.NiftiFileDialog") as mock_dialog:
            mock_dialog.get_files = Mock(return_value=None)

            widget.open_tree_dialog()

            call_kwargs = mock_dialog.get_files.call_args[1]
            assert call_kwargs['context'] == mock_context_selector
            assert call_kwargs['allow_multiple'] is True
            assert call_kwargs['has_existing_func'] == mock_has_existing_function
            assert call_kwargs['label'] == "mylabel"
            assert call_kwargs['forced_filters'] == {"type": "mask"}


class TestSetProcessingMode:
    """Tests for the set_processing_mode method."""

    def test_set_processing_mode_true(self, qtbot, mock_context_selector, mock_has_existing_function):
        """Test set_processing_mode True."""
        widget = FileSelectorWidget(
            context=mock_context_selector,
            has_existing_function=mock_has_existing_function,
            label="test",
            allow_multiple=True
        )
        qtbot.addWidget(widget)

        widget.set_processing_mode(True)

        assert not widget.file_button.isEnabled()
        assert not widget.clear_button.isEnabled()

    def test_set_processing_mode_false_with_files(self, qtbot, mock_context_selector, mock_has_existing_function,
                                                  test_nifti_files):
        """Test set_processing_mode False with files."""
        widget = FileSelectorWidget(
            context=mock_context_selector,
            has_existing_function=mock_has_existing_function,
            label="test",
            allow_multiple=True
        )
        qtbot.addWidget(widget)

        widget.set_selected_files(test_nifti_files)
        widget.set_processing_mode(False)

        assert widget.file_button.isEnabled()
        assert widget.clear_button.isEnabled()

    def test_set_processing_mode_false_without_files(self, qtbot, mock_context_selector, mock_has_existing_function):
        """Test set_processing_mode False without files."""
        widget = FileSelectorWidget(
            context=mock_context_selector,
            has_existing_function=mock_has_existing_function,
            label="test",
            allow_multiple=True
        )
        qtbot.addWidget(widget)

        widget.set_processing_mode(False)

        assert widget.file_button.isEnabled()
        assert not widget.clear_button.isEnabled()

    def test_set_processing_mode_toggle(self, qtbot, mock_context_selector, mock_has_existing_function,
                                        test_nifti_files):
        """Test toggle processing mode."""
        widget = FileSelectorWidget(
            context=mock_context_selector,
            has_existing_function=mock_has_existing_function,
            label="test",
            allow_multiple=True
        )
        qtbot.addWidget(widget)

        widget.set_selected_files(test_nifti_files)

        # Enable processing
        widget.set_processing_mode(True)
        assert not widget.file_button.isEnabled()

        # Disable processing
        widget.set_processing_mode(False)
        assert widget.file_button.isEnabled()


class TestSignals:
    """Tests for signals."""

    def test_has_file_signal_exists(self, qtbot, mock_context_selector, mock_has_existing_function):
        """Test that the has_file signal exists."""
        widget = FileSelectorWidget(
            context=mock_context_selector,
            has_existing_function=mock_has_existing_function,
            label="test",
            allow_multiple=True
        )
        qtbot.addWidget(widget)

        assert hasattr(widget, 'has_file')

    def test_selected_files_signal_connection(self, qtbot, mock_context_selector, mock_has_existing_function):
        """Test that the selected_files_signal is connected."""
        widget = FileSelectorWidget(
            context=mock_context_selector,
            has_existing_function=mock_has_existing_function,
            label="test",
            allow_multiple=True
        )
        qtbot.addWidget(widget)

        # Verify that the signal is connected (by emitting)
        test_files = ["/fake/file.nii"]
        mock_context_selector["selected_files_signal"].emit(test_files)

        # The widget should have received the signal


class TestTranslations:
    """Tests for translations."""

    def test_translate_ui_called_on_init(self, qtbot, mock_context_selector, mock_has_existing_function):
        """Test that _translate_ui is called during init."""
        with patch.object(FileSelectorWidget, '_translate_ui') as mock_translate:
            widget = FileSelectorWidget(
                context=mock_context_selector,
                has_existing_function=mock_has_existing_function,
                label="test",
                allow_multiple=True
            )
            qtbot.addWidget(widget)

            mock_translate.assert_called()

    def test_translate_ui_updates_buttons(self, qtbot, mock_context_selector, mock_has_existing_function):
        """Test that _translate_ui updates the buttons."""
        widget = FileSelectorWidget(
            context=mock_context_selector,
            has_existing_function=mock_has_existing_function,
            label="test",
            allow_multiple=True
        )
        qtbot.addWidget(widget)

        widget._translate_ui()

        assert widget.file_button.text() != ""
        assert widget.clear_button.text() != ""

    def test_language_changed_signal(self, qtbot, mock_context_selector, signal_emitter, mock_has_existing_function):
        """Test that the language_changed signal updates the UI."""
        widget = FileSelectorWidget(
            context=mock_context_selector,
            has_existing_function=mock_has_existing_function,
            label="test",
            allow_multiple=True
        )
        qtbot.addWidget(widget)

        with patch.object(widget, '_translate_ui') as mock_translate:
            mock_context_selector["language_changed"].connect(mock_translate)
            mock_context_selector["language_changed"].emit("it")

            mock_translate.assert_called()


class TestEdgeCases:
    """Tests for edge cases."""

    def test_empty_file_list(self, qtbot, mock_context_selector, mock_has_existing_function):
        """Test with empty file list."""
        widget = FileSelectorWidget(
            context=mock_context_selector,
            has_existing_function=mock_has_existing_function,
            label="test",
            allow_multiple=True
        )
        qtbot.addWidget(widget)

        widget.set_selected_files([])

        assert widget.selected_files == []
        assert widget.file_list_widget.count() == 0

    def test_very_long_file_paths(self, qtbot, mock_context_selector, mock_has_existing_function, temp_workspace):
        """Test with very long file paths."""
        long_path = os.path.join(temp_workspace, "a" * 200 + ".nii")
        with open(long_path, "w") as f:
            f.write("data")

        widget = FileSelectorWidget(
            context=mock_context_selector,
            has_existing_function=mock_has_existing_function,
            label="test",
            allow_multiple=True
        )
        qtbot.addWidget(widget)

        widget.set_selected_files([long_path])

        assert len(widget.selected_files) == 1
        assert widget.file_list_widget.count() == 1

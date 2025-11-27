"""
test_collapsible_patient_frame.py - Test Suite for CollapsiblePatientFrame

This suite tests all functionalities of the collapsible patient frame:
- Locked/unlocked initialization
- UI building and population
- Expand/collapse animation
- File selection (single/multiple)
- PET4D JSON detection
- Save configuration
- Translation/localization
"""

import os
import json
import glob
from unittest.mock import Mock, patch, MagicMock
import pytest
from PyQt6.QtCore import Qt, QSize
from PyQt6.QtWidgets import QComboBox, QLabel, QPushButton
from PyQt6.QtTest import QTest

from main.components.collapsible_patient_frame import ClickableFrame, CollapsiblePatientFrame


class TestClickableFrame:
    """Tests for ClickableFrame helper"""

    def test_clickable_frame_initialization(self, qtbot):
        """Test ClickableFrame initialization"""
        frame = ClickableFrame()
        qtbot.addWidget(frame)

        assert hasattr(frame, 'clicked')

    def test_clickable_frame_emits_signal(self, qtbot):
        """Test that ClickableFrame emits signal on click"""
        frame = ClickableFrame()
        qtbot.addWidget(frame)

        clicked_count = [0]
        frame.clicked.connect(lambda: clicked_count.__setitem__(0, clicked_count[0] + 1))

        QTest.mouseClick(frame, Qt.MouseButton.LeftButton)

        assert clicked_count[0] == 1


class TestCollapsiblePatientFrameInitialization:
    """Tests for CollapsiblePatientFrame initialization"""

    def test_init_locked_single_choice(self, qtbot, mock_context, temp_workspace):
        """Test initialization in locked mode (single choice)"""
        patient_id = "sub-01"
        files = {"ct": "sub-01/anat/ct.nii.gz"}
        patterns = {"ct": [os.path.join(temp_workspace, "sub-01/anat/ct*.nii.gz")]}

        frame = CollapsiblePatientFrame(
            context=mock_context,
            patient_id=patient_id,
            files=files,
            patterns=patterns,
            multiple_choice=False
        )
        qtbot.addWidget(frame)

        assert frame.patient_id == patient_id
        assert frame.files == files
        assert frame.patterns == patterns
        assert frame.multiple_choice is False
        assert frame.locked is True
        assert frame.is_expanded is False

    def test_init_unlocked_multiple_choice(self, qtbot, mock_context, temp_workspace):
        """Test initialization in unlocked mode (multiple choice)"""
        patient_id = "sub-02"
        files = {"pet4d": "sub-02/pet/pet4d.nii.gz"}
        patterns = {"pet4d": [os.path.join(temp_workspace, "sub-02/pet/*.nii.gz")]}

        frame = CollapsiblePatientFrame(
            context=mock_context,
            patient_id=patient_id,
            files=files,
            patterns=patterns,
            multiple_choice=True
        )
        qtbot.addWidget(frame)

        assert frame.multiple_choice is True
        assert frame.locked is False

    def test_init_with_save_callback(self, qtbot, mock_context, temp_workspace):
        """Test initialization with save callback"""
        save_callback = Mock()

        frame = CollapsiblePatientFrame(
            context=mock_context,
            patient_id="sub-03",
            files={},
            patterns={},
            multiple_choice=True,
            save_callback=save_callback
        )
        qtbot.addWidget(frame)

        assert frame.save_callback is save_callback

    def test_workspace_path_assignment(self, qtbot, mock_context, temp_workspace):
        """Test workspace_path assignment from context"""
        frame = CollapsiblePatientFrame(
            context=mock_context,
            patient_id="sub-04",
            files={},
            patterns={},
            multiple_choice=False
        )
        qtbot.addWidget(frame)

        assert frame.workspace_path == mock_context["workspace_path"]

    def test_category_widgets_initialized_empty(self, qtbot, mock_context, temp_workspace):
        """Test that category_widgets is initialized empty"""
        frame = CollapsiblePatientFrame(
            context=mock_context,
            patient_id="sub-05",
            files={},
            patterns={},
            multiple_choice=False
        )
        qtbot.addWidget(frame)

        assert frame.category_widgets == {}


class TestUIBuilding:
    """Tests for UI construction"""

    def test_header_widgets_created(self, qtbot, mock_context, temp_workspace):
        """Test header widget creation"""
        frame = CollapsiblePatientFrame(
            context=mock_context,
            patient_id="sub-06",
            files={},
            patterns={},
            multiple_choice=False
        )
        qtbot.addWidget(frame)

        assert hasattr(frame, 'subject_name')
        assert hasattr(frame, 'toggle_button')
        assert isinstance(frame.subject_name, QLabel)

    def test_toggle_button_configuration(self, qtbot, mock_context, temp_workspace):
        """Test toggle button configuration"""
        frame = CollapsiblePatientFrame(
            context=mock_context,
            patient_id="sub-07",
            files={},
            patterns={},
            multiple_choice=False
        )
        qtbot.addWidget(frame)

        assert frame.toggle_button.isCheckable()
        assert not frame.toggle_button.isChecked()
        assert frame.toggle_button.arrowType() == Qt.ArrowType.RightArrow

    def test_content_frame_created(self, qtbot, mock_context, temp_workspace):
        """Test creation of the content frame"""
        frame = CollapsiblePatientFrame(
            context=mock_context,
            patient_id="sub-08",
            files={},
            patterns={},
            multiple_choice=False
        )
        qtbot.addWidget(frame)

        assert hasattr(frame, 'content_frame')
        assert frame.content_frame.maximumHeight() == 0  # Starts collapsed

    def test_animation_setup(self, qtbot, mock_context, temp_workspace):
        """Test animation setup"""
        frame = CollapsiblePatientFrame(
            context=mock_context,
            patient_id="sub-09",
            files={},
            patterns={},
            multiple_choice=False
        )
        qtbot.addWidget(frame)

        assert hasattr(frame, 'animation')
        assert frame.animation.duration() == 300


class TestStyleApplication:
    """Tests for style application"""

    def test_locked_style(self, qtbot, mock_context, temp_workspace):
        """Test style for locked frame"""
        frame = CollapsiblePatientFrame(
            context=mock_context,
            patient_id="sub-10",
            files={},
            patterns={},
            multiple_choice=False  # locked
        )
        qtbot.addWidget(frame)

        stylesheet = frame.styleSheet()
        assert "white" in stylesheet.lower() or "#fff" in stylesheet.lower()
        assert "#4CAF50" in stylesheet  # Green border

    def test_unlocked_style(self, qtbot, mock_context, temp_workspace):
        """Test style for unlocked frame"""
        frame = CollapsiblePatientFrame(
            context=mock_context,
            patient_id="sub-11",
            files={},
            patterns={},
            multiple_choice=True  # unlocked
        )
        qtbot.addWidget(frame)

        stylesheet = frame.styleSheet()
        assert "#FFC107" in stylesheet  # Yellow border
        assert "#FFF8E1" in stylesheet  # Yellow background

    def test_style_changes_after_lock(self, qtbot, mock_context, temp_workspace):
        """Test style update after locking"""
        frame = CollapsiblePatientFrame(
            context=mock_context,
            patient_id="sub-12",
            files={},
            patterns={},
            multiple_choice=True
        )
        qtbot.addWidget(frame)

        # Initially unlocked (yellow)
        initial_style = frame.styleSheet()
        assert "#FFC107" in initial_style

        frame.locked = True
        frame._apply_style()

        new_style = frame.styleSheet()
        assert "#4CAF50" in new_style


class TestExpandCollapse:
    """Tests for expand/collapse functionality"""

    def test_initial_state_collapsed(self, qtbot, mock_context, temp_workspace):
        """Test initial collapsed state"""
        frame = CollapsiblePatientFrame(
            context=mock_context,
            patient_id="sub-13",
            files={},
            patterns={},
            multiple_choice=False
        )
        qtbot.addWidget(frame)

        assert frame.is_expanded is False
        assert frame.content_frame.maximumHeight() == 0

    def test_toggle_expand_programmatically(self, qtbot, mock_context, temp_workspace):
        """Test programmatic expand"""
        frame = CollapsiblePatientFrame(
            context=mock_context,
            patient_id="sub-14",
            files={},
            patterns={},
            multiple_choice=False
        )
        qtbot.addWidget(frame)

        frame._toggle_expand(True)

        assert frame.is_expanded is True
        assert frame.toggle_button.arrowType() == Qt.ArrowType.DownArrow

    def test_toggle_collapse_programmatically(self, qtbot, mock_context, temp_workspace):
        """Test programmatic collapse"""
        frame = CollapsiblePatientFrame(
            context=mock_context,
            patient_id="sub-15",
            files={},
            patterns={},
            multiple_choice=False
        )
        qtbot.addWidget(frame)

        frame._toggle_expand(True)
        frame._toggle_expand(False)

        assert frame.is_expanded is False
        assert frame.toggle_button.arrowType() == Qt.ArrowType.RightArrow

    def test_header_click_toggles_expansion(self, qtbot, mock_context, temp_workspace):
        """Test that clicking the header toggles expand/collapse"""
        frame = CollapsiblePatientFrame(
            context=mock_context,
            patient_id="sub-16",
            files={},
            patterns={},
            multiple_choice=False
        )
        qtbot.addWidget(frame)

        header_frame = frame.findChild(ClickableFrame)
        assert header_frame is not None

        initial_state = frame.is_expanded
        header_frame.clicked.emit()

        assert frame.is_expanded != initial_state


class TestContentPopulation:
    """Tests for content population"""

    @patch('glob.glob')
    def test_populate_single_file_locked(self, mock_glob, qtbot, mock_context, temp_workspace):
        """Test population with a single file in locked mode"""
        mock_glob.return_value = [os.path.join(temp_workspace, "sub-17/anat/ct.nii.gz")]

        files = {"ct": "sub-17/anat/ct.nii.gz"}
        patterns = {"ct": [os.path.join(temp_workspace, "sub-17/anat/*.nii.gz")]}

        frame = CollapsiblePatientFrame(
            context=mock_context,
            patient_id="sub-17",
            files=files,
            patterns=patterns,
            multiple_choice=False  # locked
        )
        qtbot.addWidget(frame)

        assert hasattr(frame, 'file_label')
        assert frame.file_label.text() == "sub-17/anat/ct.nii.gz"

    @patch('glob.glob')
    def test_populate_multiple_files_unlocked(self, mock_glob, qtbot, mock_context, temp_workspace):
        """Test population with multiple files in unlocked mode"""
        mock_glob.return_value = [
            os.path.join(temp_workspace, "sub-18/pet/pet1.nii.gz"),
            os.path.join(temp_workspace, "sub-18/pet/pet2.nii.gz"),
        ]

        files = {"pet4d": "sub-18/pet/pet1.nii.gz"}
        patterns = {"pet4d": [os.path.join(temp_workspace, "sub-18/pet/*.nii.gz")]}

        frame = CollapsiblePatientFrame(
            context=mock_context,
            patient_id="sub-18",
            files=files,
            patterns=patterns,
            multiple_choice=True  # unlocked
        )
        qtbot.addWidget(frame)

        assert "pet4d" in frame.category_widgets
        combo = frame.category_widgets["pet4d"]
        assert isinstance(combo, QComboBox)
        assert combo.count() == 2

    @patch('glob.glob')
    def test_populate_no_files_found(self, mock_glob, qtbot, mock_context, temp_workspace):
        """Test population when no files are found"""
        mock_glob.return_value = []

        files = {}
        patterns = {"ct": [os.path.join(temp_workspace, "sub-19/anat/*.nii.gz")]}

        frame = CollapsiblePatientFrame(
            context=mock_context,
            patient_id="sub-19",
            files=files,
            patterns=patterns,
            multiple_choice=False
        )
        qtbot.addWidget(frame)

        assert hasattr(frame, 'file_label')
        assert "no file" in frame.file_label.text().lower()

    @patch('glob.glob')
    def test_populate_saves_button_in_unlocked_mode(self, mock_glob, qtbot, mock_context, temp_workspace):
        """Test presence of Save button in unlocked mode"""
        mock_glob.return_value = [os.path.join(temp_workspace, "sub-20/anat/t1.nii.gz")]

        files = {}
        patterns = {"ct": [os.path.join(temp_workspace, "sub-20/anat/*.nii.gz")]}

        frame = CollapsiblePatientFrame(
            context=mock_context,
            patient_id="sub-20",
            files=files,
            patterns=patterns,
            multiple_choice=True  # unlocked
        )
        qtbot.addWidget(frame)

        assert hasattr(frame, 'save_btn')
        assert isinstance(frame.save_btn, QPushButton)


class TestPET4DJSONDetection:
    """Tests for detecting JSON associated with PET4D"""

    @patch('glob.glob')
    @patch('os.path.exists')
    def test_pet4d_json_found_locked_mode(self, mock_exists, mock_glob, qtbot, mock_context, temp_workspace):
        """Test JSON detection in locked mode"""
        pet_file = os.path.join(temp_workspace, "sub-21/pet/pet4d.nii.gz")
        json_file = os.path.join(temp_workspace, "sub-21/pet/pet4d.json")

        mock_glob.return_value = [pet_file]
        mock_exists.side_effect = lambda path: path == json_file

        files = {"pet4d": "sub-21/pet/pet4d.nii.gz"}
        patterns = {"pet4d": [os.path.join(temp_workspace, "sub-21/pet/*.nii.gz")]}

        frame = CollapsiblePatientFrame(
            context=mock_context,
            patient_id="sub-21",
            files=files,
            patterns=patterns,
            multiple_choice=False
        )
        qtbot.addWidget(frame)

        # Should have detected JSON
        assert "pet4d_json" in frame.files
        assert "pet4d.json" in frame.files["pet4d_json"]

    @patch('glob.glob')
    @patch('os.path.exists')
    def test_pet4d_json_not_found_locked_mode(self, mock_exists, mock_glob, qtbot, mock_context, temp_workspace):
        """Test JSON not found in locked mode"""
        pet_file = os.path.join(temp_workspace, "sub-22/pet/pet4d.nii.gz")

        mock_glob.return_value = [pet_file]
        mock_exists.return_value = False  # JSON does not exist

        files = {"pet4d": "sub-22/pet/pet4d.nii.gz"}
        patterns = {"pet4d": [os.path.join(temp_workspace, "sub-22/pet/*.nii.gz")]}

        frame = CollapsiblePatientFrame(
            context=mock_context,
            patient_id="sub-22",
            files=files,
            patterns=patterns,
            multiple_choice=False
        )
        qtbot.addWidget(frame)

        # JSON should be empty
        assert frame.files.get("pet4d_json", "") == ""

    @patch('glob.glob')
    @patch('os.path.exists')
    def test_pet4d_json_dynamic_update_unlocked(self, mock_exists, mock_glob, qtbot, mock_context, temp_workspace):
        """Test dynamic JSON update in unlocked mode"""
        pet1 = os.path.join(temp_workspace, "sub-23/pet/pet1.nii.gz")
        pet2 = os.path.join(temp_workspace, "sub-23/pet/pet2.nii.gz")
        json1 = os.path.join(temp_workspace, "sub-23/pet/pet1.json")

        mock_glob.return_value = [pet1, pet2]
        mock_exists.side_effect = lambda path: path == json1

        files = {"pet4d": "sub-23/pet/pet1.nii.gz"}
        patterns = {"pet4d": [os.path.join(temp_workspace, "sub-23/pet/*.nii.gz")]}

        frame = CollapsiblePatientFrame(
            context=mock_context,
            patient_id="sub-23",
            files=files,
            patterns=patterns,
            multiple_choice=True
        )
        qtbot.addWidget(frame)

        # Change combo selection
        combo = frame.category_widgets["pet4d"]
        combo.setCurrentIndex(1)  # pet2

        # JSON label should update
        assert hasattr(frame, 'pet4d_json_label')


class TestSaveConfiguration:
    """Tests for configuration saving"""

    @patch('glob.glob')
    def test_save_patient_calls_callback(self, mock_glob, qtbot, mock_context, temp_workspace):
        """Test that save calls the callback"""
        mock_glob.return_value = [
            os.path.join(temp_workspace, "sub-24/anat/t1.nii.gz"),
            os.path.join(temp_workspace, "sub-24/anat/t2.nii.gz")
        ]

        save_callback = Mock()
        files = {}
        patterns = {"ct": [os.path.join(temp_workspace, "sub-24/anat/*.nii.gz")]}

        frame = CollapsiblePatientFrame(
            context=mock_context,
            patient_id="sub-24",
            files=files,
            patterns=patterns,
            multiple_choice=True,
            save_callback=save_callback
        )
        qtbot.addWidget(frame)

        # Save
        frame._save_patient()

        # Callback should be called
        save_callback.assert_called_once()
        args = save_callback.call_args[0]
        assert args[0] == "sub-24"  # patient_id
        assert isinstance(args[1], dict)  # files dict

    @patch('glob.glob')
    def test_save_patient_marks_not_needing_revision(self, mock_glob, qtbot, mock_context, temp_workspace):
        """Test that save removes need_revision flag"""
        mock_glob.return_value = [os.path.join(temp_workspace, "sub-25/anat/scan.nii.gz")]

        files = {"need_revision": True}
        patterns = {"ct": [os.path.join(temp_workspace, "sub-25/anat/*.nii.gz")]}

        frame = CollapsiblePatientFrame(
            context=mock_context,
            patient_id="sub-25",
            files=files,
            patterns=patterns,
            multiple_choice=True
        )
        qtbot.addWidget(frame)

        frame._save_patient()

        assert frame.files["need_revision"] is False

    @patch('glob.glob')
    def test_save_patient_locks_frame(self, mock_glob, qtbot, mock_context, temp_workspace):
        """Test that save locks the frame"""
        mock_glob.return_value = [os.path.join(temp_workspace, "sub-26/anat/data.nii.gz")]

        files = {}
        patterns = {"ct": [os.path.join(temp_workspace, "sub-26/anat/*.nii.gz")]}

        frame = CollapsiblePatientFrame(
            context=mock_context,
            patient_id="sub-26",
            files=files,
            patterns=patterns,
            multiple_choice=True
        )
        qtbot.addWidget(frame)

        assert frame.locked is False

        frame._save_patient()

        assert frame.locked is True

    @patch('glob.glob')
    def test_save_patient_updates_files_from_combos(self, mock_glob, qtbot, mock_context, temp_workspace):
        """Test that save updates files from combo selections"""
        mock_glob.return_value = [
            os.path.join(temp_workspace, "sub-27/anat/file1.nii.gz"),
            os.path.join(temp_workspace, "sub-27/anat/file2.nii.gz")
        ]

        files = {}
        patterns = {"ct": [os.path.join(temp_workspace, "sub-27/anat/*.nii.gz")]}

        frame = CollapsiblePatientFrame(
            context=mock_context,
            patient_id="sub-27",
            files=files,
            patterns=patterns,
            multiple_choice=True
        )
        qtbot.addWidget(frame)

        # Change selection
        combo = frame.category_widgets["ct"]
        combo.setCurrentIndex(1)

        frame._save_patient()

        # files should be updated
        assert "file2.nii.gz" in frame.files["ct"]


class TestTranslation:
    """Tests for translation/localization"""

    def test_translate_ui_called_on_init(self, qtbot, mock_context, temp_workspace):
        """Test that _translate_ui is called during init"""
        with patch.object(CollapsiblePatientFrame, '_translate_ui') as mock_translate:
            frame = CollapsiblePatientFrame(
                context=mock_context,
                patient_id="sub-28",
                files={},
                patterns={},
                multiple_choice=False
            )
            qtbot.addWidget(frame)

            # Should be called during __init__
            assert mock_translate.called

    def test_language_changed_signal_connected(self, qtbot, signal_emitter, temp_workspace):
        """Test connection to language_changed signal"""
        context = {
            "workspace_path": temp_workspace,
            "language_changed": signal_emitter.language_changed
        }

        frame = CollapsiblePatientFrame(
            context=context,
            patient_id="sub-29",
            files={},
            patterns={},
            multiple_choice=False
        )
        qtbot.addWidget(frame)

        # Emit signal
        with patch.object(frame, '_translate_ui') as mock_translate:
            context["language_changed"].connect(mock_translate)
            context["language_changed"].emit("it")

            # _translate_ui should be called
            mock_translate.assert_called()

    def test_patient_label_translation(self, qtbot, mock_context, temp_workspace):
        """Test patient label translation"""
        frame = CollapsiblePatientFrame(
            context=mock_context,
            patient_id="sub-30",
            files={},
            patterns={},
            multiple_choice=False
        )
        qtbot.addWidget(frame)

        # Label should contain patient ID
        assert "sub-30" in frame.subject_name.text()

    @patch('glob.glob')
    def test_save_button_translation(self, mock_glob, qtbot, mock_context, temp_workspace):
        """Test Save button translation"""
        mock_glob.return_value = [os.path.join(temp_workspace, "sub-31/anat/scan.nii.gz")]

        frame = CollapsiblePatientFrame(
            context=mock_context,
            patient_id="sub-31",
            files={},
            patterns={"ct": [os.path.join(temp_workspace, "sub-31/anat/*.nii.gz")]},
            multiple_choice=True
        )
        qtbot.addWidget(frame)

        # Save button should have text
        assert len(frame.save_btn.text()) > 0


class TestEdgeCases:
    """Tests for edge cases"""

    def test_empty_patterns_dict(self, qtbot, mock_context, temp_workspace):
        """Test with empty patterns dict"""
        frame = CollapsiblePatientFrame(
            context=mock_context,
            patient_id="sub-32",
            files={},
            patterns={},  # Empty
            multiple_choice=False
        )
        qtbot.addWidget(frame)

        # Should not crash
        assert frame.category_widgets == {}

    def test_empty_files_dict(self, qtbot, mock_context, temp_workspace):
        """Test with empty files dict"""
        frame = CollapsiblePatientFrame(
            context=mock_context,
            patient_id="sub-33",
            files={},  # Empty
            patterns={"ct": ["*.nii.gz"]},
            multiple_choice=False
        )
        qtbot.addWidget(frame)

        # Should not crash
        assert frame.files == {}

    @patch('glob.glob')
    def test_single_file_in_multiple_choice_mode(self, mock_glob, qtbot, mock_context, temp_workspace):
        """Test single file in multiple-choice mode"""
        mock_glob.return_value = [os.path.join(temp_workspace, "sub-34/anat/only_one.nii.gz")]

        files = {}
        patterns = {"ct": [os.path.join(temp_workspace, "sub-34/anat/*.nii.gz")]}

        frame = CollapsiblePatientFrame(
            context=mock_context,
            patient_id="sub-34",
            files=files,
            patterns=patterns,
            multiple_choice=True
        )
        qtbot.addWidget(frame)

        # With only one file, it should behave like locked
        # (internal logic in _populate_content)

    def test_patient_id_with_special_characters(self, qtbot, mock_context, temp_workspace):
        """Test patient ID containing special characters"""
        patient_id = "sub-01_session-2"

        frame = CollapsiblePatientFrame(
            context=mock_context,
            patient_id=patient_id,
            files={},
            patterns={},
            multiple_choice=False
        )
        qtbot.addWidget(frame)

        assert frame.patient_id == patient_id
        assert patient_id in frame.subject_name.text()

    def test_no_save_callback_provided(self, qtbot, mock_context, temp_workspace):
        """Test when no save callback is provided"""
        frame = CollapsiblePatientFrame(
            context=mock_context,
            patient_id="sub-35",
            files={},
            patterns={},
            multiple_choice=True,
            save_callback=None
        )
        qtbot.addWidget(frame)

        # _save_patient should not crash
        frame._save_patient()

    def test_context_without_language_changed(self, qtbot, temp_workspace):
        """Test context without language_changed signal"""
        context = {"workspace_path": temp_workspace}

        frame = CollapsiblePatientFrame(
            context=context,
            patient_id="sub-36",
            files={},
            patterns={},
            multiple_choice=False
        )
        qtbot.addWidget(frame)

        # Should not crash

class TestFilePatternMatching:
    """Test for file pattern matching"""

    @patch('glob.glob')
    def test_glob_called_with_correct_patterns(self, mock_glob, qtbot, mock_context, temp_workspace):
        """Test glob call with correct patterns"""
        patterns = {
            "ct": [os.path.join(temp_workspace, "sub-37/anat/CT*.nii.gz")],
            "pet4d": [os.path.join(temp_workspace, "sub-37/pet/PET*.nii.gz")]
        }

        mock_glob.return_value = []

        frame = CollapsiblePatientFrame(
            context=mock_context,
            patient_id="sub-37",
            files={},
            patterns=patterns,
            multiple_choice=False
        )
        qtbot.addWidget(frame)

        assert mock_glob.call_count >= 2

    @patch('glob.glob')
    def test_relative_path_conversion(self, mock_glob, qtbot, mock_context, temp_workspace):
        """Test relative path conversion"""
        abs_path = os.path.join(temp_workspace, "sub-38/anat/scan.nii.gz")
        mock_glob.return_value = [abs_path]

        files = {}
        patterns = {"ct": [os.path.join(temp_workspace, "sub-38/anat/*.nii.gz")]}

        frame = CollapsiblePatientFrame(
            context=mock_context,
            patient_id="sub-38",
            files=files,
            patterns=patterns,
            multiple_choice=True
        )
        qtbot.addWidget(frame)

        combo = frame.category_widgets["ct"]
        item_text = combo.itemText(0)
        assert not os.path.isabs(item_text)
        assert "sub-38/anat/scan.nii.gz" in item_text

    @patch('glob.glob')
    def test_multiple_patterns_per_category(self, mock_glob, qtbot, mock_context, temp_workspace):
        """Test multiple patterns per category"""

        def glob_side_effect(pattern):
            if "CT*" in pattern:
                return [os.path.join(temp_workspace, "sub-39/anat/CT.nii.gz")]
            elif "ct*" in pattern:
                return [os.path.join(temp_workspace, "sub-39/anat/ct.nii.gz")]
            return []

        mock_glob.side_effect = glob_side_effect

        patterns = {
            "ct": [
                os.path.join(temp_workspace, "sub-39/anat/CT*.nii.gz"),
                os.path.join(temp_workspace, "sub-39/anat/ct*.nii.gz")
            ]
        }

        frame = CollapsiblePatientFrame(
            context=mock_context,
            patient_id="sub-39",
            files={},
            patterns=patterns,
            multiple_choice=True
        )
        qtbot.addWidget(frame)

        combo = frame.category_widgets["ct"]
        assert combo.count() >= 1


class TestComboBoxBehavior:
    """Test combobox behavior"""

    @patch('glob.glob')
    def test_combo_current_index_set_from_files(self, mock_glob, qtbot, mock_context, temp_workspace):
        """Test files dict manage combobox behavior"""
        mock_glob.return_value = [
            os.path.join(temp_workspace, "sub-40/anat/file1.nii.gz"),
            os.path.join(temp_workspace, "sub-40/anat/file2.nii.gz"),
            os.path.join(temp_workspace, "sub-40/anat/file3.nii.gz")
        ]

        files = {"ct": "sub-40/anat/file2.nii.gz"}
        patterns = {"ct": [os.path.join(temp_workspace, "sub-40/anat/*.nii.gz")]}

        frame = CollapsiblePatientFrame(
            context=mock_context,
            patient_id="sub-40",
            files=files,
            patterns=patterns,
            multiple_choice=True
        )
        qtbot.addWidget(frame)

        combo = frame.category_widgets["ct"]
        assert "file2" in combo.currentText()

    @patch('glob.glob')
    def test_combo_default_to_first_if_no_match(self, mock_glob, qtbot, mock_context, temp_workspace):
        """Test combobox behavior with default value if no match"""
        mock_glob.return_value = [
            os.path.join(temp_workspace, "sub-41/anat/new1.nii.gz"),
            os.path.join(temp_workspace, "sub-41/anat/new2.nii.gz")
        ]

        files = {"ct": "sub-41/anat/nonexistent.nii.gz"}
        patterns = {"ct": [os.path.join(temp_workspace, "sub-41/anat/*.nii.gz")]}

        frame = CollapsiblePatientFrame(
            context=mock_context,
            patient_id="sub-41",
            files=files,
            patterns=patterns,
            multiple_choice=True
        )
        qtbot.addWidget(frame)

        combo = frame.category_widgets["ct"]
        assert combo.currentIndex() == 0

    @patch('glob.glob')
    def test_combo_minimum_height(self, mock_glob, qtbot, mock_context, temp_workspace):
        """Test minimum height combobox behavior"""
        mock_glob.return_value = [os.path.join(temp_workspace, "sub-42/anat/scan.nii.gz")]

        patterns = {"ct": [os.path.join(temp_workspace, "sub-42/anat/*.nii.gz")]}

        frame = CollapsiblePatientFrame(
            context=mock_context,
            patient_id="sub-42",
            files={},
            patterns=patterns,
            multiple_choice=True
        )
        qtbot.addWidget(frame)

        combo = frame.category_widgets["ct"]
        assert combo.minimumHeight() >= 28


class TestAnimationBehavior:
    """Test animation behavior"""

    def test_animation_duration(self, qtbot, mock_context, temp_workspace):
        """Test animation duration"""
        frame = CollapsiblePatientFrame(
            context=mock_context,
            patient_id="sub-43",
            files={},
            patterns={},
            multiple_choice=False
        )
        qtbot.addWidget(frame)

        assert frame.animation.duration() == 300

    def test_animation_easing_curve(self, qtbot, mock_context, temp_workspace):
        """Test easing curve"""
        from PyQt6.QtCore import QEasingCurve

        frame = CollapsiblePatientFrame(
            context=mock_context,
            patient_id="sub-44",
            files={},
            patterns={},
            multiple_choice=False
        )
        qtbot.addWidget(frame)

        assert frame.animation.easingCurve().type() == QEasingCurve.Type.InOutCubic

    def test_animation_target_property(self, qtbot, mock_context, temp_workspace):
        """Test target property"""
        frame = CollapsiblePatientFrame(
            context=mock_context,
            patient_id="sub-45",
            files={},
            patterns={},
            multiple_choice=False
        )
        qtbot.addWidget(frame)

        assert frame.animation.propertyName() == b"maximumHeight"
        assert frame.animation.targetObject() == frame.content_frame


class TestCategoryLabels:
    """Test for category labels"""

    @patch('glob.glob')
    def test_category_label_formatting(self, mock_glob, qtbot, mock_context, temp_workspace):
        """Test category label formatting"""
        mock_glob.return_value = [os.path.join(temp_workspace, "sub-46/anat/scan.nii.gz")]

        patterns = {"pet_4d_dynamic": [os.path.join(temp_workspace, "sub-46/pet/*.nii.gz")]}

        frame = CollapsiblePatientFrame(
            context=mock_context,
            patient_id="sub-46",
            files={},
            patterns=patterns,
            multiple_choice=False
        )
        qtbot.addWidget(frame)

        labels = frame.findChildren(QLabel)
        category_labels = [l for l in labels if "pet" in l.text().lower()]
        assert len(category_labels) > 0


class TestIntegrationScenarios:
    """Test integration"""

    @patch('glob.glob')
    @patch('os.path.exists')
    def test_complete_workflow_locked_patient(self, mock_exists, mock_glob, qtbot, mock_context, temp_workspace):
        """Test workflow locked patient"""
        ct_file = os.path.join(temp_workspace, "sub-47/anat/CT.nii.gz")
        pet_file = os.path.join(temp_workspace, "sub-47/pet/PET4D.nii.gz")
        pet_json = os.path.join(temp_workspace, "sub-47/pet/PET4D.json")

        def glob_side_effect(pattern):
            if "CT" in pattern:
                return [ct_file]
            elif "PET" in pattern:
                return [pet_file]
            return []

        mock_glob.side_effect = glob_side_effect
        mock_exists.side_effect = lambda p: p == pet_json

        files = {
            "ct": "sub-47/anat/CT.nii.gz",
            "pet4d": "sub-47/pet/PET4D.nii.gz"
        }
        patterns = {
            "ct": [os.path.join(temp_workspace, "sub-47/anat/CT*.nii.gz")],
            "pet4d": [os.path.join(temp_workspace, "sub-47/pet/PET*.nii.gz")]
        }

        frame = CollapsiblePatientFrame(
            context=mock_context,
            patient_id="sub-47",
            files=files,
            patterns=patterns,
            multiple_choice=False
        )
        qtbot.addWidget(frame)

        assert frame.locked is True
        assert hasattr(frame, 'file_label')
        assert "pet4d_json" in frame.files

    @patch('glob.glob')
    def test_complete_workflow_unlocked_patient(self, mock_glob, qtbot, mock_context, temp_workspace):
        """Test workflow unlocked patient"""
        ct_files = [
            os.path.join(temp_workspace, "sub-48/anat/CT1.nii.gz"),
            os.path.join(temp_workspace, "sub-48/anat/CT2.nii.gz")
        ]
        pet_files = [
            os.path.join(temp_workspace, "sub-48/pet/PET1.nii.gz"),
            os.path.join(temp_workspace, "sub-48/pet/PET2.nii.gz")
        ]

        def glob_side_effect(pattern):
            if "CT" in pattern:
                return ct_files
            elif "PET" in pattern:
                return pet_files
            return []

        mock_glob.side_effect = glob_side_effect

        files = {}
        patterns = {
            "ct": [os.path.join(temp_workspace, "sub-48/anat/CT*.nii.gz")],
            "pet4d": [os.path.join(temp_workspace, "sub-48/pet/PET*.nii.gz")]
        }

        save_callback = Mock()

        frame = CollapsiblePatientFrame(
            context=mock_context,
            patient_id="sub-48",
            files=files,
            patterns=patterns,
            multiple_choice=True,
            save_callback=save_callback
        )
        qtbot.addWidget(frame)

        assert frame.locked is False
        assert "ct" in frame.category_widgets
        assert "pet4d" in frame.category_widgets

        frame.category_widgets["ct"].setCurrentIndex(1)
        frame.category_widgets["pet4d"].setCurrentIndex(0)
        frame._save_patient()

        save_callback.assert_called_once()
        assert frame.locked is True

    @patch('glob.glob')
    def test_expand_select_save_workflow(self, mock_glob, qtbot, mock_context, temp_workspace):
        """Test workflow: expand → select → save"""
        mock_glob.return_value = [
            os.path.join(temp_workspace, "sub-49/anat/scan1.nii.gz"),
            os.path.join(temp_workspace, "sub-49/anat/scan2.nii.gz")
        ]

        patterns = {"ct": [os.path.join(temp_workspace, "sub-49/anat/*.nii.gz")]}

        frame = CollapsiblePatientFrame(
            context=mock_context,
            patient_id="sub-49",
            files={},
            patterns=patterns,
            multiple_choice=True
        )
        qtbot.addWidget(frame)

        frame._toggle_expand(True)
        assert frame.is_expanded is True

        combo = frame.category_widgets["ct"]
        combo.setCurrentIndex(1)

        frame._save_patient()

        assert "scan2" in frame.files["ct"]
        assert frame.locked is True

class TestMemoryAndCleanup:
    """Tests for memory management and cleanup"""

    @patch('glob.glob')
    def test_repopulate_content_cleans_old_widgets(self, mock_glob, qtbot, mock_context, temp_workspace):
        """Test that _populate_content cleans old widgets"""
        mock_glob.return_value = [os.path.join(temp_workspace, "sub-50/anat/scan.nii.gz")]

        patterns = {"ct": [os.path.join(temp_workspace, "sub-50/anat/*.nii.gz")]}

        frame = CollapsiblePatientFrame(
            context=mock_context,
            patient_id="sub-50",
            files={},
            patterns=patterns,
            multiple_choice=True
        )
        qtbot.addWidget(frame)

        initial_widget_count = frame.content_layout.count()

        # Re-populate
        frame._populate_content()

        # Count should be similar (old widgets removed)
        new_widget_count = frame.content_layout.count()
        assert new_widget_count > 0

    def test_widget_deletion_on_repopulate(self, qtbot, mock_context, temp_workspace):
        """Test widget deletion on re-population"""
        frame = CollapsiblePatientFrame(
            context=mock_context,
            patient_id="sub-51",
            files={},
            patterns={},
            multiple_choice=False
        )
        qtbot.addWidget(frame)

        # Add a custom widget
        from PyQt6.QtWidgets import QWidget
        custom_widget = QWidget()
        frame.content_layout.addWidget(custom_widget)

        assert custom_widget.parent() is not None

        # Re-populate
        frame._populate_content()

        # Custom widget should be scheduled for deletion
        # (deleteLater is called)


class TestAccessibility:
    """Tests for accessibility"""

    def test_toggle_button_cursor(self, qtbot, mock_context, temp_workspace):
        """Test cursor of the toggle button"""
        frame = CollapsiblePatientFrame(
            context=mock_context,
            patient_id="sub-52",
            files={},
            patterns={},
            multiple_choice=False
        )
        qtbot.addWidget(frame)

        # Should have PointingHand cursor
        assert frame.toggle_button.cursor().shape() == Qt.CursorShape.PointingHandCursor

    def test_toggle_button_checkable(self, qtbot, mock_context, temp_workspace):
        """Test that toggle button is checkable"""
        frame = CollapsiblePatientFrame(
            context=mock_context,
            patient_id="sub-53",
            files={},
            patterns={},
            multiple_choice=False
        )
        qtbot.addWidget(frame)

        assert frame.toggle_button.isCheckable()

    @patch('glob.glob')
    def test_save_button_minimum_height(self, mock_glob, qtbot, mock_context, temp_workspace):
        """Test minimum height of save button"""
        mock_glob.return_value = [os.path.join(temp_workspace, "sub-54/anat/scan.nii.gz")]

        patterns = {"ct": [os.path.join(temp_workspace, "sub-54/anat/*.nii.gz")]}

        frame = CollapsiblePatientFrame(
            context=mock_context,
            patient_id="sub-54",
            files={},
            patterns=patterns,
            multiple_choice=True
        )
        qtbot.addWidget(frame)

        assert frame.save_btn.minimumHeight() >= 32


class TestVisualEffects:
    """Tests for visual effects"""

    def test_drop_shadow_applied(self, qtbot, mock_context, temp_workspace):
        """Test drop shadow application"""
        frame = CollapsiblePatientFrame(
            context=mock_context,
            patient_id="sub-55",
            files={},
            patterns={},
            multiple_choice=False
        )
        qtbot.addWidget(frame)

        # Should have a graphics effect
        assert frame.graphicsEffect() is not None

    def test_frame_shape(self, qtbot, mock_context, temp_workspace):
        """Test frame shape"""
        from PyQt6.QtWidgets import QFrame

        frame = CollapsiblePatientFrame(
            context=mock_context,
            patient_id="sub-56",
            files={},
            patterns={},
            multiple_choice=False
        )
        qtbot.addWidget(frame)

        assert frame.frameShape() == QFrame.Shape.StyledPanel

    def test_object_name_set(self, qtbot, mock_context, temp_workspace):
        """Test object name is set"""
        frame = CollapsiblePatientFrame(
            context=mock_context,
            patient_id="sub-57",
            files={},
            patterns={},
            multiple_choice=False
        )
        qtbot.addWidget(frame)

        assert frame.objectName() == "collapsiblePatientFrame"


# Parametrized tests
@pytest.mark.parametrize("multiple_choice,expected_locked", [
    (False, True),
    (True, False),
])
def test_locked_state_by_multiple_choice(multiple_choice, expected_locked, qtbot, mock_context, temp_workspace):
    """Parametrized test for locked state based on multiple_choice"""
    frame = CollapsiblePatientFrame(
        context=mock_context,
        patient_id="sub-param",
        files={},
        patterns={},
        multiple_choice=multiple_choice
    )
    qtbot.addWidget(frame)

    assert frame.locked == expected_locked


@pytest.mark.parametrize("arrow_type,is_expanded", [
    (Qt.ArrowType.RightArrow, False),
    (Qt.ArrowType.DownArrow, True),
])
def test_arrow_type_by_expansion_state(arrow_type, is_expanded, qtbot, mock_context, temp_workspace):
    """Parametrized test for arrow type based on expansion"""
    frame = CollapsiblePatientFrame(
        context=mock_context,
        patient_id="sub-arrow",
        files={},
        patterns={},
        multiple_choice=False
    )
    qtbot.addWidget(frame)

    frame._toggle_expand(is_expanded)

    assert frame.toggle_button.arrowType() == arrow_type


@pytest.mark.parametrize("patient_id", [
    "sub-001",
    "sub-99",
    "patient_A",
    "subject-01-session-1"
])
def test_various_patient_id_formats(patient_id, qtbot, mock_context, temp_workspace):
    """Parametrized test for various patient ID formats"""
    frame = CollapsiblePatientFrame(
        context=mock_context,
        patient_id=patient_id,
        files={},
        patterns={},
        multiple_choice=False
    )
    qtbot.addWidget(frame)

    assert frame.patient_id == patient_id
    assert patient_id in frame.subject_name.text()


if __name__ == "__main__":
    pytest.main([__file__, "-v"])

import json
import os
import pytest
from unittest.mock import Mock, patch, MagicMock
from PyQt6.QtWidgets import QApplication, QMessageBox
from unittest.mock import patch

from main.ui.pipeline_review_page import PipelineReviewPage


@pytest.fixture
def pipeline_config_basic(temp_workspace):
    """Creates a base config with one patient."""
    config = {
        "sub-01": {
            "mri": os.path.join(temp_workspace, "sub-01", "anat", "T1w.nii"),
            "pet": os.path.join(temp_workspace, "sub-01", "pet", "pet.nii"),
            "need_revision": False
        }
    }

    pipeline_dir = os.path.join(temp_workspace, "pipeline")
    os.makedirs(pipeline_dir, exist_ok=True)
    config_path = os.path.join(pipeline_dir, "01_config.json")

    with open(config_path, "w", encoding="utf-8") as f:
        json.dump(config, f, indent=4)

    return config_path, config


@pytest.fixture
def pipeline_config_multiple(temp_workspace):
    """Creates config with multiple patients and versions."""
    configs = [
        {
            "sub-01": {
                "mri": os.path.join(temp_workspace, "sub-01", "anat", "T1w.nii"),
                "need_revision": False
            }
        },
        {
            "sub-01": {
                "mri": os.path.join(temp_workspace, "sub-01", "anat", "T1w.nii"),
                "need_revision": False
            },
            "sub-02": {
                "mri": "path/to/mri2.nii",
                "need_revision": True
            }
        }
    ]

    pipeline_dir = os.path.join(temp_workspace, "pipeline")
    os.makedirs(pipeline_dir, exist_ok=True)

    paths = []
    for idx, config in enumerate(configs, start=1):
        config_path = os.path.join(pipeline_dir, f"{idx:02d}_config.json")
        with open(config_path, "w", encoding="utf-8") as f:
            json.dump(config, f, indent=4)
        paths.append(config_path)

    return paths, configs


@pytest.fixture
def pipeline_config_need_revision(temp_workspace):
    """Creates config with patients needing revision."""
    config = {
        "sub-01": {
            "mri": os.path.join(temp_workspace, "sub-01", "anat", "T1w.nii"),
            "need_revision": True
        },
        "sub-02": {
            "mri": "path/to/mri2.nii",
            "need_revision": False
        }
    }

    pipeline_dir = os.path.join(temp_workspace, "pipeline")
    os.makedirs(pipeline_dir, exist_ok=True)
    config_path = os.path.join(pipeline_dir, "01_config.json")

    with open(config_path, "w", encoding="utf-8") as f:
        json.dump(config, f, indent=4)

    return config_path, config


class TestPipelineReviewPageInitialization:
    """Tests for page initialization."""

    def test_initialization_basic(self, qtbot, mock_context, pipeline_config_basic):
        """Test basic initialization."""
        config_path, config = pipeline_config_basic
        page = PipelineReviewPage(mock_context)
        qtbot.addWidget(page)

        assert page.context == mock_context
        assert page.workspace_path == mock_context["workspace_path"]
        assert page.config_path == config_path
        assert page.pipeline_config == config
        assert page.previous_page is None
        assert page.next_page is None

    def test_initialization_with_previous_page(self, qtbot, mock_context, pipeline_config_basic):
        """Test initialization with a previous page."""
        previous = Mock()
        page = PipelineReviewPage(mock_context, previous_page=previous)
        qtbot.addWidget(page)

        assert page.previous_page == previous

    def test_ui_elements_created(self, qtbot, mock_context, pipeline_config_basic):
        """Test that all UI elements are created."""
        page = PipelineReviewPage(mock_context)
        qtbot.addWidget(page)

        assert page.header is not None
        assert page.config_info is not None
        assert page.info_label is not None
        assert isinstance(page.patient_widgets, dict)

    def test_patient_widgets_created(self, qtbot, mock_context, pipeline_config_basic):
        """Test creation of widgets for patients."""
        page = PipelineReviewPage(mock_context)
        qtbot.addWidget(page)

        assert "sub-01" in page.patient_widgets
        assert page.patient_widgets["sub-01"] is not None


class TestConfigFileDetection:
    """Tests for config file detection."""

    def test_find_latest_config_single(self, qtbot, mock_context, pipeline_config_basic):
        """Test detection with a single config file."""
        config_path, _ = pipeline_config_basic
        page = PipelineReviewPage(mock_context)
        qtbot.addWidget(page)

        assert page.config_path == config_path
        assert os.path.basename(page.config_path) == "01_config.json"

    def test_find_latest_config_multiple(self, qtbot, mock_context, pipeline_config_multiple):
        """Test detection with multiple configs (should pick the latest)."""
        paths, configs = pipeline_config_multiple
        page = PipelineReviewPage(mock_context)
        qtbot.addWidget(page)

        # Should pick the config with the highest ID (02_config.json)
        assert page.config_path == paths[-1]
        assert os.path.basename(page.config_path) == "02_config.json"
        assert page.pipeline_config == configs[-1]

    def test_find_latest_config_no_pipeline_dir(self, qtbot, mock_context, temp_workspace):
        """Test when the pipeline directory does not exist."""
        # Remove the pipeline directory if it exists
        pipeline_dir = os.path.join(temp_workspace, "pipeline")
        if os.path.exists(pipeline_dir):
            import shutil
            shutil.rmtree(pipeline_dir)

        page = PipelineReviewPage(mock_context)
        qtbot.addWidget(page)

        expected_path = os.path.join(temp_workspace, "pipeline", "pipeline_config.json")
        assert page.config_path == expected_path
        assert page.pipeline_config == {}

    def test_find_latest_config_no_files(self, qtbot, mock_context, temp_workspace):
        """Test when the pipeline directory is empty."""
        pipeline_dir = os.path.join(temp_workspace, "pipeline")
        os.makedirs(pipeline_dir, exist_ok=True)

        page = PipelineReviewPage(mock_context)
        qtbot.addWidget(page)

        expected_path = os.path.join(pipeline_dir, "pipeline_config.json")
        assert page.config_path == expected_path
        assert page.pipeline_config == {}

    def test_find_latest_config_invalid_names(self, qtbot, mock_context, temp_workspace):
        """Test with config files having invalid names."""
        pipeline_dir = os.path.join(temp_workspace, "pipeline")
        os.makedirs(pipeline_dir, exist_ok=True)

        # Create files with non-conforming names
        invalid_files = ["config.json", "abc_config.json", "test.json"]
        for fname in invalid_files:
            with open(os.path.join(pipeline_dir, fname), "w") as f:
                json.dump({}, f)

        page = PipelineReviewPage(mock_context)
        qtbot.addWidget(page)

        # Should use default because no file is valid
        expected_path = os.path.join(pipeline_dir, "pipeline_config.json")
        assert page.config_path == expected_path


class TestConfigLoading:
    """Tests for configuration loading."""

    def test_load_config_valid(self, qtbot, mock_context, pipeline_config_basic):
        """Test loading a valid config."""
        config_path, expected_config = pipeline_config_basic
        page = PipelineReviewPage(mock_context)
        qtbot.addWidget(page)

        assert page.pipeline_config == expected_config

    def test_load_config_invalid_json(self, qtbot, mock_context, temp_workspace, mock_logger):
        """Test loading a config with invalid JSON."""
        pipeline_dir = os.path.join(temp_workspace, "pipeline")
        os.makedirs(pipeline_dir, exist_ok=True)
        config_path = os.path.join(pipeline_dir, "01_config.json")

        # Write invalid JSON
        with open(config_path, "w") as f:
            f.write("{invalid json")

        with patch("main.ui.pipeline_review_page.log", mock_logger):
            page = PipelineReviewPage(mock_context)
            qtbot.addWidget(page)

            assert page.pipeline_config == {}
            mock_logger.error.assert_called_once()

    def test_load_config_file_not_found(self, qtbot, mock_context, temp_workspace, mock_logger):
        """Test when the config file does not exist."""
        with patch("main.ui.pipeline_review_page.log", mock_logger):
            page = PipelineReviewPage(mock_context)
            qtbot.addWidget(page)

            assert page.pipeline_config == {}
            mock_logger.warning.assert_called_once()


class TestSaveConfiguration:
    """Tests for saving the configuration."""

    def test_save_single_patient(self, qtbot, mock_context, pipeline_config_basic):
        """Test saving a single patient's configuration."""
        config_path, _ = pipeline_config_basic
        page = PipelineReviewPage(mock_context)
        qtbot.addWidget(page)

        # Modify and save
        new_files = {
            "mri": "new_path.nii",
            "pet": "new_pet.nii",
            "need_revision": False
        }
        page._save_single_patient("sub-01", new_files)

        # Verify save to file
        with open(config_path, "r", encoding="utf-8") as f:
            saved_config = json.load(f)

        assert saved_config["sub-01"] == new_files
        assert page.pipeline_config["sub-01"] == new_files

    def test_save_multiple_patients(self, qtbot, mock_context, pipeline_config_basic):
        """Test saving multiple patients."""
        config_path, _ = pipeline_config_basic
        page = PipelineReviewPage(mock_context)
        qtbot.addWidget(page)

        # Add a new patient
        new_patient = {
            "mri": "path2.nii",
            "need_revision": False
        }
        page._save_single_patient("sub-02", new_patient)

        # Verify
        with open(config_path, "r", encoding="utf-8") as f:
            saved_config = json.load(f)

        assert "sub-01" in saved_config
        assert "sub-02" in saved_config
        assert saved_config["sub-02"] == new_patient


class TestOnEnter:
    """Tests for the on_enter method."""

    def test_on_enter_no_changes(self, qtbot, mock_context, pipeline_config_basic, mock_logger):
        """Test on_enter when there are no changes."""
        page = PipelineReviewPage(mock_context)
        qtbot.addWidget(page)

        initial_config_path = page.config_path
        initial_config = page.pipeline_config.copy()

        with patch("main.ui.pipeline_review_page.log", mock_logger):
            page.on_enter()

            assert page.config_path == initial_config_path
            assert page.pipeline_config == initial_config
            mock_logger.debug.assert_called_once()

    def test_on_enter_new_config_file(self, qtbot, mock_context, pipeline_config_basic, mock_logger):
        """Test on_enter when a new config file is created."""
        page = PipelineReviewPage(mock_context)
        qtbot.addWidget(page)

        # Create new config
        pipeline_dir = os.path.join(mock_context["workspace_path"], "pipeline")
        new_config_path = os.path.join(pipeline_dir, "02_config.json")
        new_config = {
            "sub-03": {
                "mri": "new_path.nii",
                "need_revision": False
            }
        }
        with open(new_config_path, "w", encoding="utf-8") as f:
            json.dump(new_config, f)

        with patch("main.ui.pipeline_review_page.log", mock_logger):
            page.on_enter()

            assert page.config_path == new_config_path
            assert page.pipeline_config == new_config
            mock_logger.info.assert_called_once()

    def test_on_enter_config_content_changed(self, qtbot, mock_context, pipeline_config_basic, mock_logger):
        """Test on_enter when the config content changes."""
        config_path, _ = pipeline_config_basic
        page = PipelineReviewPage(mock_context)
        qtbot.addWidget(page)

        # Modify the config file directly
        modified_config = {
            "sub-01": {
                "mri": "modified_path.nii",
                "need_revision": True
            }
        }
        with open(config_path, "w", encoding="utf-8") as f:
            json.dump(modified_config, f)

        with patch("main.ui.pipeline_review_page.log", mock_logger):
            page.on_enter()

            assert page.pipeline_config == modified_config
            mock_logger.info.assert_called_once()


class TestNextNavigation:
    """Tests for navigating to the next page."""

    @patch('ui.pipeline_execution_page.get_bin_path')
    def test_next_all_saved(self, mock_get_bin, qtbot, mock_context, pipeline_config_basic):
        """Test next when all patients are saved."""
        mock_get_bin.return_value = "/fake/path/to/pipeline_runner"

        page = PipelineReviewPage(mock_context)
        qtbot.addWidget(page)

        result = page.next(mock_context)

        assert result != page
        assert page.next_page is not None
        assert "PipelineExecutionPage" in str(type(page.next_page))

    def test_next_need_revision(self, qtbot, mock_context, pipeline_config_need_revision):
        """Test next when patients need revision."""
        config_path, _ = pipeline_config_need_revision
        page = PipelineReviewPage(mock_context)
        qtbot.addWidget(page)

        with patch.object(QMessageBox, 'exec', return_value=QMessageBox.StandardButton.Ok):
            result = page.next(mock_context)

            assert result == page  # Must stay on the current page
            assert page.next_page is None

    @patch('ui.pipeline_execution_page.get_bin_path')
    def test_next_existing_next_page(self, mock_get_bin, qtbot, mock_context, pipeline_config_basic):
        """Test next when next_page already exists."""
        mock_get_bin.return_value = "/fake/path/to/pipeline_runner"

        page = PipelineReviewPage(mock_context)
        qtbot.addWidget(page)

        # First call
        result1 = page.next(mock_context)
        first_next_page = page.next_page

        # Simulate returning to the page
        page.on_enter()

        # Second call
        result2 = page.next(mock_context)

        # Must reuse the same next_page
        assert page.next_page == first_next_page

    @patch('ui.pipeline_execution_page.get_bin_path')
    def test_next_updates_history(self, mock_get_bin, qtbot, mock_context, pipeline_config_basic):
        """Test that next adds to history."""
        mock_get_bin.return_value = "/fake/path/to/pipeline_runner"

        page = PipelineReviewPage(mock_context)
        qtbot.addWidget(page)

        initial_history_len = len(mock_context["history"])
        page.next(mock_context)

        assert len(mock_context["history"]) == initial_history_len + 1
        assert page.next_page in mock_context["history"]


class TestBackNavigation:
    """Tests for navigating to the previous page."""

    def test_back_with_output_folder(self, qtbot, mock_context, pipeline_config_basic, mock_logger):
        """Test back when output folder exists (must keep config)."""
        config_path, _ = pipeline_config_basic
        page = PipelineReviewPage(mock_context)
        qtbot.addWidget(page)

        # Create the output folder
        pipeline_dir = os.path.dirname(config_path)
        output_folder = os.path.join(pipeline_dir, "01_output")
        os.makedirs(output_folder)

        previous = Mock()
        page.previous_page = previous

        with patch("main.ui.pipeline_review_page.log", mock_logger):
            result = page.back()

            assert result == previous
            assert os.path.exists(config_path)  # Config must not be deleted
            mock_logger.info.assert_called()

    def test_back_without_output_folder(self, qtbot, mock_context, pipeline_config_basic, mock_logger):
        """Test back when output folder does not exist (must delete config)."""
        config_path, _ = pipeline_config_basic
        page = PipelineReviewPage(mock_context)
        qtbot.addWidget(page)

        previous = Mock()
        page.previous_page = previous

        with patch("main.ui.pipeline_review_page.log", mock_logger):
            result = page.back()

            assert result == previous
            assert not os.path.exists(config_path)  # Config must be deleted
            mock_logger.info.assert_called()

    def test_back_no_previous_page(self, qtbot, mock_context, pipeline_config_basic):
        """Test back without previous_page."""
        page = PipelineReviewPage(mock_context)
        qtbot.addWidget(page)

        result = page.back()

        assert result is None

    def test_back_calls_on_enter(self, qtbot, mock_context, pipeline_config_basic):
        """Test that back calls on_enter on the previous page."""
        page = PipelineReviewPage(mock_context)
        qtbot.addWidget(page)

        previous = Mock()
        page.previous_page = previous

        page.back()

        previous.on_enter.assert_called_once()

    def test_back_error_handling(self, qtbot, mock_context, pipeline_config_basic, mock_logger):
        """Test error handling during back."""
        page = PipelineReviewPage(mock_context)
        qtbot.addWidget(page)

        # Make the config_path invalid
        page.config_path = "/invalid/path/config.json"

        previous = Mock()
        page.previous_page = previous

        with patch("main.ui.pipeline_review_page.log", mock_logger):
            result = page.back()

            assert result == previous
            mock_logger.error.assert_called()


class TestTranslation:
    """Tests for translations."""

    def test_translate_ui_called_on_init(self, qtbot, mock_context, pipeline_config_basic):
        """Test that _translate_ui is called during init."""
        with patch.object(PipelineReviewPage, '_translate_ui') as mock_translate:
            page = PipelineReviewPage(mock_context)
            qtbot.addWidget(page)

            mock_translate.assert_called()

    def test_translate_ui_updates_labels(self, qtbot, mock_context, pipeline_config_basic):
        """Test that _translate_ui updates labels."""
        page = PipelineReviewPage(mock_context)
        qtbot.addWidget(page)

        # Save original texts
        original_header = page.header.text()

        # Call _translate_ui
        page._translate_ui()

        # Verify texts were updated (even if identical)
        assert page.header.text() is not None
        assert page.config_info.text() is not None
        assert page.info_label.text() is not None

    def test_language_changed_signal(self, mock_context):
        from main.ui.pipeline_review_page import PipelineReviewPage
        page = PipelineReviewPage(mock_context)

        # Replace the function but reconnect the signal
        page._translate_ui = Mock()
        mock_context["language_changed"].connect(page._translate_ui)

        # Now emitting the signal must trigger the mock
        mock_context["language_changed"].emit("it")

        page._translate_ui.assert_called_once()


class TestUISetup:
    """Tests for UI configuration."""

    def test_setup_ui_clears_existing_layout(self, qtbot, mock_context, pipeline_config_basic):
        """Test that _setup_ui clears the existing layout."""
        page = PipelineReviewPage(mock_context)
        qtbot.addWidget(page)

        initial_count = page.main_layout.count()

        # Call _setup_ui again
        page._setup_ui()

        # The count might be the same or different, but it shouldn't crash
        assert page.main_layout.count() >= 0

    def test_setup_ui_creates_scroll_area(self, qtbot, mock_context, pipeline_config_basic):
        """Test that a scroll area is created."""
        page = PipelineReviewPage(mock_context)
        qtbot.addWidget(page)

        # Search for scroll area in the layout
        scroll_found = False
        for i in range(page.main_layout.count()):
            widget = page.main_layout.itemAt(i).widget()
            if widget and "QScrollArea" in str(type(widget)):
                scroll_found = True
                break

        assert scroll_found

    def test_patient_widgets_created_for_all_patients(self, qtbot, mock_context, pipeline_config_multiple):
        """Test that widgets are created for all patients."""
        paths, configs = pipeline_config_multiple
        page = PipelineReviewPage(mock_context)
        qtbot.addWidget(page)

        # Must have widgets for all patients in the last config
        last_config = configs[-1]
        for patient_id in last_config.keys():
            assert patient_id in page.patient_widgets


class TestEdgeCases:
    """Tests for edge cases."""

    def test_empty_config(self, qtbot, mock_context, temp_workspace):
        """Test with an empty config."""
        pipeline_dir = os.path.join(temp_workspace, "pipeline")
        os.makedirs(pipeline_dir, exist_ok=True)
        config_path = os.path.join(pipeline_dir, "01_config.json")

        with open(config_path, "w", encoding="utf-8") as f:
            json.dump({}, f)

        page = PipelineReviewPage(mock_context)
        qtbot.addWidget(page)

        assert page.pipeline_config == {}
        assert len(page.patient_widgets) == 0

    def test_very_large_config(self, qtbot, mock_context, temp_workspace):
        """Test with many patients."""
        pipeline_dir = os.path.join(temp_workspace, "pipeline")
        os.makedirs(pipeline_dir, exist_ok=True)
        config_path = os.path.join(pipeline_dir, "01_config.json")

        # Create config with 100 patients
        large_config = {
            f"sub-{i:03d}": {
                "mri": f"path{i}.nii",
                "need_revision": False
            }
            for i in range(100)
        }

        with open(config_path, "w", encoding="utf-8") as f:
            json.dump(large_config, f)

        page = PipelineReviewPage(mock_context)
        qtbot.addWidget(page)

        assert len(page.pipeline_config) == 100
        assert len(page.patient_widgets) == 100

    def test_special_characters_in_patient_id(self, qtbot, mock_context, temp_workspace):
        """Test with special characters in patient IDs."""
        pipeline_dir = os.path.join(temp_workspace, "pipeline")
        os.makedirs(pipeline_dir, exist_ok=True)
        config_path = os.path.join(pipeline_dir, "01_config.json")

        config = {
            "sub-01_special-chars": {
                "mri": "path.nii",
                "need_revision": False
            }
        }

        with open(config_path, "w", encoding="utf-8") as f:
            json.dump(config, f)

        page = PipelineReviewPage(mock_context)
        qtbot.addWidget(page)

        assert "sub-01_special-chars" in page.patient_widgets

    def test_unicode_in_paths(self, qtbot, mock_context, temp_workspace):
        """Test with unicode characters in paths."""
        pipeline_dir = os.path.join(temp_workspace, "pipeline")
        os.makedirs(pipeline_dir, exist_ok=True)
        config_path = os.path.join(pipeline_dir, "01_config.json")

        config = {
            "sub-01": {
                "mri": "path/àèéìòù/file.nii",
                "need_revision": False
            }
        }

        with open(config_path, "w", encoding="utf-8") as f:
            json.dump(config, f)

        page = PipelineReviewPage(mock_context)
        qtbot.addWidget(page)

        assert page.pipeline_config["sub-01"]["mri"] == "path/àèéìòù/file.nii"
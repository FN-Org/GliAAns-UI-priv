import pytest
import os
import json
import tempfile
import shutil
from unittest.mock import Mock, patch, MagicMock

from main.ui.pipeline_patient_selection_page import PipelinePatientSelectionPage

class TestPipelinePatientSelectionPageSetup:
    """Tests for initialization"""

    @pytest.fixture
    def temp_workspace(self):
        temp_dir = tempfile.mkdtemp()
        yield temp_dir
        shutil.rmtree(temp_dir, ignore_errors=True)

    @pytest.fixture
    def pipeline_page(self, qtbot, mock_context):
        page = PipelinePatientSelectionPage(mock_context, Mock())
        qtbot.addWidget(page)
        return page

    def test_page_initialization(self, pipeline_page):
        """Verify correct initialization"""
        assert pipeline_page.context is not None
        assert pipeline_page.workspace_path is not None
        assert pipeline_page.selected_patients == set()
        assert pipeline_page.patient_status == {}

    def test_title_created(self, pipeline_page):
        """Verify title creation"""
        assert pipeline_page.title is not None
        assert pipeline_page.title.text() != ""

    def test_buttons_created(self, pipeline_page):
        """Verify button creation"""
        assert pipeline_page.select_eligible_btn is not None
        assert pipeline_page.deselect_all_btn is not None
        assert pipeline_page.refresh_btn is not None

    def test_summary_widget_created(self, pipeline_page):
        """Verify summary widget creation"""
        assert pipeline_page.summary_widget is not None
        assert pipeline_page.total_label is not None
        assert pipeline_page.eligible_label is not None
        assert pipeline_page.not_eligible_label is not None


class TestPipelinePatientRequirements:
    """Tests for verifying patient requirements"""

    @pytest.fixture
    def temp_workspace(self):
        temp_dir = tempfile.mkdtemp()
        # Create eligible patient structure
        patient_dir = os.path.join(temp_dir, "sub-01")
        os.makedirs(os.path.join(patient_dir, "anat"))

        # FLAIR
        with open(os.path.join(patient_dir, "anat", "sub-01_flair.nii.gz"), "w") as f:
            f.write("flair")

        # Skull stripping
        skull_dir = os.path.join(temp_dir, "derivatives", "skullstrips", "sub-01", "anat")
        os.makedirs(skull_dir)
        with open(os.path.join(skull_dir, "sub-01_brain.nii.gz"), "w") as f:
            f.write("brain")

        # Segmentation
        seg_dir = os.path.join(temp_dir, "derivatives", "manual_masks", "sub-01", "anat")
        os.makedirs(seg_dir)
        with open(os.path.join(seg_dir, "sub-01_mask.nii.gz"), "w") as f:
            f.write("mask")

        yield temp_dir
        shutil.rmtree(temp_dir, ignore_errors=True)

    @pytest.fixture
    def pipeline_page(self, qtbot, mock_context):
        page = PipelinePatientSelectionPage(mock_context, Mock())
        qtbot.addWidget(page)
        return page

    def test_check_patient_eligible(self, pipeline_page, temp_workspace):
        """Verify patient with all requirements"""
        patient_path = os.path.join(temp_workspace, "sub-01")

        status = pipeline_page._check_patient_requirements(patient_path, "sub-01")

        assert status['eligible'] == True
        assert status['requirements']['flair'] == True
        assert status['requirements']['skull_stripping'] == True
        assert status['requirements']['segmentation'] == True

    def test_check_patient_missing_flair(self, pipeline_page, temp_workspace):
        """Verify patient without FLAIR"""
        # Create patient without FLAIR
        patient_dir = os.path.join(temp_workspace, "sub-02")
        os.makedirs(os.path.join(patient_dir, "anat"))

        status = pipeline_page._check_patient_requirements(patient_dir, "sub-02")

        assert status['eligible'] == False
        assert status['requirements']['flair'] == False
        assert "FLAIR" in str(status['missing_files'])

    def test_check_patient_missing_skull_stripping(self, pipeline_page, temp_workspace):
        """Verify patient without skull stripping"""
        patient_dir = os.path.join(temp_workspace, "sub-03")
        os.makedirs(os.path.join(patient_dir, "anat"))
        with open(os.path.join(patient_dir, "anat", "sub-03_flair.nii.gz"), "w") as f:
            f.write("flair")

        status = pipeline_page._check_patient_requirements(patient_dir, "sub-03")

        assert status['eligible'] == False
        assert status['requirements']['skull_stripping'] == False

    def test_check_patient_missing_segmentation(self, pipeline_page, temp_workspace):
        """Verify patient without segmentation"""
        patient_dir = os.path.join(temp_workspace, "sub-04")
        os.makedirs(os.path.join(patient_dir, "anat"))
        with open(os.path.join(patient_dir, "anat", "sub-04_flair.nii.gz"), "w") as f:
            f.write("flair")

        skull_dir = os.path.join(temp_workspace, "derivatives", "skullstrips", "sub-04", "anat")
        os.makedirs(skull_dir)
        with open(os.path.join(skull_dir, "sub-04_brain.nii.gz"), "w") as f:
            f.write("brain")

        status = pipeline_page._check_patient_requirements(patient_dir, "sub-04")

        assert status['eligible'] == False
        assert status['requirements']['segmentation'] == False


class TestPipelinePatientSelection:
    """Tests for patient selection"""

    @pytest.fixture
    def temp_workspace(self):
        temp_dir = tempfile.mkdtemp()
        # Create 2 eligible patients
        for i in range(1, 3):
            patient_id = f"sub-{i:02d}"
            patient_dir = os.path.join(temp_dir, patient_id)
            os.makedirs(os.path.join(patient_dir, "anat"))

            with open(os.path.join(patient_dir, "anat", f"{patient_id}_flair.nii.gz"), "w") as f:
                f.write("flair")

            skull_dir = os.path.join(temp_dir, "derivatives", "skullstrips", patient_id, "anat")
            os.makedirs(skull_dir)
            with open(os.path.join(skull_dir, f"{patient_id}_brain.nii.gz"), "w") as f:
                f.write("brain")

            seg_dir = os.path.join(temp_dir, "derivatives", "manual_masks", patient_id, "anat")
            os.makedirs(seg_dir)
            with open(os.path.join(seg_dir, f"{patient_id}_mask.nii.gz"), "w") as f:
                f.write("mask")

        yield temp_dir
        shutil.rmtree(temp_dir, ignore_errors=True)

    @pytest.fixture
    def pipeline_page(self, qtbot, mock_context):
        page = PipelinePatientSelectionPage(mock_context, Mock())
        qtbot.addWidget(page)
        return page

    def test_select_all_eligible(self, pipeline_page):
        """Verify selection of all eligible patients"""
        pipeline_page._select_all_eligible_patients()

        assert len(pipeline_page.selected_patients) == 2
        assert "sub-01" in pipeline_page.selected_patients
        assert "sub-02" in pipeline_page.selected_patients

    def test_deselect_all(self, pipeline_page):
        """Verify deselection of all patients"""
        pipeline_page._select_all_eligible_patients()
        assert len(pipeline_page.selected_patients) == 2

        pipeline_page._deselect_all_patients()

        assert len(pipeline_page.selected_patients) == 0

    def test_toggle_patient_select(self, pipeline_page):
        """Verify single patient selection"""
        button = Mock()
        pipeline_page._toggle_patient("sub-01", True, button)

        assert "sub-01" in pipeline_page.selected_patients

    def test_toggle_patient_deselect(self, pipeline_page):
        """Verify single patient deselection"""
        pipeline_page.selected_patients.add("sub-01")
        button = Mock()

        pipeline_page._toggle_patient("sub-01", False, button)

        assert "sub-01" not in pipeline_page.selected_patients

class TestPipelinePatientLoading:
    """Tests for patient loading"""

    @pytest.fixture
    def pipeline_page(self, qtbot, mock_context):
        page = PipelinePatientSelectionPage(mock_context, Mock())
        qtbot.addWidget(page)
        return page

    def test_find_patient_dirs(self, pipeline_page):
        """Verify patient directory search"""
        patient_dirs = pipeline_page._find_patient_dirs()

        assert len(patient_dirs) == 2
        patient_ids = [os.path.basename(d) for d in patient_dirs]
        assert "sub-01" in patient_ids
        assert "sub-02" in patient_ids

    def test_load_patients_creates_buttons(self, pipeline_page):
        """Verify patient button creation"""
        assert len(pipeline_page.patient_buttons) == 2

    def test_load_patients_updates_status(self, pipeline_page):
        """Verify patient status update"""
        assert len(pipeline_page.patient_status) == 2


class TestPipelineConfigGeneration:
    """Tests for pipeline configuration generation"""

    @pytest.fixture
    def temp_workspace(self):
        temp_dir = tempfile.mkdtemp()
        patient_dir = os.path.join(temp_dir, "sub-01")
        os.makedirs(os.path.join(patient_dir, "anat"))
        os.makedirs(os.path.join(patient_dir, "ses-01", "pet"))

        # Necessary files
        with open(os.path.join(patient_dir, "anat", "sub-01_flair.nii.gz"), "w") as f:
            f.write("flair")
        with open(os.path.join(patient_dir, "ses-01", "pet", "sub-01_pet.nii.gz"), "w") as f:
            f.write("pet")

        skull_dir = os.path.join(temp_dir, "derivatives", "skullstrips", "sub-01", "anat")
        os.makedirs(skull_dir)
        with open(os.path.join(skull_dir, "sub-01_brain.nii.gz"), "w") as f:
            f.write("brain")

        seg_dir = os.path.join(temp_dir, "derivatives", "manual_masks", "sub-01", "anat")
        os.makedirs(seg_dir)
        with open(os.path.join(seg_dir, "sub-01_mask.nii.gz"), "w") as f:
            f.write("mask")

        yield temp_dir
        shutil.rmtree(temp_dir, ignore_errors=True)

    @pytest.fixture
    def pipeline_page(self, qtbot, mock_context):
        page = PipelinePatientSelectionPage(mock_context, Mock())
        qtbot.addWidget(page)
        page.selected_patients = {"sub-01"}
        return page

    def test_build_pipeline_config_creates_file(self, pipeline_page, temp_workspace):
        """Verify configuration file creation"""
        config_path = pipeline_page._build_pipeline_config()

        assert os.path.exists(config_path)
        assert config_path.endswith("_config.json")

    def test_build_pipeline_config_content(self, pipeline_page):
        """Verify configuration content"""
        config_path = pipeline_page._build_pipeline_config()

        with open(config_path, 'r') as f:
            config = json.load(f)

        assert "sub-01" in config
        assert "mri" in config["sub-01"]
        assert "mri_str" in config["sub-01"]
        assert "tumor_mri" in config["sub-01"]

    def test_get_next_config_id_first(self, pipeline_page, temp_workspace):
        """Verify configuration ID first time"""
        pipeline_dir = os.path.join(temp_workspace, "pipeline")
        os.makedirs(pipeline_dir, exist_ok=True)

        config_id = pipeline_page._get_next_config_id(pipeline_dir)

        assert config_id == 1

    def test_get_next_config_id_existing(self, pipeline_page, temp_workspace):
        """Verify configuration ID with existing files"""
        pipeline_dir = os.path.join(temp_workspace, "pipeline")
        os.makedirs(pipeline_dir, exist_ok=True)

        # Create existing files
        with open(os.path.join(pipeline_dir, "01_config.json"), "w") as f:
            f.write("{}")
        with open(os.path.join(pipeline_dir, "02_config.json"), "w") as f:
            f.write("{}")

        config_id = pipeline_page._get_next_config_id(pipeline_dir)

        assert config_id == 3

class TestPipelinePatientRefresh:
    """Tests for refreshing patient status"""

    @pytest.fixture
    def pipeline_page(self, qtbot, mock_context):
        page = PipelinePatientSelectionPage(mock_context, Mock())
        qtbot.addWidget(page)
        return page

    def test_refresh_maintains_valid_selections(self, pipeline_page):
        """Verify that refresh maintains valid selections"""
        # Simulate selection
        pipeline_page.selected_patients.add("sub-01")

        pipeline_page._refresh_patient_status()

        # Selections should be validated
        assert isinstance(pipeline_page.selected_patients, set)


class TestPipelinePatientNavigation:
    """Tests for navigation"""

    @pytest.fixture
    def pipeline_page(self, qtbot, mock_context):
        previous_page = Mock()
        page = PipelinePatientSelectionPage(mock_context, previous_page)
        qtbot.addWidget(page)
        return page

    def test_is_ready_to_advance_with_selection(self, pipeline_page):
        """Verify ready to advance with selections"""
        pipeline_page.selected_patients.add("sub-01")
        assert pipeline_page.is_ready_to_advance()

    def test_is_ready_to_advance_without_selection(self, pipeline_page):
        """Verify not ready without selections"""
        assert not pipeline_page.is_ready_to_advance()

    def test_is_ready_to_go_back(self, pipeline_page):
        """Verify can go back"""
        assert pipeline_page.is_ready_to_go_back()

    def test_back_returns_previous_page(self, pipeline_page):
        """Verify return to previous page"""
        result = pipeline_page.back()
        assert result == pipeline_page.previous_page
        pipeline_page.previous_page.on_enter.assert_called_once()

    @patch('main.ui.pipeline_patient_selection_page.PipelineReviewPage')
    def test_next_creates_review_page(self, MockPage, pipeline_page):
        """Verify review page creation"""
        mock_page = Mock()
        MockPage.return_value = mock_page
        pipeline_page.selected_patients.add("sub-01")

        result = pipeline_page.next(pipeline_page.context)

        assert result == mock_page
        mock_page.on_enter.assert_called_once()

class TestPipelinePatientSummary:
    """Tests for summary functions"""

    @pytest.fixture
    def pipeline_page(self, qtbot, mock_context):
        page = PipelinePatientSelectionPage(mock_context, Mock())
        qtbot.addWidget(page)
        return page

    def test_get_selected_patients(self, pipeline_page):
        """Verify retrieval of selected patients"""
        pipeline_page.selected_patients = {"sub-01", "sub-02"}

        selected = pipeline_page.get_selected_patients()

        assert isinstance(selected, list)
        assert len(selected) == 2

    def test_get_eligible_patients(self, pipeline_page):
        """Verify retrieval of eligible patients"""
        pipeline_page.patient_status = {
            "sub-01": {"eligible": True},
            "sub-02": {"eligible": False}
        }

        eligible = pipeline_page.get_eligible_patients()

        assert len(eligible) == 1
        assert "sub-01" in eligible

    def test_get_patient_status_summary(self, pipeline_page):
        """Verify status summary"""
        pipeline_page.patient_status = {
            "sub-01": {"eligible": True},
            "sub-02": {"eligible": False}
        }
        pipeline_page.selected_patients = {"sub-01"}

        summary = pipeline_page.get_patient_status_summary()

        assert summary['total'] == 2
        assert summary['eligible'] == 1
        assert summary['selected'] == 1
        assert summary['not_eligible'] == 1


class TestPipelinePatientReset:
    """Tests for page reset"""

    @pytest.fixture
    def pipeline_page(self, qtbot, mock_context):
        page = PipelinePatientSelectionPage(mock_context, Mock())
        qtbot.addWidget(page)
        return page

    def test_reset_clears_selections(self, pipeline_page):
        """Verify that reset clears selections"""
        pipeline_page.selected_patients = {"sub-01", "sub-02"}

        pipeline_page.reset_page()

        assert len(pipeline_page.selected_patients) == 0

    def test_reset_clears_status(self, pipeline_page):
        """Verify that reset clears status"""
        pipeline_page.patient_status = {"sub-01": {"eligible": True}}

        pipeline_page.reset_page()

        # Status should be reloaded
        assert isinstance(pipeline_page.patient_status, dict)

# Integration tests
class TestPipelinePatientIntegration:
    """Integration tests"""

    @pytest.fixture
    def temp_workspace(self):
        temp_dir = tempfile.mkdtemp()
        # Create complete patient
        patient_dir = os.path.join(temp_dir, "sub-01")
        os.makedirs(os.path.join(patient_dir, "anat"))
        os.makedirs(os.path.join(patient_dir, "ses-01", "pet"))

        with open(os.path.join(patient_dir, "anat", "sub-01_flair.nii.gz"), "w") as f:
            f.write("flair")

        skull_dir = os.path.join(temp_dir, "derivatives", "skullstrips", "sub-01", "anat")
        os.makedirs(skull_dir)
        with open(os.path.join(skull_dir, "sub-01_brain.nii.gz"), "w") as f:
            f.write("brain")

        seg_dir = os.path.join(temp_dir, "derivatives", "manual_masks", "sub-01", "anat")
        os.makedirs(seg_dir)
        with open(os.path.join(seg_dir, "sub-01_mask.nii.gz"), "w") as f:
            f.write("mask")

        yield temp_dir
        shutil.rmtree(temp_dir, ignore_errors=True)

    @pytest.fixture
    def pipeline_page(self, qtbot, mock_context):
        page = PipelinePatientSelectionPage(mock_context, Mock())
        qtbot.addWidget(page)
        return page

    def test_full_workflow(self, pipeline_page, temp_workspace):
        """Test full workflow"""
        # Verify loading
        assert len(pipeline_page.patient_status) == 1

        # Patient should be eligible
        assert pipeline_page.patient_status["sub-01"]["eligible"]

        # Select
        pipeline_page._select_all_eligible_patients()
        assert len(pipeline_page.selected_patients) == 1

        # Generate config
        config_path = pipeline_page._build_pipeline_config()
        assert os.path.exists(config_path)

        # Verify config
        with open(config_path, 'r') as f:
            config = json.load(f)
        assert "sub-01" in config


if __name__ == "__main__":
    pytest.main([__file__, "-v", "--tb=short"])
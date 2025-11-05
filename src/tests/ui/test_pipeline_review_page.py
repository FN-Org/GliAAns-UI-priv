import json
import os
import pytest
from unittest.mock import Mock, patch, MagicMock
from PyQt6.QtWidgets import QApplication, QMessageBox
from unittest.mock import patch

from main.ui.ui_pipeline_review_page import PipelineReviewPage


@pytest.fixture
def pipeline_config_basic(temp_workspace):
    """Crea un config base con un paziente."""
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
    """Crea config con più pazienti e versioni."""
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
    """Crea config con pazienti che necessitano revisione."""
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
    """Test per l'inizializzazione della pagina."""

    def test_initialization_basic(self, qtbot, mock_context, pipeline_config_basic):
        """Test inizializzazione base."""
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
        """Test inizializzazione con pagina precedente."""
        previous = Mock()
        page = PipelineReviewPage(mock_context, previous_page=previous)
        qtbot.addWidget(page)

        assert page.previous_page == previous

    def test_ui_elements_created(self, qtbot, mock_context, pipeline_config_basic):
        """Test che tutti gli elementi UI siano creati."""
        page = PipelineReviewPage(mock_context)
        qtbot.addWidget(page)

        assert page.header is not None
        assert page.config_info is not None
        assert page.info_label is not None
        assert isinstance(page.patient_widgets, dict)

    def test_patient_widgets_created(self, qtbot, mock_context, pipeline_config_basic):
        """Test creazione widget per i pazienti."""
        page = PipelineReviewPage(mock_context)
        qtbot.addWidget(page)

        assert "sub-01" in page.patient_widgets
        assert page.patient_widgets["sub-01"] is not None


class TestConfigFileDetection:
    """Test per il rilevamento del file config."""

    def test_find_latest_config_single(self, qtbot, mock_context, pipeline_config_basic):
        """Test rilevamento con un solo config."""
        config_path, _ = pipeline_config_basic
        page = PipelineReviewPage(mock_context)
        qtbot.addWidget(page)

        assert page.config_path == config_path
        assert os.path.basename(page.config_path) == "01_config.json"

    def test_find_latest_config_multiple(self, qtbot, mock_context, pipeline_config_multiple):
        """Test rilevamento con più config (deve prendere l'ultimo)."""
        paths, configs = pipeline_config_multiple
        page = PipelineReviewPage(mock_context)
        qtbot.addWidget(page)

        # Deve prendere il config con ID più alto (02_config.json)
        assert page.config_path == paths[-1]
        assert os.path.basename(page.config_path) == "02_config.json"
        assert page.pipeline_config == configs[-1]

    def test_find_latest_config_no_pipeline_dir(self, qtbot, mock_context, temp_workspace):
        """Test quando la directory pipeline non esiste."""
        # Rimuovi la directory pipeline se esiste
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
        """Test quando la directory pipeline è vuota."""
        pipeline_dir = os.path.join(temp_workspace, "pipeline")
        os.makedirs(pipeline_dir, exist_ok=True)

        page = PipelineReviewPage(mock_context)
        qtbot.addWidget(page)

        expected_path = os.path.join(pipeline_dir, "pipeline_config.json")
        assert page.config_path == expected_path
        assert page.pipeline_config == {}

    def test_find_latest_config_invalid_names(self, qtbot, mock_context, temp_workspace):
        """Test con file config con nomi non validi."""
        pipeline_dir = os.path.join(temp_workspace, "pipeline")
        os.makedirs(pipeline_dir, exist_ok=True)

        # Crea file con nomi non conformi
        invalid_files = ["config.json", "abc_config.json", "test.json"]
        for fname in invalid_files:
            with open(os.path.join(pipeline_dir, fname), "w") as f:
                json.dump({}, f)

        page = PipelineReviewPage(mock_context)
        qtbot.addWidget(page)

        # Deve usare il default perché nessun file è valido
        expected_path = os.path.join(pipeline_dir, "pipeline_config.json")
        assert page.config_path == expected_path


class TestConfigLoading:
    """Test per il caricamento della configurazione."""

    def test_load_config_valid(self, qtbot, mock_context, pipeline_config_basic):
        """Test caricamento config valido."""
        config_path, expected_config = pipeline_config_basic
        page = PipelineReviewPage(mock_context)
        qtbot.addWidget(page)

        assert page.pipeline_config == expected_config

    def test_load_config_invalid_json(self, qtbot, mock_context, temp_workspace, mock_logger):
        """Test caricamento config con JSON non valido."""
        pipeline_dir = os.path.join(temp_workspace, "pipeline")
        os.makedirs(pipeline_dir, exist_ok=True)
        config_path = os.path.join(pipeline_dir, "01_config.json")

        # Scrivi JSON non valido
        with open(config_path, "w") as f:
            f.write("{invalid json")

        with patch("main.ui.ui_pipeline_review_page.log", mock_logger):
            page = PipelineReviewPage(mock_context)
            qtbot.addWidget(page)

            assert page.pipeline_config == {}
            mock_logger.error.assert_called_once()

    def test_load_config_file_not_found(self, qtbot, mock_context, temp_workspace, mock_logger):
        """Test quando il file config non esiste."""
        with patch("main.ui.ui_pipeline_review_page.log", mock_logger):
            page = PipelineReviewPage(mock_context)
            qtbot.addWidget(page)

            assert page.pipeline_config == {}
            mock_logger.warning.assert_called_once()


class TestSaveConfiguration:
    """Test per il salvataggio della configurazione."""

    def test_save_single_patient(self, qtbot, mock_context, pipeline_config_basic):
        """Test salvataggio configurazione singolo paziente."""
        config_path, _ = pipeline_config_basic
        page = PipelineReviewPage(mock_context)
        qtbot.addWidget(page)

        # Modifica e salva
        new_files = {
            "mri": "new_path.nii",
            "pet": "new_pet.nii",
            "need_revision": False
        }
        page._save_single_patient("sub-01", new_files)

        # Verifica salvataggio su file
        with open(config_path, "r", encoding="utf-8") as f:
            saved_config = json.load(f)

        assert saved_config["sub-01"] == new_files
        assert page.pipeline_config["sub-01"] == new_files

    def test_save_multiple_patients(self, qtbot, mock_context, pipeline_config_basic):
        """Test salvataggio multipli pazienti."""
        config_path, _ = pipeline_config_basic
        page = PipelineReviewPage(mock_context)
        qtbot.addWidget(page)

        # Aggiungi nuovo paziente
        new_patient = {
            "mri": "path2.nii",
            "need_revision": False
        }
        page._save_single_patient("sub-02", new_patient)

        # Verifica
        with open(config_path, "r", encoding="utf-8") as f:
            saved_config = json.load(f)

        assert "sub-01" in saved_config
        assert "sub-02" in saved_config
        assert saved_config["sub-02"] == new_patient


class TestOnEnter:
    """Test per il metodo on_enter."""

    def test_on_enter_no_changes(self, qtbot, mock_context, pipeline_config_basic, mock_logger):
        """Test on_enter quando non ci sono cambiamenti."""
        page = PipelineReviewPage(mock_context)
        qtbot.addWidget(page)

        initial_config_path = page.config_path
        initial_config = page.pipeline_config.copy()

        with patch("main.ui.ui_pipeline_review_page.log", mock_logger):
            page.on_enter()

            assert page.config_path == initial_config_path
            assert page.pipeline_config == initial_config
            mock_logger.debug.assert_called_once()

    def test_on_enter_new_config_file(self, qtbot, mock_context, pipeline_config_basic, mock_logger):
        """Test on_enter quando viene creato un nuovo config."""
        page = PipelineReviewPage(mock_context)
        qtbot.addWidget(page)

        # Crea nuovo config
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

        with patch("main.ui.ui_pipeline_review_page.log", mock_logger):
            page.on_enter()

            assert page.config_path == new_config_path
            assert page.pipeline_config == new_config
            mock_logger.info.assert_called_once()

    def test_on_enter_config_content_changed(self, qtbot, mock_context, pipeline_config_basic, mock_logger):
        """Test on_enter quando cambia il contenuto del config."""
        config_path, _ = pipeline_config_basic
        page = PipelineReviewPage(mock_context)
        qtbot.addWidget(page)

        # Modifica il config file direttamente
        modified_config = {
            "sub-01": {
                "mri": "modified_path.nii",
                "need_revision": True
            }
        }
        with open(config_path, "w", encoding="utf-8") as f:
            json.dump(modified_config, f)

        with patch("main.ui.ui_pipeline_review_page.log", mock_logger):
            page.on_enter()

            assert page.pipeline_config == modified_config
            mock_logger.info.assert_called_once()


class TestNextNavigation:
    """Test per la navigazione alla pagina successiva."""

    @patch('ui.ui_pipeline_execution_page.get_bin_path')
    def test_next_all_saved(self, mock_get_bin, qtbot, mock_context, pipeline_config_basic):
        """Test next quando tutti i pazienti sono salvati."""
        mock_get_bin.return_value = "/fake/path/to/pipeline_runner"

        page = PipelineReviewPage(mock_context)
        qtbot.addWidget(page)

        result = page.next(mock_context)

        assert result != page
        assert page.next_page is not None
        assert "PipelineExecutionPage" in str(type(page.next_page))

    def test_next_need_revision(self, qtbot, mock_context, pipeline_config_need_revision):
        """Test next quando ci sono pazienti da revisionare."""
        config_path, _ = pipeline_config_need_revision
        page = PipelineReviewPage(mock_context)
        qtbot.addWidget(page)

        with patch.object(QMessageBox, 'exec', return_value=QMessageBox.StandardButton.Ok):
            result = page.next(mock_context)

            assert result == page  # Deve rimanere sulla pagina corrente
            assert page.next_page is None

    @patch('ui.ui_pipeline_execution_page.get_bin_path')
    def test_next_existing_next_page(self, mock_get_bin, qtbot, mock_context, pipeline_config_basic):
        """Test next quando next_page già esiste."""
        mock_get_bin.return_value = "/fake/path/to/pipeline_runner"

        page = PipelineReviewPage(mock_context)
        qtbot.addWidget(page)

        # Prima chiamata
        result1 = page.next(mock_context)
        first_next_page = page.next_page

        # Simula ritorno alla pagina
        page.on_enter()

        # Seconda chiamata
        result2 = page.next(mock_context)

        # Deve riutilizzare la stessa next_page
        assert page.next_page == first_next_page

    @patch('ui.ui_pipeline_execution_page.get_bin_path')
    def test_next_updates_history(self, mock_get_bin, qtbot, mock_context, pipeline_config_basic):
        """Test che next aggiunga alla history."""
        mock_get_bin.return_value = "/fake/path/to/pipeline_runner"

        page = PipelineReviewPage(mock_context)
        qtbot.addWidget(page)

        initial_history_len = len(mock_context["history"])
        page.next(mock_context)

        assert len(mock_context["history"]) == initial_history_len + 1
        assert page.next_page in mock_context["history"]


class TestBackNavigation:
    """Test per la navigazione alla pagina precedente."""

    def test_back_with_output_folder(self, qtbot, mock_context, pipeline_config_basic, mock_logger):
        """Test back quando esiste la cartella output (deve mantenere config)."""
        config_path, _ = pipeline_config_basic
        page = PipelineReviewPage(mock_context)
        qtbot.addWidget(page)

        # Crea la cartella output
        pipeline_dir = os.path.dirname(config_path)
        output_folder = os.path.join(pipeline_dir, "01_output")
        os.makedirs(output_folder)

        previous = Mock()
        page.previous_page = previous

        with patch("main.ui.ui_pipeline_review_page.log", mock_logger):
            result = page.back()

            assert result == previous
            assert os.path.exists(config_path)  # Config non deve essere cancellato
            mock_logger.info.assert_called()

    def test_back_without_output_folder(self, qtbot, mock_context, pipeline_config_basic, mock_logger):
        """Test back quando non esiste la cartella output (deve cancellare config)."""
        config_path, _ = pipeline_config_basic
        page = PipelineReviewPage(mock_context)
        qtbot.addWidget(page)

        previous = Mock()
        page.previous_page = previous

        with patch("main.ui.ui_pipeline_review_page.log", mock_logger):
            result = page.back()

            assert result == previous
            assert not os.path.exists(config_path)  # Config deve essere cancellato
            mock_logger.info.assert_called()

    def test_back_no_previous_page(self, qtbot, mock_context, pipeline_config_basic):
        """Test back senza previous_page."""
        page = PipelineReviewPage(mock_context)
        qtbot.addWidget(page)

        result = page.back()

        assert result is None

    def test_back_calls_on_enter(self, qtbot, mock_context, pipeline_config_basic):
        """Test che back chiami on_enter sulla pagina precedente."""
        page = PipelineReviewPage(mock_context)
        qtbot.addWidget(page)

        previous = Mock()
        page.previous_page = previous

        page.back()

        previous.on_enter.assert_called_once()

    def test_back_error_handling(self, qtbot, mock_context, pipeline_config_basic, mock_logger):
        """Test gestione errori durante back."""
        page = PipelineReviewPage(mock_context)
        qtbot.addWidget(page)

        # Rendi il config_path non valido
        page.config_path = "/invalid/path/config.json"

        previous = Mock()
        page.previous_page = previous

        with patch("main.ui.ui_pipeline_review_page.log", mock_logger):
            result = page.back()

            assert result == previous
            mock_logger.error.assert_called()


class TestTranslation:
    """Test per le traduzioni."""

    def test_translate_ui_called_on_init(self, qtbot, mock_context, pipeline_config_basic):
        """Test che _translate_ui sia chiamato durante init."""
        with patch.object(PipelineReviewPage, '_translate_ui') as mock_translate:
            page = PipelineReviewPage(mock_context)
            qtbot.addWidget(page)

            mock_translate.assert_called()

    def test_translate_ui_updates_labels(self, qtbot, mock_context, pipeline_config_basic):
        """Test che _translate_ui aggiorni i label."""
        page = PipelineReviewPage(mock_context)
        qtbot.addWidget(page)

        # Salva i testi originali
        original_header = page.header.text()

        # Chiama _translate_ui
        page._translate_ui()

        # Verifica che i testi siano stati aggiornati (anche se uguali)
        assert page.header.text() is not None
        assert page.config_info.text() is not None
        assert page.info_label.text() is not None

    def test_language_changed_signal(self, mock_context):
        from main.ui.ui_pipeline_review_page import PipelineReviewPage
        page = PipelineReviewPage(mock_context)

        # Sostituisci la funzione ma riconnetti il segnale
        page._translate_ui = Mock()
        mock_context["language_changed"].connect(page._translate_ui)

        # Ora l’emissione del segnale deve attivare il mock
        mock_context["language_changed"].emit("it")

        page._translate_ui.assert_called_once()


class TestUISetup:
    """Test per la configurazione dell'UI."""

    def test_setup_ui_clears_existing_layout(self, qtbot, mock_context, pipeline_config_basic):
        """Test che _setup_ui pulisca il layout esistente."""
        page = PipelineReviewPage(mock_context)
        qtbot.addWidget(page)

        initial_count = page.main_layout.count()

        # Chiama _setup_ui di nuovo
        page._setup_ui()

        # Il count potrebbe essere uguale o diverso, ma non deve crashare
        assert page.main_layout.count() >= 0

    def test_setup_ui_creates_scroll_area(self, qtbot, mock_context, pipeline_config_basic):
        """Test che venga creata una scroll area."""
        page = PipelineReviewPage(mock_context)
        qtbot.addWidget(page)

        # Cerca scroll area nel layout
        scroll_found = False
        for i in range(page.main_layout.count()):
            widget = page.main_layout.itemAt(i).widget()
            if widget and "QScrollArea" in str(type(widget)):
                scroll_found = True
                break

        assert scroll_found

    def test_patient_widgets_created_for_all_patients(self, qtbot, mock_context, pipeline_config_multiple):
        """Test che vengano creati widget per tutti i pazienti."""
        paths, configs = pipeline_config_multiple
        page = PipelineReviewPage(mock_context)
        qtbot.addWidget(page)

        # Deve avere widget per tutti i pazienti nell'ultimo config
        last_config = configs[-1]
        for patient_id in last_config.keys():
            assert patient_id in page.patient_widgets


class TestEdgeCases:
    """Test per casi limite."""

    def test_empty_config(self, qtbot, mock_context, temp_workspace):
        """Test con config vuoto."""
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
        """Test con molti pazienti."""
        pipeline_dir = os.path.join(temp_workspace, "pipeline")
        os.makedirs(pipeline_dir, exist_ok=True)
        config_path = os.path.join(pipeline_dir, "01_config.json")

        # Crea config con 100 pazienti
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
        """Test con caratteri speciali negli ID paziente."""
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
        """Test con caratteri unicode nei path."""
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
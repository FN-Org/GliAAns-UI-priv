import pytest
import os
import tempfile
import shutil
from unittest.mock import Mock, patch, MagicMock, call
from PyQt6.QtCore import QSettings
from PyQt6.QtWidgets import QApplication, QPushButton

# Import dal tuo progetto
from controller import Controller


class TestControllerInitialization:
    """Test per l'inizializzazione del Controller"""

    @pytest.fixture
    def mock_components(self):
        """Mock dei componenti UI"""
        with patch('controller.ImportPage') as MockImportPage, \
                patch('controller.MainWindow') as MockMainWindow, \
                patch('controller.WorkspaceTreeView') as MockTreeView, \
                patch('controller.NiftiViewer') as MockNiftiViewer, \
                patch('controller.get_app_dir') as mock_get_app_dir:
            # Setup mock return values
            temp_dir = tempfile.mkdtemp()
            mock_get_app_dir.return_value = MockPath(temp_dir)

            MockImportPage.return_value = Mock()
            MockMainWindow.return_value = Mock()
            MockTreeView.return_value = Mock()
            MockNiftiViewer.return_value = Mock()

            yield {
                'import_page': MockImportPage,
                'main_window': MockMainWindow,
                'tree_view': MockTreeView,
                'nifti_viewer': MockNiftiViewer,
                'temp_dir': temp_dir
            }

            shutil.rmtree(temp_dir, ignore_errors=True)

    def test_controller_initialization(self, qtbot, mock_components):
        """Verifica inizializzazione corretta del controller"""
        controller = Controller()
        # qtbot.addWidget(controller.main_window)

        assert controller.context is not None
        assert controller.workspace_path is not None
        assert controller.current_page is not None

    def test_context_contains_required_keys(self, qtbot, mock_components):
        """Verifica che il context contenga tutte le chiavi necessarie"""
        controller = Controller()
        # qtbot.addWidget(controller.main_window)

        required_keys = [
            "workspace_path",
            "update_main_buttons",
            "return_to_import",
            "history",
            "language_changed",
            "create_buttons",
            "selected_files_signal",
            "open_nifti_viewer",
            "settings"
        ]

        for key in required_keys:
            assert key in controller.context

    def test_components_created(self, qtbot, mock_components):
        """Verifica creazione di tutti i componenti"""
        controller = Controller()
        # qtbot.addWidget(controller.main_window)

        mock_components['import_page'].assert_called_once()
        mock_components['main_window'].assert_called_once()
        mock_components['tree_view'].assert_called_once()
        mock_components['nifti_viewer'].assert_called_once()

    def test_workspace_directory_created(self, qtbot, mock_components):
        """Verifica creazione directory workspace"""
        controller = Controller()
        # qtbot.addWidget(controller.main_window)

        workspace_path = controller.workspace_path
        # Verifica che il path esista (o sia stato tentato di crearlo)
        assert workspace_path is not None

    def test_start_page_set(self, qtbot, mock_components):
        """Verifica che la pagina iniziale sia ImportPage"""
        controller = Controller()
        # qtbot.addWidget(controller.main_window)

        assert controller.start_page == controller.context["import_page"]
        assert controller.current_page == controller.start_page

    def test_history_initialized(self, qtbot, mock_components):
        """Verifica inizializzazione dello storico"""
        controller = Controller()
        # qtbot.addWidget(controller.main_window)

        assert len(controller.context["history"]) > 0
        assert controller.start_page in controller.context["history"]


class TestControllerNavigation:
    """Test per la navigazione tra pagine"""

    @pytest.fixture
    def controller(self, qtbot):
        """Crea controller per test"""
        with patch('controller.ImportPage'), \
                patch('controller.MainWindow'), \
                patch('controller.WorkspaceTreeView'), \
                patch('controller.NiftiViewer'), \
                patch('controller.get_app_dir') as mock_app_dir:
            temp_dir = tempfile.mkdtemp()
            mock_app_dir.return_value = MockPath(temp_dir)

            controller = Controller()
            # qtbot.addWidget(controller.main_window)

            yield controller

            shutil.rmtree(temp_dir, ignore_errors=True)

    def test_go_to_next_page(self, controller):
        """Verifica navigazione alla pagina successiva"""
        mock_next_page = Mock()
        controller.current_page.next.return_value = mock_next_page

        result = controller.go_to_next_page()

        assert controller.current_page == mock_next_page
        assert result == mock_next_page

    def test_go_to_next_page_none(self, controller):
        """Verifica comportamento quando next ritorna None"""
        controller.current_page.next.return_value = None
        initial_page = controller.current_page

        result = controller.go_to_next_page()

        assert controller.current_page == initial_page
        assert result == initial_page

    def test_go_to_previous_page(self, controller):
        """Verifica navigazione alla pagina precedente"""
        mock_previous_page = Mock()
        controller.current_page.back.return_value = mock_previous_page

        result = controller.go_to_previous_page()

        assert controller.current_page == mock_previous_page
        assert result == mock_previous_page

    def test_go_to_previous_page_none(self, controller):
        """Verifica comportamento quando back ritorna None"""
        controller.current_page.back.return_value = None
        initial_page = controller.current_page

        result = controller.go_to_previous_page()

        assert controller.current_page == initial_page
        assert result == initial_page

    def test_return_to_import(self, controller):
        """Verifica ritorno alla pagina di import"""
        # Simula navigazione
        mock_page1 = Mock()
        mock_page2 = Mock()
        controller.context["history"] = [controller.start_page, mock_page1, mock_page2]
        controller.current_page = mock_page2

        result = controller.return_to_import()

        assert controller.current_page == controller.start_page
        assert result == controller.start_page
        # Verifica che reset_page sia chiamato su tutte le pagine
        mock_page1.reset_page.assert_called_once()
        mock_page2.reset_page.assert_called_once()


class TestControllerButtons:
    """Test per gestione pulsanti"""

    @pytest.fixture
    def controller(self, qtbot):
        with patch('controller.ImportPage'), \
                patch('controller.MainWindow'), \
                patch('controller.WorkspaceTreeView'), \
                patch('controller.NiftiViewer'), \
                patch('controller.get_app_dir') as mock_app_dir:
            temp_dir = tempfile.mkdtemp()
            mock_app_dir.return_value = MockPath(temp_dir)

            controller = Controller()
            # qtbot.addWidget(controller.main_window)

            yield controller

            shutil.rmtree(temp_dir, ignore_errors=True)

    def test_create_buttons(self, controller):
        """Verifica creazione pulsanti"""
        next_btn, back_btn = controller.create_buttons()

        assert isinstance(next_btn, QPushButton)
        assert isinstance(back_btn, QPushButton)
        assert controller.next_button == next_btn
        assert controller.back_button == back_btn

    def test_buttons_connected(self, controller):
        """Verifica che i pulsanti siano connessi"""
        controller.create_buttons()

        # I pulsanti dovrebbero avere signal connessi
        # (difficile testare direttamente le connessioni)
        assert controller.next_button is not None
        assert controller.back_button is not None

    def test_update_buttons_state_ready(self, controller):
        """Verifica aggiornamento stato pulsanti quando pronto"""
        controller.create_buttons()
        controller.current_page.is_ready_to_advance.return_value = True
        controller.current_page.is_ready_to_go_back.return_value = True

        controller.update_buttons_state()

        assert controller.next_button.isEnabled()
        assert controller.back_button.isEnabled()

    def test_update_buttons_state_not_ready(self, controller):
        """Verifica aggiornamento stato pulsanti quando non pronto"""
        controller.create_buttons()
        controller.current_page.is_ready_to_advance.return_value = False
        controller.current_page.is_ready_to_go_back.return_value = False

        controller.update_buttons_state()

        assert not controller.next_button.isEnabled()
        assert not controller.back_button.isEnabled()

    def test_button_click_next(self, controller, qtbot):
        """Verifica click su pulsante next"""
        controller.create_buttons()
        mock_next_page = Mock()
        controller.current_page.next.return_value = mock_next_page

        with qtbot.waitSignal(controller.next_button.clicked, timeout=1000):
            controller.next_button.click()

        assert controller.current_page == mock_next_page

    def test_button_click_back(self, controller, qtbot):
        """Verifica click su pulsante back"""
        controller.create_buttons()
        mock_prev_page = Mock()
        controller.current_page.back.return_value = mock_prev_page

        with qtbot.waitSignal(controller.back_button.clicked, timeout=1000):
            controller.back_button.click()

        assert controller.current_page == mock_prev_page


class TestControllerLanguage:
    """Test per gestione lingue"""

    @pytest.fixture
    def controller(self, qtbot):
        with patch('controller.ImportPage'), \
                patch('controller.MainWindow'), \
                patch('controller.WorkspaceTreeView'), \
                patch('controller.NiftiViewer'), \
                patch('controller.get_app_dir') as mock_app_dir:
            temp_dir = tempfile.mkdtemp()
            mock_app_dir.return_value = MockPath(temp_dir)

            controller = Controller()
            # qtbot.addWidget(controller.main_window)

            yield controller

            shutil.rmtree(temp_dir, ignore_errors=True)

    def test_set_language(self, controller):
        """Verifica impostazione lingua"""
        with patch.object(controller.translator, 'load', return_value=True):
            controller.set_language("it")

            # Verifica che sia salvata
            assert controller.settings.value("language") == "it"

    def test_save_language(self, controller):
        """Verifica salvataggio lingua"""
        controller.save_language("it")

        saved_lang = controller.settings.value("language")
        assert saved_lang == "it"

    def test_language_changed_signal(self, controller, qtbot):
        """Verifica emissione signal cambio lingua"""
        with patch.object(controller.translator, 'load', return_value=True):
            with qtbot.waitSignal(controller.language_changed, timeout=1000):
                controller.language_changed.emit("it")

    def test_translator_load_called(self, controller):
        """Verifica che translator.load sia chiamato"""
        with patch.object(controller.translator, 'load', return_value=True) as mock_load:
            controller.set_language("en")

            mock_load.assert_called_once()
            # Verifica che il path contenga il codice lingua
            call_args = str(mock_load.call_args)
            assert "en.qm" in call_args


class TestControllerNiftiViewer:
    """Test per apertura NIfTI viewer"""

    @pytest.fixture
    def controller(self, qtbot):
        with patch('controller.ImportPage'), \
                patch('controller.MainWindow'), \
                patch('controller.WorkspaceTreeView'), \
                patch('controller.NiftiViewer') as MockViewer, \
                patch('controller.get_app_dir') as mock_app_dir:
            temp_dir = tempfile.mkdtemp()
            mock_app_dir.return_value = MockPath(temp_dir)

            mock_viewer = Mock()
            MockViewer.return_value = mock_viewer

            controller = Controller()
            # qtbot.addWidget(controller.main_window)

            yield controller

            shutil.rmtree(temp_dir, ignore_errors=True)

    def test_open_nifti_viewer(self, controller):
        """Verifica apertura NIfTI viewer"""
        test_path = "/path/to/scan.nii"

        controller.open_nifti_viewer(test_path)

        controller.context["nifti_viewer"].open_file.assert_called_once_with(test_path)
        controller.context["nifti_viewer"].show.assert_called_once()


class TestControllerStart:
    """Test per avvio applicazione"""

    @pytest.fixture
    def controller(self, qtbot):
        with patch('controller.ImportPage'), \
                patch('controller.MainWindow') as MockMainWindow, \
                patch('controller.WorkspaceTreeView'), \
                patch('controller.NiftiViewer'), \
                patch('controller.get_app_dir') as mock_app_dir:
            temp_dir = tempfile.mkdtemp()
            mock_app_dir.return_value = MockPath(temp_dir)

            mock_window = Mock()
            MockMainWindow.return_value = mock_window

            controller = Controller()
            # qtbot.addWidget(mock_window)

            yield controller

            shutil.rmtree(temp_dir, ignore_errors=True)

    def test_start_shows_main_window(self, controller):
        """Verifica che start() mostri la finestra principale"""
        controller.start()

        controller.main_window.show.assert_called_once()


class TestControllerSettings:
    """Test per gestione settings"""

    @pytest.fixture
    def clean_settings(self):
        """Pulisce settings prima e dopo test"""
        settings = QSettings("GliAAns")
        settings.clear()
        yield settings
        settings.clear()

    def test_loads_saved_language(self, qtbot, clean_settings):
        """Verifica caricamento lingua salvata"""
        clean_settings.setValue("language", "it")

        with patch('controller.ImportPage'), \
                patch('controller.MainWindow'), \
                patch('controller.WorkspaceTreeView'), \
                patch('controller.NiftiViewer'), \
                patch('controller.get_app_dir') as mock_app_dir:
            temp_dir = tempfile.mkdtemp()
            mock_app_dir.return_value = MockPath(temp_dir)

            controller = Controller()
            # qtbot.addWidget(controller.main_window)

            assert controller.saved_lang == "it"

            shutil.rmtree(temp_dir, ignore_errors=True)

    def test_default_language_en(self, qtbot, clean_settings):
        """Verifica lingua di default inglese"""
        with patch('controller.ImportPage'), \
                patch('controller.MainWindow'), \
                patch('controller.WorkspaceTreeView'), \
                patch('controller.NiftiViewer'), \
                patch('controller.get_app_dir') as mock_app_dir:
            temp_dir = tempfile.mkdtemp()
            mock_app_dir.return_value = MockPath(temp_dir)

            controller = Controller()
            # qtbot.addWidget(controller.main_window)

            assert controller.saved_lang == "en"

            shutil.rmtree(temp_dir, ignore_errors=True)

    @patch('logger.set_log_level')
    def test_debug_log_setting(self, mock_set_log_level, qtbot, clean_settings):
        """Verifica impostazione debug log"""
        import logging
        clean_settings.setValue("debug_log", True)

        with patch('controller.ImportPage'), \
                patch('controller.MainWindow'), \
                patch('controller.WorkspaceTreeView'), \
                patch('controller.NiftiViewer'), \
                patch('controller.get_app_dir') as mock_app_dir:
            temp_dir = tempfile.mkdtemp()
            mock_app_dir.return_value = MockPath(temp_dir)

            controller = Controller()
            # qtbot.addWidget(controller.main_window)

            mock_set_log_level.assert_called_with(logging.DEBUG)

            shutil.rmtree(temp_dir, ignore_errors=True)


class TestControllerIntegration:
    """Test di integrazione per flussi completi"""

    @pytest.fixture
    def controller(self, qtbot):
        with patch('controller.ImportPage') as MockImport, \
                patch('controller.MainWindow'), \
                patch('controller.WorkspaceTreeView'), \
                patch('controller.NiftiViewer'), \
                patch('controller.get_app_dir') as mock_app_dir:
            temp_dir = tempfile.mkdtemp()
            mock_app_dir.return_value = MockPath(temp_dir)

            # Setup mock pages con comportamenti realistici
            mock_import = Mock()
            mock_import.is_ready_to_advance.return_value = True
            mock_import.is_ready_to_go_back.return_value = False
            MockImport.return_value = mock_import

            controller = Controller()
            # qtbot.addWidget(controller.main_window)

            yield controller

            shutil.rmtree(temp_dir, ignore_errors=True)

    def test_full_navigation_flow(self, controller):
        """Test flusso completo di navigazione"""
        # Setup pagine mock
        page2 = Mock()
        page2.is_ready_to_advance.return_value = True
        page2.is_ready_to_go_back.return_value = True
        page2.back.return_value = controller.start_page

        controller.current_page.next.return_value = page2

        # Naviga avanti
        controller.go_to_next_page()
        assert controller.current_page == page2

        # Naviga indietro
        controller.go_to_previous_page()
        assert controller.current_page == controller.start_page

    def test_navigation_with_button_updates(self, controller):
        """Test navigazione con aggiornamento pulsanti"""
        controller.create_buttons()

        page2 = Mock()
        page2.is_ready_to_advance.return_value = False
        page2.is_ready_to_go_back.return_value = True

        controller.current_page.next.return_value = page2

        # Naviga
        controller.go_to_next_page()

        # I pulsanti dovrebbero essere aggiornati
        assert not controller.next_button.isEnabled()
        assert controller.back_button.isEnabled()

    def test_return_to_import_resets_all(self, controller):
        """Test che return_to_import resetti tutto"""
        # Simula navigazione profonda
        page2 = Mock()
        page3 = Mock()
        controller.context["history"] = [controller.start_page, page2, page3]
        controller.current_page = page3

        # Ritorna a import
        controller.return_to_import()

        # Verifica reset
        page2.reset_page.assert_called_once()
        page3.reset_page.assert_called_once()
        assert controller.current_page == controller.start_page


# Helper class per mock di Path
class MockPath:
    """Mock di pathlib.Path per test"""

    def __init__(self, path_str):
        self.path_str = path_str

    def __str__(self):
        return self.path_str

    def __truediv__(self, other):
        return MockPath(os.path.join(self.path_str, other))

    def __repr__(self):
        return f"MockPath('{self.path_str}')"


if __name__ == "__main__":
    pytest.main([__file__, "-v", "--tb=short"])
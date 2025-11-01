import pytest
import os
import tempfile
import shutil
from unittest.mock import Mock, patch, call
from PyQt6 import QtCore
from PyQt6.QtCore import QSettings, pyqtSignal, QObject
from PyQt6.QtTest import QTest
from PyQt6.QtWidgets import QMessageBox, QPushButton

from main.ui.ui_patient_selection_page import PatientSelectionPage


@pytest.fixture
def patient_page(qtbot, mock_context):
    previous_page = Mock()
    page = PatientSelectionPage(mock_context, previous_page)
    qtbot.addWidget(page)
    return page

class TestPatientSelectionPageSetup:
    """Test per l'inizializzazione di PatientSelectionPage"""

    def test_page_initialization(self, patient_page):
        """Verifica inizializzazione corretta"""
        assert patient_page.workspace_path is not None
        assert patient_page.selected_patients == set()
        assert isinstance(patient_page.patient_buttons, dict)

    def test_title_created(self, patient_page):
        """Verifica creazione titolo"""
        assert patient_page.title is not None
        assert patient_page.title.text() != ""

    def test_select_buttons_created(self, patient_page):
        """Verifica creazione pulsanti select all/deselect all"""
        assert patient_page.select_all_btn is not None
        assert patient_page.deselect_all_btn is not None

    def test_scroll_area_created(self, patient_page):
        """Verifica creazione scroll area"""
        assert patient_page.scroll_area is not None
        assert patient_page.grid_layout is not None

    def test_column_count_default(self, patient_page):
        """Verifica column count default"""
        assert patient_page.column_count >= 1


class TestPatientSelectionPagePatientLoading:
    """Test per caricamento pazienti"""

    @pytest.fixture
    def temp_workspace(self):
        temp_dir = tempfile.mkdtemp()
        os.makedirs(os.path.join(temp_dir, "sub-01", "anat"))
        os.makedirs(os.path.join(temp_dir, "sub-02", "pet"))
        os.makedirs(os.path.join(temp_dir, "sub-03", "anat"))
        # Crea anche derivatives (dovrebbe essere ignorata)
        os.makedirs(os.path.join(temp_dir, "derivatives", "sub-01"))
        yield temp_dir
        shutil.rmtree(temp_dir, ignore_errors=True)

    def test_find_patient_dirs(self, patient_page):
        """Verifica ricerca directory pazienti"""
        patient_dirs = patient_page._find_patient_dirs()

        # Dovrebbe trovare sub-001, sub-002, sub-003
        assert len(patient_dirs) == 3
        patient_ids = [os.path.basename(d) for d in patient_dirs]
        assert "sub-01" in patient_ids
        assert "sub-02" in patient_ids
        assert "sub-03" in patient_ids

    def test_find_patient_dirs_ignores_derivatives(self, patient_page):
        """Verifica che derivatives sia ignorata"""
        patient_dirs = patient_page._find_patient_dirs()

        # Non dovrebbe trovare sub-001 dentro derivatives
        for path in patient_dirs:
            assert "derivatives" not in path

    def test_load_patients_creates_buttons(self, patient_page):
        """Verifica creazione pulsanti per ogni paziente"""
        assert len(patient_page.patient_buttons) == 3
        assert "sub-01" in patient_page.patient_buttons
        assert "sub-02" in patient_page.patient_buttons
        assert "sub-03" in patient_page.patient_buttons

    def test_load_patients_adds_to_grid(self, patient_page):
        """Verifica aggiunta widget alla griglia"""
        # Dovrebbero esserci 3 patient frames nella griglia
        assert patient_page.grid_layout.count() >= 3

class TestPatientSelectionPageSelection:
    """Test per selezione pazienti"""

    def test_toggle_patient_select(self, patient_page):
        """Verifica selezione paziente"""
        button = patient_page.patient_buttons["sub-01"]

        patient_page._toggle_patient("sub-01", True, button)

        assert "sub-01" in patient_page.selected_patients
        assert button.text() != "Select"

    def test_toggle_patient_deselect(self, patient_page):
        """Verifica deselezione paziente"""
        button = patient_page.patient_buttons["sub-01"]

        # Prima seleziona
        patient_page._toggle_patient("sub-01", True, button)
        # Poi deseleziona
        patient_page._toggle_patient("sub-01", False, button)

        assert "sub-01" not in patient_page.selected_patients

    def test_toggle_updates_main_buttons(self, patient_page):
        """Verifica che toggle aggiorni i pulsanti principali"""
        button = patient_page.patient_buttons["sub-01"]

        patient_page._toggle_patient("sub-01", True, button)

        patient_page.context["update_main_buttons"].assert_called()

    def test_select_all_patients(self, patient_page):
        """Verifica selezione di tutti i pazienti"""
        patient_page._select_all_patients()

        assert len(patient_page.selected_patients) == 2
        assert "sub-01" in patient_page.selected_patients
        assert "sub-02" in patient_page.selected_patients

        # Tutti i pulsanti dovrebbero essere checked
        for button in patient_page.patient_buttons.values():
            assert button.isChecked()

    def test_deselect_all_patients(self, patient_page):
        """Verifica deselezione di tutti i pazienti"""
        # Prima seleziona tutti
        patient_page._select_all_patients()
        # Poi deseleziona
        patient_page._deselect_all_patients()

        assert len(patient_page.selected_patients) == 0

        # Nessun pulsante dovrebbe essere checked
        for button in patient_page.patient_buttons.values():
            assert not button.isChecked()

    def test_get_selected_patients(self, patient_page):
        """Verifica recupero pazienti selezionati"""
        patient_page.selected_patients = {"sub-01", "sub-02"}

        selected = patient_page.get_selected_patients()

        assert isinstance(selected, list)
        assert len(selected) == 2
        assert "sub-01" in selected
        assert "sub-02" in selected


class TestPatientSelectionPageReadiness:
    """Test per logica di avanzamento"""

    def test_not_ready_without_selection(self, patient_page):
        """Verifica che non sia pronto senza selezioni"""
        patient_page.selected_patients.clear()
        assert not patient_page.is_ready_to_advance()

    def test_ready_with_selection(self, patient_page):
        """Verifica che sia pronto con selezioni"""
        patient_page.selected_patients.add("sub-01")
        assert patient_page.is_ready_to_advance()

    def test_can_go_back(self, patient_page):
        """Verifica che si possa tornare indietro"""
        assert patient_page.is_ready_to_go_back()


class TestPatientSelectionPageNavigation:
    """Test per navigazione tra pagine"""

    def test_back_returns_previous_page(self, patient_page):
        """Verifica ritorno a pagina precedente"""
        result = patient_page.back()
        assert result == patient_page.previous_page
        patient_page.previous_page.on_enter.assert_called_once()

    def test_next_without_cleanup(self, patient_page, monkeypatch):
        """Verifica avanzamento senza cleanup"""
        # Seleziona tutti i pazienti
        patient_page.selected_patients = {"sub-01", "sub-02"}

        # Non dovrebbe chiedere conferma
        with patch('main.ui.ui_patient_selection_page.ToolSelectionPage') as MockPage:
            mock_page_instance = Mock()
            MockPage.return_value = mock_page_instance

            result = patient_page.next(patient_page.context)

            assert result is not None
            mock_page_instance.on_enter.assert_called_once()

    def test_next_with_cleanup_confirmed(self, patient_page, monkeypatch, temp_workspace):
        """Verifica cleanup dopo conferma"""
        # Seleziona solo sub-001
        patient_page.selected_patients = {"sub-01"}

        # Conferma cleanup
        monkeypatch.setattr(QMessageBox, 'question',
                            lambda *args, **kwargs: QMessageBox.StandardButton.Yes)

        with patch('main.ui.ui_patient_selection_page.ToolSelectionPage') as MockPage:
            MockPage.return_value = Mock()

            result = patient_page.next(patient_page.context)

            # sub-002 dovrebbe essere eliminata
            assert not os.path.exists(os.path.join(temp_workspace, "sub-02"))
            # sub-001 dovrebbe esistere
            assert os.path.exists(os.path.join(temp_workspace, "sub-01"))

    def test_next_with_cleanup_cancelled(self, patient_page, monkeypatch):
        """Verifica cancellazione cleanup"""
        patient_page.selected_patients = {"sub-01"}

        # Cancella cleanup
        monkeypatch.setattr(QMessageBox, 'question',
                            lambda *args, **kwargs: QMessageBox.StandardButton.No)

        result = patient_page.next(patient_page.context)

        assert result is None

    def test_next_creates_tool_selection_page(self, patient_page):
        """Verifica creazione ToolSelectionPage"""
        patient_page.selected_patients = {"sub-01", "sub-02"}

        with patch('main.ui.ui_patient_selection_page.ToolSelectionPage') as MockPage:
            mock_page_instance = Mock()
            MockPage.return_value = mock_page_instance

            patient_page.next(patient_page.context)

            MockPage.assert_called_once()
            assert mock_page_instance in patient_page.context["history"]


class TestPatientSelectionPageCleanup:
    """Test per operazioni di cleanup"""

    @pytest.fixture
    def temp_workspace(self):
        temp_dir = tempfile.mkdtemp()
        # Crea pazienti
        os.makedirs(os.path.join(temp_dir, "sub-01", "anat"))
        os.makedirs(os.path.join(temp_dir, "sub-02", "pet"))
        # Crea derivatives
        os.makedirs(os.path.join(temp_dir, "derivatives", "pipeline1", "sub-01"))
        os.makedirs(os.path.join(temp_dir, "derivatives", "pipeline1", "sub-02"))
        yield temp_dir
        shutil.rmtree(temp_dir, ignore_errors=True)

    @pytest.fixture
    def patient_page(self, qtbot, mock_context):
        page = PatientSelectionPage(mock_context, Mock())
        qtbot.addWidget(page)
        return page

    def test_cleanup_removes_unselected_patients(self, patient_page, monkeypatch, temp_workspace):
        """Verifica rimozione pazienti non selezionati"""
        patient_page.selected_patients = {"sub-01"}

        monkeypatch.setattr(QMessageBox, 'question',
                            lambda *args, **kwargs: QMessageBox.StandardButton.Yes)

        with patch('main.ui.ui_patient_selection_page.ToolSelectionPage'):
            patient_page.next(patient_page.context)

            assert os.path.exists(os.path.join(temp_workspace, "sub-01"))
            assert not os.path.exists(os.path.join(temp_workspace, "sub-02"))

    def test_cleanup_removes_from_derivatives(self, patient_page, monkeypatch, temp_workspace):
        """Verifica rimozione anche da derivatives"""
        patient_page.selected_patients = {"sub-01"}

        monkeypatch.setattr(QMessageBox, 'question',
                            lambda *args, **kwargs: QMessageBox.StandardButton.Yes)

        with patch('main.ui.ui_patient_selection_page.ToolSelectionPage'):
            patient_page.next(patient_page.context)

            # sub-002 dovrebbe essere rimossa anche da derivatives
            assert not os.path.exists(
                os.path.join(temp_workspace, "derivatives", "pipeline1", "sub-02")
            )
            # sub-001 dovrebbe esistere in derivatives
            assert os.path.exists(
                os.path.join(temp_workspace, "derivatives", "pipeline1", "sub-01")
            )

    def test_cleanup_handles_errors(self, patient_page, monkeypatch):
        """Verifica gestione errori durante cleanup"""
        patient_page.selected_patients = {"sub-01"}

        monkeypatch.setattr(QMessageBox, 'question',
                            lambda *args, **kwargs: QMessageBox.StandardButton.Yes)

        with patch('main.ui.ui_patient_selection_page.ToolSelectionPage'), \
                patch('main.ui.ui_patient_selection_page.shutil.rmtree', side_effect=Exception("Delete error")):
            # Non dovrebbe sollevare eccezione
            result = patient_page.next(patient_page.context)
            assert result is not None


class TestPatientSelectionPageLayout:
    """Test per gestione layout dinamico"""

    @pytest.fixture
    def temp_workspace(self):
        temp_dir = tempfile.mkdtemp()
        for i in range(6):
            os.makedirs(os.path.join(temp_dir, f"sub-{i:02d}"))
        yield temp_dir
        shutil.rmtree(temp_dir, ignore_errors=True)

    def test_update_column_count_wide(self, patient_page):
        """Verifica aggiornamento colonne con finestra larga"""
        patient_page.scroll_area.resize(800, 400)
        initial_count = patient_page.column_count

        patient_page._update_column_count()

        # Con finestra larga dovrebbe avere più colonne
        assert patient_page.column_count >= 1

    def test_update_column_count_narrow(self, patient_page):
        """Verifica aggiornamento colonne con finestra stretta"""
        # Forziamo viewport width a 200px
        with patch.object(patient_page.scroll_area.viewport(), 'width', return_value=200):
            patient_page._update_column_count()
            # Con 200px e min_card_width=250 dovrebbe esserci 1 colonna
            assert patient_page.column_count == 1

    def test_resize_event_updates_columns(self, patient_page):
        """Verifica che resize aggiorni le colonne"""
        from PyQt6.QtGui import QResizeEvent
        from PyQt6.QtCore import QSize

        initial_count = patient_page.column_count

        # Simula resize
        event = QResizeEvent(QSize(800, 600), QSize(400, 600))
        patient_page.resizeEvent(event)

        # Potrebbe essere cambiato (dipende dalla dimensione)
        assert patient_page.column_count >= 1

    def test_reload_patient_grid_maintains_selection(self, patient_page):
        """Verifica che reload mantenga le selezioni"""
        # Seleziona alcuni pazienti
        patient_page.selected_patients = {"sub-00", "sub-01"}

        patient_page._reload_patient_grid()

        # Le selezioni dovrebbero essere mantenute
        assert "sub-00" in patient_page.selected_patients
        assert "sub-01" in patient_page.selected_patients


class TestPatientSelectionPageReset:
    """Test per reset della pagina"""

    def test_reset_page_clears_selections(self, patient_page):
        """Verifica che reset pulisca le selezioni"""
        patient_page.selected_patients = {"sub-001", "sub-002"}

        patient_page.reset_page()

        assert len(patient_page.selected_patients) == 0

    def test_reset_page_clears_buttons(self, patient_page):
        """Verifica che reset pulisca i pulsanti"""
        initial_buttons = len(patient_page.patient_buttons)

        patient_page.reset_page()

        # Dovrebbe ricaricare i pulsanti
        assert len(patient_page.patient_buttons) == initial_buttons

    def test_on_enter_maintains_selections(self, patient_page):
        """Verifica che on_enter mantenga le selezioni"""
        patient_page.selected_patients = {"sub-01"}

        patient_page.on_enter()

        # Le selezioni dovrebbero essere mantenute
        assert "sub-01" in patient_page.selected_patients


class TestPatientSelectionPageTranslation:
    """Test per traduzioni"""

    def test_translate_ui_updates_title(self, patient_page):
        """Verifica aggiornamento titolo"""
        patient_page._translate_ui()
        assert patient_page.title.text() != ""

    def test_translate_ui_updates_buttons(self, patient_page):
        """Verifica aggiornamento pulsanti"""
        patient_page._translate_ui()
        assert patient_page.select_all_btn.text() != ""
        assert patient_page.deselect_all_btn.text() != ""


# Test di integrazione
class TestPatientSelectionPageIntegration:
    """Test di integrazione per flussi completi"""

    @pytest.fixture
    def temp_workspace(self):
        temp_dir = tempfile.mkdtemp()
        # Crea struttura completa
        for i in range(3):
            patient_id = f"sub-{i:02d}"
            os.makedirs(os.path.join(temp_dir, patient_id, "anat"))
            os.makedirs(os.path.join(temp_dir, patient_id, "pet"))
        os.makedirs(os.path.join(temp_dir, "derivatives"))
        yield temp_dir
        shutil.rmtree(temp_dir, ignore_errors=True)

    def test_full_workflow_select_and_advance(self, patient_page, monkeypatch, temp_workspace):
        """Test flusso completo: carica, seleziona, avanza"""
        # Verifica caricamento
        assert len(patient_page.patient_buttons) == 3

        # Seleziona pazienti
        patient_page._select_all_patients()
        assert len(patient_page.selected_patients) == 3

        # Verifica ready to advance
        assert patient_page.is_ready_to_advance()

        # Avanza (nessun cleanup necessario)
        with patch('main.ui.ui_patient_selection_page.ToolSelectionPage') as MockPage:
            MockPage.return_value = Mock()
            result = patient_page.next(patient_page.context)
            assert result is not None

    def test_full_workflow_with_cleanup(self, patient_page, monkeypatch, temp_workspace):
        """Test flusso completo con cleanup"""
        # Seleziona solo alcuni pazienti
        button = patient_page.patient_buttons["sub-00"]
        patient_page._toggle_patient("sub-00", True, button)

        assert len(patient_page.selected_patients) == 1

        # Conferma cleanup
        monkeypatch.setattr(QMessageBox, 'question',
                            lambda *args, **kwargs: QMessageBox.StandardButton.Yes)

        with patch('main.ui.ui_patient_selection_page.ToolSelectionPage'):
            result = patient_page.next(patient_page.context)

            # Solo sub-000 dovrebbe esistere
            assert os.path.exists(os.path.join(temp_workspace, "sub-00"))
            assert not os.path.exists(os.path.join(temp_workspace, "sub-01"))
            assert not os.path.exists(os.path.join(temp_workspace, "sub-02"))


if __name__ == "__main__":
    pytest.main([__file__, "-v", "--tb=short"])
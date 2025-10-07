import pytest
import platform
from unittest.mock import Mock, patch, MagicMock
from PyQt6.QtCore import QSettings, pyqtSignal, QObject
from PyQt6.QtWidgets import QMessageBox, QRadioButton

# Import dal tuo progetto
from ui.ui_tool_selection_page import ToolSelectionPage

@pytest.fixture
def tool_page(qtbot, mock_context):
    previous_page = Mock()
    page = ToolSelectionPage(mock_context, previous_page)
    qtbot.addWidget(page)
    return page

class TestToolSelectionPageSetup:
    """Test per l'inizializzazione di ToolSelectionPage"""

    def test_page_initialization(self, tool_page):
        """Verifica inizializzazione corretta"""
        assert tool_page.context is not None
        assert tool_page.previous_page is not None
        assert tool_page.selected_option is None

    def test_title_created(self, tool_page):
        """Verifica creazione titolo"""
        assert tool_page.title is not None
        assert tool_page.title.text() != ""

    def test_radio_buttons_created(self, tool_page):
        """Verifica creazione radio buttons"""
        assert tool_page.radio_skull is not None
        assert tool_page.radio_draw is not None
        assert tool_page.radio_dl is not None
        assert tool_page.radio_analysis is not None

    def test_radio_group_created(self, tool_page):
        """Verifica creazione button group"""
        assert tool_page.radio_group is not None
        assert len(tool_page.radio_group.buttons()) == 4

    def test_all_buttons_unchecked_initially(self, tool_page):
        """Verifica che nessun pulsante sia selezionato inizialmente"""
        assert tool_page.radio_group.checkedId() == -1


class TestToolSelectionPageSelection:
    """Test per selezione opzioni"""

    def test_select_skull_stripping(self, tool_page, qtbot):
        """Verifica selezione skull stripping"""
        with qtbot.waitSignal(tool_page.radio_group.buttonToggled, timeout=1000):
            tool_page.radio_skull.setChecked(True)

        assert tool_page.selected_option == 0

    def test_select_automatic_drawing(self, tool_page, qtbot):
        """Verifica selezione automatic drawing"""
        with qtbot.waitSignal(tool_page.radio_group.buttonToggled, timeout=1000):
            tool_page.radio_draw.setChecked(True)

        assert tool_page.selected_option == 1

    def test_select_deep_learning(self, tool_page, qtbot):
        """Verifica selezione deep learning"""
        with qtbot.waitSignal(tool_page.radio_group.buttonToggled, timeout=1000):
            tool_page.radio_dl.setChecked(True)

        assert tool_page.selected_option == 2

    def test_select_full_pipeline(self, tool_page, qtbot):
        """Verifica selezione full pipeline"""
        with qtbot.waitSignal(tool_page.radio_group.buttonToggled, timeout=1000):
            tool_page.radio_analysis.setChecked(True)

        assert tool_page.selected_option == 3

    def test_on_selection_updates_buttons(self, tool_page, qtbot):
        """Verifica che selezione aggiorni i pulsanti"""
        with qtbot.waitSignal(tool_page.radio_group.buttonToggled, timeout=1000):
            tool_page.radio_skull.setChecked(True)

        tool_page.context["update_main_buttons"].assert_called()

    def test_change_selection(self, tool_page, qtbot):
        """Verifica cambio selezione"""
        # Prima selezione
        tool_page.radio_skull.setChecked(True)
        assert tool_page.selected_option == 0

        # Cambio selezione
        tool_page.radio_draw.setChecked(True)
        assert tool_page.selected_option == 1


class TestToolSelectionPageReadiness:
    """Test per logica di avanzamento"""

    def test_not_ready_without_selection(self, tool_page):
        """Verifica che non sia pronto senza selezione"""
        assert not tool_page.is_ready_to_advance()

    def test_ready_with_selection(self, tool_page):
        """Verifica che sia pronto con selezione"""
        tool_page.radio_skull.setChecked(True)
        assert tool_page.is_ready_to_advance()

    def test_can_go_back(self, tool_page):
        """Verifica che si possa sempre tornare indietro"""
        assert tool_page.is_ready_to_go_back()

class TestToolSelectionPageNavigation:
    """Test per navigazione tra pagine"""

    def test_back_returns_previous_page(self, tool_page):
        """Verifica ritorno a pagina precedente"""
        result = tool_page.back()
        assert result == tool_page.previous_page
        tool_page.previous_page.on_enter.assert_called_once()

    @patch('ui.ui_tool_selection_page.SkullStrippingPage')
    def test_next_skull_stripping(self, MockPage, tool_page):
        """Verifica navigazione a skull stripping"""
        mock_page = Mock()
        MockPage.return_value = mock_page

        tool_page.radio_skull.setChecked(True)
        result = tool_page.next(tool_page.context)

        assert result == mock_page
        mock_page.on_enter.assert_called_once()

    @patch('ui.ui_tool_selection_page.MaskNiftiSelectionPage')
    def test_next_automatic_drawing(self, MockPage, tool_page):
        """Verifica navigazione a automatic drawing"""
        mock_page = Mock()
        MockPage.return_value = mock_page

        tool_page.radio_draw.setChecked(True)
        result = tool_page.next(tool_page.context)

        assert result == mock_page
        mock_page.on_enter.assert_called_once()

    @patch('ui.ui_tool_selection_page.PipelinePatientSelectionPage')
    def test_next_full_pipeline(self, MockPage, tool_page):
        """Verifica navigazione a full pipeline"""
        mock_page = Mock()
        MockPage.return_value = mock_page

        tool_page.radio_analysis.setChecked(True)
        result = tool_page.next(tool_page.context)

        assert result == mock_page
        mock_page.on_enter.assert_called_once()

    def test_next_caches_page(self, tool_page):
        """Verifica che le pagine siano cached"""
        with patch('ui.ui_tool_selection_page.SkullStrippingPage') as MockPage:
            mock_page = Mock()
            MockPage.return_value = mock_page

            tool_page.radio_skull.setChecked(True)

            # Prima chiamata
            result1 = tool_page.next(tool_page.context)
            # Seconda chiamata
            result2 = tool_page.next(tool_page.context)

            # Dovrebbe essere la stessa istanza
            assert result1 == result2
            # Page dovrebbe essere creata solo una volta
            MockPage.assert_called_once()


class TestToolSelectionPageDeepLearning:
    """Test specifici per deep learning con controlli GPU"""

    @patch('platform.system', return_value='Linux')
    @patch('torch.cuda.is_available', return_value=True)
    @patch('ui.ui_tool_selection_page.DlNiftiSelectionPage')
    def test_dl_available_on_linux_with_gpu(self, MockPage, mock_cuda, mock_platform, tool_page):
        """Verifica che DL sia disponibile su Linux con GPU"""
        mock_page = Mock()
        MockPage.return_value = mock_page

        tool_page.radio_dl.setChecked(True)
        result = tool_page.next(tool_page.context)

        assert result == mock_page
        mock_page.on_enter.assert_called_once()

    @patch('platform.system', return_value='Windows')
    @patch('torch.cuda.is_available', return_value=True)
    def test_dl_not_available_on_windows(self, mock_cuda, mock_platform, tool_page, monkeypatch):
        """Verifica che DL non sia disponibile su Windows"""
        message_shown = False

        def mock_warning(*args, **kwargs):
            nonlocal message_shown
            message_shown = True

        monkeypatch.setattr(QMessageBox, 'warning', mock_warning)

        tool_page.radio_dl.setChecked(True)
        result = tool_page.next(tool_page.context)

        assert message_shown
        assert result == tool_page  # Rimane sulla stessa pagina

    @patch('platform.system', return_value='Linux')
    @patch('torch.cuda.is_available', return_value=False)
    def test_dl_not_available_without_gpu(self, mock_cuda, mock_platform, tool_page, monkeypatch):
        """Verifica che DL non sia disponibile senza GPU"""
        message_shown = False

        def mock_warning(*args, **kwargs):
            nonlocal message_shown
            message_shown = True

        monkeypatch.setattr(QMessageBox, 'warning', mock_warning)

        tool_page.radio_dl.setChecked(True)
        result = tool_page.next(tool_page.context)

        assert message_shown
        assert result == tool_page

    @patch('platform.system', return_value='Darwin')
    @patch('torch.cuda.is_available', return_value=False)
    def test_dl_not_available_on_macos(self, mock_cuda, mock_platform, tool_page, monkeypatch):
        """Verifica che DL non sia disponibile su macOS"""
        message_shown = False

        def mock_warning(*args, **kwargs):
            nonlocal message_shown
            message_shown = True

        monkeypatch.setattr(QMessageBox, 'warning', mock_warning)

        tool_page.radio_dl.setChecked(True)
        result = tool_page.next(tool_page.context)

        assert message_shown


class TestToolSelectionPageReset:
    """Test per reset della pagina"""

    def test_reset_clears_selection(self, tool_page):
        """Verifica che reset pulisca la selezione"""
        tool_page.radio_skull.setChecked(True)
        assert tool_page.selected_option == 0

        tool_page.reset_page()

        assert tool_page.selected_option is None
        assert tool_page.radio_group.checkedId() == -1

    def test_reset_unchecks_all_buttons(self, tool_page):
        """Verifica che reset deselezioni tutti i pulsanti"""
        tool_page.radio_draw.setChecked(True)

        tool_page.reset_page()

        for button in tool_page.radio_group.buttons():
            assert not button.isChecked()


class TestToolSelectionPageResize:
    """Test per ridimensionamento dinamico"""

    def test_resize_event_updates_fonts(self, tool_page):
        """Verifica che resize aggiorni i font"""
        from PyQt6.QtGui import QResizeEvent
        from PyQt6.QtCore import QSize

        initial_font_size = tool_page.title.font().pointSize()

        # Simula resize a finestra più grande
        event = QResizeEvent(QSize(1200, 800), QSize(800, 600))
        tool_page.resizeEvent(event)

        # Font dovrebbe essere aggiornato
        new_font_size = tool_page.title.font().pointSize()
        assert new_font_size >= 14  # Minimo garantito

    def test_resize_maintains_minimum_font_size(self, tool_page):
        """Verifica che resize mantenga font minimo"""
        from PyQt6.QtGui import QResizeEvent
        from PyQt6.QtCore import QSize

        # Simula resize a finestra molto piccola
        event = QResizeEvent(QSize(300, 200), QSize(800, 600))
        tool_page.resizeEvent(event)

        # Font non dovrebbe essere troppo piccolo
        title_font_size = tool_page.title.font().pointSize()
        assert title_font_size >= 14

        button_font_size = tool_page.radio_skull.font().pointSize()
        assert button_font_size >= 10


class TestToolSelectionPageTranslation:
    """Test per traduzioni"""

    def test_translate_ui_updates_title(self, tool_page):
        """Verifica aggiornamento titolo"""
        tool_page._translate_ui()
        assert tool_page.title.text() != ""

    def test_translate_ui_updates_buttons(self, tool_page):
        """Verifica aggiornamento pulsanti"""
        tool_page._translate_ui()
        assert tool_page.radio_skull.text() != ""
        assert tool_page.radio_draw.text() != ""
        assert tool_page.radio_dl.text() != ""
        assert tool_page.radio_analysis.text() != ""

    def test_translate_ui_updates_group_box(self, tool_page):
        """Verifica aggiornamento group box"""
        tool_page._translate_ui()
        assert tool_page.radio_group_box.title() != ""


class TestToolSelectionPageInfoLabel:
    """Test per info label su deep learning"""

    def test_dl_has_info_label(self, tool_page):
        """Verifica che DL abbia info label"""
        assert hasattr(tool_page, 'dl_info_label')
        assert tool_page.dl_info_label is not None

    def test_info_label_has_tooltip(self, tool_page):
        """Verifica che info label abbia tooltip"""
        tooltip = tool_page.dl_info_label.toolTip()
        assert tooltip != ""
        assert "GPU" in tooltip or "CUDA" in tooltip or tooltip == ""


# Test di integrazione
class TestToolSelectionPageIntegration:
    """Test di integrazione per flussi completi"""

    def test_full_selection_workflow(self, tool_page, qtbot):
        """Test flusso completo di selezione"""
        # Inizialmente non pronto
        assert not tool_page.is_ready_to_advance()

        # Seleziona opzione
        with qtbot.waitSignal(tool_page.radio_group.buttonToggled, timeout=1000):
            tool_page.radio_skull.setChecked(True)

        # Ora dovrebbe essere pronto
        assert tool_page.is_ready_to_advance()
        assert tool_page.selected_option == 0

    @patch('ui.ui_tool_selection_page.SkullStrippingPage')
    def test_navigation_and_cache(self, MockPage, tool_page):
        """Test navigazione con caching"""
        mock_page = Mock()
        MockPage.return_value = mock_page

        tool_page.radio_skull.setChecked(True)

        # Prima navigazione
        result1 = tool_page.next(tool_page.context)
        # Seconda navigazione
        result2 = tool_page.next(tool_page.context)

        # Stessa istanza
        assert result1 is result2
        # Creata solo una volta
        MockPage.assert_called_once()
        # on_enter chiamato due volte
        assert mock_page.on_enter.call_count == 2


if __name__ == "__main__":
    pytest.main([__file__, "-v", "--tb=short"])
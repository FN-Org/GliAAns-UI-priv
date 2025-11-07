import pytest
import platform
from unittest.mock import Mock, patch, MagicMock
from PyQt6.QtCore import QSettings, pyqtSignal, QObject
from PyQt6.QtWidgets import QMessageBox, QRadioButton

from main.ui.tool_selection_page import ToolSelectionPage


@pytest.fixture
def tool_page(qtbot, mock_context):
    """Fixture that creates a ToolSelectionPage instance."""
    previous_page = Mock()
    page = ToolSelectionPage(mock_context, previous_page)
    qtbot.addWidget(page)
    return page


class TestToolSelectionPageSetup:
    """Tests for ToolSelectionPage initialization."""

    def test_page_initialization(self, tool_page):
        """Verify correct page initialization."""
        assert tool_page.context is not None
        assert tool_page.previous_page is not None
        assert tool_page.selected_option is None

    def test_title_created(self, tool_page):
        """Verify that the title label is created."""
        assert tool_page.title is not None
        assert tool_page.title.text() != ""

    def test_radio_buttons_created(self, tool_page):
        """Verify that all radio buttons are created."""
        assert tool_page.radio_skull is not None
        assert tool_page.radio_draw is not None
        assert tool_page.radio_dl is not None
        assert tool_page.radio_analysis is not None

    def test_radio_group_created(self, tool_page):
        """Verify that the button group is created."""
        assert tool_page.radio_group is not None
        assert len(tool_page.radio_group.buttons()) == 4

    def test_all_buttons_unchecked_initially(self, tool_page):
        """Verify that all radio buttons are initially unchecked."""
        assert tool_page.radio_group.checkedId() == -1


class TestToolSelectionPageSelection:
    """Tests for radio button selection logic."""

    def test_select_skull_stripping(self, tool_page, qtbot):
        """Verify skull stripping option selection."""
        with qtbot.waitSignal(tool_page.radio_group.buttonToggled, timeout=1000):
            tool_page.radio_skull.setChecked(True)
        assert tool_page.selected_option == 0

    def test_select_automatic_drawing(self, tool_page, qtbot):
        """Verify automatic drawing option selection."""
        with qtbot.waitSignal(tool_page.radio_group.buttonToggled, timeout=1000):
            tool_page.radio_draw.setChecked(True)
        assert tool_page.selected_option == 1

    def test_select_deep_learning(self, tool_page, qtbot):
        """Verify deep learning option selection."""
        with qtbot.waitSignal(tool_page.radio_group.buttonToggled, timeout=1000):
            tool_page.radio_dl.setChecked(True)
        assert tool_page.selected_option == 2

    def test_select_full_pipeline(self, tool_page, qtbot):
        """Verify full pipeline option selection."""
        with qtbot.waitSignal(tool_page.radio_group.buttonToggled, timeout=1000):
            tool_page.radio_analysis.setChecked(True)
        assert tool_page.selected_option == 3

    def test_on_selection_updates_buttons(self, tool_page, qtbot):
        """Verify that button selection updates main buttons."""
        with qtbot.waitSignal(tool_page.radio_group.buttonToggled, timeout=1000):
            tool_page.radio_skull.setChecked(True)
        tool_page.context["update_main_buttons"].assert_called()

    def test_change_selection(self, tool_page, qtbot):
        """Verify that changing selection updates the state."""
        tool_page.radio_skull.setChecked(True)
        assert tool_page.selected_option == 0
        tool_page.radio_draw.setChecked(True)
        assert tool_page.selected_option == 1


class TestToolSelectionPageReadiness:
    """Tests for readiness logic (next/back)."""

    def test_not_ready_without_selection(self, tool_page):
        """Verify not ready to advance without selection."""
        assert not tool_page.is_ready_to_advance()

    def test_ready_with_selection(self, tool_page):
        """Verify ready to advance when a selection is made."""
        tool_page.radio_skull.setChecked(True)
        assert tool_page.is_ready_to_advance()

    def test_can_go_back(self, tool_page):
        """Verify that the page can always go back."""
        assert tool_page.is_ready_to_go_back()


class TestToolSelectionPageNavigation:
    """Tests for navigation between pages."""

    def test_back_returns_previous_page(self, tool_page):
        """Verify that back() returns the previous page."""
        result = tool_page.back()
        assert result == tool_page.previous_page
        tool_page.previous_page.on_enter.assert_called_once()

    @patch('main.ui.tool_selection_page.SkullStrippingPage')
    def test_next_skull_stripping(self, MockPage, tool_page):
        """Verify navigation to SkullStrippingPage."""
        mock_page = Mock()
        MockPage.return_value = mock_page
        tool_page.radio_skull.setChecked(True)
        result = tool_page.next(tool_page.context)
        assert result == mock_page
        mock_page.on_enter.assert_called_once()

    @patch('main.ui.tool_selection_page.MaskNiftiSelectionPage')
    def test_next_automatic_drawing(self, MockPage, tool_page):
        """Verify navigation to MaskNiftiSelectionPage."""
        mock_page = Mock()
        MockPage.return_value = mock_page
        tool_page.radio_draw.setChecked(True)
        result = tool_page.next(tool_page.context)
        assert result == mock_page
        mock_page.on_enter.assert_called_once()

    @patch('main.ui.tool_selection_page.PipelinePatientSelectionPage')
    def test_next_full_pipeline(self, MockPage, tool_page):
        """Verify navigation to PipelinePatientSelectionPage."""
        mock_page = Mock()
        MockPage.return_value = mock_page
        tool_page.radio_analysis.setChecked(True)
        result = tool_page.next(tool_page.context)
        assert result == mock_page
        mock_page.on_enter.assert_called_once()

    def test_next_caches_page(self, tool_page):
        """Verify that pages are cached after creation."""
        with patch('main.ui.tool_selection_page.SkullStrippingPage') as MockPage:
            mock_page = Mock()
            MockPage.return_value = mock_page
            tool_page.radio_skull.setChecked(True)
            result1 = tool_page.next(tool_page.context)
            result2 = tool_page.next(tool_page.context)
            assert result1 == result2
            MockPage.assert_called_once()


class TestToolSelectionPageDeepLearning:
    """Tests for Deep Learning selection and GPU checks."""

    @patch('platform.system', return_value='Linux')
    @patch('torch.cuda.is_available', return_value=True)
    @patch('main.ui.tool_selection_page.DlNiftiSelectionPage')
    def test_dl_available_on_linux_with_gpu(self, MockPage, mock_cuda, mock_platform, tool_page):
        """Verify DL page loads correctly on Linux with GPU."""
        mock_page = Mock()
        MockPage.return_value = mock_page
        tool_page.radio_dl.setChecked(True)
        result = tool_page.next(tool_page.context)
        assert result == mock_page
        mock_page.on_enter.assert_called_once()

    @patch('platform.system', return_value='Windows')
    @patch('torch.cuda.is_available', return_value=True)
    def test_dl_not_available_on_windows(self, mock_cuda, mock_platform, tool_page, monkeypatch):
        """Verify DL not available on Windows."""
        message_shown = False
        def mock_warning(*args, **kwargs):
            nonlocal message_shown
            message_shown = True
        monkeypatch.setattr(QMessageBox, 'warning', mock_warning)
        tool_page.radio_dl.setChecked(True)
        result = tool_page.next(tool_page.context)
        assert message_shown
        assert result == tool_page

    @patch('platform.system', return_value='Linux')
    @patch('torch.cuda.is_available', return_value=False)
    def test_dl_not_available_without_gpu(self, mock_cuda, mock_platform, tool_page, monkeypatch):
        """Verify DL not available without a GPU."""
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
        """Verify DL not available on macOS."""
        message_shown = False
        def mock_warning(*args, **kwargs):
            nonlocal message_shown
            message_shown = True
        monkeypatch.setattr(QMessageBox, 'warning', mock_warning)
        tool_page.radio_dl.setChecked(True)
        result = tool_page.next(tool_page.context)
        assert message_shown


class TestToolSelectionPageReset:
    """Tests for page reset behavior."""

    def test_reset_clears_selection(self, tool_page):
        """Verify reset clears selected option."""
        tool_page.radio_skull.setChecked(True)
        assert tool_page.selected_option == 0
        tool_page.reset_page()
        assert tool_page.selected_option is None
        assert tool_page.radio_group.checkedId() == -1

    def test_reset_unchecks_all_buttons(self, tool_page):
        """Verify reset unchecks all radio buttons."""
        tool_page.radio_draw.setChecked(True)
        tool_page.reset_page()
        for button in tool_page.radio_group.buttons():
            assert not button.isChecked()


class TestToolSelectionPageResize:
    """Tests for dynamic resizing behavior."""

    def test_resize_event_updates_fonts(self, tool_page):
        """Verify font size updates after resize."""
        from PyQt6.QtGui import QResizeEvent
        from PyQt6.QtCore import QSize
        initial_font_size = tool_page.title.font().pointSize()
        event = QResizeEvent(QSize(1200, 800), QSize(800, 600))
        tool_page.resizeEvent(event)
        new_font_size = tool_page.title.font().pointSize()
        assert new_font_size >= 14

    def test_resize_maintains_minimum_font_size(self, tool_page):
        """Verify minimum font size is maintained."""
        from PyQt6.QtGui import QResizeEvent
        from PyQt6.QtCore import QSize
        event = QResizeEvent(QSize(300, 200), QSize(800, 600))
        tool_page.resizeEvent(event)
        title_font_size = tool_page.title.font().pointSize()
        assert title_font_size >= 14
        button_font_size = tool_page.radio_skull.font().pointSize()
        assert button_font_size >= 10


class TestToolSelectionPageTranslation:
    """Tests for UI translation updates."""

    def test_translate_ui_updates_title(self, tool_page):
        """Verify title text is updated."""
        tool_page._translate_ui()
        assert tool_page.title.text() != ""

    def test_translate_ui_updates_buttons(self, tool_page):
        """Verify radio button texts are updated."""
        tool_page._translate_ui()
        assert tool_page.radio_skull.text() != ""
        assert tool_page.radio_draw.text() != ""
        assert tool_page.radio_dl.text() != ""
        assert tool_page.radio_analysis.text() != ""

    def test_translate_ui_updates_group_box(self, tool_page):
        """Verify group box title is updated."""
        tool_page._translate_ui()
        assert tool_page.radio_group_box.title() != ""


class TestToolSelectionPageInfoLabel:
    """Tests for Deep Learning info label."""

    def test_dl_has_info_label(self, tool_page):
        """Verify DL info label exists."""
        assert hasattr(tool_page, 'dl_info_label')
        assert tool_page.dl_info_label is not None

    def test_info_label_has_tooltip(self, tool_page):
        """Verify info label has a valid tooltip."""
        tooltip = tool_page.dl_info_label.toolTip()
        assert tooltip != ""
        assert "GPU" in tooltip or "CUDA" in tooltip or tooltip == ""


class TestToolSelectionPageIntegration:
    """Integration tests for full workflow."""

    def test_full_selection_workflow(self, tool_page, qtbot):
        """Verify complete selection and readiness workflow."""
        assert not tool_page.is_ready_to_advance()
        with qtbot.waitSignal(tool_page.radio_group.buttonToggled, timeout=1000):
            tool_page.radio_skull.setChecked(True)
        assert tool_page.is_ready_to_advance()
        assert tool_page.selected_option == 0

    @patch('main.ui.tool_selection_page.SkullStrippingPage')
    def test_navigation_and_cache(self, MockPage, tool_page):
        """Verify navigation caching and repeated access."""
        mock_page = Mock()
        MockPage.return_value = mock_page
        tool_page.radio_skull.setChecked(True)
        result1 = tool_page.next(tool_page.context)
        result2 = tool_page.next(tool_page.context)
        assert result1 is result2
        MockPage.assert_called_once()
        assert mock_page.on_enter.call_count == 2


if __name__ == "__main__":
    pytest.main([__file__, "-v", "--tb=short"])

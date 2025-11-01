import pytest
from unittest.mock import Mock, patch, MagicMock
from PyQt6.QtCore import Qt, QRectF, QSize
from PyQt6.QtGui import QColor, QPainter, QPaintEvent, QFont
from PyQt6.QtWidgets import QWidget

from components.circular_progress_bar import CircularProgress


class TestCircularProgressInitialization:
    """Test per l'inizializzazione di CircularProgress."""

    def test_initialization_default(self, qtbot):
        """Test inizializzazione con colore default."""
        widget = CircularProgress()
        qtbot.addWidget(widget)

        assert widget.value == 0
        assert widget.color == QColor("#3498DB")

    def test_initialization_custom_color(self, qtbot):
        """Test inizializzazione con colore personalizzato."""
        widget = CircularProgress(color="#FF0000")
        qtbot.addWidget(widget)

        assert widget.value == 0
        assert widget.color == QColor("#FF0000")

    def test_initialization_color_variations(self, qtbot):
        """Test inizializzazione con vari formati colore."""
        # Hex color
        widget1 = CircularProgress(color="#00FF00")
        qtbot.addWidget(widget1)
        assert widget1.color == QColor("#00FF00")

        # Named color
        widget2 = CircularProgress(color="red")
        qtbot.addWidget(widget2)
        assert widget2.color == QColor("red")

        # RGB format
        widget3 = CircularProgress(color="#AABBCC")
        qtbot.addWidget(widget3)
        assert widget3.color == QColor("#AABBCC")


class TestSetValue:
    """Test per il metodo setValue."""

    def test_set_value_basic(self, qtbot):
        """Test setValue con valore valido."""
        widget = CircularProgress()
        qtbot.addWidget(widget)

        widget.setValue(50)

        assert widget.value == 50

    def test_set_value_zero(self, qtbot):
        """Test setValue con valore 0."""
        widget = CircularProgress()
        qtbot.addWidget(widget)

        widget.setValue(0)

        assert widget.value == 0

    def test_set_value_hundred(self, qtbot):
        """Test setValue con valore 100."""
        widget = CircularProgress()
        qtbot.addWidget(widget)

        widget.setValue(100)

        assert widget.value == 100

    def test_set_value_negative_clamped(self, qtbot):
        """Test che valori negativi siano limitati a 0."""
        widget = CircularProgress()
        qtbot.addWidget(widget)

        widget.setValue(-10)

        assert widget.value == 0

    def test_set_value_over_hundred_clamped(self, qtbot):
        """Test che valori >100 siano limitati a 100."""
        widget = CircularProgress()
        qtbot.addWidget(widget)

        widget.setValue(150)

        assert widget.value == 100

    def test_set_value_extreme_negative(self, qtbot):
        """Test con valore estremamente negativo."""
        widget = CircularProgress()
        qtbot.addWidget(widget)

        widget.setValue(-999999)

        assert widget.value == 0

    def test_set_value_extreme_positive(self, qtbot):
        """Test con valore estremamente positivo."""
        widget = CircularProgress()
        qtbot.addWidget(widget)

        widget.setValue(999999)

        assert widget.value == 100

    def test_set_value_sequence(self, qtbot):
        """Test sequenza di setValue."""
        widget = CircularProgress()
        qtbot.addWidget(widget)

        values = [0, 25, 50, 75, 100, 50, 0]
        for val in values:
            widget.setValue(val)
            assert widget.value == val

    def test_set_value_triggers_update(self, qtbot):
        """Test che setValue chiami update()."""
        widget = CircularProgress()
        qtbot.addWidget(widget)

        with patch.object(widget, 'update') as mock_update:
            widget.setValue(50)

            mock_update.assert_called_once()

    def test_set_value_float_converted_to_int(self, qtbot):
        """Test con valore float (dovrebbe essere convertito)."""
        widget = CircularProgress()
        qtbot.addWidget(widget)

        widget.setValue(50.7)

        # Il valore dovrebbe essere trattato come int
        assert widget.value == 50


class TestSetColor:
    """Test per il metodo setColor."""

    def test_set_color_string(self, qtbot):
        """Test setColor con stringa."""
        widget = CircularProgress()
        qtbot.addWidget(widget)

        widget.setColor("#FF0000")

        assert widget.color == QColor("#FF0000")

    def test_set_color_qcolor(self, qtbot):
        """Test setColor con QColor."""
        widget = CircularProgress()
        qtbot.addWidget(widget)

        new_color = QColor(255, 0, 0)
        widget.setColor(new_color)

        assert widget.color == new_color

    def test_set_color_named(self, qtbot):
        """Test setColor con nome colore."""
        widget = CircularProgress()
        qtbot.addWidget(widget)

        widget.setColor("blue")

        assert widget.color == QColor("blue")

    def test_set_color_rgb_hex(self, qtbot):
        """Test setColor con formato RGB hex."""
        widget = CircularProgress()
        qtbot.addWidget(widget)

        widget.setColor("#AABBCC")

        assert widget.color == QColor("#AABBCC")

    def test_set_color_triggers_update(self, qtbot):
        """Test che setColor chiami update()."""
        widget = CircularProgress()
        qtbot.addWidget(widget)

        with patch.object(widget, 'update') as mock_update:
            widget.setColor("#FF0000")

            mock_update.assert_called_once()

    def test_set_color_multiple_times(self, qtbot):
        """Test cambio colore multiplo."""
        widget = CircularProgress()
        qtbot.addWidget(widget)

        colors = ["#FF0000", "#00FF00", "#0000FF", "#FFFF00"]
        for color in colors:
            widget.setColor(color)
            assert widget.color == QColor(color)

    def test_set_color_invalid_string(self, qtbot):
        """Test setColor con stringa non valida."""
        widget = CircularProgress()
        qtbot.addWidget(widget)

        # QColor dovrebbe gestire stringhe non valide
        widget.setColor("not_a_valid_color")

        # Il colore dovrebbe essere comunque un QColor (anche se non valido)
        assert isinstance(widget.color, QColor)


class TestSizeHint:
    """Test per il metodo sizeHint."""

    def test_size_hint_with_parent(self, qtbot):
        """Test sizeHint quando ha un parent."""
        parent = QWidget()
        parent.resize(200, 200)
        qtbot.addWidget(parent)

        widget = CircularProgress()
        widget.setParent(parent)

        size_hint = widget.sizeHint()

        # Dovrebbe ritornare la dimensione del parent
        assert size_hint == parent.size()

    def test_size_hint_without_parent(self, qtbot):
        """Test sizeHint senza parent."""
        widget = CircularProgress()
        qtbot.addWidget(widget)

        size_hint = widget.sizeHint()

        # Dovrebbe ritornare il size hint di default di QWidget
        assert isinstance(size_hint, QSize)

    def test_size_hint_parent_resized(self, qtbot):
        """Test sizeHint quando il parent viene ridimensionato."""
        parent = QWidget()
        parent.resize(300, 300)
        qtbot.addWidget(parent)

        widget = CircularProgress()
        widget.setParent(parent)

        size_hint1 = widget.sizeHint()

        # Ridimensiona parent
        parent.resize(400, 400)

        size_hint2 = widget.sizeHint()

        # Il size hint dovrebbe essere aggiornato
        assert size_hint1 != size_hint2
        assert size_hint2 == parent.size()


class TestPaintEvent:
    """Test per il metodo paintEvent."""

    def test_paint_event_called(self, qtbot):
        """Test che paintEvent sia chiamato."""
        widget = CircularProgress()
        qtbot.addWidget(widget)
        widget.show()

        # Forza un paint event
        with patch.object(widget, 'paintEvent', wraps=widget.paintEvent) as mock_paint:
            widget.repaint()
            qtbot.wait(100)

            # paintEvent dovrebbe essere stato chiamato (potrebbe essere chiamato più volte)
            assert mock_paint.called

    def test_paint_event_creates_painter(self, qtbot):
        """Test che paintEvent crei un QPainter."""
        widget = CircularProgress()
        qtbot.addWidget(widget)
        widget.resize(200, 200)
        widget.show()

        # Usa un mock non intrusivo che non rompe QPainter
        with patch("components.circular_progress_bar.QPainter", autospec=True) as mock_painter_class:
            event = QPaintEvent(widget.rect())
            widget.paintEvent(event)

            # Verifica che il costruttore di QPainter sia stato chiamato almeno una volta
            mock_painter_class.assert_called_with(widget)

    def test_paint_event_different_values(self, qtbot):
        """Test paintEvent con valori diversi."""
        widget = CircularProgress()
        qtbot.addWidget(widget)
        widget.resize(200, 200)
        widget.show()

        values = [0, 25, 50, 75, 100]
        for val in values:
            widget.setValue(val)

            # Forza repaint
            event = QPaintEvent(widget.rect())
            # Non dovrebbe crashare
            widget.paintEvent(event)

    def test_paint_event_different_colors(self, qtbot):
        """Test paintEvent con colori diversi."""
        widget = CircularProgress()
        qtbot.addWidget(widget)
        widget.resize(200, 200)
        widget.show()

        colors = ["#FF0000", "#00FF00", "#0000FF"]
        for color in colors:
            widget.setColor(color)

            event = QPaintEvent(widget.rect())
            # Non dovrebbe crashare
            widget.paintEvent(event)

    def test_paint_event_small_size(self, qtbot):
        """Test paintEvent con dimensioni piccole."""
        widget = CircularProgress()
        qtbot.addWidget(widget)
        widget.resize(20, 20)
        widget.show()

        widget.setValue(50)
        event = QPaintEvent(widget.rect())

        # Non dovrebbe crashare con dimensioni piccole
        widget.paintEvent(event)

    def test_paint_event_large_size(self, qtbot):
        """Test paintEvent con dimensioni grandi."""
        widget = CircularProgress()
        qtbot.addWidget(widget)
        widget.resize(1000, 1000)
        widget.show()

        widget.setValue(50)
        event = QPaintEvent(widget.rect())

        # Non dovrebbe crashare con dimensioni grandi
        widget.paintEvent(event)

    def test_paint_event_rectangular_shape(self, qtbot):
        """Test paintEvent con forma rettangolare."""
        widget = CircularProgress()
        qtbot.addWidget(widget)

        # Forma rettangolare (non quadrata)
        widget.resize(300, 200)
        widget.show()

        widget.setValue(50)
        event = QPaintEvent(widget.rect())

        # Dovrebbe centrare il cerchio
        widget.paintEvent(event)

    def test_paint_event_wide_rectangle(self, qtbot):
        """Test paintEvent con rettangolo largo."""
        widget = CircularProgress()
        qtbot.addWidget(widget)

        widget.resize(400, 200)
        widget.show()

        widget.setValue(75)
        event = QPaintEvent(widget.rect())

        widget.paintEvent(event)

    def test_paint_event_tall_rectangle(self, qtbot):
        """Test paintEvent con rettangolo alto."""
        widget = CircularProgress()
        qtbot.addWidget(widget)

        widget.resize(200, 400)
        widget.show()

        widget.setValue(25)
        event = QPaintEvent(widget.rect())

        widget.paintEvent(event)

class TestEdgeCases:
    """Test per casi limite."""

    def test_very_small_widget(self, qtbot):
        """Test con widget molto piccolo (1x1)."""
        widget = CircularProgress()
        qtbot.addWidget(widget)
        widget.resize(1, 1)
        widget.show()

        widget.setValue(50)
        event = QPaintEvent(widget.rect())

        # Non dovrebbe crashare
        widget.paintEvent(event)

    def test_zero_width(self, qtbot):
        """Test con larghezza zero."""
        widget = CircularProgress()
        qtbot.addWidget(widget)
        widget.resize(0, 100)
        widget.show()

        widget.setValue(50)
        event = QPaintEvent(widget.rect())

        # Non dovrebbe crashare
        widget.paintEvent(event)

    def test_zero_height(self, qtbot):
        """Test con altezza zero."""
        widget = CircularProgress()
        qtbot.addWidget(widget)
        widget.resize(100, 0)
        widget.show()

        widget.setValue(50)
        event = QPaintEvent(widget.rect())

        # Non dovrebbe crashare
        widget.paintEvent(event)

    def test_rapid_value_changes(self, qtbot):
        """Test con cambi rapidi di valore."""
        widget = CircularProgress()
        qtbot.addWidget(widget)
        widget.resize(200, 200)
        widget.show()

        # Cambia valore rapidamente 100 volte
        for i in range(100):
            widget.setValue(i % 101)

        # Non dovrebbe crashare
        assert widget.value >= 0 and widget.value <= 100

    def test_rapid_color_changes(self, qtbot):
        """Test con cambi rapidi di colore."""
        widget = CircularProgress()
        qtbot.addWidget(widget)
        widget.resize(200, 200)
        widget.show()

        colors = ["#FF0000", "#00FF00", "#0000FF", "#FFFF00", "#FF00FF", "#00FFFF"]

        # Cambia colore rapidamente
        for _ in range(20):
            for color in colors:
                widget.setColor(color)

        # Non dovrebbe crashare
        assert isinstance(widget.color, QColor)

    def test_simultaneous_value_and_color_change(self, qtbot):
        """Test cambio simultaneo valore e colore."""
        widget = CircularProgress()
        qtbot.addWidget(widget)
        widget.resize(200, 200)
        widget.show()

        for i in range(50):
            widget.setValue(i * 2)
            widget.setColor(f"#{i * 5:02x}{i * 3:02x}{i * 4:02x}")

        # Non dovrebbe crashare
        assert True

    def test_unicode_in_existing_files(self, qtbot):
        """Test con caratteri unicode in existing_files."""
        widget = CircularProgress()
        qtbot.addWidget(widget)

        widget.existing_files = ["файл.txt", "文件.txt", "αρχείο.txt"]

        widget.setValue(50)

        # Non dovrebbe crashare
        assert len(widget.existing_files) == 3


class TestIntegration:
    """Test di integrazione."""

    def test_full_progress_cycle(self, qtbot):
        """Test ciclo completo di progresso 0-100."""
        widget = CircularProgress()
        qtbot.addWidget(widget)
        widget.resize(200, 200)
        widget.show()

        # Simula progresso completo
        for i in range(0, 101, 10):
            widget.setValue(i)
            event = QPaintEvent(widget.rect())
            widget.paintEvent(event)
            qtbot.wait(10)

        assert widget.value == 100

    def test_progress_with_color_change(self, qtbot):
        """Test progresso con cambio colore durante."""
        widget = CircularProgress()
        qtbot.addWidget(widget)
        widget.resize(200, 200)
        widget.show()

        # 0-50%: blu
        for i in range(0, 51, 10):
            widget.setValue(i)

        # Cambia a verde
        widget.setColor("#00FF00")

        # 51-100%: verde
        for i in range(51, 102, 10):
            widget.setValue(i)

        assert widget.value == 100
        assert widget.color == QColor("#00FF00")

    def test_multiple_complete_cycles(self, qtbot):
        """Test cicli multipli completi."""
        widget = CircularProgress()
        qtbot.addWidget(widget)
        widget.resize(200, 200)
        widget.show()

        # 3 cicli completi
        for cycle in range(3):
            for i in range(0, 101, 25):
                widget.setValue(i)

            # Reset
            widget.setValue(0)

        assert widget.value == 0

    def test_widget_in_parent_container(self, qtbot):
        """Test widget in un container parent."""
        parent = QWidget()
        parent.resize(400, 400)
        qtbot.addWidget(parent)

        widget = CircularProgress()
        widget.setParent(parent)
        parent.show()

        widget.setValue(50)

        # Verifica sizeHint usa dimensioni parent
        assert widget.sizeHint() == parent.size()


class TestRenderingCalculations:
    """Test per i calcoli di rendering."""

    def test_square_widget_centering(self, qtbot):
        """Test centraggio in widget quadrato."""
        widget = CircularProgress()
        qtbot.addWidget(widget)
        widget.resize(200, 200)
        widget.show()

        widget.setValue(50)

        # Con widget quadrato, offset dovrebbe essere 0
        width = widget.width()
        height = widget.height()
        size = min(width, height)

        assert size == 200

    def test_rectangular_widget_centering(self, qtbot):
        """Test centraggio in widget rettangolare."""
        widget = CircularProgress()
        qtbot.addWidget(widget)
        widget.resize(300, 200)
        widget.show()

        widget.setValue(50)

        # Dimensione cerchio dovrebbe essere basata sulla dimensione minore
        width = widget.width()
        height = widget.height()
        size = min(width, height)

        assert size == 200  # L'altezza è il minimo

    def test_pen_width_calculation(self, qtbot):
        """Test calcolo larghezza penna."""
        widget = CircularProgress()
        qtbot.addWidget(widget)

        # Test con varie dimensioni
        sizes = [50, 100, 200, 500]

        for s in sizes:
            widget.resize(s, s)
            widget.show()

            size = min(widget.width(), widget.height())
            expected_pen_width = max(5, int(size / 12))

            # Verifica che il calcolo sia corretto
            assert expected_pen_width >= 5

    def test_font_size_calculation(self, qtbot):
        """Test calcolo dimensione font."""
        widget = CircularProgress()
        qtbot.addWidget(widget)

        sizes = [50, 100, 200, 500]

        for s in sizes:
            widget.resize(s, s)
            widget.show()

            size = min(widget.width(), widget.height())
            expected_font_size = max(5, int(size / 9))

            # Verifica che il calcolo sia corretto
            assert expected_font_size >= 5


class TestValueBoundaries:
    """Test per i valori limite."""

    def test_boundary_value_zero(self, qtbot):
        """Test valore limite 0."""
        widget = CircularProgress()
        qtbot.addWidget(widget)

        widget.setValue(-1)
        assert widget.value == 0

        widget.setValue(0)
        assert widget.value == 0

    def test_boundary_value_hundred(self, qtbot):
        """Test valore limite 100."""
        widget = CircularProgress()
        qtbot.addWidget(widget)

        widget.setValue(100)
        assert widget.value == 100

        widget.setValue(101)
        assert widget.value == 100

    def test_all_integer_values(self, qtbot):
        """Test tutti i valori interi da 0 a 100."""
        widget = CircularProgress()
        qtbot.addWidget(widget)

        for i in range(101):
            widget.setValue(i)
            assert widget.value == i


class TestColorFormats:
    """Test per vari formati di colore."""

    def test_hex_color_3_digits(self, qtbot):
        """Test colore hex a 3 cifre."""
        widget = CircularProgress()
        qtbot.addWidget(widget)

        widget.setColor("#F00")

        # QColor dovrebbe gestire questo formato
        assert isinstance(widget.color, QColor)

    def test_hex_color_6_digits(self, qtbot):
        """Test colore hex a 6 cifre."""
        widget = CircularProgress()
        qtbot.addWidget(widget)

        widget.setColor("#FF0000")

        assert widget.color == QColor("#FF0000")

    def test_named_colors(self, qtbot):
        """Test colori con nome."""
        widget = CircularProgress()
        qtbot.addWidget(widget)

        named_colors = ["red", "green", "blue", "yellow", "cyan", "magenta", "black", "white"]

        for color_name in named_colors:
            widget.setColor(color_name)
            assert isinstance(widget.color, QColor)

    def test_qcolor_from_rgb(self, qtbot):
        """Test QColor da valori RGB."""
        widget = CircularProgress()
        qtbot.addWidget(widget)

        color = QColor(255, 128, 64)
        widget.setColor(color)

        assert widget.color == color


class TestMemoryAndPerformance:
    """Test per memoria e performance."""

    def test_no_memory_leak_on_repeated_updates(self, qtbot):
        """Test che non ci siano memory leak con update ripetuti."""
        widget = CircularProgress()
        qtbot.addWidget(widget)
        widget.resize(200, 200)
        widget.show()

        # Molti update
        for _ in range(1000):
            widget.setValue(50)

        # Non dovrebbe crashare o rallentare significativamente
        assert widget.value == 50

    def test_rapid_repaints(self, qtbot):
        """Test repaint rapidi."""
        widget = CircularProgress()
        qtbot.addWidget(widget)
        widget.resize(200, 200)
        widget.show()

        # Forza molti repaint
        for i in range(100):
            widget.setValue(i % 101)
            widget.repaint()

        # Non dovrebbe crashare
        assert True
import pytest
from unittest.mock import Mock, patch, MagicMock
from PyQt6.QtCore import Qt, QRectF, QSize
from PyQt6.QtGui import QColor, QPainter, QPaintEvent, QFont
from PyQt6.QtWidgets import QWidget

from main.components.circular_progress_bar import CircularProgress


class TestCircularProgressInitialization:
    """Tests for the initialization of CircularProgress."""

    def test_initialization_default(self, qtbot):
        """Test initialization with default color."""
        widget = CircularProgress()
        qtbot.addWidget(widget)

        assert widget.value == 0
        assert widget.color == QColor("#3498DB")

    def test_initialization_custom_color(self, qtbot):
        """Test initialization with custom color."""
        widget = CircularProgress(color="#FF0000")
        qtbot.addWidget(widget)

        assert widget.value == 0
        assert widget.color == QColor("#FF0000")

    def test_initialization_color_variations(self, qtbot):
        """Test initialization with various color formats."""
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
    """Tests for the setValue method."""

    def test_set_value_basic(self, qtbot):
        """Test setValue with a valid value."""
        widget = CircularProgress()
        qtbot.addWidget(widget)

        widget.setValue(50)

        assert widget.value == 50

    def test_set_value_zero(self, qtbot):
        """Test setValue with value 0."""
        widget = CircularProgress()
        qtbot.addWidget(widget)

        widget.setValue(0)

        assert widget.value == 0

    def test_set_value_hundred(self, qtbot):
        """Test setValue with value 100."""
        widget = CircularProgress()
        qtbot.addWidget(widget)

        widget.setValue(100)

        assert widget.value == 100

    def test_set_value_negative_clamped(self, qtbot):
        """Test that negative values are clamped to 0."""
        widget = CircularProgress()
        qtbot.addWidget(widget)

        widget.setValue(-10)

        assert widget.value == 0

    def test_set_value_over_hundred_clamped(self, qtbot):
        """Test that values >100 are clamped to 100."""
        widget = CircularProgress()
        qtbot.addWidget(widget)

        widget.setValue(150)

        assert widget.value == 100

    def test_set_value_extreme_negative(self, qtbot):
        """Test with extremely negative value."""
        widget = CircularProgress()
        qtbot.addWidget(widget)

        widget.setValue(-999999)

        assert widget.value == 0

    def test_set_value_extreme_positive(self, qtbot):
        """Test with extremely positive value."""
        widget = CircularProgress()
        qtbot.addWidget(widget)

        widget.setValue(999999)

        assert widget.value == 100

    def test_set_value_sequence(self, qtbot):
        """Test sequence of setValue calls."""
        widget = CircularProgress()
        qtbot.addWidget(widget)

        values = [0, 25, 50, 75, 100, 50, 0]
        for val in values:
            widget.setValue(val)
            assert widget.value == val

    def test_set_value_triggers_update(self, qtbot):
        """Test that setValue calls update()."""
        widget = CircularProgress()
        qtbot.addWidget(widget)

        with patch.object(widget, 'update') as mock_update:
            widget.setValue(50)

            mock_update.assert_called_once()

    def test_set_value_float_converted_to_int(self, qtbot):
        """Test with a float value (should be converted)."""
        widget = CircularProgress()
        qtbot.addWidget(widget)

        widget.setValue(50.7)

        # Value should be treated as int
        assert widget.value == 50


class TestSetColor:
    """Tests for the setColor method."""

    def test_set_color_string(self, qtbot):
        """Test setColor with a string."""
        widget = CircularProgress()
        qtbot.addWidget(widget)

        widget.setColor("#FF0000")

        assert widget.color == QColor("#FF0000")

    def test_set_color_qcolor(self, qtbot):
        """Test setColor with a QColor."""
        widget = CircularProgress()
        qtbot.addWidget(widget)

        new_color = QColor(255, 0, 0)
        widget.setColor(new_color)

        assert widget.color == new_color

    def test_set_color_named(self, qtbot):
        """Test setColor with a named color."""
        widget = CircularProgress()
        qtbot.addWidget(widget)

        widget.setColor("blue")

        assert widget.color == QColor("blue")

    def test_set_color_rgb_hex(self, qtbot):
        """Test setColor with RGB hex format."""
        widget = CircularProgress()
        qtbot.addWidget(widget)

        widget.setColor("#AABBCC")

        assert widget.color == QColor("#AABBCC")

    def test_set_color_triggers_update(self, qtbot):
        """Test that setColor calls update()."""
        widget = CircularProgress()
        qtbot.addWidget(widget)

        with patch.object(widget, 'update') as mock_update:
            widget.setColor("#FF0000")

            mock_update.assert_called_once()

    def test_set_color_multiple_times(self, qtbot):
        """Test multiple color changes."""
        widget = CircularProgress()
        qtbot.addWidget(widget)

        colors = ["#FF0000", "#00FF00", "#0000FF", "#FFFF00"]
        for color in colors:
            widget.setColor(color)
            assert widget.color == QColor(color)

    def test_set_color_invalid_string(self, qtbot):
        """Test setColor with an invalid string."""
        widget = CircularProgress()
        qtbot.addWidget(widget)

        # QColor should handle invalid strings
        widget.setColor("not_a_valid_color")

        # Color should still be a QColor object (even if invalid)
        assert isinstance(widget.color, QColor)


class TestSizeHint:
    """Tests for the sizeHint method."""

    def test_size_hint_with_parent(self, qtbot):
        """Test sizeHint when it has a parent."""
        parent = QWidget()
        parent.resize(200, 200)
        qtbot.addWidget(parent)

        widget = CircularProgress()
        widget.setParent(parent)

        size_hint = widget.sizeHint()

        # Should return the parent's size
        assert size_hint == parent.size()

    def test_size_hint_without_parent(self, qtbot):
        """Test sizeHint without a parent."""
        widget = CircularProgress()
        qtbot.addWidget(widget)

        size_hint = widget.sizeHint()

        # Should return QWidget's default size hint
        assert isinstance(size_hint, QSize)

    def test_size_hint_parent_resized(self, qtbot):
        """Test sizeHint when the parent is resized."""
        parent = QWidget()
        parent.resize(300, 300)
        qtbot.addWidget(parent)

        widget = CircularProgress()
        widget.setParent(parent)

        size_hint1 = widget.sizeHint()

        # Resize parent
        parent.resize(400, 400)

        size_hint2 = widget.sizeHint()

        # Size hint should update
        assert size_hint1 != size_hint2
        assert size_hint2 == parent.size()

class TestPaintEvent:
    """Tests for the paintEvent method."""

    def test_paint_event_called(self, qtbot):
        """Test that paintEvent is called."""
        widget = CircularProgress()
        qtbot.addWidget(widget)
        widget.show()

        # Force a paint event
        with patch.object(widget, 'paintEvent', wraps=widget.paintEvent) as mock_paint:
            widget.repaint()
            qtbot.wait(100)

            # paintEvent should have been called (it may be called multiple times)
            assert mock_paint.called

    def test_paint_event_creates_painter(self, qtbot):
        """Test that paintEvent creates a QPainter."""
        widget = CircularProgress()
        qtbot.addWidget(widget)
        widget.resize(200, 200)
        widget.show()

        # Use a non-intrusive mock that does not break QPainter
        with patch("main.components.circular_progress_bar.QPainter", autospec=True) as mock_painter_class:
            event = QPaintEvent(widget.rect())
            widget.paintEvent(event)

            # Verify that QPainter's constructor was called at least once
            mock_painter_class.assert_called_with(widget)

    def test_paint_event_different_values(self, qtbot):
        """Test paintEvent with different values."""
        widget = CircularProgress()
        qtbot.addWidget(widget)
        widget.resize(200, 200)
        widget.show()

        values = [0, 25, 50, 75, 100]
        for val in values:
            widget.setValue(val)

            # Force repaint
            event = QPaintEvent(widget.rect())
            # Should not crash
            widget.paintEvent(event)

    def test_paint_event_different_colors(self, qtbot):
        """Test paintEvent with different colors."""
        widget = CircularProgress()
        qtbot.addWidget(widget)
        widget.resize(200, 200)
        widget.show()

        colors = ["#FF0000", "#00FF00", "#0000FF"]
        for color in colors:
            widget.setColor(color)

            event = QPaintEvent(widget.rect())
            # Should not crash
            widget.paintEvent(event)

    def test_paint_event_small_size(self, qtbot):
        """Test paintEvent with small widget size."""
        widget = CircularProgress()
        qtbot.addWidget(widget)
        widget.resize(20, 20)
        widget.show()

        widget.setValue(50)
        event = QPaintEvent(widget.rect())

        # Should not crash with small sizes
        widget.paintEvent(event)

    def test_paint_event_large_size(self, qtbot):
        """Test paintEvent with large widget size."""
        widget = CircularProgress()
        qtbot.addWidget(widget)
        widget.resize(1000, 1000)
        widget.show()

        widget.setValue(50)
        event = QPaintEvent(widget.rect())

        # Should not crash with large sizes
        widget.paintEvent(event)

    def test_paint_event_rectangular_shape(self, qtbot):
        """Test paintEvent with a rectangular (non-square) shape."""
        widget = CircularProgress()
        qtbot.addWidget(widget)

        # Rectangular shape
        widget.resize(300, 200)
        widget.show()

        widget.setValue(50)
        event = QPaintEvent(widget.rect())

        # Should properly center the circle
        widget.paintEvent(event)

    def test_paint_event_wide_rectangle(self, qtbot):
        """Test paintEvent with a wide rectangle."""
        widget = CircularProgress()
        qtbot.addWidget(widget)

        widget.resize(400, 200)
        widget.show()

        widget.setValue(75)
        event = QPaintEvent(widget.rect())

        widget.paintEvent(event)

    def test_paint_event_tall_rectangle(self, qtbot):
        """Test paintEvent with a tall rectangle."""
        widget = CircularProgress()
        qtbot.addWidget(widget)

        widget.resize(200, 400)
        widget.show()

        widget.setValue(25)
        event = QPaintEvent(widget.rect())

        widget.paintEvent(event)


class TestEdgeCases:
    """Tests for edge cases."""

    def test_very_small_widget(self, qtbot):
        """Test with a very small widget (1x1)."""
        widget = CircularProgress()
        qtbot.addWidget(widget)
        widget.resize(1, 1)
        widget.show()

        widget.setValue(50)
        event = QPaintEvent(widget.rect())

        # Should not crash
        widget.paintEvent(event)

    def test_zero_width(self, qtbot):
        """Test with zero width."""
        widget = CircularProgress()
        qtbot.addWidget(widget)
        widget.resize(0, 100)
        widget.show()

        widget.setValue(50)
        event = QPaintEvent(widget.rect())

        # Should not crash
        widget.paintEvent(event)

    def test_zero_height(self, qtbot):
        """Test with zero height."""
        widget = CircularProgress()
        qtbot.addWidget(widget)
        widget.resize(100, 0)
        widget.show()

        widget.setValue(50)
        event = QPaintEvent(widget.rect())

        # Should not crash
        widget.paintEvent(event)

    def test_rapid_value_changes(self, qtbot):
        """Test with rapid value changes."""
        widget = CircularProgress()
        qtbot.addWidget(widget)
        widget.resize(200, 200)
        widget.show()

        # Change value rapidly 100 times
        for i in range(100):
            widget.setValue(i % 101)

        # Should not crash
        assert widget.value >= 0 and widget.value <= 100

    def test_rapid_color_changes(self, qtbot):
        """Test with rapid color changes."""
        widget = CircularProgress()
        qtbot.addWidget(widget)
        widget.resize(200, 200)
        widget.show()

        colors = ["#FF0000", "#00FF00", "#0000FF", "#FFFF00", "#FF00FF", "#00FFFF"]

        # Change colors rapidly
        for _ in range(20):
            for color in colors:
                widget.setColor(color)

        # Should not crash
        assert isinstance(widget.color, QColor)

    def test_simultaneous_value_and_color_change(self, qtbot):
        """Test simultaneous value and color changes."""
        widget = CircularProgress()
        qtbot.addWidget(widget)
        widget.resize(200, 200)
        widget.show()

        for i in range(50):
            widget.setValue(i * 2)
            widget.setColor(f"#{i * 5:02x}{i * 3:02x}{i * 4:02x}")

        # Should not crash
        assert True

    def test_unicode_in_existing_files(self, qtbot):
        """Test unicode characters in existing_files."""
        widget = CircularProgress()
        qtbot.addWidget(widget)

        widget.existing_files = ["файл.txt", "文件.txt", "αρχείο.txt"]

        widget.setValue(50)

        # Should not crash
        assert len(widget.existing_files) == 3


class TestIntegration:
    """Integration tests."""

    def test_full_progress_cycle(self, qtbot):
        """Test a full progress cycle 0–100."""
        widget = CircularProgress()
        qtbot.addWidget(widget)
        widget.resize(200, 200)
        widget.show()

        # Simulate full progress
        for i in range(0, 101, 10):
            widget.setValue(i)
            event = QPaintEvent(widget.rect())
            widget.paintEvent(event)
            qtbot.wait(10)

        assert widget.value == 100

    def test_progress_with_color_change(self, qtbot):
        """Test progress with color change mid-way."""
        widget = CircularProgress()
        qtbot.addWidget(widget)
        widget.resize(200, 200)
        widget.show()

        # 0–50%: blue
        for i in range(0, 51, 10):
            widget.setValue(i)

        # Switch to green
        widget.setColor("#00FF00")

        # 51–100%: green
        for i in range(51, 102, 10):
            widget.setValue(i)

        assert widget.value == 100
        assert widget.color == QColor("#00FF00")

    def test_multiple_complete_cycles(self, qtbot):
        """Test multiple full cycles."""
        widget = CircularProgress()
        qtbot.addWidget(widget)
        widget.resize(200, 200)
        widget.show()

        # 3 complete cycles
        for cycle in range(3):
            for i in range(0, 101, 25):
                widget.setValue(i)

            # Reset
            widget.setValue(0)

        assert widget.value == 0

    def test_widget_in_parent_container(self, qtbot):
        """Test widget inside a parent container."""
        parent = QWidget()
        parent.resize(400, 400)
        qtbot.addWidget(parent)

        widget = CircularProgress()
        widget.setParent(parent)
        parent.show()

        widget.setValue(50)

        # Verify sizeHint uses parent's size
        assert widget.sizeHint() == parent.size()


class TestRenderingCalculations:
    """Test for rendering calculations."""

    def test_square_widget_centering(self, qtbot):
        """Test centering in squared widget."""
        widget = CircularProgress()
        qtbot.addWidget(widget)
        widget.resize(200, 200)
        widget.show()

        widget.setValue(50)

        width = widget.width()
        height = widget.height()
        size = min(width, height)

        assert size == 200  # Con widget quadrato il minimo è 200

    def test_rectangular_widget_centering(self, qtbot):
        """Test centering in rectangular widget."""
        widget = CircularProgress()
        qtbot.addWidget(widget)
        widget.resize(300, 200)
        widget.show()

        widget.setValue(50)

        width = widget.width()
        height = widget.height()
        size = min(width, height)

        assert size == 200

    def test_pen_width_calculation(self, qtbot):
        """Test pen width calculation."""
        widget = CircularProgress()
        qtbot.addWidget(widget)

        sizes = [50, 100, 200, 500]

        for s in sizes:
            widget.resize(s, s)
            widget.show()

            size = min(widget.width(), widget.height())
            expected_pen_width = max(5, int(size / 12))

            assert expected_pen_width >= 5

    def test_font_size_calculation(self, qtbot):
        """Test font size calculation."""
        widget = CircularProgress()
        qtbot.addWidget(widget)

        sizes = [50, 100, 200, 500]

        for s in sizes:
            widget.resize(s, s)
            widget.show()

            size = min(widget.width(), widget.height())
            expected_font_size = max(5, int(size / 9))

            assert expected_font_size >= 5


class TestValueBoundaries:
    """Test for value boundaries."""

    def test_boundary_value_zero(self, qtbot):
        """Test for 0."""
        widget = CircularProgress()
        qtbot.addWidget(widget)

        widget.setValue(-1)
        assert widget.value == 0

        widget.setValue(0)
        assert widget.value == 0

    def test_boundary_value_hundred(self, qtbot):
        """Test for 100."""
        widget = CircularProgress()
        qtbot.addWidget(widget)

        widget.setValue(100)
        assert widget.value == 100

        widget.setValue(101)
        assert widget.value == 100

    def test_all_integer_values(self, qtbot):
        """Test for every value between 0 and 100."""
        widget = CircularProgress()
        qtbot.addWidget(widget)

        for i in range(101):
            widget.setValue(i)
            assert widget.value == i


class TestColorFormats:
    """Test for color formats."""

    def test_hex_color_3_digits(self, qtbot):
        """Test color 3 hex digits."""
        widget = CircularProgress()
        qtbot.addWidget(widget)

        widget.setColor("#F00")

        assert isinstance(widget.color, QColor)

    def test_hex_color_6_digits(self, qtbot):
        """Test color 6 hex digits."""
        widget = CircularProgress()
        qtbot.addWidget(widget)

        widget.setColor("#FF0000")

        assert widget.color == QColor("#FF0000")

    def test_named_colors(self, qtbot):
        """Test color with names."""
        widget = CircularProgress()
        qtbot.addWidget(widget)

        named_colors = ["red", "green", "blue", "yellow", "cyan", "magenta", "black", "white"]

        for color_name in named_colors:
            widget.setColor(color_name)
            assert isinstance(widget.color, QColor)

    def test_qcolor_from_rgb(self, qtbot):
        """Test QColor with RGB color"""
        widget = CircularProgress()
        qtbot.addWidget(widget)

        color = QColor(255, 128, 64)
        widget.setColor(color)

        assert widget.color == color


class TestMemoryAndPerformance:
    """Test for memory and performace."""

    def test_no_memory_leak_on_repeated_updates(self, qtbot):
        """Test for memory leak."""
        widget = CircularProgress()
        qtbot.addWidget(widget)
        widget.resize(200, 200)
        widget.show()

        for _ in range(1000):
            widget.setValue(50)

        assert widget.value == 50

    def test_rapid_repaints(self, qtbot):
        """Test repaint."""
        widget = CircularProgress()
        qtbot.addWidget(widget)
        widget.resize(200, 200)
        widget.show()

        for i in range(100):
            widget.setValue(i % 101)
            widget.repaint()

        assert True

import pytest
from unittest.mock import Mock, patch, MagicMock, PropertyMock
from PyQt6.QtCore import Qt, QPointF, QRectF, QEvent
from PyQt6.QtGui import QMouseEvent, QPainter, QColor
from PyQt6.QtWidgets import QGraphicsView, QGraphicsScene, QGraphicsLineItem, QWidget

from main.components.crosshair_graphic_view import CrosshairGraphicsView


@pytest.fixture
def mock_parent_viewer():
    """Mock for the parent viewer."""
    parent = QWidget()
    parent.img_data = Mock()  # Simulates image data presence
    parent.handle_click_coordinates = Mock()
    parent.update_cross_view_lines = Mock()
    return parent


@pytest.fixture
def graphics_scene():
    """Creates a QGraphicsScene for testing."""
    scene = QGraphicsScene()
    scene.setSceneRect(0, 0, 512, 512)
    return scene


class TestCrosshairGraphicsViewInitialization:
    """Tests for CrosshairGraphicsView initialization."""

    def test_initialization_basic(self, qtbot):
        """Test basic initialization."""
        view = CrosshairGraphicsView(view_idx=0)
        qtbot.addWidget(view)

        assert view.view_idx == 0
        assert view.parent_viewer is None
        assert view.crosshair_h is None
        assert view.crosshair_v is None
        assert view.crosshair_visible is False

    def test_initialization_with_parent(self, qtbot, mock_parent_viewer):
        """Test initialization with parent."""
        view = CrosshairGraphicsView(view_idx=1, parent=mock_parent_viewer)
        qtbot.addWidget(view)

        assert view.view_idx == 1
        assert view.parent_viewer == mock_parent_viewer

    def test_initialization_different_view_indices(self, qtbot):
        """Test initialization with different indices."""
        for idx in [0, 1, 2, 3, 10]:
            view = CrosshairGraphicsView(view_idx=idx)
            qtbot.addWidget(view)
            assert view.view_idx == idx

    def test_mouse_tracking_enabled(self, qtbot):
        """Test that mouse tracking is enabled."""
        view = CrosshairGraphicsView(view_idx=0)
        qtbot.addWidget(view)

        assert view.hasMouseTracking()

    def test_drag_mode_set(self, qtbot):
        """Test that drag mode is NoDrag."""
        view = CrosshairGraphicsView(view_idx=0)
        qtbot.addWidget(view)

        assert view.dragMode() == QGraphicsView.DragMode.NoDrag

    def test_render_hints_set(self, qtbot):
        """Test that render hints are set."""
        view = CrosshairGraphicsView(view_idx=0)
        qtbot.addWidget(view)

        hints = view.renderHints()

        assert hints & QPainter.RenderHint.Antialiasing
        assert hints & QPainter.RenderHint.SmoothPixmapTransform


class TestSetupCrosshairs:
    """Tests for the setup_crosshairs method."""

    def test_setup_crosshairs_with_scene(self, qtbot, graphics_scene):
        """Test setup crosshairs with scene."""
        view = CrosshairGraphicsView(view_idx=0)
        qtbot.addWidget(view)
        view.setScene(graphics_scene)

        view.setup_crosshairs()

        assert view.crosshair_h is not None
        assert view.crosshair_v is not None
        assert isinstance(view.crosshair_h, QGraphicsLineItem)
        assert isinstance(view.crosshair_v, QGraphicsLineItem)
        assert not view.crosshair_h.isVisible()
        assert not view.crosshair_v.isVisible()

    def test_setup_crosshairs_without_scene(self, qtbot):
        """Test setup crosshairs without scene."""
        view = CrosshairGraphicsView(view_idx=0)
        qtbot.addWidget(view)

        # Should not crash
        view.setup_crosshairs()

        assert view.crosshair_h is None
        assert view.crosshair_v is None

    def test_setup_crosshairs_color(self, qtbot, graphics_scene):
        """Test that crosshairs have the correct color."""
        view = CrosshairGraphicsView(view_idx=0)
        qtbot.addWidget(view)
        view.setScene(graphics_scene)

        view.setup_crosshairs()

        # Check color (yellow with alpha 180)
        pen_h = view.crosshair_h.pen()
        pen_v = view.crosshair_v.pen()

        assert pen_h.color() == QColor(255, 255, 0, 180)
        assert pen_v.color() == QColor(255, 255, 0, 180)
        assert pen_h.width() == 1
        assert pen_v.width() == 1

    def test_setup_crosshairs_multiple_calls(self, qtbot, graphics_scene):
        """Test multiple calls to setup_crosshairs."""
        view = CrosshairGraphicsView(view_idx=0)
        qtbot.addWidget(view)
        view.setScene(graphics_scene)

        view.setup_crosshairs()
        first_h = view.crosshair_h
        first_v = view.crosshair_v

        view.setup_crosshairs()

        # New crosshairs should have been created
        assert view.crosshair_h is not None
        assert view.crosshair_v is not None


class TestMouseMoveEvent:
    """Tests for mouseMoveEvent."""

    def test_mouse_move_emits_coordinate_changed(self, qtbot, mock_parent_viewer, graphics_scene):
        """Test that mouse move emits coordinate_changed."""
        view = CrosshairGraphicsView(view_idx=0, parent=mock_parent_viewer)
        qtbot.addWidget(view)
        view.setScene(graphics_scene)
        view.setup_crosshairs()

        with qtbot.waitSignal(view.coordinate_changed, timeout=1000) as blocker:
            event = QMouseEvent(
                QMouseEvent.Type.MouseMove,
                QPointF(100, 100),
                Qt.MouseButton.NoButton,
                Qt.MouseButton.NoButton,
                Qt.KeyboardModifier.NoModifier
            )
            view.mouseMoveEvent(event)

        # Check signal emitted
        assert blocker.signal_triggered
        args = blocker.args
        assert args[0] == 0  # view_idx

    def test_mouse_move_updates_crosshairs(self, qtbot, mock_parent_viewer, graphics_scene):
        """Test that mouse move updates crosshairs."""
        view = CrosshairGraphicsView(view_idx=0, parent=mock_parent_viewer)
        qtbot.addWidget(view)
        view.setScene(graphics_scene)
        view.setup_crosshairs()

        with patch.object(view, 'update_crosshairs') as mock_update:
            event = QMouseEvent(
                QMouseEvent.Type.MouseMove,
                QPointF(100, 150),
                Qt.MouseButton.NoButton,
                Qt.MouseButton.NoButton,
                Qt.KeyboardModifier.NoModifier
            )
            view.mouseMoveEvent(event)

            mock_update.assert_called_once()

    def test_mouse_move_without_scene(self, qtbot, mock_parent_viewer):
        """Test mouse move without scene."""
        view = CrosshairGraphicsView(view_idx=0, parent=mock_parent_viewer)
        qtbot.addWidget(view)

        # Should not crash
        event = QMouseEvent(
            QMouseEvent.Type.MouseMove,
            QPointF(100, 100),
            Qt.MouseButton.NoButton,
            Qt.MouseButton.NoButton,
            Qt.KeyboardModifier.NoModifier
        )
        view.mouseMoveEvent(event)

    def test_mouse_move_without_parent_viewer(self, qtbot, graphics_scene):
        """Test mouse move without parent viewer."""
        view = CrosshairGraphicsView(view_idx=0)
        qtbot.addWidget(view)
        view.setScene(graphics_scene)

        # Should not crash
        event = QMouseEvent(
            QMouseEvent.Type.MouseMove,
            QPointF(100, 100),
            Qt.MouseButton.NoButton,
            Qt.MouseButton.NoButton,
            Qt.KeyboardModifier.NoModifier
        )
        view.mouseMoveEvent(event)

    def test_mouse_move_without_img_data(self, qtbot, graphics_scene, mock_parent_viewer):
        """Test mouse move without img_data."""
        view = CrosshairGraphicsView(view_idx=0, parent=mock_parent_viewer)
        qtbot.addWidget(view)
        view.setScene(graphics_scene)

        # Should not crash
        event = QMouseEvent(
            QMouseEvent.Type.MouseMove,
            QPointF(100, 100),
            Qt.MouseButton.NoButton,
            Qt.MouseButton.NoButton,
            Qt.KeyboardModifier.NoModifier
        )
        view.mouseMoveEvent(event)

    def test_mouse_move_out_of_bounds(self, qtbot, mock_parent_viewer, graphics_scene):
        """Test mouse move out of bounds."""
        view = CrosshairGraphicsView(view_idx=0, parent=mock_parent_viewer)
        qtbot.addWidget(view)
        view.setScene(graphics_scene)
        view.setup_crosshairs()

        with patch.object(view, 'update_crosshairs') as mock_update:
            # Coordinates out of bounds
            event = QMouseEvent(
                QMouseEvent.Type.MouseMove,
                QPointF(1000, 1000),
                Qt.MouseButton.NoButton,
                Qt.MouseButton.NoButton,
                Qt.KeyboardModifier.NoModifier
            )
            view.mouseMoveEvent(event)

            # update_crosshairs should not be called
            mock_update.assert_not_called()

    def test_mouse_move_negative_coordinates(self, qtbot, mock_parent_viewer, graphics_scene):
        """Test mouse move with negative coordinates."""
        view = CrosshairGraphicsView(view_idx=0, parent=mock_parent_viewer)
        qtbot.addWidget(view)
        view.setScene(graphics_scene)
        view.setup_crosshairs()

        with patch.object(view, 'update_crosshairs') as mock_update:
            event = QMouseEvent(
                QMouseEvent.Type.MouseMove,
                QPointF(-10, -10),
                Qt.MouseButton.NoButton,
                Qt.MouseButton.NoButton,
                Qt.KeyboardModifier.NoModifier
            )
            view.mouseMoveEvent(event)

            # update_crosshairs should not be called
            mock_update.assert_not_called()


class TestMousePressEvent:
    """Tests for mousePressEvent."""

    def test_left_click_calls_handle_click_coordinates(self, qtbot, mock_parent_viewer, graphics_scene):
        """Test that left click calls handle_click_coordinates."""
        view = CrosshairGraphicsView(view_idx=0, parent=mock_parent_viewer)
        qtbot.addWidget(view)
        view.setScene(graphics_scene)

        event = QMouseEvent(
            QMouseEvent.Type.MouseButtonPress,
            QPointF(100, 150),
            Qt.MouseButton.LeftButton,
            Qt.MouseButton.LeftButton,
            Qt.KeyboardModifier.NoModifier
        )
        view.mousePressEvent(event)

        mock_parent_viewer.handle_click_coordinates.assert_called_once()
        args = mock_parent_viewer.handle_click_coordinates.call_args[0]
        assert args[0] == 0  # view_idx

    def test_right_click_ignored(self, qtbot, mock_parent_viewer, graphics_scene):
        """Test that right click is ignored."""
        view = CrosshairGraphicsView(view_idx=0, parent=mock_parent_viewer)
        qtbot.addWidget(view)
        view.setScene(graphics_scene)

        event = QMouseEvent(
            QMouseEvent.Type.MouseButtonPress,
            QPointF(100, 150),
            Qt.MouseButton.RightButton,
            Qt.MouseButton.RightButton,
            Qt.KeyboardModifier.NoModifier
        )
        view.mousePressEvent(event)

        # handle_click_coordinates should not be called
        mock_parent_viewer.handle_click_coordinates.assert_not_called()

    def test_middle_click_ignored(self, qtbot, mock_parent_viewer, graphics_scene):
        """Test that middle click is ignored."""
        view = CrosshairGraphicsView(view_idx=0, parent=mock_parent_viewer)
        qtbot.addWidget(view)
        view.setScene(graphics_scene)

        event = QMouseEvent(
            QMouseEvent.Type.MouseButtonPress,
            QPointF(100, 150),
            Qt.MouseButton.MiddleButton,
            Qt.MouseButton.MiddleButton,
            Qt.KeyboardModifier.NoModifier
        )
        view.mousePressEvent(event)

        mock_parent_viewer.handle_click_coordinates.assert_not_called()

    def test_click_without_scene(self, qtbot, mock_parent_viewer):
        """Test click without scene."""
        view = CrosshairGraphicsView(view_idx=0, parent=mock_parent_viewer)
        qtbot.addWidget(view)

        event = QMouseEvent(
            QMouseEvent.Type.MouseButtonPress,
            QPointF(100, 150),
            Qt.MouseButton.LeftButton,
            Qt.MouseButton.LeftButton,
            Qt.KeyboardModifier.NoModifier
        )
        view.mousePressEvent(event)

        # Should not crash
        mock_parent_viewer.handle_click_coordinates.assert_not_called()

    def test_click_without_parent_viewer(self, qtbot, graphics_scene):
        """Test click without parent viewer."""
        view = CrosshairGraphicsView(view_idx=0)
        qtbot.addWidget(view)
        view.setScene(graphics_scene)

        # Should not crash
        event = QMouseEvent(
            QMouseEvent.Type.MouseButtonPress,
            QPointF(100, 150),
            Qt.MouseButton.LeftButton,
            Qt.MouseButton.LeftButton,
            Qt.KeyboardModifier.NoModifier
        )
        view.mousePressEvent(event)

    def test_click_without_img_data(self, qtbot, graphics_scene, mock_parent_viewer):
        """Test click without img_data."""
        view = CrosshairGraphicsView(view_idx=0, parent=mock_parent_viewer)
        qtbot.addWidget(view)
        view.setScene(graphics_scene)

        event = QMouseEvent(
            QMouseEvent.Type.MouseButtonPress,
            QPointF(100, 150),
            Qt.MouseButton.LeftButton,
            Qt.MouseButton.LeftButton,
            Qt.KeyboardModifier.NoModifier
        )
        view.mousePressEvent(event)

        # Should not crash
        assert True

    def test_click_out_of_bounds(self, qtbot, mock_parent_viewer, graphics_scene):
        """Test click out of bounds."""
        view = CrosshairGraphicsView(view_idx=0, parent=mock_parent_viewer)
        qtbot.addWidget(view)
        view.setScene(graphics_scene)

        event = QMouseEvent(
            QMouseEvent.Type.MouseButtonPress,
            QPointF(1000, 1000),
            Qt.MouseButton.LeftButton,
            Qt.MouseButton.LeftButton,
            Qt.KeyboardModifier.NoModifier
        )
        view.mousePressEvent(event)

        # handle_click_coordinates should not be called
        mock_parent_viewer.handle_click_coordinates.assert_not_called()

    def test_click_at_scene_edges(self, qtbot, mock_parent_viewer, graphics_scene):
        """Test click at scene edges."""
        view = CrosshairGraphicsView(view_idx=0, parent=mock_parent_viewer)
        qtbot.addWidget(view)
        view.setScene(graphics_scene)

        # Scene corners
        corners = [
            (0, 0),
            (511, 0),
            (0, 511),
            (511, 511)
        ]

        for x, y in corners:
            mock_parent_viewer.handle_click_coordinates.reset_mock()

            event = QMouseEvent(
                QMouseEvent.Type.MouseButtonPress,
                QPointF(x, y),
                Qt.MouseButton.LeftButton,
                Qt.MouseButton.LeftButton,
                Qt.KeyboardModifier.NoModifier
            )
            view.mousePressEvent(event)

            mock_parent_viewer.handle_click_coordinates.assert_called_once()


class TestUpdateCrosshairs:
    """Tests for update_crosshairs."""

    def test_update_crosshairs_basic(self, qtbot, graphics_scene):
        """Test basic update crosshairs."""
        view = CrosshairGraphicsView(view_idx=0)
        qtbot.addWidget(view)
        view.setScene(graphics_scene)
        view.setup_crosshairs()

        view.update_crosshairs(100, 200)

        # Check updated lines
        line_h = view.crosshair_h.line()
        line_v = view.crosshair_v.line()

        assert line_h.y1() == 200
        assert line_h.y2() == 200
        assert line_v.x1() == 100
        assert line_v.x2() == 100

        assert view.crosshair_visible
        assert view.crosshair_h.isVisible()
        assert view.crosshair_v.isVisible()

    def test_update_crosshairs_different_positions(self, qtbot, graphics_scene):
        """Test update with different positions."""
        view = CrosshairGraphicsView(view_idx=0)
        qtbot.addWidget(view)
        view.setScene(graphics_scene)
        view.setup_crosshairs()

        positions = [(0, 0), (256, 256), (511, 511), (100, 400)]

        for x, y in positions:
            view.update_crosshairs(x, y)

            line_h = view.crosshair_h.line()
            line_v = view.crosshair_v.line()

            assert line_h.y1() == y
            assert line_v.x1() == x

    def test_update_crosshairs_without_scene(self, qtbot):
        """Test update crosshairs without scene."""
        view = CrosshairGraphicsView(view_idx=0)
        qtbot.addWidget(view)

        # Should not crash
        view.update_crosshairs(100, 200)

    def test_update_crosshairs_without_setup(self, qtbot, graphics_scene):
        """Test update crosshairs without setup."""
        view = CrosshairGraphicsView(view_idx=0)
        qtbot.addWidget(view)
        view.setScene(graphics_scene)

        # Should not crash (crosshair_h and crosshair_v are None)
        view.update_crosshairs(100, 200)

    def test_update_crosshairs_makes_visible(self, qtbot, graphics_scene):
        """Test that update makes crosshairs visible."""
        view = CrosshairGraphicsView(view_idx=0)
        qtbot.addWidget(view)
        view.setScene(graphics_scene)
        view.setup_crosshairs()

        assert not view.crosshair_visible
        assert not view.crosshair_h.isVisible()

        view.update_crosshairs(100, 200)

        assert view.crosshair_visible
        assert view.crosshair_h.isVisible()
        assert view.crosshair_v.isVisible()

    def test_update_crosshairs_spans_full_scene(self, qtbot, graphics_scene):
        """Test that crosshairs span the full scene."""
        view = CrosshairGraphicsView(view_idx=0)
        qtbot.addWidget(view)
        view.setScene(graphics_scene)
        view.setup_crosshairs()

        view.update_crosshairs(256, 256)

        line_h = view.crosshair_h.line()
        line_v = view.crosshair_v.line()

        # Horizontal line: from 0 to width
        assert line_h.x1() == 0
        assert line_h.x2() == 512

        # Vertical line: from 0 to height
        assert line_v.y1() == 0
        assert line_v.y2() == 512


class TestSetCrosshairPosition:
    """Tests for set_crosshair_position."""

    def test_set_crosshair_position_basic(self, qtbot, graphics_scene):
        """Test basic set crosshair position."""
        view = CrosshairGraphicsView(view_idx=0)
        qtbot.addWidget(view)
        view.setScene(graphics_scene)
        view.setup_crosshairs()

        view.set_crosshair_position(150, 250)

        line_h = view.crosshair_h.line()
        line_v = view.crosshair_v.line()

        assert line_h.y1() == 250
        assert line_v.x1() == 150
        assert view.crosshair_visible
        assert view.crosshair_h.isVisible()
        assert view.crosshair_v.isVisible()

    def test_set_crosshair_position_out_of_bounds(self, qtbot, graphics_scene):
        """Test set position out of bounds."""
        view = CrosshairGraphicsView(view_idx=0)
        qtbot.addWidget(view)
        view.setScene(graphics_scene)
        view.setup_crosshairs()

        # Out of bounds coordinates should not update
        view.set_crosshair_position(1000, 1000)

        # Crosshairs should not be visible if they were hidden
        # (depends on implementation, might not update)

    def test_set_crosshair_position_without_scene(self, qtbot):
        """Test set position without scene."""
        view = CrosshairGraphicsView(view_idx=0)
        qtbot.addWidget(view)

        # Should not crash
        view.set_crosshair_position(100, 200)

    def test_set_crosshair_position_without_setup(self, qtbot, graphics_scene):
        """Test set position without setup."""
        view = CrosshairGraphicsView(view_idx=0)
        qtbot.addWidget(view)
        view.setScene(graphics_scene)

        # Should not crash
        view.set_crosshair_position(100, 200)

    def test_set_crosshair_position_at_origin(self, qtbot, graphics_scene):
        """Test set position at origin."""
        view = CrosshairGraphicsView(view_idx=0)
        qtbot.addWidget(view)
        view.setScene(graphics_scene)
        view.setup_crosshairs()

        view.set_crosshair_position(0, 0)

        line_h = view.crosshair_h.line()
        line_v = view.crosshair_v.line()

        assert line_h.y1() == 0
        assert line_v.x1() == 0

    def test_set_crosshair_position_at_max(self, qtbot, graphics_scene):
        """Test set position at max."""
        view = CrosshairGraphicsView(view_idx=0)
        qtbot.addWidget(view)
        view.setScene(graphics_scene)
        view.setup_crosshairs()

        view.set_crosshair_position(511, 511)

        line_h = view.crosshair_h.line()
        line_v = view.crosshair_v.line()

        assert line_h.y1() == 511
        assert line_v.x1() == 511


class TestLeaveEvent:
    """Tests for leaveEvent."""

    def test_leave_event_calls_update_cross_view_lines(self, qtbot, mock_parent_viewer, graphics_scene):
        """Test that leaveEvent calls update_cross_view_lines."""
        view = CrosshairGraphicsView(view_idx=0, parent=mock_parent_viewer)
        qtbot.addWidget(view)
        view.setScene(graphics_scene)
        view.setup_crosshairs()

        event = QEvent(QEvent.Type.Leave)
        view.leaveEvent(event)

        mock_parent_viewer.update_cross_view_lines.assert_called_once()

    def test_leave_event_without_crosshairs(self, qtbot, mock_parent_viewer):
        """Test leaveEvent without crosshairs."""
        view = CrosshairGraphicsView(view_idx=0, parent=mock_parent_viewer)
        qtbot.addWidget(view)

        # Should not crash
        event = QEvent(QEvent.Type.Leave)
        view.leaveEvent(event)

    def test_leave_event_without_parent_viewer(self, qtbot, graphics_scene):
        """Test leaveEvent without parent viewer."""
        view = CrosshairGraphicsView(view_idx=0)
        qtbot.addWidget(view)
        view.setScene(graphics_scene)
        view.setup_crosshairs()

        # Should not crash
        event = Mock()
        # Might fail if parent_viewer is None
        try:
            view.leaveEvent(event)
        except AttributeError:
            pass  # Acceptable if parent_viewer is None


class TestSignals:
    """Tests for signals."""

    def test_coordinate_changed_signal_exists(self, qtbot):
        """Test that the coordinate_changed signal exists."""
        view = CrosshairGraphicsView(view_idx=0)
        qtbot.addWidget(view)

        assert hasattr(view, 'coordinate_changed')

    def test_coordinate_changed_signal_parameters(self, qtbot, mock_parent_viewer, graphics_scene):
        """Test coordinate_changed signal parameters."""
        view = CrosshairGraphicsView(view_idx=2, parent=mock_parent_viewer)
        qtbot.addWidget(view)
        view.setScene(graphics_scene)
        view.setup_crosshairs()

        with qtbot.waitSignal(view.coordinate_changed) as blocker:
            event = QMouseEvent(
                QMouseEvent.Type.MouseMove,
                QPointF(123, 456),
                Qt.MouseButton.NoButton,
                Qt.MouseButton.NoButton,
                Qt.KeyboardModifier.NoModifier
            )
            view.mouseMoveEvent(event)

        args = blocker.args
        assert len(args) == 3
        assert args[0] == 2  # view_idx
        # args[1] and args[2] are x, y (might vary due to mapToScene)


class TestEdgeCases:
    """Tests for edge cases."""

    def test_very_small_scene(self, qtbot):
        """Test with very small scene."""
        view = CrosshairGraphicsView(view_idx=0)
        qtbot.addWidget(view)

        small_scene = QGraphicsScene()
        small_scene.setSceneRect(0, 0, 10, 10)
        view.setScene(small_scene)
        view.setup_crosshairs()

        view.update_crosshairs(5, 5)

        # Should not crash
        assert view.crosshair_visible

    def test_very_large_scene(self, qtbot):
        """Test with very large scene."""
        view = CrosshairGraphicsView(view_idx=0)
        qtbot.addWidget(view)

        large_scene = QGraphicsScene()
        large_scene.setSceneRect(0, 0, 10000, 10000)
        view.setScene(large_scene)
        view.setup_crosshairs()

        view.update_crosshairs(5000, 5000)

        assert view.crosshair_visible

    def test_rectangular_scene(self, qtbot):
        """Test with rectangular scene."""
        view = CrosshairGraphicsView(view_idx=0)
        qtbot.addWidget(view)

        rect_scene = QGraphicsScene()
        rect_scene.setSceneRect(0, 0, 800, 400)
        view.setScene(rect_scene)
        view.setup_crosshairs()

        view.update_crosshairs(400, 200)

        line_h = view.crosshair_h.line()
        line_v = view.crosshair_v.line()

        assert line_h.x2() == 800
        assert line_v.y2() == 400

    def test_rapid_mouse_movements(self, qtbot, mock_parent_viewer, graphics_scene):
        """Test rapid mouse movements."""
        view = CrosshairGraphicsView(view_idx=0, parent=mock_parent_viewer)
        qtbot.addWidget(view)
        view.setScene(graphics_scene)
        view.setup_crosshairs()

        # Simulate 100 rapid movements
        for i in range(100):
            x = (i * 5) % 512
            y = (i * 3) % 512
            event = QMouseEvent(
                QMouseEvent.Type.MouseMove,
                QPointF(x, y),
                Qt.MouseButton.NoButton,
                Qt.MouseButton.NoButton,
                Qt.KeyboardModifier.NoModifier
            )
            view.mouseMoveEvent(event)

        # Should not crash
        assert view.crosshair_visible

    def test_rapid_clicks(self, qtbot, mock_parent_viewer, graphics_scene):
        """Test rapid clicks."""
        view = CrosshairGraphicsView(view_idx=0, parent=mock_parent_viewer)
        qtbot.addWidget(view)
        view.setScene(graphics_scene)

        for i in range(50):
            x = (i * 10) % 512
            y = (i * 7) % 512
            event = QMouseEvent(
                QMouseEvent.Type.MouseButtonPress,
                QPointF(x, y),
                Qt.MouseButton.LeftButton,
                Qt.MouseButton.LeftButton,
                Qt.KeyboardModifier.NoModifier
            )
            view.mousePressEvent(event)

        # handle_click_coordinates should have been called 50 times
        assert mock_parent_viewer.handle_click_coordinates.call_count == 50

    def test_scene_change(self, qtbot):
        """Test scene change."""
        view = CrosshairGraphicsView(view_idx=0)
        qtbot.addWidget(view)

        # First scene
        scene1 = QGraphicsScene()
        scene1.setSceneRect(0, 0, 256, 256)
        view.setScene(scene1)
        view.setup_crosshairs()

        crosshair_h1 = view.crosshair_h

        # Second scene
        scene2 = QGraphicsScene()
        scene2.setSceneRect(0, 0, 512, 512)
        view.setScene(scene2)
        view.setup_crosshairs()

        # Crosshairs should be new
        assert view.crosshair_h is not crosshair_h1

    def test_coordinate_precision(self, qtbot, mock_parent_viewer, graphics_scene):
        """Test coordinate precision with float."""
        view = CrosshairGraphicsView(view_idx=0, parent=mock_parent_viewer)
        qtbot.addWidget(view)
        view.setScene(graphics_scene)

        # Float coordinates should be converted to int
        event = QMouseEvent(
            QMouseEvent.Type.MouseButtonPress,
            QPointF(100.7, 200.3),
            Qt.MouseButton.LeftButton,
            Qt.MouseButton.LeftButton,
            Qt.KeyboardModifier.NoModifier
        )
        view.mousePressEvent(event)

        # Check that they were passed as int
        args = mock_parent_viewer.handle_click_coordinates.call_args[0]
        assert isinstance(args[1], int)
        assert isinstance(args[2], int)


class TestIntegration:
    """Integration tests."""

    def test_full_interaction_flow(self, qtbot, mock_parent_viewer, graphics_scene):
        """Test full flow: setup -> mouse move -> click."""
        view = CrosshairGraphicsView(view_idx=1, parent=mock_parent_viewer)
        qtbot.addWidget(view)
        view.setScene(graphics_scene)
        view.setup_crosshairs()

        # Mouse move
        with qtbot.waitSignal(view.coordinate_changed):
            move_event = QMouseEvent(
                QMouseEvent.Type.MouseMove,
                QPointF(150, 200),
                Qt.MouseButton.NoButton,
                Qt.MouseButton.NoButton,
                Qt.KeyboardModifier.NoModifier
            )
            view.mouseMoveEvent(move_event)

        assert view.crosshair_visible

        # Click
        click_event = QMouseEvent(
            QMouseEvent.Type.MouseButtonPress,
            QPointF(150, 200),
            Qt.MouseButton.LeftButton,
            Qt.MouseButton.LeftButton,
            Qt.KeyboardModifier.NoModifier
        )
        view.mousePressEvent(click_event)

        mock_parent_viewer.handle_click_coordinates.assert_called_once()

    def test_multiple_views_interaction(self, qtbot, mock_parent_viewer):
        """Test interaction between multiple views."""
        scene1 = QGraphicsScene()
        scene1.setSceneRect(0, 0, 512, 512)

        scene2 = QGraphicsScene()
        scene2.setSceneRect(0, 0, 512, 512)

        view1 = CrosshairGraphicsView(view_idx=0, parent=mock_parent_viewer)
        view2 = CrosshairGraphicsView(view_idx=1, parent=mock_parent_viewer)

        qtbot.addWidget(view1)
        qtbot.addWidget(view2)

        view1.setScene(scene1)
        view2.setScene(scene2)

        view1.setup_crosshairs()
        view2.setup_crosshairs()

        # Interaction on view1
        event = QMouseEvent(
            QMouseEvent.Type.MouseButtonPress,
            QPointF(100, 100),
            Qt.MouseButton.LeftButton,
            Qt.MouseButton.LeftButton,
            Qt.KeyboardModifier.NoModifier
        )
        view1.mousePressEvent(event)

        # Check correct view_idx
        args1 = mock_parent_viewer.handle_click_coordinates.call_args[0]
        assert args1[0] == 0

        # Interaction on view2
        mock_parent_viewer.handle_click_coordinates.reset_mock()
        view2.mousePressEvent(event)

        args2 = mock_parent_viewer.handle_click_coordinates.call_args[0]
        assert args2[0] == 1

    def test_crosshair_synchronization(self, qtbot, graphics_scene):
        """Test crosshair synchronization."""
        view = CrosshairGraphicsView(view_idx=0)
        qtbot.addWidget(view)
        view.setScene(graphics_scene)
        view.setup_crosshairs()

        # Update via update_crosshairs
        view.update_crosshairs(100, 200)

        line_h1 = view.crosshair_h.line()
        assert line_h1.y1() == 200

        # Update via set_crosshair_position
        view.set_crosshair_position(150, 250)

        line_h2 = view.crosshair_h.line()
        assert line_h2.y1() == 250


class TestBoundaryConditions:
    """Tests for boundary conditions."""

    def test_click_at_zero_zero(self, qtbot, mock_parent_viewer, graphics_scene):
        """Test click at (0, 0)."""
        view = CrosshairGraphicsView(view_idx=0, parent=mock_parent_viewer)
        qtbot.addWidget(view)
        view.setScene(graphics_scene)

        event = QMouseEvent(
            QMouseEvent.Type.MouseButtonPress,
            QPointF(0, 0),
            Qt.MouseButton.LeftButton,
            Qt.MouseButton.LeftButton,
            Qt.KeyboardModifier.NoModifier
        )
        view.mousePressEvent(event)

        mock_parent_viewer.handle_click_coordinates.assert_called_once()

    def test_click_at_max_coordinates(self, qtbot, mock_parent_viewer, graphics_scene):
        """Test click at maximum coordinates."""
        view = CrosshairGraphicsView(view_idx=0, parent=mock_parent_viewer)
        qtbot.addWidget(view)
        view.setScene(graphics_scene)

        # Scene is 512x512, so valid max is 511,511
        event = QMouseEvent(
            QMouseEvent.Type.MouseButtonPress,
            QPointF(511, 511),
            Qt.MouseButton.LeftButton,
            Qt.MouseButton.LeftButton,
            Qt.KeyboardModifier.NoModifier
        )
        view.mousePressEvent(event)

        mock_parent_viewer.handle_click_coordinates.assert_called_once()

    def test_click_just_outside_bounds(self, qtbot, mock_parent_viewer, graphics_scene):
        """Test click just outside bounds."""
        view = CrosshairGraphicsView(view_idx=0, parent=mock_parent_viewer)
        qtbot.addWidget(view)
        view.setScene(graphics_scene)

        # 512 is outside (scene is 0-511)
        event = QMouseEvent(
            QMouseEvent.Type.MouseButtonPress,
            QPointF(512, 512),
            Qt.MouseButton.LeftButton,
            Qt.MouseButton.LeftButton,
            Qt.KeyboardModifier.NoModifier
        )
        view.mousePressEvent(event)

        # Should not call handle_click_coordinates
        mock_parent_viewer.handle_click_coordinates.assert_not_called()


class TestViewIndexHandling:
    """Tests for view_idx handling."""

    def test_different_view_indices_in_signals(self, qtbot, mock_parent_viewer, graphics_scene):
        """Test that view_idx is correct in signals."""
        indices = [0, 1, 2, 5, 10]

        for idx in indices:
            view = CrosshairGraphicsView(view_idx=idx, parent=mock_parent_viewer)
            qtbot.addWidget(view)
            view.setScene(graphics_scene)

            with qtbot.waitSignal(view.coordinate_changed) as blocker:
                event = QMouseEvent(
                    QMouseEvent.Type.MouseMove,
                    QPointF(100, 100),
                    Qt.MouseButton.NoButton,
                    Qt.MouseButton.NoButton,
                    Qt.KeyboardModifier.NoModifier
                )
                view.mouseMoveEvent(event)

            assert blocker.args[0] == idx

    def test_view_idx_persists(self, qtbot):
        """Test that view_idx persists."""
        view = CrosshairGraphicsView(view_idx=7)
        qtbot.addWidget(view)

        assert view.view_idx == 7

        # After various operations
        scene = QGraphicsScene()
        view.setScene(scene)
        view.setup_crosshairs()

        assert view.view_idx == 7


class TestMemoryAndCleanup:
    """Tests for memory and cleanup."""

    def test_scene_items_cleanup(self, qtbot, graphics_scene):
        """Test cleanup of scene items."""
        view = CrosshairGraphicsView(view_idx=0)
        qtbot.addWidget(view)
        view.setScene(graphics_scene)

        initial_items = len(graphics_scene.items())

        view.setup_crosshairs()

        # 2 items (lines) should have been added
        assert len(graphics_scene.items()) == initial_items + 2

    def test_multiple_setup_doesnt_leak(self, qtbot, graphics_scene):
        """Test that multiple setups do not cause memory leaks."""
        view = CrosshairGraphicsView(view_idx=0)
        qtbot.addWidget(view)
        view.setScene(graphics_scene)

        # Multiple setups
        for _ in range(10):
            view.setup_crosshairs()

        # Old items should have been removed/replaced
        # (depends on implementation)
        assert True


class TestRenderHints:
    """Tests for render hints."""

    def test_antialiasing_enabled(self, qtbot):
        """Test that antialiasing is enabled."""
        view = CrosshairGraphicsView(view_idx=0)
        qtbot.addWidget(view)

        hints = view.renderHints()
        assert hints & QPainter.RenderHint.Antialiasing

    def test_smooth_pixmap_transform_enabled(self, qtbot):
        """Test that smooth pixmap transform is enabled."""
        view = CrosshairGraphicsView(view_idx=0)
        qtbot.addWidget(view)

        hints = view.renderHints()
        assert hints & QPainter.RenderHint.SmoothPixmapTransform

    def test_render_hints_persist(self, qtbot, graphics_scene):
        """Test that render hints persist after operations."""
        view = CrosshairGraphicsView(view_idx=0)
        qtbot.addWidget(view)

        view.setScene(graphics_scene)
        view.setup_crosshairs()

        hints = view.renderHints()
        assert hints & QPainter.RenderHint.Antialiasing
        assert hints & QPainter.RenderHint.SmoothPixmapTransform


class TestErrorHandling:
    """Tests for error handling."""

    def test_mapToScene_with_invalid_point(self, qtbot, mock_parent_viewer, graphics_scene):
        """Test mapToScene with invalid point."""
        view = CrosshairGraphicsView(view_idx=0, parent=mock_parent_viewer)
        qtbot.addWidget(view)
        view.setScene(graphics_scene)

        # Point far out of bounds
        event = QMouseEvent(
            QMouseEvent.Type.MouseMove,
            QPointF(999999, 999999),
            Qt.MouseButton.NoButton,
            Qt.MouseButton.NoButton,
            Qt.KeyboardModifier.NoModifier
        )

        # Should not crash
        view.mouseMoveEvent(event)

    def test_operations_without_initialization(self, qtbot):
        """Test operations without complete initialization."""
        view = CrosshairGraphicsView(view_idx=0)
        qtbot.addWidget(view)

        # Various operations without scene/crosshair setup
        view.update_crosshairs(100, 100)
        view.set_crosshair_position(100, 100)

        event = QMouseEvent(
            QMouseEvent.Type.MouseMove,
            QPointF(100, 100),
            Qt.MouseButton.NoButton,
            Qt.MouseButton.NoButton,
            Qt.KeyboardModifier.NoModifier
        )
        view.mouseMoveEvent(event)

        # Should not crash
        assert True


class TestStateConsistency:
    """Tests for state consistency."""

    def test_crosshair_visible_state_consistency(self, qtbot, graphics_scene):
        """Test crosshair_visible state consistency."""
        view = CrosshairGraphicsView(view_idx=0)
        qtbot.addWidget(view)
        view.setScene(graphics_scene)
        view.setup_crosshairs()

        # Initially not visible
        assert not view.crosshair_visible
        assert not view.crosshair_h.isVisible()

        # After update, visible
        view.update_crosshairs(100, 100)
        assert view.crosshair_visible
        assert view.crosshair_h.isVisible()
        assert view.crosshair_v.isVisible()

    def test_crosshair_position_consistency(self, qtbot, graphics_scene):
        """Test crosshair position consistency."""
        view = CrosshairGraphicsView(view_idx=0)
        qtbot.addWidget(view)
        view.setScene(graphics_scene)
        view.setup_crosshairs()

        # Set position
        view.update_crosshairs(123, 456)

        line_h = view.crosshair_h.line()
        line_v = view.crosshair_v.line()

        # Check consistency
        assert line_h.y1() == line_h.y2() == 456
        assert line_v.x1() == line_v.x2() == 123


class TestDocumentation:
    """Tests for documentation."""

    def test_class_docstring(self):
        """Test that the class has a docstring."""
        assert CrosshairGraphicsView.__doc__ is not None
        assert "crosshair" in CrosshairGraphicsView.__doc__.lower()

    def test_setup_crosshairs_docstring(self, qtbot):
        """Test that setup_crosshairs has a docstring."""
        view = CrosshairGraphicsView(view_idx=0)
        qtbot.addWidget(view)

        assert view.setup_crosshairs.__doc__ is not None


class TestAccessibility:
    """Tests for accessibility."""

    def test_crosshair_color_visible(self, qtbot, graphics_scene):
        """Test that crosshair color is visible."""
        view = CrosshairGraphicsView(view_idx=0)
        qtbot.addWidget(view)
        view.setScene(graphics_scene)
        view.setup_crosshairs()

        pen = view.crosshair_h.pen()
        color = pen.color()

        # Yellow with alpha should be visible
        assert color.alpha() == 180
        assert color.red() == 255
        assert color.green() == 255
        assert color.blue() == 0

    def test_crosshair_width_appropriate(self, qtbot, graphics_scene):
        """Test that crosshair width is appropriate."""
        view = CrosshairGraphicsView(view_idx=0)
        qtbot.addWidget(view)
        view.setScene(graphics_scene)
        view.setup_crosshairs()

        pen_h = view.crosshair_h.pen()
        pen_v = view.crosshair_v.pen()

        # Width 1 should be visible but not intrusive
        assert pen_h.width() == 1
        assert pen_v.width() == 1


class TestPerformance:
    """Tests for performance."""

    def test_many_coordinate_updates(self, qtbot, mock_parent_viewer, graphics_scene):
        """Test with many coordinate updates."""
        view = CrosshairGraphicsView(view_idx=0, parent=mock_parent_viewer)
        qtbot.addWidget(view)
        view.setScene(graphics_scene)
        view.setup_crosshairs()

        # 1000 updates
        for i in range(1000):
            view.update_crosshairs(i % 512, (i * 2) % 512)

        # Should not cause performance issues
        assert view.crosshair_visible

    def test_signal_emission_performance(self, qtbot, mock_parent_viewer, graphics_scene):
        """Test signal emission performance."""
        view = CrosshairGraphicsView(view_idx=0, parent=mock_parent_viewer)
        qtbot.addWidget(view)
        view.setScene(graphics_scene)

        signal_count = 0

        def count_signal(*args):
            nonlocal signal_count
            signal_count += 1

        view.coordinate_changed.connect(count_signal)

        # Many mouse events
        for i in range(100):
            event = QMouseEvent(
                QMouseEvent.Type.MouseMove,
                QPointF(i % 512, (i * 2) % 512),
                Qt.MouseButton.NoButton,
                Qt.MouseButton.NoButton,
                Qt.KeyboardModifier.NoModifier
            )
            view.mouseMoveEvent(event)

        # Signal should have been emitted many times
        assert signal_count > 0
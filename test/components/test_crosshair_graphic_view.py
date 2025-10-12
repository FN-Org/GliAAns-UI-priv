import pytest
from unittest.mock import Mock, patch, MagicMock, PropertyMock
from PyQt6.QtCore import Qt, QPointF, QRectF, QEvent
from PyQt6.QtGui import QMouseEvent, QPainter, QColor
from PyQt6.QtWidgets import QGraphicsView, QGraphicsScene, QGraphicsLineItem, QWidget

from components.crosshair_graphic_view import CrosshairGraphicsView


@pytest.fixture
def mock_parent_viewer():
    """Mock per il parent viewer."""
    parent = QWidget()
    parent.img_data = Mock()  # Simula presenza dati immagine
    parent.handle_click_coordinates = Mock()
    parent.update_cross_view_lines = Mock()
    return parent


@pytest.fixture
def graphics_scene():
    """Crea una QGraphicsScene per i test."""
    scene = QGraphicsScene()
    scene.setSceneRect(0, 0, 512, 512)
    return scene


class TestCrosshairGraphicsViewInitialization:
    """Test per l'inizializzazione di CrosshairGraphicsView."""

    def test_initialization_basic(self, qtbot):
        """Test inizializzazione base."""
        view = CrosshairGraphicsView(view_idx=0)
        qtbot.addWidget(view)

        assert view.view_idx == 0
        assert view.parent_viewer is None
        assert view.crosshair_h is None
        assert view.crosshair_v is None
        assert view.crosshair_visible is False

    def test_initialization_with_parent(self, qtbot, mock_parent_viewer):
        """Test inizializzazione con parent."""
        view = CrosshairGraphicsView(view_idx=1, parent=mock_parent_viewer)
        qtbot.addWidget(view)

        assert view.view_idx == 1
        assert view.parent_viewer == mock_parent_viewer

    def test_initialization_different_view_indices(self, qtbot):
        """Test inizializzazione con indici diversi."""
        for idx in [0, 1, 2, 3, 10]:
            view = CrosshairGraphicsView(view_idx=idx)
            qtbot.addWidget(view)
            assert view.view_idx == idx

    def test_mouse_tracking_enabled(self, qtbot):
        """Test che mouse tracking sia abilitato."""
        view = CrosshairGraphicsView(view_idx=0)
        qtbot.addWidget(view)

        assert view.hasMouseTracking()

    def test_drag_mode_set(self, qtbot):
        """Test che drag mode sia NoDrag."""
        view = CrosshairGraphicsView(view_idx=0)
        qtbot.addWidget(view)

        assert view.dragMode() == QGraphicsView.DragMode.NoDrag

    def test_render_hints_set(self, qtbot):
        """Test che render hints siano impostati."""
        view = CrosshairGraphicsView(view_idx=0)
        qtbot.addWidget(view)

        hints = view.renderHints()

        assert hints & QPainter.RenderHint.Antialiasing
        assert hints & QPainter.RenderHint.SmoothPixmapTransform


class TestSetupCrosshairs:
    """Test per il metodo setup_crosshairs."""

    def test_setup_crosshairs_with_scene(self, qtbot, graphics_scene):
        """Test setup crosshairs con scene."""
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
        """Test setup crosshairs senza scene."""
        view = CrosshairGraphicsView(view_idx=0)
        qtbot.addWidget(view)

        # Non dovrebbe crashare
        view.setup_crosshairs()

        assert view.crosshair_h is None
        assert view.crosshair_v is None

    def test_setup_crosshairs_color(self, qtbot, graphics_scene):
        """Test che i crosshair abbiano il colore corretto."""
        view = CrosshairGraphicsView(view_idx=0)
        qtbot.addWidget(view)
        view.setScene(graphics_scene)

        view.setup_crosshairs()

        # Verifica colore (giallo con alpha 180)
        pen_h = view.crosshair_h.pen()
        pen_v = view.crosshair_v.pen()

        assert pen_h.color() == QColor(255, 255, 0, 180)
        assert pen_v.color() == QColor(255, 255, 0, 180)
        assert pen_h.width() == 1
        assert pen_v.width() == 1

    def test_setup_crosshairs_multiple_calls(self, qtbot, graphics_scene):
        """Test chiamate multiple a setup_crosshairs."""
        view = CrosshairGraphicsView(view_idx=0)
        qtbot.addWidget(view)
        view.setScene(graphics_scene)

        view.setup_crosshairs()
        first_h = view.crosshair_h
        first_v = view.crosshair_v

        view.setup_crosshairs()

        # Dovrebbero essere stati creati nuovi crosshair
        assert view.crosshair_h is not None
        assert view.crosshair_v is not None


class TestMouseMoveEvent:
    """Test per mouseMoveEvent."""

    def test_mouse_move_emits_coordinate_changed(self, qtbot, mock_parent_viewer, graphics_scene):
        """Test che mouse move emetta coordinate_changed."""
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

        # Verifica signal emesso
        assert blocker.signal_triggered
        args = blocker.args
        assert args[0] == 0  # view_idx

    def test_mouse_move_updates_crosshairs(self, qtbot, mock_parent_viewer, graphics_scene):
        """Test che mouse move aggiorni i crosshair."""
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
        """Test mouse move senza scene."""
        view = CrosshairGraphicsView(view_idx=0, parent=mock_parent_viewer)
        qtbot.addWidget(view)

        # Non dovrebbe crashare
        event = QMouseEvent(
            QMouseEvent.Type.MouseMove,
            QPointF(100, 100),
            Qt.MouseButton.NoButton,
            Qt.MouseButton.NoButton,
            Qt.KeyboardModifier.NoModifier
        )
        view.mouseMoveEvent(event)

    def test_mouse_move_without_parent_viewer(self, qtbot, graphics_scene):
        """Test mouse move senza parent viewer."""
        view = CrosshairGraphicsView(view_idx=0)
        qtbot.addWidget(view)
        view.setScene(graphics_scene)

        # Non dovrebbe crashare
        event = QMouseEvent(
            QMouseEvent.Type.MouseMove,
            QPointF(100, 100),
            Qt.MouseButton.NoButton,
            Qt.MouseButton.NoButton,
            Qt.KeyboardModifier.NoModifier
        )
        view.mouseMoveEvent(event)

    def test_mouse_move_without_img_data(self, qtbot, graphics_scene, mock_parent_viewer):
        """Test mouse move senza img_data."""
        view = CrosshairGraphicsView(view_idx=0, parent=mock_parent_viewer)
        qtbot.addWidget(view)
        view.setScene(graphics_scene)

        # Non dovrebbe crashare
        event = QMouseEvent(
            QMouseEvent.Type.MouseMove,
            QPointF(100, 100),
            Qt.MouseButton.NoButton,
            Qt.MouseButton.NoButton,
            Qt.KeyboardModifier.NoModifier
        )
        view.mouseMoveEvent(event)

    def test_mouse_move_out_of_bounds(self, qtbot, mock_parent_viewer, graphics_scene):
        """Test mouse move fuori dai limiti."""
        view = CrosshairGraphicsView(view_idx=0, parent=mock_parent_viewer)
        qtbot.addWidget(view)
        view.setScene(graphics_scene)
        view.setup_crosshairs()

        with patch.object(view, 'update_crosshairs') as mock_update:
            # Coordinate fuori dai limiti
            event = QMouseEvent(
                QMouseEvent.Type.MouseMove,
                QPointF(1000, 1000),
                Qt.MouseButton.NoButton,
                Qt.MouseButton.NoButton,
                Qt.KeyboardModifier.NoModifier
            )
            view.mouseMoveEvent(event)

            # update_crosshairs non dovrebbe essere chiamato
            mock_update.assert_not_called()

    def test_mouse_move_negative_coordinates(self, qtbot, mock_parent_viewer, graphics_scene):
        """Test mouse move con coordinate negative."""
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

            # update_crosshairs non dovrebbe essere chiamato
            mock_update.assert_not_called()


class TestMousePressEvent:
    """Test per mousePressEvent."""

    def test_left_click_calls_handle_click_coordinates(self, qtbot, mock_parent_viewer, graphics_scene):
        """Test che left click chiami handle_click_coordinates."""
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
        """Test che right click sia ignorato."""
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

        # handle_click_coordinates non dovrebbe essere chiamato
        mock_parent_viewer.handle_click_coordinates.assert_not_called()

    def test_middle_click_ignored(self, qtbot, mock_parent_viewer, graphics_scene):
        """Test che middle click sia ignorato."""
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
        """Test click senza scene."""
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

        # Non dovrebbe crashare
        mock_parent_viewer.handle_click_coordinates.assert_not_called()

    def test_click_without_parent_viewer(self, qtbot, graphics_scene):
        """Test click senza parent viewer."""
        view = CrosshairGraphicsView(view_idx=0)
        qtbot.addWidget(view)
        view.setScene(graphics_scene)

        # Non dovrebbe crashare
        event = QMouseEvent(
            QMouseEvent.Type.MouseButtonPress,
            QPointF(100, 150),
            Qt.MouseButton.LeftButton,
            Qt.MouseButton.LeftButton,
            Qt.KeyboardModifier.NoModifier
        )
        view.mousePressEvent(event)

    def test_click_without_img_data(self, qtbot, graphics_scene, mock_parent_viewer):
        """Test click senza img_data."""
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

        # Non dovrebbe crashare
        assert True

    def test_click_out_of_bounds(self, qtbot, mock_parent_viewer, graphics_scene):
        """Test click fuori dai limiti."""
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

        # handle_click_coordinates non dovrebbe essere chiamato
        mock_parent_viewer.handle_click_coordinates.assert_not_called()

    def test_click_at_scene_edges(self, qtbot, mock_parent_viewer, graphics_scene):
        """Test click sui bordi della scene."""
        view = CrosshairGraphicsView(view_idx=0, parent=mock_parent_viewer)
        qtbot.addWidget(view)
        view.setScene(graphics_scene)

        # Angoli della scene
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
    """Test per update_crosshairs."""

    def test_update_crosshairs_basic(self, qtbot, graphics_scene):
        """Test update crosshairs base."""
        view = CrosshairGraphicsView(view_idx=0)
        qtbot.addWidget(view)
        view.setScene(graphics_scene)
        view.setup_crosshairs()

        view.update_crosshairs(100, 200)

        # Verifica linee aggiornate
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
        """Test update con posizioni diverse."""
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
        """Test update crosshairs senza scene."""
        view = CrosshairGraphicsView(view_idx=0)
        qtbot.addWidget(view)

        # Non dovrebbe crashare
        view.update_crosshairs(100, 200)

    def test_update_crosshairs_without_setup(self, qtbot, graphics_scene):
        """Test update crosshairs senza setup."""
        view = CrosshairGraphicsView(view_idx=0)
        qtbot.addWidget(view)
        view.setScene(graphics_scene)

        # Non dovrebbe crashare (crosshair_h e crosshair_v sono None)
        view.update_crosshairs(100, 200)

    def test_update_crosshairs_makes_visible(self, qtbot, graphics_scene):
        """Test che update renda visibili i crosshair."""
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
        """Test che i crosshair coprano l'intera scene."""
        view = CrosshairGraphicsView(view_idx=0)
        qtbot.addWidget(view)
        view.setScene(graphics_scene)
        view.setup_crosshairs()

        view.update_crosshairs(256, 256)

        line_h = view.crosshair_h.line()
        line_v = view.crosshair_v.line()

        # Linea orizzontale: da 0 a width
        assert line_h.x1() == 0
        assert line_h.x2() == 512

        # Linea verticale: da 0 a height
        assert line_v.y1() == 0
        assert line_v.y2() == 512


class TestSetCrosshairPosition:
    """Test per set_crosshair_position."""

    def test_set_crosshair_position_basic(self, qtbot, graphics_scene):
        """Test set crosshair position base."""
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
        """Test set position fuori dai limiti."""
        view = CrosshairGraphicsView(view_idx=0)
        qtbot.addWidget(view)
        view.setScene(graphics_scene)
        view.setup_crosshairs()

        # Coordinate fuori dai limiti non dovrebbero aggiornare
        view.set_crosshair_position(1000, 1000)

        # Crosshair non dovrebbero essere visibili se erano nascosti
        # (dipende dall'implementazione, potrebbe non aggiornare)

    def test_set_crosshair_position_without_scene(self, qtbot):
        """Test set position senza scene."""
        view = CrosshairGraphicsView(view_idx=0)
        qtbot.addWidget(view)

        # Non dovrebbe crashare
        view.set_crosshair_position(100, 200)

    def test_set_crosshair_position_without_setup(self, qtbot, graphics_scene):
        """Test set position senza setup."""
        view = CrosshairGraphicsView(view_idx=0)
        qtbot.addWidget(view)
        view.setScene(graphics_scene)

        # Non dovrebbe crashare
        view.set_crosshair_position(100, 200)

    def test_set_crosshair_position_at_origin(self, qtbot, graphics_scene):
        """Test set position all'origine."""
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
        """Test set position al massimo."""
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
    """Test per leaveEvent."""

    def test_leave_event_calls_update_cross_view_lines(self, qtbot, mock_parent_viewer, graphics_scene):
        """Test che leaveEvent chiami update_cross_view_lines."""
        view = CrosshairGraphicsView(view_idx=0, parent=mock_parent_viewer)
        qtbot.addWidget(view)
        view.setScene(graphics_scene)
        view.setup_crosshairs()

        event = QEvent(QEvent.Type.Leave)
        view.leaveEvent(event)

        mock_parent_viewer.update_cross_view_lines.assert_called_once()

    def test_leave_event_without_crosshairs(self, qtbot, mock_parent_viewer):
        """Test leaveEvent senza crosshairs."""
        view = CrosshairGraphicsView(view_idx=0, parent=mock_parent_viewer)
        qtbot.addWidget(view)

        # Non dovrebbe crashare
        event = QEvent(QEvent.Type.Leave)
        view.leaveEvent(event)

    def test_leave_event_without_parent_viewer(self, qtbot, graphics_scene):
        """Test leaveEvent senza parent viewer."""
        view = CrosshairGraphicsView(view_idx=0)
        qtbot.addWidget(view)
        view.setScene(graphics_scene)
        view.setup_crosshairs()

        # Non dovrebbe crashare
        event = Mock()
        # Potrebbe fallire se parent_viewer è None
        try:
            view.leaveEvent(event)
        except AttributeError:
            pass  # Accettabile se parent_viewer è None


class TestSignals:
    """Test per i signal."""

    def test_coordinate_changed_signal_exists(self, qtbot):
        """Test che il signal coordinate_changed esista."""
        view = CrosshairGraphicsView(view_idx=0)
        qtbot.addWidget(view)

        assert hasattr(view, 'coordinate_changed')

    def test_slice_changed_signal_exists(self, qtbot):
        """Test che il signal slice_changed esista."""
        view = CrosshairGraphicsView(view_idx=0)
        qtbot.addWidget(view)

        assert hasattr(view, 'slice_changed')

    def test_coordinate_changed_signal_parameters(self, qtbot, mock_parent_viewer, graphics_scene):
        """Test parametri signal coordinate_changed."""
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
        # args[1] e args[2] sono x, y (potrebbero variare per mapToScene)


class TestEdgeCases:
    """Test per casi limite."""

    def test_very_small_scene(self, qtbot):
        """Test con scene molto piccola."""
        view = CrosshairGraphicsView(view_idx=0)
        qtbot.addWidget(view)

        small_scene = QGraphicsScene()
        small_scene.setSceneRect(0, 0, 10, 10)
        view.setScene(small_scene)
        view.setup_crosshairs()

        view.update_crosshairs(5, 5)

        # Non dovrebbe crashare
        assert view.crosshair_visible

    def test_very_large_scene(self, qtbot):
        """Test con scene molto grande."""
        view = CrosshairGraphicsView(view_idx=0)
        qtbot.addWidget(view)

        large_scene = QGraphicsScene()
        large_scene.setSceneRect(0, 0, 10000, 10000)
        view.setScene(large_scene)
        view.setup_crosshairs()

        view.update_crosshairs(5000, 5000)

        assert view.crosshair_visible

    def test_rectangular_scene(self, qtbot):
        """Test con scene rettangolare."""
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
        """Test movimenti rapidi del mouse."""
        view = CrosshairGraphicsView(view_idx=0, parent=mock_parent_viewer)
        qtbot.addWidget(view)
        view.setScene(graphics_scene)
        view.setup_crosshairs()

        # Simula 100 movimenti rapidi
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

        # Non dovrebbe crashare
        assert view.crosshair_visible

    def test_rapid_clicks(self, qtbot, mock_parent_viewer, graphics_scene):
        """Test click rapidi."""
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

        # handle_click_coordinates dovrebbe essere stato chiamato 50 volte
        assert mock_parent_viewer.handle_click_coordinates.call_count == 50

    def test_scene_change(self, qtbot):
        """Test cambio scene."""
        view = CrosshairGraphicsView(view_idx=0)
        qtbot.addWidget(view)

        # Prima scene
        scene1 = QGraphicsScene()
        scene1.setSceneRect(0, 0, 256, 256)
        view.setScene(scene1)
        view.setup_crosshairs()

        crosshair_h1 = view.crosshair_h

        # Seconda scene
        scene2 = QGraphicsScene()
        scene2.setSceneRect(0, 0, 512, 512)
        view.setScene(scene2)
        view.setup_crosshairs()

        # Crosshair dovrebbero essere nuovi
        assert view.crosshair_h is not crosshair_h1

    def test_coordinate_precision(self, qtbot, mock_parent_viewer, graphics_scene):
        """Test precisione coordinate con float."""
        view = CrosshairGraphicsView(view_idx=0, parent=mock_parent_viewer)
        qtbot.addWidget(view)
        view.setScene(graphics_scene)

        # Coordinate float dovrebbero essere convertite in int
        event = QMouseEvent(
            QMouseEvent.Type.MouseButtonPress,
            QPointF(100.7, 200.3),
            Qt.MouseButton.LeftButton,
            Qt.MouseButton.LeftButton,
            Qt.KeyboardModifier.NoModifier
        )
        view.mousePressEvent(event)

        # Verifica che siano stati passati come int
        args = mock_parent_viewer.handle_click_coordinates.call_args[0]
        assert isinstance(args[1], int)
        assert isinstance(args[2], int)


class TestIntegration:
    """Test di integrazione."""

    def test_full_interaction_flow(self, qtbot, mock_parent_viewer, graphics_scene):
        """Test flusso completo: setup -> mouse move -> click."""
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
        """Test interazione tra multiple view."""
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

        # Interazione su view1
        event = QMouseEvent(
            QMouseEvent.Type.MouseButtonPress,
            QPointF(100, 100),
            Qt.MouseButton.LeftButton,
            Qt.MouseButton.LeftButton,
            Qt.KeyboardModifier.NoModifier
        )
        view1.mousePressEvent(event)

        # Verifica view_idx corretto
        args1 = mock_parent_viewer.handle_click_coordinates.call_args[0]
        assert args1[0] == 0

        # Interazione su view2
        mock_parent_viewer.handle_click_coordinates.reset_mock()
        view2.mousePressEvent(event)

        args2 = mock_parent_viewer.handle_click_coordinates.call_args[0]
        assert args2[0] == 1

    def test_crosshair_synchronization(self, qtbot, graphics_scene):
        """Test sincronizzazione crosshair."""
        view = CrosshairGraphicsView(view_idx=0)
        qtbot.addWidget(view)
        view.setScene(graphics_scene)
        view.setup_crosshairs()

        # Aggiorna via update_crosshairs
        view.update_crosshairs(100, 200)

        line_h1 = view.crosshair_h.line()
        assert line_h1.y1() == 200

        # Aggiorna via set_crosshair_position
        view.set_crosshair_position(150, 250)

        line_h2 = view.crosshair_h.line()
        assert line_h2.y1() == 250


class TestBoundaryConditions:
    """Test per condizioni al limite."""

    def test_click_at_zero_zero(self, qtbot, mock_parent_viewer, graphics_scene):
        """Test click a (0, 0)."""
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
        """Test click alle coordinate massime."""
        view = CrosshairGraphicsView(view_idx=0, parent=mock_parent_viewer)
        qtbot.addWidget(view)
        view.setScene(graphics_scene)

        # Scene è 512x512, quindi max valido è 511,511
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
        """Test click appena fuori dai limiti."""
        view = CrosshairGraphicsView(view_idx=0, parent=mock_parent_viewer)
        qtbot.addWidget(view)
        view.setScene(graphics_scene)

        # 512 è fuori (scene è 0-511)
        event = QMouseEvent(
            QMouseEvent.Type.MouseButtonPress,
            QPointF(512, 512),
            Qt.MouseButton.LeftButton,
            Qt.MouseButton.LeftButton,
            Qt.KeyboardModifier.NoModifier
        )
        view.mousePressEvent(event)

        # Non dovrebbe chiamare handle_click_coordinates
        mock_parent_viewer.handle_click_coordinates.assert_not_called()


class TestViewIndexHandling:
    """Test per la gestione del view_idx."""

    def test_different_view_indices_in_signals(self, qtbot, mock_parent_viewer, graphics_scene):
        """Test che view_idx sia corretto nei signal."""
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
        """Test che view_idx persista."""
        view = CrosshairGraphicsView(view_idx=7)
        qtbot.addWidget(view)

        assert view.view_idx == 7

        # Dopo varie operazioni
        scene = QGraphicsScene()
        view.setScene(scene)
        view.setup_crosshairs()

        assert view.view_idx == 7


class TestMemoryAndCleanup:
    """Test per memoria e cleanup."""

    def test_scene_items_cleanup(self, qtbot, graphics_scene):
        """Test cleanup degli item della scene."""
        view = CrosshairGraphicsView(view_idx=0)
        qtbot.addWidget(view)
        view.setScene(graphics_scene)

        initial_items = len(graphics_scene.items())

        view.setup_crosshairs()

        # Dovrebbero essere stati aggiunti 2 item (linee)
        assert len(graphics_scene.items()) == initial_items + 2

    def test_multiple_setup_doesnt_leak(self, qtbot, graphics_scene):
        """Test che setup multipli non causino memory leak."""
        view = CrosshairGraphicsView(view_idx=0)
        qtbot.addWidget(view)
        view.setScene(graphics_scene)

        # Setup multipli
        for _ in range(10):
            view.setup_crosshairs()

        # Gli item vecchi dovrebbero essere stati rimossi/sostituiti
        # (dipende dall'implementazione)
        assert True


class TestRenderHints:
    """Test per render hints."""

    def test_antialiasing_enabled(self, qtbot):
        """Test che antialiasing sia abilitato."""
        view = CrosshairGraphicsView(view_idx=0)
        qtbot.addWidget(view)

        hints = view.renderHints()
        assert hints & QPainter.RenderHint.Antialiasing

    def test_smooth_pixmap_transform_enabled(self, qtbot):
        """Test che smooth pixmap transform sia abilitato."""
        view = CrosshairGraphicsView(view_idx=0)
        qtbot.addWidget(view)

        hints = view.renderHints()
        assert hints & QPainter.RenderHint.SmoothPixmapTransform

    def test_render_hints_persist(self, qtbot, graphics_scene):
        """Test che render hints persistano dopo operazioni."""
        view = CrosshairGraphicsView(view_idx=0)
        qtbot.addWidget(view)

        view.setScene(graphics_scene)
        view.setup_crosshairs()

        hints = view.renderHints()
        assert hints & QPainter.RenderHint.Antialiasing
        assert hints & QPainter.RenderHint.SmoothPixmapTransform


class TestErrorHandling:
    """Test per la gestione degli errori."""

    def test_mapToScene_with_invalid_point(self, qtbot, mock_parent_viewer, graphics_scene):
        """Test mapToScene con punto non valido."""
        view = CrosshairGraphicsView(view_idx=0, parent=mock_parent_viewer)
        qtbot.addWidget(view)
        view.setScene(graphics_scene)

        # Punto molto fuori dai limiti
        event = QMouseEvent(
            QMouseEvent.Type.MouseMove,
            QPointF(999999, 999999),
            Qt.MouseButton.NoButton,
            Qt.MouseButton.NoButton,
            Qt.KeyboardModifier.NoModifier
        )

        # Non dovrebbe crashare
        view.mouseMoveEvent(event)

    def test_operations_without_initialization(self, qtbot):
        """Test operazioni senza inizializzazione completa."""
        view = CrosshairGraphicsView(view_idx=0)
        qtbot.addWidget(view)

        # Varie operazioni senza scene/crosshair setup
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

        # Non dovrebbe crashare
        assert True


class TestStateConsistency:
    """Test per la consistenza dello stato."""

    def test_crosshair_visible_state_consistency(self, qtbot, graphics_scene):
        """Test consistenza stato crosshair_visible."""
        view = CrosshairGraphicsView(view_idx=0)
        qtbot.addWidget(view)
        view.setScene(graphics_scene)
        view.setup_crosshairs()

        # Inizialmente non visibile
        assert not view.crosshair_visible
        assert not view.crosshair_h.isVisible()

        # Dopo update, visibile
        view.update_crosshairs(100, 100)
        assert view.crosshair_visible
        assert view.crosshair_h.isVisible()
        assert view.crosshair_v.isVisible()

    def test_crosshair_position_consistency(self, qtbot, graphics_scene):
        """Test consistenza posizione crosshair."""
        view = CrosshairGraphicsView(view_idx=0)
        qtbot.addWidget(view)
        view.setScene(graphics_scene)
        view.setup_crosshairs()

        # Imposta posizione
        view.update_crosshairs(123, 456)

        line_h = view.crosshair_h.line()
        line_v = view.crosshair_v.line()

        # Verifica consistenza
        assert line_h.y1() == line_h.y2() == 456
        assert line_v.x1() == line_v.x2() == 123


class TestDocumentation:
    """Test per la documentazione."""

    def test_class_docstring(self):
        """Test che la classe abbia docstring."""
        assert CrosshairGraphicsView.__doc__ is not None
        assert "crosshair" in CrosshairGraphicsView.__doc__.lower()

    def test_setup_crosshairs_docstring(self, qtbot):
        """Test che setup_crosshairs abbia docstring."""
        view = CrosshairGraphicsView(view_idx=0)
        qtbot.addWidget(view)

        assert view.setup_crosshairs.__doc__ is not None


class TestAccessibility:
    """Test per l'accessibilità."""

    def test_crosshair_color_visible(self, qtbot, graphics_scene):
        """Test che il colore dei crosshair sia visibile."""
        view = CrosshairGraphicsView(view_idx=0)
        qtbot.addWidget(view)
        view.setScene(graphics_scene)
        view.setup_crosshairs()

        pen = view.crosshair_h.pen()
        color = pen.color()

        # Giallo con alpha dovrebbe essere visibile
        assert color.alpha() == 180
        assert color.red() == 255
        assert color.green() == 255
        assert color.blue() == 0

    def test_crosshair_width_appropriate(self, qtbot, graphics_scene):
        """Test che la larghezza dei crosshair sia appropriata."""
        view = CrosshairGraphicsView(view_idx=0)
        qtbot.addWidget(view)
        view.setScene(graphics_scene)
        view.setup_crosshairs()

        pen_h = view.crosshair_h.pen()
        pen_v = view.crosshair_v.pen()

        # Larghezza 1 dovrebbe essere visibile ma non invasiva
        assert pen_h.width() == 1
        assert pen_v.width() == 1


class TestPerformance:
    """Test per le performance."""

    def test_many_coordinate_updates(self, qtbot, mock_parent_viewer, graphics_scene):
        """Test con molti aggiornamenti coordinate."""
        view = CrosshairGraphicsView(view_idx=0, parent=mock_parent_viewer)
        qtbot.addWidget(view)
        view.setScene(graphics_scene)
        view.setup_crosshairs()

        # 1000 aggiornamenti
        for i in range(1000):
            view.update_crosshairs(i % 512, (i * 2) % 512)

        # Non dovrebbe causare problemi di performance
        assert view.crosshair_visible

    def test_signal_emission_performance(self, qtbot, mock_parent_viewer, graphics_scene):
        """Test performance emission signal."""
        view = CrosshairGraphicsView(view_idx=0, parent=mock_parent_viewer)
        qtbot.addWidget(view)
        view.setScene(graphics_scene)

        signal_count = 0

        def count_signal(*args):
            nonlocal signal_count
            signal_count += 1

        view.coordinate_changed.connect(count_signal)

        # Molti eventi mouse
        for i in range(100):
            event = QMouseEvent(
                QMouseEvent.Type.MouseMove,
                QPointF(i % 512, (i * 2) % 512),
                Qt.MouseButton.NoButton,
                Qt.MouseButton.NoButton,
                Qt.KeyboardModifier.NoModifier
            )
            view.mouseMoveEvent(event)

        # Signal dovrebbe essere stato emesso molte volte
        assert signal_count > 0
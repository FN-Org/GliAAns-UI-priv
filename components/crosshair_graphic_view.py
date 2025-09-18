from PyQt6.QtCore import pyqtSignal, Qt
from PyQt6.QtGui import QPainter, QPen, QColor, QMouseEvent
from PyQt6.QtWidgets import QGraphicsView


class CrosshairGraphicsView(QGraphicsView):
    """Custom QGraphicsView with crosshair support and coordinate capture"""

    coordinate_changed = pyqtSignal(int, int, int)  # view_idx, x, y
    slice_changed = pyqtSignal(int, int)  # view_idx, new_slice

    def __init__(self, view_idx, parent=None):
        super().__init__(parent)
        self.view_idx = view_idx
        self.parent_viewer = parent
        self.setMouseTracking(True)
        self.setDragMode(QGraphicsView.DragMode.NoDrag)

        # Crosshair lines
        self.crosshair_h = None
        self.crosshair_v = None
        self.crosshair_visible = False

        # Set rendering hints for smooth display
        self.setRenderHints(
            QPainter.RenderHint.Antialiasing |
            QPainter.RenderHint.SmoothPixmapTransform
        )

    def setup_crosshairs(self):
        """Initialize crosshair lines"""
        if self.scene():
            pen = QPen(QColor(255, 255, 0, 180), 1)
            self.crosshair_h = self.scene().addLine(0, 0, 0, 0, pen)
            self.crosshair_v = self.scene().addLine(0, 0, 0, 0, pen)
            self.crosshair_h.setVisible(False)
            self.crosshair_v.setVisible(False)

    def mouseMoveEvent(self, event: QMouseEvent):
        """Handle mouse movement for coordinate display and crosshairs"""
        if self.scene() and self.parent_viewer and self.parent_viewer.img_data is not None:
            pos = self.mapToScene(event.pos())
            x, y = int(pos.x()), int(pos.y())

            # Check bounds
            scene_rect = self.scene().sceneRect()
            if (0 <= x < scene_rect.width() and 0 <= y < scene_rect.height()):
                # Update crosshairs
                self.update_crosshairs(x, y)
                # Emit coordinate change
                self.coordinate_changed.emit(self.view_idx, x, y)

        super().mouseMoveEvent(event)

    def mousePressEvent(self, event: QMouseEvent):
        """Handle mouse clicks for coordinate selection and slice navigation"""
        if (event.button() == Qt.MouseButton.LeftButton and
                self.scene() and self.parent_viewer and
                self.parent_viewer.img_data is not None):

            pos = self.mapToScene(event.pos())
            x, y = int(pos.x()), int(pos.y())

            # Check bounds
            scene_rect = self.scene().sceneRect()
            if 0 <= x < scene_rect.width() and 0 <= y < scene_rect.height():
                # Update clicked coordinates and trigger cross-view updates
                self.parent_viewer.handle_click_coordinates(self.view_idx, x, y)

        super().mousePressEvent(event)

    def update_crosshairs(self, x, y):
        """Update crosshair position"""
        if self.crosshair_h and self.crosshair_v and self.scene():
            scene_rect = self.scene().sceneRect()

            # Horizontal line
            self.crosshair_h.setLine(0, y, scene_rect.width(), y)
            # Vertical line
            self.crosshair_v.setLine(x, 0, x, scene_rect.height())

            if not self.crosshair_visible:
                self.crosshair_h.setVisible(True)
                self.crosshair_v.setVisible(True)
                self.crosshair_visible = True

    def set_crosshair_position(self, x, y):
        """Set crosshair position from external call"""
        if self.crosshair_h and self.crosshair_v and self.scene():
            scene_rect = self.scene().sceneRect()
            if (0 <= x < scene_rect.width() and 0 <= y < scene_rect.height()):
                self.crosshair_h.setLine(0, y, scene_rect.width(), y)
                self.crosshair_v.setLine(x, 0, x, scene_rect.height())
                self.crosshair_h.setVisible(True)
                self.crosshair_v.setVisible(True)
                self.crosshair_visible = True

    def leaveEvent(self, event):
        """Hide crosshairs when mouse leaves the view"""
        if self.crosshair_h and self.crosshair_v:
            #self.crosshair_h.setVisible(False)
            #self.crosshair_v.setVisible(False)
            #self.crosshair_visible = False
            self.parent_viewer.update_cross_view_lines()
        super().leaveEvent(event)


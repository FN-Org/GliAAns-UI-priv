from PyQt6.QtCore import pyqtSignal, Qt
from PyQt6.QtGui import QPainter, QPen, QColor, QMouseEvent, QWheelEvent
from PyQt6.QtWidgets import QGraphicsView


class CrosshairGraphicsView(QGraphicsView):
    """Custom QGraphicsView subclass that supports:
       - Live crosshair display following mouse movements
       - Coordinate tracking and emission via Qt signals
       - Integration with a parent viewer for synchronized slice updates
    """

    # Signal emitted whenever the mouse moves — sends (view_idx, x, y).
    coordinate_changed = pyqtSignal(int, int, int)
    """**Signal(int, int, int):** Emitted whenever the mouse moves within a view.  
    Parameters represent:
    - `view_idx`: The index of the active view (e.g., axial, coronal, sagittal).  
    - `x`, `y`: The current mouse coordinates within that view.
    """

    def __init__(self, view_idx, parent=None):
        """
        Initialize the crosshair view.

        Args:
            view_idx (int): Index of the view (e.g. axial=0, coronal=1, sagittal=2)
            parent (QWidget): Parent viewer widget (usually manages multiple CrosshairGraphicsViews)
        """
        super().__init__(parent)
        self.view_idx = view_idx
        self.parent_viewer = parent

        # Enable continuous mouse tracking (even when no button pressed)
        self.setMouseTracking(True)

        # Disable dragging mode (only used for coordinate interaction)
        self.setDragMode(QGraphicsView.DragMode.NoDrag)

        # Crosshair graphics items (horizontal and vertical lines)
        self.crosshair_h = None
        self.crosshair_v = None
        self.crosshair_visible = False

        # Enable anti-aliasing and smooth scaling for better visual quality
        self.setRenderHints(
            QPainter.RenderHint.Antialiasing |
            QPainter.RenderHint.SmoothPixmapTransform
        )

    # -------------------------------------------------------------------------
    # Crosshair setup and management
    # -------------------------------------------------------------------------
    def setup_crosshairs(self):
        """
        Initialize the crosshair lines once the QGraphicsScene is available.
        Adds two semi-transparent yellow lines to the scene (horizontal + vertical).
        """
        if self.scene():
            # Yellow, semi-transparent pen for crosshair
            pen = QPen(QColor(255, 255, 0, 180), 1)

            # Create horizontal and vertical crosshair lines in the scene
            self.crosshair_h = self.scene().addLine(0, 0, 0, 0, pen)
            self.crosshair_v = self.scene().addLine(0, 0, 0, 0, pen)

            # Initially invisible
            self.crosshair_h.setVisible(False)
            self.crosshair_v.setVisible(False)

    # -------------------------------------------------------------------------
    # Mouse movement: update coordinates and crosshair position
    # -------------------------------------------------------------------------
    def mouseMoveEvent(self, event: QMouseEvent):
        """
        Handle mouse movement:
          - Maps cursor position to scene coordinates
          - Checks bounds
          - Updates crosshair lines
          - Emits coordinate_changed signal
        """
        if self.scene() and self.parent_viewer and self.parent_viewer.img_data is not None:
            # Map mouse position from view to scene coordinates
            pos = self.mapToScene(event.pos())
            x, y = int(pos.x()), int(pos.y())

            # Get scene dimensions for bounds checking
            scene_rect = self.scene().sceneRect()

            # Only process if cursor is inside the image area
            if (0 <= x < scene_rect.width() and 0 <= y < scene_rect.height()):
                # Move crosshair to current position
                self.update_crosshairs(x, y)

                # Notify parent about the new coordinates
                self.coordinate_changed.emit(self.view_idx, x, y)

        # Pass event to base class for default behavior
        super().mouseMoveEvent(event)

    # -------------------------------------------------------------------------
    # Mouse scroll: change slices
    # -------------------------------------------------------------------------

    def wheelEvent(self, event: QWheelEvent):
        delta = int(event.angleDelta().y()/120)
        self.parent_viewer.handle_scroll(self.view_idx, delta)
        event.accept()

    # -------------------------------------------------------------------------
    # Mouse click: trigger coordinate selection or slice updates
    # -------------------------------------------------------------------------
    def mousePressEvent(self, event: QMouseEvent):
        """
        Handle mouse clicks:
          - On left-click, compute image coordinates
          - Notify parent viewer for cross-view synchronization or slice update
        """
        if (event.button() == Qt.MouseButton.LeftButton and
                self.scene() and self.parent_viewer and
                self.parent_viewer.img_data is not None):

            # Convert click position to scene coordinates
            pos = self.mapToScene(event.pos())
            x, y = int(pos.x()), int(pos.y())

            # Verify position is inside the scene
            scene_rect = self.scene().sceneRect()
            if 0 <= x < scene_rect.width() and 0 <= y < scene_rect.height():
                # Delegate handling to parent viewer (e.g., update other views)
                self.parent_viewer.handle_click_coordinates(self.view_idx, x, y)

        super().mousePressEvent(event)

    # -------------------------------------------------------------------------
    # Update crosshair position visually
    # -------------------------------------------------------------------------
    def update_crosshairs(self, x, y):
        """
        Move crosshair lines to a new position (x, y).
        Makes them visible if hidden.
        """
        if self.crosshair_h and self.crosshair_v and self.scene():
            scene_rect = self.scene().sceneRect()

            # Horizontal line across the scene
            self.crosshair_h.setLine(0, y, scene_rect.width(), y)

            # Vertical line across the scene
            self.crosshair_v.setLine(x, 0, x, scene_rect.height())

            # If not visible yet, make them appear
            if not self.crosshair_visible:
                self.crosshair_h.setVisible(True)
                self.crosshair_v.setVisible(True)
                self.crosshair_visible = True

    # -------------------------------------------------------------------------
    # External setter for crosshair position (used by parent viewer)
    # -------------------------------------------------------------------------
    def set_crosshair_position(self, x, y):
        """
        Allows external components (e.g. linked views) to set the crosshair.
        Ensures it's within bounds before updating.
        """
        if self.crosshair_h and self.crosshair_v and self.scene():
            scene_rect = self.scene().sceneRect()
            if (0 <= x < scene_rect.width() and 0 <= y < scene_rect.height()):
                self.crosshair_h.setLine(0, y, scene_rect.width(), y)
                self.crosshair_v.setLine(x, 0, x, scene_rect.height())
                self.crosshair_h.setVisible(True)
                self.crosshair_v.setVisible(True)
                self.crosshair_visible = True

    # -------------------------------------------------------------------------
    # Handle when the mouse leaves the widget area
    # -------------------------------------------------------------------------
    def leaveEvent(self, event):
        """
        Hide or update crosshairs when the mouse leaves the view area.
        Currently, it calls the parent viewer’s update function to
        synchronize crosshairs across multiple views.
        """
        if self.crosshair_h and self.crosshair_v:
            # Previous behavior (hidden when leaving):
            # self.crosshair_h.setVisible(False)
            # self.crosshair_v.setVisible(False)
            # self.crosshair_visible = False

            # New behavior: ask parent to refresh all cross-view lines
            self.parent_viewer.update_cross_view_lines()

        super().leaveEvent(event)

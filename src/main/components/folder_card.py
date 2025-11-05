import os
from PyQt6.QtCore import (
    pyqtProperty, QPropertyAnimation, QSize, Qt,
    QEasingCurve, QSequentialAnimationGroup, QParallelAnimationGroup, pyqtSignal, QCoreApplication
)
from PyQt6.QtGui import QColor, QIcon, QPainter, QPen
from PyQt6.QtWidgets import (
    QWidget, QVBoxLayout, QPushButton, QDialog, QListWidget,
    QListWidgetItem, QHBoxLayout, QLabel, QFrame, QScrollArea, QAbstractItemView
)


class FolderCard(QWidget):
    """
    A modern, self-contained widget representing a monitored output folder.
    It shows the folder name, file count, and allows the user to open or inspect
    newly generated files. Includes subtle visual animations for updates.
    """

    # Signal emitted when the user requests to open the folder externally
    open_folder_requested = pyqtSignal(str)

    def __init__(self, context, folder):
        """
        Initialize the FolderCard.

        Args:
            context (dict): Shared application context (unused here, reserved for integration).
            folder (str): Path to the folder being represented by this card.
        """
        super().__init__()

        self.folder = folder
        self.files = []  # Tracks new files added since the last check
        self.is_finished = False
        # self.existing_files = set(os.listdir(folder)) if os.path.isdir(folder) else set()
        self.existing_files = self._list_all_files(folder)

        # Animation and visual properties
        self.pulse_animation = None
        self._scale = 1.0
        self._glow_opacity = 0.0

        # Define a fixed height for uniform card size
        self.setFixedHeight(100)

        # Build the UI
        self._setup_ui()

    # -------------------------------------------------------------------------
    # UI setup
    # -------------------------------------------------------------------------
    def _setup_ui(self):
        """Configure the visual layout and styling for the folder card."""
        layout = QVBoxLayout(self)
        layout.setContentsMargins(8, 8, 8, 8)

        # Main container frame with light elevation
        self.card_frame = QFrame()
        self.card_frame.setObjectName("outputsCard")
        self.card_frame.setStyleSheet("""
            QFrame#outputsCard {
                background-color: white;
                border-radius: 12px;
                border: 1px solid #e0e0e0;
            }
        """)

        # Horizontal layout for card contents
        card_layout = QHBoxLayout(self.card_frame)
        card_layout.setContentsMargins(16, 12, 16, 12)
        card_layout.setSpacing(12)

        # Left section: folder icon
        self.folder_icon = QLabel("📁")
        self.folder_icon.setStyleSheet("""
            font-size: 32px;
            padding: 8px;
            background-color: #f0f7ff;
            border-radius: 8px;
        """)
        self.folder_icon.setFixedSize(56, 56)
        self.folder_icon.setAlignment(Qt.AlignmentFlag.AlignCenter)
        card_layout.addWidget(self.folder_icon)

        # Center section: folder name and status
        info_layout = QVBoxLayout()
        info_layout.setSpacing(4)

        # Folder name label
        self.folder_name = QLabel(os.path.basename(self.folder))
        self.folder_name.setStyleSheet("""
            font-size: 14px;
            font-weight: 600;
            color: #2c3e50;
        """)
        info_layout.addWidget(self.folder_name)

        # Status label (e.g., “Waiting for files…” or “3 new files”)
        self.status_label = QLabel(QCoreApplication.translate("Components", "Waiting for files..."))
        self.status_label.setStyleSheet("""
            font-size: 12px;
            color: #7f8c8d;
        """)
        info_layout.addWidget(self.status_label)

        card_layout.addLayout(info_layout, stretch=1)

        # Right section: action button
        self.action_btn = QPushButton(QCoreApplication.translate("Components", "Visualize"))
        self.action_btn.setStyleSheet("""
            QPushButton {
                background-color: #3498db;
                color: white;
                border: none;
                border-radius: 8px;
                padding: 8px 20px;
                font-size: 13px;
                font-weight: 600;
            }
            QPushButton:hover {
                background-color: #2980b9;
            }
            QPushButton:pressed {
                background-color: #21618c;
            }
            QPushButton:disabled {
                background-color: #bdc3c7;
                color: #7f8c8d;
            }
        """)
        self.action_btn.clicked.connect(self.show_files_dialog)
        self.action_btn.setEnabled(False)
        card_layout.addWidget(self.action_btn)

        layout.addWidget(self.card_frame)

    # -------------------------------------------------------------------------
    # File handling and state updates
    # -------------------------------------------------------------------------
    def add_files(self, new_files):
        """
        Add new files to the card, update the UI, and trigger a pulse animation.

        Args:
            new_files (list[str]): Names of newly detected files.
        """
        if self.is_finished:
            return

        self.files.extend(new_files)
        file_count = len(self.files)

        # Update visual state to show activity
        self.status_label.setText(
            QCoreApplication.translate("Components", "{file_count} new file").format(file_count=file_count)
        )
        self.status_label.setStyleSheet("""
            font-size: 12px;
            color: #27ae60;
            font-weight: 600;
        """)

        self.action_btn.setEnabled(True)

        # Change the icon and color scheme to indicate success
        self.folder_icon.setText("✓")
        self.folder_icon.setStyleSheet("""
            font-size: 32px;
            padding: 8px;
            background-color: #d5f4e6;
            border-radius: 8px;
            color: #27ae60;
        """)

        # Update card border to highlight new content
        self.card_frame.setStyleSheet("""
            QFrame#outputsCard {
                background-color: white;
                border-radius: 12px;
                border: 2px solid #27ae60;
            }
        """)

        # Trigger pulse animation for visual feedback
        self.start_pulse_animation()

    def start_pulse_animation(self):
        """
        Perform a subtle pulsing height animation when new files are added.
        """
        if self.pulse_animation:
            self.pulse_animation.stop()

        self.pulse_animation = QSequentialAnimationGroup()

        # Expand slightly
        pulse1 = QPropertyAnimation(self.card_frame, b"maximumHeight")
        pulse1.setDuration(300)
        pulse1.setStartValue(100)
        pulse1.setEndValue(104)
        pulse1.setEasingCurve(QEasingCurve.Type.OutCubic)

        # Contract back
        pulse2 = QPropertyAnimation(self.card_frame, b"maximumHeight")
        pulse2.setDuration(300)
        pulse2.setStartValue(104)
        pulse2.setEndValue(100)
        pulse2.setEasingCurve(QEasingCurve.Type.InCubic)

        self.pulse_animation.addAnimation(pulse1)
        self.pulse_animation.addAnimation(pulse2)
        self.pulse_animation.start()

    def reset_state(self):
        """
        Reset the card’s appearance to its initial “waiting” state.
        Called after viewing or clearing files.
        """
        self.files.clear()
        self.is_finished = False  # Resetta lo stato
        self.existing_files = self._list_all_files(self.folder)

        self.status_label.setText(QCoreApplication.translate("Components", "Waiting for files..."))
        self.status_label.setStyleSheet("""
            font-size: 12px;
            color: #7f8c8d;
        """)

        self.folder_icon.setText("📁")
        self.folder_icon.setStyleSheet("""
            font-size: 32px;
            padding: 8px;
            background-color: #f0f7ff;
            border-radius: 8px;
        """)

        self.card_frame.setStyleSheet("""
            QFrame#outputsCard {
                background-color: white;
                border-radius: 12px;
                border: 1px solid #e0e0e0;
            }
        """)

        self.action_btn.setEnabled(False)

        if self.pulse_animation:
            self.pulse_animation.stop()

    # -------------------------------------------------------------------------
    # Dialog for file inspection
    # -------------------------------------------------------------------------
    def show_files_dialog(self):
        """
        Open a dialog window displaying all new files detected for this folder.
        Provides options to open the folder or close the dialog.
        """
        if not self.files:
            return

        dialog = QDialog(self)
        dialog.setWindowTitle(
            QCoreApplication.translate("Components", "Generated file - {0}")
            .format(os.path.basename(self.folder))
        )
        dialog.setModal(True)
        dialog.setMinimumSize(600, 500)

        layout = QVBoxLayout(dialog)
        layout.setContentsMargins(20, 20, 20, 20)
        layout.setSpacing(16)

        # Header with file count
        header = QLabel(
            QCoreApplication.translate("Components", "📊 {0} generated file").format(len(self.files))
        )
        header.setStyleSheet("""
            font-size: 18px;
            font-weight: bold;
            color: #2c3e50;
            padding: 8px;
        """)
        layout.addWidget(header)

        # Folder path subtitle
        path_label = QLabel(f"📁 {self.folder}")
        path_label.setStyleSheet("""
            font-size: 12px;
            color: #7f8c8d;
            padding: 0 8px 8px 8px;
        """)
        path_label.setWordWrap(True)
        layout.addWidget(path_label)

        # File list area
        list_widget = QListWidget()
        list_widget.setSelectionMode(QAbstractItemView.SelectionMode.NoSelection)
        list_widget.setFocusPolicy(Qt.FocusPolicy.NoFocus)
        list_widget.setEditTriggers(QAbstractItemView.EditTrigger.NoEditTriggers)
        list_widget.setStyleSheet("""
            QListWidget {
                border: 1px solid #e0e0e0;
                border-radius: 8px;
                background-color: #fafafa;
                padding: 8px;
            }
            QListWidget::item {
                padding: 12px;
                border-radius: 6px;
                margin: 2px;
            }
        """)

        # Populate list with filenames
        for f in sorted(self.files):
            item = QListWidgetItem(f"📄  {f.replace(os.sep, '/')}")
            item.setToolTip(os.path.join(self.folder, f))
            list_widget.addItem(item)

        layout.addWidget(list_widget)

        # Footer buttons
        button_layout = QHBoxLayout()
        button_layout.setSpacing(12)

        # Button: open containing folder
        btn_open_folder = QPushButton(QCoreApplication.translate("Components", "📂 Open Folder"))
        btn_open_folder.setStyleSheet("""
            QPushButton {
                background-color: #3498db;
                color: white;
                border: none;
                border-radius: 8px;
                padding: 12px 24px;
                font-size: 14px;
                font-weight: 600;
            }
            QPushButton:hover {
                background-color: #2980b9;
            }
        """)
        btn_open_folder.clicked.connect(lambda: self.open_folder_requested.emit(self.folder))

        # Button: close dialog
        btn_close = QPushButton(QCoreApplication.translate("Components", "Close"))
        btn_close.setStyleSheet("""
            QPushButton {
                background-color: #ecf0f1;
                color: #2c3e50;
                border: 1px solid #bdc3c7;
                border-radius: 8px;
                padding: 12px 24px;
                font-size: 14px;
                font-weight: 600;
            }
            QPushButton:hover {
                background-color: #e0e0e0;
            }
        """)
        btn_close.clicked.connect(dialog.accept)

        button_layout.addWidget(btn_open_folder)
        button_layout.addStretch()
        button_layout.addWidget(btn_close)

        layout.addLayout(button_layout)

        dialog.exec()

        # After closing the dialog, clear and reset
        self.files.clear()
        self.reset_state()

    # -------------------------------------------------------------------------
    # Monitoring logic
    # -------------------------------------------------------------------------
    def check_new_files(self):
        """
        Check if new files have appeared in the monitored folder.
        If new files are found, they are added and the UI is updated.
        """
        if self.is_finished:
            return

        if not os.path.isdir(self.folder):
            return

        current_files = self._list_all_files(self.folder)
        new_files = current_files - self.existing_files

        if new_files:
            self.add_files(list(new_files))

        self.existing_files = current_files

    def _list_all_files(self, root_folder):
        """Restituisce un set con tutti i file nella cartella e nelle sottocartelle."""
        all_files = set()
        if not os.path.isdir(root_folder):
            return all_files
        for dirpath, _, filenames in os.walk(root_folder):
            for f in filenames:
                # Salva percorsi relativi (rispetto alla root) per coerenza
                relative_path = os.path.relpath(os.path.join(dirpath, f), root_folder)
                all_files.add(relative_path)
        return all_files

    def set_finished_state(self):
        """
        Sets the card to a visual "Completed" state.
        Performs a final file check and updates the interface.
        """
        if self.is_finished:
            return

        self.is_finished = True

        self.check_new_files()

        file_count = len(self.existing_files)

        self.status_label.setText(
            QCoreApplication.translate("Components", "Processing complete ({file_count} files)")
            .format(file_count=file_count)
        )
        self.status_label.setStyleSheet("""
            font-size: 12px;
            color: #27ae60;
            font-weight: 600;
        """)

        self.action_btn.setEnabled(False)

        self.folder_icon.setText("✓")
        self.folder_icon.setStyleSheet("""
            font-size: 32px;
            padding: 8px;
            background-color: #d5f4e6;
            border-radius: 8px;
            color: #27ae60;
        """)

        self.card_frame.setStyleSheet("""
            QFrame#outputsCard {
                background-color: white;
                border-radius: 12px;
                border: 2px solid #27ae60;
            }
        """)

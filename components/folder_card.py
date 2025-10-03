import os
from PyQt6.QtCore import (
    pyqtProperty, QPropertyAnimation, QSize, Qt,
    QEasingCurve, QSequentialAnimationGroup, QParallelAnimationGroup, pyqtSignal
)
from PyQt6.QtGui import QColor, QIcon, QPainter, QPen
from PyQt6.QtWidgets import (
    QWidget, QVBoxLayout, QPushButton, QDialog, QListWidget,
    QListWidgetItem, QHBoxLayout, QLabel, QFrame, QScrollArea
)


class FolderCard(QWidget):
    open_folder_requested = pyqtSignal(str)

    def __init__(self, folder):
        super().__init__()

        self.folder = folder
        self.files = []
        self.existing_files = set(os.listdir(folder)) if os.path.isdir(folder) else set()
        self.pulse_animation = None
        self._scale = 1.0
        self._glow_opacity = 0.0

        self.setFixedHeight(100)
        self._setup_ui()

    def _setup_ui(self):
        """Configura l'interfaccia moderna della card"""
        layout = QVBoxLayout(self)
        layout.setContentsMargins(8, 8, 8, 8)

        # Container principale con effetto elevato
        self.card_frame = QFrame()
        self.card_frame.setObjectName("outputsCard")
        self.card_frame.setStyleSheet("""
            QFrame#outputsCard {
                background-color: white;
                border-radius: 12px;
                border: 1px solid #e0e0e0;
            }
        """)

        card_layout = QHBoxLayout(self.card_frame)
        card_layout.setContentsMargins(16, 12, 16, 12)
        card_layout.setSpacing(12)

        # Icona cartella (lato sinistro)
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

        # Area centrale con info
        info_layout = QVBoxLayout()
        info_layout.setSpacing(4)

        # Nome cartella
        self.folder_name = QLabel(os.path.basename(self.folder))
        self.folder_name.setStyleSheet("""
            font-size: 14px;
            font-weight: 600;
            color: #2c3e50;
        """)
        info_layout.addWidget(self.folder_name)

        # Stato/sottotitolo
        self.status_label = QLabel("In attesa di file...")
        self.status_label.setStyleSheet("""
            font-size: 12px;
            color: #7f8c8d;
        """)
        info_layout.addWidget(self.status_label)

        card_layout.addLayout(info_layout, stretch=1)

        # Pulsante azione
        self.action_btn = QPushButton("Visualizza")
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

    def add_files(self, new_files):
        """Aggiunge nuovi file e attiva l'animazione"""
        self.files.extend(new_files)

        # Aggiorna UI
        file_count = len(self.files)

        self.status_label.setText(f"{file_count} nuov{'o' if file_count == 1 else 'i'} file")
        self.status_label.setStyleSheet("""
            font-size: 12px;
            color: #27ae60;
            font-weight: 600;
        """)

        self.action_btn.setEnabled(True)

        # Cambia icona e colore
        self.folder_icon.setText("✓")
        self.folder_icon.setStyleSheet("""
            font-size: 32px;
            padding: 8px;
            background-color: #d5f4e6;
            border-radius: 8px;
            color: #27ae60;
        """)

        # Cambia stile card
        self.card_frame.setStyleSheet("""
            QFrame#outputsCard {
                background-color: white;
                border-radius: 12px;
                border: 2px solid #27ae60;
            }
        """)

        # Avvia animazione di pulse
        self.start_pulse_animation()

    def start_pulse_animation(self):
        """Animazione sottile di pulse quando arrivano nuovi file"""
        if self.pulse_animation:
            self.pulse_animation.stop()

        # Crea sequenza di animazioni
        self.pulse_animation = QSequentialAnimationGroup()

        # Prima pulsazione
        pulse1 = QPropertyAnimation(self.card_frame, b"maximumHeight")
        pulse1.setDuration(300)
        pulse1.setStartValue(100)
        pulse1.setEndValue(104)
        pulse1.setEasingCurve(QEasingCurve.Type.OutCubic)

        pulse2 = QPropertyAnimation(self.card_frame, b"maximumHeight")
        pulse2.setDuration(300)
        pulse2.setStartValue(104)
        pulse2.setEndValue(100)
        pulse2.setEasingCurve(QEasingCurve.Type.InCubic)

        self.pulse_animation.addAnimation(pulse1)
        self.pulse_animation.addAnimation(pulse2)
        self.pulse_animation.start()

    def reset_state(self):
        """Resetta lo stato della card"""

        self.status_label.setText("In attesa di file...")
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

    def show_files_dialog(self):
        """Mostra dialog moderno con lista file"""
        if not self.files:
            return

        dialog = QDialog(self)
        dialog.setWindowTitle(f"File generati - {os.path.basename(self.folder)}")
        dialog.setModal(True)
        dialog.setMinimumSize(600, 500)

        layout = QVBoxLayout(dialog)
        layout.setContentsMargins(20, 20, 20, 20)
        layout.setSpacing(16)

        # Header
        header = QLabel(f"📊 {len(self.files)} file generat{'o' if len(self.files) == 1 else 'i'}")
        header.setStyleSheet("""
            font-size: 18px;
            font-weight: bold;
            color: #2c3e50;
            padding: 8px;
        """)
        layout.addWidget(header)

        # Sottotitolo con path
        path_label = QLabel(f"📁 {self.folder}")
        path_label.setStyleSheet("""
            font-size: 12px;
            color: #7f8c8d;
            padding: 0 8px 8px 8px;
        """)
        path_label.setWordWrap(True)
        layout.addWidget(path_label)

        # Lista file moderna
        list_widget = QListWidget()
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

        # Aggiungi file alla lista
        for f in sorted(self.files):
            item = QListWidgetItem(f"📄  {f}")
            item.setToolTip(os.path.join(self.folder, f))
            list_widget.addItem(item)

        layout.addWidget(list_widget)

        # Pulsanti azione
        button_layout = QHBoxLayout()
        button_layout.setSpacing(12)

        btn_open_folder = QPushButton("📂 Apri Cartella")
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

        btn_close = QPushButton("Chiudi")
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

        # Reset dopo visualizzazione
        self.files.clear()
        self.reset_state()

    def check_new_files(self):
        """Controlla se ci sono nuovi file nella cartella"""
        if not os.path.isdir(self.folder):
            return

        current_files = set(os.listdir(self.folder))
        new_files = current_files - self.existing_files

        if new_files:
            self.add_files(list(new_files))

        self.existing_files = current_files
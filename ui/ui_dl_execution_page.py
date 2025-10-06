import os
from PyQt6 import QtWidgets, QtGui, QtCore
from PyQt6.QtWidgets import (QWidget, QVBoxLayout, QLabel, QPushButton,
                             QScrollArea, QFrame, QGridLayout, QHBoxLayout,
                             QMessageBox, QGroupBox, QListWidget, QProgressBar,
                             QListWidgetItem, QTextEdit, QSplitter, QFileDialog,
                             QCheckBox)
from PyQt6.QtCore import Qt, QThread, QCoreApplication

from components.circular_progress_bar import CircularProgress
from threads.dl_thread import DlWorker
from page import Page
from logger import get_logger

log = get_logger()


class DlExecutionPage(Page):
    """Pagina per SynthStrip + Coregistrazione dei file NIfTI selezionati"""

    def __init__(self, context=None, previous_page=None):
        super().__init__()
        self.worker = None
        self.current_file = None
        self.context = context
        self.previous_page = previous_page
        self.next_page = None

        self.processing = False
        self.processing_completed = False

        self._setup_ui()

        self._translate_ui()
        if context and "language_changed" in context:
            context["language_changed"].connect(self._translate_ui)

    def _setup_ui(self):
        """Configura l'interfaccia utente"""
        main_layout = QVBoxLayout(self)

        # Header
        self.header = QLabel("Deep Learning Segmentation")
        self.header.setStyleSheet("""
            font-size: 24px; 
            font-weight: bold; 
            color: #2c3e50;
            margin-bottom: 10px;
        """)
        self.header.setAlignment(Qt.AlignmentFlag.AlignCenter)
        main_layout.addWidget(self.header)

        # Current operation
        self.current_operation = QLabel("Ready to start")
        self.current_operation.setStyleSheet("""
            font-size: 13px;
            color: #7f8c8d;
            margin-top: 8px;
        """)
        self.current_operation.setAlignment(Qt.AlignmentFlag.AlignCenter)
        main_layout.addWidget(self.current_operation)

        # --- Content area ---
        content_layout = QGridLayout()
        main_layout.addLayout(content_layout, stretch=1)

        # --- Left: Circular progress bar ---
        left_layout = QVBoxLayout()
        self.progress_bar = CircularProgress()
        left_layout.addWidget(self.progress_bar, alignment=Qt.AlignmentFlag.AlignCenter)
        content_layout.addLayout(left_layout, 0, 0)

        # === SEZIONE FILE SELEZIONATI ===
        self.files_group = QGroupBox("Files to process")
        files_layout = QVBoxLayout(self.files_group)

        self.files_list = QListWidget()
        self.files_list.setMaximumHeight(150)
        files_layout.addWidget(self.files_list)

        content_layout.addWidget(self.files_list, 0, 1)

        # === SEZIONE PROGRESSO ===
        left_layout = QVBoxLayout()
        self.progress_bar = CircularProgress()
        left_layout.addWidget(self.progress_bar, alignment=Qt.AlignmentFlag.AlignCenter)
        content_layout.addLayout(left_layout, 0, 0)

        # Columns: 1/3 for progress bar, 2/3 for scroll area
        content_layout.setColumnStretch(0, 1)  # left column (progress bar)
        content_layout.setColumnStretch(1, 2)  # right column (folder list)

        # === SEZIONE LOG ===
        self.log_label = QLabel("Execution Log:")
        self.log_label.setStyleSheet("""
                    font-size: 16px;
                    font-weight: bold;
                    color: #2c3e50;
                    margin-top: 15px;
                    margin-bottom: 5px;
                """)
        content_layout.addWidget(self.log_label, 1, 0, 1, 2)

        self.log_text = QTextEdit()
        self.log_text.setStyleSheet("""
                    QTextEdit {
                        background-color: #2c3e50;
                        color: #ecf0f1;
                        font-family: 'Courier New', monospace;
                        font-size: 11px;
                        border: 2px solid #34495e;
                        border-radius: 8px;
                        padding: 8px;
                    }
                """)
        self.log_text.setMaximumHeight(200)
        self.log_text.setReadOnly(True)
        content_layout.addWidget(self.log_text, 2, 0, 1, 2)

        # === PULSANTI CONTROLLO ===

        # --- Stop button (centered) ---
        button_frame = QFrame()
        button_layout = QHBoxLayout(button_frame)
        button_layout.setContentsMargins(0, 15, 0, 0)

        self.start_button = QPushButton("Start deep learning")
        button_layout.addStretch()
        self.start_button.clicked.connect(self.start_processing)
        self.start_button.setStyleSheet("""
            QPushButton {
                font-size: 14px;
                font-weight: bold;
                background-color: #27ae60;
                color: white;
                border-radius: 8px;
                padding: 10px 20px;
                min-width: 140px;
            }
            QPushButton:hover { 
                background-color: #229954; 
            }
            QPushButton:disabled {
                background-color: #bdc3c7;
                color: #7f8c8d;
            }
        """)
        button_layout.addWidget(self.start_button)

        self.cancel_button = QPushButton("Stop processing")
        self.cancel_button.setStyleSheet("""
            QPushButton {
                font-size: 14px;
                font-weight: bold;
                background-color: #e74c3c;
                color: white;
                border-radius: 8px;
                padding: 10px 20px;
                min-width: 140px;
            }
            QPushButton:hover { 
                background-color: #c0392b; 
            }
            QPushButton:disabled {
                background-color: #bdc3c7;
                color: #7f8c8d;
            }
        """)
        self.cancel_button.clicked.connect(self.cancel_processing)
        button_layout.addStretch()
        button_layout.addWidget(self.cancel_button)
        button_layout.addStretch()

        main_layout.addWidget(button_frame)

    def on_enter(self):
        """Chiamata quando si entra nella pagina"""
        self.reset_processing_state()

        # Popoliamo la lista dei file se disponibile
        if self.context and "selected_segmentation_files" in self.context:
            self.files_list.clear()
            for file_path in self.context["selected_segmentation_files"]:
                filename = os.path.basename(file_path)
                self.files_list.addItem(QCoreApplication.translate("DlExecutionPage", "📄 {filename} - Waiting...").format(filename=filename))

    def start_processing(self):
        """Avvia il processamento"""
        if not self.context or "selected_segmentation_files" not in self.context:
            QMessageBox.warning(self, QCoreApplication.translate("DlExecutionPage", "Error"), QCoreApplication.translate("DlExecutionPage", "No files selected for processing."))
            return

        selected_files = self.context["selected_segmentation_files"]
        if not selected_files:
            QMessageBox.warning(self, QCoreApplication.translate("DlExecutionPage", "Error"), QCoreApplication.translate("DlExecutionPage", "No files selected for processing."))
            return

        # Avvia worker thread
        self.worker = DlWorker(
            input_files=selected_files,
            workspace_path=self.context["workspace_path"]
        )
        # self.worker.moveToThread(self.thread)

        # Connects signals
        self.worker.progressbar_update.connect(self.update_progress)
        self.worker.file_update.connect(self.update_file_status)
        self.worker.log_update.connect(self.add_log_message)
        self.worker.finished.connect(self.processing_finished)

        # self.worker.finished.connect(self.worker.deleteLater)

        # Update UI
        self.processing = True
        self.start_button.setVisible(False)
        self.cancel_button.setVisible(True)
        self.progress_bar.setVisible(True)
        self.progress_bar.setValue(0)
        self.current_operation.setText(QCoreApplication.translate("DlExecutionPage", "Processing..."))
        self.log_text.clear()

        # Start worker on thread
        # self.thread.start()
        self.worker.start()

        self.add_log_message(QCoreApplication.translate("DlExecutionPage", "Deep learning processing started for {0} file").format(len(selected_files)), 'i')
        log.info(f"Deep learning processing started for {len(selected_files)} file")

    def update_progress(self, value):
        """Aggiorna la barra di progresso"""
        self.progress_bar.setValue(value)

    def add_log_message(self, message, type):
        """Aggiunge un messaggio al log"""
        timestamp = QtCore.QDateTime.currentDateTime().toString("hh:mm:ss")
        self.log_text.append(f"[{timestamp}] {message}")

        if type == 'e':
            log.error(f"[{timestamp}] {message}")
        elif type == 'i':
            log.info(f"[{timestamp}] {message}")
        elif type == 'w':
            log.warning(f"[{timestamp}] {message}")
        else:
            log.debug(f"[{timestamp}] {message}")

        # Scrolla automaticamente verso il basso
        scrollbar = self.log_text.verticalScrollBar()
        scrollbar.setValue(scrollbar.maximum())

    def update_file_status(self, filename, status):
        """Aggiorna lo stato di un file nella lista"""
        for i in range(self.files_list.count()):
            item = self.files_list.item(i)
            if filename in item.text():
                item.setText(f"📄 {filename} - {status}")
                break

    def cancel_processing(self):
        """Cancella il processamento in corso"""
        if self.worker:
            self.worker.cancel_requested.emit()
            # self.worker.cancel()
            self.add_log_message(QCoreApplication.translate("DlExecutionPage", "Cancellation requested..."), 'i')

    def processing_finished(self, success, message):
        """Chiamata quando il processamento termina"""
        self.processing = False
        self.processing_completed = True

        # Aggiorna UI
        self.start_button.setVisible(True)
        self.cancel_button.setVisible(False)
        self.progress_bar.setVisible(False)

        if success:
            self.current_operation.setText(QCoreApplication.translate("DlExecutionPage", "✓ Processing completed!"))
            self.current_operation.setStyleSheet("color: green; font-weight: bold;")
            self.start_button.setText("Reprocess")
        else:
            self.current_operation.setText("✗ Processing failed!")
            self.current_operation.setStyleSheet("color: #c0392b; font-weight: bold;")

        self.add_log_message(QCoreApplication.translate("DlExecutionPage", "Final: {message}").format(message=message), 'i')

        # Aggiorna context con risultati
        if success and "workspace_path" in self.context:
            output_dir = os.path.join(self.context["workspace_path"], "outputs")
            self.context["processing_output_dir"] = output_dir

        # Notifica cambio stato
        if "update_main_buttons" in self.context:
            self.context["update_main_buttons"]()

        # Mostra messaggio finale
        if success:
            QMessageBox.information(self, QCoreApplication.translate("DlExecutionPage", "Completed"), message)
        else:
            QMessageBox.critical(self, QCoreApplication.translate("DlExecutionPage", "Error"), message)

    def reset_processing_state(self):
        """Resetta lo stato del processamento"""
        self.processing = False
        self.processing_completed = False
        self.start_button.setText(QCoreApplication.translate("DlExecutionPage", "Start deep learning"))
        self.start_button.setVisible(True)
        self.cancel_button.setVisible(False)
        self.progress_bar.setVisible(False)
        self.current_operation.setStyleSheet("")

        if self.worker:
            self.worker = None

    def back(self):
        """Torna alla pagina precedente"""
        if self.processing:
            reply = QMessageBox.question(
                self,
                QCoreApplication.translate("DlExecutionPage", "Processing in progress"),
                QCoreApplication.translate("DlExecutionPage", "Processing is in progress. Do you really want to go back?\nProcessing will be interrupted."),
                QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
                QMessageBox.StandardButton.No
            )
            if reply == QMessageBox.StandardButton.No:
                return None

            # Interrompi processamento
            if self.worker:
                self.worker.cancel_requested.emit()
                # self.worker.cancel()

        if self.previous_page:
            self.previous_page.on_enter()
            return self.previous_page
        return None

    def next(self, context):
        """Avanza alla pagina successiva"""
        return None

    def is_ready_to_advance(self):
        """Controlla se è possibile andare alla pagina successiva"""
        return False

    def is_ready_to_go_back(self):
        """Controlla se è possibile tornare indietro"""
        return True

    def _translate_ui(self):
        self.header.setText(QCoreApplication.translate("DlExecutionPage", "Deep Learning Segmentation"))
        self.current_operation.setText(QCoreApplication.translate("DlExecutionPage", "Ready to start"))
        self.files_group.setTitle(QCoreApplication.translate("DlExecutionPage", "Files to process"))
        self.log_label.setText(QCoreApplication.translate("DlExecutionPage", "Execution Log:"))
        self.start_button.setText(QCoreApplication.translate("DlExecutionPage", "Start deep learning"))
        self.cancel_button.setText(QCoreApplication.translate("DlExecutionPage", "Stop processing"))

        if self.context and "selected_segmentation_files" in self.context:
            self.files_list.clear()
            for file_path in self.context["selected_segmentation_files"]:
                filename = os.path.basename(file_path)
                self.files_list.addItem(QCoreApplication.translate("DlExecutionPage", "📄 {filename} - Waiting...").format(filename=filename))


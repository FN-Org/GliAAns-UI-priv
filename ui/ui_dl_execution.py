import os
from PyQt6 import QtWidgets, QtGui, QtCore
from PyQt6.QtGui import QIcon, QPixmap
from PyQt6.QtWidgets import (QWidget, QVBoxLayout, QLabel, QPushButton,
                             QScrollArea, QFrame, QGridLayout, QHBoxLayout,
                             QMessageBox, QGroupBox, QListWidget, QProgressBar,
                             QListWidgetItem, QTextEdit, QSplitter, QFileDialog,
                             QCheckBox)
from PyQt6.QtCore import Qt, QThread, pyqtSignal, QTimer, QProcess

from pediatric_fdopa_pipeline.utils import align, transform
from threads.dl_thread import DlThread
from wizard_state import WizardPage
from logger import get_logger

log = get_logger()


class DlExecutionPage(WizardPage):
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

    def _setup_ui(self):
        """Configura l'interfaccia utente"""
        self.layout = QVBoxLayout(self)
        self.setLayout(self.layout)

        # Titolo
        self.title = QLabel("Skull Stripping + Coregistrazione")
        self.title.setStyleSheet("font-size: 18px; font-weight: bold;")
        self.title.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.layout.addWidget(self.title)

        description = QLabel(
            "I file NIfTI verranno processati con SynthStrip per rimuovere il cranio,\n"
            "seguiti opzionalmente da coregistrazione con atlas T1.\n"
            "I risultati saranno salvati nella cartella outputs del workspace."
        )
        description.setAlignment(Qt.AlignmentFlag.AlignCenter)
        description.setStyleSheet("color: gray; margin-bottom: 20px;")
        self.layout.addWidget(description)

        # === CONFIGURAZIONE ATLAS ===
        atlas_group = QGroupBox("Configurazione Coregistrazione")
        atlas_layout = QVBoxLayout(atlas_group)

        # Checkbox coregistrazione (di default attiva)
        self.enable_coregistration = QCheckBox("Abilita coregistrazione con atlas")
        self.enable_coregistration.setChecked(True)
        atlas_layout.addWidget(self.enable_coregistration)

        # Label percorso atlas (bloccata sul default)
        atlas_selection_layout = QHBoxLayout()
        self.atlas_label = QLabel("Atlas T1.nii.gz:")
        self.atlas_path_label = QLabel(os.path.basename(self.atlas_path))
        self.atlas_path_label.setToolTip(self.atlas_path)
        self.atlas_path_label.setStyleSheet("color: black; font-style: normal;")

        # Disabilitiamo il pulsante (niente scelta manuale)
        self.select_atlas_button = QPushButton("Seleziona Atlas")
        self.select_atlas_button.setEnabled(False)

        atlas_selection_layout.addWidget(self.atlas_label)
        atlas_selection_layout.addWidget(self.atlas_path_label, 1)
        atlas_selection_layout.addWidget(self.select_atlas_button)
        atlas_layout.addLayout(atlas_selection_layout)

        self.layout.addWidget(atlas_group)

        # Splitter per dividere file list e log
        splitter = QSplitter(Qt.Orientation.Vertical)
        self.layout.addWidget(splitter)

        # === SEZIONE FILE SELEZIONATI ===
        files_group = QGroupBox("File da processare")
        files_layout = QVBoxLayout(files_group)

        self.files_list = QListWidget()
        self.files_list.setMaximumHeight(150)
        files_layout.addWidget(self.files_list)

        splitter.addWidget(files_group)

        # === SEZIONE PROGRESSO ===
        progress_group = QGroupBox("Progresso")
        progress_layout = QVBoxLayout(progress_group)

        # Barra progresso generale
        self.progress_bar = QProgressBar()
        self.progress_bar.setVisible(False)
        progress_layout.addWidget(self.progress_bar)

        # Label stato
        self.status_label = QLabel("Pronto per iniziare il processamento")
        self.status_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        progress_layout.addWidget(self.status_label)

        splitter.addWidget(progress_group)

        # === SEZIONE LOG ===
        log_group = QGroupBox("Log processamento")
        log_layout = QVBoxLayout(log_group)

        self.log_text = QTextEdit()
        self.log_text.setReadOnly(True)
        self.log_text.setMaximumHeight(200)
        self.log_text.setStyleSheet("font-family: monospace; font-size: 10px;")
        log_layout.addWidget(self.log_text)

        splitter.addWidget(log_group)

        # Imposta dimensioni splitter
        splitter.setSizes([80, 150, 100, 200])

        # === PULSANTI CONTROLLO ===
        button_layout = QHBoxLayout()

        self.start_button = QPushButton("Avvia Processamento")
        self.start_button.clicked.connect(self.start_processing)
        self.start_button.setStyleSheet("font-weight: bold; padding: 10px;")
        button_layout.addWidget(self.start_button)

        self.cancel_button = QPushButton("Annulla")
        self.cancel_button.clicked.connect(self.cancel_processing)
        self.cancel_button.setVisible(False)
        button_layout.addWidget(self.cancel_button)

        self.layout.addLayout(button_layout)

    def toggle_atlas_selection(self, state):
        """Abilita/disabilita selezione atlas"""
        enabled = state == Qt.CheckState.Checked.value
        self.atlas_label.setEnabled(enabled)
        self.atlas_path_label.setEnabled(enabled)
        self.select_atlas_button.setEnabled(enabled)

    def select_atlas_file(self):
        """Seleziona file atlas"""
        file_path, _ = QFileDialog.getOpenFileName(
            self,
            "Seleziona Atlas T1.nii.gz",
            "",
            "File NIfTI (*.nii.gz *.nii);;Tutti i file (*)"
        )

        if file_path:
            self.atlas_path = file_path
            self.atlas_path_label.setText(os.path.basename(file_path))
            self.atlas_path_label.setStyleSheet("color: black; font-style: normal;")
            self.atlas_path_label.setToolTip(file_path)

    def on_enter(self):
        """Chiamata quando si entra nella pagina"""
        self.reset_processing_state()

        # Popoliamo la lista dei file se disponibile
        if self.context and "selected_segmentation_files" in self.context:
            self.files_list.clear()
            for file_path in self.context["selected_segmentation_files"]:
                filename = os.path.basename(file_path)
                self.files_list.addItem(f"📄 {filename} - In attesa")

    def start_processing(self):
        """Avvia il processamento"""
        if not self.context or "selected_segmentation_files" not in self.context:
            QMessageBox.warning(self, "Errore", "Nessun file selezionato per il processamento.")
            return

        selected_files = self.context["selected_segmentation_files"]
        if not selected_files:
            QMessageBox.warning(self, "Errore", "Nessun file selezionato per il processamento.")
            return

        # Verifica atlas se coregistrazione abilitata
        if self.enable_coregistration.isChecked():
            if not self.atlas_path or not os.path.exists(self.atlas_path):
                QMessageBox.warning(
                    self,
                    "Atlas mancante",
                    "Seleziona un file atlas valido per la coregistrazione\no disabilita la coregistrazione."
                )
                return

        # Avvia worker thread
        self.worker = DlThread(
            input_files=selected_files,
            workspace_path=self.context["workspace_path"]
        )

        # Connetti segnali
        self.worker.progressbar_update.connect(self.update_progress)
        self.worker.file_update.connect(self.update_file_status)
        self.worker.log_update.connect(self.add_log_message)
        self.worker.finished.connect(self.processing_finished)

        # Aggiorna UI
        self.processing = True
        self.start_button.setVisible(False)
        self.cancel_button.setVisible(True)
        self.progress_bar.setVisible(True)
        self.progress_bar.setValue(0)
        self.status_label.setText("Processamento in corso...")
        self.log_text.clear()

        # Avvia worker
        self.worker.start()

        self.add_log_message(f"Deep learning processing started for {len(selected_files)} file")
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
            self.worker.stop_processing()
            self.worker.cancel()
            self.add_log_message("Cancellazione richiesta...")

    def processing_finished(self, success, message):
        """Chiamata quando il processamento termina"""
        self.processing = False
        self.processing_completed = True

        # Aggiorna UI
        self.start_button.setVisible(True)
        self.cancel_button.setVisible(False)
        self.progress_bar.setVisible(False)

        if success:
            self.status_label.setText("✓ Processamento completato!")
            self.status_label.setStyleSheet("color: green; font-weight: bold;")
            self.start_button.setText("Riprocessa")
        else:
            self.status_label.setText("✗ Processamento fallito")
            self.status_label.setStyleSheet("color: red; font-weight: bold;")

        self.add_log_message(f"FINALE: {message}")

        # Aggiorna context con risultati
        if success and "workspace_path" in self.context:
            output_dir = os.path.join(self.context["workspace_path"], "outputs")
            self.context["processing_output_dir"] = output_dir
            if self.enable_coregistration.isChecked():
                self.context["coregistration_completed"] = True

        # Notifica cambio stato
        if "update_main_buttons" in self.context:
            self.context["update_main_buttons"]()

        # Mostra messaggio finale
        if success:
            QMessageBox.information(self, "Completato", message)
        else:
            QMessageBox.critical(self, "Errore", message)

    def reset_processing_state(self):
        """Resetta lo stato del processamento"""
        self.processing = False
        self.processing_completed = False
        self.start_button.setText("Avvia Processamento")
        self.start_button.setVisible(True)
        self.cancel_button.setVisible(False)
        self.progress_bar.setVisible(False)
        self.status_label.setStyleSheet("")

        if self.worker:
            self.worker.quit()
            self.worker.wait()
            self.worker = None
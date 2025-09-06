import os
import shutil
import subprocess
from pathlib import Path
from PyQt6 import QtWidgets, QtGui, QtCore
from PyQt6.QtGui import QIcon, QPixmap
from PyQt6.QtWidgets import (QWidget, QVBoxLayout, QLabel, QPushButton,
                             QScrollArea, QFrame, QGridLayout, QHBoxLayout,
                             QMessageBox, QGroupBox, QListWidget, QProgressBar,
                             QListWidgetItem, QTextEdit, QSplitter)
from PyQt6.QtCore import Qt, QThread, pyqtSignal, QTimer

from wizard_state import WizardPage
from logger import get_logger

log = get_logger()


class SynthStripWorker(QThread):
    """Worker thread per processare i file NIfTI con SynthStrip"""

    progress_updated = pyqtSignal(int)  # Progresso generale (0-100)
    file_progress_updated = pyqtSignal(str, str)  # (filename, status)
    log_updated = pyqtSignal(str)  # Messaggi di log
    finished = pyqtSignal(bool, str)  # (success, message)

    def __init__(self, input_files, output_dir):
        super().__init__()
        self.input_files = input_files
        self.output_dir = output_dir
        self.is_cancelled = False

    def run(self):
        """Processa tutti i file NIfTI con SynthStrip"""
        try:
            # if not SYNTHSTRIP_AVAILABLE:
            #     self.finished.emit(False, "SynthStrip o Pydra non disponibili. Verificare l'installazione.")
            #     return

            # Crea la directory di output se non esiste
            os.makedirs(self.output_dir, exist_ok=True)

            total_files = len(self.input_files)
            processed_files = 0
            failed_files = []

            for i, input_file in enumerate(self.input_files):
                if self.is_cancelled:
                    break

                try:
                    success = self.process_single_file(input_file)
                    if success:
                        processed_files += 1
                        self.file_progress_updated.emit(
                            os.path.basename(input_file),
                            "✓ Completato"
                        )
                    else:
                        failed_files.append(os.path.basename(input_file))
                        self.file_progress_updated.emit(
                            os.path.basename(input_file),
                            "✗ Fallito"
                        )

                except Exception as e:
                    failed_files.append(os.path.basename(input_file))
                    self.file_progress_updated.emit(
                        os.path.basename(input_file),
                        f"✗ Errore: {str(e)}"
                    )
                    log.error(f"Errore processando {input_file}: {e}")

                # Aggiorna progresso generale
                progress = int((i + 1) * 100 / total_files)
                self.progress_updated.emit(progress)

            # Risultato finale
            if self.is_cancelled:
                self.finished.emit(False, "Processamento cancellato dall'utente.")
            elif failed_files:
                message = f"Processamento completato con errori.\n"
                message += f"Processati con successo: {processed_files}/{total_files}\n"
                message += f"Falliti: {', '.join(failed_files)}"
                self.finished.emit(True, message)
            else:
                message = f"Tutti i {total_files} file processati con successo!"
                self.finished.emit(True, message)

        except Exception as e:
            log.error(f"Errore generale nel worker: {e}")
            self.finished.emit(False, f"Errore generale: {str(e)}")

    def process_single_file(self, input_file):
        input_basename = os.path.basename(input_file)
        if input_file.endswith('.nii.gz'):
            output_filename = input_basename.replace('.nii.gz', '_skull_stripped.nii.gz')
        elif input_file.endswith('.nii'):
            output_filename = input_basename.replace('.nii', '_skull_stripped.nii')
        else:
            output_filename = input_basename + '_skull_stripped.nii.gz'

        output_file = os.path.join(self.output_dir, output_filename)

        if os.path.exists(output_file):
            self.log_updated.emit(f"File {output_filename} già esistente, saltato.")
            return True

        self.log_updated.emit(f"Avvio SynthStrip su {input_basename}...")
        self.file_progress_updated.emit(input_basename, "🔄 Processando...")

        cmd = [
            "nipreps-synthstrip",
            "-i", input_file,
            "-o", output_file,
            "--model", "synthstrip.1.pt"
        ]

        try:
            result = subprocess.run(cmd, capture_output=True, text=True)
            # Log completo stdout/stderr
            self.log_updated.emit(f"stdout:\n{result.stdout}")
            self.log_updated.emit(f"stderr:\n{result.stderr}")

            if result.returncode != 0:
                self.log_updated.emit(f"✗ Errore processando {input_basename}: returncode {result.returncode}")
                return False

            if os.path.exists(output_file):
                self.log_updated.emit(f"✓ SynthStrip completato per {input_basename}")
                return True
            else:
                self.log_updated.emit(f"✗ File di output non creato per {input_basename}")
                return False

        except Exception as e:
            self.log_updated.emit(f"✗ Eccezione processando {input_basename}: {str(e)}")
            return False

    def cancel(self):
        """Cancella il processamento"""
        self.is_cancelled = True


class DlExecutionPage(WizardPage):
    """Pagina per il processamento SynthStrip dei file NIfTI selezionati"""

    def __init__(self, context=None, previous_page=None):
        super().__init__()
        self.context = context
        self.previous_page = previous_page
        self.next_page = None

        self.worker = None
        self.processing = False
        self.processing_completed = False

        self._setup_ui()

    def _setup_ui(self):
        """Configura l'interfaccia utente"""
        self.layout = QVBoxLayout(self)
        self.setLayout(self.layout)

        # Titolo
        self.title = QLabel("Skull Stripping con SynthStrip")
        self.title.setStyleSheet("font-size: 18px; font-weight: bold;")
        self.title.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.layout.addWidget(self.title)

        # Descrizione
        description = QLabel(
            "I file NIfTI selezionati verranno processati con SynthStrip per rimuovere il cranio.\n"
            "I risultati saranno salvati nella cartella outputs del workspace."
        )
        description.setAlignment(Qt.AlignmentFlag.AlignCenter)
        description.setStyleSheet("color: gray; margin-bottom: 20px;")
        self.layout.addWidget(description)

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
        splitter.setSizes([150, 100, 200])

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

        # Verifica disponibilità SynthStrip
        # if not SYNTHSTRIP_AVAILABLE:
        #     self.start_button.setEnabled(False)
        #     # self.status_label.setText(f"⚠️ {SYNTHSTRIP_STATUS}")
        #     self.status_label.setText(f"⚠️belin")
        #     self.status_label.setStyleSheet("color: red;")

    def on_enter(self):
        """Chiamata quando si entra nella pagina"""
        self.load_selected_files()
        self.reset_processing_state()

    def load_selected_files(self):
        """Carica i file selezionati dal contesto"""
        self.files_list.clear()

        if not self.context or "selected_segmentation_files" not in self.context:
            self.status_label.setText("Nessun file selezionato")
            return

        selected_files = self.context["selected_segmentation_files"]

        if not selected_files:
            self.status_label.setText("Nessun file selezionato")
            return

        # Aggiungi file alla lista
        for file_path in selected_files:
            item = QListWidgetItem()
            item.setText(f"📄 {os.path.basename(file_path)}")
            item.setToolTip(file_path)
            self.files_list.addItem(item)

        self.status_label.setText(f"Pronti {len(selected_files)} file per il processamento")

    def start_processing(self):
        """Avvia il processamento SynthStrip"""
        if not self.context or "selected_segmentation_files" not in self.context:
            QMessageBox.warning(self, "Errore", "Nessun file selezionato per il processamento.")
            return

        selected_files = self.context["selected_segmentation_files"]
        if not selected_files:
            QMessageBox.warning(self, "Errore", "Nessun file selezionato per il processamento.")
            return

        # Configura directory di output
        if "workspace_path" in self.context:
            output_dir = os.path.join(self.context["workspace_path"], "outputs")
        else:
            output_dir = os.path.join(os.getcwd(), ".workspace", "outputs")

        # Avvia worker thread
        self.worker = SynthStripWorker(selected_files, output_dir)
        self.worker.progress_updated.connect(self.update_progress)
        self.worker.file_progress_updated.connect(self.update_file_status)
        self.worker.log_updated.connect(self.add_log_message)
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

        log.info(f"Avviato processamento SynthStrip per {len(selected_files)} file")

    def cancel_processing(self):
        """Cancella il processamento in corso"""
        if self.worker:
            self.worker.cancel()
            self.add_log_message("Cancellazione richiesta...")

    def update_progress(self, value):
        """Aggiorna la barra di progresso"""
        self.progress_bar.setValue(value)

    def update_file_status(self, filename, status):
        """Aggiorna lo stato di un file nella lista"""
        for i in range(self.files_list.count()):
            item = self.files_list.item(i)
            if filename in item.text():
                item.setText(f"📄 {filename} - {status}")
                break

    def add_log_message(self, message):
        """Aggiunge un messaggio al log"""
        timestamp = QtCore.QDateTime.currentDateTime().toString("hh:mm:ss")
        self.log_text.append(f"[{timestamp}] {message}")
        # Scrolla automaticamente verso il basso
        scrollbar = self.log_text.verticalScrollBar()
        scrollbar.setValue(scrollbar.maximum())

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
            self.context["synthstrip_output_dir"] = output_dir

        # Notifica cambio stato per abilitare pulsante Next
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

    def back(self):
        """Torna alla pagina precedente"""
        if self.processing:
            reply = QMessageBox.question(
                self,
                "Processamento in corso",
                "Il processamento è in corso. Vuoi davvero tornare indietro?\nIl processamento verrà interrotto.",
                QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
                QMessageBox.StandardButton.No
            )
            if reply == QMessageBox.StandardButton.No:
                return None

            # Interrompi processamento
            if self.worker:
                self.worker.cancel()
                self.worker.quit()
                self.worker.wait()

        if self.previous_page:
            self.previous_page.on_enter()
            return self.previous_page
        return None

    def next(self, context):
        """Avanza alla pagina successiva"""
        # Qui puoi creare la pagina successiva o tornare al menu principale
        # Per ora restituiamo None per indicare fine del workflow
        return None

    def is_ready_to_advance(self):
        """Controlla se è possibile andare alla pagina successiva"""
        return self.processing_completed and not self.processing

    def is_ready_to_go_back(self):
        """Controlla se è possibile tornare indietro"""
        return True  # Sempre possibile, ma con conferma se processing attivo

    def reset_page(self):
        """Resetta la pagina allo stato iniziale"""
        self.reset_processing_state()
        self.log_text.clear()
        self.files_list.clear()
        self.status_label.setText("Pronto per iniziare il processamento")
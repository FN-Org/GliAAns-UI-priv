
import os
import json
import sys

from PyQt6.QtGui import QPen, QColor, QFont, QPainter
from PyQt6.QtWidgets import (
    QWidget, QVBoxLayout, QLabel, QProgressBar, QPushButton,
    QTextEdit, QFrame, QHBoxLayout, QScrollArea, QDialog, QListWidget, QSpacerItem, QSizePolicy, QGridLayout,
    QMessageBox
)
from PyQt6.QtCore import Qt, QTimer, pyqtSignal, QProcess, QRectF, QPropertyAnimation, pyqtProperty
from wizard_state import WizardPage
from logger import get_logger

log = get_logger()


class CircularProgress(QWidget):
    def __init__(self, color="#3498DB"):
        super().__init__()
        self.value = 0
        self.color = QColor(color)
        self.existing_files = []

    def setValue(self, val: int):
        self.value = max(0, min(100, val))
        self.update()

    def setColor(self, color: str | QColor):
        if isinstance(color, str):
            self.color = QColor(color)
        else:
            self.color = color
        self.update()

    def sizeHint(self):
        return self.parentWidget().size() if self.parentWidget() else super().sizeHint()

    def paintEvent(self, event):
        width = self.width()
        height = self.height()
        size = min(width, height)  # make it square

        # Center the circle
        x_offset = int((width - size) / 2)
        y_offset = int((height - size) / 2)

        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)

        # Background circle
        painter.setPen(Qt.PenStyle.NoPen)
        painter.setBrush(QColor("#f0f0f0"))
        painter.drawEllipse(x_offset, y_offset, int(size), int(size))

        # Progress arc
        pen_width = max(5, int(size / 12))
        pen = QPen(self.color)
        pen.setWidth(pen_width)
        pen.setCapStyle(Qt.PenCapStyle.RoundCap)
        painter.setPen(pen)
        painter.setBrush(Qt.BrushStyle.NoBrush)
        rect = QRectF(x_offset + pen_width / 2, y_offset + pen_width / 2,
                      size - pen_width, size - pen_width)
        angle_span = int(360 * self.value / 100)
        painter.drawArc(rect, -90 * 16, -angle_span * 16)

        # Text
        font_size = max(5, int(size / 9))
        painter.setPen(QColor("#2C3E50"))
        painter.setFont(QFont("Arial", font_size, QFont.Weight.Bold))
        painter.drawText(rect, Qt.AlignmentFlag.AlignCenter, f"{self.value}%")



class FolderCard(QWidget):
    def __init__(self, folder):
        super().__init__()

        self.folder = folder
        self.files = []
        self.existing_files = set(os.listdir(folder)) if os.path.isdir(folder) else set()
        self.animation = None
        self._bg_color = QColor("#ecf0f1")
        self.expanded = False

        # --- Layout ---
        self.layout = QVBoxLayout(self)
        self.layout.setContentsMargins(0, 0, 0, 0)

        # main button
        self.button = QPushButton(os.path.basename(folder))
        self.button.setFixedHeight(60)
        self.button.setStyleSheet("background-color: #ecf0f1; color: #2C3E50; border-radius: 8px;")
        self.button.clicked.connect(self.show_files)
        self.layout.addWidget(self.button)

        # expandable area
        self.file_area = QScrollArea()
        self.file_area.setWidgetResizable(True)
        self.file_list = QWidget()
        self.file_list_layout = QVBoxLayout(self.file_list)
        self.file_area.setWidget(self.file_list)
        self.file_area.setVisible(False)
        self.layout.addWidget(self.file_area)

    # --- property for animating background color ---
    def get_bg_color(self):
        return self._bg_color

    def set_bg_color(self, color):
        self._bg_color = color
        self.button.setStyleSheet(
            f"background-color: {color.name()}; color: white; border-radius: 8px;"
        )

    bgColor = pyqtProperty(QColor, fget=get_bg_color, fset=set_bg_color)

    # --- logic ---
    def add_files(self, new_files):
        self.files.extend(new_files)
        self.start_blinking()

    def start_blinking(self):
        if self.animation:  # already blinking
            return
        self.animation = QPropertyAnimation(self, b"bgColor")
        self.animation.setDuration(800)
        self.animation.setLoopCount(-1)  # blink until clicked
        self.animation.setKeyValueAt(0, QColor("#2ECC71"))
        self.animation.setKeyValueAt(0.5, QColor("#27AE60"))
        self.animation.setKeyValueAt(1, QColor("#2ECC71"))
        self.animation.start()

    def reset_state(self):
        if self.animation:
            self.animation.stop()
            self.animation = None
        self._bg_color = QColor("#ecf0f1")
        self.button.setStyleSheet("background-color: #ecf0f1; color: #2C3E50; border-radius: 8px;")

    def show_files(self):
        if not self.files and not self.expanded:
            return

        if not self.expanded:
            # expand and list files
            for i in reversed(range(self.file_list_layout.count())):
                w = self.file_list_layout.itemAt(i).widget()
                if w:
                    w.deleteLater()
            for f in self.files:
                self.file_list_layout.addWidget(QLabel(f))
            self.file_area.setVisible(True)
            self.expanded = True
            self.files.clear()
            self.reset_state()
        else:
            # collapse
            self.file_area.setVisible(False)
            self.expanded = False

    def check_new_files(self):
        if not os.path.isdir(self.folder):
            return
        current_files = set(os.listdir(self.folder))
        new_files = current_files - self.existing_files
        if new_files:
            self.add_files(list(new_files))
        self.existing_files = current_files

# Dialog che mostra i file di una cartella
class FileDialog(QDialog):
    def __init__(self, folder, files, parent=None):
        super().__init__(parent)
        self.setWindowTitle(f"Nuovi file in {folder}")
        layout = QVBoxLayout()
        list_widget = QListWidget()
        for f in files:
            list_widget.addItem(f)
        layout.addWidget(list_widget)
        self.setLayout(layout)
        self.resize(400, 300)

class PipelineExecutionPage(WizardPage):
    def __init__(self, context=None, previous_page=None):
        super().__init__()
        self.context = context
        self.workspace_path = context["workspace_path"]
        self.previous_page = previous_page
        self.next_page = None

        # Riferimento al processo della pipeline
        self.pipeline_process = None
        self.pipeline_completed = False
        self.pipeline_error = None

        # Trova l'ultimo config file creato
        self.config_path = self._find_latest_config()

        # Estrae l'ID dal nome del file config per determinare la directory di output
        config_filename = os.path.basename(self.config_path)
        try:
            config_id = config_filename.split('_')[0]
            self.pipeline_output_dir = os.path.join(self.workspace_path, "pipeline", f"{config_id}_output")
            os.makedirs(self.pipeline_output_dir, exist_ok=True)
        except (IndexError, ValueError):
            log.debug(f"Failed to create pipeline_output_dir: {self.pipeline_output_dir}")
            self.pipeline_output_dir = os.path.join(self.workspace_path, "pipeline")

        # Crea lo script temporaneo per la pipeline
        self.pipeline_script_path = "./pediatric_fdopa_pipeline/pipeline_runner.py"
        # self._create_pipeline_script()
        self._setup_ui()

    # def _create_pipeline_script(self):
    #     """Crea lo script Python temporaneo per l'esecuzione della pipeline."""
    #     os.makedirs(os.path.dirname(self.pipeline_script_path), exist_ok=True)
    #     with open(self.pipeline_script_path, 'w', encoding='utf-8') as f:
    #         f.write(PIPELINE_SCRIPT_CONTENT)

    def _find_latest_config(self):
        """Trova il file config con l'ID più alto nella cartella pipeline."""
        import glob
        pipeline_dir = os.path.join(self.workspace_path, "pipeline")

        if not os.path.exists(pipeline_dir):
            return os.path.join(pipeline_dir, "pipeline_config.json")

        config_pattern = os.path.join(pipeline_dir, "*_config.json")
        config_files = glob.glob(config_pattern)

        if not config_files:
            return os.path.join(pipeline_dir, "pipeline_config.json")

        max_id = 0
        latest_config = None

        for config_file in config_files:
            filename = os.path.basename(config_file)
            try:
                id_str = filename.split('_')[0]
                config_id = int(id_str)
                if config_id > max_id:
                    max_id = config_id
                    latest_config = config_file

            except (ValueError, IndexError):
                continue

        return latest_config if latest_config else os.path.join(pipeline_dir, "pipeline_config.json")

    def _setup_ui(self):
        # --- Top-level layout ---
        main_layout = QVBoxLayout(self)

        # Header
        header = QLabel("Pipeline Execution")
        header.setStyleSheet("""
            font-size: 24px; 
            font-weight: bold; 
            color: #2c3e50;
            margin-bottom: 10px;
        """)
        header.setAlignment(Qt.AlignmentFlag.AlignCenter)
        main_layout.addWidget(header)

        # Current operation
        self.current_operation = QLabel("Preparing to start...")
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

        # --- Right: Folder cards scroll area ---
        scroll_area = QScrollArea()
        scroll_area.setWidgetResizable(True)
        scroll_content = QWidget()
        scroll_layout = QVBoxLayout(scroll_content)
        scroll_area.setWidget(scroll_content)
        content_layout.addWidget(scroll_area, 0, 1)

        # Add FolderCards
        self.folder_cards = {}
        self.watch_dirs = self.get_sub_list(self.config_path)
        self.watch_dirs = [os.path.join(self.pipeline_output_dir, d) for d in self.watch_dirs]
        for d in self.watch_dirs:
            card = FolderCard(d)
            scroll_layout.addWidget(card)
            self.folder_cards[d] = card

        # Columns: 1/3 for progress bar, 2/3 for scroll area
        content_layout.setColumnStretch(0, 1)  # left column (progress bar)
        content_layout.setColumnStretch(1, 2)  # right column (folder list)

        # Rows: make first row expand vertically
        content_layout.setRowStretch(0, 1)  # main content row expands
        content_layout.setRowStretch(1, 0)  # log label fixed
        content_layout.setRowStretch(2, 1)  # log text fixed

        # --- Log section ---
        log_label = QLabel("Execution Log:")
        log_label.setStyleSheet("""
            font-size: 16px;
            font-weight: bold;
            color: #2c3e50;
            margin-top: 15px;
            margin-bottom: 5px;
        """)
        content_layout.addWidget(log_label, 1, 0, 1, 2)

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

        # --- Stop button (centered) ---
        button_frame = QFrame()
        button_layout = QHBoxLayout(button_frame)
        button_layout.setContentsMargins(0, 15, 0, 0)

        self.stop_button = QPushButton("Stop Pipeline")
        self.stop_button.setStyleSheet("""
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
        self.stop_button.clicked.connect(self._on_stop_clicked)
        button_layout.addStretch()
        button_layout.addWidget(self.stop_button)
        button_layout.addStretch()

        # Add button frame at bottom
        main_layout.addWidget(button_frame)

    def _start_pipeline(self):
        """Avvia il processo della pipeline."""
        if self.pipeline_process is not None:
            return  # Processo già in esecuzione

        self.pipeline_process = QProcess()

        # Connetti i segnali del processo
        self.pipeline_process.finished.connect(self._on_process_finished)
        self.pipeline_process.errorOccurred.connect(self._on_process_error)
        self.pipeline_process.readyReadStandardOutput.connect(self._on_stdout_ready)
        self.pipeline_process.readyReadStandardError.connect(self._on_stderr_ready)

        # Aggiorna UI per stato "in esecuzione"
        self.progress_bar.setValue(0)
        self.stop_button.setEnabled(True)

        # Aggiorna lo stile del frame di stato

        self._log_message("Starting pipeline execution...")

        # Prepara gli argomenti per il processo
        python_executable = sys.executable  # Usa lo stesso interprete Python
        args = [
            self.pipeline_script_path,
            '--config', self.config_path,
            '--work-dir', self.workspace_path,
            '--out-dir', self.pipeline_output_dir
        ]

        # Avvia il processo
        self.pipeline_process.start(python_executable, args)

        if not self.pipeline_process.waitForStarted(3000):
            self._log_message("ERROR: Failed to start pipeline process")
            self._on_pipeline_error("Failed to start pipeline process")

    def _on_process_finished(self, exit_code, exit_status):
        """Chiamato quando il processo termina."""
        if exit_code == 0 and exit_status == QProcess.ExitStatus.NormalExit:
            self._on_pipeline_finished()
        else:
            self._on_pipeline_error(f"Process exited with code {exit_code}")

    def _on_process_error(self, error):
        """Chiamato quando si verifica un errore nel processo."""
        error_messages = {
            QProcess.ProcessError.FailedToStart: "Failed to start process",
            QProcess.ProcessError.Crashed: "Process crashed",
            QProcess.ProcessError.Timedout: "Process timed out",
            QProcess.ProcessError.WriteError: "Write error",
            QProcess.ProcessError.ReadError: "Read error",
            QProcess.ProcessError.UnknownError: "Unknown error"
        }
        error_msg = error_messages.get(error, f"Process error: {error}")
        self._on_pipeline_error(error_msg)

    def _on_stdout_ready(self):
        """Chiamato quando ci sono dati pronti su stdout."""
        if self.pipeline_process:
            data = self.pipeline_process.readAllStandardOutput()
            output = data.data().decode('utf-8').strip()

            for line in output.split('\n'):
                if line.strip():
                    self._process_pipeline_output(line.strip())

    def _on_stderr_ready(self):
        """Chiamato quando ci sono dati pronti su stderr."""
        if self.pipeline_process:
            data = self.pipeline_process.readAllStandardError()
            error_output = data.data().decode('utf-8').strip()

            for line in error_output.split('\n'):
                if line.strip():
                    self._log_message(f"STDERR: {line.strip()}")

    def _process_pipeline_output(self, line):
        """Processa una riga di output dalla pipeline."""
        if line.startswith("LOG: "):
            message = line[5:]  # Rimuove "LOG: "
            self._log_message(message)
            self._update_current_operation(message)
        elif line.startswith("ERROR: "):
            error_msg = line[7:]  # Rimuove "ERROR: "
            self._log_message(f"ERROR: {error_msg}")
        elif line.startswith("PROGRESS: "):
            progress_info = line[10:]  # Rimuove "PROGRESS: "
            self._update_progress(progress_info)
        elif line.startswith("FINISHED: "):
            message = line[10:]  # Rimuove "FINISHED: "
            self._log_message(message)
        else:
            # Output generico
            self._log_message(line)

    def _update_progress(self, progress_info):
        """Aggiorna la barra di progresso basandosi sui dati ricevuti."""
        try:
            if '/' in progress_info:
                current, total = map(int, progress_info.split('/'))
                self.progress_bar.setValue(current)
                self.check_new_files()
        except ValueError:
            log.warning("Failed to update progress bar")
            pass  # Ignora se non riesco a parsare il progresso

    def _update_current_operation(self, message):
        """Aggiorna l'operazione corrente basandosi sul messaggio."""
        if "Starting pipeline" in message:
            self.current_operation.setText("Initializing pipeline...")
        elif "Processing patient" in message or "sub-" in message:
            patient_id = self._extract_patient_id_from_log(message)
            if patient_id:
                self.current_operation.setText(f"Processing patient: {patient_id}")
            else:
                self.current_operation.setText("Processing patient data...")
        elif "analysis" in message.lower():
            self.current_operation.setText("Performing statistical analysis...")
        elif "saving" in message.lower() or "csv" in message.lower():
            self.current_operation.setText("Saving results...")

    def _extract_patient_id_from_log(self, message):
        """Estrae l'ID del paziente dal messaggio di log."""
        import re
        match = re.search(r'sub-(\w+)', message)
        return f"sub-{match.group(1)}" if match else None

    def _on_pipeline_finished(self):
        """Chiamato quando la pipeline termina con successo."""
        self.pipeline_completed = True

        # Aggiorna UI per stato "completato"
        self.current_operation.setText("All patients processed successfully.")
        self.progress_bar.setValue(100)


        # Abilita i pulsanti appropriati
        self.stop_button.setEnabled(False)

        self._log_message("Pipeline execution completed successfully!")
        self._log_message(f"Results saved in: {self.pipeline_output_dir}")

        # Cleanup del processo
        self.pipeline_process = None

        self.context["update_main_buttons"]()

    def _on_pipeline_error(self, error_message):
        """Chiamato quando la pipeline termina con errore."""
        self.pipeline_error = error_message

        # Aggiorna UI per stato "errore"
        self.current_operation.setText("An error occurred during execution.")
        self.current_operation.setStyleSheet("""
            color: #c0392b;
            font-weight: bold;
        """)

        self.progress_bar.setColor("#c0392b")

        # Abilita i pulsanti appropriati
        self.stop_button.setEnabled(False)

        self._log_message(f"ERROR: {error_message}")

        # Cleanup del processo
        self.pipeline_process = None

        self.context["update_main_buttons"]()

    def _log_message(self, message):
        """Aggiunge un messaggio al log con timestamp."""
        from datetime import datetime
        timestamp = datetime.now().strftime("%H:%M:%S")
        formatted_message = f"[{timestamp}] {message}"
        self.log_text.append(formatted_message)

        # Auto-scroll to bottom
        scrollbar = self.log_text.verticalScrollBar()
        scrollbar.setValue(scrollbar.maximum())

    def _return_to_import(self):
        """Gestisce il click sul pulsante Back."""
        if self.pipeline_process and self.pipeline_process.state() == QProcess.ProcessState.Running:
            return  # Non permettere di tornare indietro durante l'esecuzione

        if self.context and "return_to_import" in self.context:
            self.context["return_to_import"]()

    def _on_stop_clicked(self):
        """Gestisce il click sul pulsante Stop."""
        if self.pipeline_process and self.pipeline_process.state() == QProcess.ProcessState.Running:
            self._log_message("Stopping pipeline...")

            # Prova prima una terminazione gentile
            self.pipeline_process.terminate()

            # Se non si ferma entro 5 secondi, forza la chiusura
            if not self.pipeline_process.waitForFinished(5000):
                self.pipeline_process.kill()
                self.pipeline_process.waitForFinished(3000)

            self._log_message("Pipeline stopped by user.")

            # Resetta UI
            self.current_operation.setText("Execution was interrupted by user.")
            self.progress_bar.setValue(0)

            self.stop_button.setEnabled(False)
            self.pipeline_process = None

            self.context["update_main_buttons"]()

    def on_enter(self):
        """Chiamato quando si entra nella pagina."""
        # Avvia automaticamente la pipeline quando si entra nella pagina
        if not self.pipeline_completed and self.pipeline_process is None:
            # Usa QTimer per avviare la pipeline dopo che l'UI è stata completamente renderizzata
            QTimer.singleShot(500, self._start_pipeline)

    def back(self):
        self.reset_page()
        if self.previous_page:
            self.previous_page.on_enter()
            return self.previous_page
        return None

    def is_ready_to_go_back(self):
        return self.pipeline_completed or self.pipeline_error is not None

    def is_ready_to_advance(self):
        return self.pipeline_completed or self.pipeline_error is not None

    def next(self, context):
        msg_box = QMessageBox()
        msg_box.setWindowTitle("Confirm")
        msg_box.setText("You want to return to the import page?")
        msg_box.setIcon(QMessageBox.Icon.Question)

        # Bottoni standard: OK e Cancel
        msg_box.setStandardButtons(QMessageBox.StandardButton.Ok | QMessageBox.StandardButton.Cancel)

        result = msg_box.exec()  # mostra la finestra modale

        if result == QMessageBox.StandardButton.Ok:
            self._return_to_import()
            return self.context["return_to_import"]()
        return None

    def get_sub_list(self,json_path: str) -> list:
        """
        Legge un file JSON e ritorna la lista dei 'sub' trovati.

        Args:
        json_path (str): percorso al file JSON

        Returns:
        list: lista delle chiavi tipo 'sub-XX'
        """
        with open(json_path, "r", encoding="utf-8") as f:
            data = json.load(f)

        # prendo tutte le chiavi che iniziano con "sub-"
        sub_list = [key for key in data.keys() if key.startswith("sub-")]
        return sub_list

    def check_new_files(self):
        for card in self.folder_cards.values():
            card.check_new_files()

    def reset_page(self):
        self.progress_bar.setValue(0)
        self.progress_bar.setColor("#3498DB")

        self.stop_button.setEnabled(False)

        self.current_operation.setText("Preparing to start...")
        self.current_operation.setStyleSheet("""
                    font-size: 13px;
                    color: #7f8c8d;
                    margin-top: 8px;
                """)

        self.log_text.clear()
        self.pipeline_process = None
        self.pipeline_error = None
        self.pipeline_completed = False



    def __del__(self):
        """Cleanup quando l'oggetto viene distrutto."""
        if self.pipeline_process and self.pipeline_process.state() == QProcess.ProcessState.Running:
            self.pipeline_process.kill()
            self.pipeline_process.waitForFinished(1000)
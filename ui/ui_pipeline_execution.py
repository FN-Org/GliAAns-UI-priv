import os
import json
import sys

from PyQt6.QtWidgets import (
    QWidget, QVBoxLayout, QLabel, QProgressBar, QPushButton,
    QTextEdit, QFrame, QHBoxLayout, QScrollArea
)
from PyQt6.QtCore import Qt, QTimer, pyqtSignal, QProcess
from wizard_state import WizardPage


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
        layout = QVBoxLayout(self)
        layout.setContentsMargins(20, 20, 20, 20)
        layout.setSpacing(15)

        # Header
        header = QLabel("Pipeline Execution")
        header.setStyleSheet("""
            font-size: 24px; 
            font-weight: bold; 
            color: #2c3e50;
            margin-bottom: 10px;
        """)
        header.setAlignment(Qt.AlignmentFlag.AlignCenter)
        layout.addWidget(header)

        # Subtitle con informazioni sul config
        config_info = QLabel(f"Processing configuration: {os.path.basename(self.config_path)}")
        config_info.setStyleSheet("""
            font-size: 14px; 
            color: #7f8c8d; 
            font-style: italic;
            margin-bottom: 15px;
        """)
        config_info.setAlignment(Qt.AlignmentFlag.AlignCenter)
        layout.addWidget(config_info)

        # Status frame
        self.status_frame = QFrame()
        self.status_frame.setStyleSheet("""
            QFrame {
                background-color: #ecf0f1;
                border: 2px solid #bdc3c7;
                border-radius: 10px;
                padding: 15px;
                margin: 10px 0px;
            }
        """)
        status_layout = QVBoxLayout(self.status_frame)

        # Status label
        self.status_label = QLabel("Initializing pipeline...")
        self.status_label.setStyleSheet("""
            font-size: 16px;
            font-weight: bold;
            color: #34495e;
            margin-bottom: 10px;
        """)
        self.status_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        status_layout.addWidget(self.status_label)

        # Progress bar
        self.progress_bar = QProgressBar()
        self.progress_bar.setMinimum(0)
        self.progress_bar.setMaximum(0)  # Indeterminate progress
        self.progress_bar.setStyleSheet("""
            QProgressBar {
                border: 2px solid #bdc3c7;
                border-radius: 8px;
                text-align: center;
                font-size: 12px;
                font-weight: bold;
                height: 25px;
            }
            QProgressBar::chunk {
                background-color: #3498db;
                border-radius: 6px;
            }
        """)
        status_layout.addWidget(self.progress_bar)

        # Current operation label
        self.current_operation = QLabel("Preparing to start...")
        self.current_operation.setStyleSheet("""
            font-size: 13px;
            color: #7f8c8d;
            margin-top: 8px;
        """)
        self.current_operation.setAlignment(Qt.AlignmentFlag.AlignCenter)
        status_layout.addWidget(self.current_operation)

        layout.addWidget(self.status_frame)

        # Log section
        log_label = QLabel("Execution Log:")
        log_label.setStyleSheet("""
            font-size: 16px;
            font-weight: bold;
            color: #2c3e50;
            margin-top: 15px;
            margin-bottom: 5px;
        """)
        layout.addWidget(log_label)

        # Log text area
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
        layout.addWidget(self.log_text)

        # Buttons frame
        button_frame = QFrame()
        button_layout = QHBoxLayout(button_frame)
        button_layout.setContentsMargins(0, 15, 0, 0)

        # Back button
        self.back_button = QPushButton("Back to Start")
        self.back_button.setStyleSheet("""
            QPushButton {
                font-size: 14px;
                font-weight: bold;
                background-color: #95a5a6;
                color: white;
                border-radius: 8px;
                padding: 10px 20px;
                min-width: 120px;
            }
            QPushButton:hover { 
                background-color: #7f8c8d; 
            }
            QPushButton:disabled {
                background-color: #bdc3c7;
                color: #7f8c8d;
            }
        """)
        self.back_button.clicked.connect(self._on_back_clicked)
        self.back_button.setEnabled(False)  # Disabilitato durante l'esecuzione

        # Stop button
        self.stop_button = QPushButton("Stop Pipeline")
        self.stop_button.setStyleSheet("""
            QPushButton {
                font-size: 14px;
                font-weight: bold;
                background-color: #e74c3c;
                color: white;
                border-radius: 8px;
                padding: 10px 20px;
                min-width: 120px;
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
        button_layout.addWidget(self.back_button)
        button_layout.addWidget(self.stop_button)
        button_layout.addStretch()

        layout.addWidget(button_frame)

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
        self.status_label.setText("Pipeline Running...")
        self.current_operation.setText("Processing patients...")
        self.progress_bar.setMaximum(0)  # Indeterminate
        self.stop_button.setEnabled(True)
        self.back_button.setEnabled(False)

        # Aggiorna lo stile del frame di stato
        self.status_frame.setStyleSheet("""
            QFrame {
                background-color: #e8f6f3;
                border: 2px solid #1abc9c;
                border-radius: 10px;
                padding: 15px;
                margin: 10px 0px;
            }
        """)

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
                self.progress_bar.setMaximum(total)
                self.progress_bar.setValue(current)
        except ValueError:
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
        self.status_label.setText("Pipeline Completed Successfully!")
        self.current_operation.setText("All patients processed successfully.")
        self.progress_bar.setMaximum(100)
        self.progress_bar.setValue(100)

        # Aggiorna lo stile del frame di stato
        self.status_frame.setStyleSheet("""
            QFrame {
                background-color: #eafaf1;
                border: 2px solid #27ae60;
                border-radius: 10px;
                padding: 15px;
                margin: 10px 0px;
            }
        """)

        # Abilita i pulsanti appropriati
        self.back_button.setEnabled(True)
        self.stop_button.setEnabled(False)

        self._log_message("Pipeline execution completed successfully!")
        self._log_message(f"Results saved in: {self.pipeline_output_dir}")

        # Cleanup del processo
        self.pipeline_process = None

    def _on_pipeline_error(self, error_message):
        """Chiamato quando la pipeline termina con errore."""
        self.pipeline_error = error_message

        # Aggiorna UI per stato "errore"
        self.status_label.setText("Pipeline Failed!")
        self.current_operation.setText("An error occurred during execution.")
        self.progress_bar.setMaximum(100)
        self.progress_bar.setValue(0)

        # Aggiorna lo stile del frame di stato
        self.status_frame.setStyleSheet("""
            QFrame {
                background-color: #fdeaea;
                border: 2px solid #e74c3c;
                border-radius: 10px;
                padding: 15px;
                margin: 10px 0px;
            }
        """)

        # Abilita i pulsanti appropriati
        self.back_button.setEnabled(True)
        self.stop_button.setEnabled(False)

        self._log_message(f"ERROR: {error_message}")

        # Cleanup del processo
        self.pipeline_process = None

    def _log_message(self, message):
        """Aggiunge un messaggio al log con timestamp."""
        from datetime import datetime
        timestamp = datetime.now().strftime("%H:%M:%S")
        formatted_message = f"[{timestamp}] {message}"
        self.log_text.append(formatted_message)

        # Auto-scroll to bottom
        scrollbar = self.log_text.verticalScrollBar()
        scrollbar.setValue(scrollbar.maximum())

    def _on_back_clicked(self):
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
            self.status_label.setText("Pipeline Stopped")
            self.current_operation.setText("Execution was interrupted by user.")
            self.progress_bar.setMaximum(100)
            self.progress_bar.setValue(0)

            # Aggiorna lo stile del frame di stato
            self.status_frame.setStyleSheet("""
                QFrame {
                    background-color: #fef9e7;
                    border: 2px solid #f39c12;
                    border-radius: 10px;
                    padding: 15px;
                    margin: 10px 0px;
                }
            """)

            self.back_button.setEnabled(True)
            self.stop_button.setEnabled(False)
            self.pipeline_process = None

    def on_enter(self):
        """Chiamato quando si entra nella pagina."""
        # Avvia automaticamente la pipeline quando si entra nella pagina
        if not self.pipeline_completed and self.pipeline_process is None:
            # Usa QTimer per avviare la pipeline dopo che l'UI è stata completamente renderizzata
            QTimer.singleShot(500, self._start_pipeline)

    def back(self):
        """Implementazione del metodo back per compatibilità."""
        pass

    def is_ready_to_go_back(self):
        return False

    def is_ready_to_advance(self):
        return self.pipeline_completed

    def next(self, context):
        """Implementazione del metodo next per compatibilità."""
        pass

    def __del__(self):
        """Cleanup quando l'oggetto viene distrutto."""
        if self.pipeline_process and self.pipeline_process.state() == QProcess.ProcessState.Running:
            self.pipeline_process.kill()
            self.pipeline_process.waitForFinished(1000)
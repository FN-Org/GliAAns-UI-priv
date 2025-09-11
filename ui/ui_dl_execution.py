import os
import re
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path
import ants
import numpy as np
from PyQt6 import QtWidgets, QtGui, QtCore
from PyQt6.QtGui import QIcon, QPixmap
from PyQt6.QtWidgets import (QWidget, QVBoxLayout, QLabel, QPushButton,
                             QScrollArea, QFrame, QGridLayout, QHBoxLayout,
                             QMessageBox, QGroupBox, QListWidget, QProgressBar,
                             QListWidgetItem, QTextEdit, QSplitter, QFileDialog,
                             QCheckBox)
from PyQt6.QtCore import Qt, QThread, pyqtSignal, QTimer, QProcess

from pediatric_fdopa_pipeline.utils import align, transform
from wizard_state import WizardPage
from logger import get_logger

# --- nuovi import per reorientazione ---
import nibabel as nib
from nibabel.orientations import aff2axcodes, io_orientation, ornt_transform, apply_orientation

log = get_logger()


class NIfTICoregistration:
    """Classe per la coregistrazione NIfTI con atlas usando ANTs"""

    def __init__(self, input_nifti, brain_nifti, atlas_path, output_dir, clobber=False, log_callback=None):
        self.output_dir = Path(output_dir)
        self.clobber = clobber
        self.log_callback = log_callback or (lambda x: print(x))

        # Crea la directory di output se non esiste
        self.output_dir.mkdir(parents=True, exist_ok=True)

        # Prefissi per i file di output
        input_basename = Path(input_nifti).stem.replace('.nii', '')
        self.prefix = str(self.output_dir / f"{input_basename}_")

        # File input
        self.mri = input_nifti       # MRI FLAIR scelta dal medico
        self.mri_str = brain_nifti   # Skull-stripped output di SynthStrip
        self.stx = atlas_path        # Atlas stereotassico

    def run_coregistration(self):
        """Esegue la registrazione MRI → Atlas (SyN) e ritorna i file di output"""
        self.log_callback("=== Avvio coregistrazione MRI → Atlas ===")

        # Esegue la registrazione
        stx_space_mri, mri_space_stx, stx2mri_tfm, mri2stx_tfm = align(
            fx=self.mri,
            mv=self.stx,
            transform_method='SyNAggro',
            outprefix=f'{self.prefix}_stx2mri_SyN_'
        )

        # Applica la trasformazione al brain mask skull-stripped
        brain_in_atlas = transform(
            prefix=self.prefix,
            fx=self.stx,
            mv=self.mri_str,
            tfm=mri2stx_tfm,
            clobber=self.clobber
        )

        # Applica la trasformazione alla MRI originale
        # mri_in_atlas = transform(
        #     prefix=self.prefix,
        #     fx=self.stx,
        #     mv=self.mri,
        #     tfm=mri2stx_tfm,
        #     clobber=self.clobber
        # )

        self.log_callback("✓ Coregistrazione completata")

        # Restituiamo tutti i path utili in un dizionario
        return {
            # "warped_moving": stx_space_mri,          # Atlas → MRI
            # "warped_fixed": mri_space_stx,           # MRI → Atlas
            # "forward_transform": stx2mri_tfm,     # file .h5 MRI<-Atlas
            # "inverse_transform": mri2stx_tfm,     # file .h5 Atlas<-MRI
            # "mri_in_atlas": mri_in_atlas,           # MRI allineata allo spazio atlas
            "brain_in_atlas": brain_in_atlas        # Brain mask allineata
        }

class SynthStripCoregistrationWorker(QThread):
    """Worker thread per processare file NIfTI con SynthStrip + Coregistrazione"""

    progress_updated = pyqtSignal(int)  # Progresso generale (0-100)
    file_progress_updated = pyqtSignal(str, str)  # (filename, status)
    log_updated = pyqtSignal(str)  # Messaggi di log
    finished = pyqtSignal(bool, str)  # (success, message)

    def __init__(self, input_files, workspace_path, atlas_path=None, enable_coregistration=True):
        super().__init__()
        self.output_dir = f"{workspace_path}/outputs"
        self.temp_dir = None
        self.coreg_results = None
        self.input_files = input_files
        self.atlas_path = atlas_path
        self.enable_coregistration = enable_coregistration
        self.is_cancelled = False

        self.dl_preprocess = QProcess(self)
        self.dl_process = QProcess(self)
        self.dl_postprocess = QProcess(self)

    def run(self):
        """Processa tutti i file NIfTI con SynthStrip + Coregistrazione"""
        try:
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
                message += f"Processati: {processed_files}/{total_files}\n"
                message += f"Falliti: {', '.join(failed_files)}"
                self.finished.emit(True, message)
            else:
                message = f"Tutti i {total_files} file processati con successo!"
                self.finished.emit(True, message)

        except Exception as e:
            log.error(f"Errore generale nel worker: {e}")
            self.finished.emit(False, f"Errore generale: {str(e)}")

    def process_single_file(self, input_file):
        """Processa un singolo file con SynthStrip + Coregistrazione + Reorientazione"""
        input_basename = os.path.basename(input_file)
        base_name = input_basename.replace('.nii.gz', '').replace('.nii', '')

        # cartella temporanea
        # self.temp_dir = tempfile.TemporaryDirectory()
        # self.output_dir = self.temp_dir.name  # tutte le fasi intermedie scrivono qui

        # === FASE 1: SKULL STRIPPING ===
        self.log_updated.emit(f"=== PROCESSAMENTO: {input_basename} ===")
        self.file_progress_updated.emit(input_basename, "🔄 Skull Stripping...")

        # Nome file skull stripped
        skull_stripped_file = os.path.join(self.output_dir, f"{base_name}_skull_stripped.nii.gz")

        if not os.path.exists(skull_stripped_file):
            if not self.run_synthstrip(input_file, skull_stripped_file):
                return False
        else:
            self.log_updated.emit(f"File skull-stripped già esistente: {os.path.basename(skull_stripped_file)}")

        # === FASE 2: COREGISTRAZIONE ===
        aligned_file = None
        if self.enable_coregistration and self.atlas_path and os.path.exists(self.atlas_path):
            self.file_progress_updated.emit(input_basename, "🔄 Coregistrazione...")

            if not self.run_coregistration(input_file, skull_stripped_file, input_basename):
                self.log_updated.emit(f"⚠️ Coregistrazione fallita per {input_basename}, ma skull stripping completato")
            else:
                # Recupera il file allineato dalla coregistrazione
                if hasattr(self, 'coreg_results') and self.coreg_results:
                    aligned_file = self.coreg_results.get("brain_in_atlas")
                    if aligned_file and os.path.exists(aligned_file):
                        self.file_progress_updated.emit(input_basename, "✓ Coregistrazione completata")
                        self.log_updated.emit(f"File allineato creato: {os.path.basename(aligned_file)}")
                    else:
                        self.log_updated.emit(f"⚠️ File allineato non trovato: {aligned_file}")
                        aligned_file = None

        # === FASE 3: RIORIENTAZIONE MATRICE AFFINE ===
        if aligned_file and os.path.exists(aligned_file):
            self.file_progress_updated.emit(input_basename, "🔄 Riorientazione...")

            if not self.run_reorientation(aligned_file, input_basename):
                self.log_updated.emit(f"⚠️ Riorientazione fallita per {input_basename}")
            else:
                self.file_progress_updated.emit(input_basename, "✓ Riorientazione completata")

        print("FASE 3 completata, entro in FASE 4&5")

        # === FASE 4: PREPARE & FASE 5: PREPROCESS ===
        data_path = os.path.join(self.output_dir, "reoriented")
        results_path = os.path.join(self.output_dir, "preprocess")

        # Connetti i segnali del processo
        # self.dl_preprocess.finished.connect(self._on_process_finished)
        # self.dl_preprocess.errorOccurred.connect(self._on_process_error)
        # self.dl_preprocess.readyReadStandardOutput.connect(self._on_stdout_ready)
        # self.dl_preprocess.readyReadStandardError.connect(self._on_stderr_ready)

        # Prepara gli argomenti per il processo
        python_executable = sys.executable  # Usa lo stesso interprete Python
        args = [
            "deep_learning/preprocess.py",
            '--data', data_path,
            '--results', results_path,
            '--ohe'
        ]

        # Avvia il processo
        self.dl_preprocess.start(python_executable, args)

        stdout = self.dl_preprocess.readAllStandardOutput().data().decode()
        stderr = self.dl_preprocess.readAllStandardError().data().decode()

        self.dl_preprocess.waitForFinished()

        print(f"[PREPROCESS STDOUT]\n{stdout}")
        print(f"[PREPROCESS STDERR]\n{stderr}")

        print("FASE 5 completata, entro in FASE 6")

        # === FASE 6: DEEP LEARNING ===

        args = [
            "deep_learning/deep_learning_runner.py",
            '--depth 6'
            '--filters 64 96 128 192 256 384 512',
            '--min_fmap 2',
            '--gpus 1',
            '--amp',
            '--save_preds',
            '--exec_mode predict',
            '--data', f'{self.output_dir}/preprocess/val_3d/test',
            '--ckpt_path', 'deep_learning/checkpoints/fold3/epoch=146-dice=88.05.ckpt',
            '--tta',
            '--ckpt_store_dir', f'{self.output_dir}/dl_results'
        ]

        self.dl_process.start(python_executable, args)

        self.dl_process.waitForFinished()

        # === FASE 7: POST PROCESS ===

        args = [
            "deep_learning/postprocess.py",
            '-i', f'{self.output_dir}/dl_results',
            '-o', '.workspace/outputs/nifti_dl_results'
        ]

        self.dl_postprocess.start(python_executable, args)
        self.dl_postprocess.waitForFinished()

        self.log_updated.emit(f"=== COMPLETATO: {input_basename} ===\n")
        return True

    def run_reorientation(self, brain_in_atlas_file, original_basename):
        """Esegue la riorientazione del file brain_in_atlas usando la matrice affine di BraTS"""
        try:
            self.log_updated.emit(f"Avvio riorientazione: {os.path.basename(brain_in_atlas_file)}")

            # Percorso del file BraTS di riferimento
            brats_reference_path = os.path.join("pediatric_fdopa_pipeline", "atlas", "BraTS-GLI-01-001.nii")

            # Verifica esistenza file BraTS di riferimento
            if not os.path.exists(brats_reference_path):
                self.log_updated.emit(f"⚠️ File BraTS di riferimento non trovato: {brats_reference_path}")
                return False

            # Carica il file brain_in_atlas (file da riorientare)
            my_img = nib.load(brain_in_atlas_file)

            # Carica il file BraTS di riferimento
            brats_img = nib.load(brats_reference_path)

            # Ottieni le matrici affini
            my_affine = my_img.affine
            brats_affine = brats_img.affine

            # Ottieni gli orientamenti
            my_ornt = io_orientation(my_affine)
            brats_ornt = io_orientation(brats_affine)

            self.log_updated.emit(f"Orientamento brain_in_atlas: {my_ornt}")
            self.log_updated.emit(f"Orientamento BraTS riferimento: {brats_ornt}")

            # Controlla se è necessaria la riorientazione
            if not (my_ornt == brats_ornt).all():
                self.log_updated.emit("Orientamenti diversi - eseguo riorientazione...")

                # Calcola la trasformazione necessaria
                transform = ornt_transform(my_ornt, brats_ornt)

                # Applica la riorientazione ai dati
                reoriented_data = apply_orientation(my_img.get_fdata(), transform)

                self.log_updated.emit("✓ Dati riorientati")
            else:
                reoriented_data = my_img.get_fdata()
                self.log_updated.emit("✓ Orientamento già coerente con BraTS")

            # Crea il nuovo file NIfTI con la matrice affine di BraTS
            reoriented_img = nib.Nifti1Image(reoriented_data, affine=brats_affine)

            # Determina il percorso di output per il file riorientato
            output_filename = f"{original_basename.replace('.nii.gz', '').replace('.nii', '')}_reoriented.nii.gz"
            reoriented_output_path = os.path.join(self.output_dir, "reoriented", output_filename)

            # Crea la directory se non esiste
            os.makedirs(os.path.dirname(reoriented_output_path), exist_ok=True)

            # Salva il file riorientato
            nib.save(reoriented_img, reoriented_output_path)

            self.log_updated.emit(f"✓ File riorientato salvato: {os.path.basename(reoriented_output_path)}")
            self.log_updated.emit(f"✓ Matrice affine BraTS applicata")

            # Verifica finale
            final_img = nib.load(reoriented_output_path)
            final_ornt = aff2axcodes(final_img.affine)
            brats_ornt_codes = aff2axcodes(brats_affine)

            self.log_updated.emit(f"Orientamento finale: {final_ornt}")
            self.log_updated.emit(f"Orientamento BraTS: {brats_ornt_codes}")

            # Verifica dimensioni
            final_shape = final_img.get_fdata().shape
            brats_shape = brats_img.get_fdata().shape
            self.log_updated.emit(f"Dimensioni file riorientato: {final_shape}")
            self.log_updated.emit(f"Dimensioni BraTS riferimento: {brats_shape}")

            return True

        except Exception as e:
            self.log_updated.emit(f"✗ Errore durante riorientazione: {str(e)}")
            import traceback
            self.log_updated.emit(f"Traceback: {traceback.format_exc()}")
            return False

    def run_synthstrip(self, input_file, output_file):
        """Esegue SynthStrip su un file"""
        self.log_updated.emit(f"Avvio SynthStrip: {os.path.basename(input_file)}")

        cmd = [
            "nipreps-synthstrip",
            "-i", input_file,
            "-o", output_file,
            "-g",
            "--model", "synthstrip.infant.1.pt"
        ]

        try:
            result = subprocess.run(cmd, capture_output=True, text=True)

            if result.stdout:
                self.log_updated.emit(f"SynthStrip stdout: {result.stdout}")
            if result.stderr:
                self.log_updated.emit(f"SynthStrip stderr: {result.stderr}")

            if result.returncode != 0:
                self.log_updated.emit(f"✗ SynthStrip fallito (code: {result.returncode})")
                return False

            if os.path.exists(output_file):
                self.log_updated.emit(f"✓ Skull stripping completato")
                return True
            else:
                self.log_updated.emit(f"✗ File di output non creato")
                return False

        except Exception as e:
            self.log_updated.emit(f"✗ Eccezione SynthStrip: {str(e)}")
            return False

    def run_coregistration(self, input_file, skull_stripped_file, original_basename):
        """Esegue coregistrazione con atlas"""
        try:
            self.log_updated.emit(f"Avvio coregistrazione: {os.path.basename(skull_stripped_file)}")

            # Crea directory per coregistrazione
            coreg_dir = os.path.join(self.output_dir, "coregistration")
            os.makedirs(coreg_dir, exist_ok=True)

            # Inizializza coregistrazione
            coregistration = NIfTICoregistration(
                input_nifti=input_file,
                brain_nifti=skull_stripped_file,
                atlas_path=self.atlas_path,
                output_dir=coreg_dir,
                clobber=False,
                log_callback=self.log_updated.emit
            )

            # Esegui coregistrazione
            self.coreg_results = coregistration.run_coregistration()

            self.log_updated.emit(f"✓ Coregistrazione completata per {original_basename}")
            return True

        except Exception as e:
            self.log_updated.emit(f"✗ Errore coregistrazione: {str(e)}")
            return False

    def cancel(self):
        """Cancella il processamento"""
        self.is_cancelled = True


class DlExecutionPage(WizardPage):
    """Pagina per SynthStrip + Coregistrazione dei file NIfTI selezionati"""

    def __init__(self, context=None, previous_page=None):
        super().__init__()
        self.context = context
        self.previous_page = previous_page
        self.next_page = None

        self.worker = None
        self.processing = False
        self.processing_completed = False

        # 🔹 Percorso atlas di default
        self.atlas_path = os.path.join("pediatric_fdopa_pipeline", "atlas", "T1.nii.gz")

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

        # 🔹 Disabilitiamo il pulsante (niente scelta manuale)
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

        # Configura directory di output
        if "workspace_path" in self.context:
            output_dir = os.path.join(self.context["workspace_path"], "outputs")
        else:
            output_dir = os.path.join(os.getcwd(), ".workspace", "outputs")

        # Avvia worker thread
        self.worker = SynthStripCoregistrationWorker(
            input_files=selected_files,
            workspace_path=self.context["workspace_path"],
            atlas_path=self.atlas_path if self.enable_coregistration.isChecked() else None,
            enable_coregistration=self.enable_coregistration.isChecked()
        )

        # Connetti segnali
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

        pipeline_type = "SynthStrip + Coregistrazione" if self.enable_coregistration.isChecked() else "Solo SynthStrip"
        log.info(f"Avviato processamento {pipeline_type} per {len(selected_files)} file")

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
        return None

    def is_ready_to_advance(self):
        """Controlla se è possibile andare alla pagina successiva"""
        return self.processing_completed and not self.processing

    def is_ready_to_go_back(self):
        """Controlla se è possibile tornare indietro"""
        return True

    def reset_page(self):
        """Resetta la pagina allo stato iniziale"""
        self.reset_processing_state()
        self.log_text.clear()
        self.files_list.clear()
        self.status_label.setText("Pronto per iniziare il processamento")
        self.atlas_path = None
        self.atlas_path_label.setText("Nessun atlas selezionato")
        self.atlas_path_label.setStyleSheet("color: gray; font-style: italic;")
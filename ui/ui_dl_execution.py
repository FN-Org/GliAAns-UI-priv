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
        self.mri = input_nifti  # MRI FLAIR scelta dal medico
        self.mri_str = brain_nifti  # Skull-stripped output di SynthStrip
        self.stx = atlas_path  # Atlas stereotassico

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

        self.log_callback("✓ Coregistrazione completata")

        # Restituiamo tutti i path utili in un dizionario
        return {
            "brain_in_atlas": brain_in_atlas  # Brain mask allineata
        }


class DlExecutionPage(WizardPage):
    """Pagina per SynthStrip + Coregistrazione dei file NIfTI selezionati"""

    def __init__(self, context=None, previous_page=None):
        super().__init__()
        self.context = context
        self.previous_page = previous_page
        self.next_page = None

        self.processing = False
        self.processing_completed = False
        self.is_cancelled = False

        # File processing state
        self.input_files = []
        self.current_file_index = 0
        self.processed_files = 0
        self.failed_files = []

        # Output directories
        self.output_dir = None
        self.coreg_results = None

        # QProcess instances
        self.synthstrip_process = None
        self.dl_preprocess = None
        self.dl_process = None
        self.dl_postprocess = None

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
        # self.cancel_button.clicked.connect(self.cancel_processing)
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

        # Inizializza stato processamento
        self.input_files = selected_files
        self.current_file_index = 0
        self.processed_files = 0
        self.failed_files = []
        self.is_cancelled = False

        # Configura directory di output
        if "workspace_path" in self.context:
            self.output_dir = os.path.join(self.context["workspace_path"], "outputs")
        else:
            self.output_dir = os.path.join(os.getcwd(), ".workspace", "outputs")

        os.makedirs(self.output_dir, exist_ok=True)

        # Aggiorna UI
        self.processing = True
        self.start_button.setVisible(False)
        self.cancel_button.setVisible(True)
        self.progress_bar.setVisible(True)
        self.progress_bar.setValue(0)
        self.status_label.setText("Processamento in corso...")
        self.log_text.clear()

        pipeline_type = "SynthStrip + Coregistrazione" if self.enable_coregistration.isChecked() else "Solo SynthStrip"
        self.add_log_message(f"Avviato processamento {pipeline_type} per {len(selected_files)} file")
        log.info(f"Avviato processamento {pipeline_type} per {len(selected_files)} file")

        # Inizia processamento del primo file
        self.process_next_file()

    def process_next_file(self):
        """Processa il prossimo file nella lista"""
        if self.is_cancelled:
            self.processing_finished(False, "Processamento cancellato dall'utente.")
            return

        if self.current_file_index >= len(self.input_files):
            # Tutti i file processati
            self.finalize_processing()
            return

        # Processa file corrente
        current_file = self.input_files[self.current_file_index]
        self.process_single_file(current_file)

    def process_single_file(self, input_file):
        """Processa un singolo file con SynthStrip + Coregistrazione + Reorientazione"""
        input_basename = os.path.basename(input_file)
        base_name = input_basename.replace('.nii.gz', '').replace('.nii', '')

        self.add_log_message(f"=== PROCESSAMENTO: {input_basename} ===")
        self.update_file_status(input_basename, "🔄 Skull Stripping...")

        # Nome file skull stripped
        self.current_skull_stripped_file = os.path.join(self.output_dir, f"{base_name}_skull_stripped.nii.gz")
        self.current_input_file = input_file
        self.current_basename = input_basename

        if os.path.exists(self.current_skull_stripped_file):
            self.add_log_message(
                f"File skull-stripped già esistente: {os.path.basename(self.current_skull_stripped_file)}")
            self.on_synthstrip_finished()
        else:
            self.run_synthstrip(input_file, self.current_skull_stripped_file)

    def run_synthstrip(self, input_file, output_file):
        """Esegue SynthStrip su un file"""
        self.add_log_message(f"Avvio SynthStrip: {os.path.basename(input_file)}")

        if self.synthstrip_process:
            self.synthstrip_process.kill()
            self.synthstrip_process = None

        self.synthstrip_process = QProcess(self)
        self.synthstrip_process.finished.connect(self.on_synthstrip_finished)
        self.synthstrip_process.errorOccurred.connect(self.on_synthstrip_error)
        self.synthstrip_process.readyReadStandardOutput.connect(self.on_synthstrip_stdout)
        self.synthstrip_process.readyReadStandardError.connect(self.on_synthstrip_stderr)

        cmd = [
            "nipreps-synthstrip",
            "-i", input_file,
            "-o", output_file,
            "-g",
            "--model", "synthstrip.infant.1.pt"
        ]

        self.synthstrip_process.start(cmd[0], cmd[1:])

    def on_synthstrip_stdout(self):
        """Gestisce stdout di SynthStrip"""
        if self.synthstrip_process:
            data = self.synthstrip_process.readAllStandardOutput()
            stdout = bytes(data).decode("utf8")
            if stdout.strip():
                self.add_log_message(f"SynthStrip stdout: {stdout.strip()}")

    def on_synthstrip_stderr(self):
        """Gestisce stderr di SynthStrip"""
        if self.synthstrip_process:
            data = self.synthstrip_process.readAllStandardError()
            stderr = bytes(data).decode("utf8")
            if stderr.strip():
                self.add_log_message(f"SynthStrip stderr: {stderr.strip()}")

    def on_synthstrip_error(self, error):
        """Gestisce errori del processo SynthStrip"""
        self.add_log_message(f"✗ Errore SynthStrip: {error}")
        self.mark_current_file_failed(f"Errore SynthStrip: {error}")

    def on_synthstrip_finished(self):
        """Chiamata quando SynthStrip termina"""
        if self.synthstrip_process and self.synthstrip_process.exitCode() != 0:
            self.add_log_message(f"✗ SynthStrip fallito (code: {self.synthstrip_process.exitCode()})")
            self.mark_current_file_failed(f"SynthStrip fallito")
            return

        if not os.path.exists(self.current_skull_stripped_file):
            self.add_log_message(f"✗ File di output non creato")
            self.mark_current_file_failed("File output non creato")
            return

        self.add_log_message(f"✓ Skull stripping completato")

        # Procedi con coregistrazione se abilitata
        if self.enable_coregistration.isChecked() and self.atlas_path and os.path.exists(self.atlas_path):
            self.update_file_status(self.current_basename, "🔄 Coregistrazione...")
            self.run_coregistration()
        else:
            # Salta direttamente alla riorientazione o termina
            self.on_coregistration_finished(True)

    def run_coregistration(self):
        """Esegue coregistrazione con atlas"""
        try:
            self.add_log_message(f"Avvio coregistrazione: {os.path.basename(self.current_skull_stripped_file)}")

            # Crea directory per coregistrazione
            coreg_dir = os.path.join(self.output_dir, "coregistration")
            os.makedirs(coreg_dir, exist_ok=True)

            # Inizializza coregistrazione
            coregistration = NIfTICoregistration(
                input_nifti=self.current_input_file,
                brain_nifti=self.current_skull_stripped_file,
                atlas_path=self.atlas_path,
                output_dir=coreg_dir,
                clobber=False,
                log_callback=self.add_log_message
            )

            # Esegui coregistrazione
            self.coreg_results = coregistration.run_coregistration()

            self.add_log_message(f"✓ Coregistrazione completata per {self.current_basename}")
            self.update_file_status(self.current_basename, "✓ Coregistrazione completata")
            self.on_coregistration_finished(True)

        except Exception as e:
            self.add_log_message(f"✗ Errore coregistrazione: {str(e)}")
            self.on_coregistration_finished(False)

    def on_coregistration_finished(self, success):
        """Chiamata quando la coregistrazione termina"""
        if success and self.coreg_results:
            aligned_file = self.coreg_results.get("brain_in_atlas")
            if aligned_file and os.path.exists(aligned_file):
                self.add_log_message(f"File allineato creato: {os.path.basename(aligned_file)}")
                self.run_reorientation(aligned_file)
            else:
                self.add_log_message(f"⚠️ File allineato non trovato: {aligned_file}")
                self.on_reorientation_finished(False)
        else:
            if self.enable_coregistration.isChecked():
                self.add_log_message(
                    f"⚠️ Coregistrazione fallita per {self.current_basename}, ma skull stripping completato")
            self.on_reorientation_finished(True)  # Continua anche se coregistrazione fallisce

    def run_reorientation(self, brain_in_atlas_file):
        """Esegue la riorientazione del file brain_in_atlas usando la matrice affine di BraTS"""
        try:
            self.update_file_status(self.current_basename, "🔄 Riorientazione...")
            self.add_log_message(f"Avvio riorientazione: {os.path.basename(brain_in_atlas_file)}")

            # Percorso del file BraTS di riferimento
            brats_reference_path = os.path.join("pediatric_fdopa_pipeline", "atlas", "BraTS-GLI-01-001.nii")

            # Verifica esistenza file BraTS di riferimento
            if not os.path.exists(brats_reference_path):
                self.add_log_message(f"⚠️ File BraTS di riferimento non trovato: {brats_reference_path}")
                self.on_reorientation_finished(False)
                return

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

            self.add_log_message(f"Orientamento brain_in_atlas: {my_ornt}")
            self.add_log_message(f"Orientamento BraTS riferimento: {brats_ornt}")

            # Controlla se è necessaria la riorientazione
            if not (my_ornt == brats_ornt).all():
                self.add_log_message("Orientamenti diversi - eseguo riorientazione...")

                # Calcola la trasformazione necessaria
                transform = ornt_transform(my_ornt, brats_ornt)

                # Applica la riorientazione ai dati
                reoriented_data = apply_orientation(my_img.get_fdata(), transform)

                self.add_log_message("✓ Dati riorientati")
            else:
                reoriented_data = my_img.get_fdata()
                self.add_log_message("✓ Orientamento già coerente con BraTS")

            # Crea il nuovo file NIfTI con la matrice affine di BraTS
            reoriented_img = nib.Nifti1Image(reoriented_data, affine=brats_affine)

            # Determina il percorso di output per il file riorientato
            output_filename = f"{self.current_basename.replace('.nii.gz', '').replace('.nii', '')}_reoriented.nii.gz"
            reoriented_output_path = os.path.join(self.output_dir, "reoriented", output_filename)

            # Crea la directory se non esiste
            os.makedirs(os.path.dirname(reoriented_output_path), exist_ok=True)

            # Salva il file riorientato
            nib.save(reoriented_img, reoriented_output_path)

            self.add_log_message(f"✓ File riorientato salvato: {os.path.basename(reoriented_output_path)}")
            self.add_log_message(f"✓ Matrice affine BraTS applicata")

            # Verifica finale
            final_img = nib.load(reoriented_output_path)
            final_ornt = aff2axcodes(final_img.affine)
            brats_ornt_codes = aff2axcodes(brats_affine)

            self.add_log_message(f"Orientamento finale: {final_ornt}")
            self.add_log_message(f"Orientamento BraTS: {brats_ornt_codes}")

            # Verifica dimensioni
            final_shape = final_img.get_fdata().shape
            brats_shape = brats_img.get_fdata().shape
            self.add_log_message(f"Dimensioni file riorientato: {final_shape}")
            self.add_log_message(f"Dimensioni BraTS riferimento: {brats_shape}")

            self.update_file_status(self.current_basename, "✓ Riorientazione completata")
            self.on_reorientation_finished(True)

        except Exception as e:
            self.add_log_message(f"✗ Errore durante riorientazione: {str(e)}")
            import traceback
            self.add_log_message(f"Traceback: {traceback.format_exc()}")
            self.on_reorientation_finished(False)

    def on_reorientation_finished(self, success):
        """Chiamata quando la riorientazione termina"""
        if not success:
            self.add_log_message(f"⚠️ Riorientazione fallita per {self.current_basename}")

        self.add_log_message("FASE 3 completata, entro in FASE 4&5")
        self.run_preprocess()

    def run_preprocess(self):
        """Esegue FASE 4: PREPARE & FASE 5: PREPROCESS"""
        self.update_file_status(self.current_basename, "🔄 Preprocessing...")

        data_path = os.path.join(self.output_dir, "reoriented")
        results_path = os.path.join(self.output_dir, "preprocess")

        if self.dl_preprocess:
            self.dl_preprocess.kill()
            self.dl_preprocess = None

        self.dl_preprocess = QProcess(self)
        self.dl_preprocess.finished.connect(self.on_preprocess_finished)
        self.dl_preprocess.errorOccurred.connect(self.on_preprocess_error)
        self.dl_preprocess.readyReadStandardOutput.connect(self.on_preprocess_stdout)
        self.dl_preprocess.readyReadStandardError.connect(self.on_preprocess_stderr)

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

    def on_preprocess_stdout(self):
        """Gestisce stdout del preprocess"""
        if self.dl_preprocess:
            data = self.dl_preprocess.readAllStandardOutput()
            stdout = bytes(data).decode("utf8")
            if stdout.strip():
                self.add_log_message(f"[PREPROCESS] {stdout.strip()}")

    def on_preprocess_stderr(self):
        """Gestisce stderr del preprocess"""
        if self.dl_preprocess:
            data = self.dl_preprocess.readAllStandardError()
            stderr = bytes(data).decode("utf8")
            if stderr.strip():
                self.add_log_message(f"[PREPROCESS ERROR] {stderr.strip()}")

    def on_preprocess_error(self, error):
        """Gestisce errori del processo preprocess"""
        self.add_log_message(f"✗ Errore preprocess: {error}")
        self.mark_current_file_failed(f"Errore preprocess: {error}")

    def on_preprocess_finished(self):
        """Chiamata quando il preprocess termina"""
        if self.dl_preprocess and self.dl_preprocess.exitCode() != 0:
            self.add_log_message(f"✗ Preprocess fallito (code: {self.dl_preprocess.exitCode()})")
            self.mark_current_file_failed("Preprocess fallito")
            return

        self.add_log_message("FASE 5 completata, entro in FASE 6")
        self.run_deep_learning()

    def run_deep_learning(self):
        """Esegue FASE 6: DEEP LEARNING"""
        self.update_file_status(self.current_basename, "🔄 Deep Learning...")

        if self.dl_process:
            self.dl_process.kill()
            self.dl_process = None

        self.dl_process = QProcess(self)
        self.dl_process.finished.connect(self.on_deep_learning_finished)
        self.dl_process.errorOccurred.connect(self.on_deep_learning_error)
        self.dl_process.readyReadStandardOutput.connect(self.on_deep_learning_stdout)
        self.dl_process.readyReadStandardError.connect(self.on_deep_learning_stderr)

        python_executable = sys.executable
        args = [
            "deep_learning/deep_learning_runner.py",
            '--depth', '6',
            '--filters', '64', '96', '128', '192', '256', '384', '512',
            '--min_fmap', '2',
            '--gpus', '1',
            '--amp',
            '--save_preds',
            '--exec_mode', 'predict',
            '--data', f'{self.output_dir}/preprocess/val_3d/test',
            '--ckpt_path', 'deep_learning/checkpoints/fold3/epoch=146-dice=88.05.ckpt',
            '--tta',
            '--results', f'{self.output_dir}/dl_results'
        ]

        self.dl_process.start(python_executable, args)

    def on_deep_learning_stdout(self):
        """Gestisce stdout del processo deep learning"""
        if self.dl_process:
            data = self.dl_process.readAllStandardOutput()
            stdout = bytes(data).decode("utf8")
            if stdout.strip():
                self.add_log_message(f"[DL] {stdout.strip()}")
                log.debug(f"[DL]  {stdout.strip()}")

    def on_deep_learning_stderr(self):
        """Gestisce stderr del processo deep learning"""
        if self.dl_process:
            data = self.dl_process.readAllStandardError()
            stderr = bytes(data).decode("utf8")
            if stderr.strip():
                self.add_log_message(f"[DL ERROR] {stderr.strip()}")
                log.error(f"[DL ERROR] {stderr.strip()}")

    def on_deep_learning_error(self, error):
        """Gestisce errori del processo deep learning"""
        self.add_log_message(f"✗ Errore Deep Learning: {error}")
        log.error(f"Errore Deep Learning: {error}")
        self.mark_current_file_failed(f"Errore Deep Learning: {error}")

    def on_deep_learning_finished(self):
        """Chiamata quando il processo deep learning termina"""
        if self.dl_process and self.dl_process.exitCode() != 0:
            self.add_log_message(f"✗ Deep Learning fallito (code: {self.dl_process.exitCode()})")
            self.mark_current_file_failed("Deep Learning fallito")
            return

        self.add_log_message("✓ Deep Learning completato con successo")
        self.update_file_status(self.current_basename, "✓ Deep Learning completato")

        # Avanza al prossimo file
        self.processed_files += 1
        self.current_file_index += 1

        progress = int((self.processed_files / len(self.input_files)) * 100)
        self.progress_bar.setValue(progress)

        self.run_postprocess()

    def run_postprocess(self):
        self.update_file_status(self.current_basename, "🔄 Deep Learning...")

        if self.dl_postprocess:
            self.dl_postprocess.kill()
            self.dl_postprocess = None

        self.dl_postprocess = QProcess(self)
        # self.dl_postprocess.finished.connect(self.on_deep_learning_finished)
        # self.dl_postprocess.errorOccurred.connect(self.on_deep_learning_error)
        # self.dl_postprocess.readyReadStandardOutput.connect(self.on_deep_learning_stdout)
        # self.dl_postprocess.readyReadStandardError.connect(self.on_deep_learning_stderr)

        python_executable = sys.executable
        args = [
            "deep_learning/postprocess.py",
            '-i', f'{self.output_dir}/dl_results/predictions_epoch=146-dice=88_05_task=train_fold=0_tta',
            '-o', f'{self.output_dir}/dl_postprocess'
        ]

        self.dl_postprocess.start(python_executable, args)

    def mark_current_file_failed(self, reason: str):
        """Segna il file corrente come fallito e passa al successivo"""
        # Aggiorna lista fallimenti
        self.failed_files.append(self.current_input_file)

        # Log
        self.add_log_message(f"✗ File fallito: {self.current_basename} → {reason}")

        # Aggiorna lo stato nella lista
        self.update_file_status(self.current_basename, f"✗ Fallito ({reason})")

        # Aggiorna progress bar e contatori
        self.current_file_index += 1
        self.processed_files += 1
        if self.input_files:
            progress = int((self.processed_files / len(self.input_files)) * 100)
            self.progress_bar.setValue(progress)

        # Continua con il prossimo file
        self.process_next_file()

    def finalize_processing(self):
        """Finalizza il processamento dopo che tutti i file sono stati gestiti"""
        self.processing = False
        self.processing_completed = True

        # Ripristina UI
        self.start_button.setVisible(True)
        self.start_button.setText("Rielabora File")
        self.cancel_button.setVisible(False)
        self.progress_bar.setValue(100)
        self.status_label.setStyleSheet("font-weight: bold; color: green;")

        # Log e stato finale
        if self.failed_files:
            self.status_label.setText("Processamento completato con errori ⚠️")
            self.add_log_message(f"⚠️ Alcuni file non sono stati processati correttamente: {len(self.failed_files)} falliti")
            for failed_file in self.failed_files:
                self.add_log_message(f"   ✗ {os.path.basename(failed_file)}")
            QMessageBox.warning(
                self,
                "Processamento completato con errori",
                f"Il processamento è terminato, ma {len(self.failed_files)} file non sono stati processati correttamente.\n"
                "Controlla il log per maggiori dettagli."
            )
        else:
            self.status_label.setText("✓ Processamento completato con successo")
            self.add_log_message("✓ Tutti i file sono stati processati correttamente")
            QMessageBox.information(
                self,
                "Processamento completato",
                "Tutti i file sono stati processati con successo 🎉"
            )

        log.info("Processamento finale completato")

    def add_log_message(self, message):
        """Aggiunge un messaggio al log"""
        timestamp = QtCore.QDateTime.currentDateTime().toString("hh:mm:ss")
        self.log_text.append(f"[{timestamp}] {message}")
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

    def reset_processing_state(self):
        """Resetta lo stato del processamento"""
        self.processing = False
        self.processing_completed = False
        self.start_button.setText("Avvia Processamento")
        self.start_button.setVisible(True)
        self.cancel_button.setVisible(False)
        self.progress_bar.setVisible(False)
        self.status_label.setStyleSheet("")
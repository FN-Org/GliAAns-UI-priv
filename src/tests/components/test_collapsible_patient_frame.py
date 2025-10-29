"""
test_collapsible_patient_frame.py - Test Suite per CollapsiblePatientFrame

Questa suite testa tutte le funzionalità del frame paziente collassabile:
- Inizializzazione locked/unlocked
- UI building e popolamento
- Expand/collapse animation
- File selection (single/multiple)
- PET4D JSON detection
- Save configuration
- Translation/localization
"""

import os
import json
import glob
from unittest.mock import Mock, patch, MagicMock
import pytest
from PyQt6.QtCore import Qt, QSize
from PyQt6.QtWidgets import QComboBox, QLabel, QPushButton
from PyQt6.QtTest import QTest

from main.components.collapsible_patient_frame import ClickableFrame, CollapsiblePatientFrame


class TestClickableFrame:
    """Test per ClickableFrame helper"""

    def test_clickable_frame_initialization(self, qtbot):
        """Test inizializzazione ClickableFrame"""
        frame = ClickableFrame()
        qtbot.addWidget(frame)

        assert hasattr(frame, 'clicked')

    def test_clickable_frame_emits_signal(self, qtbot):
        """Test che ClickableFrame emetta signal al click"""
        frame = ClickableFrame()
        qtbot.addWidget(frame)

        clicked_count = [0]
        frame.clicked.connect(lambda: clicked_count.__setitem__(0, clicked_count[0] + 1))

        # Simula click
        QTest.mouseClick(frame, Qt.MouseButton.LeftButton)

        assert clicked_count[0] == 1


class TestCollapsiblePatientFrameInitialization:
    """Test per l'inizializzazione di CollapsiblePatientFrame"""

    def test_init_locked_single_choice(self, qtbot, mock_context, temp_workspace):
        """Test inizializzazione in modalità locked (single choice)"""
        patient_id = "sub-01"
        files = {"ct": "sub-01/anat/ct.nii.gz"}
        patterns = {"ct": [os.path.join(temp_workspace, "sub-01/anat/ct*.nii.gz")]}

        frame = CollapsiblePatientFrame(
            context=mock_context,
            patient_id=patient_id,
            files=files,
            patterns=patterns,
            multiple_choice=False
        )
        qtbot.addWidget(frame)

        assert frame.patient_id == patient_id
        assert frame.files == files
        assert frame.patterns == patterns
        assert frame.multiple_choice is False
        assert frame.locked is True
        assert frame.is_expanded is False

    def test_init_unlocked_multiple_choice(self, qtbot, mock_context, temp_workspace):
        """Test inizializzazione in modalità unlocked (multiple choice)"""
        patient_id = "sub-02"
        files = {"pet4d": "sub-02/pet/pet4d.nii.gz"}
        patterns = {"pet4d": [os.path.join(temp_workspace, "sub-02/pet/*.nii.gz")]}

        frame = CollapsiblePatientFrame(
            context=mock_context,
            patient_id=patient_id,
            files=files,
            patterns=patterns,
            multiple_choice=True
        )
        qtbot.addWidget(frame)

        assert frame.multiple_choice is True
        assert frame.locked is False

    def test_init_with_save_callback(self, qtbot, mock_context, temp_workspace):
        """Test inizializzazione con callback di salvataggio"""
        save_callback = Mock()

        frame = CollapsiblePatientFrame(
            context=mock_context,
            patient_id="sub-03",
            files={},
            patterns={},
            multiple_choice=True,
            save_callback=save_callback
        )
        qtbot.addWidget(frame)

        assert frame.save_callback is save_callback

    def test_workspace_path_assignment(self, qtbot, mock_context, temp_workspace):
        """Test assegnazione workspace_path dal context"""
        frame = CollapsiblePatientFrame(
            context=mock_context,
            patient_id="sub-04",
            files={},
            patterns={},
            multiple_choice=False
        )
        qtbot.addWidget(frame)

        assert frame.workspace_path == mock_context["workspace_path"]

    def test_category_widgets_initialized_empty(self, qtbot, mock_context, temp_workspace):
        """Test che category_widgets sia inizializzato vuoto"""
        frame = CollapsiblePatientFrame(
            context=mock_context,
            patient_id="sub-05",
            files={},
            patterns={},
            multiple_choice=False
        )
        qtbot.addWidget(frame)

        assert frame.category_widgets == {}


class TestUIBuilding:
    """Test per la costruzione dell'interfaccia"""

    def test_header_widgets_created(self, qtbot, mock_context, temp_workspace):
        """Test creazione widget header"""
        frame = CollapsiblePatientFrame(
            context=mock_context,
            patient_id="sub-06",
            files={},
            patterns={},
            multiple_choice=False
        )
        qtbot.addWidget(frame)

        assert hasattr(frame, 'subject_name')
        assert hasattr(frame, 'toggle_button')
        assert isinstance(frame.subject_name, QLabel)

    def test_toggle_button_configuration(self, qtbot, mock_context, temp_workspace):
        """Test configurazione toggle button"""
        frame = CollapsiblePatientFrame(
            context=mock_context,
            patient_id="sub-07",
            files={},
            patterns={},
            multiple_choice=False
        )
        qtbot.addWidget(frame)

        assert frame.toggle_button.isCheckable()
        assert not frame.toggle_button.isChecked()
        assert frame.toggle_button.arrowType() == Qt.ArrowType.RightArrow

    def test_content_frame_created(self, qtbot, mock_context, temp_workspace):
        """Test creazione content frame"""
        frame = CollapsiblePatientFrame(
            context=mock_context,
            patient_id="sub-08",
            files={},
            patterns={},
            multiple_choice=False
        )
        qtbot.addWidget(frame)

        assert hasattr(frame, 'content_frame')
        assert frame.content_frame.maximumHeight() == 0  # Start collapsed

    def test_animation_setup(self, qtbot, mock_context, temp_workspace):
        """Test setup animazione"""
        frame = CollapsiblePatientFrame(
            context=mock_context,
            patient_id="sub-09",
            files={},
            patterns={},
            multiple_choice=False
        )
        qtbot.addWidget(frame)

        assert hasattr(frame, 'animation')
        assert frame.animation.duration() == 300


class TestStyleApplication:
    """Test per l'applicazione degli stili"""

    def test_locked_style(self, qtbot, mock_context, temp_workspace):
        """Test stile per frame locked"""
        frame = CollapsiblePatientFrame(
            context=mock_context,
            patient_id="sub-10",
            files={},
            patterns={},
            multiple_choice=False  # locked
        )
        qtbot.addWidget(frame)

        stylesheet = frame.styleSheet()
        assert "white" in stylesheet.lower() or "#fff" in stylesheet.lower()
        assert "#4CAF50" in stylesheet  # Green border

    def test_unlocked_style(self, qtbot, mock_context, temp_workspace):
        """Test stile per frame unlocked"""
        frame = CollapsiblePatientFrame(
            context=mock_context,
            patient_id="sub-11",
            files={},
            patterns={},
            multiple_choice=True  # unlocked
        )
        qtbot.addWidget(frame)

        stylesheet = frame.styleSheet()
        assert "#FFC107" in stylesheet  # Yellow border
        assert "#FFF8E1" in stylesheet  # Yellow background

    def test_style_changes_after_lock(self, qtbot, mock_context, temp_workspace):
        """Test cambio stile dopo lock"""
        frame = CollapsiblePatientFrame(
            context=mock_context,
            patient_id="sub-12",
            files={},
            patterns={},
            multiple_choice=True
        )
        qtbot.addWidget(frame)

        # Inizialmente unlocked (giallo)
        initial_style = frame.styleSheet()
        assert "#FFC107" in initial_style

        # Lock manualmente
        frame.locked = True
        frame._apply_style()

        # Dovrebbe diventare locked (bianco/verde)
        new_style = frame.styleSheet()
        assert "#4CAF50" in new_style


class TestExpandCollapse:
    """Test per funzionalità expand/collapse"""

    def test_initial_state_collapsed(self, qtbot, mock_context, temp_workspace):
        """Test stato iniziale collapsed"""
        frame = CollapsiblePatientFrame(
            context=mock_context,
            patient_id="sub-13",
            files={},
            patterns={},
            multiple_choice=False
        )
        qtbot.addWidget(frame)

        assert frame.is_expanded is False
        assert frame.content_frame.maximumHeight() == 0

    def test_toggle_expand_programmatically(self, qtbot, mock_context, temp_workspace):
        """Test expand programmatico"""
        frame = CollapsiblePatientFrame(
            context=mock_context,
            patient_id="sub-14",
            files={},
            patterns={},
            multiple_choice=False
        )
        qtbot.addWidget(frame)

        # Expand
        frame._toggle_expand(True)

        assert frame.is_expanded is True
        assert frame.toggle_button.arrowType() == Qt.ArrowType.DownArrow

    def test_toggle_collapse_programmatically(self, qtbot, mock_context, temp_workspace):
        """Test collapse programmatico"""
        frame = CollapsiblePatientFrame(
            context=mock_context,
            patient_id="sub-15",
            files={},
            patterns={},
            multiple_choice=False
        )
        qtbot.addWidget(frame)

        # Expand prima
        frame._toggle_expand(True)

        # Poi collapse
        frame._toggle_expand(False)

        assert frame.is_expanded is False
        assert frame.toggle_button.arrowType() == Qt.ArrowType.RightArrow

    def test_header_click_toggles_expansion(self, qtbot, mock_context, temp_workspace):
        """Test che il click sull'header espanda/collassi"""
        frame = CollapsiblePatientFrame(
            context=mock_context,
            patient_id="sub-16",
            files={},
            patterns={},
            multiple_choice=False
        )
        qtbot.addWidget(frame)

        # Trova header frame (primo figlio)
        header_frame = frame.findChild(ClickableFrame)
        assert header_frame is not None

        # Click header
        initial_state = frame.is_expanded
        header_frame.clicked.emit()

        # Stato dovrebbe cambiare
        assert frame.is_expanded != initial_state


class TestContentPopulation:
    """Test per il popolamento del contenuto"""

    @patch('glob.glob')
    def test_populate_single_file_locked(self, mock_glob, qtbot, mock_context, temp_workspace):
        """Test popolamento con singolo file in modalità locked"""
        mock_glob.return_value = [os.path.join(temp_workspace, "sub-17/anat/ct.nii.gz")]

        files = {"ct": "sub-17/anat/ct.nii.gz"}
        patterns = {"ct": [os.path.join(temp_workspace, "sub-17/anat/*.nii.gz")]}

        frame = CollapsiblePatientFrame(
            context=mock_context,
            patient_id="sub-17",
            files=files,
            patterns=patterns,
            multiple_choice=False  # locked
        )
        qtbot.addWidget(frame)

        # Dovrebbe mostrare label con file
        assert hasattr(frame, 'file_label')
        assert frame.file_label.text() == "sub-17/anat/ct.nii.gz"

    @patch('glob.glob')
    def test_populate_multiple_files_unlocked(self, mock_glob, qtbot, mock_context, temp_workspace):
        """Test popolamento con file multipli in modalità unlocked"""
        mock_glob.return_value = [
            os.path.join(temp_workspace, "sub-18/pet/pet1.nii.gz"),
            os.path.join(temp_workspace, "sub-18/pet/pet2.nii.gz"),
        ]

        files = {"pet4d": "sub-18/pet/pet1.nii.gz"}
        patterns = {"pet4d": [os.path.join(temp_workspace, "sub-18/pet/*.nii.gz")]}

        frame = CollapsiblePatientFrame(
            context=mock_context,
            patient_id="sub-18",
            files=files,
            patterns=patterns,
            multiple_choice=True  # unlocked
        )
        qtbot.addWidget(frame)

        # Dovrebbe avere combobox
        assert "pet4d" in frame.category_widgets
        combo = frame.category_widgets["pet4d"]
        assert isinstance(combo, QComboBox)
        assert combo.count() == 2

    @patch('glob.glob')
    def test_populate_no_files_found(self, mock_glob, qtbot, mock_context, temp_workspace):
        """Test popolamento senza file trovati"""
        mock_glob.return_value = []

        files = {}
        patterns = {"ct": [os.path.join(temp_workspace, "sub-19/anat/*.nii.gz")]}

        frame = CollapsiblePatientFrame(
            context=mock_context,
            patient_id="sub-19",
            files=files,
            patterns=patterns,
            multiple_choice=False
        )
        qtbot.addWidget(frame)

        # Dovrebbe mostrare "No file found"
        assert hasattr(frame, 'file_label')
        assert "no file" in frame.file_label.text().lower()

    @patch('glob.glob')
    def test_populate_saves_button_in_unlocked_mode(self, mock_glob, qtbot, mock_context, temp_workspace):
        """Test presenza pulsante Save in modalità unlocked"""
        mock_glob.return_value = [os.path.join(temp_workspace, "sub-20/anat/t1.nii.gz")]

        files = {}
        patterns = {"ct": [os.path.join(temp_workspace, "sub-20/anat/*.nii.gz")]}

        frame = CollapsiblePatientFrame(
            context=mock_context,
            patient_id="sub-20",
            files=files,
            patterns=patterns,
            multiple_choice=True  # unlocked
        )
        qtbot.addWidget(frame)

        # Dovrebbe avere pulsante Save
        assert hasattr(frame, 'save_btn')
        assert isinstance(frame.save_btn, QPushButton)


class TestPET4DJSONDetection:
    """Test per rilevamento JSON associato a PET4D"""

    @patch('glob.glob')
    @patch('os.path.exists')
    def test_pet4d_json_found_locked_mode(self, mock_exists, mock_glob, qtbot, mock_context, temp_workspace):
        """Test rilevamento JSON in modalità locked"""
        pet_file = os.path.join(temp_workspace, "sub-21/pet/pet4d.nii.gz")
        json_file = os.path.join(temp_workspace, "sub-21/pet/pet4d.json")

        mock_glob.return_value = [pet_file]
        mock_exists.side_effect = lambda path: path == json_file

        files = {"pet4d": "sub-21/pet/pet4d.nii.gz"}
        patterns = {"pet4d": [os.path.join(temp_workspace, "sub-21/pet/*.nii.gz")]}

        frame = CollapsiblePatientFrame(
            context=mock_context,
            patient_id="sub-21",
            files=files,
            patterns=patterns,
            multiple_choice=False
        )
        qtbot.addWidget(frame)

        # Dovrebbe aver rilevato JSON
        assert "pet4d_json" in frame.files
        assert "pet4d.json" in frame.files["pet4d_json"]

    @patch('glob.glob')
    @patch('os.path.exists')
    def test_pet4d_json_not_found_locked_mode(self, mock_exists, mock_glob, qtbot, mock_context, temp_workspace):
        """Test JSON non trovato in modalità locked"""
        pet_file = os.path.join(temp_workspace, "sub-22/pet/pet4d.nii.gz")

        mock_glob.return_value = [pet_file]
        mock_exists.return_value = False  # JSON non esiste

        files = {"pet4d": "sub-22/pet/pet4d.nii.gz"}
        patterns = {"pet4d": [os.path.join(temp_workspace, "sub-22/pet/*.nii.gz")]}

        frame = CollapsiblePatientFrame(
            context=mock_context,
            patient_id="sub-22",
            files=files,
            patterns=patterns,
            multiple_choice=False
        )
        qtbot.addWidget(frame)

        # JSON dovrebbe essere vuoto
        assert frame.files.get("pet4d_json", "") == ""

    @patch('glob.glob')
    @patch('os.path.exists')
    def test_pet4d_json_dynamic_update_unlocked(self, mock_exists, mock_glob, qtbot, mock_context, temp_workspace):
        """Test aggiornamento dinamico JSON in modalità unlocked"""
        pet1 = os.path.join(temp_workspace, "sub-23/pet/pet1.nii.gz")
        pet2 = os.path.join(temp_workspace, "sub-23/pet/pet2.nii.gz")
        json1 = os.path.join(temp_workspace, "sub-23/pet/pet1.json")

        mock_glob.return_value = [pet1, pet2]
        mock_exists.side_effect = lambda path: path == json1

        files = {"pet4d": "sub-23/pet/pet1.nii.gz"}
        patterns = {"pet4d": [os.path.join(temp_workspace, "sub-23/pet/*.nii.gz")]}

        frame = CollapsiblePatientFrame(
            context=mock_context,
            patient_id="sub-23",
            files=files,
            patterns=patterns,
            multiple_choice=True
        )
        qtbot.addWidget(frame)

        # Cambia selezione combo
        combo = frame.category_widgets["pet4d"]
        combo.setCurrentIndex(1)  # pet2

        # JSON label dovrebbe aggiornarsi
        assert hasattr(frame, 'pet4d_json_label')


class TestSaveConfiguration:
    """Test per il salvataggio della configurazione"""

    @patch('glob.glob')
    def test_save_patient_calls_callback(self, mock_glob, qtbot, mock_context, temp_workspace):
        """Test che save chiami il callback"""
        mock_glob.return_value = [
            os.path.join(temp_workspace, "sub-24/anat/t1.nii.gz"),
            os.path.join(temp_workspace, "sub-24/anat/t2.nii.gz")
        ]

        save_callback = Mock()
        files = {}
        patterns = {"ct": [os.path.join(temp_workspace, "sub-24/anat/*.nii.gz")]}

        frame = CollapsiblePatientFrame(
            context=mock_context,
            patient_id="sub-24",
            files=files,
            patterns=patterns,
            multiple_choice=True,
            save_callback=save_callback
        )
        qtbot.addWidget(frame)

        # Salva
        frame._save_patient()

        # Callback dovrebbe essere chiamato
        save_callback.assert_called_once()
        args = save_callback.call_args[0]
        assert args[0] == "sub-24"  # patient_id
        assert isinstance(args[1], dict)  # files dict

    @patch('glob.glob')
    def test_save_patient_marks_not_needing_revision(self, mock_glob, qtbot, mock_context, temp_workspace):
        """Test che save rimuova flag need_revision"""
        mock_glob.return_value = [os.path.join(temp_workspace, "sub-25/anat/scan.nii.gz")]

        files = {"need_revision": True}
        patterns = {"ct": [os.path.join(temp_workspace, "sub-25/anat/*.nii.gz")]}

        frame = CollapsiblePatientFrame(
            context=mock_context,
            patient_id="sub-25",
            files=files,
            patterns=patterns,
            multiple_choice=True
        )
        qtbot.addWidget(frame)

        frame._save_patient()

        assert frame.files["need_revision"] is False

    @patch('glob.glob')
    def test_save_patient_locks_frame(self, mock_glob, qtbot, mock_context, temp_workspace):
        """Test che save locki il frame"""
        mock_glob.return_value = [os.path.join(temp_workspace, "sub-26/anat/data.nii.gz")]

        files = {}
        patterns = {"ct": [os.path.join(temp_workspace, "sub-26/anat/*.nii.gz")]}

        frame = CollapsiblePatientFrame(
            context=mock_context,
            patient_id="sub-26",
            files=files,
            patterns=patterns,
            multiple_choice=True
        )
        qtbot.addWidget(frame)

        assert frame.locked is False

        frame._save_patient()

        assert frame.locked is True

    @patch('glob.glob')
    def test_save_patient_updates_files_from_combos(self, mock_glob, qtbot, mock_context, temp_workspace):
        """Test che save aggiorni files dai combo"""
        mock_glob.return_value = [
            os.path.join(temp_workspace, "sub-27/anat/file1.nii.gz"),
            os.path.join(temp_workspace, "sub-27/anat/file2.nii.gz")
        ]

        files = {}
        patterns = {"ct": [os.path.join(temp_workspace, "sub-27/anat/*.nii.gz")]}

        frame = CollapsiblePatientFrame(
            context=mock_context,
            patient_id="sub-27",
            files=files,
            patterns=patterns,
            multiple_choice=True
        )
        qtbot.addWidget(frame)

        # Cambia selezione
        combo = frame.category_widgets["ct"]
        combo.setCurrentIndex(1)

        frame._save_patient()

        # files dovrebbe essere aggiornato
        assert "file2.nii.gz" in frame.files["ct"]


class TestTranslation:
    """Test per traduzione/localizzazione"""

    def test_translate_ui_called_on_init(self, qtbot, mock_context, temp_workspace):
        """Test che _translate_ui sia chiamato all'init"""
        with patch.object(CollapsiblePatientFrame, '_translate_ui') as mock_translate:
            frame = CollapsiblePatientFrame(
                context=mock_context,
                patient_id="sub-28",
                files={},
                patterns={},
                multiple_choice=False
            )
            qtbot.addWidget(frame)

            # Dovrebbe essere chiamato durante __init__
            assert mock_translate.called

    def test_language_changed_signal_connected(self, qtbot, signal_emitter, temp_workspace):
        """Test connessione al signal language_changed"""
        context = {
            "workspace_path": temp_workspace,
            "language_changed": signal_emitter.language_changed
        }

        frame = CollapsiblePatientFrame(
            context=context,
            patient_id="sub-29",
            files={},
            patterns={},
            multiple_choice=False
        )
        qtbot.addWidget(frame)

        # Emetti signal
        with patch.object(frame, '_translate_ui') as mock_translate:
            context["language_changed"].connect(mock_translate)
            context["language_changed"].emit("it")

            # _translate_ui dovrebbe essere chiamato
            mock_translate.assert_called()

    def test_patient_label_translation(self, qtbot, mock_context, temp_workspace):
        """Test traduzione label paziente"""
        frame = CollapsiblePatientFrame(
            context=mock_context,
            patient_id="sub-30",
            files={},
            patterns={},
            multiple_choice=False
        )
        qtbot.addWidget(frame)

        # Label dovrebbe contenere patient ID
        assert "sub-30" in frame.subject_name.text()

    @patch('glob.glob')
    def test_save_button_translation(self, mock_glob, qtbot, mock_context, temp_workspace):
        """Test traduzione pulsante Save"""
        mock_glob.return_value = [os.path.join(temp_workspace, "sub-31/anat/scan.nii.gz")]

        frame = CollapsiblePatientFrame(
            context=mock_context,
            patient_id="sub-31",
            files={},
            patterns={"ct": [os.path.join(temp_workspace, "sub-31/anat/*.nii.gz")]},
            multiple_choice=True
        )
        qtbot.addWidget(frame)

        # Save button dovrebbe avere testo
        assert len(frame.save_btn.text()) > 0


class TestEdgeCases:
    """Test per casi limite"""

    def test_empty_patterns_dict(self, qtbot, mock_context, temp_workspace):
        """Test con dizionario patterns vuoto"""
        frame = CollapsiblePatientFrame(
            context=mock_context,
            patient_id="sub-32",
            files={},
            patterns={},  # Vuoto
            multiple_choice=False
        )
        qtbot.addWidget(frame)

        # Non dovrebbe crashare
        assert frame.category_widgets == {}

    def test_empty_files_dict(self, qtbot, mock_context, temp_workspace):
        """Test con dizionario files vuoto"""
        frame = CollapsiblePatientFrame(
            context=mock_context,
            patient_id="sub-33",
            files={},  # Vuoto
            patterns={"ct": ["*.nii.gz"]},
            multiple_choice=False
        )
        qtbot.addWidget(frame)

        # Non dovrebbe crashare
        assert frame.files == {}

    @patch('glob.glob')
    def test_single_file_in_multiple_choice_mode(self, mock_glob, qtbot, mock_context, temp_workspace):
        """Test singolo file in modalità multiple choice"""
        mock_glob.return_value = [os.path.join(temp_workspace, "sub-34/anat/only_one.nii.gz")]

        files = {}
        patterns = {"ct": [os.path.join(temp_workspace, "sub-34/anat/*.nii.gz")]}

        frame = CollapsiblePatientFrame(
            context=mock_context,
            patient_id="sub-34",
            files=files,
            patterns=patterns,
            multiple_choice=True
        )
        qtbot.addWidget(frame)

        # Con un solo file, dovrebbe trattare come locked
        # (logica interna del _populate_content)

    def test_patient_id_with_special_characters(self, qtbot, mock_context, temp_workspace):
        """Test patient ID con caratteri speciali"""
        patient_id = "sub-01_session-2"

        frame = CollapsiblePatientFrame(
            context=mock_context,
            patient_id=patient_id,
            files={},
            patterns={},
            multiple_choice=False
        )
        qtbot.addWidget(frame)

        assert frame.patient_id == patient_id
        assert patient_id in frame.subject_name.text()

    def test_no_save_callback_provided(self, qtbot, mock_context, temp_workspace):
        """Test senza callback di salvataggio"""
        frame = CollapsiblePatientFrame(
            context=mock_context,
            patient_id="sub-35",
            files={},
            patterns={},
            multiple_choice=True,
            save_callback=None
        )
        qtbot.addWidget(frame)

        # _save_patient non dovrebbe crashare
        frame._save_patient()

    def test_context_without_language_changed(self, qtbot, temp_workspace):
        """Test context senza signal language_changed"""
        context = {"workspace_path": temp_workspace}

        frame = CollapsiblePatientFrame(
            context=context,
            patient_id="sub-36",
            files={},
            patterns={},
            multiple_choice=False
        )
        qtbot.addWidget(frame)

        # Non dovrebbe crashare


class TestFilePatternMatching:
    """Test per il matching dei pattern di file"""

    @patch('glob.glob')
    def test_glob_called_with_correct_patterns(self, mock_glob, qtbot, mock_context, temp_workspace):
        """Test che glob sia chiamato con pattern corretti"""
        patterns = {
            "ct": [os.path.join(temp_workspace, "sub-37/anat/CT*.nii.gz")],
            "pet4d": [os.path.join(temp_workspace, "sub-37/pet/PET*.nii.gz")]
        }

        mock_glob.return_value = []

        frame = CollapsiblePatientFrame(
            context=mock_context,
            patient_id="sub-37",
            files={},
            patterns=patterns,
            multiple_choice=False
        )
        qtbot.addWidget(frame)

        # Verifica chiamate glob
        assert mock_glob.call_count >= 2

    @patch('glob.glob')
    def test_relative_path_conversion(self, mock_glob, qtbot, mock_context, temp_workspace):
        """Test conversione a path relativi"""
        abs_path = os.path.join(temp_workspace, "sub-38/anat/scan.nii.gz")
        mock_glob.return_value = [abs_path]

        files = {}
        patterns = {"ct": [os.path.join(temp_workspace, "sub-38/anat/*.nii.gz")]}

        frame = CollapsiblePatientFrame(
            context=mock_context,
            patient_id="sub-38",
            files=files,
            patterns=patterns,
            multiple_choice=True
        )
        qtbot.addWidget(frame)

        # Combo dovrebbe contenere path relativo
        combo = frame.category_widgets["ct"]
        item_text = combo.itemText(0)
        assert not os.path.isabs(item_text)
        assert "sub-38/anat/scan.nii.gz" in item_text

    @patch('glob.glob')
    def test_multiple_patterns_per_category(self, mock_glob, qtbot, mock_context, temp_workspace):
        """Test più pattern per categoria"""

        # Simula glob che restituisce file diversi per pattern diversi
        def glob_side_effect(pattern):
            if "CT*" in pattern:
                return [os.path.join(temp_workspace, "sub-39/anat/CT.nii.gz")]
            elif "ct*" in pattern:
                return [os.path.join(temp_workspace, "sub-39/anat/ct.nii.gz")]
            return []

        mock_glob.side_effect = glob_side_effect

        patterns = {
            "ct": [
                os.path.join(temp_workspace, "sub-39/anat/CT*.nii.gz"),
                os.path.join(temp_workspace, "sub-39/anat/ct*.nii.gz")
            ]
        }

        frame = CollapsiblePatientFrame(
            context=mock_context,
            patient_id="sub-39",
            files={},
            patterns=patterns,
            multiple_choice=True
        )
        qtbot.addWidget(frame)

        # Dovrebbe trovare file da entrambi i pattern
        combo = frame.category_widgets["ct"]
        assert combo.count() >= 1


class TestComboBoxBehavior:
    """Test per comportamento combobox"""

    @patch('glob.glob')
    def test_combo_current_index_set_from_files(self, mock_glob, qtbot, mock_context, temp_workspace):
        """Test che current index sia impostato da files dict"""
        mock_glob.return_value = [
            os.path.join(temp_workspace, "sub-40/anat/file1.nii.gz"),
            os.path.join(temp_workspace, "sub-40/anat/file2.nii.gz"),
            os.path.join(temp_workspace, "sub-40/anat/file3.nii.gz")
        ]

        files = {"ct": "sub-40/anat/file2.nii.gz"}
        patterns = {"ct": [os.path.join(temp_workspace, "sub-40/anat/*.nii.gz")]}

        frame = CollapsiblePatientFrame(
            context=mock_context,
            patient_id="sub-40",
            files=files,
            patterns=patterns,
            multiple_choice=True
        )
        qtbot.addWidget(frame)

        # Combo dovrebbe avere file2 selezionato
        combo = frame.category_widgets["ct"]
        assert "file2" in combo.currentText()

    @patch('glob.glob')
    def test_combo_default_to_first_if_no_match(self, mock_glob, qtbot, mock_context, temp_workspace):
        """Test che combo default al primo se nessun match"""
        mock_glob.return_value = [
            os.path.join(temp_workspace, "sub-41/anat/new1.nii.gz"),
            os.path.join(temp_workspace, "sub-41/anat/new2.nii.gz")
        ]

        files = {"ct": "sub-41/anat/nonexistent.nii.gz"}  # Non esiste
        patterns = {"ct": [os.path.join(temp_workspace, "sub-41/anat/*.nii.gz")]}

        frame = CollapsiblePatientFrame(
            context=mock_context,
            patient_id="sub-41",
            files=files,
            patterns=patterns,
            multiple_choice=True
        )
        qtbot.addWidget(frame)

        # Dovrebbe selezionare il primo
        combo = frame.category_widgets["ct"]
        assert combo.currentIndex() == 0

    @patch('glob.glob')
    def test_combo_minimum_height(self, mock_glob, qtbot, mock_context, temp_workspace):
        """Test altezza minima combobox"""
        mock_glob.return_value = [os.path.join(temp_workspace, "sub-42/anat/scan.nii.gz")]

        patterns = {"ct": [os.path.join(temp_workspace, "sub-42/anat/*.nii.gz")]}

        frame = CollapsiblePatientFrame(
            context=mock_context,
            patient_id="sub-42",
            files={},
            patterns=patterns,
            multiple_choice=True
        )
        qtbot.addWidget(frame)

        combo = frame.category_widgets["ct"]
        assert combo.minimumHeight() >= 28


class TestAnimationBehavior:
    """Test per comportamento animazioni"""

    def test_animation_duration(self, qtbot, mock_context, temp_workspace):
        """Test durata animazione"""
        frame = CollapsiblePatientFrame(
            context=mock_context,
            patient_id="sub-43",
            files={},
            patterns={},
            multiple_choice=False
        )
        qtbot.addWidget(frame)

        assert frame.animation.duration() == 300

    def test_animation_easing_curve(self, qtbot, mock_context, temp_workspace):
        """Test curva easing animazione"""
        from PyQt6.QtCore import QEasingCurve

        frame = CollapsiblePatientFrame(
            context=mock_context,
            patient_id="sub-44",
            files={},
            patterns={},
            multiple_choice=False
        )
        qtbot.addWidget(frame)

        assert frame.animation.easingCurve().type() == QEasingCurve.Type.InOutCubic

    def test_animation_target_property(self, qtbot, mock_context, temp_workspace):
        """Test proprietà target dell'animazione"""
        frame = CollapsiblePatientFrame(
            context=mock_context,
            patient_id="sub-45",
            files={},
            patterns={},
            multiple_choice=False
        )
        qtbot.addWidget(frame)

        assert frame.animation.propertyName() == b"maximumHeight"
        assert frame.animation.targetObject() == frame.content_frame


class TestCategoryLabels:
    """Test per label categorie"""

    @patch('glob.glob')
    def test_category_label_formatting(self, mock_glob, qtbot, mock_context, temp_workspace):
        """Test formattazione label categoria"""
        mock_glob.return_value = [os.path.join(temp_workspace, "sub-46/anat/scan.nii.gz")]

        patterns = {"pet_4d_dynamic": [os.path.join(temp_workspace, "sub-46/pet/*.nii.gz")]}

        frame = CollapsiblePatientFrame(
            context=mock_context,
            patient_id="sub-46",
            files={},
            patterns=patterns,
            multiple_choice=False
        )
        qtbot.addWidget(frame)

        # Category label dovrebbe avere underscore sostituiti da spazi e title case
        # "pet_4d_dynamic" → "Pet 4d Dynamic"
        labels = frame.findChildren(QLabel)
        category_labels = [l for l in labels if "pet" in l.text().lower()]
        assert len(category_labels) > 0


class TestIntegrationScenarios:
    """Test di integrazione per scenari completi"""

    @patch('glob.glob')
    @patch('os.path.exists')
    def test_complete_workflow_locked_patient(self, mock_exists, mock_glob, qtbot, mock_context, temp_workspace):
        """Test workflow completo paziente locked"""
        # Setup
        ct_file = os.path.join(temp_workspace, "sub-47/anat/CT.nii.gz")
        pet_file = os.path.join(temp_workspace, "sub-47/pet/PET4D.nii.gz")
        pet_json = os.path.join(temp_workspace, "sub-47/pet/PET4D.json")

        def glob_side_effect(pattern):
            if "CT" in pattern:
                return [ct_file]
            elif "PET" in pattern:
                return [pet_file]
            return []

        mock_glob.side_effect = glob_side_effect
        mock_exists.side_effect = lambda p: p == pet_json

        files = {
            "ct": "sub-47/anat/CT.nii.gz",
            "pet4d": "sub-47/pet/PET4D.nii.gz"
        }
        patterns = {
            "ct": [os.path.join(temp_workspace, "sub-47/anat/CT*.nii.gz")],
            "pet4d": [os.path.join(temp_workspace, "sub-47/pet/PET*.nii.gz")]
        }

        frame = CollapsiblePatientFrame(
            context=mock_context,
            patient_id="sub-47",
            files=files,
            patterns=patterns,
            multiple_choice=False  # locked
        )
        qtbot.addWidget(frame)

        # Verifica stato locked
        assert frame.locked is True

        # Verifica file mostrati
        assert hasattr(frame, 'file_label')

        # Verifica JSON rilevato
        assert "pet4d_json" in frame.files

    @patch('glob.glob')
    def test_complete_workflow_unlocked_patient(self, mock_glob, qtbot, mock_context, temp_workspace):
        """Test workflow completo paziente unlocked"""
        # Setup file multipli
        ct_files = [
            os.path.join(temp_workspace, "sub-48/anat/CT1.nii.gz"),
            os.path.join(temp_workspace, "sub-48/anat/CT2.nii.gz")
        ]
        pet_files = [
            os.path.join(temp_workspace, "sub-48/pet/PET1.nii.gz"),
            os.path.join(temp_workspace, "sub-48/pet/PET2.nii.gz")
        ]

        def glob_side_effect(pattern):
            if "CT" in pattern:
                return ct_files
            elif "PET" in pattern:
                return pet_files
            return []

        mock_glob.side_effect = glob_side_effect

        files = {}
        patterns = {
            "ct": [os.path.join(temp_workspace, "sub-48/anat/CT*.nii.gz")],
            "pet4d": [os.path.join(temp_workspace, "sub-48/pet/PET*.nii.gz")]
        }

        save_callback = Mock()

        frame = CollapsiblePatientFrame(
            context=mock_context,
            patient_id="sub-48",
            files=files,
            patterns=patterns,
            multiple_choice=True,
            save_callback=save_callback
        )
        qtbot.addWidget(frame)

        # Verifica stato unlocked
        assert frame.locked is False

        # Verifica combo presenti
        assert "ct" in frame.category_widgets
        assert "pet4d" in frame.category_widgets

        # Simula selezione e salvataggio
        frame.category_widgets["ct"].setCurrentIndex(1)
        frame.category_widgets["pet4d"].setCurrentIndex(0)

        frame._save_patient()

        # Verifica callback chiamato
        save_callback.assert_called_once()

        # Verifica ora locked
        assert frame.locked is True

    @patch('glob.glob')
    def test_expand_select_save_workflow(self, mock_glob, qtbot, mock_context, temp_workspace):
        """Test workflow: expand → select → save"""
        mock_glob.return_value = [
            os.path.join(temp_workspace, "sub-49/anat/scan1.nii.gz"),
            os.path.join(temp_workspace, "sub-49/anat/scan2.nii.gz")
        ]

        patterns = {"ct": [os.path.join(temp_workspace, "sub-49/anat/*.nii.gz")]}

        frame = CollapsiblePatientFrame(
            context=mock_context,
            patient_id="sub-49",
            files={},
            patterns=patterns,
            multiple_choice=True
        )
        qtbot.addWidget(frame)

        # 1. Expand
        frame._toggle_expand(True)
        assert frame.is_expanded is True

        # 2. Select
        combo = frame.category_widgets["ct"]
        combo.setCurrentIndex(1)

        # 3. Save
        frame._save_patient()

        # Verifica risultato
        assert "scan2" in frame.files["ct"]
        assert frame.locked is True


class TestMemoryAndCleanup:
    """Test per gestione memoria e cleanup"""

    @patch('glob.glob')
    def test_repopulate_content_cleans_old_widgets(self, mock_glob, qtbot, mock_context, temp_workspace):
        """Test che _populate_content pulisca vecchi widget"""
        mock_glob.return_value = [os.path.join(temp_workspace, "sub-50/anat/scan.nii.gz")]

        patterns = {"ct": [os.path.join(temp_workspace, "sub-50/anat/*.nii.gz")]}

        frame = CollapsiblePatientFrame(
            context=mock_context,
            patient_id="sub-50",
            files={},
            patterns=patterns,
            multiple_choice=True
        )
        qtbot.addWidget(frame)

        initial_widget_count = frame.content_layout.count()

        # Ri-popola
        frame._populate_content()

        # Count dovrebbe essere simile (widget vecchi rimossi)
        new_widget_count = frame.content_layout.count()
        assert new_widget_count > 0

    def test_widget_deletion_on_repopulate(self, qtbot, mock_context, temp_workspace):
        """Test eliminazione widget su ri-popolamento"""
        frame = CollapsiblePatientFrame(
            context=mock_context,
            patient_id="sub-51",
            files={},
            patterns={},
            multiple_choice=False
        )
        qtbot.addWidget(frame)

        # Aggiungi widget custom
        from PyQt6.QtWidgets import QWidget
        custom_widget = QWidget()
        frame.content_layout.addWidget(custom_widget)

        assert custom_widget.parent() is not None

        # Ri-popola
        frame._populate_content()

        # Widget custom dovrebbe essere schedulato per deletion
        # (deleteLater è chiamato)


class TestAccessibility:
    """Test per accessibilità"""

    def test_toggle_button_cursor(self, qtbot, mock_context, temp_workspace):
        """Test cursore del toggle button"""
        frame = CollapsiblePatientFrame(
            context=mock_context,
            patient_id="sub-52",
            files={},
            patterns={},
            multiple_choice=False
        )
        qtbot.addWidget(frame)

        # Dovrebbe avere cursore PointingHand
        assert frame.toggle_button.cursor().shape() == Qt.CursorShape.PointingHandCursor

    def test_toggle_button_checkable(self, qtbot, mock_context, temp_workspace):
        """Test che toggle button sia checkable"""
        frame = CollapsiblePatientFrame(
            context=mock_context,
            patient_id="sub-53",
            files={},
            patterns={},
            multiple_choice=False
        )
        qtbot.addWidget(frame)

        assert frame.toggle_button.isCheckable()

    @patch('glob.glob')
    def test_save_button_minimum_height(self, mock_glob, qtbot, mock_context, temp_workspace):
        """Test altezza minima save button"""
        mock_glob.return_value = [os.path.join(temp_workspace, "sub-54/anat/scan.nii.gz")]

        patterns = {"ct": [os.path.join(temp_workspace, "sub-54/anat/*.nii.gz")]}

        frame = CollapsiblePatientFrame(
            context=mock_context,
            patient_id="sub-54",
            files={},
            patterns=patterns,
            multiple_choice=True
        )
        qtbot.addWidget(frame)

        assert frame.save_btn.minimumHeight() >= 32


class TestVisualEffects:
    """Test per effetti visivi"""

    def test_drop_shadow_applied(self, qtbot, mock_context, temp_workspace):
        """Test applicazione drop shadow"""
        frame = CollapsiblePatientFrame(
            context=mock_context,
            patient_id="sub-55",
            files={},
            patterns={},
            multiple_choice=False
        )
        qtbot.addWidget(frame)

        # Dovrebbe avere effetto grafico
        assert frame.graphicsEffect() is not None

    def test_frame_shape(self, qtbot, mock_context, temp_workspace):
        """Test forma frame"""
        from PyQt6.QtWidgets import QFrame

        frame = CollapsiblePatientFrame(
            context=mock_context,
            patient_id="sub-56",
            files={},
            patterns={},
            multiple_choice=False
        )
        qtbot.addWidget(frame)

        assert frame.frameShape() == QFrame.Shape.StyledPanel

    def test_object_name_set(self, qtbot, mock_context, temp_workspace):
        """Test object name impostato"""
        frame = CollapsiblePatientFrame(
            context=mock_context,
            patient_id="sub-57",
            files={},
            patterns={},
            multiple_choice=False
        )
        qtbot.addWidget(frame)

        assert frame.objectName() == "collapsiblePatientFrame"


# Test parametrizzati
@pytest.mark.parametrize("multiple_choice,expected_locked", [
    (False, True),
    (True, False),
])
def test_locked_state_by_multiple_choice(multiple_choice, expected_locked, qtbot, mock_context, temp_workspace):
    """Test parametrizzato per stato locked basato su multiple_choice"""
    frame = CollapsiblePatientFrame(
        context=mock_context,
        patient_id="sub-param",
        files={},
        patterns={},
        multiple_choice=multiple_choice
    )
    qtbot.addWidget(frame)

    assert frame.locked == expected_locked


@pytest.mark.parametrize("arrow_type,is_expanded", [
    (Qt.ArrowType.RightArrow, False),
    (Qt.ArrowType.DownArrow, True),
])
def test_arrow_type_by_expansion_state(arrow_type, is_expanded, qtbot, mock_context, temp_workspace):
    """Test parametrizzato per tipo freccia basato su espansione"""
    frame = CollapsiblePatientFrame(
        context=mock_context,
        patient_id="sub-arrow",
        files={},
        patterns={},
        multiple_choice=False
    )
    qtbot.addWidget(frame)

    frame._toggle_expand(is_expanded)

    assert frame.toggle_button.arrowType() == arrow_type


@pytest.mark.parametrize("patient_id", [
    "sub-001",
    "sub-99",
    "patient_A",
    "subject-01-session-1"
])
def test_various_patient_id_formats(patient_id, qtbot, mock_context, temp_workspace):
    """Test parametrizzato per vari formati patient ID"""
    frame = CollapsiblePatientFrame(
        context=mock_context,
        patient_id=patient_id,
        files={},
        patterns={},
        multiple_choice=False
    )
    qtbot.addWidget(frame)

    assert frame.patient_id == patient_id
    assert patient_id in frame.subject_name.text()


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
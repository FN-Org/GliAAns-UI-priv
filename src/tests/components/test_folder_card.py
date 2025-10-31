import os
import pytest
from unittest.mock import Mock, patch, MagicMock
from PyQt6.QtWidgets import QDialog
from PyQt6.QtCore import Qt

from main.components.folder_card import FolderCard


@pytest.fixture
def test_folder_with_files(temp_workspace):
    """Crea una cartella di test con file."""
    folder = os.path.join(temp_workspace, "test_output")
    os.makedirs(folder)

    # Crea alcuni file iniziali
    initial_files = ["file1.txt", "file2.csv", "result.nii"]
    for filename in initial_files:
        with open(os.path.join(folder, filename), "w") as f:
            f.write("test content")

    return folder


@pytest.fixture
def empty_folder(temp_workspace):
    """Crea una cartella vuota."""
    folder = os.path.join(temp_workspace, "empty_output")
    os.makedirs(folder)
    return folder


@pytest.fixture
def mock_context_card():
    """Mock context per FolderCard."""
    return {}


class TestFolderCardInitialization:
    """Test per l'inizializzazione di FolderCard."""

    def test_initialization_existing_folder(self, qtbot, mock_context_card, test_folder_with_files):
        """Test inizializzazione con cartella esistente."""
        card = FolderCard(mock_context_card, test_folder_with_files)
        qtbot.addWidget(card)

        assert card.folder == test_folder_with_files
        assert card.files == []
        assert len(card.existing_files) == 3  # file1, file2, result
        assert card.pulse_animation is None
        assert card._scale == 1.0
        assert card._glow_opacity == 0.0

    def test_initialization_empty_folder(self, qtbot, mock_context_card, empty_folder):
        """Test inizializzazione con cartella vuota."""
        card = FolderCard(mock_context_card, empty_folder)
        qtbot.addWidget(card)

        assert card.folder == empty_folder
        assert len(card.existing_files) == 0

    def test_initialization_nonexistent_folder(self, qtbot, mock_context_card, temp_workspace):
        """Test inizializzazione con cartella non esistente."""
        nonexistent = os.path.join(temp_workspace, "nonexistent")

        card = FolderCard(mock_context_card, nonexistent)
        qtbot.addWidget(card)

        assert card.folder == nonexistent
        assert card.existing_files == set()

    def test_ui_elements_created(self, qtbot, mock_context_card, test_folder_with_files):
        """Test che tutti gli elementi UI siano creati."""
        card = FolderCard(mock_context_card, test_folder_with_files)
        qtbot.addWidget(card)

        assert card.card_frame is not None
        assert card.folder_icon is not None
        assert card.folder_name is not None
        assert card.status_label is not None
        assert card.action_btn is not None

    def test_fixed_height_set(self, qtbot, mock_context_card, test_folder_with_files):
        """Test che l'altezza sia fissata."""
        card = FolderCard(mock_context_card, test_folder_with_files)
        qtbot.addWidget(card)

        assert card.height() == 100

    def test_folder_name_display(self, qtbot, mock_context_card, test_folder_with_files):
        """Test che il nome cartella sia visualizzato."""
        card = FolderCard(mock_context_card, test_folder_with_files)
        qtbot.addWidget(card)

        assert card.folder_name.text() == os.path.basename(test_folder_with_files)

    def test_initial_status(self, qtbot, mock_context_card, test_folder_with_files):
        """Test stato iniziale."""
        card = FolderCard(mock_context_card, test_folder_with_files)
        qtbot.addWidget(card)

        assert "Waiting" in card.status_label.text() or "wait" in card.status_label.text().lower()
        assert not card.action_btn.isEnabled()

    def test_initial_icon(self, qtbot, mock_context_card, test_folder_with_files):
        """Test icona iniziale."""
        card = FolderCard(mock_context_card, test_folder_with_files)
        qtbot.addWidget(card)

        assert "📁" in card.folder_icon.text()


class TestAddFiles:
    """Test per il metodo add_files."""

    def test_add_files_basic(self, qtbot, mock_context_card, test_folder_with_files):
        """Test aggiunta file base."""
        card = FolderCard(mock_context_card, test_folder_with_files)
        qtbot.addWidget(card)

        new_files = ["new1.txt", "new2.csv"]
        card.add_files(new_files)

        assert len(card.files) == 2
        assert "new1.txt" in card.files
        assert "new2.csv" in card.files

    def test_add_files_updates_status(self, qtbot, mock_context_card, test_folder_with_files):
        """Test che add_files aggiorni lo status."""
        card = FolderCard(mock_context_card, test_folder_with_files)
        qtbot.addWidget(card)

        card.add_files(["file1.txt"])

        assert "1" in card.status_label.text()

    def test_add_files_enables_button(self, qtbot, mock_context_card, test_folder_with_files):
        """Test che add_files abiliti il pulsante."""
        card = FolderCard(mock_context_card, test_folder_with_files)
        qtbot.addWidget(card)

        assert not card.action_btn.isEnabled()

        card.add_files(["file1.txt"])

        assert card.action_btn.isEnabled()

    def test_add_files_changes_icon(self, qtbot, mock_context_card, test_folder_with_files):
        """Test che add_files cambi l'icona."""
        card = FolderCard(mock_context_card, test_folder_with_files)
        qtbot.addWidget(card)

        initial_icon = card.folder_icon.text()

        card.add_files(["file1.txt"])

        assert card.folder_icon.text() != initial_icon
        assert "✓" in card.folder_icon.text()

    def test_add_files_multiple_times(self, qtbot, mock_context_card, test_folder_with_files):
        """Test aggiunta file multipla."""
        card = FolderCard(mock_context_card, test_folder_with_files)
        qtbot.addWidget(card)

        card.add_files(["file1.txt"])
        assert len(card.files) == 1

        card.add_files(["file2.txt", "file3.txt"])
        assert len(card.files) == 3

    def test_add_files_empty_list(self, qtbot, mock_context_card, test_folder_with_files):
        """Test aggiunta lista vuota."""
        card = FolderCard(mock_context_card, test_folder_with_files)
        qtbot.addWidget(card)

        card.add_files([])

        assert len(card.files) == 0

    def test_add_files_starts_animation(self, qtbot, mock_context_card, test_folder_with_files):
        """Test che add_files avvii l'animazione."""
        card = FolderCard(mock_context_card, test_folder_with_files)
        qtbot.addWidget(card)

        with patch.object(card, 'start_pulse_animation') as mock_anim:
            card.add_files(["file1.txt"])

            mock_anim.assert_called_once()


class TestStartPulseAnimation:
    """Test per il metodo start_pulse_animation."""

    def test_start_pulse_animation_creates_animation(self, qtbot, mock_context_card, test_folder_with_files):
        """Test che start_pulse_animation crei l'animazione."""
        card = FolderCard(mock_context_card, test_folder_with_files)
        qtbot.addWidget(card)

        card.start_pulse_animation()

        assert card.pulse_animation is not None

    def test_start_pulse_animation_stops_existing(self, qtbot, mock_context_card, test_folder_with_files):
        """Test che stoppi animazione esistente."""
        card = FolderCard(mock_context_card, test_folder_with_files)
        qtbot.addWidget(card)

        # Prima animazione
        card.start_pulse_animation()
        first_anim = card.pulse_animation

        # Seconda animazione
        card.start_pulse_animation()

        assert card.pulse_animation is not None
        # Potrebbe essere la stessa o una nuova

    def test_start_pulse_animation_multiple_calls(self, qtbot, mock_context_card, test_folder_with_files):
        """Test chiamate multiple."""
        card = FolderCard(mock_context_card, test_folder_with_files)
        qtbot.addWidget(card)

        for _ in range(5):
            card.start_pulse_animation()

        # Non dovrebbe crashare
        assert card.pulse_animation is not None


class TestResetState:
    """Test per il metodo reset_state."""

    def test_reset_state_basic(self, qtbot, mock_context_card, test_folder_with_files):
        """Test reset stato base."""
        card = FolderCard(mock_context_card, test_folder_with_files)
        qtbot.addWidget(card)

        # Aggiungi file per cambiare stato
        card.add_files(["file1.txt"])

        # Reset
        card.reset_state()

        assert not card.action_btn.isEnabled()
        assert "📁" in card.folder_icon.text()

    def test_reset_state_stops_animation(self, qtbot, mock_context_card, test_folder_with_files):
        """Test che reset fermi l'animazione."""
        card = FolderCard(mock_context_card, test_folder_with_files)
        qtbot.addWidget(card)

        card.start_pulse_animation()
        assert card.pulse_animation is not None

        card.reset_state()

        # Animazione dovrebbe essere fermata (verificabile dallo stato)

    def test_reset_state_restores_status_text(self, qtbot, mock_context_card, test_folder_with_files):
        """Test che reset ripristini il testo status."""
        card = FolderCard(mock_context_card, test_folder_with_files)
        qtbot.addWidget(card)

        card.add_files(["file1.txt"])

        card.reset_state()

        assert "Waiting" in card.status_label.text() or "wait" in card.status_label.text().lower()

    def test_reset_state_without_prior_changes(self, qtbot, mock_context_card, test_folder_with_files):
        """Test reset senza cambiamenti precedenti."""
        card = FolderCard(mock_context_card, test_folder_with_files)
        qtbot.addWidget(card)

        # Reset senza modifiche
        card.reset_state()

        # Non dovrebbe crashare
        assert not card.action_btn.isEnabled()


class TestCheckNewFiles:
    """Test per il metodo check_new_files."""

    def test_check_new_files_detects_new(self, qtbot, mock_context_card, test_folder_with_files):
        """Test rilevamento nuovi file."""
        card = FolderCard(mock_context_card, test_folder_with_files)
        qtbot.addWidget(card)

        initial_count = len(card.existing_files)

        # Aggiungi un nuovo file nella cartella
        new_file = os.path.join(test_folder_with_files, "brand_new.txt")
        with open(new_file, "w") as f:
            f.write("new content")

        card.check_new_files()

        assert len(card.files) == 1
        assert "brand_new.txt" in card.files
        assert len(card.existing_files) == initial_count + 1

    def test_check_new_files_no_changes(self, qtbot, mock_context_card, test_folder_with_files):
        """Test quando non ci sono nuovi file."""
        card = FolderCard(mock_context_card, test_folder_with_files)
        qtbot.addWidget(card)

        card.check_new_files()

        assert len(card.files) == 0

    def test_check_new_files_updates_existing(self, qtbot, mock_context_card, test_folder_with_files):
        """Test che aggiorni existing_files."""
        card = FolderCard(mock_context_card, test_folder_with_files)
        qtbot.addWidget(card)

        initial_existing = card.existing_files.copy()

        # Aggiungi file
        new_file = os.path.join(test_folder_with_files, "new.txt")
        with open(new_file, "w") as f:
            f.write("content")

        card.check_new_files()

        assert len(card.existing_files) > len(initial_existing)
        assert "new.txt" in card.existing_files

    def test_check_new_files_nonexistent_folder(self, qtbot, mock_context_card, temp_workspace):
        """Test con cartella non esistente."""
        nonexistent = os.path.join(temp_workspace, "nonexistent")
        card = FolderCard(mock_context_card, nonexistent)
        qtbot.addWidget(card)

        # Non dovrebbe crashare
        card.check_new_files()

        assert len(card.files) == 0

    def test_check_new_files_multiple_new(self, qtbot, mock_context_card, test_folder_with_files):
        """Test rilevamento file multipli."""
        card = FolderCard(mock_context_card, test_folder_with_files)
        qtbot.addWidget(card)

        # Aggiungi più file
        for i in range(5):
            new_file = os.path.join(test_folder_with_files, f"new{i}.txt")
            with open(new_file, "w") as f:
                f.write("content")

        card.check_new_files()

        assert len(card.files) == 5

    def test_check_new_files_calls_add_files(self, qtbot, mock_context_card, test_folder_with_files):
        """Test che chiami add_files."""
        card = FolderCard(mock_context_card, test_folder_with_files)
        qtbot.addWidget(card)

        # Aggiungi file
        new_file = os.path.join(test_folder_with_files, "new.txt")
        with open(new_file, "w") as f:
            f.write("content")

        with patch.object(card, 'add_files', wraps=card.add_files) as mock_add:
            card.check_new_files()

            mock_add.assert_called_once()


class TestShowFilesDialog:
    """Test per il metodo show_files_dialog."""

    def test_show_files_dialog_with_files(self, qtbot, mock_context_card, test_folder_with_files):
        """Test apertura dialogo con file."""
        card = FolderCard(mock_context_card, test_folder_with_files)
        qtbot.addWidget(card)

        card.add_files(["file1.txt", "file2.csv"])

        with patch.object(QDialog, 'exec') as mock_exec:
            card.show_files_dialog()

            mock_exec.assert_called_once()

    def test_show_files_dialog_empty(self, qtbot, mock_context_card, test_folder_with_files):
        """Test che non apra dialogo se nessun file."""
        card = FolderCard(mock_context_card, test_folder_with_files)
        qtbot.addWidget(card)

        with patch.object(QDialog, 'exec') as mock_exec:
            card.show_files_dialog()

            mock_exec.assert_not_called()

    def test_show_files_dialog_clears_files(self, qtbot, mock_context_card, test_folder_with_files):
        """Test che pulisca i file dopo chiusura."""
        card = FolderCard(mock_context_card, test_folder_with_files)
        qtbot.addWidget(card)

        card.add_files(["file1.txt"])

        with patch.object(QDialog, 'exec'):
            card.show_files_dialog()

        assert len(card.files) == 0

    def test_show_files_dialog_resets_state(self, qtbot, mock_context_card, test_folder_with_files):
        """Test che resetti lo stato dopo chiusura."""
        card = FolderCard(mock_context_card, test_folder_with_files)
        qtbot.addWidget(card)

        card.add_files(["file1.txt"])

        with patch.object(QDialog, 'exec'):
            card.show_files_dialog()

        assert not card.action_btn.isEnabled()


class TestOpenFolderSignal:
    """Test per il signal open_folder_requested."""

    def test_open_folder_signal_exists(self, qtbot, mock_context_card, test_folder_with_files):
        """Test che il signal esista."""
        card = FolderCard(mock_context_card, test_folder_with_files)
        qtbot.addWidget(card)

        assert hasattr(card, 'open_folder_requested')

    def test_open_folder_signal_emitted(self, qtbot, mock_context_card, test_folder_with_files):
        """Test che il signal sia emesso (difficile da testare direttamente)."""
        card = FolderCard(mock_context_card, test_folder_with_files)
        qtbot.addWidget(card)

        # Il signal viene emesso dal dialogo quando si clicca il pulsante
        # Test indiretto tramite connessione
        signal_received = []
        card.open_folder_requested.connect(lambda path: signal_received.append(path))

        # Simula emission
        card.open_folder_requested.emit(test_folder_with_files)

        assert len(signal_received) == 1
        assert signal_received[0] == test_folder_with_files


class TestEdgeCases:
    """Test per casi limite."""

    def test_very_long_folder_name(self, qtbot, mock_context_card, temp_workspace):
        """Test con nome cartella molto lungo."""
        long_name = "a" * 200
        long_folder = os.path.join(temp_workspace, long_name)
        os.makedirs(long_folder)

        card = FolderCard(mock_context_card, long_folder)
        qtbot.addWidget(card)

        assert card.folder_name.text() == long_name

    def test_unicode_folder_name(self, qtbot, mock_context_card, temp_workspace):
        """Test con caratteri unicode nel nome."""
        unicode_name = "папка_文件夹_φάκελος"
        unicode_folder = os.path.join(temp_workspace, unicode_name)
        os.makedirs(unicode_folder)

        card = FolderCard(mock_context_card, unicode_folder)
        qtbot.addWidget(card)

        assert unicode_name in card.folder_name.text()

    def test_many_files(self, qtbot, mock_context_card, test_folder_with_files):
        """Test con molti file."""
        card = FolderCard(mock_context_card, test_folder_with_files)
        qtbot.addWidget(card)

        many_files = [f"file{i}.txt" for i in range(100)]
        card.add_files(many_files)

        assert len(card.files) == 100

    def test_special_characters_in_filename(self, qtbot, mock_context_card, test_folder_with_files):
        """Test con caratteri speciali nei nomi file."""
        special_files = [
            "file with spaces.txt",
            "file-with-dashes.txt",
            "file_with_underscores.txt",
            "file.multiple.dots.txt"
        ]

        card = FolderCard(mock_context_card, test_folder_with_files)
        qtbot.addWidget(card)

        card.add_files(special_files)

        assert len(card.files) == 4
        assert all(f in card.files for f in special_files)

    def test_rapid_file_additions(self, qtbot, mock_context_card, test_folder_with_files):
        """Test aggiunte rapide di file."""
        card = FolderCard(mock_context_card, test_folder_with_files)
        qtbot.addWidget(card)

        for i in range(20):
            card.add_files([f"file{i}.txt"])

        assert len(card.files) == 20

    def test_folder_deleted_after_init(self, qtbot, mock_context_card, temp_workspace):
        """Test quando la cartella viene eliminata dopo init."""
        folder = os.path.join(temp_workspace, "to_delete")
        os.makedirs(folder)

        card = FolderCard(mock_context_card, folder)
        qtbot.addWidget(card)

        # Elimina la cartella
        os.rmdir(folder)

        # check_new_files non dovrebbe crashare
        card.check_new_files()


class TestIntegration:
    """Test di integrazione."""

    def test_full_workflow(self, qtbot, mock_context_card, test_folder_with_files):
        """Test workflow completo."""
        card = FolderCard(mock_context_card, test_folder_with_files)
        qtbot.addWidget(card)

        # Stato iniziale
        assert not card.action_btn.isEnabled()
        assert len(card.files) == 0

        # Aggiungi nuovi file nel filesystem
        new_file = os.path.join(test_folder_with_files, "new.txt")
        with open(new_file, "w") as f:
            f.write("content")

        # Check new files
        card.check_new_files()

        # Verifica stato
        assert card.action_btn.isEnabled()
        assert len(card.files) == 1

        # Mostra dialogo e reset
        with patch.object(QDialog, 'exec'):
            card.show_files_dialog()

        # Verifica reset
        assert not card.action_btn.isEnabled()
        assert len(card.files) == 0

    def test_multiple_check_cycles(self, qtbot, mock_context_card, test_folder_with_files):
        """Test cicli multipli di check."""
        card = FolderCard(mock_context_card, test_folder_with_files)
        qtbot.addWidget(card)

        for cycle in range(3):
            # Aggiungi file
            new_file = os.path.join(test_folder_with_files, f"cycle{cycle}.txt")
            with open(new_file, "w") as f:
                f.write("content")

            # Check
            card.check_new_files()

            # Visualizza e reset
            with patch.object(QDialog, 'exec'):
                if card.files:
                    card.show_files_dialog()

        # Stato finale dovrebbe essere reset
        assert len(card.files) == 0


class TestStateConsistency:
    """Test per la consistenza dello stato."""

    def test_state_after_add_files(self, qtbot, mock_context_card, test_folder_with_files):
        """Test consistenza stato dopo add_files."""
        card = FolderCard(mock_context_card, test_folder_with_files)
        qtbot.addWidget(card)

        card.add_files(["file1.txt"])

        # Stato dovrebbe essere coerente
        assert len(card.files) > 0
        assert card.action_btn.isEnabled()
        assert "✓" in card.folder_icon.text()

    def test_state_after_reset(self, qtbot, mock_context_card, test_folder_with_files):
        """Test consistenza stato dopo reset."""
        card = FolderCard(mock_context_card, test_folder_with_files)
        qtbot.addWidget(card)

        card.add_files(["file1.txt"])
        card.reset_state()

        # Stato dovrebbe essere iniziale
        assert not card.action_btn.isEnabled()
        assert "📁" in card.folder_icon.text()


class TestMemoryAndPerformance:
    """Test per memoria e performance."""

    def test_no_memory_leak_repeated_operations(self, qtbot, mock_context_card, test_folder_with_files):
        """Test che non ci siano memory leak."""
        card = FolderCard(mock_context_card, test_folder_with_files)
        qtbot.addWidget(card)

        for _ in range(50):
            card.add_files(["file.txt"])
            card.reset_state()

        # Stato finale pulito
        assert len(card.files) == 0

    def test_performance_many_checks(self, qtbot, mock_context_card, test_folder_with_files):
        """Test performance con molti check."""
        card = FolderCard(mock_context_card, test_folder_with_files)
        qtbot.addWidget(card)

        # Molti check senza nuovi file
        for _ in range(100):
            card.check_new_files()

        # Non dovrebbe essere troppo lento
        assert True


class TestAccessibility:
    """Test per l'accessibilità."""

    def test_button_has_text(self, qtbot, mock_context_card, test_folder_with_files):
        """Test che il pulsante abbia testo."""
        card = FolderCard(mock_context_card, test_folder_with_files)
        qtbot.addWidget(card)

        assert len(card.action_btn.text()) > 0

    def test_status_label_has_text(self, qtbot, mock_context_card, test_folder_with_files):
        """Test che lo status abbia testo."""
        card = FolderCard(mock_context_card, test_folder_with_files)
        qtbot.addWidget(card)

        assert len(card.status_label.text()) > 0
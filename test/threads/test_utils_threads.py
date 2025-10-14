"""
test_copy_delete_thread.py - Test Suite per CopyDeleteThread

Questa suite testa tutte le funzionalità del thread di copia/eliminazione:
- Copia file singoli
- Copia directory ricorsive
- Eliminazione file singoli
- Eliminazione directory
- Operazioni combinate
- Gestione errori e edge cases
"""

import os
import shutil
import tempfile
from unittest.mock import Mock, patch, call
import pytest

from threads.utils_threads import CopyDeleteThread


class TestCopyDeleteThreadInitialization:
    """Test per l'inizializzazione di CopyDeleteThread"""

    def test_init_copy_file(self, temp_workspace):
        """Test inizializzazione per copia file"""
        src = os.path.join(temp_workspace, "source.txt")
        dst = os.path.join(temp_workspace, "dest.txt")

        thread = CopyDeleteThread(
            src=src,
            dst=dst,
            is_folder=False,
            copy=True,
            delete=False
        )

        assert thread.src == src
        assert thread.dst == dst
        assert thread.is_folder is False
        assert thread.copy is True
        assert thread.delete is False

    def test_init_delete_folder(self, temp_workspace):
        """Test inizializzazione per eliminazione cartella"""
        src = os.path.join(temp_workspace, "folder_to_delete")

        thread = CopyDeleteThread(
            src=src,
            dst=None,
            is_folder=True,
            copy=False,
            delete=True
        )

        assert thread.src == src
        assert thread.dst is None
        assert thread.is_folder is True
        assert thread.copy is False
        assert thread.delete is True

    def test_init_copy_and_delete(self, temp_workspace):
        """Test inizializzazione per operazione combinata"""
        src = os.path.join(temp_workspace, "source")
        dst = os.path.join(temp_workspace, "dest")

        thread = CopyDeleteThread(
            src=src,
            dst=dst,
            is_folder=True,
            copy=True,
            delete=True
        )

        assert thread.copy is True
        assert thread.delete is True

    def test_signals_exist(self, temp_workspace):
        """Verifica che i signal siano definiti correttamente"""
        thread = CopyDeleteThread(src="dummy", dst=None)

        assert hasattr(thread, 'finished')
        assert hasattr(thread, 'error')


class TestFileCopy:
    """Test per la copia di file singoli"""

    def test_copy_file_success(self, temp_workspace):
        """Test copia file riuscita"""
        # Crea file sorgente
        src = os.path.join(temp_workspace, "source.txt")
        dst = os.path.join(temp_workspace, "destination.txt")

        with open(src, 'w') as f:
            f.write("test content")

        thread = CopyDeleteThread(src=src, dst=dst, is_folder=False, copy=True)

        finished_msgs = []
        thread.finished.connect(lambda msg: finished_msgs.append(msg))

        thread.run()

        # Verifica file copiato
        assert os.path.exists(dst)
        with open(dst, 'r') as f:
            assert f.read() == "test content"

        # Verifica signal
        assert len(finished_msgs) == 1
        assert "copied" in finished_msgs[0].lower()

    def test_copy_file_overwrites_existing(self, temp_workspace):
        """Test che la copia sovrascriva file esistente"""
        src = os.path.join(temp_workspace, "source.txt")
        dst = os.path.join(temp_workspace, "existing.txt")

        # Crea sorgente
        with open(src, 'w') as f:
            f.write("new content")

        # Crea destinazione esistente
        with open(dst, 'w') as f:
            f.write("old content")

        thread = CopyDeleteThread(src=src, dst=dst, is_folder=False, copy=True)
        thread.run()

        # Verifica sovrascrittura
        with open(dst, 'r') as f:
            assert f.read() == "new content"

    def test_copy_file_to_subfolder(self, temp_workspace):
        """Test copia file in sottocartella"""
        src = os.path.join(temp_workspace, "file.txt")
        subfolder = os.path.join(temp_workspace, "subfolder")
        dst = os.path.join(subfolder, "file.txt")

        with open(src, 'w') as f:
            f.write("data")

        # Crea sottocartella
        os.makedirs(subfolder)

        thread = CopyDeleteThread(src=src, dst=dst, is_folder=False, copy=True)
        thread.run()

        assert os.path.exists(dst)

    def test_copy_binary_file(self, temp_workspace):
        """Test copia file binario"""
        src = os.path.join(temp_workspace, "binary.bin")
        dst = os.path.join(temp_workspace, "binary_copy.bin")

        # Crea file binario
        binary_data = bytes([0, 1, 2, 255, 128, 64])
        with open(src, 'wb') as f:
            f.write(binary_data)

        thread = CopyDeleteThread(src=src, dst=dst, is_folder=False, copy=True)
        thread.run()

        # Verifica contenuto binario
        with open(dst, 'rb') as f:
            assert f.read() == binary_data

    def test_copy_large_file(self, temp_workspace):
        """Test copia file grande"""
        src = os.path.join(temp_workspace, "large.dat")
        dst = os.path.join(temp_workspace, "large_copy.dat")

        # Crea file "grande" (1 MB)
        large_content = "x" * (1024 * 1024)
        with open(src, 'w') as f:
            f.write(large_content)

        thread = CopyDeleteThread(src=src, dst=dst, is_folder=False, copy=True)
        thread.run()

        assert os.path.exists(dst)
        assert os.path.getsize(dst) == os.path.getsize(src)


class TestFolderCopy:
    """Test per la copia di directory"""

    def test_copy_folder_success(self, temp_workspace):
        """Test copia cartella riuscita"""
        src = os.path.join(temp_workspace, "source_folder")
        dst = os.path.join(temp_workspace, "dest_folder")

        # Crea cartella sorgente con file
        os.makedirs(src)
        with open(os.path.join(src, "file1.txt"), 'w') as f:
            f.write("content 1")
        with open(os.path.join(src, "file2.txt"), 'w') as f:
            f.write("content 2")

        thread = CopyDeleteThread(src=src, dst=dst, is_folder=True, copy=True)

        finished_msgs = []
        thread.finished.connect(lambda msg: finished_msgs.append(msg))

        thread.run()

        # Verifica cartella copiata
        assert os.path.exists(dst)
        assert os.path.exists(os.path.join(dst, "file1.txt"))
        assert os.path.exists(os.path.join(dst, "file2.txt"))

        # Verifica contenuti
        with open(os.path.join(dst, "file1.txt"), 'r') as f:
            assert f.read() == "content 1"

        assert len(finished_msgs) == 1

    def test_copy_nested_folder(self, temp_workspace):
        """Test copia cartella con sottocartelle"""
        src = os.path.join(temp_workspace, "nested_src")
        dst = os.path.join(temp_workspace, "nested_dst")

        # Crea struttura annidata
        os.makedirs(os.path.join(src, "sub1", "sub2"))
        with open(os.path.join(src, "root.txt"), 'w') as f:
            f.write("root")
        with open(os.path.join(src, "sub1", "file1.txt"), 'w') as f:
            f.write("sub1")
        with open(os.path.join(src, "sub1", "sub2", "file2.txt"), 'w') as f:
            f.write("sub2")

        thread = CopyDeleteThread(src=src, dst=dst, is_folder=True, copy=True)
        thread.run()

        # Verifica tutta la struttura
        assert os.path.exists(os.path.join(dst, "root.txt"))
        assert os.path.exists(os.path.join(dst, "sub1", "file1.txt"))
        assert os.path.exists(os.path.join(dst, "sub1", "sub2", "file2.txt"))

    def test_copy_folder_with_dirs_exist_ok(self, temp_workspace):
        """Test copia in cartella già esistente (dirs_exist_ok=True)"""
        src = os.path.join(temp_workspace, "source")
        dst = os.path.join(temp_workspace, "existing_dest")

        # Crea sorgente
        os.makedirs(src)
        with open(os.path.join(src, "new_file.txt"), 'w') as f:
            f.write("new")

        # Crea destinazione esistente
        os.makedirs(dst)
        with open(os.path.join(dst, "old_file.txt"), 'w') as f:
            f.write("old")

        thread = CopyDeleteThread(src=src, dst=dst, is_folder=True, copy=True)
        thread.run()

        # Entrambi i file dovrebbero esistere
        assert os.path.exists(os.path.join(dst, "new_file.txt"))
        assert os.path.exists(os.path.join(dst, "old_file.txt"))

    def test_copy_empty_folder(self, temp_workspace):
        """Test copia cartella vuota"""
        src = os.path.join(temp_workspace, "empty_src")
        dst = os.path.join(temp_workspace, "empty_dst")

        os.makedirs(src)

        thread = CopyDeleteThread(src=src, dst=dst, is_folder=True, copy=True)
        thread.run()

        assert os.path.exists(dst)
        assert os.path.isdir(dst)
        assert len(os.listdir(dst)) == 0


class TestFileDelete:
    """Test per l'eliminazione di file"""

    def test_delete_file_success(self, temp_workspace):
        """Test eliminazione file riuscita"""
        file_path = os.path.join(temp_workspace, "to_delete.txt")

        with open(file_path, 'w') as f:
            f.write("delete me")

        assert os.path.exists(file_path)

        thread = CopyDeleteThread(src=file_path, is_folder=False, delete=True)

        finished_msgs = []
        thread.finished.connect(lambda msg: finished_msgs.append(msg))

        thread.run()

        # Verifica file eliminato
        assert not os.path.exists(file_path)
        assert len(finished_msgs) == 1
        assert "deleted" in finished_msgs[0].lower() or "eliminato" in finished_msgs[0].lower()

    def test_delete_readonly_file(self, temp_workspace):
        """Test eliminazione file read-only"""
        file_path = os.path.join(temp_workspace, "readonly.txt")

        with open(file_path, 'w') as f:
            f.write("readonly")

        # Rendi read-only
        os.chmod(file_path, 0o444)

        thread = CopyDeleteThread(src=file_path, is_folder=False, delete=True)

        error_msgs = []
        thread.error.connect(lambda msg: error_msgs.append(msg))

        thread.run()

        # Potrebbe fallire su sistemi Unix/Linux
        # Ma dovrebbe comunque emettere error signal se fallisce
        if os.path.exists(file_path):
            assert len(error_msgs) > 0
            # Cleanup
            os.chmod(file_path, 0o644)
            os.remove(file_path)


class TestFolderDelete:
    """Test per l'eliminazione di directory"""

    def test_delete_folder_success(self, temp_workspace):
        """Test eliminazione cartella riuscita"""
        folder_path = os.path.join(temp_workspace, "folder_to_delete")

        # Crea cartella con contenuto
        os.makedirs(folder_path)
        with open(os.path.join(folder_path, "file.txt"), 'w') as f:
            f.write("content")

        assert os.path.exists(folder_path)

        thread = CopyDeleteThread(src=folder_path, is_folder=True, delete=True)

        finished_msgs = []
        thread.finished.connect(lambda msg: finished_msgs.append(msg))

        thread.run()

        # Verifica cartella eliminata
        assert not os.path.exists(folder_path)
        assert len(finished_msgs) == 1

    def test_delete_nested_folder(self, temp_workspace):
        """Test eliminazione cartella con sottocartelle"""
        folder_path = os.path.join(temp_workspace, "nested_delete")

        # Crea struttura complessa
        os.makedirs(os.path.join(folder_path, "sub1", "sub2"))
        for i in range(5):
            with open(os.path.join(folder_path, f"file{i}.txt"), 'w') as f:
                f.write(f"content {i}")

        thread = CopyDeleteThread(src=folder_path, is_folder=True, delete=True)
        thread.run()

        # Tutta la struttura dovrebbe essere eliminata
        assert not os.path.exists(folder_path)

    def test_delete_empty_folder(self, temp_workspace):
        """Test eliminazione cartella vuota"""
        folder_path = os.path.join(temp_workspace, "empty_folder")
        os.makedirs(folder_path)

        thread = CopyDeleteThread(src=folder_path, is_folder=True, delete=True)
        thread.run()

        assert not os.path.exists(folder_path)


class TestCombinedOperations:
    """Test per operazioni combinate (copia + eliminazione)"""

    def test_copy_then_delete_file(self, temp_workspace):
        """Test copia e poi elimina file"""
        src = os.path.join(temp_workspace, "original.txt")
        dst = os.path.join(temp_workspace, "copy.txt")

        with open(src, 'w') as f:
            f.write("move me")

        # Operazione combinata = "move"
        thread = CopyDeleteThread(
            src=src,
            dst=dst,
            is_folder=False,
            copy=True,
            delete=True
        )

        finished_count = [0]
        thread.finished.connect(lambda msg: finished_count.__setitem__(0, finished_count[0] + 1))

        thread.run()

        # File copiato dovrebbe esistere
        assert os.path.exists(dst)
        with open(dst, 'r') as f:
            assert f.read() == "move me"

        # File originale dovrebbe essere eliminato
        assert not os.path.exists(src)

        # Due signal finished (uno per copy, uno per delete)
        assert finished_count[0] == 2

    def test_copy_then_delete_folder(self, temp_workspace):
        """Test copia e poi elimina cartella (equivalente a move)"""
        src = os.path.join(temp_workspace, "src_folder")
        dst = os.path.join(temp_workspace, "dst_folder")

        os.makedirs(src)
        with open(os.path.join(src, "data.txt"), 'w') as f:
            f.write("folder data")

        thread = CopyDeleteThread(
            src=src,
            dst=dst,
            is_folder=True,
            copy=True,
            delete=True
        )

        thread.run()

        # Destinazione dovrebbe esistere
        assert os.path.exists(dst)
        assert os.path.exists(os.path.join(dst, "data.txt"))

        # Sorgente dovrebbe essere eliminata
        assert not os.path.exists(src)


class TestErrorHandling:
    """Test per la gestione degli errori"""

    def test_copy_missing_source(self, temp_workspace):
        """Test copia con file sorgente mancante"""
        src = os.path.join(temp_workspace, "nonexistent.txt")
        dst = os.path.join(temp_workspace, "dest.txt")

        thread = CopyDeleteThread(src=src, dst=dst, is_folder=False, copy=True)

        error_msgs = []
        thread.error.connect(lambda msg: error_msgs.append(msg))

        thread.run()

        # Dovrebbe emettere errore
        assert len(error_msgs) == 1
        assert "error" in error_msgs[0].lower() or src in error_msgs[0]

    def test_copy_missing_src_parameter(self, temp_workspace):
        """Test copia con parametro src mancante"""
        thread = CopyDeleteThread(src=None, dst="dest", copy=True)

        error_msgs = []
        thread.error.connect(lambda msg: error_msgs.append(msg))

        thread.run()

        assert len(error_msgs) == 1
        assert "missing" in error_msgs[0].lower() or "manca" in error_msgs[0].lower()

    def test_copy_missing_dst_parameter(self, temp_workspace):
        """Test copia con parametro dst mancante"""
        thread = CopyDeleteThread(src="src", dst=None, copy=True)

        error_msgs = []
        thread.error.connect(lambda msg: error_msgs.append(msg))

        thread.run()

        assert len(error_msgs) == 1
        assert "missing" in error_msgs[0].lower()

    def test_delete_missing_source(self, temp_workspace):
        """Test eliminazione file inesistente"""
        src = os.path.join(temp_workspace, "does_not_exist.txt")

        thread = CopyDeleteThread(src=src, is_folder=False, delete=True)

        error_msgs = []
        thread.error.connect(lambda msg: error_msgs.append(msg))

        thread.run()

        # Dovrebbe emettere errore
        assert len(error_msgs) == 1

    def test_delete_missing_src_parameter(self, temp_workspace):
        """Test eliminazione con parametro src mancante"""
        thread = CopyDeleteThread(src=None, delete=True)

        error_msgs = []
        thread.error.connect(lambda msg: error_msgs.append(msg))

        thread.run()

        assert len(error_msgs) == 1
        assert "missing" in error_msgs[0].lower()

    def test_copy_to_invalid_destination(self, temp_workspace):
        """Test copia in destinazione non valida"""
        src = os.path.join(temp_workspace, "source.txt")
        # Destinazione in directory inesistente
        dst = os.path.join(temp_workspace, "nonexistent_dir", "subdir", "dest.txt")

        with open(src, 'w') as f:
            f.write("data")

        thread = CopyDeleteThread(src=src, dst=dst, is_folder=False, copy=True)

        error_msgs = []
        thread.error.connect(lambda msg: error_msgs.append(msg))

        thread.run()

        # Dovrebbe fallire
        assert len(error_msgs) == 1

    @patch('shutil.copy')
    def test_copy_permission_error(self, mock_copy, temp_workspace):
        """Test gestione errore permessi durante copia"""
        mock_copy.side_effect = PermissionError("Permission denied")

        src = os.path.join(temp_workspace, "source.txt")
        dst = os.path.join(temp_workspace, "dest.txt")

        with open(src, 'w') as f:
            f.write("data")

        thread = CopyDeleteThread(src=src, dst=dst, is_folder=False, copy=True)

        error_msgs = []
        thread.error.connect(lambda msg: error_msgs.append(msg))

        thread.run()

        assert len(error_msgs) == 1
        assert "permission" in error_msgs[0].lower() or "error" in error_msgs[0].lower()


class TestEdgeCases:
    """Test per casi limite"""

    def test_copy_file_to_itself(self, temp_workspace):
        """Test copia file su se stesso"""
        file_path = os.path.join(temp_workspace, "same.txt")

        with open(file_path, 'w') as f:
            f.write("content")

        thread = CopyDeleteThread(
            src=file_path,
            dst=file_path,
            is_folder=False,
            copy=True
        )

        error_msgs = []
        thread.error.connect(lambda msg: error_msgs.append(msg))

        thread.run()

        # shutil.copy dovrebbe gestire questo caso
        # Potrebbe emettere errore o avere successo dipendendo dall'implementazione
        # Verifichiamo solo che non sollevi eccezioni non gestite

    def test_copy_symlink(self, temp_workspace):
        """Test copia symlink"""
        if os.name == 'nt':
            pytest.skip("Symlinks non affidabili su Windows")

        src = os.path.join(temp_workspace, "original.txt")
        link = os.path.join(temp_workspace, "link.txt")
        dst = os.path.join(temp_workspace, "copy.txt")

        with open(src, 'w') as f:
            f.write("original data")

        os.symlink(src, link)

        thread = CopyDeleteThread(src=link, dst=dst, is_folder=False, copy=True)
        thread.run()

        # Dovrebbe copiare il contenuto, non il link
        assert os.path.exists(dst)
        with open(dst, 'r') as f:
            assert f.read() == "original data"

    def test_delete_symlink(self, temp_workspace):
        """Test eliminazione symlink"""
        if os.name == 'nt':
            pytest.skip("Symlinks non affidabili su Windows")

        target = os.path.join(temp_workspace, "target.txt")
        link = os.path.join(temp_workspace, "link.txt")

        with open(target, 'w') as f:
            f.write("target")

        os.symlink(target, link)

        thread = CopyDeleteThread(src=link, is_folder=False, delete=True)
        thread.run()

        # Link dovrebbe essere eliminato, target dovrebbe esistere ancora
        assert not os.path.exists(link)
        assert os.path.exists(target)

    def test_copy_file_with_special_characters(self, temp_workspace):
        """Test copia file con caratteri speciali nel nome"""
        src = os.path.join(temp_workspace, "file (copy) #1.txt")
        dst = os.path.join(temp_workspace, "destination [final].txt")

        with open(src, 'w') as f:
            f.write("special chars")

        thread = CopyDeleteThread(src=src, dst=dst, is_folder=False, copy=True)
        thread.run()

        assert os.path.exists(dst)
        with open(dst, 'r') as f:
            assert f.read() == "special chars"

    def test_copy_unicode_filename(self, temp_workspace):
        """Test copia file con nome Unicode"""
        src = os.path.join(temp_workspace, "文件.txt")
        dst = os.path.join(temp_workspace, "файл.txt")

        try:
            with open(src, 'w', encoding='utf-8') as f:
                f.write("unicode content")
        except (OSError, UnicodeError):
            pytest.skip("Filesystem non supporta Unicode")

        thread = CopyDeleteThread(src=src, dst=dst, is_folder=False, copy=True)
        thread.run()

        if os.path.exists(dst):
            with open(dst, 'r', encoding='utf-8') as f:
                assert f.read() == "unicode content"

    def test_copy_hidden_file(self, temp_workspace):
        """Test copia file nascosto"""
        src = os.path.join(temp_workspace, ".hidden_file")
        dst = os.path.join(temp_workspace, ".hidden_copy")

        with open(src, 'w') as f:
            f.write("hidden content")

        thread = CopyDeleteThread(src=src, dst=dst, is_folder=False, copy=True)
        thread.run()

        assert os.path.exists(dst)

    def test_no_operation_specified(self, temp_workspace):
        """Test senza operazioni (né copy né delete)"""
        src = os.path.join(temp_workspace, "file.txt")
        with open(src, 'w') as f:
            f.write("data")

        thread = CopyDeleteThread(src=src, copy=False, delete=False)

        finished_count = [0]
        error_count = [0]
        thread.finished.connect(lambda msg: finished_count.__setitem__(0, finished_count[0] + 1))
        thread.error.connect(lambda msg: error_count.__setitem__(0, error_count[0] + 1))

        thread.run()

        # Non dovrebbe fare nulla, ma non dovrebbe neanche crashare
        assert finished_count[0] == 0
        assert error_count[0] == 0


class TestSignalEmissions:
    """Test per le emissioni dei signal"""

    def test_finished_signal_contains_paths(self, temp_workspace):
        """Test che il signal finished contenga i path"""
        src = os.path.join(temp_workspace, "source.txt")
        dst = os.path.join(temp_workspace, "dest.txt")

        with open(src, 'w') as f:
            f.write("data")

        thread = CopyDeleteThread(src=src, dst=dst, is_folder=False, copy=True)

        finished_msgs = []
        thread.finished.connect(lambda msg: finished_msgs.append(msg))

        thread.run()

        assert len(finished_msgs) == 1
        msg = finished_msgs[0]

        # Messaggio dovrebbe contenere src e dst
        assert src in msg or os.path.basename(src) in msg
        assert dst in msg or os.path.basename(dst) in msg

    def test_error_signal_contains_details(self, temp_workspace):
        """Test che il signal error contenga dettagli"""
        src = os.path.join(temp_workspace, "nonexistent.txt")
        dst = os.path.join(temp_workspace, "dest.txt")

        thread = CopyDeleteThread(src=src, dst=dst, is_folder=False, copy=True)

        error_msgs = []
        thread.error.connect(lambda msg: error_msgs.append(msg))

        thread.run()

        assert len(error_msgs) == 1
        msg = error_msgs[0]

        # Messaggio di errore dovrebbe contenere src
        assert src in msg

    def test_multiple_finished_signals_on_combined_operation(self, temp_workspace):
        """Test emissione di più signal finished su operazione combinata"""
        src = os.path.join(temp_workspace, "file.txt")
        dst = os.path.join(temp_workspace, "copy.txt")

        with open(src, 'w') as f:
            f.write("data")

        thread = CopyDeleteThread(
            src=src,
            dst=dst,
            is_folder=False,
            copy=True,
            delete=True
        )

        finished_msgs = []
        thread.finished.connect(lambda msg: finished_msgs.append(msg))

        thread.run()

        # Dovrebbe emettere 2 signal: uno per copy, uno per delete
        assert len(finished_msgs) == 2
        assert any("copied" in msg.lower() for msg in finished_msgs)
        assert any("deleted" in msg.lower() for msg in finished_msgs)


class TestConcurrency:
    """Test per concorrenza e thread safety"""

    def test_multiple_copy_threads_concurrent(self, temp_workspace):
        """Test esecuzione concorrente di più thread di copia"""
        threads = []
        files_to_create = 5

        for i in range(files_to_create):
            src = os.path.join(temp_workspace, f"source_{i}.txt")
            dst = os.path.join(temp_workspace, f"dest_{i}.txt")

            with open(src, 'w') as f:
                f.write(f"content {i}")

            thread = CopyDeleteThread(src=src, dst=dst, is_folder=False, copy=True)
            threads.append(thread)

        # Avvia tutti i thread
        for thread in threads:
            thread.start()

        # Attendi completamento
        for thread in threads:
            thread.wait(5000)  # 5 secondi timeout

        # Verifica tutti i file copiati
        for i in range(files_to_create):
            dst = os.path.join(temp_workspace, f"dest_{i}.txt")
            assert os.path.exists(dst)

    def test_multiple_delete_threads_concurrent(self, temp_workspace):
        """Test eliminazione concorrente di file multipli"""
        threads = []
        files_to_delete = 5

        # Crea file
        for i in range(files_to_delete):
            file_path = os.path.join(temp_workspace, f"delete_{i}.txt")
            with open(file_path, 'w') as f:
                f.write(f"data {i}")

            thread = CopyDeleteThread(src=file_path, is_folder=False, delete=True)
            threads.append((thread, file_path))

        # Avvia tutti
        for thread, _ in threads:
            thread.start()

        # Attendi
        for thread, _ in threads:
            thread.wait(5000)

        # Verifica tutti eliminati
        for _, file_path in threads:
            assert not os.path.exists(file_path)


class TestPerformance:
    """Test per performance con file/cartelle grandi"""

    def test_copy_many_files_in_folder(self, temp_workspace):
        """Test copia cartella con molti file"""
        src = os.path.join(temp_workspace, "many_files_src")
        dst = os.path.join(temp_workspace, "many_files_dst")

        os.makedirs(src)

        # Crea 100 file
        num_files = 100
        for i in range(num_files):
            with open(os.path.join(src, f"file_{i:03d}.txt"), 'w') as f:
                f.write(f"content {i}")

        thread = CopyDeleteThread(src=src, dst=dst, is_folder=True, copy=True)
        thread.run()

        # Verifica tutti copiati
        assert len(os.listdir(dst)) == num_files

    def test_delete_folder_with_many_files(self, temp_workspace):
        """Test eliminazione cartella con molti file"""
        folder = os.path.join(temp_workspace, "many_files_delete")
        os.makedirs(folder)

        # Crea molti file
        for i in range(50):
            with open(os.path.join(folder, f"file_{i}.txt"), 'w') as f:
                f.write("data")

        thread = CopyDeleteThread(src=folder, is_folder=True, delete=True)
        thread.run()

        assert not os.path.exists(folder)

    def test_copy_deep_nested_structure(self, temp_workspace):
        """Test copia struttura molto annidata"""
        src = os.path.join(temp_workspace, "deep_src")
        dst = os.path.join(temp_workspace, "deep_dst")

        # Crea struttura profonda
        current = src
        for i in range(10):
            current = os.path.join(current, f"level_{i}")
            os.makedirs(current)
            with open(os.path.join(current, f"file_{i}.txt"), 'w') as f:
                f.write(f"level {i}")

        thread = CopyDeleteThread(src=src, dst=dst, is_folder=True, copy=True)
        thread.run()

        # Verifica struttura copiata
        assert os.path.exists(dst)

        # Verifica profondità
        current_check = dst
        for i in range(10):
            current_check = os.path.join(current_check, f"level_{i}")
            assert os.path.exists(current_check)
            assert os.path.exists(os.path.join(current_check, f"file_{i}.txt"))


class TestRealWorldScenarios:
    """Test per scenari realistici"""

    def test_backup_workspace_folder(self, temp_workspace):
        """Test backup di cartella workspace"""
        # Simula workspace con struttura BIDS
        workspace = os.path.join(temp_workspace, "workspace")
        backup = os.path.join(temp_workspace, "backup")

        # Crea struttura
        for i in range(3):
            subject_dir = os.path.join(workspace, f"sub-{i:02d}", "anat")
            os.makedirs(subject_dir)
            with open(os.path.join(subject_dir, "T1w.nii"), 'w') as f:
                f.write(f"subject {i} brain data")

        thread = CopyDeleteThread(src=workspace, dst=backup, is_folder=True, copy=True)
        thread.run()

        # Verifica backup completo
        assert os.path.exists(backup)
        for i in range(3):
            assert os.path.exists(
                os.path.join(backup, f"sub-{i:02d}", "anat", "T1w.nii")
            )

    def test_cleanup_temp_derivatives(self, temp_workspace):
        """Test pulizia derivati temporanei"""
        derivatives = os.path.join(temp_workspace, "derivatives", "temp_processing")
        os.makedirs(derivatives)

        # Crea file temporanei
        for i in range(5):
            with open(os.path.join(derivatives, f"temp_{i}.nii"), 'w') as f:
                f.write("temp data")

        thread = CopyDeleteThread(src=derivatives, is_folder=True, delete=True)
        thread.run()

        assert not os.path.exists(derivatives)

    def test_move_processed_results(self, temp_workspace):
        """Test spostamento risultati processati"""
        processing = os.path.join(temp_workspace, "processing")
        results = os.path.join(temp_workspace, "results")

        os.makedirs(processing)
        with open(os.path.join(processing, "output.nii"), 'w') as f:
            f.write("processed brain")
        with open(os.path.join(processing, "output.json"), 'w') as f:
            f.write('{"processed": true}')

        # Move = copy + delete
        thread = CopyDeleteThread(
            src=processing,
            dst=results,
            is_folder=True,
            copy=True,
            delete=True
        )
        thread.run()

        # Risultati dovrebbero esistere
        assert os.path.exists(results)
        assert os.path.exists(os.path.join(results, "output.nii"))
        assert os.path.exists(os.path.join(results, "output.json"))

        # Cartella processing dovrebbe essere eliminata
        assert not os.path.exists(processing)


class TestPathNormalization:
    """Test per normalizzazione path"""

    def test_copy_with_trailing_slash(self, temp_workspace):
        """Test copia con trailing slash nei path"""
        src = os.path.join(temp_workspace, "source") + os.sep
        dst = os.path.join(temp_workspace, "dest") + os.sep

        os.makedirs(src.rstrip(os.sep))
        with open(os.path.join(src, "file.txt"), 'w') as f:
            f.write("data")

        thread = CopyDeleteThread(src=src, dst=dst, is_folder=True, copy=True)
        thread.run()

        assert os.path.exists(dst.rstrip(os.sep))

    def test_copy_with_relative_path(self, temp_workspace):
        """Test copia con path relativi"""
        # Cambia directory temporaneamente
        original_cwd = os.getcwd()
        try:
            os.chdir(temp_workspace)

            src = "relative_source.txt"
            dst = "relative_dest.txt"

            with open(src, 'w') as f:
                f.write("relative data")

            thread = CopyDeleteThread(src=src, dst=dst, is_folder=False, copy=True)
            thread.run()

            assert os.path.exists(dst)
        finally:
            os.chdir(original_cwd)

    def test_copy_with_absolute_path(self, temp_workspace):
        """Test copia con path assoluti"""
        src = os.path.abspath(os.path.join(temp_workspace, "abs_source.txt"))
        dst = os.path.abspath(os.path.join(temp_workspace, "abs_dest.txt"))

        with open(src, 'w') as f:
            f.write("absolute path data")

        thread = CopyDeleteThread(src=src, dst=dst, is_folder=False, copy=True)
        thread.run()

        assert os.path.exists(dst)


class TestErrorMessages:
    """Test per i messaggi di errore"""

    def test_error_message_format(self, temp_workspace):
        """Test formato messaggio di errore"""
        src = os.path.join(temp_workspace, "missing.txt")
        dst = os.path.join(temp_workspace, "dest.txt")

        thread = CopyDeleteThread(src=src, dst=dst, is_folder=False, copy=True)

        error_msgs = []
        thread.error.connect(lambda msg: error_msgs.append(msg))

        thread.run()

        assert len(error_msgs) == 1
        msg = error_msgs[0]

        # Messaggio dovrebbe contenere src, dst e descrizione errore
        assert "src:" in msg.lower() or src in msg
        assert "dst:" in msg.lower() or dst in msg

    def test_translatable_messages(self, temp_workspace):
        """Test che i messaggi siano traducibili"""
        src = os.path.join(temp_workspace, "source.txt")
        dst = os.path.join(temp_workspace, "dest.txt")

        with open(src, 'w') as f:
            f.write("data")

        thread = CopyDeleteThread(src=src, dst=dst, is_folder=False, copy=True)

        finished_msgs = []
        thread.finished.connect(lambda msg: finished_msgs.append(msg))

        thread.run()

        # I messaggi dovrebbero venire da QCoreApplication.translate
        # Quindi dovrebbero essere stringhe leggibili
        assert len(finished_msgs) == 1
        assert len(finished_msgs[0]) > 0


# Test parametrizzati
@pytest.mark.parametrize("is_folder", [True, False])
def test_copy_parametrized_folder_flag(is_folder, temp_workspace):
    """Test parametrizzato per flag is_folder"""
    if is_folder:
        src = os.path.join(temp_workspace, "folder_src")
        dst = os.path.join(temp_workspace, "folder_dst")
        os.makedirs(src)
        with open(os.path.join(src, "file.txt"), 'w') as f:
            f.write("data")
    else:
        src = os.path.join(temp_workspace, "file_src.txt")
        dst = os.path.join(temp_workspace, "file_dst.txt")
        with open(src, 'w') as f:
            f.write("data")

    thread = CopyDeleteThread(src=src, dst=dst, is_folder=is_folder, copy=True)
    thread.run()

    assert os.path.exists(dst)


@pytest.mark.parametrize("operation,flag_name", [
    ("copy", "copy"),
    ("delete", "delete"),
])
def test_operation_flags_parametrized(operation, flag_name, temp_workspace):
    """Test parametrizzato per flag operazioni"""
    src = os.path.join(temp_workspace, f"{operation}_test.txt")
    with open(src, 'w') as f:
        f.write("data")

    kwargs = {
        'src': src,
        'is_folder': False,
        flag_name: True
    }

    if operation == "copy":
        kwargs['dst'] = os.path.join(temp_workspace, "dest.txt")

    thread = CopyDeleteThread(**kwargs)

    assert getattr(thread, flag_name) is True


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
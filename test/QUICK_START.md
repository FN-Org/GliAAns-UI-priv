# 🚀 Quick Start - Esegui i Test in 5 Minuti

## Step 1: Preparazione (2 minuti)

### Struttura File
Assicurati di avere questa struttura:

```
your_project/
├── main_window.py          # Il tuo codice originale
├── test_main_window.py     # Test suite
├── conftest.py             # Configurazione pytest
├── requirements-test.txt   # Dipendenze test
├── run_tests.sh           # Script Linux/Mac
├── run_tests.bat          # Script Windows
├── TESTING_GUIDE.md       # Guida completa
└── QUICK_START.md         # Questa guida
```

### Installa Dipendenze

```bash
pip install -r requirements-test.txt
```

Output atteso:
```
Successfully installed pytest-7.4.0 pytest-qt-4.2.0 pytest-cov-4.1.0 ...
```

## Step 2: Primo Test (1 minuto)

### Metodo Veloce

**Linux/Mac:**
```bash
chmod +x run_tests.sh
./run_tests.sh
```

**Windows:**
```cmd
run_tests.bat
```

### Output Atteso

```
==========================================
Test Suite per MainWindow
==========================================

>>> Esecuzione test
===================== test session starts =====================
collected 25 items

test_main_window.py::TestMainWindowSetup::test_window_initialization PASSED
test_main_window.py::TestMainWindowSetup::test_menu_bar_created PASSED
test_main_window.py::TestLanguageManagement::test_set_language_emits_signal PASSED
...

===================== 25 passed in 3.45s =====================

✓ Tutti i test sono passati!
```

## Step 3: Test con Coverage (2 minuti)

```bash
./run_tests.sh -c
```

Questo genera un report HTML. Aprilo con:

- **Linux:** `xdg-open htmlcov/index.html`
- **Mac:** `open htmlcov/index.html`
- **Windows:** `start htmlcov\index.html`

### Interpretare il Coverage

Nel browser vedrai:

```
main_window.py    Coverage: 85%
├── Covered lines:     170/200
├── Missing lines:     30/200
└── Branch coverage:   80%
```

Clicca sul file per vedere quali linee NON sono coperte (in rosso).

## 🎯 Comandi Essenziali

### Durante lo Sviluppo

```bash
# Test rapido (ferma al primo errore)
pytest test_main_window.py -x

# Test con output dettagliato
pytest test_main_window.py -v -s

# Solo un test specifico
pytest test_main_window.py::TestMainWindowSetup::test_window_initialization -v
```

### Prima di Commit

```bash
# Test completi con coverage
./run_tests.sh -c

# Verifica che coverage sia > 80%
pytest --cov=. --cov-fail-under=80 test_main_window.py
```

## ⚡ Troubleshooting Rapido

### Problema: "ModuleNotFoundError: No module named 'main_window'"

**Causa:** Il nome del file è diverso

**Soluzione:** Modifica l'import nel test:
```python
# In test_main_window.py, cambia:
from main_window import MainWindow
# In (ad esempio):
from your_actual_filename import MainWindow
```

### Problema: "QApplication instance already exists"

**Causa:** Normale con PyQt6

**Soluzione:** Già gestito in `conftest.py`, ignora il warning

### Problema: Test falliscono tutti

**Causa:** Dipendenze mancanti o import errati

**Soluzione:**
```bash
# Reinstalla dipendenze
pip install --upgrade -r requirements-test.txt

# Verifica import
python -c "from main_window import MainWindow; print('Import OK')"

# Esegui test singolo per debug
pytest test_main_window.py::TestMainWindowSetup::test_window_initialization -v -s
```

### Problema: "Permission denied" su run_tests.sh

**Soluzione:**
```bash
chmod +x run_tests.sh
```

### Problema: Test lenti

**Soluzione:** Esegui solo test veloci:
```bash
pytest -m "not slow" test_main_window.py
```

## 📊 Checklist Pre-Commit

Prima di fare commit, verifica:

- [ ] Tutti i test passano: `pytest test_main_window.py`
- [ ] Coverage > 80%: `pytest --cov=. --cov-fail-under=80`
- [ ] Nessun warning: `pytest -W error`
- [ ] Code linting OK: `flake8 main_window.py` (opzionale)

### Script Automatico Pre-Commit

```bash
#!/bin/bash
# save as .git/hooks/pre-commit

echo "Running tests before commit..."
pytest test_main_window.py -x --cov=. --cov-fail-under=80

if [ $? -ne 0 ]; then
    echo "❌ Tests failed! Commit aborted."
    exit 1
fi

echo "✅ All tests passed!"
exit 0
```

## 🎓 Prossimi Passi

### 1. Esplora i Test (5 minuti)

Apri `test_main_window.py` e leggi i commenti:

```python
def test_window_initialization(self, main_window):
    """Verifica che la finestra si inizializzi correttamente"""
    # Ogni test ha:
    # - Un nome descrittivo
    # - Un docstring che spiega cosa testa
    # - Arrange, Act, Assert chiari
```

### 2. Aggiungi un Test (10 minuti)

Prova ad aggiungere un test semplice:

```python
class TestMainWindowSetup:
    # ... altri test ...
    
    def test_window_has_title(self, main_window):
        """Verifica che la finestra abbia un titolo"""
        title = main_window.windowTitle()
        assert title != ""
        assert len(title) > 0
```

Esegui:
```bash
pytest test_main_window.py::TestMainWindowSetup::test_window_has_title -v
```

### 3. Migliora Coverage (15 minuti)

Identifica codice non coperto:

```bash
# Genera report
pytest --cov=. --cov-report=term-missing test_main_window.py

# Output mostra linee mancanti
main_window.py    85%    30-35, 40-42
```

Aggiungi test per quelle linee.

### 4. Refactoring (30 minuti)

Leggi `REFACTORING_SUGGESTIONS.md` per rendere il codice più testabile.

## 📚 Risorse

### Documentazione
- [TESTING_GUIDE.md](TESTING_GUIDE.md) - Guida completa
- [REFACTORING_SUGGESTIONS.md](REFACTORING_SUGGESTIONS.md) - Migliorare testabilità

### Comandi Utili
```bash
# Help degli script
./run_tests.sh -h

# Help pytest
pytest --help

# Markers disponibili
pytest --markers
```

### Esempi di Test

**Test semplice:**
```python
def test_something(main_window):
    assert main_window.some_value == expected_value
```

**Test con mock:**
```python
def test_with_mock(main_window, monkeypatch):
    mock_func = Mock(return_value="mocked")
    monkeypatch.setattr(main_window, 'function', mock_func)
    result = main_window.call_function()
    assert result == "mocked"
```

**Test con signals Qt:**
```python
def test_signal(main_window, qtbot):
    with qtbot.waitSignal(main_window.my_signal):
        main_window.trigger_signal()
```

## ⏱️ Timing Atteso

| Operazione | Tempo |
|------------|-------|
| Installazione dipendenze | 1-2 min |
| Primo run test | 3-5 sec |
| Test con coverage | 5-8 sec |
| Aggiungere nuovo test | 5-10 min |
| Debug test fallito | 2-15 min |

## 🎯 Obiettivi per Oggi

### Minimo (30 minuti)
- [x] Installare dipendenze
- [x] Eseguire tutti i test
- [x] Vedere report coverage

### Consigliato (1 ora)
- [x] Minimo +
- [ ] Aggiungere 2-3 nuovi test
- [ ] Portare coverage a 85%
- [ ] Leggere TESTING_GUIDE.md

### Avanzato (2 ore)
- [x] Consigliato +
- [ ] Refactoring di una funzione
- [ ] Setup pre-commit hook
- [ ] Documentare casi edge

## 💡 Tips

### Sviluppo Test-Driven (TDD)

1. **Scrivi il test** (che fallisce)
```python
def test_new_feature(main_window):
    result = main_window.new_feature()
    assert result == "expected"
```

2. **Implementa la funzionalità**
```python
def new_feature(self):
    return "expected"
```

3. **Esegui il test** (dovrebbe passare)
```bash
pytest test_main_window.py::test_new_feature -v
```

4. **Refactoring** (se necessario)

### Debug Efficace

```bash
# Mostra print statements
pytest test_main_window.py -s

# Entra in debugger su errore
pytest test_main_window.py --pdb

# Solo ultimo test fallito
pytest --lf

# Verbose con traceback completo
pytest -vv --tb=long
```

### Performance

```bash
# Mostra i 5 test più lenti
pytest --durations=5

# Esegui in parallelo (richiede pytest-xdist)
pytest -n auto
```

## 🚨 Errori Comuni

### 1. Import Errato
```python
# ❌ Sbagliato
from MainWindow import MainWindow

# ✅ Corretto
from main_window import MainWindow
```

### 2. Fixture Non Trovata
```python
# ❌ Sbagliato - parametro errato
def test_something(wrong_fixture):
    pass

# ✅ Corretto - usa fixture esistente
def test_something(main_window):
    pass
```

### 3. Assert su Oggetti Qt
```python
# ❌ Può fallire per riferimenti
assert widget == expected_widget

# ✅ Confronta proprietà
assert widget.text() == expected_widget.text()
```

## 📞 Hai Bisogno di Aiuto?

### Problemi con i Test
1. Controlla l'output di pytest con `-v`
2. Verifica che tutte le dipendenze siano installate
3. Leggi il traceback completo con `--tb=long`

### Problemi con Coverage
1. Identifica linee non coperte con `--cov-report=term-missing`
2. Aggiungi test per quelle linee
3. Verifica che i test eseguano effettivamente il codice

### Problemi con PyQt6
1. Usa `qtbot` fixture per operazioni Qt
2. Usa `qtbot.waitSignal()` per signals asincroni
3. Usa `qtbot.waitExposed()` per widget visibili

---

## ✨ Congratulazioni!

Hai completato il quick start! Ora hai:
- ✅ Test funzionanti
- ✅ Coverage report
- ✅ Conoscenza base di pytest

**Prossimi passi:** Leggi la guida completa e inizia ad aggiungere test per nuove funzionalità!

---

**Tempo totale:** ~5-10 minuti
**Difficoltà:** ⭐⭐☆☆☆ (Facile)
**Versione:** 1.0.0
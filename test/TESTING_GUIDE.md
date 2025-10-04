# Guida ai Test per MainWindow

## 📋 Indice
- [Installazione](#installazione)
- [Esecuzione dei Test](#esecuzione-dei-test)
- [Struttura dei Test](#struttura-dei-test)
- [Coverage](#coverage)
- [Best Practices](#best-practices)
- [Troubleshooting](#troubleshooting)

## 🚀 Installazione

### 1. Installa le dipendenze di test

```bash
pip install -r requirements-test.txt
```

### 2. Verifica l'installazione

```bash
pytest --version
```

## ▶️ Esecuzione dei Test

### Metodo 1: Script automatici (Raccomandato)

**Linux/Mac:**
```bash
chmod +x run_tests.sh
./run_tests.sh
```

**Windows:**
```cmd
run_tests.bat
```

### Metodo 2: Comandi pytest diretti

**Esegui tutti i test:**
```bash
pytest test_main_window.py -v
```

**Con coverage:**
```bash
pytest test_main_window.py --cov=. --cov-report=html --cov-report=term
```

**Test specifico:**
```bash
pytest test_main_window.py::TestMainWindowSetup::test_window_initialization -v
```

**Solo test veloci (escludi slow):**
```bash
pytest -m "not slow" test_main_window.py
```

### Opzioni degli script

| Opzione | Descrizione |
|---------|-------------|
| `-c, --coverage` | Genera report di copertura |
| `-v, --verbose` | Output dettagliato |
| `-t, --test NAME` | Esegui solo test specifici |
| `-h, --help` | Mostra l'aiuto |

**Esempi:**
```bash
# Con coverage
./run_tests.sh -c

# Test specifico verbose
./run_tests.sh -v -t test_language

# Solo test di setup
./run_tests.sh -t TestMainWindowSetup
```

## 📁 Struttura dei Test

### Classi di Test

```
test_main_window.py
├── TestMainWindowSetup          # Test inizializzazione e UI
├── TestLanguageManagement       # Test gestione lingue
├── TestWorkspaceOperations      # Test operazioni workspace
├── TestThreadManagement         # Test gestione thread
├── TestDebugLog                 # Test funzionalità debug
├── TestWidgetManagement         # Test gestione widget
└── TestIntegration              # Test di integrazione
```

### Test Principali

#### 1. **TestMainWindowSetup**
Verifica l'inizializzazione corretta della finestra:
- Dimensioni finestra (950x650)
- Creazione menu bar
- Creazione splitter
- Creazione footer con pulsanti

#### 2. **TestLanguageManagement**
Verifica il sistema multilingua:
- Cambio lingua
- Emissione segnali
- Esclusività selezione lingua

#### 3. **TestWorkspaceOperations**
Verifica operazioni sul workspace:
- Conferma eliminazione
- Eliminazione file
- Ritorno a import page

#### 4. **TestThreadManagement**
Verifica gestione thread asincroni:
- Aggiunta thread
- Gestione errori
- Rimozione thread completati
- Chiusura thread all'uscita

#### 5. **TestDebugLog**
Verifica funzionalità debug:
- Abilitazione/disabilitazione logging
- Persistenza impostazioni

## 📊 Coverage

### Visualizzare il Coverage Report

**Genera il report:**
```bash
pytest --cov=. --cov-report=html test_main_window.py
```

**Apri il report HTML:**

- **Linux:** `xdg-open htmlcov/index.html`
- **Mac:** `open htmlcov/index.html`
- **Windows:** `start htmlcov\index.html`

### Interpretare i Risultati

Il report mostra:
- **Linee coperte** (verde): codice testato
- **Linee non coperte** (rosso): codice non testato
- **Percentuale coverage**: obiettivo > 80%

### Coverage per file specifico

```bash
pytest --cov=main_window --cov-report=term-missing test_main_window.py
```

## ✅ Best Practices

### 1. **Fixtures Riutilizzabili**

Le fixture comuni sono definite in `conftest.py`:

```python
@pytest.fixture
def temp_workspace():
    """Workspace temporaneo per test"""
    temp_dir = tempfile.mkdtemp()
    yield temp_dir
    shutil.rmtree(temp_dir, ignore_errors=True)
```

### 2. **Mock degli Oggetti Esterni**

Usa mock per dipendenze esterne:

```python
@pytest.fixture
def mock_context(self, temp_workspace):
    context = {
        "language_changed": Mock(spec=['connect', 'emit']),
        "settings": QSettings("TestOrg", "TestApp"),
        # ... altri mock
    }
    return context
```

### 3. **Test Isolation**

Ogni test è indipendente grazie a:
- Fixture `clean_settings` (autouse)
- Workspace temporanei
- Mock delle dipendenze

### 4. **Nomi Descrittivi**

```python
def test_clear_folder_confirms_deletion(self, main_window, monkeypatch):
    """Verifica che venga richiesta conferma prima di eliminare"""
    # Test chiaro e autoesplicativo
```

## 🔧 Troubleshooting

### Problema: "QApplication instance already exists"

**Soluzione:** La fixture `qapp` in `conftest.py` gestisce questo caso

```python
@pytest.fixture(scope="session")
def qapp():
    app = QApplication.instance()
    if app is None:
        app = QApplication([])
    yield app
```

### Problema: "ModuleNotFoundError: No module named 'main_window'"

**Soluzione:** Aggiorna il nome del modulo nel test:

```python
from main_window import MainWindow  # Sostituisci con il nome corretto
```

Oppure aggiungi il path:

```python
import sys
sys.path.insert(0, os.path.abspath('.'))
```

### Problema: Test lenti

**Soluzione:** Usa marker per saltare test lenti:

```python
@pytest.mark.slow
def test_operazione_lenta():
    # ...
```

Esegui solo test veloci:
```bash
pytest -m "not slow"
```

### Problema: "Permission denied" su file temporanei

**Soluzione:** Usa `ignore_errors=True` nella pulizia:

```python
shutil.rmtree(temp_dir, ignore_errors=True)
```

## 📈 Metriche di Qualità

### Obiettivi

| Metrica | Obiettivo | Attuale |
|---------|-----------|---------|
| Coverage | > 80% | Da verificare |
| Test passati | 100% | Da verificare |
| Tempo esecuzione | < 10s | Da verificare |

### Verifica Qualità

```bash
# Coverage completo
pytest --cov=. --cov-report=term --cov-fail-under=80

# Con report dettagliato
pytest -v --tb=short --strict-markers
```

## 🎯 Comandi Rapidi

### Sviluppo Quotidiano

```bash
# Quick test
pytest test_main_window.py -x  # Ferma al primo errore

# Test specifico con output
pytest test_main_window.py::TestMainWindowSetup -v -s

# Watch mode (richiede pytest-watch)
ptw test_main_window.py
```

### CI/CD

```bash
# Test completi per CI
pytest test_main_window.py --cov=. --cov-report=xml --junitxml=junit.xml

# Con fallimento su coverage basso
pytest --cov=. --cov-fail-under=80
```

### Debug

```bash
# Con print statements
pytest test_main_window.py -s

# Con debugger integrato
pytest test_main_window.py --pdb

# Ultimo test fallito
pytest --lf
```

## 📝 Aggiungere Nuovi Test

### Template per nuovo test

```python
class TestNuovaFunzionalita:
    """Test per [descrizione funzionalità]"""
    
    @pytest.fixture
    def setup_specifico(self):
        # Setup specifico per questi test
        yield
        # Teardown
    
    def test_comportamento_base(self, main_window):
        """Verifica [cosa viene testato]"""
        # Arrange
        expected = "valore_atteso"
        
        # Act
        result = main_window.metodo()
        
        # Assert
        assert result == expected
    
    def test_caso_edge(self, main_window):
        """Verifica comportamento in caso edge"""
        # ...
```

## 🔗 Risorse Utili

- [Documentazione pytest](https://docs.pytest.org/)
- [pytest-qt Documentation](https://pytest-qt.readthedocs.io/)
- [Coverage.py Guide](https://coverage.readthedocs.io/)
- [PyQt6 Documentation](https://www.riverbankcomputing.com/static/Docs/PyQt6/)

## 📞 Supporto

Per problemi con i test:

1. Verifica che tutte le dipendenze siano installate
2. Controlla i log di pytest con `-v`
3. Esegui test singoli per isolare il problema
4. Verifica la versione di Python (raccomandato: 3.8+)

---

**Ultima modifica:** 2025-01-04
**Versione test suite:** 1.0.0
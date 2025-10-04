#!/bin/bash

# Script per eseguire i test con diverse opzioni

echo "=========================================="
echo "Test Suite per MainWindow"
echo "=========================================="
echo ""

# Colori per output
GREEN='\033[0;32m'
BLUE='\033[0;34m'
RED='\033[0;31m'
NC='\033[0m' # No Color

# Funzione per stampare intestazioni
print_header() {
    echo -e "${BLUE}>>> $1${NC}"
}

# Funzione per verificare se pytest è installato
check_pytest() {
    if ! command -v pytest &> /dev/null; then
        echo -e "${RED}pytest non è installato. Installalo con:${NC}"
        echo "pip install -r requirements-test.txt"
        exit 1
    fi
}

# Verifica pytest
check_pytest

# Parsing argomenti
COVERAGE=false
VERBOSE=false
SPECIFIC_TEST=""

while [[ $# -gt 0 ]]; do
    case $1 in
        -c|--coverage)
            COVERAGE=true
            shift
            ;;
        -v|--verbose)
            VERBOSE=true
            shift
            ;;
        -t|--test)
            SPECIFIC_TEST="$2"
            shift 2
            ;;
        -h|--help)
            echo "Uso: $0 [opzioni]"
            echo ""
            echo "Opzioni:"
            echo "  -c, --coverage    Esegui test con coverage report"
            echo "  -v, --verbose     Output verboso"
            echo "  -t, --test NAME   Esegui solo un test specifico"
            echo "  -h, --help        Mostra questo messaggio"
            echo ""
            echo "Esempi:"
            echo "  $0                           # Esegui tutti i test"
            echo "  $0 -c                        # Con coverage"
            echo "  $0 -v -c                     # Verbose con coverage"
            echo "  $0 -t test_window_initialization  # Test specifico"
            exit 0
            ;;
        *)
            echo "Opzione sconosciuta: $1"
            echo "Usa -h per aiuto"
            exit 1
            ;;
    esac
done

# Costruisci il comando pytest
PYTEST_CMD="pytest"

if [ "$VERBOSE" = true ]; then
    PYTEST_CMD="$PYTEST_CMD -v"
fi

if [ -n "$SPECIFIC_TEST" ]; then
    PYTEST_CMD="$PYTEST_CMD -k $SPECIFIC_TEST"
fi

if [ "$COVERAGE" = true ]; then
    print_header "Esecuzione test con coverage"
    $PYTEST_CMD --cov=. --cov-report=html --cov-report=term-missing test_main_window.py
    
    if [ $? -eq 0 ]; then
        echo ""
        echo -e "${GREEN}✓ Test completati con successo!${NC}"
        echo ""
        print_header "Coverage report generato in: htmlcov/index.html"
        echo "Apri il report con: open htmlcov/index.html (macOS) o xdg-open htmlcov/index.html (Linux)"
    else
        echo ""
        echo -e "${RED}✗ Alcuni test sono falliti${NC}"
        exit 1
    fi
else
    print_header "Esecuzione test"
    export QT_QPA_PLATFORM=offscreen
    echo "QT_QPA_PLATFORM=$QT_QPA_PLATFORM"
    $PYTEST_CMD test_main_window.py
    
    if [ $? -eq 0 ]; then
        echo ""
        echo -e "${GREEN}✓ Tutti i test sono passati!${NC}"
    else
        echo ""
        echo -e "${RED}✗ Alcuni test sono falliti${NC}"
        exit 1
    fi
fi

echo ""
echo "=========================================="
print_header "Comandi utili:"
echo "  • Test specifici:      $0 -t test_name"
echo "  • Con coverage:        $0 -c"
echo "  • Verbose:             $0 -v"
echo "  • Solo unit test:      pytest -m unit"
echo "  • Solo integration:    pytest -m integration"
echo "=========================================="
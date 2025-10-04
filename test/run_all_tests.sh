#!/bin/bash

# Script per eseguire TUTTI i test del progetto

echo "=========================================="
echo "Test Suite Completa - GliAAns UI"
echo "=========================================="
echo ""

GREEN='\033[0;32m'
BLUE='\033[0;34m'
RED='\033[0;31m'
YELLOW='\033[1;33m'
NC='\033[0m'

print_header() {
    echo -e "${BLUE}>>> $1${NC}"
}

# Verifica pytest
if ! command -v pytest &> /dev/null; then
    echo -e "${RED}pytest non installato!${NC}"
    echo "pip install -r requirements-test.txt"
    exit 1
fi

# Parsing argomenti
COVERAGE=false
VERBOSE=false
MODULE=""
PATTERN=""

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
        -m|--module)
            MODULE="$2"
            shift 2
            ;;
        -k|--pattern)
            PATTERN="$2"
            shift 2
            ;;
        -h|--help)
            echo "Uso: $0 [opzioni]"
            echo ""
            echo "Opzioni:"
            echo "  -c, --coverage       Coverage report"
            echo "  -v, --verbose        Output verboso"
            echo "  -m, --module NAME    Solo un modulo (main_window, import_page)"
            echo "  -k, --pattern PAT    Pattern per test specifici"
            echo "  -h, --help           Mostra questo messaggio"
            echo ""
            echo "Esempi:"
            echo "  $0                              # Tutti i test"
            echo "  $0 -c                           # Con coverage"
            echo "  $0 -m main_window               # Solo MainWindow"
            echo "  $0 -k test_initialization       # Pattern specifico"
            exit 0
            ;;
        *)
            echo "Opzione sconosciuta: $1"
            exit 1
            ;;
    esac
done

# Costruisci comando
PYTEST_CMD="pytest"

if [ "$VERBOSE" = true ]; then
    PYTEST_CMD="$PYTEST_CMD -v"
fi

if [ -n "$MODULE" ]; then
    PYTEST_CMD="$PYTEST_CMD test_${MODULE}.py"
else
    PYTEST_CMD="$PYTEST_CMD test_*.py"
fi

if [ -n "$PATTERN" ]; then
    PYTEST_CMD="$PYTEST_CMD -k $PATTERN"
fi

# Esegui test
print_header "Esecuzione test"

if [ "$COVERAGE" = true ]; then
    $PYTEST_CMD --cov=../ui --cov-report=html --cov-report=term-missing

    if [ $? -eq 0 ]; then
        echo ""
        echo -e "${GREEN}✓ Test completati!${NC}"
        echo ""
        print_header "Coverage report: htmlcov/index.html"

        # Mostra statistiche
        echo ""
        echo -e "${YELLOW}Statistiche Coverage:${NC}"
        pytest --cov=../ui --cov-report=term --quiet 2>/dev/null | tail -5
    else
        echo ""
        echo -e "${RED}✗ Alcuni test falliti${NC}"
        exit 1
    fi
else
    $PYTEST_CMD

    if [ $? -eq 0 ]; then
        echo ""
        echo -e "${GREEN}✓ Tutti i test passati!${NC}"
    else
        echo ""
        echo -e "${RED}✗ Alcuni test falliti${NC}"
        exit 1
    fi
fi

echo ""
echo "=========================================="
print_header "Comandi Utili"
echo "  • Solo MainWindow:     $0 -m main_window"
echo "  • Solo ImportPage:     $0 -m import_page"
echo "  • Con coverage:        $0 -c"
echo "  • Verbose:             $0 -v"
echo "  • Pattern specifico:   $0 -k pattern"
echo "=========================================="
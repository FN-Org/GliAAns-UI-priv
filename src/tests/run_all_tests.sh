#!/bin/bash

# Determine the script directory
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
export PYTHONPATH="$SCRIPT_DIR/../main:$SCRIPT_DIR/.."

echo "=========================================="
echo "Complete test suite - GliAAns UI"
echo "=========================================="
echo ""

# Define colors
GREEN='\033[0;32m'
BLUE='\033[0;34m'
RED='\033[0;31m'
YELLOW='\033[1;33m'
NC='\033[0m' # No Color

print_header() {
    echo -e "${BLUE}>>> $1${NC}"
}

# Verify pytest
if ! command -v pytest &> /dev/null; then
    echo -e "${RED}pytest not installed!${NC}"
    echo "pip install -r requirements-test.txt"
    exit 1
fi

# Parse arguments
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
            echo "Usage: $0 [options]"
            echo ""
            echo "Options:"
            echo "  -c, --coverage       Generate coverage report"
            echo "  -v, --verbose        Verbose output"
            echo "  -m, --module NAME    Run tests for a specific module (e.g., main_window, import_page)"
            echo "  -k, --pattern PAT    Run tests matching a specific pattern"
            echo "  -h, --help           Show this help message"
            echo ""
            echo "Examples:"
            echo "  $0                                    # Run all tests"
            echo "  $0 -c                                 # Run with coverage"
            echo "  $0 -m main_window                     # Run only MainWindow tests"
            echo "  $0 -k test_initialization             # Run tests matching a specific pattern"
            exit 0
            ;;
        *)
            echo "Unknown option: $1"
            exit 1
            ;;
    esac
done

# Construct pytest command
PYTEST_CMD="pytest"

if [ "$VERBOSE" = true ]; then
    PYTEST_CMD="$PYTEST_CMD -v"
fi

if [ -n "$MODULE" ]; then
    PYTEST_CMD="$PYTEST_CMD src/tests/**/test_${MODULE}.py"
else
    PYTEST_CMD="$PYTEST_CMD"
fi

if [ -n "$PATTERN" ]; then
    PYTEST_CMD="$PYTEST_CMD -k $PATTERN"
fi

# Test execution
print_header "Running tests"

if [ "$COVERAGE" = true ]; then
    COVERAGE_DIR="$SCRIPT_DIR/htmlcov"
    COVERAGE_FILE="$SCRIPT_DIR/.coverage"
    export COVERAGE_FILE

    $PYTEST_CMD --cov=./ --cov-report=html:"$COVERAGE_DIR" --cov-report=term-missing

    if [ $? -eq 0 ]; then
        echo ""
        echo -e "${GREEN}✓ Tests completed!${NC}"
        echo ""
        print_header "Coverage report: htmlcov/index.html"

        # Show stats
        echo ""
        echo -e "${YELLOW}Coverage Stats:${NC}"
        pytest --cov=ui --cov-report=term --quiet 2>/dev/null | tail -5
    else
        echo ""
        echo -e "${RED}✗ Some tests failed${NC}"
        exit 1
    fi
else
    $PYTEST_CMD

    if [ $? -eq 0 ]; then
        echo ""
        echo -e "${GREEN}✓ All tests passed!${NC}"
    else
        echo ""
        echo -e "${RED}✗ Some tests failed${NC}"
        exit 1
    fi
fi

echo ""
echo "=========================================="
print_header "Useful Commands"
echo "  • MainWindow only:   $0 -m main_window"
echo "  • With coverage:     $0 -c"
echo "  • Verbose:           $0 -v"
echo "  • Specific pattern:  $0 -k pattern"
echo "=========================================="
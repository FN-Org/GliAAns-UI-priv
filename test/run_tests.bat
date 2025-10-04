@echo off
REM Script per eseguire i test su Windows

echo ==========================================
echo Test Suite per MainWindow
echo ==========================================
echo.

REM Verifica se pytest è installato
where pytest >nul 2>nul
if %ERRORLEVEL% NEQ 0 (
    echo [ERRORE] pytest non è installato
    echo Installalo con: pip install -r requirements-test.txt
    exit /b 1
)

REM Parsing argomenti semplificato
set COVERAGE=0
set VERBOSE=0
set SPECIFIC_TEST=

:parse_args
if "%~1"=="" goto end_parse
if /i "%~1"=="-c" set COVERAGE=1
if /i "%~1"=="--coverage" set COVERAGE=1
if /i "%~1"=="-v" set VERBOSE=1
if /i "%~1"=="--verbose" set VERBOSE=1
if /i "%~1"=="-t" (
    set SPECIFIC_TEST=%~2
    shift
)
if /i "%~1"=="--test" (
    set SPECIFIC_TEST=%~2
    shift
)
if /i "%~1"=="-h" goto show_help
if /i "%~1"=="--help" goto show_help
shift
goto parse_args

:show_help
echo Uso: run_tests.bat [opzioni]
echo.
echo Opzioni:
echo   -c, --coverage    Esegui test con coverage report
echo   -v, --verbose     Output verboso
echo   -t, --test NAME   Esegui solo un test specifico
echo   -h, --help        Mostra questo messaggio
echo.
echo Esempi:
echo   run_tests.bat                           # Esegui tutti i test
echo   run_tests.bat -c                        # Con coverage
echo   run_tests.bat -v -c                     # Verbose con coverage
echo   run_tests.bat -t test_window_initialization  # Test specifico
exit /b 0

:end_parse

REM Costruisci il comando
set PYTEST_CMD=pytest

if %VERBOSE%==1 (
    set PYTEST_CMD=%PYTEST_CMD% -v
)

if not "%SPECIFIC_TEST%"=="" (
    set PYTEST_CMD=%PYTEST_CMD% -k %SPECIFIC_TEST%
)

if %COVERAGE%==1 (
    echo ^>^>^> Esecuzione test con coverage
    %PYTEST_CMD% --cov=. --cov-report=html --cov-report=term-missing test_main_window.py

    if %ERRORLEVEL% EQU 0 (
        echo.
        echo [OK] Test completati con successo!
        echo.
        echo ^>^>^> Coverage report generato in: htmlcov\index.html
        echo Apri il report con: start htmlcov\index.html
    ) else (
        echo.
        echo [ERRORE] Alcuni test sono falliti
        exit /b 1
    )
) else (
    echo ^>^>^> Esecuzione test
    %PYTEST_CMD% test_main_window.py

    if %ERRORLEVEL% EQU 0 (
        echo.
        echo [OK] Tutti i test sono passati!
    ) else (
        echo.
        echo [ERRORE] Alcuni test sono falliti
        exit /b 1
    )
)

echo.
echo ==========================================
echo ^>^>^> Comandi utili:
echo   • Test specifici:      run_tests.bat -t test_name
echo   • Con coverage:        run_tests.bat -c
echo   • Verbose:             run_tests.bat -v
echo   • Solo unit test:      pytest -m unit
echo   • Solo integration:    pytest -m integration
echo ==========================================
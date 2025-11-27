# Test Suite Guide

## Setup & Installation

You can set up the testing environment automatically using the Makefile, or manually via pip.

### Method 1: Automatic Setup

Using [Makefile](./../Makefile).

This command creates the virtual environment and installs all required dependencies defined in `requirements-test.txt`.

```bash
make tests_python-setup
```

### Method 2: Manual Setup

If you prefer to manage the environment manually, use [requirements-test.txt](./requirements-test.txt):

```bash
pip install -r requirements-test.txt
```

-----

## Running Tests

### Method 1: Using Make

The easiest way to run tests is via the [Makefile](./../Makefile), which automatically handles environment variables (like `PYTHONPATH` and `VIRTUAL_ENV`).

**Run all tests:**

```bash
make tests
```

**Run tests with code coverage report:**

```bash
make tests-coverage
```

### Method 2: Shell Scripts (Linux/macOS)

For more granular control, you can use the `run_all_tests.sh` script directly. This allows you to pass specific flags to filter tests or change output modes.

**Basic execution:**

```bash
chmod +x tests/run_all_tests.sh
./tests/run_all_tests.sh
```

**Run a single test case (Specific Code):**
Use the `-m` flag to target a specific module or test keyword.

```bash
./tests/run_all_tests.sh -m "test_*"
```

**Run with Coverage:**

```bash
./tests/run_all_tests.sh -c
```

-----

### Script Options

When using the `run_all_tests.sh` script on Linux or macOS, the following flags are available to customize the execution:

| Flag | Long Option | Description |
| :--- | :--- | :--- |
| **`-c`** | `--coverage` | Generates a code coverage report (HTML & Term). |
| **`-m`** | `--match` | Runs a **single test** or specific piece of code matching the name provided. |
| **`-h`** | `--help` | Displays the help menu and usage instructions. |
| **`-v`** | `--verbose` | Increases output verbosity (shows each test passing/failing). |

### Examples

```bash
# View help
./tests/run_all_tests.sh -h

# Run only tests matching with verbose output
./tests/run_all_tests.sh -v -m "test_*"

# Run full suite with coverage generation
./tests/run_all_tests.sh -c
```

-----

### Troubleshooting

  * **Permission Denied:** If the `.sh` script does not run, ensure it is executable:
    ```bash
    chmod +x tests/run_all_tests.sh
    ```
  * **Import Errors:** If running manually (without Make), ensure your `PYTHONPATH` includes the `main` directory. The Makefile handles this automatically.

Here is the text to append to the end of your document. I have maintained the same formatting style and tone as the existing guide.

***

## Test Structure
### Coverage summary

Comprehensive test coverage details are reported in the folder [htmlcov](./htmlcov), which are available for consultation directly in [index.html](./htmlcov/index.html).

Currently, the project maintains an average code coverage of **96%** across the entire codebase.

### Test Breakdown

Below is a summary of the test components, their specific functionality targets, and their current implementation status:

| File                       | # classes | # tests | Status |
|:---------------------------|:----------|:--------|:-------|
| Components                 |           |         |        |
| Circular Progress Bar      | 11        | 56      | Passed |
| Collapsible Patient Frame  | 18        | 68      | Passed |
| Crosshair Graphic View     | 19        | 72      | Passed |
| File Role Dialog           | 12        | 57      | Passed |
| File Selector Widget       | 16        | 59      | Passed |
| Folder Card                | 12        | 48      | Passed |
| Nifti File Dialog          | 22        | 66      | Passed |
| Core                       |           |         |        |
| Controller                 | 9         | 29      | Passed |
| Logger                     | 7         | 32      | Passed |
| Page Contract              | /         | 10      | Passed |
| Utils                      | 9         | 34      | Passed |
| Threads                    |           |         |        |
| Dl Worker                  | 16        | 39      | Passed |
| Import Thread              | 18        | 63      | Passed |
| Nifti Utils Threads        | 17        | 56      | Passed |
| Skull Strip Thread         | 12        | 41      | Passed |
| Utils Threads              | 14        | 54      | Passed |
| Ui                         |           |         |        |
| Dl Execution Page          | 25        | 92      | Passed |
| Dl Selection Page          | 20        | 66      | Passed |
| Import Page                | 9         | 27      | Passed |
| Main Window                | 8         | 20      | Passed |
| Nifti Mask Selection       | 9         | 22      | Passed |
| Nifti Viewer               | 5         | 21      | Passed |
| Patient Selection Page     | 10        | 37      | Passed |
| Pipeline Execution Page    | 18        | 75      | Passed |
| Pipeline Patient Selection | 10        | 31      | Passed |
| Pipeline Review Page       | 10        | 36      | Passed |
| Skull Stripping Page       | 10        | 45      | Passed |
| Tool Selection Page        | 10        | 34      | Passed |
| Workspace Tree View        | 9         | 37      | Passed |


# 🧮 Enhanced Command-Line Calculator

This is an advanced Python command-line REPL calculator application. This version incorporates software design patterns, persistent history management using pandas, environment variable configuration, expanded arithmetic operations, and 100% test coverage enforced via GitHub Actions.

Interactive terminal output uses Colorama: results and successful actions are green, informational text and prompts are cyan, warnings are yellow, and errors are red. Color is omitted when output is redirected.

---

# 🛠️ 1. Project Setup

## Clone the Repository

Clone the GitHub repository and navigate into the project directory:

```bash
git clone <repository-url>
cd <repository-directory>
```

## Install Python

- **MacOS (Homebrew)**

```bash
brew install python
```

- **Windows**

Download and install [Python for Windows](https://www.python.org/downloads/).  
✅ Make sure you **check the box** `Add Python to PATH` during setup.

**Verify Python:**

```bash
python3 --version
```
or
```bash
python --version
```

---

## Create and Activate a Virtual Environment

```bash
python3 -m venv venv
source venv/bin/activate   # Mac/Linux
venv\Scripts\activate.bat  # Windows
```

## Install Required Packages
```bash
pip install -r requirements.txt
```

## Configuration

The calculator loads an optional `.env` file from the project root using `python-dotenv`. Copy `.env.example` to `.env` and adjust the values as needed:

| Variable | Default | Description |
| --- | --- | --- |
| `CALCULATOR_LOG_DIR` | `./logs` | Directory for log files |
| `CALCULATOR_LOG_FILE` | `./logs/calculator.log` | File for application logs |
| `CALCULATOR_HISTORY_DIR` | `./history` | Directory for history files |
| `CALCULATOR_MAX_HISTORY_SIZE` | `1000` | Maximum number of history entries |
| `CALCULATOR_AUTO_SAVE` | `true` | Whether to save after each calculation (`true`/`false`; `1`/`0` also accepted) |
| `CALCULATOR_PRECISION` | `10` | Number of decimal places for formatted calculation results |
| `CALCULATOR_MAX_INPUT_VALUE` | `1e999` | Maximum allowed absolute input value |
| `CALCULATOR_DEFAULT_ENCODING` | `utf-8` | Default file encoding |

The application validates numeric settings at startup. Invalid numbers, non-positive limits, and unsupported auto-save values are reported as configuration errors. INFO, WARNING, and ERROR messages—including calculation details and failures—are written to `CALCULATOR_LOG_FILE` through the shared `Logger` class.

# 🚀 2. Running the Calculator

Start the calculator:

```bash
python3 main.py
```

After starting, the calculator displays a welcome message and waits for a command:

```bash
Calculator started. Type 'help' for commands.

Enter command: 
```

**Operation Execution Flow**

The REPL uses a two-step prompt flow for calculations. Select an operation command first, and then enter the target numbers step-by-step when prompted:

1. Type the operation name (e.g., `add`, `multiply`, `power`).
2. Provide the **First number** and **Second number** at the secondary prompts.
3. Type `'cancel'` at any point during number input to abort the operation.

Example Interactive Session:

```bash
Enter command: add

Enter numbers (or 'cancel' to abort):
First number: 5
Second number: 3

Result: 8

Enter command:
```

The calculator supports:
- **`add`**
- **`subtract`**
- **`multiply`**
- **`divide`**
- **`power`**
- **`root`**
- **`modulus`**
- **`int_divide`**
- **`percent`** — calculates `(first number / second number) * 100`
- **`abs_diff`**

The calculator handles invalid input, unknown operations, and division by zero with appropriate error messages.

## Queuing calculations

Use `queue` to select an operation and provide its two operands without running it. Repeat to add more commands, then enter `run_queue` to execute them in FIFO order.

Queued calculations use the same validation, history, logging, and auto-save behavior as calculations executed immediately. If a queued command fails, it and the remaining commands stay queued for retry.

Each calculation request is encapsulated as a `CalculateCommand` containing the calculator receiver, operation, and operands. `CommandInvoker` can execute commands immediately or enqueue them for later execution.


# 📜 3. Special Commands

- **`help`** - Displays available commands and usage instructions
- **`history`** - Displays current calculation history
- **`exit`** - Auto-saves history and exits REPL
- **`clear`** - Auto-saves history and exits REPL
- **`undo`** - Undoes the last calculation using Memento
- **`redo`** - Redoes the last undone calculation
- **`save`** - Exports calculation history to file
- **`load`** - Imports calculation history from file
- **`queue`** - Add a calculation to the command queue
- **`run_queue`** - Execute queued calculations in order


# 🧪 4. Running Tests

Run all tests:

```bash
pytest
```

Lines intentionally excluded from coverage requirements use the `# pragma: no cover` comment.


# ⚙️ 5. GitHub Actions

GitHub Actions automatically runs the test suite when code is pushed to the repository.

The CI workflow:
- Runs all pytest tests.
- Measures test coverage.
- Requires 100% test coverage.
- Fails if any test fails or coverage is below 100%.

# 📁 6. Project Structure

```text
calculator/
├── app/
│   ├── calculation.py
│   ├── calculator_config.py
│   ├── calculator_memento.py
│   ├── calculator.py
│   ├── commands.py
│   ├── exceptions.py
│   ├── history.py
│   ├── input_validators.py
│   ├── logger.py
│   └── operations.py
├── tests/
│   ├── test_calculation.py
│   ├── test_calculator_config.py
│   ├── test_calculator_memento.py
│   ├── test_calculator.py
│   ├── test_commands.py
│   ├── test_exceptions.py
│   ├── test_history.py
│   ├── test_input_validators.py
│   ├── test_logger.py
│   └── test_operations.py
├── .github/workflows/
│   └── tests.yml
├── .env
├── requirements.txt
├── main.py
└── README.md

```
import datetime
from pathlib import Path
import pandas as pd
import pytest
import sys
from types import SimpleNamespace
from unittest.mock import Mock, patch, PropertyMock
from decimal import Decimal
from tempfile import TemporaryDirectory
from colorama import Fore, Style
from app.calculator import (
    Calculator,
    HelpMenu,
    HelpMenuDecorator,
    OperationHelpDecorator,
    StandardHelpMenu,
    calculator_repl,
    _colorize,
)
from app.calculator_config import CalculatorConfig
from app.exceptions import OperationError, ValidationError
from app.history import LoggingObserver, AutoSaveObserver
from app.operations import Operation, OperationFactory


def test_colorize_omits_ansi_codes_when_output_is_not_a_terminal(monkeypatch):
    monkeypatch.setattr(sys, "stdout", SimpleNamespace(isatty=lambda: False))

    assert _colorize("Result: 5", Fore.GREEN) == "Result: 5"


def test_colorize_adds_ansi_codes_for_terminal_output(monkeypatch):
    monkeypatch.setattr(sys, "stdout", SimpleNamespace(isatty=lambda: True))

    assert _colorize("Result: 5", Fore.GREEN) == (
        f"{Fore.GREEN}Result: 5{Style.RESET_ALL}"
    )


# Fixture to initialize Calculator with a temporary directory for file paths
@pytest.fixture
def calculator():
    with TemporaryDirectory() as temp_dir:
        temp_path = Path(temp_dir)
        config = CalculatorConfig(base_dir=temp_path)

        # Patch properties to use the temporary directory paths
        with patch.object(CalculatorConfig, 'log_dir', new_callable=PropertyMock) as mock_log_dir, \
             patch.object(CalculatorConfig, 'log_file', new_callable=PropertyMock) as mock_log_file, \
             patch.object(CalculatorConfig, 'history_dir', new_callable=PropertyMock) as mock_history_dir, \
             patch.object(CalculatorConfig, 'history_file', new_callable=PropertyMock) as mock_history_file:
            
            # Set return values to use paths within the temporary directory
            mock_log_dir.return_value = temp_path / "logs"
            mock_log_file.return_value = temp_path / "logs/calculator.log"
            mock_history_dir.return_value = temp_path / "history"
            mock_history_file.return_value = temp_path / "history/calculator_history.csv"
            
            # Return an instance of Calculator with the mocked config
            yield Calculator(config=config)

# Test Calculator Initialization

def test_calculator_initialization(calculator):
    assert calculator.history == []
    assert calculator.undo_stack == []
    assert calculator.redo_stack == []
    assert calculator.operation_strategy is None

# Test Logging Setup

@patch('app.logger.Logger.configure')
@patch('app.logger.Logger.info')
def test_logging_setup(logging_info_mock, configure_mock):
    with patch.object(CalculatorConfig, 'log_dir', new_callable=PropertyMock) as mock_log_dir, \
         patch.object(CalculatorConfig, 'log_file', new_callable=PropertyMock) as mock_log_file:
        mock_log_dir.return_value = Path('/tmp/logs')
        mock_log_file.return_value = Path('/tmp/logs/calculator.log')
        
        # Instantiate calculator to trigger logging
        calculator = Calculator(CalculatorConfig())
        configure_mock.assert_called_once()
        logging_info_mock.assert_any_call("Calculator initialized with configuration")

@patch('app.logger.Logger.configure', side_effect=Exception("Logging setup failed"))
@patch('builtins.print')
def test_setup_logging_error(mock_print, mock_configure):
    with patch.object(CalculatorConfig, 'log_dir', new_callable=PropertyMock) as mock_log_dir, \
         patch.object(CalculatorConfig, 'log_file', new_callable=PropertyMock) as mock_log_file:

        mock_log_dir.return_value = Path('/tmp/logs')
        mock_log_file.return_value = Path('/tmp/logs/calculator.log')

        with pytest.raises(Exception, match="Logging setup failed"):
            Calculator(CalculatorConfig())

    mock_print.assert_any_call("Error setting up logging: Logging setup failed")


# Test Adding and Removing Observers

def test_add_observer(calculator):
    observer = LoggingObserver()
    calculator.add_observer(observer)
    assert observer in calculator.observers

def test_remove_observer(calculator):
    observer = LoggingObserver()
    calculator.add_observer(observer)
    calculator.remove_observer(observer)
    assert observer not in calculator.observers

# Test Setting Operations

def test_set_operation(calculator):
    operation = OperationFactory.create_operation('add')
    calculator.set_operation(operation)
    assert calculator.operation_strategy == operation

# Test Performing Operations

def test_perform_operation_addition(calculator):
    operation = OperationFactory.create_operation('add')
    calculator.set_operation(operation)
    result = calculator.perform_operation(2, 3)
    assert result == Decimal('5')

def test_perform_operation_validation_error(calculator):
    calculator.set_operation(OperationFactory.create_operation('add'))
    with pytest.raises(ValidationError):
        calculator.perform_operation('invalid', 3)

def test_perform_operation_operation_error(calculator):
    with pytest.raises(OperationError, match="No operation set"):
        calculator.perform_operation(2, 3)

def test_perform_operation_max_history_size(calculator):
    calculator.config.max_history_size = 2

    operation = OperationFactory.create_operation('add')
    calculator.set_operation(operation)

    calculator.perform_operation(1, 1)
    calculator.perform_operation(2, 2)
    calculator.perform_operation(3, 3)

    assert len(calculator.history) == 2
    assert calculator.history[0].operand1 == Decimal('2')
    assert calculator.history[1].operand1 == Decimal('3')

def test_perform_operation_unexpected_error(calculator):
    operation = OperationFactory.create_operation('add')
    calculator.set_operation(operation)

    with patch.object(operation, 'execute', side_effect=Exception("Unexpected operation failure")):
        with pytest.raises(OperationError, match="Operation failed: Unexpected operation failure"):
            calculator.perform_operation(2, 3)


# Test Get History
def test_get_history_dataframe(calculator):
    operation = OperationFactory.create_operation('add')
    calculator.set_operation(operation)

    calculator.perform_operation(2, 3)

    df = calculator.get_history_dataframe()

    assert isinstance(df, pd.DataFrame)
    assert len(df) == 1
    assert df.iloc[0]['operation'] == 'Addition'
    assert df.iloc[0]['operand1'] == '2'
    assert df.iloc[0]['operand2'] == '3'
    assert df.iloc[0]['result'] == '5'


def test_show_history_formats_normalized_operands_without_scientific_notation(calculator):
    calculator.set_operation(OperationFactory.create_operation('modulus'))
    calculator.perform_operation('10', '4')

    assert calculator.show_history() == ["Modulus(10, 4) = 2"]


# Test Undo/Redo Functionality

def test_undo(calculator):
    operation = OperationFactory.create_operation('add')
    calculator.set_operation(operation)
    calculator.perform_operation(2, 3)
    calculator.undo()
    assert calculator.history == []

def test_undo_empty_stack(calculator):
    assert calculator.undo() is False

def test_redo(calculator):
    operation = OperationFactory.create_operation('add')
    calculator.set_operation(operation)
    calculator.perform_operation(2, 3)
    calculator.undo()
    calculator.redo()
    assert len(calculator.history) == 1

def test_redo_empty_stack(calculator):
    assert calculator.redo() is False


# Test History Management

@patch('app.calculator.pd.DataFrame.to_csv')
def test_save_history(mock_to_csv, calculator):
    operation = OperationFactory.create_operation('add')
    calculator.set_operation(operation)
    calculator.perform_operation(2, 3)
    calculator.save_history()
    mock_to_csv.assert_called_once()

@patch('app.calculator.Path.mkdir', side_effect=Exception("Save failure"))
def test_save_history_error(mock_mkdir, calculator):
    with pytest.raises(OperationError, match="Failed to save history: Save failure"):
        calculator.save_history()


@patch('app.calculator.pd.read_csv')
@patch('app.calculator.Path.exists', return_value=True)
def test_load_history(mock_exists, mock_read_csv, calculator):
    # Mock CSV data to match the expected format in from_dict
    mock_read_csv.return_value = pd.DataFrame({
        'operation': ['Addition'],
        'operand1': ['2'],
        'operand2': ['3'],
        'result': ['5'],
        'timestamp': [datetime.datetime.now().isoformat()]
    })
    
    # Test the load_history functionality
    try:
        calculator.load_history()
        # Verify history length after loading
        assert len(calculator.history) == 1
        # Verify the loaded values
        assert calculator.history[0].operation == "Addition"
        assert calculator.history[0].operand1 == Decimal("2")
        assert calculator.history[0].operand2 == Decimal("3")
        assert calculator.history[0].result == Decimal("5")
    except OperationError:
        pytest.fail("Loading history failed due to OperationError")


@patch('app.calculator.pd.read_csv', side_effect=Exception("Load failure"))
@patch('app.calculator.Path.exists', return_value=True)
def test_load_history_error(mock_exists, mock_read_csv, calculator):
    with pytest.raises(OperationError, match="Failed to load history: Load failure"):
        calculator.load_history()

            
# Test Clearing History

def test_clear_history(calculator):
    operation = OperationFactory.create_operation('add')
    calculator.set_operation(operation)
    calculator.perform_operation(2, 3)
    calculator.clear_history()
    assert calculator.history == []
    assert calculator.undo_stack == []
    assert calculator.redo_stack == []

# ----- Test Calculator REPL -----

@patch('builtins.input', side_effect=['exit'])
@patch('builtins.print')
def test_calculator_repl_exit(mock_print, mock_input):
    with patch('app.calculator.Calculator.save_history') as mock_save_history:
        calculator_repl()
        mock_save_history.assert_called_once()
        mock_print.assert_any_call("History saved successfully.")
        mock_print.assert_any_call("Goodbye!")

# Test exception while saving history during exit
@patch('builtins.input', side_effect=['exit'])
@patch('builtins.print')
def test_calculator_repl_exit_save_error(mock_print, mock_input):
    with patch('app.calculator.Calculator.save_history', side_effect=Exception("Save failed")):
        calculator_repl()

    mock_print.assert_any_call("Warning: Could not save history: Save failed")
    mock_print.assert_any_call("Goodbye!")

@patch('builtins.input', side_effect=['help', 'exit'])
@patch('builtins.print')
def test_calculator_repl_help(mock_print, mock_input):
    calculator_repl()
    mock_print.assert_any_call("\nAvailable commands:")


def test_standard_help_menu_lists_non_operation_commands():
    lines = StandardHelpMenu().get_lines()

    assert "history - Show calculation history" in lines
    assert "help - Display available commands" in lines
    assert not any("Perform calculations" in line for line in lines)


def test_help_menu_decorator_preserves_wrapped_component():
    class CustomMenu(HelpMenu):
        def get_lines(self):
            return ["custom command"]

    decorator = HelpMenuDecorator(CustomMenu())

    assert decorator.get_lines() == ["custom command"]


def test_operation_help_menu_reflects_newly_registered_operation(monkeypatch):
    class CustomOperation(Operation):
        def execute(self, a: Decimal, b: Decimal) -> Decimal:
            return a + b

    monkeypatch.setitem(
        OperationFactory._operations,
        "custom_operation",
        CustomOperation,
    )

    lines = OperationHelpDecorator(StandardHelpMenu()).get_lines()

    assert lines[0].startswith("add, subtract, multiply")
    assert "custom_operation" in lines[0]
    assert lines[1] == "history - Show calculation history"


def test_repl_help_uses_registered_operations(monkeypatch):
    class CustomOperation(Operation):
        def execute(self, a: Decimal, b: Decimal) -> Decimal:
            return a + b

    monkeypatch.setitem(
        OperationFactory._operations,
        "custom_operation",
        CustomOperation,
    )

    with patch("builtins.input", side_effect=["help", "exit"]), patch(
        "builtins.print"
    ) as mock_print:
        calculator_repl()

    mock_print.assert_any_call(
        "  add, subtract, multiply, divide, power, root, modulus, "
        "int_divide, percent, abs_diff, custom_operation - Perform calculations"
    )


@patch('builtins.input', side_effect=['add', '2', '3', 'exit'])
@patch('builtins.print')
def test_calculator_repl_addition(mock_print, mock_input):
    calculator_repl()
    mock_print.assert_any_call("\nResult: 5")


@patch(
    'builtins.input',
    side_effect=[
        'queue', 'add', '2', '3',
        'queue', 'multiply', '4', '5',
        'run_queue', 'exit',
    ],
)
@patch('builtins.print')
def test_calculator_repl_queues_and_runs_commands(mock_print, mock_input):
    calculator_repl()

    mock_print.assert_any_call("Calculation queued (1 pending)")
    mock_print.assert_any_call("Calculation queued (2 pending)")
    mock_print.assert_any_call("Result: 5")
    mock_print.assert_any_call("Result: 20")


@pytest.mark.parametrize(
    "input_sequence",
    [
        ['queue', 'cancel', 'exit'],
        ['queue', 'add', 'cancel', 'exit'],
        ['queue', 'add', '2', 'cancel', 'exit'],
    ],
)
@patch('builtins.print')
def test_calculator_repl_queue_cancellation(
    mock_print, input_sequence
):
    with patch('builtins.input', side_effect=input_sequence):
        calculator_repl()

    mock_print.assert_any_call("Operation cancelled")


@patch('builtins.input', side_effect=['queue', 'unknown', 'exit'])
@patch('builtins.print')
def test_calculator_repl_queue_unknown_operation(mock_print, mock_input):
    calculator_repl()

    mock_print.assert_any_call("Error: Unknown operation: unknown")


@patch('builtins.input', side_effect=['run_queue', 'exit'])
@patch('builtins.print')
def test_calculator_repl_run_empty_queue(mock_print, mock_input):
    calculator_repl()

    mock_print.assert_any_call("No queued calculations")


@patch('builtins.input', side_effect=['queue', 'multiply', '0', '4', 'run_queue', 'exit'])
@patch('builtins.print')
def test_calculator_repl_runs_zero_result_from_queue(mock_print, mock_input):
    calculator_repl()

    mock_print.assert_any_call("Result: 0")


@patch('builtins.input', side_effect=['queue', 'add', '2', '3', 'run_queue', 'exit'])
@patch('builtins.print')
def test_calculator_repl_queued_non_decimal_result(mock_print, mock_input):
    with patch(
        'app.calculator.Calculator.perform_operation',
        return_value=42,
    ):
        calculator_repl()

    mock_print.assert_any_call("Result: 42")


@patch(
    'builtins.input',
    side_effect=['queue', 'divide', '1', '0', 'run_queue', 'exit'],
)
@patch('builtins.print')
def test_calculator_repl_queue_execution_error(mock_print, mock_input):
    calculator_repl()

    assert any(
        call.args == ("Error: Division by zero is not allowed.",)
        for call in mock_print.call_args_list
    )


@patch('builtins.input', side_effect=['history', 'exit'])
@patch('builtins.print')
def test_calculator_repl_empty_history(mock_print, mock_input):
    with patch('app.calculator.Calculator.show_history', return_value=[]):
        calculator_repl()

    mock_print.assert_any_call("No calculations in history")

@patch('builtins.input', side_effect=['add', '2', '3', 'history', 'exit'])
@patch('builtins.print')
def test_calculator_repl_history(mock_print, mock_input):
    calculator_repl()

    mock_print.assert_any_call("\nCalculation History:")

@patch('builtins.input', side_effect=['clear', 'exit'])
@patch('builtins.print')
def test_calculator_repl_clear(mock_print, mock_input):
    with patch('app.calculator.Calculator.clear_history') as mock_clear:
        calculator_repl()

        mock_clear.assert_called_once()
        mock_print.assert_any_call("History cleared")

@patch('builtins.input', side_effect=['undo', 'exit'])
@patch('builtins.print')
def test_calculator_repl_undo_success(mock_print, mock_input):
    with patch('app.calculator.Calculator.undo', return_value=True):
        calculator_repl()

    mock_print.assert_any_call("Operation undone")

@patch('builtins.input', side_effect=['undo', 'exit'])
@patch('builtins.print')
def test_calculator_repl_undo_nothing(mock_print, mock_input):
    with patch('app.calculator.Calculator.undo', return_value=False):
        calculator_repl()

    mock_print.assert_any_call("Nothing to undo")

@patch('builtins.input', side_effect=['redo', 'exit'])
@patch('builtins.print')
def test_calculator_repl_redo_success(mock_print, mock_input):
    with patch('app.calculator.Calculator.redo', return_value=True):
        calculator_repl()

    mock_print.assert_any_call("Operation redone")

@patch('builtins.input', side_effect=['redo', 'exit'])
@patch('builtins.print')
def test_calculator_repl_redo_nothing(mock_print, mock_input):
    with patch('app.calculator.Calculator.redo', return_value=False):
        calculator_repl()

    mock_print.assert_any_call("Nothing to redo")

@patch('builtins.input', side_effect=['save', 'exit'])
@patch('builtins.print')
def test_calculator_repl_save(mock_print, mock_input):
    with patch('app.calculator.Calculator.save_history') as mock_save_history:
        calculator_repl()

        # Called once for "save" and once for "exit"
        assert mock_save_history.call_count == 2

    mock_print.assert_any_call("History saved successfully")

# Test exception while explicitly using the save command
@patch('builtins.input', side_effect=['save', 'exit'])
@patch('builtins.print')
def test_calculator_repl_save_error(mock_print, mock_input):
    with patch('app.calculator.Calculator.save_history', side_effect=Exception("Save failed")):
        calculator_repl()

    mock_print.assert_any_call("Error saving history: Save failed")

@patch('builtins.input', side_effect=['load', 'exit'])
@patch('builtins.print')
def test_calculator_repl_load(mock_print, mock_input):
    with patch('app.calculator.Calculator.load_history') as mock_load_history:
        calculator_repl()

    mock_load_history.assert_called()
    mock_print.assert_any_call("History loaded successfully")

# Test exception while loading history
@patch('builtins.input', side_effect=['load', 'exit'])
@patch('builtins.print')
def test_calculator_repl_load_error(mock_print, mock_input):
    with patch('app.calculator.Calculator.load_history', side_effect=Exception("Load failed")):
        calculator_repl()

    mock_print.assert_any_call("Error loading history: Load failed")

@patch('builtins.input', side_effect=['add', 'cancel', 'exit'])
@patch('builtins.print')
def test_calculator_repl_cancel_first_number(mock_print, mock_input):
    calculator_repl()

    mock_print.assert_any_call("Operation cancelled")

@patch('builtins.input', side_effect=['add', '2', 'cancel', 'exit'])
@patch('builtins.print')
def test_calculator_repl_cancel_second_number(mock_print, mock_input):
    calculator_repl()

    mock_print.assert_any_call("Operation cancelled")

@patch('builtins.input', side_effect=['divide', '10', '0', 'exit'])
@patch('builtins.print')
def test_calculator_repl_operation_error(mock_print, mock_input):
    calculator_repl()

    assert any(
        "Error:" in str(call)
        for call in mock_print.call_args_list
    )

@patch('builtins.input', side_effect=['add', 'abc', '3', 'exit'])
@patch('builtins.print')
def test_calculator_repl_validation_error(mock_print, mock_input):
    calculator_repl()

    assert any(
        "Error:" in str(call)
        for call in mock_print.call_args_list
    )

# Test non-Decimal result branch
@patch('builtins.input', side_effect=['add', '2', '3', 'exit'])
@patch('builtins.print')
def test_calculator_repl_non_decimal_result(mock_print, mock_input):
    with patch('app.calculator.Calculator.perform_operation', return_value=5):
        calculator_repl()

    mock_print.assert_any_call("\nResult: 5")

# Test unexpected exception during an operation
@patch('builtins.input', side_effect=['add', '2', '3', 'exit'])
@patch('builtins.print')
def test_calculator_repl_unexpected_operation_error(mock_print, mock_input):
    with patch('app.calculator.Calculator.perform_operation', side_effect=Exception("Unexpected operation failure")):
        calculator_repl()

    mock_print.assert_any_call("Unexpected error: Unexpected operation failure")

@patch('builtins.input', side_effect=['unknown', 'exit'])
@patch('builtins.print')
def test_calculator_repl_unknown_command(mock_print, mock_input):
    calculator_repl()

    mock_print.assert_any_call("Unknown command: 'unknown'. Type 'help' for available commands.")

@patch('builtins.input', side_effect=KeyboardInterrupt)
@patch('builtins.print')
def test_calculator_repl_keyboard_interrupt(mock_print, mock_input):
    # First input raises KeyboardInterrupt. The REPL catches it and
    # continues, so the next input needs to eventually terminate it.
    mock_input.side_effect = [KeyboardInterrupt, 'exit']

    calculator_repl()

    mock_print.assert_any_call("\nOperation cancelled")

@patch('builtins.input', side_effect=EOFError)
@patch('builtins.print')
def test_calculator_repl_eof_error(mock_print, mock_input):
    calculator_repl()

    mock_print.assert_any_call("\nInput terminated. Exiting...")

# Test unexpected exception in the main command-processing loop
@patch('builtins.input', side_effect=['help', 'exit'])
@patch('builtins.print')
def test_calculator_repl_unexpected_command_error(mock_print, mock_input):
    with patch('app.calculator.Calculator.show_history', side_effect=Exception("Unexpected command failure")):
        
        # Trigger the history command instead of help
        mock_input.side_effect = ['history', 'exit']

        calculator_repl()

    mock_print.assert_any_call("Error: Unexpected command failure")

@patch('builtins.print')
@patch('app.calculator.Calculator')
def test_calculator_repl_initialization_error(mock_calculator, mock_print):
    mock_calculator.side_effect = Exception("Initialization failed")

    with pytest.raises(Exception, match="Initialization failed"):
        calculator_repl()

    mock_print.assert_any_call("Fatal error: Initialization failed")
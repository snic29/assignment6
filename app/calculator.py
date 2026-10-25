from decimal import Decimal
from pathlib import Path
import sys
from typing import List, Optional, Union

from colorama import Fore, Style, just_fix_windows_console
import pandas as pd

from app.calculation import Calculation
from app.calculator_config import CalculatorConfig
from app.commands import CalculateCommand, CommandInvoker
from app.calculator_memento import CalculatorMemento
from app.exceptions import OperationError, ValidationError
from app.history import HistoryObserver, AutoSaveObserver, LoggingObserver
from app.input_validators import InputValidator
from app.logger import Logger
from app.operations import Operation, OperationFactory

# Type aliases for better readability
Number = Union[int, float, Decimal]
CalculationResult = Union[Number, str]


def _colorize(message: str, color: str) -> str:
    if not sys.stdout.isatty():
        return message
    return f"{color}{message}{Style.RESET_ALL}"


class Calculator:
    """
    Main calculator class implementing multiple design patterns.

    This class serves as the core of the calculator application, managing operations,
    calculation history, observers, configuration settings, and data persistence.
    It integrates various design patterns to enhance flexibility, maintainability, and
    scalability.
    """

    def __init__(self, config: Optional[CalculatorConfig] = None):
        """
        Initialize calculator with configuration.

        Args:
            config (Optional[CalculatorConfig], optional): Configuration settings for the calculator.
                If not provided, default settings are loaded based on environment variables.
        """
        if config is None:
            # Determine the project root directory if no configuration is provided
            current_file = Path(__file__)
            project_root = current_file.parent.parent
            config = CalculatorConfig(base_dir=project_root)

        # Assign the configuration and validate its parameters
        self.config = config
        self.config.validate()

        # Set up the logging system
        self._setup_logging()

        # Initialize calculation history and operation strategy
        self.history: List[Calculation] = []
        self.operation_strategy: Optional[Operation] = None

        # Initialize observer list for the Observer pattern
        self.observers: List[HistoryObserver] = []

        # Initialize stacks for undo and redo functionality using the Memento pattern
        self.undo_stack: List[CalculatorMemento] = []
        self.redo_stack: List[CalculatorMemento] = []

        # Create required directories for history management
        self._setup_directories()

        try:
            # Attempt to load existing calculation history from file
            self.load_history()
        except Exception as e:
            # Log a warning if history could not be loaded
            Logger.warning(f"Could not load existing history: {e}")

        # Log the successful initialization of the calculator
        Logger.info("Calculator initialized with configuration")

    def _setup_logging(self) -> None:
        """
        Configure the logging system.

        Sets up logging to a file with a specified format and log level.
        """
        try:
            Logger.configure(self.config.log_file, self.config.default_encoding)
        except Exception as e:
            # Print an error message and re-raise the exception if logging setup fails
            print(_colorize(f"Error setting up logging: {e}", Fore.RED))
            raise

    def _setup_directories(self) -> None:
        """
        Create required directories.

        Ensures that all necessary directories for history management exist.
        """
        self.config.history_dir.mkdir(parents=True, exist_ok=True)

    def add_observer(self, observer: HistoryObserver) -> None:
        """
        Register a new observer.

        Adds an observer to the list, allowing it to receive updates when new
        calculations are performed.

        Args:
            observer (HistoryObserver): The observer to be added.
        """
        self.observers.append(observer)
        Logger.info(f"Added observer: {observer.__class__.__name__}")

    def remove_observer(self, observer: HistoryObserver) -> None:
        """
        Remove an existing observer.

        Removes an observer from the list, preventing it from receiving further updates.

        Args:
            observer (HistoryObserver): The observer to be removed.
        """
        self.observers.remove(observer)
        Logger.info(f"Removed observer: {observer.__class__.__name__}")

    def notify_observers(self, calculation: Calculation) -> None:
        """
        Notify all observers of a new calculation.

        Iterates through the list of observers and calls their update method,
        passing the new calculation as an argument.

        Args:
            calculation (Calculation): The latest calculation performed.
        """
        for observer in self.observers:
            observer.update(calculation)

    def set_operation(self, operation: Operation) -> None:
        """
        Set the current operation strategy.

        Assigns the operation strategy that will be used for performing calculations.
        This is part of the Strategy pattern, allowing the calculator to switch between
        different operation algorithms dynamically.

        Args:
            operation (Operation): The operation strategy to be set.
        """
        self.operation_strategy = operation
        Logger.info(f"Set operation: {operation}")

    def perform_operation(
        self,
        a: Union[str, Number],
        b: Union[str, Number]
    ) -> CalculationResult:
        """
        Perform calculation with the current operation.

        Validates and sanitizes user inputs, executes the calculation using the
        current operation strategy, updates the history, and notifies observers.

        Args:
            a (Union[str, Number]): The first operand, can be a string or a numeric type.
            b (Union[str, Number]): The second operand, can be a string or a numeric type.

        Returns:
            CalculationResult: The result of the calculation.

        Raises:
            OperationError: If no operation is set or if the operation fails.
            ValidationError: If input validation fails.
        """
        if not self.operation_strategy:
            raise OperationError("No operation set")

        try:
            # Validate and convert inputs to Decimal
            validated_a = InputValidator.validate_number(a, self.config)
            validated_b = InputValidator.validate_number(b, self.config)

            # Execute the operation strategy
            result = self.operation_strategy.execute(validated_a, validated_b)

            # Create a new Calculation instance with the operation details
            calculation = Calculation(
                operation=str(self.operation_strategy),
                operand1=validated_a,
                operand2=validated_b
            )

            # Save the current state to the undo stack before making changes
            self.undo_stack.append(CalculatorMemento(self.history.copy()))

            # Clear the redo stack since new operation invalidates the redo history
            self.redo_stack.clear()

            # Append the new calculation to the history
            self.history.append(calculation)

            # Ensure the history does not exceed the maximum size
            if len(self.history) > self.config.max_history_size:
                self.history.pop(0)

            # Notify all observers about the new calculation
            self.notify_observers(calculation)

            return result

        except ValidationError as e:
            # Log and re-raise validation errors
            Logger.error(f"Validation error: {str(e)}")
            raise
        except Exception as e:
            # Log and raise operation errors for any other exceptions
            Logger.error(f"Operation failed: {str(e)}")
            raise OperationError(f"Operation failed: {str(e)}")

    def save_history(self) -> None:
        """
        Save calculation history to a CSV file using pandas.

        Serializes the history of calculations and writes them to a CSV file for
        persistent storage. Utilizes pandas DataFrames for efficient data handling.

        Raises:
            OperationError: If saving the history fails.
        """
        try:
            # Ensure the history directory exists
            self.config.history_dir.mkdir(parents=True, exist_ok=True)

            history_data = []
            for calc in self.history:
                # Serialize each Calculation instance to a dictionary
                history_data.append({
                    'operation': str(calc.operation),
                    'operand1': str(calc.operand1),
                    'operand2': str(calc.operand2),
                    'result': str(calc.result),
                    'timestamp': calc.timestamp.isoformat()
                })

            if history_data:
                # Create a pandas DataFrame from the history data
                df = pd.DataFrame(history_data)
                # Write the DataFrame to a CSV file without the index
                df.to_csv(self.config.history_file, index=False)
                Logger.info(f"History saved successfully to {self.config.history_file}")
            else:
                # If history is empty, create an empty CSV with headers
                pd.DataFrame(columns=['operation', 'operand1', 'operand2', 'result', 'timestamp']
                           ).to_csv(self.config.history_file, index=False)
                Logger.info("Empty history saved")

        except Exception as e:
            # Log and raise an OperationError if saving fails
            Logger.error(f"Failed to save history: {e}")
            raise OperationError(f"Failed to save history: {e}")

    def load_history(self) -> None:
        """
        Load calculation history from a CSV file using pandas.

        Reads the calculation history from a CSV file and reconstructs the
        Calculation instances, restoring the calculator's history.

        Raises:
            OperationError: If loading the history fails.
        """
        try:
            if self.config.history_file.exists():
                # Read the CSV file into a pandas DataFrame
                df = pd.read_csv(self.config.history_file)
                if not df.empty:
                    # Deserialize each row into a Calculation instance
                    self.history = [
                        Calculation.from_dict({
                            'operation': row['operation'],
                            'operand1': row['operand1'],
                            'operand2': row['operand2'],
                            'result': row['result'],
                            'timestamp': row['timestamp']
                        })
                        for _, row in df.iterrows()
                    ]
                    Logger.info(f"Loaded {len(self.history)} calculations from history")
                else:
                    Logger.info("Loaded empty history file")
            else:
                # If no history file exists, start with an empty history
                Logger.info("No history file found - starting with empty history")
        except Exception as e:
            # Log and raise an OperationError if loading fails
            Logger.error(f"Failed to load history: {e}")
            raise OperationError(f"Failed to load history: {e}")

    def get_history_dataframe(self) -> pd.DataFrame:
        """
        Get calculation history as a pandas DataFrame.

        Converts the list of Calculation instances into a pandas DataFrame for
        advanced data manipulation or analysis.

        Returns:
            pd.DataFrame: DataFrame containing the calculation history.
        """
        history_data = []
        for calc in self.history:
            history_data.append({
                'operation': str(calc.operation),
                'operand1': str(calc.operand1),
                'operand2': str(calc.operand2),
                'result': str(calc.result),
                'timestamp': calc.timestamp
            })
        return pd.DataFrame(history_data)

    def show_history(self) -> List[str]:
        """
        Get formatted history of calculations.

        Returns a list of human-readable strings representing each calculation.

        Returns:
            List[str]: List of formatted calculation history entries.
        """
        return [str(calc) for calc in self.history]

    def clear_history(self) -> None:
        """
        Clear calculation history.

        Empties the calculation history and clears the undo and redo stacks.
        """
        self.history.clear()
        self.undo_stack.clear()
        self.redo_stack.clear()
        Logger.info("History cleared")

    def undo(self) -> bool:
        """
        Undo the last operation.

        Restores the calculator's history to the state before the last calculation
        was performed.

        Returns:
            bool: True if an operation was undone, False if there was nothing to undo.
        """
        if not self.undo_stack:
            return False
        # Pop the last state from the undo stack
        memento = self.undo_stack.pop()
        # Push the current state onto the redo stack
        self.redo_stack.append(CalculatorMemento(self.history.copy()))
        # Restore the history from the memento
        self.history = memento.history.copy()
        return True

    def redo(self) -> bool:
        """
        Redo the previously undone operation.

        Restores the calculator's history to the state before the last undo.

        Returns:
            bool: True if an operation was redone, False if there was nothing to redo.
        """
        if not self.redo_stack:
            return False
        # Pop the last state from the redo stack
        memento = self.redo_stack.pop()
        # Push the current state onto the undo stack
        self.undo_stack.append(CalculatorMemento(self.history.copy()))
        # Restore the history from the memento
        self.history = memento.history.copy()
        return True

def calculator_repl():
    """
    Command-line interface for the calculator.

    Implements a Read-Eval-Print Loop (REPL) that continuously prompts the user
    for commands, processes arithmetic operations, and manages calculation history.
    """
    try:
        just_fix_windows_console()

        # Initialize the Calculator instance
        calc = Calculator()

        # Register observers for logging and auto-saving history
        calc.add_observer(LoggingObserver())
        calc.add_observer(AutoSaveObserver(calc))
        invoker = CommandInvoker()

        print(_colorize("Calculator started. Type 'help' for commands.", Fore.CYAN))

        while True:
            try:
                # Prompt the user for a command
                command = input(_colorize("\nEnter command: ", Fore.CYAN)).lower().strip()

                if command == 'help':
                    # Display available commands
                    print(_colorize("\nAvailable commands:", Fore.CYAN))
                    print(_colorize(
                        "  add, subtract, multiply, divide, power, root, modulus, "
                        "int_divide, percent, abs_diff - Perform calculations",
                        Fore.CYAN,
                    ))
                    print(_colorize("  history - Show calculation history", Fore.CYAN))
                    print(_colorize("  clear - Clear calculation history", Fore.CYAN))
                    print(_colorize("  undo - Undo the last calculation", Fore.CYAN))
                    print(_colorize("  redo - Redo the last undone calculation", Fore.CYAN))
                    print(_colorize("  save - Save calculation history to file", Fore.CYAN))
                    print(_colorize("  load - Load calculation history from file", Fore.CYAN))
                    print(_colorize("  queue - Add a calculation to the command queue", Fore.CYAN))
                    print(_colorize("  run_queue - Execute queued calculations in order", Fore.CYAN))
                    print(_colorize("  help - Display available commands", Fore.CYAN))
                    print(_colorize("  exit - Exit the calculator", Fore.CYAN))
                    continue

                if command == 'exit':
                    # Attempt to save history before exiting
                    try:
                        calc.save_history()
                        print(_colorize("History saved successfully.", Fore.GREEN))
                    except Exception as e:
                        print(_colorize(f"Warning: Could not save history: {e}", Fore.YELLOW))
                    print(_colorize("Goodbye!", Fore.CYAN))
                    break

                if command == 'history':
                    # Display calculation history
                    history = calc.show_history()
                    if not history:
                        print(_colorize("No calculations in history", Fore.YELLOW))
                    else:
                        print(_colorize("\nCalculation History:", Fore.CYAN))
                        for i, entry in enumerate(history, 1):
                            print(_colorize(f"{i}. {entry}", Fore.WHITE))
                    continue

                if command == 'clear':
                    # Clear calculation history
                    calc.clear_history()
                    print(_colorize("History cleared", Fore.GREEN))
                    continue

                if command == 'undo':
                    # Undo the last calculation
                    if calc.undo():
                        print(_colorize("Operation undone", Fore.GREEN))
                    else:
                        print(_colorize("Nothing to undo", Fore.YELLOW))
                    continue

                if command == 'redo':
                    # Redo the last undone calculation
                    if calc.redo():
                        print(_colorize("Operation redone", Fore.GREEN))
                    else:
                        print(_colorize("Nothing to redo", Fore.YELLOW))
                    continue

                if command == 'save':
                    # Save calculation history to file
                    try:
                        calc.save_history()
                        print(_colorize("History saved successfully", Fore.GREEN))
                    except Exception as e:
                        print(_colorize(f"Error saving history: {e}", Fore.RED))
                    continue

                if command == 'load':
                    # Load calculation history from file
                    try:
                        calc.load_history()
                        print(_colorize("History loaded successfully", Fore.GREEN))
                    except Exception as e:
                        print(_colorize(f"Error loading history: {e}", Fore.RED))
                    continue

                if command == 'queue':
                    try:
                        operation_name = input(
                            _colorize("Operation to queue: ", Fore.CYAN)
                        ).lower().strip()
                        if operation_name == 'cancel':
                            print(_colorize("Operation cancelled", Fore.YELLOW))
                            continue
                        operation = OperationFactory.create_operation(operation_name)
                        a = input(_colorize("First number: ", Fore.CYAN))
                        if a.lower() == 'cancel':
                            print(_colorize("Operation cancelled", Fore.YELLOW))
                            continue
                        b = input(_colorize("Second number: ", Fore.CYAN))
                        if b.lower() == 'cancel':
                            print(_colorize("Operation cancelled", Fore.YELLOW))
                            continue
                        invoker.enqueue(CalculateCommand(calc, operation, a, b))
                        print(_colorize(
                            f"Calculation queued ({invoker.queued_count} pending)",
                            Fore.GREEN,
                        ))
                    except (ValidationError, OperationError, ValueError) as e:
                        print(_colorize(f"Error: {e}", Fore.RED))
                    continue

                if command == 'run_queue':
                    try:
                        results = invoker.execute_queue()
                        if not results:
                            print(_colorize("No queued calculations", Fore.YELLOW))
                        else:
                            for result in results:
                                if isinstance(result, Decimal):
                                    result = format(
                                        result,
                                        f".{calc.config.precision}f",
                                    ).rstrip("0").rstrip(".")
                                print(_colorize(f"Result: {result}", Fore.GREEN))
                    except (ValidationError, OperationError) as e:
                        print(_colorize(f"Error: {e}", Fore.RED))
                    continue

                if command in ['add', 'subtract', 'multiply', 'divide', 'power', 'root', 'modulus', 'int_divide', 'percent', 'abs_diff']:
                    # Perform the specified arithmetic operation
                    try:
                        print(_colorize("\nEnter numbers (or 'cancel' to abort):", Fore.CYAN))
                        a = input(_colorize("First number: ", Fore.CYAN))
                        if a.lower() == 'cancel':
                            print(_colorize("Operation cancelled", Fore.YELLOW))
                            continue
                        b = input(_colorize("Second number: ", Fore.CYAN))
                        if b.lower() == 'cancel':
                            print(_colorize("Operation cancelled", Fore.YELLOW))
                            continue

                        # Create the operation and encapsulate the request as a command.
                        operation = OperationFactory.create_operation(command)
                        calculate_command = CalculateCommand(
                            calc, operation, a, b
                        )
                        result = invoker.execute(calculate_command)

                        # Format Decimal results with the configured precision.
                        if isinstance(result, Decimal):
                            result = calc.history[-1].format_result(
                                calc.config.precision
                            )

                        print(_colorize(f"\nResult: {result}", Fore.GREEN))
                    except (ValidationError, OperationError) as e:
                        # Handle known exceptions related to validation or operation errors
                        print(_colorize(f"Error: {e}", Fore.RED))
                    except Exception as e:
                        # Handle any unexpected exceptions
                        print(_colorize(f"Unexpected error: {e}", Fore.RED))
                    continue

                # Handle unknown commands
                print(_colorize(
                    f"Unknown command: '{command}'. Type 'help' for available commands.",
                    Fore.YELLOW,
                ))

            except KeyboardInterrupt:
                # Handle Ctrl+C interruption gracefully
                print(_colorize("\nOperation cancelled", Fore.YELLOW))
                continue
            except EOFError:
                # Handle end-of-file (e.g., Ctrl+D) gracefully
                print(_colorize("\nInput terminated. Exiting...", Fore.YELLOW))
                break
            except Exception as e:
                # Handle any other unexpected exceptions
                print(_colorize(f"Error: {e}", Fore.RED))
                continue

    except Exception as e:
        # Handle fatal errors during initialization
        print(_colorize(f"Fatal error: {e}", Fore.RED))
        Logger.error(f"Fatal error in calculator REPL: {e}")
        raise
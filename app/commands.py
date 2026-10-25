from abc import ABC, abstractmethod
from collections import deque
from decimal import Decimal
from typing import Deque, List, Protocol, Union

from app.operations import Operation


CalculationResult = Union[int, float, Decimal, str]


class CalculatorReceiver(Protocol):
    def set_operation(self, operation: Operation) -> None:
        ...  # pragma: no cover

    def perform_operation(
        self,
        a: Union[str, int, float, Decimal],
        b: Union[str, int, float, Decimal],
    ) -> CalculationResult:
        ...  # pragma: no cover


class Command(ABC):
    """An executable request handled by the calculator."""

    @abstractmethod
    def execute(self) -> CalculationResult:
        """Run the request and return its result."""


class CalculateCommand(Command):
    """Encapsulate a calculator operation and its two operands."""

    def __init__(
        self,
        receiver: CalculatorReceiver,
        operation: Operation,
        a: Union[str, int, float, Decimal],
        b: Union[str, int, float, Decimal],
    ) -> None:
        self.receiver = receiver
        self.operation = operation
        self.a = a
        self.b = b

    def execute(self) -> CalculationResult:
        self.receiver.set_operation(self.operation)
        return self.receiver.perform_operation(self.a, self.b)


class CommandInvoker:
    """Execute commands immediately or retain them for FIFO execution."""

    def __init__(self) -> None:
        self._queue: Deque[Command] = deque()

    @property
    def queued_count(self) -> int:
        return len(self._queue)

    def execute(self, command: Command) -> CalculationResult:
        return command.execute()

    def enqueue(self, command: Command) -> None:
        self._queue.append(command)

    def execute_queue(self) -> List[CalculationResult]:
        results: List[CalculationResult] = []
        while self._queue:
            command = self._queue.popleft()
            try:
                results.append(command.execute())
            except Exception:
                self._queue.appendleft(command)
                raise
        return results

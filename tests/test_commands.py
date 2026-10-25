from decimal import Decimal
from unittest.mock import Mock

import pytest

from app.commands import CalculateCommand, Command, CommandInvoker
from app.exceptions import ValidationError
from app.operations import Addition


def test_calculate_command_sets_operation_and_executes_parameters():
    receiver = Mock()
    receiver.perform_operation.return_value = Decimal("5")
    command = CalculateCommand(receiver, Addition(), "2", "3")

    assert command.execute() == Decimal("5")
    receiver.set_operation.assert_called_once_with(command.operation)
    receiver.perform_operation.assert_called_once_with("2", "3")


def test_invoker_executes_command_immediately():
    command = Mock(spec=Command)
    command.execute.return_value = Decimal("5")
    invoker = CommandInvoker()

    assert invoker.execute(command) == Decimal("5")
    command.execute.assert_called_once_with()


def test_invoker_executes_queued_commands_in_fifo_order():
    first = Mock(spec=Command)
    first.execute.return_value = Decimal("5")
    second = Mock(spec=Command)
    second.execute.return_value = Decimal("9")
    invoker = CommandInvoker()

    invoker.enqueue(first)
    invoker.enqueue(second)

    assert invoker.queued_count == 2
    assert invoker.execute_queue() == [Decimal("5"), Decimal("9")]
    assert invoker.queued_count == 0
    first.execute.assert_called_once_with()
    second.execute.assert_called_once_with()


def test_invoker_keeps_failed_and_remaining_commands_queued():
    failed = Mock(spec=Command)
    failed.execute.side_effect = ValidationError("Invalid operand")
    remaining = Mock(spec=Command)
    invoker = CommandInvoker()

    invoker.enqueue(failed)
    invoker.enqueue(remaining)

    with pytest.raises(ValidationError, match="Invalid operand"):
        invoker.execute_queue()

    assert invoker.queued_count == 2
    remaining.execute.assert_not_called()

    failed.execute.side_effect = None
    failed.execute.return_value = Decimal("5")
    assert invoker.execute_queue() == [Decimal("5"), remaining.execute.return_value]
    remaining.execute.assert_called_once_with()


def test_invoker_empty_queue_returns_no_results():
    assert CommandInvoker().execute_queue() == []

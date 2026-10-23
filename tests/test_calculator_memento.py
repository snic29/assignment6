import pytest
from decimal import Decimal
from datetime import datetime
from app.calculation import Calculation
from app.calculator_memento import CalculatorMemento

def test_calculator_memento_to_dict():
    calculation = Calculation(
        operation="Addition",
        operand1=Decimal("2"),
        operand2=Decimal("3")
    )

    timestamp = datetime(2026, 1, 1, 12, 0, 0)

    memento = CalculatorMemento(
        history=[calculation],
        timestamp=timestamp
    )

    result = memento.to_dict()

    assert result['timestamp'] == '2026-01-01T12:00:00'
    assert len(result['history']) == 1
    assert result['history'][0] == calculation.to_dict()


def test_calculator_memento_from_dict():
    calculation = Calculation(
        operation="Addition",
        operand1=Decimal("2"),
        operand2=Decimal("3")
    )

    data = {
        'history': [calculation.to_dict()],
        'timestamp': '2026-01-01T12:00:00'
    }

    memento = CalculatorMemento.from_dict(data)

    assert len(memento.history) == 1
    assert memento.history[0].operation == "Addition"
    assert memento.history[0].operand1 == Decimal("2")
    assert memento.history[0].operand2 == Decimal("3")
    assert memento.history[0].result == Decimal("5")
    assert memento.timestamp == datetime(2026, 1, 1, 12, 0, 0)
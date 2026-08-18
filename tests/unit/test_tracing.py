from __future__ import annotations

import sys
from unittest.mock import MagicMock, patch

from pipeline.tracing import setup_tracing


def test_setup_tracing_success():
    mock_px = MagicMock()
    mock_register = MagicMock()
    mock_instrumentor_instance = MagicMock()
    mock_instrumentor_cls = MagicMock(return_value=mock_instrumentor_instance)

    mock_otel_module = MagicMock()
    mock_otel_module.register = mock_register

    mock_openinference_module = MagicMock()
    mock_openinference_module.AnthropicInstrumentor = mock_instrumentor_cls

    modules = {
        "phoenix": mock_px,
        "phoenix.otel": mock_otel_module,
        "openinference.instrumentation.anthropic": mock_openinference_module,
    }
    with patch.dict(sys.modules, modules):
        result = setup_tracing("test-project")

    assert result is True
    mock_px.launch_app.assert_called_once()
    mock_register.assert_called_once_with(
        project_name="test-project",
        endpoint="http://localhost:6006/v1/traces",
        auto_instrument=True,
    )
    mock_instrumentor_instance.instrument.assert_called_once()


def test_setup_tracing_failure_returns_false(capsys):
    mock_px = MagicMock()
    mock_px.launch_app.side_effect = RuntimeError("Phoenix unavailable")

    with patch.dict(sys.modules, {"phoenix": mock_px}):
        result = setup_tracing("test-project")

    assert result is False
    captured = capsys.readouterr()
    assert "Warning" in captured.err

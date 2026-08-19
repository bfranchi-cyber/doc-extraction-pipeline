from __future__ import annotations

import sys
from unittest.mock import AsyncMock, MagicMock, patch

import pytest


@pytest.fixture()
def agent(monkeypatch):
    monkeypatch.setenv("MEDIUM_MODEL", "claude-test-model")
    monkeypatch.setenv("PHOENIX_HOST", "localhost:6006")

    mock_anthropic_module = MagicMock()
    mock_anthropic_client = MagicMock()
    mock_anthropic_module.AsyncAnthropic.return_value = mock_anthropic_client

    with patch.dict(sys.modules, {"anthropic": mock_anthropic_module}):
        from eval.eval_agent import EvalAgent
        a = EvalAgent()
        a._client = mock_anthropic_client
        return a, mock_anthropic_client


@pytest.mark.asyncio
async def test_judge_span_correct(agent):
    eval_agent, mock_client = agent
    mock_response = MagicMock()
    mock_response.content = [MagicMock(text="correct")]
    mock_client.messages.create = AsyncMock(return_value=mock_response)

    span = {
        "attributes": {"document.name": "test.md", "eval.category": "Coding"},
        "input.value": "Some python code snippet",
    }
    result = await eval_agent._judge_span(span)
    assert result == "correct"


@pytest.mark.asyncio
async def test_judge_span_incorrect(agent):
    eval_agent, mock_client = agent
    mock_response = MagicMock()
    mock_response.content = [MagicMock(text="incorrect")]
    mock_client.messages.create = AsyncMock(return_value=mock_response)

    span = {
        "attributes": {"document.name": "architecture.md", "eval.category": "Coding"},
        "input.value": "A system design document about microservices",
    }
    result = await eval_agent._judge_span(span)
    assert result == "incorrect"


@pytest.mark.asyncio
async def test_judge_span_api_failure_returns_skipped(agent):
    eval_agent, mock_client = agent
    mock_client.messages.create = AsyncMock(side_effect=Exception("API timeout"))

    span = {
        "attributes": {"document.name": "test.md", "eval.category": "Cloud"},
        "input.value": "Some content",
    }
    result = await eval_agent._judge_span(span)
    assert result == "skipped"


@pytest.mark.asyncio
async def test_run_evals_no_spans(agent, monkeypatch):
    eval_agent, _ = agent

    mock_px = MagicMock()
    mock_client_instance = MagicMock()
    mock_client_instance.get_spans_dataframe.return_value = None
    mock_px.Client.return_value = mock_client_instance

    with patch.dict(sys.modules, {"phoenix": mock_px}):
        result = await eval_agent.run_evals()

    assert result == {"evaluated": 0, "correct": 0, "incorrect": 0}

from __future__ import annotations

import sys
from pathlib import Path
from unittest.mock import AsyncMock, MagicMock, patch

import pytest


@pytest.fixture()
def vault_root(tmp_path: Path) -> Path:
    vault = tmp_path / "vault"
    vault.mkdir()
    for cat in ("Architecture", "Cloud", "Coding"):
        (vault / cat).mkdir()
    return vault


@pytest.fixture()
def agent(monkeypatch, vault_root: Path):
    monkeypatch.setenv("MEDIUM_MODEL", "claude-test-model")
    monkeypatch.setenv("PHOENIX_HOST", "localhost:6006")

    mock_anthropic_module = MagicMock()
    mock_anthropic_client = MagicMock()
    mock_anthropic_module.AsyncAnthropic.return_value = mock_anthropic_client

    with patch.dict(sys.modules, {"anthropic": mock_anthropic_module}):
        from eval.eval_agent import EvalAgent
        a = EvalAgent(vault_root=vault_root)
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


@pytest.mark.asyncio
async def test_judge_prompt_includes_discovered_categories(agent):
    """Judge prompt should reference categories discovered from vault_root."""
    eval_agent, mock_client = agent
    mock_response = MagicMock()
    mock_response.content = [MagicMock(text="correct")]
    mock_client.messages.create = AsyncMock(return_value=mock_response)

    span = {
        "attributes": {"document.name": "test.md", "eval.category": "Cloud"},
        "input.value": "Cloud content",
    }
    await eval_agent._judge_span(span)

    call_kwargs = mock_client.messages.create.call_args.kwargs
    prompt_text = call_kwargs["messages"][0]["content"]
    assert "Architecture" in prompt_text or "Cloud" in prompt_text or "Coding" in prompt_text


@pytest.mark.asyncio
async def test_eval_agent_without_vault_root_omits_category_list(monkeypatch):
    """EvalAgent with vault_root=None should not include a category list in the prompt."""
    monkeypatch.setenv("MEDIUM_MODEL", "claude-test-model")

    mock_anthropic_module = MagicMock()
    mock_anthropic_client = MagicMock()
    mock_anthropic_module.AsyncAnthropic.return_value = mock_anthropic_client
    mock_response = MagicMock()
    mock_response.content = [MagicMock(text="correct")]
    mock_anthropic_client.messages.create = AsyncMock(return_value=mock_response)

    with patch.dict(sys.modules, {"anthropic": mock_anthropic_module}):
        from eval.eval_agent import EvalAgent
        a = EvalAgent(vault_root=None)
        a._client = mock_anthropic_client

    span = {
        "attributes": {"document.name": "test.md", "eval.category": "Cloud"},
        "input.value": "content",
    }
    await a._judge_span(span)

    call_kwargs = mock_anthropic_client.messages.create.call_args.kwargs
    prompt_text = call_kwargs["messages"][0]["content"]
    assert "Valid categories" not in prompt_text

from __future__ import annotations

import sys

import opentelemetry.trace as trace


def setup_tracing(project_name: str) -> bool:
    """Launch Phoenix in-process and register the OTEL provider.

    Returns True on success, False on any exception (logs warning to stderr).
    """
    try:
        import phoenix as px
        from openinference.instrumentation.anthropic import AnthropicInstrumentor
        from phoenix.otel import register

        px.launch_app()
        register(project_name=project_name, endpoint="http://localhost:6006/v1/traces", auto_instrument=True)
        AnthropicInstrumentor().instrument()
        return True
    except Exception as exc:
        print(f"Warning: Phoenix tracing setup failed: {exc}", file=sys.stderr)
        return False


def get_tracer(name: str = __name__) -> trace.Tracer:
    """Return an OTEL tracer. Falls back to a no-op tracer when no provider is configured."""
    return trace.get_tracer(name)

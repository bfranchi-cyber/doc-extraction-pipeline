# SDK Clarification Questions

You asked to use the Anthropic SDK for the agents, including those already implemented.

I have a few questions to understand the exact scope before changing any code or plans.

---

## Question 1
Which Anthropic SDK do you mean?

A) The standard `anthropic` Python package (already in `pyproject.toml` as `anthropic>=0.25`) — using `anthropic.Anthropic` / `anthropic.AsyncAnthropic` for all LLM calls

B) The **Anthropic Agents SDK** — a newer, separate package (e.g. `anthropic-agents`) that provides higher-level agent constructs (tool use loops, agent state, etc.)

C) Other (please describe after [Answer]: tag below)

[Answer]: B

---

## Question 2
What part of the SDK do you want to use for the agents?

A) Just the raw `messages.create` API (as already planned in `extraction-code-generation-plan.md`) — the change is about consistency across all agent classes, not a different API surface

B) **Tool use / function calling** — structure the agent's actions as tool calls the model dispatches

C) A specific higher-level abstraction from the SDK (e.g. an `Agent` class, an `Anthropic.beta.agents` API, a streaming interface)

D) Other (please describe after [Answer]: tag below)

[Answer]: C

---

## Question 3
Which classes do you consider "agents" that should use the Anthropic SDK?

A) Only `ExtractionAgent` (Unit 3 — not yet generated)

B) `ExtractionAgent` (Unit 3) + any future agent classes in Units 4 and 5

C) All classes named `*Agent` across all units, including `IngestionAgent` if one exists

D) Other (please describe after [Answer]: tag below)

[Answer]: B

---

## Question 4
For the units already implemented (Unit 1: Foundation, Unit 2: Ingestion), `ingestion.py` currently uses
the **Google Drive API** only — there is no Anthropic SDK usage there. What should change for already-implemented code?

A) Nothing in Units 1–2 needs changing — they don't make LLM calls; the change only affects LLM-calling agents (Unit 3 onwards)

B) Refactor `ingestion.py` to add Anthropic SDK usage for a specific purpose (please describe in Other)

C) Other (please describe after [Answer]: tag below)

[Answer]: A

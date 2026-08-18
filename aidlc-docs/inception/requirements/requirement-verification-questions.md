# Requirements Clarification — Phoenix Tracing & Eval

Please answer each question by filling in the letter choice after `[Answer]:`.
If none of the options fit, choose the last option and describe your preference.

---

## Question 1
How should Phoenix run during local development and pipeline execution?

A) In-process — call `px.launch_app()` at pipeline startup; Phoenix UI available on localhost while the process is running (simplest, no Docker required)

B) External server — connect to a separately running Phoenix instance (e.g., Docker container or remote host); pipeline only sends OTLP traces to it

C) Other (please describe after [Answer]: tag below)

[Answer]: A

---

## Question 2
Which parts of the pipeline should be traced?

A) Classification only — trace every `ClassificationAgent.classify()` call (LLM request, response, category, latency)

B) Full pipeline — trace both extraction (`Extractor.process()`) and classification in the same trace, linked by a parent span

C) Other (please describe after [Answer]: tag below)

[Answer]: B

---

## Question 3
What eval metrics do you want collected?

A) LLM-as-a-judge quality eval — for each classification, a second LLM call judges whether the assigned category is correct given the document excerpt (requires `MEDIUM_MODEL`)

B) Programmatic metrics only — no second LLM call; collect: latency per call, category distribution (% per category), unknown rate (% classified as `unknown`), API error rate

C) Both — programmatic metrics + LLM-as-a-judge quality eval

D) Other (please describe after [Answer]: tag below)

[Answer]: C 

---

## Question 4
When should evals run?

A) Online — evals run immediately after each classify() call, within the same pipeline execution

B) Offline — evals run separately after traces are collected, as a distinct CLI command or script

C) Other (please describe after [Answer]: tag below)

[Answer]: A

---

## Question 5
How should the Phoenix project be named in the UI?

A) `docs-extraction` (matches the package name)

B) `classification-agent` (matches the component name)

C) Other (please describe after [Answer]: tag below)

[Answer]: A

---

## Extension Configuration (carrying forward from previous iteration)

The following extension settings were decided in the previous cycle.
Please confirm they still apply, or override below.

| Extension | Previous Decision |
|---|---|
| Security Baseline | No |
| Resiliency Baseline | No |
| Property-Based Testing | Partial (PBT-02, 07, 08) |

## Question 6
Should the extension configuration above carry forward unchanged?

A) Yes — keep all three settings as-is

B) No — I want to change one or more (please describe after [Answer]: tag below)

[Answer]: A


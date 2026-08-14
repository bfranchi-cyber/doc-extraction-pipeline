# Requirements Clarification — Corporate Proxy

One follow-up needed to nail down the Anthropic SDK configuration.

---

## Question 1
What is the env var name that holds the **model name** in your `.env`?

A) `MODEL_NAME`

B) `ANTHROPIC_MODEL`

C) Other (please write the exact var name after [Answer]: tag below)

[Answer]: there are three env vars for different capabilities of models. LIGHT_MODEL is the one for haiku. MEDIUM_MODEL for sonnet and HEAVY_MODEL for opus

---

## Question 2
How is the **corporate proxy** configured for the Anthropic SDK?

A) Standard — `ANTHROPIC_BASE_URL` env var (the SDK picks it up automatically, nothing special in code)

B) Custom — a different env var name for the proxy URL (write the var name after [Answer]: tag below)

C) Other (please describe after [Answer]: tag below — e.g. HTTP_PROXY, custom headers, certificate, etc.)

[Answer]:  A

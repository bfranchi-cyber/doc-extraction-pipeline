# Requirements Clarification Questions
## Classification Agent — New Feature

Please answer each question by filling in the letter after `[Answer]:`.
Choose the last option and describe your preference if none of the provided options fit.

---

## Question 1
What is the absolute path to your Obsidian vault (the root folder that contains the Architecture, CI&T, Cloud, Coding, ML&AI subfolders)?

A) I will provide the path as a CLI argument at runtime (e.g. `--vault /path/to/vault`)

B) I will set it via an environment variable (e.g. `OBSIDIAN_VAULT_PATH`)

C) Other (please describe after [Answer]: tag below — e.g. hardcode it, read from a config file, etc.)

[Answer]: B

---

## Question 2
How should classification fit into the existing pipeline?

A) Integrated — classification runs automatically right after extraction in the same command (extract → classify → move, all in one `docs-extraction` call)

B) Separate command — classification is a new CLI command (e.g. `docs-classify --input <output-folder> --vault <vault-path>`) that the user runs after extraction

C) Other (please describe after [Answer]: tag below)

[Answer]: A 

---

## Question 3
What should happen when the agent cannot confidently classify a file into any of the five categories?

A) Leave the file in the output folder and log a warning — do not move it

B) Move it to a dedicated `_unclassified` folder inside the vault

C) Other (please describe after [Answer]: tag below)

[Answer]: A

---

## Question 4
How much of the extracted text should be sent to Claude Haiku for classification?

A) Full text — send the entire markdown content (most accurate, higher token cost)

B) First 2 000 characters — enough context for most documents, low token cost

C) First 500 characters — title + opening paragraph only, minimal tokens

D) Other (please describe after [Answer]: tag below)

[Answer]:  C

---

## Question 5
What rename should `ExtractionAgent` (in `extraction.py`) receive?

A) `DocxExtractor` — plain descriptive name for what the class does

B) `ExtractionTool` — matches the "tool vs agent" language the user introduced

C) `Extractor` — short and simple

D) Other (please describe after [Answer]: tag below)

[Answer]: C

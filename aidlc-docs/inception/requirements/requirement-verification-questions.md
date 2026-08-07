# Requirements Clarification Questions — Extraction Pipeline

Please answer each question by filling in the letter choice after the `[Answer]:` tag.
If none of the options fit, choose the last option (X) and describe your preference.

---

## Question 1
How should the pipeline be triggered to run?

A) Scheduled polling on a fixed interval (e.g., every hour), checking for files not modified in 5 days

B) Google Drive webhook only — triggered in real time when Drive signals a change, then checks the 5-day rule

C) Both: webhook for immediate detection + scheduled polling as a fallback

D) Manually triggered by running a script/command

X) Other (please describe after [Answer]: tag below)

[Answer]:A, But schedule pooling not for fallback. Schedule the extraction for the time of the modification + 5 days  

---

## Question 2
Where should the output Markdown files be saved inside the Obsidian vault?

A) Flat folder — all `.md` files go into one root folder inside the vault

B) Mirrored structure — replicate the Google Drive folder hierarchy inside the vault

C) Categorized by document type or metadata (e.g., tags, date, topic derived from content)

D) Configurable via a settings file — user defines the mapping

X) Other (please describe after [Answer]: tag below)

[Answer]:X, in C:\Users\bfranchi\Documents\Obsidian Vault 

---

## Question 3
How should Google Drive authentication be handled?

A) OAuth 2.0 with a local credentials file (user authenticates once, token refreshed automatically)

B) Google Service Account key (JSON key file, no interactive login required)

C) Other (please describe after [Answer]: tag below)

X) Other (please describe after [Answer]: tag below)

[Answer]: A

---

## Question 4
Which document formats should the pipeline support as input?

A) `.docx` only (as stated in the use case)

B) `.docx` and `.pdf`

C) `.docx`, `.pdf`, and `.pptx`

D) `.docx`, `.pdf`, `.pptx`, and `.xlsx`

X) Other (please describe after [Answer]: tag below)

[Answer]: B

---

## Question 5
What should the pipeline do when an extraction or API error occurs (e.g., rate limit, corrupted file)?

A) Retry with exponential backoff (up to N attempts), then log failure to scratchpad and skip the file

B) Retry with exponential backoff, then pause the entire pipeline and wait for human review

C) Skip the file immediately without retrying, log the error to scratchpad

D) Send a desktop or email notification on failure in addition to logging

X) Other (please describe after [Answer]: tag below)

[Answer]: X, handle on anthropic guidelines for error handling using the Google Drive MCP. Rate limits we will wait the necessary time for the google API. Corrupted files we will pass the information for the coordinator agent to handle it gracefully.

---

## Question 6
Where should extracted images be saved?

A) A single flat folder alongside the vault (e.g., `C:\ObsidianImages\`)

B) Mirrored sub-folders matching the document structure (e.g., `C:\ObsidianImages\FolderA\doc1\`)

C) A folder configurable via a settings file

X) Other (please describe after [Answer]: tag below)

[Answer]: X, C:\Users\bfranchi\Documents\Obsidian Images

---

## Question 7
Should the pipeline track which files have already been processed to avoid re-extracting them on the next run?

A) Yes — maintain a local state/manifest file (e.g., JSON) recording processed file IDs and their last-processed timestamp

B) Yes — use the output `.md` file's existence as the signal (re-run only if no `.md` exists for that doc)

C) No — always re-extract all eligible files on every run

X) Other (please describe after [Answer]: tag below)

[Answer]: A

---

## Question 8
Should the Markdown enhancement step (Analysis agent — Claude Sonnet 4.5) do anything beyond formatting and adding citations?

A) Formatting and citations only (as stated)

B) Also add a YAML frontmatter summary block (title, date, tags auto-generated)

C) Also produce a short abstract/summary section at the top of the document

D) B and C together (frontmatter + abstract)

X) Other (please describe after [Answer]: tag below)

[Answer]: D

---

## Question 9
How should the pipeline be packaged and run on Windows 11?

A) Python script(s) run directly from the command line (e.g., `python main.py`)

B) A single executable or batch file that wraps the Python scripts

C) A Windows background service / scheduled task that runs automatically

D) Docker container

X) Other (please describe after [Answer]: tag below)

[Answer]: C

---

## Question 10
What concurrency model should the Extraction stage use for parallel parsing?

A) Python `asyncio` with async HTTP calls to the Claude API

B) Python `concurrent.futures.ThreadPoolExecutor` (threads)

C) Python `multiprocessing` (separate processes)

D) Sequential processing is fine — no parallelism needed

X) Other (please describe after [Answer]: tag below)

[Answer]: A

---

## Question: Security Extensions
Should security extension rules be enforced for this project?

A) Yes — enforce all SECURITY rules as blocking constraints (recommended for production-grade applications)

B) No — skip all SECURITY rules (suitable for PoCs, prototypes, and experimental projects)

X) Other (please describe after [Answer]: tag below)

[Answer]:  B

---

## Question: Resiliency Extensions
Should the resiliency baseline be applied to this project?

**What this extension is.** Enabling it applies a set of **directional, design-time best practices** for building resilient systems, derived from the **AWS Well-Architected Framework (Reliability Pillar)** and resilience-review guidance. It steers requirements, design, and code toward fault tolerance, high availability, observability, and recoverability.

**What this extension is NOT.** Enabling it does **not** make your workload production-ready. It is a **starting point** — not a substitute for a formal AWS Well-Architected Review.

A) Yes — apply the resiliency baseline as directional best practices and design-time guidance

B) No — skip the resiliency baseline (suitable for PoCs, prototypes, and experimental projects)

X) Other (please describe after [Answer]: tag below)

[Answer]: B

---

## Question: Property-Based Testing Extension
Should property-based testing (PBT) rules be enforced for this project?

A) Yes — enforce all PBT rules as blocking constraints (recommended for projects with business logic, data transformations, serialization, or stateful components)

B) Partial — enforce PBT rules only for pure functions and serialization round-trips

C) No — skip all PBT rules (suitable for simple CRUD applications or thin integration layers)

X) Other (please describe after [Answer]: tag below)

[Answer]: B

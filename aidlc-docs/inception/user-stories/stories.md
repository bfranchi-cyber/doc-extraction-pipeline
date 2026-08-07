# User Stories — Extraction Pipeline

**Persona**: Bruno (The Knowledge Worker)  
**Breakdown**: Feature-Based  
**Acceptance Criteria**: Standard — 3-5 Given/When/Then scenarios per story

---

## US-01: Scheduled Eligibility Detection

**As** Bruno,  
**I want** the pipeline to automatically identify Google Drive documents that haven't been modified in 5 days,  
**So that** only stable, finalized documents are processed — never works-in-progress.

### Acceptance Criteria

**AC-01.1 — Eligible file detected**  
Given a document in Google Drive was last modified exactly 5 days ago,  
When the pipeline polling loop runs,  
Then that document appears in the eligible file list for processing.

**AC-01.2 — Recently modified file excluded**  
Given a document in Google Drive was last modified 3 days ago,  
When the pipeline polling loop runs,  
Then that document is NOT included in the eligible file list.

**AC-01.3 — Boundary: exactly 5 days**  
Given a document's last modification timestamp is exactly `now - 5 days`,  
When eligibility is evaluated,  
Then the document is considered eligible (`>=` comparison, inclusive boundary).

**AC-01.4 — Already-processed file excluded**  
Given a document is eligible by the 5-day rule but already recorded as successfully processed in the manifest,  
When the pipeline polling loop runs,  
Then that document is skipped and not added to the eligible list.

**AC-01.5 — Unsupported file type excluded**  
Given a Google Drive file is a `.gdoc`, `.xlsx`, or any format other than `.docx` or `.pdf`,  
When the pipeline scans for eligible files,  
Then that file is silently skipped and not added to the eligible list.

---

## US-02: Google Drive Authentication Setup

**As** Bruno,  
**I want** to authenticate with Google Drive once using OAuth 2.0,  
**So that** the pipeline can access my Drive files on all subsequent runs without requiring me to log in again.

### Acceptance Criteria

**AC-02.1 — First-time authentication**  
Given no OAuth token exists locally,  
When the pipeline starts for the first time,  
Then it opens a browser-based OAuth flow and saves the resulting token to a local credentials file.

**AC-02.2 — Token reuse on subsequent runs**  
Given a valid OAuth token exists locally,  
When the pipeline starts,  
Then it uses the existing token without triggering a new browser flow.

**AC-02.3 — Automatic token refresh**  
Given an OAuth access token has expired but a valid refresh token exists,  
When the pipeline attempts a Google Drive API call,  
Then the token is refreshed automatically and the API call proceeds without user intervention.

**AC-02.4 — Missing credentials file**  
Given no credentials file exists and the pipeline is run non-interactively (e.g., via Task Scheduler),  
When the pipeline starts,  
Then it logs a clear error to the scratchpad indicating credentials are missing and exits gracefully.

---

## US-03: Document Ingestion from Google Drive

**As** Bruno,  
**I want** the pipeline to download eligible documents from Google Drive,  
**So that** they are available locally for extraction processing.

### Acceptance Criteria

**AC-03.1 — Successful download**  
Given an eligible `.docx` or `.pdf` file exists in Google Drive,  
When the Ingestion Agent runs,  
Then the file is downloaded to a local temporary working directory and its metadata (ID, name, MIME type, last modified) is passed to the Coordinator.

**AC-03.2 — Google Drive API rate limit handled**  
Given the Google Drive API returns a rate-limit response (HTTP 429 or equivalent),  
When the Ingestion Agent encounters it,  
Then it waits the duration specified in the API response (retry-after) before retrying, and logs the wait event to the Coordinator scratchpad.

**AC-03.3 — Network or API error**  
Given the Google Drive API returns a non-rate-limit error (e.g., 500, timeout),  
When the Ingestion Agent encounters it,  
Then the affected file is marked as failed in the manifest, the error is logged to the scratchpad, and the pipeline continues processing other eligible files.

**AC-03.4 — Empty eligible list**  
Given no files meet the 5-day eligibility rule on a given run,  
When the Ingestion Agent completes its scan,  
Then the pipeline logs "no eligible files found" to the scratchpad and exits cleanly without error.

---

## US-04: Parallel Document Extraction

**As** Bruno,  
**I want** the pipeline to extract text content and classify each document in parallel,  
**So that** large batches of documents are processed efficiently without unnecessary waiting.

### Acceptance Criteria

**AC-04.1 — Text extraction to compact artifact**  
Given a downloaded `.docx` or `.pdf` file,  
When the Extraction Agent processes it,  
Then all text content is extracted and structured into a compact artifact containing the document text and image metadata (IDs + alt-text only — no raw image data).

**AC-04.2 — Category classification from pre-existing vault folders**  
Given the vault contains pre-defined category folders (e.g., Research, Notes, Reference),  
When the Extraction Agent classifies a document,  
Then it selects the single best-fitting category from that pre-defined list and includes it in the compact artifact.

**AC-04.3 — Image metadata extraction (no raw data)**  
Given a document contains embedded images,  
When the Extraction Agent processes it,  
Then each image is downloaded to a local temporary staging folder, and only its ID and alt-text string appear in the compact artifact — no base64 or raw binary data is included anywhere in the artifact.

**AC-04.4 — Parallel execution**  
Given multiple eligible documents are queued,  
When the Extraction stage runs,  
Then multiple Extraction Agents process documents concurrently via Python asyncio, not sequentially.

**AC-04.5 — Corrupted or unreadable file**  
Given a document cannot be parsed (corrupted file, unsupported encoding, unreadable PDF),  
When the Extraction Agent attempts to process it,  
Then the agent reports the failure to the Coordinator with a descriptive error, the file is marked as failed in the manifest, the scratchpad records the failure, and the pipeline continues with remaining documents.

**AC-04.6 — Claude API rate limit during extraction**  
Given the Claude API (Haiku 4.5) returns a rate-limit response,  
When an Extraction Agent encounters it,  
Then it follows Anthropic SDK retry guidance (respects retry-after, exponential backoff) and logs the retry to the scratchpad.

---

## US-05: Document Analysis and Enrichment

**As** Bruno,  
**I want** the extracted document content to be formatted, enriched with citations, and given a YAML frontmatter block and abstract,  
**So that** the final Markdown file is well-structured, readable, and searchable in Obsidian.

### Acceptance Criteria

**AC-05.1 — Formatting and citations**  
Given a compact artifact containing extracted document text,  
When the Analysis Agent (Sonnet 4.5) processes it,  
Then the output Markdown has clean, readable formatting and all citations/references are properly formatted — without altering the semantic content.

**AC-05.2 — YAML frontmatter generated**  
Given any document reaching the Analysis stage,  
When the Analysis Agent produces the Markdown output,  
Then the file begins with a YAML frontmatter block containing at minimum: `title`, `date`, and auto-generated `tags`.

**AC-05.3 — Abstract section generated**  
Given any document reaching the Analysis stage,  
When the Analysis Agent produces the Markdown output,  
Then a short abstract/summary section appears at the top of the document body (after the frontmatter).

**AC-05.4 — Semantic content preserved**  
Given a document with specific facts, figures, or named content,  
When the Analysis Agent enriches it,  
Then the factual content in the output Markdown matches the source document — no facts are added, removed, or altered.

**AC-05.5 — Claude API rate limit during analysis**  
Given the Claude API (Sonnet 4.5) returns a rate-limit response,  
When the Analysis Agent encounters it,  
Then it follows Anthropic SDK retry guidance and the Coordinator logs the wait to the scratchpad.

---

## US-06: Export to Obsidian Vault and Images Folder

**As** Bruno,  
**I want** the enriched Markdown file and its images to be saved to the correct locations in my Obsidian vault and images folder,  
**So that** I can immediately find and use the document inside Obsidian with all images rendering correctly.

### Acceptance Criteria

**AC-06.1 — Markdown written to correct vault category folder**  
Given an enriched Markdown file and a category assigned by the Extraction Agent,  
When the Export stage runs,  
Then the `.md` file is written to `C:\Users\bfranchi\Documents\Obsidian Vault\{category}\{filename}.md`.

**AC-06.2 — Images moved to images folder**  
Given a document had images staged in the temporary folder,  
When the Export stage runs,  
Then all images are moved to `C:\Users\bfranchi\Documents\Obsidian Images\{document-name}\` and the temporary staging files are cleaned up.

**AC-06.3 — Image URIs injected into Markdown**  
Given images have been moved to the images folder,  
When the Export stage writes the Markdown file,  
Then each image reference in the file uses an absolute local URI in the format `![Alt Text](file:///C:/Users/bfranchi/Documents/Obsidian%20Images/{document-name}/{image-file})`.

**AC-06.4 — Unknown category fallback**  
Given the Extraction Agent assigned a category that does not match any existing vault folder,  
When the Export stage attempts to write the file,  
Then the file is placed in a fallback folder (e.g., `Vault\Uncategorized\`), the issue is logged to the scratchpad, and the pipeline continues.

**AC-06.5 — Manifest updated on successful export**  
Given a document has been successfully exported,  
When the Export stage completes,  
Then the manifest JSON is updated with the file's Drive ID, name, export timestamp, and status `success`.

---

## US-07: Coordinator Handoff and Scratchpad Observability

**As** Bruno,  
**I want** the pipeline to maintain a clear log of what happened during each run,  
**So that** I can understand what was processed, what was skipped, and why any failures occurred — without reading code.

### Acceptance Criteria

**AC-07.1 — Scratchpad records each stage transition**  
Given the pipeline processes a document through all stages,  
When each stage completes and the Coordinator performs a handoff,  
Then the scratchpad log contains a timestamped entry for each stage transition (Ingestion → Extraction → Analysis → Export) for that document.

**AC-07.2 — Failures recorded with context**  
Given a stage fails for any reason (corrupted file, API error, unknown category),  
When the Coordinator handles the failure,  
Then the scratchpad records the document name, the stage that failed, and the error description.

**AC-07.3 — Run summary on completion**  
Given a pipeline run completes (all eligible files processed or skipped),  
When the Coordinator finalizes the run,  
Then the scratchpad contains a run summary: total files eligible, total processed successfully, total failed, total skipped.

**AC-07.4 — Handoff validation**  
Given a stage produces output that is structurally incomplete (e.g., missing required compact artifact fields),  
When the Coordinator attempts the handoff to the next stage,  
Then the Coordinator rejects the handoff, marks the document as failed, logs the validation error to the scratchpad, and does not pass malformed data downstream.

---

## US-08: Re-run Safety and Idempotency

**As** Bruno,  
**I want** to be able to re-run the pipeline at any time without fear of re-processing or overwriting already-completed documents,  
**So that** I can safely trigger the pipeline manually after a failure without duplicating work.

### Acceptance Criteria

**AC-08.1 — Already-processed files skipped**  
Given a document is recorded in the manifest with status `success`,  
When the pipeline runs again,  
Then that document is not downloaded, extracted, or exported again.

**AC-08.2 — Failed files retried**  
Given a document is recorded in the manifest with status `failed`,  
When the pipeline runs again and the document is still eligible (5-day rule),  
Then the pipeline retries the document from the beginning.

**AC-08.3 — Manifest survives pipeline restarts**  
Given the pipeline is interrupted mid-run (e.g., process killed),  
When the pipeline is restarted,  
Then the manifest state from before the interruption is preserved and in-progress documents at the time of interruption are retried.

**AC-08.4 — No duplicate vault files**  
Given a document was successfully exported on a previous run,  
When the pipeline runs again,  
Then no second `.md` file is created for that document in the vault.

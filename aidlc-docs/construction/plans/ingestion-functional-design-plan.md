# Functional Design Plan — Unit 2: Ingestion

## Plan Checkboxes

- [x] Step 1: Analyze unit context (done in session — all artifacts loaded)
- [x] Step 2: Collect answers to clarifying questions
- [x] Step 3: Generate functional design artifacts (business-logic-model.md, business-rules.md, domain-entities.md)
- [ ] Step 4: Present for approval

---

## Clarifying Questions

Unit 2 covers: `discover_eligible_files()`, `download_file()`, OAuth 2.0 setup, and the 5-day eligibility rule.

**Please answer by filling in the letter choice after each `[Answer]:` tag, then say "done".**

---

## Question 1
FR-02 mentions a "Google Drive MCP" integration for Drive API calls. Which approach should `ingestion.py` actually use to talk to Google Drive?

A) Standard Google API Python client library (`google-api-python-client` + `google-auth-oauthlib`) — direct HTTP SDK, no MCP

B) Google Drive MCP server — calls are made via the Anthropic MCP client (tool calls to the MCP server from within the pipeline code)

C) Other (please describe after [Answer]: tag below)

[Answer]: B, the agent calls mcp tools

---

## Question 2
`discover_eligible_files` uses `config.drive_folder_id` to scope the search. Should it search only the immediate contents of that folder, or recurse into subfolders as well?

A) Immediate children only (flat scan of the configured folder)

B) Recursive — all files in the folder tree rooted at `drive_folder_id`

C) Other (please describe after [Answer]: tag below)

[Answer]: B

---

## Question 3
When `download_file()` saves a file to `config.staging_dir`, what naming convention should be used for the local file?

A) Original Drive filename (e.g., `My Report.docx`) — simple, human-readable

B) Drive file ID as filename (e.g., `1abc2def3.docx`) — collision-safe, opaque

C) Drive file ID + original name slug (e.g., `1abc2def3_my_report.docx`) — both safe and readable

D) Other (please describe after [Answer]: tag below)

[Answer]: A

---

## Question 4
AC-03.3 says that on a network/API error during download, the affected file should be marked as `failed` in the manifest and the pipeline should continue. Should this manifest write happen **inside** `download_file()`, or should `download_file()` raise/return an error and let the **Coordinator** write the manifest record?

A) Inside `download_file()` — ingestion writes the failed manifest record directly, then returns `None`

B) `download_file()` raises a typed exception (e.g., `DownloadError`) — the Coordinator catches it and writes the manifest record

C) Other (please describe after [Answer]: tag below)

[Answer]: B

---

## Question 5
For Google Drive API rate limits (AC-03.2), `discover_eligible_files` may make multiple API calls (listing files, fetching metadata). Should rate-limit retry logic live in a shared private helper used by both functions, or independently inside each function?

A) Shared private helper `_call_with_retry(fn, *args)` used by both `discover_eligible_files` and `download_file`

B) Each function handles its own retry logic inline — simpler, no shared abstraction

C) Other (please describe after [Answer]: tag below)

[Answer]: B

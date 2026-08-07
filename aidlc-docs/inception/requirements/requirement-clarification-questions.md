# Requirements Clarification Questions — Extraction Pipeline

I found one ambiguity in your answers that needs to be resolved before I can finalize the requirements.

---

## Ambiguity: Q2 — Internal Vault Organization

Your response specified the vault root path (`C:\Users\bfranchi\Documents\Obsidian Vault`) but the original question was about *how* the Markdown files are organized **inside** the vault. The use case mentions "categorized" but doesn't define what that means structurally.

### Clarification Question 1
How should the Markdown files be organized inside the Obsidian vault?

A) Flat — all `.md` files go directly into the vault root (`C:\Users\bfranchi\Documents\Obsidian Vault\file.md`)

B) Mirrored from Google Drive — replicate the folder hierarchy from Drive inside the vault (e.g., `Vault\FolderA\SubfolderB\file.md`)

C) Single dedicated subfolder — all files go into one subfolder (e.g., `Vault\Extracted\file.md`), configurable via settings

D) Categorized by the Analysis Agent — the AI assigns a category/tag during analysis and files are placed in matching subfolders (e.g., `Vault\Research\file.md`, `Vault\Notes\file.md`)

X) Other (please describe after [Answer]: tag below)

[Answer]: X, Is exactly D but categorized by the extraction agent. Classification tasks are more intended for smaller/cheaper models

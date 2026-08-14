# Business Logic Model — Classification Agent

## Overview

The `ClassificationAgent` performs a **two-step** operation per `.md` file:

1. **Step 1 — Classify**: a text-only API call. The model responds with *only* the category name — no explanation, no verbose output. No Anthropic tools are provided in this call.
2. **Step 2 — Move**: the code validates the text response and calls `move_to_vault`, a plain Python function that executes the file move. No second API call is made.

---

## Classification Flow

```
md_file_path
     |
     v
 read content
     |
     v
 +-----------------------------------------------+
 |  STEP 1 - Classify (text-only API call)       |
 |  system: role + category list                 |
 |  user:   "Filename: {stem}\n\n{excerpt}"      |
 |  max_tokens: 20  |  no tools                  |
 +-----------------------------------------------+
     |
     v
 category = response.content[0].text.strip()
     |
     v
 validate against enum
     |
     +-- "unknown" -----> scratchpad.warn --> return False
     |
     +-- not in enum ---> scratchpad.warn --> return False
     |
     +-- valid category
             |
             v
 +-----------------------------------------------+
 |  STEP 2 - move_to_vault (Python function)     |
 |  destination_dir = vault_root / category      |
 |  destination missing? warn --> return False   |
 |  shutil.move(md_file_path, destination_dir)   |
 |  scratchpad.info --> return True              |
 +-----------------------------------------------+
```

---

## System Prompt (Step 1)

```
You are a document classifier. Given a filename and a short excerpt,
respond with ONLY one of the following category names — nothing else:

Architecture, CI&T, Cloud, Coding, ML&AI, unknown

Categories:
- Architecture: software design, system architecture, patterns, technical diagrams, ADRs
- CI&T: corporate knowledge, internal processes, methodology, organisational guidelines, agile practices
- Cloud: cloud computing, AWS, Azure, GCP, infrastructure as code, DevOps, containers
- Coding: programming, development, algorithms, software engineering, code reviews, debugging
- ML&AI: machine learning, artificial intelligence, data science, neural networks, LLMs, NLP
- unknown: use only when the content genuinely does not fit any category above

Output the category name only. No punctuation. No explanation.
```

---

## User Message Format (Step 1)

```
Filename: {stem}

{content[:500]}
```

- `stem` — `.md` filename without extension (e.g. `my-document`)
- `content[:500]` — first 500 characters of file content, stripped

---

## API Call Parameters (Step 1)

| Parameter | Value |
|---|---|
| `model` | `os.environ["LIGHT_MODEL"]` |
| `max_tokens` | 20 |
| `tools` | *(not provided)* |
| `messages` | `[{"role": "user", "content": user_message}]` |
| `system` | classification system prompt above |

---

## Response Handling (Step 1 → Step 2)

```python
category = response.content[0].text.strip()

VALID = {"Architecture", "CI&T", "Cloud", "Coding", "ML&AI", "unknown"}

if category not in VALID:
    scratchpad.warn(f"Unexpected classification response '{category}': {md_file_path.name}")
    return False

if category == "unknown":
    scratchpad.warn(f"Unclassifiable: {md_file_path.name}")
    return False

return move_to_vault(md_file_path, vault_root, category)
```

---

## move_to_vault (Python Function — Step 2)

```python
def move_to_vault(md_file_path: Path, vault_root: Path, category: str) -> bool:
    destination_dir = vault_root / category
    if not destination_dir.exists():
        scratchpad.warn(f"Vault folder missing: {destination_dir}")
        return False
    shutil.move(str(md_file_path), str(destination_dir / md_file_path.name))
    scratchpad.info(f"Classified -> {category}: {md_file_path.name}")
    return True
```

- `vault_root` — `Path(os.environ["OBSIDIAN_VAULT_PATH"])`
- destination folder must **already exist** — no auto-creation
- existing files with the same name at the destination are overwritten by `shutil.move`

---

## Pipeline Integration (main.py)

```python
vault_root = resolve_vault_root()  # reads OBSIDIAN_VAULT_PATH; warns + returns None if missing
classifier = ClassificationAgent(vault_root, scratchpad) if vault_root else None

for docx_path in docx_files:
    artifact = await extractor.process(docx_path)
    output_path.write_text(artifact["extracted_text"])

    if classifier:
        await classifier.classify(output_path)
```

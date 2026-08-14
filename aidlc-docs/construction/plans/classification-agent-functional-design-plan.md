# Functional Design Plan — Classification Agent

## Steps
- [x] Step 1: Answer clarifying questions below
- [x] Step 2: Design classification prompt (system + user message structure)
- [x] Step 3: Design `move_to_vault` tool schema
- [x] Step 4: Design agent loop and response handling
- [x] Step 5: Design error handling and fallback flows
- [x] Step 6: Generate functional design artifacts

---

## Clarifying Questions

Please fill in the `[Answer]:` tags below and let me know when done.

---

## Question 1
Should the classification prompt include a brief description for each category (to improve accuracy), or just list the folder names?

Your category names are fairly self-explanatory, but a description like "CI&T — corporate knowledge, internal processes, methodology" could help the model distinguish edge cases.

A) Include descriptions for each category in the prompt (more accurate, slightly longer prompt)

B) List only the category names — the model should infer from the document content

C) Other (please describe after [Answer]: tag below)

[Answer]: A

---

## Question 2
What should be passed as the filename in the classification input — the `.md` file's name as-is (e.g. `my-document.md`), or just the stem without extension (e.g. `my-document`)?

A) Full filename including `.md` extension

B) Stem only (no extension)

C) Other (please describe after [Answer]: tag below)

[Answer]: B

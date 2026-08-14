# Handoff: Unit 3 — Installation Issues

**Date**: 2026-08-14
**Context**: Debugging Unit 3 (Extraction) test suite — 4 failures found, 1 fixed in code, 3 blocked by missing packages.

---

## Summary

The Unit 3 test suite has 29 tests. After fixing one test-code bug (`_make_config` used `mkdir()` without `parents=True`, crashing `test_concurrent_agents_independent`), **26/29 now pass**. The remaining 3 failures all trace to two missing native packages in the venv.

Both packages are required by the `parse_document` MCP tool in `src/pipeline/extraction_server.py`, which is the entry point for document text extraction — the core function of Unit 3. Without them, any real document (DOCX or PDF) will fail at runtime, not just in tests.

The packages cannot currently be installed because:
1. PyPI downloads hit repeated `ConnectionResetError(10054)` — the connection is being dropped before the file completes (4.1 MB wheel for `lxml`).
2. Windows locks the partially-downloaded `.whl` in `%TEMP%` with `WinError 32`, preventing pip from moving it even when the download partially succeeds.

Root cause is likely **Windows Defender real-time scanning** holding the temp file open while pip tries to rename it, compounded by an unstable or corporate-filtered network connection to PyPI CDN.

---

## Missing Packages

### 1. `lxml` >= 4.9
- **PyPI name**: `lxml`
- **Wheel needed for this env**: `lxml-6.1.1-cp314-cp314-win_amd64.whl` (4.1 MB)
- **Python version**: 3.14.6 (CPython)
- **Why needed**: `python-docx` (`docx` import) depends on `lxml` for XML parsing of `.docx` files. Without it, `import docx` itself fails with `ModuleNotFoundError: No module named 'lxml'`.
- **Impact**: All DOCX parsing is broken — `parse_document` raises on import for any `.docx` file.
- **Affects tests**: `test_docx_returns_paragraph_text`, `test_docx_text_order_preserved` (and by extension any future test that writes a real DOCX).

### 2. `pymupdf` >= 1.24
- **PyPI name**: `pymupdf`
- **Import name**: `fitz`
- **Wheel needed for this env**: `pymupdf-1.28.2-cp310-abi3-win_amd64.whl`
- **Why needed**: Used directly in `extraction_server.py` to open and read PDF pages (`fitz.open()`). Also needed in test helper `_write_minimal_pdf`.
- **Current state**: A broken global install exists at `C:\Users\bfranchi\AppData\Local\Python\pythoncore-3.14-64\Lib\site-packages\pymupdf\` but fails with `ImportError: DLL load failed while importing _extra` — the native extension DLL is missing or incompatible. The venv has no install at all.
- **Impact**: All PDF parsing is broken — `parse_document` fails at import or at `fitz.open()` for any `.pdf` file.
- **Affects tests**: `test_pdf_returns_page_text`.

---

## Suggested Fix

### Option A — Disable Defender exclusion + retry (recommended, cleanest)

1. Open **Windows Security → Virus & threat protection → Manage settings → Exclusions**.
2. Add exclusion for `%LOCALAPPDATA%\Temp` (or just the `pip-unpack-*` pattern).
3. Retry:
   ```
   .venv\Scripts\pip install lxml pymupdf
   ```
4. Remove the exclusion after install completes.

### Option B — Download wheels manually, install from file

Download the wheels on a machine with a stable connection (or via browser), copy them to the project, then install offline:

```
# lxml for Python 3.14, Windows 64-bit
https://files.pythonhosted.org/packages/b8/ce/3cf9a827342269f54d405a6202397de63f07c69cbd6ce7d183a3f0cba1e9/lxml-6.1.1-cp314-cp314-win_amd64.whl

# pymupdf (abi3 wheel, works on Python 3.10+)
https://files.pythonhosted.org/packages/84/2a/bfee84cf8a30f3c804e14282e0fb0f6f7b9b37bf7b7b61c49c8c82c35c20/pymupdf-1.28.2-cp310-abi3-win_amd64.whl
```

```
.venv\Scripts\pip install lxml-6.1.1-cp314-cp314-win_amd64.whl pymupdf-1.28.2-cp310-abi3-win_amd64.whl
```

### Option C — Redirect pip's temp dir to the project folder

Avoids `%TEMP%` (the Defender hot zone). Run from an elevated terminal or from a path Defender excludes:

```
set TMP=C:\Users\bfranchi\Desktop\projetos\docs-extraction\.pip-tmp
set TEMP=%TMP%
mkdir %TMP%
.venv\Scripts\pip install lxml pymupdf
```

Note: this was attempted during debugging but still failed — the Defender lock persists regardless of temp location unless an exclusion is added.

---

## Alternative Packages

If the current packages remain uninstallable, the following are drop-in or near-drop-in substitutes:

### For `lxml` (required by `python-docx`)

`python-docx` hard-depends on `lxml` — there is no runtime alternative without patching the library. The practical options are:

| Option | Notes |
|---|---|
| **`lxml-static`** | Pre-compiled static wheel, sometimes avoids DLL issues — check PyPI for cp314 build |
| Switch to **`python-docx2txt`** | Extracts raw text from DOCX without `lxml`; loses paragraph structure but simpler |
| Switch to **`mammoth`** | Converts DOCX to HTML/plain text, no `lxml` dependency |

If the goal is just text extraction (which it is for Unit 3), replacing `python-docx` with `mammoth` or `docx2txt` is viable and eliminates the `lxml` dependency entirely.

### For `pymupdf` / `fitz`

| Package | Import | Notes |
|---|---|---|
| **`pypdf`** | `pypdf` | Pure Python, no native DLLs, slower but always installable; text extraction via `page.extract_text()` |
| **`pdfminer.six`** | `pdfminer` | Pure Python, good text layout fidelity, more complex API |
| **`pdfplumber`** | `pdfplumber` | Built on `pdfminer.six`, cleaner API, good for structured PDFs |

`pypdf` is the lowest-friction replacement: pure Python, actively maintained, same basic API shape (`open → pages → extract_text`).

---

## Recommended Path

1. Try **Option A** (Defender exclusion) first — 2-minute fix, keeps all existing code unchanged.
2. If the network continues dropping the connection, use **Option B** (manual wheel download) — the wheels are small enough to transfer via USB or a personal hotspot.
3. Only switch to alternative packages if the environment permanently blocks PyPI access.

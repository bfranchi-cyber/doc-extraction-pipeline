# Dependencies

## Internal Dependencies

```
main.py
  |-> extraction.py    (Extractor)
  |-> classification.py (ClassificationAgent)
  |-> scratchpad.py    (Scratchpad)
  |-> exceptions.py    (PipelineError)

extraction.py
  |-> models.py        (CompactArtifact)
  |-> exceptions.py    (PipelineError)
  |-> scratchpad.py    (Scratchpad)

extraction_server.py
  |-> exceptions.py    (PipelineError)
  |-> scratchpad.py    (Scratchpad)

classification.py
  |-> scratchpad.py    (Scratchpad)

models.py
  |-> exceptions.py    (re-exports PipelineError, ExtractionPipelineError)
```

## External Dependencies

### anthropic[mcp]
- **Version**: `>=0.25`
- **Purpose**: HTTP client for Anthropic Messages API; used in `ClassificationAgent`
- **License**: MIT

### mcp
- **Version**: `>=1.8,<2.0`
- **Purpose**: FastMCP server framework; used in `extraction_server.py`
- **License**: MIT

### mammoth
- **Version**: `>=1.6`
- **Purpose**: Converts `.docx` binary format to plain text; used in `Extractor` and `extraction_server`
- **License**: BSD-2-Clause

### pytest
- **Version**: `>=7.0` (dev)
- **Purpose**: Test runner
- **License**: MIT

### pytest-cov
- **Version**: `>=4.0` (dev)
- **Purpose**: Coverage measurement and reporting
- **License**: MIT

### hypothesis
- **Version**: `>=6.0` (dev)
- **Purpose**: Property-based test generation
- **License**: MPL-2.0

# Personas — Extraction Pipeline

---

## Persona 1: The Knowledge Worker (Primary)

**Name**: Bruno  
**Role**: Personal knowledge manager and document-heavy professional  
**Technical Level**: Intermediate — comfortable with Python, CLI tools, and local configuration files; not a full-time developer

### Goals
- Keep an Obsidian vault as the single source of truth for all professional documents
- Never manually convert or copy documents from Google Drive to Obsidian
- Find any document quickly via Obsidian's search, organized by category
- Trust that the pipeline runs reliably in the background without babysitting

### Pain Points
- Manual copy-paste from Drive to Obsidian is error-prone and time-consuming
- Raw `.docx` files are not searchable or linkable inside Obsidian
- Images embedded in documents are lost or misplaced during manual extraction
- Works-in-progress that aren't ready should not be processed prematurely

### Behaviors
- Saves documents to Google Drive as part of normal workflow; does not interact with the pipeline directly during processing
- Occasionally reviews the scratchpad log to understand what was processed or why something failed
- Re-runs the pipeline manually if a known failure needs to be retried
- Configures vault category folders once; expects the pipeline to respect that structure permanently

### Context
- Windows 11 machine, always-on during work hours
- Obsidian vault at `C:\Users\bfranchi\Documents\Obsidian Vault\`
- Images folder at `C:\Users\bfranchi\Documents\Obsidian Images\`
- Google Drive holds all source documents organized in folders

### Relationship to Pipeline
- **Consumer**: Receives enriched `.md` files in the vault
- **Operator**: Monitors scratchpad and manifest for pipeline health
- **Configurator**: Sets up OAuth credentials and vault category folders once at setup time

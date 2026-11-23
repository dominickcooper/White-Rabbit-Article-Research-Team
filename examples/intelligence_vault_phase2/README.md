# Phase 2 fictional extraction demonstration

This demonstration stays offline and uses the validated manual provider. It creates proposals
only; nothing enters accepted knowledge until the review and commit commands are run.

```powershell
.venv\Scripts\python.exe -m white_rabbit vault extract `
  examples\intelligence_vault_phase2\northstar_testimony.md `
  --provider manual `
  --manual-results examples\intelligence_vault_phase2\northstar_results.json

.venv\Scripts\python.exe -m white_rabbit vault extraction-status JOB-UUID
.venv\Scripts\python.exe -m white_rabbit vault extraction-review JOB-UUID
.venv\Scripts\python.exe -m white_rabbit vault extraction-review JOB-UUID --approve PROP-UUID
.venv\Scripts\python.exe -m white_rabbit vault extraction-commit JOB-UUID
```

The source, people, agency, meeting, and testimony are entirely fictional.

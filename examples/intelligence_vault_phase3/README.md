# Phase 3 fictional network demonstration

This fixture creates a separate Vault containing invented people, organizations, an event,
a place, accepted testimony, a corroborated inference, source locators, and two explicit
investigation memberships. It never reads or alters the real Vault.

From the repository root:

```powershell
.venv\Scripts\python.exe examples\intelligence_vault_phase3\load_demo.py `
  --db knowledge\phase3_demo.db
.venv\Scripts\python.exe -m white_rabbit vault `
  --db knowledge\phase3_demo.db serve --port 8765
```

Open `http://127.0.0.1:8765`, then use the IDs printed by the loader. On the Red String
Board, focus on the unit with three hops and enable the candidate overlay. Avery North and
Blake Rowan share a military unit during a potentially overlapping period; the interface
labels that as an exploratory institutional-overlap candidate and explicitly does **not**
assert that they knew one another.

The loader refuses to overwrite an existing database. Delete the disposable demo database
yourself, or choose another path, when you want a fresh run.

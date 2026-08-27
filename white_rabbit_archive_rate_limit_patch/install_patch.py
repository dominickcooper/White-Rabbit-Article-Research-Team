from __future__ import annotations

import shutil
import subprocess
import sys
from datetime import datetime
from pathlib import Path

HERE = Path(__file__).resolve().parent
ROOT = HERE.parent
SRC = HERE / 'files' / 'white_rabbit' / 'archive_sync.py'
DST = ROOT / 'white_rabbit' / 'archive_sync.py'

if not DST.exists():
    raise SystemExit(f'ERROR: Expected White Rabbit project at {ROOT}')

stamp = datetime.now().strftime('%Y%m%d_%H%M%S')
backup = ROOT / 'upgrade_backups' / f'archive_rate_limit_{stamp}' / 'white_rabbit' / 'archive_sync.py'
backup.parent.mkdir(parents=True, exist_ok=True)
shutil.copy2(DST, backup)
shutil.copy2(SRC, DST)

print(f'Backed up: {backup}')
print('Installed rate-limit-safe archive downloader.')
print('Running tests...')
result = subprocess.run([sys.executable, '-m', 'pytest', '-q', 'tests'], cwd=ROOT)
if result.returncode:
    raise SystemExit('ERROR: Tests failed. Restore the backup shown above if needed.')
print('\nPatch installed successfully.')
print('Next: python -m white_rabbit archive sync')

from __future__ import annotations
import os, shutil, subprocess, sys
from datetime import datetime
from pathlib import Path

HERE=Path(__file__).resolve().parent
ROOT=HERE.parent
FILES=HERE/'files'
DEPS=['numpy>=1.26','joblib>=1.4','scikit-learn>=1.5']

def run(cmd, **kwargs):
    print('  >', ' '.join(map(str,cmd)))
    return subprocess.run(list(map(str,cmd)), cwd=ROOT, **kwargs)

def main():
    if not (ROOT/'white_rabbit').is_dir():
        print(f'ERROR: Expected project root at {ROOT}')
        return 2
    stamp=datetime.now().strftime('%Y%m%d_%H%M%S')
    backup=ROOT/'upgrade_backups'/f'archive_retrieval_v2_{stamp}'
    backup.mkdir(parents=True,exist_ok=True)
    rels=[Path('white_rabbit/archive_retrieval.py'),Path('white_rabbit/cli.py'),Path('requirements.txt')]
    for rel in rels:
        src=ROOT/rel
        if src.exists():
            dst=backup/rel; dst.parent.mkdir(parents=True,exist_ok=True); shutil.copy2(src,dst)
    for src in FILES.rglob('*'):
        if src.is_file():
            rel=src.relative_to(FILES); dst=ROOT/rel; dst.parent.mkdir(parents=True,exist_ok=True); shutil.copy2(src,dst)
    req=ROOT/'requirements.txt'
    txt=req.read_text(encoding='utf-8') if req.exists() else ''
    with req.open('a',encoding='utf-8') as f:
        for dep in DEPS:
            name=dep.split('>')[0].lower()
            if name not in txt.lower():
                f.write(('' if txt.endswith('\n') or not txt else '\n')+dep+'\n'); txt += '\n'+dep
    test_src=HERE/'tests'/'test_archive_retrieval_v2.py'
    shutil.copy2(test_src,ROOT/'tests'/'test_archive_retrieval_v2.py')
    py=ROOT/'.venv'/'Scripts'/'python.exe'
    if not py.exists(): py=Path(sys.executable)
    print(f'Backups: {backup}')
    print('Installing retrieval dependencies...')
    r=run([py,'-m','pip','install',*DEPS])
    if r.returncode: return r.returncode
    env=os.environ.copy(); env.update({'OPENBLAS_NUM_THREADS':'1','OMP_NUM_THREADS':'1','MKL_NUM_THREADS':'1','PYTEST_DISABLE_PLUGIN_AUTOLOAD':'1'})
    print('Running tests...')
    r=run([py,'-m','pytest','-q','tests'],env=env)
    if r.returncode:
        print('ERROR: tests failed; restore from backup if needed.')
        return r.returncode
    db=ROOT/'knowledge'/'white_rabbit.db'
    if db.exists():
        print('Rebuilding cleaned archive search index...')
        r=run([py,'-m','white_rabbit','archive','reindex','--force'],env=env)
        if r.returncode: return r.returncode
    print('\nArchive Retrieval v2 installed successfully.')
    print('Try: python -m white_rabbit archive search "Flock Safety surveillance"')
    return 0

if __name__=='__main__': raise SystemExit(main())

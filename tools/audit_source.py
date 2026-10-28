"""Fail on common private data/credentials accidentally added to source/distribution inputs."""
from pathlib import Path
import re

ROOT = Path(__file__).resolve().parents[1]
EXCLUDED = {'.git', '.venv', 'venv', '__pycache__', '.pytest_cache', 'build', 'dist'}
PATTERNS = [re.compile(r'gh[pousr]_[A-Za-z0-9]{30,}'), re.compile(r'github_pat_[A-Za-z0-9_]{40,}'),
            re.compile(r'AKIA[A-Z0-9]{16}'), re.compile(r'-----BEGIN (?:RSA |EC |OPENSSH )?PRIVATE KEY-----'),
            re.compile(r'(?:C:\\Users\\|C:/Users/|/home/|/workspace/scratch/)[A-Za-z0-9_.-]+')]


def audit():
    failures = []
    for path in ROOT.rglob('*'):
        rel = path.relative_to(ROOT)
        if any(p in EXCLUDED for p in rel.parts) or not path.is_file(): continue
        if path.name.lower() in {'cookies.txt', 'settings.json', '.env'} or path.suffix in {'.key', '.pfx', '.p12'}:
            failures.append(str(rel)); continue
        if path.suffix not in {'.py', '.md', '.txt', '.yml', '.json', '.spec', '.svg'}: continue
        text = path.read_text(encoding='utf-8')
        if any(p.search(text) for p in PATTERNS): failures.append(str(rel))
    if failures: raise SystemExit('Revisar archivos antes de publicar: ' + ', '.join(failures))
    print('PASS: source/documentation privacy audit')


if __name__ == '__main__': audit()

"""Plan from the CURRENT workflow, optionally rebuilding an existing source tag."""
import ast
import json
import os
from pathlib import Path
import re
import subprocess


def git(*args):
    return subprocess.check_output(['git', *args], text=True).strip()


def plan():
    event = os.environ.get('GITHUB_EVENT_NAME', '')
    requested = os.environ.get('RELEASE_TAG', '').strip()
    ref = os.environ.get('GITHUB_REF', '')
    tag = requested or (ref.removeprefix('refs/tags/') if ref.startswith('refs/tags/') else '')
    if tag and not re.fullmatch(r'v\d+\.\d+\.\d+', tag):
        raise RuntimeError('Tag inválido')
    source = tag or 'HEAD'
    text = git('show', source + ':mediadownloader/__init__.py')
    tree = ast.parse(text)
    version = next(ast.literal_eval(n.value) for n in tree.body if isinstance(n, ast.Assign)
                   and any(isinstance(t, ast.Name) and t.id == '__version__' for t in n.targets))
    if not re.fullmatch(r'\d+\.\d+\.\d+', version) or tag and tag != 'v' + version:
        raise RuntimeError('La versión del tag y del código no coinciden')
    tagged = bool(git('tag', '--list', 'v' + version))
    publish = event == 'workflow_dispatch' or ref.startswith('refs/tags/') or (ref == 'refs/heads/main' and not tagged)
    result = {'publish': str(publish).lower(), 'version': version, 'source': git('rev-parse', source + '^{commit}')}
    if os.environ.get('GITHUB_OUTPUT'):
        with open(os.environ['GITHUB_OUTPUT'], 'a', encoding='utf-8') as f:
            for k, v in result.items(): f.write(f'{k}={v}\n')
    print(json.dumps(result))


if __name__ == '__main__':
    plan()

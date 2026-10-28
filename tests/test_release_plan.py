import os
from pathlib import Path
import subprocess

import pytest
from tools.release_plan import plan


def repo(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    monkeypatch.delenv('GITHUB_OUTPUT', raising=False)
    monkeypatch.delenv('RELEASE_TAG', raising=False)
    monkeypatch.setenv('GITHUB_EVENT_NAME', 'push')
    monkeypatch.setenv('GITHUB_REF', 'refs/heads/main')
    def git(*args):
        return subprocess.check_output(['git', *args], text=True).strip()
    git('init', '-b', 'main')
    git('config', 'user.email', 'fixture@example.invalid'); git('config', 'user.name', 'Test fixture')
    p = Path('mediadownloader/__init__.py'); p.parent.mkdir(); p.write_text('__version__ = "1.0.8"\n')
    git('add', '.'); git('commit', '-m', 'fixture')
    return git, p


def test_main_new_version_publishes_same_version_tag_does_not(tmp_path, monkeypatch, capsys):
    git, p = repo(tmp_path, monkeypatch)
    plan(); assert '"publish": "true"' in capsys.readouterr().out
    git('tag', 'v1.0.8')
    plan(); assert '"publish": "false"' in capsys.readouterr().out


def test_recovery_uses_requested_source_even_when_main_has_new_version(tmp_path, monkeypatch, capsys):
    git, p = repo(tmp_path, monkeypatch); git('tag', 'v1.0.8'); source = git('rev-parse', 'HEAD')
    p.write_text('__version__ = "1.0.9"\n'); git('add', '.'); git('commit', '-m', 'new fixture')
    monkeypatch.setenv('GITHUB_EVENT_NAME', 'workflow_dispatch'); monkeypatch.setenv('RELEASE_TAG', 'v1.0.8')
    plan(); output = capsys.readouterr().out
    assert source in output and '"version": "1.0.8"' in output and '"publish": "true"' in output


def test_tag_version_mismatch_is_rejected(tmp_path, monkeypatch):
    git, p = repo(tmp_path, monkeypatch); git('tag', 'v1.0.9')
    monkeypatch.setenv('GITHUB_REF', 'refs/tags/v1.0.9')
    with pytest.raises(RuntimeError): plan()

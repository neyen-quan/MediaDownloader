"""Real ACL fixtures for private Windows test directories, never user installations."""
import csv
import os
from contextlib import contextmanager
import subprocess


@contextmanager
def deny_directory_delete(path):
    """Deny both Windows deletion permission routes while allowing reads/writes."""
    if os.name != 'nt':
        raise RuntimeError('Windows ACL fixture requires Windows')
    sid = next(csv.reader([subprocess.check_output(
        ['whoami', '/user', '/fo', 'csv', '/nh'], text=True).strip()]))[-1]
    principal = '*' + sid
    def acl(folder, *args):
        subprocess.run(['icacls', str(folder), *args], check=True, capture_output=True, text=True)
    # These ACEs apply only to the specified directory; they are NOT inherited.
    # Other app/staging directories retain their own DELETE rights for swapping.
    acl(path.parent, '/deny', principal + ':(DC)')
    try:
        acl(path, '/deny', principal + ':(D)')
        try:
            yield
        finally:
            if path.exists():
                acl(path, '/remove:d', principal)
    finally:
        acl(path.parent, '/remove:d', principal)

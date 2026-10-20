"""Expose test evidence in the Actions job summary, including on failed builds."""
from pathlib import Path
import html
import os
import subprocess
import sys
import tempfile
import xml.etree.ElementTree as ET


def report():
    sections = ["## Resultados de las pruebas\n"]
    for name in ("results.xml", "media-results.xml"):
        path = Path(name)
        if not path.exists():
            continue
        root = ET.parse(path).getroot()
        cases = list(root.iter("testcase"))
        failed = [c for c in cases if c.find("failure") is not None or c.find("error") is not None]
        skipped = [c for c in cases if c.find("skipped") is not None]
        sections.append(f"### {name}\n\n{len(cases)} pruebas; {len(failed)} fallos; {len(skipped)} omitidas.\n")
        for case in failed:
            for kind in ("failure", "error"):
                failure = case.find(kind)
                if failure is not None:
                    detail = (failure.text or failure.get("message", ""))[-20000:]
                    sections.append(f"\n**{html.escape(case.get('name', ''))}**\n\n<pre>{html.escape(detail)}</pre>\n")
            for kind in ("system-out", "system-err"):
                captured = case.find(kind)
                if captured is not None and captured.text:
                    sections.append(f"<pre>{html.escape(captured.text[-20000:])}</pre>\n")
    # Only this controlled local fixture's engine logs are published, never application/user logs.
    logs = sorted({p.resolve() for p in Path(tempfile.gettempdir()).glob(
        "pytest-of-*/pytest-*/test_dash*/result/engine.log")}, key=lambda p: p.stat().st_mtime)
    for log in logs[-2:]:
        sections.append("\n### Motor DASH de la prueba local\n\n<pre>" +
                        html.escape(log.read_text(encoding="utf-8", errors="replace")[-20000:]) + "</pre>\n")
    content = "\n".join(sections)
    output = os.environ.get("GITHUB_STEP_SUMMARY")
    if output:
        with Path(output).open("a", encoding="utf-8") as f:
            f.write(content)
    print(content)
    if "--publish" in sys.argv and os.environ.get("GITHUB_EVENT_NAME") == "push":
        # A separate ref makes the report retrievable with Git when the cloud API is unavailable.
        # Commit-tree does not alter the checkout, its index or any application source.
        def git(*args, data=None, env=None):
            # Git's tree input is a binary protocol; Windows text pipes would add CR to filenames.
            payload = data.encode("utf-8") if data is not None else None
            result = subprocess.run(["git", *args], input=payload, capture_output=True,
                                    check=True, env=env)
            return result.stdout.decode("utf-8").strip()
        blob = git("hash-object", "-w", "--stdin", data=content)
        tree = git("mktree", data=f"100644 blob {blob}\tREPORT.md\n")
        identity = dict(os.environ, GIT_AUTHOR_NAME="github-actions[bot]",
            GIT_COMMITTER_NAME="github-actions[bot]",
            GIT_AUTHOR_EMAIL="41898282+github-actions[bot]@users.noreply.github.com",
            GIT_COMMITTER_EMAIL="41898282+github-actions[bot]@users.noreply.github.com")
        run = os.environ["GITHUB_RUN_ID"]
        attempt = os.environ["GITHUB_RUN_ATTEMPT"]
        commit = git("commit-tree", tree, "-m", f"Windows verification report {run}/{attempt}", env=identity)
        git("push", "origin", f"{commit}:refs/heads/ci/windows-report-{run}-{attempt}")


if __name__ == "__main__":
    report()

"""Expose test evidence in the Actions job summary, including on failed builds."""
from pathlib import Path
import html
import os
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
    content = "\n".join(sections)
    output = os.environ.get("GITHUB_STEP_SUMMARY")
    if output:
        with Path(output).open("a", encoding="utf-8") as f:
            f.write(content)
    print(content)


if __name__ == "__main__":
    report()

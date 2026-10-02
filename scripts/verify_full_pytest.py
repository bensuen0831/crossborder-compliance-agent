"""Mandatory gate: reject skipped/deselected/failed/incomplete full suites."""

import json
import re
import sys
import xml.etree.ElementTree as ET
from pathlib import Path


def main():
    evidence = Path(sys.argv[1])
    root = ET.parse(evidence / "pytest_full.xml").getroot()
    cases = list(root.iter("testcase"))
    log = (evidence / "pytest_full.log").read_text()
    counts = {
        "passed": sum(
            not any(c.find(tag) is not None for tag in ("skipped", "failure", "error"))
            for c in cases
        ),
        "skipped": sum(c.find("skipped") is not None for c in cases),
        "failed": sum(c.find("failure") is not None for c in cases),
        "errors": sum(c.find("error") is not None for c in cases),
        "deselected": sum(int(n) for n in re.findall(r"(\d+) deselected", log)),
    }
    phases = {
        phase: any(phase in c.get("classname", "") for c in cases)
        for phase in ("phase1b", "phase1c", "phase1d", "phase1e", "phase1f")
    }
    result = {
        **counts,
        "phase_coverage": phases,
        "pass": bool(cases)
        and all(phases.values())
        and not any(counts[k] for k in ("skipped", "failed", "errors", "deselected")),
    }
    (evidence / "pytest_full_summary.json").write_text(json.dumps(result, indent=2) + "\n")
    print(json.dumps(result, indent=2))
    raise SystemExit(0 if result["pass"] else 2)


if __name__ == "__main__":
    main()

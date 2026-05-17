from pathlib import Path
import subprocess


OBSOLETE_ATTRIBUTES = [
    'tag="resolved"',
    'tag="target_id"',
    'tag="statement_type"',
    'tag="body_type"',
    'tag="control_type"',
    'tag="condition"',
    'tag="exception"',
    'tag="value"',
    'tag="kind"',
]


def test_kdm_has_no_obsolete_attributes():
    subprocess.run(
        ["python", "src/main.py"],
        capture_output=True,
        text=True,
        check=True,
    )

    xmi = Path("output/example_project.kdm.xmi").read_text(encoding="utf-8")

    for obsolete in OBSOLETE_ATTRIBUTES:
        assert obsolete not in xmi

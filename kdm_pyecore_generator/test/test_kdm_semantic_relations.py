from pathlib import Path
import subprocess


def test_kdm_contains_expected_semantic_relations():
    subprocess.run(
        ["python", "src/main.py"],
        capture_output=True,
        text=True,
        check=True,
    )

    xmi = Path("output/example_project.kdm.xmi").read_text(encoding="utf-8")

    assert 'xsi:type="action:Calls"' in xmi
    assert 'xsi:type="action:Creates"' in xmi
    assert 'xsi:type="action:Reads"' in xmi
    assert 'xsi:type="action:Writes"' in xmi
    assert 'xsi:type="action:Throws"' in xmi
    assert 'xsi:type="action:TryUnit"' in xmi
    assert 'xsi:type="action:CatchUnit"' in xmi
    assert 'xsi:type="action:ExceptionFlow"' in xmi
    assert 'xsi:type="code:HasType"' in xmi
    assert 'xsi:type="code:HasValue"' in xmi

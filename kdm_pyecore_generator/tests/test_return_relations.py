from pathlib import Path
import subprocess


OUTPUT_PATH = Path("output/example_project.kdm.xmi")


def run_generator():
    result = subprocess.run(
        ["python", "src/main.py"],
        capture_output=True,
        text=True,
        check=False,
    )

    assert result.returncode == 0, (
        "Generator failed.\n"
        f"STDOUT:\n{result.stdout}\n"
        f"STDERR:\n{result.stderr}"
    )

    assert OUTPUT_PATH.exists(), "KDM output file was not generated."

    return OUTPUT_PATH.read_text(encoding="utf-8")


def test_return_is_modeled_with_reads():
    xmi = run_generator()

    assert 'xsi:type="action:ActionElement" name="return" kind="return"' in xmi
    assert 'xsi:type="action:Reads"' in xmi


def test_return_literal_is_modeled_as_storable_with_has_value():
    xmi = run_generator()

    assert 'role" value="returned_literal"' in xmi
    assert 'literal_value"' in xmi
    assert 'xsi:type="code:HasValue"' in xmi


def test_return_call_result_is_modeled_as_temporary_storable():
    xmi = run_generator()

    assert 'role" value="returned_call_result"' in xmi
    assert 'source_call_name"' in xmi
    assert 'return_value_of_' in xmi


def test_old_returns_action_relationship_is_not_used():
    xmi = run_generator()

    assert 'kind" value="returns"' not in xmi
    assert 'tag="kind" value="returns"' not in xmi


def test_unresolved_return_expressions_are_explicitly_marked():
    xmi = run_generator()

    assert 'unresolved_return_value' in xmi

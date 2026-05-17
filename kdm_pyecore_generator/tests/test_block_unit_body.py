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


def test_callable_body_is_modeled_with_block_unit():
    xmi = run_generator()

    assert 'xsi:type="action:BlockUnit" name="body" kind="body"' in xmi
    assert 'tag="role" value="callable_body"' in xmi
    assert 'tag="callable_body_id"' in xmi


def test_body_actions_are_nested_inside_block_unit():
    xmi = run_generator()

    block_position = xmi.find('xsi:type="action:BlockUnit" name="body" kind="body"')
    action_position = xmi.find('xsi:type="action:ActionElement"', block_position)

    assert block_position != -1
    assert action_position != -1
    assert action_position > block_position

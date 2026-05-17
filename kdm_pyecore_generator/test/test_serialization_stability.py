from pathlib import Path
import subprocess


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

    output_path = Path("output/example_project.kdm.xmi")
    assert output_path.exists(), "KDM output file was not generated."

    return output_path.read_text(encoding="utf-8")


def test_kdm_serialization_is_stable():
    first = run_generator()
    second = run_generator()

    assert first == second

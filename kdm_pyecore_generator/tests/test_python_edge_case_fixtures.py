from pathlib import Path
import subprocess


FIXTURES_DIR = Path("tests/fixtures")
OUTPUT_DIR = Path("output/test_fixtures")


def run_generator(input_name: str) -> str:
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)

    input_path = FIXTURES_DIR / input_name
    output_path = OUTPUT_DIR / input_name.replace(".json", ".kdm.xmi")

    result = subprocess.run(
        [
            "python",
            "src/main.py",
            "--input",
            str(input_path),
            "--output",
            str(output_path),
        ],
        capture_output=True,
        text=True,
        check=False,
    )

    assert result.returncode == 0, (
        f"Generator failed for fixture {input_name}.\n"
        f"STDOUT:\n{result.stdout}\n"
        f"STDERR:\n{result.stderr}"
    )

    assert output_path.exists(), f"Output was not generated: {output_path}"

    return output_path.read_text(encoding="utf-8")


def test_bare_return_fixture():
    xmi = run_generator("bare_return.json")

    assert 'name="return" kind="return"' in xmi
    assert 'tag="return_flow" value="void"' in xmi


def test_return_literal_fixture():
    xmi = run_generator("return_literal.json")

    assert 'name="return" kind="return"' in xmi
    assert 'xsi:type="action:Reads"' in xmi
    assert 'tag="role" value="returned_literal"' in xmi
    assert 'tag="literal_value" value="True"' in xmi
    assert 'xsi:type="code:HasValue"' in xmi


def test_bare_raise_fixture():
    xmi = run_generator("bare_raise.json")

    assert 'name="raise" kind="raise"' in xmi
    assert 'tag="exception_flow" value="rethrow"' in xmi


def test_bare_except_fixture():
    xmi = run_generator("bare_except.json")

    assert 'xsi:type="action:TryUnit" name="try"' in xmi
    assert 'xsi:type="action:CatchUnit" name="except"' in xmi
    assert 'xsi:type="action:ExceptionFlow"' in xmi
    assert 'tag="exception_flow" value="catch_all"' in xmi

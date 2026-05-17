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


def test_raise_is_modeled_with_throws():
    xmi = run_generator()

    assert 'xsi:type="action:Throws"' in xmi
    assert 'role" value="thrown_exception"' in xmi
    assert 'exception_type_name" value="RepositoryError"' in xmi


def test_try_except_is_modeled_with_exception_flow():
    xmi = run_generator()

    assert 'xsi:type="action:TryUnit"' in xmi
    assert 'xsi:type="action:CatchUnit"' in xmi
    assert 'xsi:type="action:ExceptionFlow"' in xmi


def test_try_finally_is_modeled_with_exit_flow():
    xmi = run_generator()

    assert 'xsi:type="action:FinallyUnit"' in xmi
    assert 'xsi:type="action:ExitFlow"' in xmi


def test_catch_unit_has_exception_parameter():
    xmi = run_generator()

    assert 'xsi:type="code:ParameterUnit" name="exception_RepositoryError"' in xmi
    assert 'role" value="caught_exception"' in xmi
    assert 'exception_type_name" value="RepositoryError"' in xmi


def test_builtin_exception_is_created_when_needed():
    xmi = run_generator()

    assert 'name="PythonBuiltins"' in xmi
    assert 'xsi:type="code:ClassUnit" name="OSError"' in xmi
    assert 'builtin_id" value="builtin:OSError"' in xmi


def test_old_catches_relation_is_not_used():
    xmi = run_generator()

    assert 'kind" value="catches"' not in xmi
    assert 'tag="kind" value="catches"' not in xmi

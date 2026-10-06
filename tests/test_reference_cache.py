import pytest

from prismqa.evaluation import evaluate
from prismqa.reference_cache import ReferenceCacheRunner
from prismqa.sampling import program_group


class Arithmetic:
    lock = {"control_environment": "v1"}

    def run_program(self, code, language, cases, directory):
        return {
            "compilation": {"status": "ok"},
            "results": [
                {"status": "ok", "stdout": str(sum(map(int, c["input"].split()))) + "\n"}
                for c in cases
            ],
        }


def test_reference_cache_checks_code_cases_environment(tmp_path):
    source = {
        "id": "source",
        "source_code": "add",
        "raw_output": "add",
        "source_language": "Python",
        "target_language": "Python",
        "original_tests": [{"input": "1 2", "expected": "3\n"}],
        "data_kind": "authors_source_control",
    }
    extra = {"input": "2 3", "expected": "5\n"}
    profile = {
        "domains": {
            program_group(source): {
                "status": "independently_checked",
                "domain_description": "Two integers",
                "tests": [extra],
            }
        }
    }
    evaluate(tmp_path, [source], profile, tmp_path / "validated", runner=Arithmetic())
    runner = ReferenceCacheRunner(tmp_path, "validated", base=Arithmetic())
    cases = source["original_tests"] + [extra]
    reused = runner.run_reference("add", "Python", cases, tmp_path / "unused")
    assert reused["execution_origin"] == "reused_validated_source"
    assert reused["results"][1]["stdout"] == "5\n"
    for code, language, inputs in [
        ("changed", "Python", cases),
        ("add", "C", cases),
        ("add", "Python", [extra]),
    ]:
        with pytest.raises(ValueError, match="differ"):
            runner.run_reference(code, language, inputs, tmp_path / "unused")
    changed = Arithmetic()
    changed.lock = {"control_environment": "v2"}
    with pytest.raises(ValueError, match="toolchain"):
        ReferenceCacheRunner(tmp_path, "validated", base=changed)

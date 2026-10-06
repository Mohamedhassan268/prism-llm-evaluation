import copy

import pytest
from hypothesis import given
from hypothesis import strategies as st

from prismqa.evaluation import evaluate, verified_report
from prismqa.extraction import extract
from prismqa.records import inside, read_json, write_json
from prismqa.sampling import program_group, sample


def record(identifier="one", code="sum"):
    return {
        "id": identifier,
        "source_code": "reference",
        "source_language": "Python",
        "target_language": "Python",
        "raw_output": code,
        "original_tests": [{"input": "1 2", "expected": "3\n"}],
        "data_kind": "controlled_fixture",
    }


class FakeRunner:
    lock = {"test_double": "arithmetic-control-v1"}

    def __init__(self, interrupt_at=None):
        self.calls = 0
        self.interrupt_at = interrupt_at

    def run_program(self, code, language, cases, directory):
        self.calls += 1
        if self.calls == self.interrupt_at:
            raise KeyboardInterrupt
        values = []
        for case in cases:
            answer = 3 if code == "constant" else sum(map(int, case["input"].split()))
            values.append({"status": "ok", "stdout": f"{answer}\n"})
        return {"compilation": {"status": "ok"}, "results": values}


def profile(expected="5\n"):
    return {
        "domains": {
            program_group(record()): {
                "status": "independently_checked",
                "domain_description": "Two bounded integers",
                "tests": [{"input": "2 3", "expected": expected}],
            }
        }
    }


@given(
    st.text(
        alphabet=st.characters(blacklist_characters="`", blacklist_categories=("Cs",)), min_size=1
    )
)
def test_extraction_preserves_program(text):
    if not text.strip():
        return
    code = text + "\n"
    assert (
        extract("```python\n" + code + "```\n", "Python", profile="conservative-fences-v1")["code"]
        == code
    )


def test_extraction_conditions():
    wrapped = "```python\r\nprint(1)\r\n```\r\n"
    assert extract(wrapped, "Python", profile="conservative-fences-v1")["code"] == "print(1)\r\n"
    blocks = "```python\na\n```\n```python\nb\n```\n"
    assert extract(blocks, "Python", profile="conservative-fences-v1")["status"] == "ambiguous"
    assert extract(blocks, "Python", prompt="Response:", profile="authors-regex-v1")["code"] == "a"


def test_sampler_groups_and_model_rows():
    records = []
    for index in range(40):
        for model in ("a", "b"):
            item = record(f"{index}-{model}")
            item.update(sample_id=str(index), source_code=f"program {index // 2}")
            records.append(item)
    first = sample(records, calibration=4, evaluation=8)
    assert first == sample(records, calibration=4, evaluation=8)
    assert not set(first["program_groups"]["calibration"]) & set(
        first["program_groups"]["evaluation"]
    )
    assert len(first["record_ids"]["evaluation"]) == 16


def test_known_fault_and_bad_oracle(tmp_path):
    result = evaluate(
        tmp_path, [record(code="constant")], profile(), tmp_path / "fault", runner=FakeRunner()
    )
    assert result["confirmed_false_passes"] == 1
    assert result["validated_extra_original_passes"] == 1
    bad = evaluate(
        tmp_path, [record(code="constant")], profile("999\n"), tmp_path / "bad", runner=FakeRunner()
    )
    assert bad["confirmed_false_passes"] == 0
    assert bad["additional_statuses"] == {"oracle_mismatch": 1}


def test_interrupt_resume_and_report_tampering(tmp_path):
    records = [record("a"), record("b")]
    destination = tmp_path / "run"
    with pytest.raises(KeyboardInterrupt):
        evaluate(tmp_path, records, {}, destination, runner=FakeRunner(interrupt_at=2))
    with pytest.raises(ValueError, match="incomplete"):
        verified_report(destination)
    runner = FakeRunner()
    evaluate(tmp_path, records, {}, destination, resume=True, runner=runner)
    assert runner.calls == 1
    assert verified_report(destination)[1]["original_test_passes"] == 2
    summary = read_json(destination / "summary.json")
    summary["selected_outputs"] = 99
    write_json(destination / "summary.json", summary)
    with pytest.raises(ValueError, match="raw outcomes"):
        verified_report(destination)


def test_empty_changed_run_and_heldout_gate(tmp_path):
    with pytest.raises(ValueError):
        evaluate(tmp_path, [], {}, tmp_path / "empty", runner=FakeRunner())
    evaluate(tmp_path, [record()], {}, tmp_path / "run", runner=FakeRunner())
    with pytest.raises(ValueError, match="identical"):
        evaluate(
            tmp_path,
            [record(code="constant")],
            {},
            tmp_path / "run",
            resume=True,
            runner=FakeRunner(),
        )
    heldout = copy.deepcopy(record())
    heldout.update(data_kind="authors_saved_outputs", split="evaluation")
    with pytest.raises(ValueError, match="recorded user review"):
        evaluate(tmp_path, [heldout], {}, tmp_path / "heldout", runner=FakeRunner())


def test_path_escape(tmp_path):
    with pytest.raises(ValueError):
        inside(tmp_path, tmp_path.parent / "outside")

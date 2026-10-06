import csv
import io
import zipfile

import pytest

from prismqa.authors import load_saved


def test_saved_generation_is_preserved_and_conditions_are_separate(tmp_path):
    values = {
        "sample_id": "42",
        "translation_output_id": "row1",
        "input_code": "print(1)\n",
        "prompt_template": "Response:",
        "new_tokens_from_inference_output": "```python\nprint(1)\n```",
        "test_case_input_data": "",
        "test_case_expected_output": "1\n",
        "target_language": "Python",
        "source_language": "C",
        "model_path": "model/path",
        "name": "Model",
        "size_in_billions": "7",
    }
    stream = io.StringIO(newline="")
    writer = csv.DictWriter(stream, fieldnames=list(values))
    writer.writeheader()
    writer.writerow(values)
    archive = tmp_path / "saved.zip"
    with zipfile.ZipFile(archive, "w") as zipped:
        for condition in ("VDE", "VRE"):
            zipped.writestr(f"{condition}/inference_output.csv", stream.getvalue())
    records = load_saved(archive, ["42"], split="calibration")
    assert len(records) == 2
    assert {r["condition"] for r in records} == {"VDE", "VRE"}
    assert {r["raw_output"] for r in records} == {values["new_tokens_from_inference_output"]}
    assert {r["extraction_profile"] for r in records} == {"direct-v1", "authors-regex-v1"}
    assert len({r["saved_generation_id"] for r in records}) == 1
    with pytest.raises(ValueError, match="No saved outputs"):
        load_saved(archive, ["missing"])


def test_unknown_archive_condition_fails(tmp_path):
    archive = tmp_path / "bad.zip"
    with zipfile.ZipFile(archive, "w") as zipped:
        zipped.writestr("unknown/inference_output.csv", "sample_id\n42\n")
    with pytest.raises(ValueError):
        load_saved(archive, ["42"])

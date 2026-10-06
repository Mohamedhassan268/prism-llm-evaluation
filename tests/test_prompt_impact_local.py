"""A resumed local run must not mix different frozen requests."""

import json

import pytest

from scripts.run_prompt_impact_local import load_existing


def test_resume_rejects_a_response_from_a_different_prompt(tmp_path) -> None:
    request = {
        "task_id": "example",
        "variant": "cosmetic",
        "prompt": "Original prompt",
        "prompt_sha256": "original-hash",
        "manifest_sha256": "manifest-hash",
    }
    existing = tmp_path / "responses.jsonl"
    existing.write_text(
        json.dumps({**request, "model_id": "pinned-model", "trial": 1, "raw_response": "{}"})
        + "\n",
        encoding="utf-8",
    )
    assert load_existing(existing, [request], "pinned-model") == {("example", "cosmetic")}
    changed_request = {**request, "prompt": "Changed prompt"}
    with pytest.raises(ValueError, match="does not match frozen request"):
        load_existing(existing, [changed_request], "pinned-model")

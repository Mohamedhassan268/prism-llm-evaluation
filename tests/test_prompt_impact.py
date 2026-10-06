"""Controls for claims the prompt-impact pilot is allowed to make."""

import json
from pathlib import Path

import pytest

from prismqa.prompt_impact import load_manifest, prepare_requests, score_response, score_responses

MANIFEST = Path(__file__).resolve().parents[1] / "data/manifests/prompt-impact-pilot-v1.json"


def test_matched_requests_have_reviewable_identity_and_no_gap_answer_leak() -> None:
    manifest, identity = load_manifest(MANIFEST)
    assert len(manifest["tasks"]) == 12
    requests = prepare_requests(manifest, identity, seed=17)
    assert len(requests) == 48
    assert len({(row["task_id"], row["variant"]) for row in requests}) == 48
    self_repair = next(row for row in requests if row["variant"] == "cosmetic_self_repair")
    assert self_repair["prompt"].startswith("Before answering, correct spelling mistakes")
    assert all('key answer' in task["gap"] for task in manifest["tasks"])
    assert requests == prepare_requests(manifest, identity, seed=17)


def test_cosmetic_edit_cannot_change_numbers_or_output_contract(tmp_path: Path) -> None:
    manifest, _ = load_manifest(MANIFEST)
    for altered_prompt, error in [
        (manifest["tasks"][0]["cosmetic"].replace("1800", "1900"), "numeric tokens"),
        (manifest["tasks"][0]["cosmetic"] + " Extra instruction.", "output contract"),
    ]:
        changed = json.loads(json.dumps(manifest))
        changed["tasks"][0]["cosmetic"] = altered_prompt
        path = tmp_path / "changed.json"
        path.write_text(json.dumps(changed), encoding="utf-8")
        with pytest.raises(ValueError, match=error):
            load_manifest(path)


def test_semantic_answer_is_separate_from_format_compliance() -> None:
    task = {"expected": {"failures": 2}}
    wrapped = score_response(task, "cosmetic", 'Here is the result: {"failures": 2}')
    assert wrapped["semantic_status"] == "correct"
    assert wrapped["format_status"] == "fail"
    wrong = score_response(task, "reference", '{"failures": 3}')
    assert wrong["semantic_status"] == "wrong"
    assert wrong["format_status"] == "pass"
    assert score_response(task, "reference", "Two failures")['semantic_status'] == (
        "human_review_required"
    )


def test_missing_intent_never_uses_hidden_reference_answer() -> None:
    task = {"expected": {"battery": "B"}}
    result = score_response(task, "gap", '{"battery":"B"}')
    assert result["semantic_status"] == "human_review_required"
    assert result["format_status"] == "not_scored"


def test_paired_scoring_rejects_stale_prompts_and_keeps_uncertainty() -> None:
    manifest, identity = load_manifest(MANIFEST)
    requests = [row for row in prepare_requests(manifest, identity, 17)
                if row["task_id"] == "failed_cases"
                and row["variant"] in {"reference", "cosmetic"}]
    outputs = {"reference": '{"failures":2}', "cosmetic": 'Two failures'}
    rows = [{**request, "model_id": "fixture-model", "trial": 1,
             "raw_response": outputs[request["variant"]]} for request in requests]
    report = score_responses(manifest, identity, rows)
    assert report["paired_semantic_counts_by_model"]["fixture-model"]["needs_review"] == 1
    stale = [dict(row) for row in rows]
    stale[0]["prompt_sha256"] = "0" * 64
    with pytest.raises(ValueError, match="prompt SHA-256"):
        score_responses(manifest, identity, stale)


def test_self_repair_is_reported_as_separate_paired_condition() -> None:
    manifest, identity = load_manifest(MANIFEST)
    requests = [row for row in prepare_requests(manifest, identity, 17)
                if row["task_id"] == "failed_cases" and row["variant"] != "gap"]
    outputs = {
        "reference": '{"failures":2}',
        "cosmetic": '{"failures":3}',
        "cosmetic_self_repair": '{"failures":2}',
    }
    rows = [{**request, "model_id": "fixture-model", "trial": 1,
             "raw_response": outputs[request["variant"]]} for request in requests]
    report = score_responses(manifest, identity, rows)
    assert report["paired_semantic_counts_by_model"]["fixture-model"]["reference_only"] == 1
    assert report["paired_self_repair_counts_by_model"]["fixture-model"]["repair_only"] == 1

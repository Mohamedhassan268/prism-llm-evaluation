"""Prepare and score a small matched-prompt feasibility study without model calls."""

from __future__ import annotations

import argparse
import difflib
import hashlib
import json
import random
import re
from collections import Counter, defaultdict
from pathlib import Path
from typing import Any

VARIANTS = ("reference", "cosmetic", "cosmetic_self_repair", "gap")
SELF_REPAIR_PREFIX = (
    "Before answering, correct spelling mistakes in the request below without changing "
    "its numbers, units, constraints, or output keys. Then answer it. "
    "Return only the requested JSON object.\n\n"
)
REQUIRED_TASK_FIELDS = {
    "id",
    "domain",
    "reference",
    "cosmetic",
    "gap",
    "cosmetic_edit",
    "gap_reason",
    "expected",
}
NUMBER_PATTERN = re.compile(r"\d+(?:\.\d+)*")
FORMAT_MARKER = "Return exactly one JSON object"


def load_manifest(path: Path) -> tuple[dict[str, Any], str]:
    raw = path.read_bytes()
    manifest = json.loads(raw)
    if manifest.get("schema_version") != 1 or not isinstance(manifest.get("tasks"), list):
        raise ValueError("Expected a version-1 manifest with a task list")
    tasks = manifest["tasks"]
    if not tasks:
        raise ValueError("The pilot needs at least one task")
    seen: set[str] = set()
    for task in tasks:
        if not isinstance(task, dict) or not REQUIRED_TASK_FIELDS <= task.keys():
            raise ValueError("Every task needs all prompt, edit, oracle and identity fields")
        task_id = task["id"]
        if not isinstance(task_id, str) or not task_id or task_id in seen:
            raise ValueError(f"Missing or duplicate task ID: {task_id!r}")
        seen.add(task_id)
        for field in REQUIRED_TASK_FIELDS - {"expected"}:
            if not isinstance(task[field], str) or not task[field].strip():
                raise ValueError(f"{task_id}: {field} must be nonempty text")
        if not isinstance(task["expected"], dict) or not task["expected"]:
            raise ValueError(f"{task_id}: expected must be a nonempty JSON object")
        if task["reference"] == task["cosmetic"]:
            raise ValueError(f"{task_id}: cosmetic variant is unchanged")
        if task["reference"] == task["gap"]:
            raise ValueError(f"{task_id}: semantic-gap variant is unchanged")
        if NUMBER_PATTERN.findall(task["reference"]) != NUMBER_PATTERN.findall(task["cosmetic"]):
            raise ValueError(f"{task_id}: cosmetic edit changed numeric tokens")
        if FORMAT_MARKER not in task["reference"] or FORMAT_MARKER not in task["cosmetic"]:
            raise ValueError(f"{task_id}: missing output-contract marker")
        if task["reference"].split(FORMAT_MARKER, 1)[1] != task["cosmetic"].split(
            FORMAT_MARKER, 1
        )[1]:
            raise ValueError(f"{task_id}: cosmetic edit changed output contract")
    return manifest, hashlib.sha256(raw).hexdigest()


def audit_pairs(manifest: dict, manifest_sha256: str) -> dict:
    """Expose exact token changes for human equivalence review; do not certify semantics."""
    rows = []
    for task in manifest["tasks"]:
        reference, cosmetic = task["reference"].split(), task["cosmetic"].split()
        changes = []
        for operation, a0, a1, b0, b1 in difflib.SequenceMatcher(
            a=reference, b=cosmetic, autojunk=False
        ).get_opcodes():
            if operation != "equal":
                changes.append({
                    "operation": operation,
                    "reference_tokens": reference[a0:a1],
                    "cosmetic_tokens": cosmetic[b0:b1],
                })
        rows.append({"task_id": task["id"], "changes": changes,
                     "numeric_tokens_preserved": True, "output_contract_preserved": True,
                     "semantic_equivalence": "human_review_pending"})
    return {
        "kind": "prompt_impact_pair_audit",
        "manifest_sha256": manifest_sha256,
        "rows": rows,
        "interpretation": "Structural checks only; semantic equivalence is unverified.",
    }


def render_prompt(task: dict, variant: str) -> str:
    if variant == "cosmetic_self_repair":
        return SELF_REPAIR_PREFIX + task["cosmetic"]
    if variant not in VARIANTS:
        raise ValueError(f"Unknown variant: {variant}")
    return task[variant]


def prepare_requests(manifest: dict[str, Any], manifest_sha256: str, seed: int) -> list[dict]:
    rows = [
        {
            "task_id": task["id"],
            "variant": variant,
            "prompt": render_prompt(task, variant),
            "prompt_sha256": hashlib.sha256(
                render_prompt(task, variant).encode("utf-8")
            ).hexdigest(),
            "manifest_sha256": manifest_sha256,
        }
        for task in manifest["tasks"]
        for variant in VARIANTS
    ]
    random.Random(seed).shuffle(rows)
    return rows


def _parse_json_object(raw: str) -> tuple[dict | None, bool]:
    """Return one JSON object and whether it was the entire, unwrapped response."""
    stripped = raw.strip()
    try:
        direct = json.loads(stripped)
    except json.JSONDecodeError:
        pass
    else:
        return (direct, True) if isinstance(direct, dict) else (None, False)
    start = stripped.find("{")
    if start == -1:
        return None, False
    try:
        parsed, length = json.JSONDecoder().raw_decode(stripped[start:])
    except json.JSONDecodeError:
        return None, False
    if not isinstance(parsed, dict) or "{" in stripped[start + length :]:
        return None, False
    return parsed, False


def score_response(task: dict, variant: str, raw_response: str) -> dict:
    if variant not in VARIANTS or not isinstance(raw_response, str):
        raise ValueError("Expected a known variant and text response")
    if variant == "gap":
        return {
            "semantic_status": "human_review_required",
            "format_status": "not_scored",
            "reason": (
                "The gap prompt lacks necessary intent; "
                "never use the hidden reference answer."
            ),
        }
    parsed, direct = _parse_json_object(raw_response)
    if parsed is None:
        return {"semantic_status": "human_review_required", "format_status": "fail"}
    expected = task["expected"]
    missing = [key for key in expected if key not in parsed]
    if missing:
        semantic_status = "human_review_required"
    elif all(parsed[key] == expected[key] for key in expected):
        semantic_status = "correct"
    else:
        semantic_status = "wrong"
    return {
        "semantic_status": semantic_status,
        "format_status": "pass" if direct and set(parsed) == set(expected) else "fail",
        "parsed_object": parsed,
    }


def score_responses(manifest: dict, manifest_sha256: str, rows: list[dict]) -> dict:
    tasks = {task["id"]: task for task in manifest["tasks"]}
    seen: set[tuple[str, str, str, int]] = set()
    scored: list[dict] = []
    for row in rows:
        if not isinstance(row, dict):
            raise ValueError("Each response row must be a JSON object")
        if row.get("manifest_sha256") != manifest_sha256:
            raise ValueError("Response has a missing or stale manifest SHA-256")
        task_id, variant = row.get("task_id"), row.get("variant")
        model_id, trial = row.get("model_id"), row.get("trial", 1)
        if task_id not in tasks or variant not in VARIANTS:
            raise ValueError(f"Unknown task/variant: {task_id!r}/{variant!r}")
        expected_prompt = render_prompt(tasks[task_id], variant)
        if row.get("prompt") != expected_prompt:
            raise ValueError("Response does not preserve the exact prompt text")
        expected_prompt_hash = hashlib.sha256(expected_prompt.encode("utf-8")).hexdigest()
        if row.get("prompt_sha256") != expected_prompt_hash:
            raise ValueError("Response has a missing or stale prompt SHA-256")
        if not isinstance(model_id, str) or not model_id.strip():
            raise ValueError("Every response needs a pinned model_id")
        if type(trial) is not int or trial < 1:
            raise ValueError("trial must be a positive integer")
        identity = (model_id, task_id, variant, trial)
        if identity in seen:
            raise ValueError(f"Duplicate response: {identity}")
        seen.add(identity)
        scored.append({
            "model_id": model_id,
            "task_id": task_id,
            "variant": variant,
            "trial": trial,
            **score_response(tasks[task_id], variant, row.get("raw_response")),
        })
    by_condition: dict[str, Counter] = defaultdict(Counter)
    by_pair: dict[tuple[str, str, int], dict[str, str]] = defaultdict(dict)
    for row in scored:
        counts = by_condition[f'{row["model_id"]}|{row["variant"]}']
        counts["responses"] += 1
        counts[f'semantic_{row["semantic_status"]}'] += 1
        counts[f'format_{row["format_status"]}'] += 1
        if row["variant"] != "gap":
            by_pair[(row["model_id"], row["task_id"], row["trial"])][row["variant"]] = row[
                "semantic_status"
            ]
    paired: dict[str, Counter] = defaultdict(Counter)
    self_repair_paired: dict[str, Counter] = defaultdict(Counter)
    for (model_id, _, _), outcomes in by_pair.items():
        if not {"reference", "cosmetic"} <= outcomes.keys():
            paired[model_id]["missing_pair"] += 1
        elif "human_review_required" in {outcomes["reference"], outcomes["cosmetic"]}:
            paired[model_id]["needs_review"] += 1
        elif outcomes["reference"] == outcomes["cosmetic"] == "correct":
            paired[model_id]["both_correct"] += 1
        elif outcomes["reference"] == "correct":
            paired[model_id]["reference_only"] += 1
        elif outcomes["cosmetic"] == "correct":
            paired[model_id]["cosmetic_only"] += 1
        else:
            paired[model_id]["neither_correct"] += 1
        if not {"cosmetic", "cosmetic_self_repair"} <= outcomes.keys():
            self_repair_paired[model_id]["missing_pair"] += 1
        elif "human_review_required" in {
            outcomes["cosmetic"], outcomes["cosmetic_self_repair"]
        }:
            self_repair_paired[model_id]["needs_review"] += 1
        elif outcomes["cosmetic"] == outcomes["cosmetic_self_repair"] == "correct":
            self_repair_paired[model_id]["both_correct"] += 1
        elif outcomes["cosmetic"] == "correct":
            self_repair_paired[model_id]["cosmetic_only"] += 1
        elif outcomes["cosmetic_self_repair"] == "correct":
            self_repair_paired[model_id]["repair_only"] += 1
        else:
            self_repair_paired[model_id]["neither_correct"] += 1
    return {
        "kind": "prompt_impact_pilot_scores",
        "manifest_sha256": manifest_sha256,
        "rows": scored,
        "counts_by_model_and_variant": dict(by_condition),
        "paired_semantic_counts_by_model": dict(paired),
        "paired_self_repair_counts_by_model": dict(self_repair_paired),
        "interpretation": (
            "Descriptive only; gap outcomes require human review "
            "and no model effect is inferred."
        ),
    }


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("command", choices=("prepare", "audit", "score"))
    parser.add_argument("--manifest", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--responses", type=Path)
    parser.add_argument("--seed", type=int, default=20260930)
    args = parser.parse_args()
    manifest, identity = load_manifest(args.manifest)
    repo_root = Path(__file__).resolve().parents[2]
    if not args.output.resolve().is_relative_to(repo_root):
        parser.error("--output must remain inside the PRISM repository")
    if args.command == "prepare":
        result = {"seed": args.seed, "manifest_sha256": identity,
                  "requests": prepare_requests(manifest, identity, args.seed)}
    elif args.command == "audit":
        result = audit_pairs(manifest, identity)
    else:
        if args.responses is None:
            parser.error("--responses is required for score")
        rows = [json.loads(line) for line in args.responses.read_text(encoding="utf-8").splitlines()
                if line.strip()]
        result = score_responses(manifest, identity, rows)
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(
        json.dumps(result, indent=2, ensure_ascii=False) + "\n", encoding="utf-8"
    )
    print(f'{args.command}: {len(manifest["tasks"])} tasks; manifest SHA-256 {identity}')


if __name__ == "__main__":
    main()

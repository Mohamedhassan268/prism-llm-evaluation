"""Deterministic, program-group-disjoint sampling; no result-based exclusions."""

from __future__ import annotations

import random
from collections import Counter, defaultdict

from .records import identity, text_hash

LANGUAGES = ("C", "C++", "Go", "Java", "Python")


def program_group(record: dict) -> str:
    # A verified original-problem identity takes precedence. Exact source hashes are a
    # fallback only; distinct source implementations may represent the same problem.
    return record.get("verified_problem_id") or text_hash(record["source_code"])


def sample(
    records: list[dict], *, seed: int = 20260929, calibration: int = 10, evaluation: int = 100
) -> dict:
    if not records or calibration < 1 or evaluation < 1:
        raise ValueError("Nonempty records and positive split sizes are required")
    identifiers = [record.get("id") for record in records]
    if any(not identifier for identifier in identifiers) or len(set(identifiers)) != len(records):
        raise ValueError("Sampling requires unique, nonempty record IDs")
    # One translation pair is selected once; every available model/condition row follows it.
    pairs: dict[str, dict] = {}
    rows: dict[str, list[str]] = defaultdict(list)
    for record in records:
        pair = str(record.get("sample_id", record["id"]))
        signature = (record["source_code"], record["source_language"], record["target_language"])
        if pair in pairs and signature != (
            pairs[pair]["source_code"],
            pairs[pair]["source_language"],
            pairs[pair]["target_language"],
        ):
            raise ValueError(f"Conflicting translation pair identity {pair}")
        pairs[pair] = record
        rows[pair].append(record["id"])
    rng = random.Random(seed)
    candidates = sorted(pairs)
    rng.shuffle(candidates)
    ranks = {pair: rank for rank, pair in enumerate(candidates)}
    observed_languages = sorted({pairs[pair]["target_language"] for pair in candidates})
    if not set(observed_languages).issubset(LANGUAGES):
        raise ValueError("Unsupported target language in sample")
    groups: dict[str, str] = {}

    def select(size: int, split: str) -> list[str]:
        targets = Counter()
        directions = Counter()
        selected: list[str] = []
        available = list(candidates)
        quota = {language: size // len(observed_languages) for language in observed_languages}
        for language in observed_languages[: size % len(observed_languages)]:
            quota[language] += 1
        while len(selected) < size:
            eligible = [
                pair
                for pair in available
                if targets[pairs[pair]["target_language"]] < quota[pairs[pair]["target_language"]]
                and groups.get(program_group(pairs[pair]), split) == split
            ]
            if not eligible:
                break
            pair = min(
                eligible,
                key=lambda item: (
                    targets[pairs[item]["target_language"]],
                    directions[(pairs[item]["source_language"], pairs[item]["target_language"])],
                    ranks[item],
                ),
            )
            record = pairs[pair]
            selected.append(pair)
            available.remove(pair)
            targets[record["target_language"]] += 1
            directions[(record["source_language"], record["target_language"])] += 1
            groups[program_group(record)] = split
        for pair in selected:
            candidates.remove(pair)
        return selected

    calibration_pairs = select(calibration, "calibration")
    evaluation_pairs = select(evaluation, "evaluation")
    splits = {"calibration": calibration_pairs, "evaluation": evaluation_pairs}
    manifest = {
        "schema_version": 1,
        "seed": seed,
        "dataset_identity": identity(records),
        "requested": {"calibration": calibration, "evaluation": evaluation},
        "pair_ids": splits,
        "record_ids": {
            name: sorted(identifier for pair in selected for identifier in rows[pair])
            for name, selected in splits.items()
        },
        "program_groups": {
            name: sorted({program_group(pairs[pair]) for pair in selected})
            for name, selected in splits.items()
        },
        "counts_by_target": {
            name: dict(Counter(pairs[pair]["target_language"] for pair in selected))
            for name, selected in splits.items()
        },
        "grouping_limit": "Verified problem IDs where supplied; otherwise exact source hash. "
        "Cross-implementation problem overlap cannot be ruled out.",
        "eligible_pairs": len(pairs),
        "excluded_after_results": 0,
    }
    manifest["manifest_identity"] = identity(manifest)
    return manifest

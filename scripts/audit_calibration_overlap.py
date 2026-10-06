"""Record confirmed problem overlap without altering the frozen v1 sample."""

from collections import Counter
from pathlib import Path

from prismqa.records import identity, read_json, write_json

ROOT = Path(__file__).resolve().parents[1]
CONFIRMED = {
    "60109": ("62222", "abc073_a"),
    "60232": ("61358", "ITP1_1_D"),
    "61669": ("59448", "abc145_a"),
}


def main():
    manifest = read_json(ROOT / "data/manifests/track-a-sample.json")
    pairs = {p["sample_id"]: p for p in read_json(ROOT / "data/cache/pairs.json")}
    findings = []
    for heldout, (calibration, task) in CONFIRMED.items():
        assert heldout in manifest["pair_ids"]["evaluation"]
        assert calibration in manifest["pair_ids"]["calibration"]
        assert pairs[heldout]["original_tests"] == pairs[calibration]["original_tests"]
        findings.append(
            {
                "heldout_pair": heldout,
                "calibration_pair": calibration,
                "task": task,
                "target_language": pairs[heldout]["target_language"],
                "basis": "Identical official sample and reviewed source algorithms "
                "implement the same problem in different languages.",
                "original_test_identity": identity(pairs[heldout]["original_tests"]),
                "heldout_source": pairs[heldout]["source_code"],
                "calibration_source_identity": identity(pairs[calibration]["source_code"]),
            }
        )
    retained = [pair for pair in manifest["pair_ids"]["evaluation"] if pair not in CONFIRMED]
    proposal = {
        "status": "proposed amendment, pending final-design review",
        "original_manifest_identity": manifest["manifest_identity"],
        "findings": findings,
        "recommended_rule": "Exclude confirmed calibration-problem overlap before "
        "grading held-out translations; preserve the frozen v1 selection.",
        "proposed_retained_pairs": retained,
        "proposed_count": len(retained),
        "proposed_counts_by_target": dict(Counter(pairs[p]["target_language"] for p in retained)),
        "remaining_limit": "Other cross-implementation overlap is not ruled out. "
        "Full task mapping is still required.",
        "heldout_translation_results_seen": False,
    }
    write_json(ROOT / "data/manifests/calibration-overlap-audit.json", proposal)
    print(proposal["proposed_counts_by_target"])


if __name__ == "__main__":
    main()

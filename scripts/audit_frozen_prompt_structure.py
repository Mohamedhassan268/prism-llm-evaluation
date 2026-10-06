"""Audit the frozen new prompt sample without assuming its language is English."""

from pathlib import Path

from prismqa.prompts import audit_prompts
from prismqa.records import file_hash, identity, read_json, write_json

ROOT = Path(__file__).resolve().parents[1]


def main():
    manifest = read_json(ROOT / "data/manifests/track-b-sample.json")
    original = read_json(ROOT / "data/cache/track-b-prompts.json")
    if identity(original) != manifest["records_identity"]:
        raise ValueError("Frozen prompt sample changed")
    for artifact in manifest["artifacts"]:
        if file_hash(ROOT / artifact["path"]) != artifact["sha256"]:
            raise ValueError("Pinned prompt artifact changed")
    if any("language" in item for item in original):
        raise ValueError("Unexpected prior language declarations; inspect before applying overlay")
    # und means undetermined, not an assertion that the text is non-English.
    # The existing auditor excludes it from English-only measurements.
    annotated = [{**item, "language": "und"} for item in original]
    report = audit_prompts(annotated, profile="extension")
    output = {
        "scope": "structural-only contemporary reconstruction; not the authors' corpus",
        "original_sample_identity": identity(original),
        "annotation_identity": identity(annotated),
        "language_overlay": "und for every record; language screening remains pending",
        "english_metrics_interpretable": False,
        "language_overlay_is_not_language_composition": True,
        "limitations": [
            "One collection repository; application/courseware categories absent.",
            "Unknown template-variable contracts are not inferred from arbitrary braces.",
            "No prompt execution, embeddings, behavioral comparison or paid calls.",
            "Raw-string duplication and word counts do not establish prompt effectiveness.",
        ],
        "report": report,
    }
    write_json(ROOT / "reports/track-b-structure-only.json", output)
    print({"records": len(original), "scope": output["scope"]})


if __name__ == "__main__":
    main()

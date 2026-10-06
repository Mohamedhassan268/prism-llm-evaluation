"""Reuse sources only when code, cases and toolchain match verified evidence."""

import copy
from pathlib import Path

from .evaluation import verified_report
from .records import identity, inside, read_json, text_hash
from .runner import ContainerRunner


class ReferenceCacheRunner:
    def __init__(self, root: Path, validation_run: str, *, base=None):
        self.base = base or ContainerRunner(root)
        directory = inside(root, validation_run)
        state, summary = verified_report(directory)
        if state["toolchain"] != self.base.lock:
            raise ValueError("Reference cache toolchain differs from current environment")
        if summary["original_test_passes"] != len(state["expected_ids"]) or summary[
            "additional_statuses"
        ] != {"pass": len(state["expected_ids"])}:
            raise ValueError("Reference controls are not all validated passes")
        self.cache = {}
        for identifier in state["expected_ids"]:
            record = read_json(directory / "records" / (text_hash(identifier) + ".json"))
            if record["data_kind"] != "authors_source_control":
                raise ValueError("Reference cache accepts original-source controls only")
            key = (
                record["extraction"]["code_hash"],
                record["target_language"],
                identity([(test["input_hash"], test["expected_hash"]) for test in record["tests"]]),
            )
            self.cache[key] = {
                **record["oracle_check"],
                "execution_origin": "reused_validated_source",
                "validation_run_identity": state["run_identity"],
                "validation_record_identity": record["result_identity"],
            }
        items = [
            {"key": list(key), "execution": value} for key, value in sorted(self.cache.items())
        ]
        self.lock = {
            **self.base.lock,
            "reference_cache_run_identity": state["run_identity"],
            "reference_cache_identity": identity(items),
        }

    def run_program(self, *args, **kwargs):
        return self.base.run_program(*args, **kwargs)

    def run_reference(self, code, language, cases, directory):
        key = (
            text_hash(code),
            language,
            identity([(text_hash(case["input"]), text_hash(case["expected"])) for case in cases]),
        )
        if key not in self.cache:
            raise ValueError("Reference code/cases differ from the frozen validated control")
        return copy.deepcopy(self.cache[key])

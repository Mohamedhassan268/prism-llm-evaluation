"""Auditable static prompt measurements; no model calls or prompt execution."""

from __future__ import annotations

import hashlib
import itertools
import json
import math
import re
from collections import Counter, defaultdict
from collections.abc import Mapping, Sequence
from importlib import import_module
from importlib import metadata as package_metadata
from pathlib import Path, PurePosixPath
from typing import Any

WORD_PATTERN = re.compile(r"\w+", flags=re.UNICODE)
PROVENANCE_FIELDS = ("repository", "commit", "path")
SUPPORTED_PROFILES = {"baseline", "extension"}
SIMILARITY_THRESHOLD = 0.95


class PromptValidationError(ValueError):
    """The corpus is structurally invalid or cannot be interpreted safely."""


def prompt_hash(text: str) -> str:
    """Hash raw Unicode text as UTF-8, without trimming or normalization."""
    if not isinstance(text, str):
        raise PromptValidationError("Prompt text must be a string")
    return hashlib.sha256(text.encode("utf-8")).hexdigest()


def _variable_names(value: Any, field: str, record_id: str) -> set[str]:
    if isinstance(value, Mapping) and field == "supplied_variables":
        names = list(value)
    elif isinstance(value, list):
        names = value
    else:
        raise PromptValidationError(
            f"{record_id}: {field} must be a list of names or, for supplied_variables, an object"
        )
    if any(not isinstance(name, str) or not name.strip() for name in names):
        raise PromptValidationError(f"{record_id}: {field} contains an empty/non-string name")
    if len(names) != len(set(names)):
        raise PromptValidationError(f"{record_id}: {field} contains duplicate names")
    return set(names)


def validate_prompt_records(records: list[dict]) -> None:
    """Reject malformed containers/identifiers; missing data becomes audit flags."""
    if not isinstance(records, list) or not records:
        raise PromptValidationError("The prompt corpus must be a nonempty list")
    seen: set[str] = set()
    for index, record in enumerate(records):
        if not isinstance(record, dict):
            raise PromptValidationError(f"Record {index} must be an object")
        record_id = record.get("id")
        if not isinstance(record_id, str) or not record_id.strip():
            raise PromptValidationError(f"Record {index} needs a nonempty string id")
        if record_id in seen:
            raise PromptValidationError(f"Duplicate prompt id: {record_id}")
        seen.add(record_id)
        for field in ("text", *PROVENANCE_FIELDS, "language", "corpus_kind"):
            if field in record and record[field] is not None and not isinstance(record[field], str):
                raise PromptValidationError(f"{record_id}: {field} must be a string or null")
        for field in ("declared_variables", "supplied_variables"):
            if field in record:
                _variable_names(record[field], field, record_id)
        if "supplied_variables" in record and "declared_variables" not in record:
            raise PromptValidationError(
                f"{record_id}: supplied_variables requires declared_variables"
            )
        if record.get("template_syntax", "brace") not in {"brace", "double_brace", "dollar_brace"}:
            raise PromptValidationError(f"{record_id}: unknown template_syntax")
        recorded_hash = record.get("recorded_response_prompt_hash")
        if recorded_hash is not None and (
            not isinstance(recorded_hash, str)
            or not re.fullmatch(r"[0-9a-fA-F]{64}", recorded_hash)
        ):
            raise PromptValidationError(
                f"{record_id}: recorded_response_prompt_hash must be SHA-256 hex"
            )


def _json_object(pairs: list[tuple[str, Any]]) -> dict:
    result: dict = {}
    for key, value in pairs:
        if key in result:
            raise PromptValidationError(f"Duplicate JSON field: {key}")
        result[key] = value
    return result


def _invalid_constant(value: str) -> None:
    raise PromptValidationError(f"Non-standard JSON numeric constant: {value}")


def _decode_json(text: str) -> Any:
    try:
        return json.loads(text, object_pairs_hook=_json_object, parse_constant=_invalid_constant)
    except json.JSONDecodeError as error:
        raise PromptValidationError(f"Malformed JSON: {error}") from error


def _fenced_prompts(text: str) -> list[str]:
    """Explicit reconstruction adapter: only standalone ```prompt blocks."""
    prompts: list[str] = []
    body: list[str] | None = None
    other_fence_length = 0
    for line in text.splitlines(keepends=True):
        stripped = line.rstrip("\r\n")
        if other_fence_length:
            if re.fullmatch(r"`{" + str(other_fence_length) + r",}\s*", stripped):
                other_fence_length = 0
            continue
        if body is None:
            if re.fullmatch(r"```prompt\s*", stripped):
                body = []
            else:
                other_fence = re.match(r"^(`{3,})([^`]*)$", stripped)
                if other_fence:
                    other_fence_length = len(other_fence.group(1))
        elif re.fullmatch(r"```\s*", stripped):
            prompts.append("".join(body))
            body = None
        else:
            body.append(line)
    if body is not None:
        raise PromptValidationError("Unclosed fenced-prompt-v1 prompt block")
    if not prompts:
        raise PromptValidationError("No declared ```prompt blocks found")
    return prompts


def load_prompt_records(
    path: str | Path, *, metadata: dict | None = None, adapter: str | None = None
) -> list[dict]:
    """Load JSON/JSONL; TXT/Markdown require an explicit extraction adapter.

    Metadata supplies shared provenance. A record's values take precedence.
    No Markdown/TXT content is inferred to be a prompt without an adapter.
    """
    source = Path(path)
    shared = dict(metadata or {})
    suffix = source.suffix.lower()
    # Avoid universal-newline conversion: raw prompt hashes distinguish CRLF/LF.
    text = source.read_bytes().decode("utf-8")
    if suffix in {".json", ".jsonl", ".ndjson"}:
        if adapter is not None:
            raise PromptValidationError("Structured JSON ingestion does not accept a text adapter")
        if suffix == ".json":
            payload = _decode_json(text.removeprefix("\ufeff"))
            if isinstance(payload, dict) and "records" in payload:
                records = payload["records"]
                if "corpus_kind" in payload:
                    shared.setdefault("corpus_kind", payload["corpus_kind"])
            else:
                records = payload
        else:
            records = []
            for number, line in enumerate(text.removeprefix("\ufeff").splitlines(), 1):
                if line.strip():
                    try:
                        records.append(_decode_json(line))
                    except PromptValidationError as error:
                        raise PromptValidationError(f"JSONL line {number}: {error}") from error
        if not isinstance(records, list) or not records:
            raise PromptValidationError("Structured corpus must contain a nonempty records list")
        if any(not isinstance(record, dict) for record in records):
            raise PromptValidationError("Each structured prompt record must be an object")
        records = [shared | record for record in records]
    elif suffix in {".txt", ".md", ".markdown"}:
        if adapter == "single-prompt-v1":
            bodies = [text]
        elif adapter == "fenced-prompt-v1" and suffix in {".md", ".markdown"}:
            bodies = _fenced_prompts(text)
        else:
            raise PromptValidationError(
                "TXT/Markdown requires an explicit supported extraction adapter"
            )
        base_id = shared.get("id")
        if not isinstance(base_id, str) or not base_id.strip():
            raise PromptValidationError("Text extraction requires an explicit metadata id")
        records = []
        for index, body in enumerate(bodies):
            record = shared | {"text": body, "extraction_adapter": adapter}
            record.setdefault("path", source.name)
            record["id"] = base_id if len(bodies) == 1 else f"{base_id}:{index + 1}"
            records.append(record)
    else:
        raise PromptValidationError(f"Unsupported prompt storage format: {suffix or '(none)'}")
    validate_prompt_records(records)
    return records


def _flag(record_id: str, code: str, **detail: Any) -> dict:
    return {"id": record_id, "code": code, "review_status": "review_required", **detail}


def _placeholder_pattern(name: str, syntax: str) -> re.Pattern:
    escaped = re.escape(name)
    if syntax == "double_brace":
        return re.compile(r"\{\{\s*" + escaped + r"\s*\}\}")
    if syntax == "dollar_brace":
        return re.compile(r"\$\{" + escaped + r"\}")
    return re.compile(r"(?<![{$])\{" + escaped + r"\}(?!\})")


def _record_assessment(record: dict) -> tuple[dict, list[dict]]:
    record_id = record["id"]
    text = record.get("text")
    valid_text = isinstance(text, str) and bool(text.strip())
    missing_provenance = [
        field for field in PROVENANCE_FIELDS if not record.get(field) or not record[field].strip()
    ]
    flags = []
    if not valid_text:
        flags.append(_flag(record_id, "missing_text"))
    if missing_provenance:
        flags.append(_flag(record_id, "missing_provenance", fields=missing_provenance))
    language = record.get("language") or "unspecified"
    english_eligible = language.lower().split("-")[0].split("_")[0] in {
        "en",
        "english",
        "unspecified",
    }
    assessment = {
        "id": record_id,
        "text": text,
        "prompt_hash": prompt_hash(text) if isinstance(text, str) else None,
        "word_count": len(WORD_PATTERN.findall(text)) if valid_text else None,
        "provenance": {field: record.get(field) for field in PROVENANCE_FIELDS},
        "provenance_complete": not missing_provenance,
        "text_complete": valid_text,
        "language": language,
        "language_assessment": "assumed_english_unverified"
        if language == "unspecified"
        else "declared_only",
        "english_metric_eligible": english_eligible and valid_text,
        "corpus_kind": record.get("corpus_kind", "unspecified"),
        "variable_contract": {"status": "not_declared"},
        "recorded_response": {"status": "not_provided"},
    }
    if "declared_variables" in record:
        declared = _variable_names(record["declared_variables"], "declared_variables", record_id)
        supplied = _variable_names(
            record.get("supplied_variables", []), "supplied_variables", record_id
        )
        absent = sorted(
            name
            for name in declared
            if not isinstance(text, str)
            or not _placeholder_pattern(name, record.get("template_syntax", "brace")).search(text)
        )
        missing = sorted(declared - supplied)
        unexpected = sorted(supplied - declared)
        assessment["variable_contract"] = {
            "status": "review_required" if absent or missing or unexpected else "matched",
            "syntax": record.get("template_syntax", "brace"),
            "declared": sorted(declared),
            "supplied": sorted(supplied),
            "declared_not_in_text": absent,
            "missing_supplied": missing,
            "unexpected_supplied": unexpected,
        }
        if absent or missing or unexpected:
            flags.append(
                _flag(
                    record_id,
                    "variable_contract_mismatch",
                    declared_not_in_text=absent,
                    missing_supplied=missing,
                    unexpected_supplied=unexpected,
                )
            )
    recorded_hash = record.get("recorded_response_prompt_hash")
    if recorded_hash is not None:
        status = (
            "unverifiable"
            if assessment["prompt_hash"] is None
            else ("matched" if recorded_hash.lower() == assessment["prompt_hash"] else "stale")
        )
        assessment["recorded_response"] = {"status": status, "prompt_hash": recorded_hash}
        if status != "matched":
            flags.append(_flag(record_id, "recorded_response_prompt_hash_mismatch", status=status))
    return assessment, flags


def _version(distribution: str) -> str | None:
    try:
        return package_metadata.version(distribution)
    except package_metadata.PackageNotFoundError:
        return None


def _optional_measurements(assessments: list[dict]) -> dict:
    eligible = [record for record in assessments if record["english_metric_eligible"]]
    measurements = {}
    for name, module_name, distribution in (
        ("spelling", "spellchecker", "pyspellchecker"),
        ("readability", "textstat", "textstat"),
    ):
        config = (
            {"language": "en", "case_sensitive": False, "tokenizer": r"\w+"}
            if name == "spelling"
            else {"language": "en_US", "metric": "flesch_reading_ease"}
        )
        entry = {
            "status": "unavailable",
            "package": distribution,
            "version": _version(distribution),
            "configuration": config,
            "implementation_status": "reconstructed_configuration",
            "eligible_count": len(eligible),
            "measured_count": 0,
            "values": None,
        }
        try:
            module = import_module(module_name)
        except ImportError as error:
            entry["reason"] = f"Optional dependency unavailable: {error}"
            measurements[name] = entry
            continue
        try:
            values = []
            if name == "spelling":
                checker = module.SpellChecker(language="en", case_sensitive=False)
                for record in eligible:
                    unknown = sorted(checker.unknown(WORD_PATTERN.findall(record["text"].lower())))
                    values.append(
                        {
                            "id": record["id"],
                            "unknown_words": unknown,
                            "flag_count": len(unknown),
                            "review_status": "review_required",
                            "interpretation": "dictionary_flags_not_confirmed_errors",
                        }
                    )
            else:
                module.set_lang("en_US")
                for record in eligible:
                    score = float(module.flesch_reading_ease(record["text"]))
                    if not math.isfinite(score):
                        raise ValueError("Non-finite readability result")
                    values.append({"id": record["id"], "flesch_reading_ease": score})
            entry.update(status="available", measured_count=len(values), values=values)
        except (ValueError, TypeError, AttributeError, LookupError, OSError, RuntimeError) as error:
            entry.update(status="error", reason=f"Measurement failed: {error}")
        measurements[name] = entry
    return measurements


def _exact_duplicates(assessments: list[dict]) -> dict:
    groups: dict[str, list[dict]] = defaultdict(list)
    for record in assessments:
        if record["text_complete"]:
            groups[record["text"]].append(record)
    within: list[dict] = []
    across: list[dict] = []
    internal_ids: set[str] = set()
    external_ids: set[str] = set()
    for records in groups.values():
        by_repository: dict[str, list[str]] = defaultdict(list)
        for record in records:
            repository = record["provenance"]["repository"]
            if repository and repository.strip():
                by_repository[repository].append(record["id"])
        for repository, ids in sorted(by_repository.items()):
            if len(ids) > 1:
                internal_ids.update(ids)
                within.append(
                    {"repository": repository, "ids": ids, "prompt_hash": records[0]["prompt_hash"]}
                )
        if len(by_repository) > 1:
            ids = [record_id for members in by_repository.values() for record_id in members]
            external_ids.update(ids)
            across.append(
                {
                    "repositories": sorted(by_repository),
                    "ids": ids,
                    "prompt_hash": records[0]["prompt_hash"],
                }
            )
    eligible_count = sum(
        record["text_complete"]
        and bool(record["provenance"]["repository"])
        and bool(record["provenance"]["repository"].strip())
        for record in assessments
    )
    return {
        "comparison": "exact_raw_unicode_string",
        "eligible_count": eligible_count,
        "within_repository_groups": within,
        "across_repository_groups": across,
        "within_participating_record_count": len(internal_ids),
        "across_participating_record_count": len(external_ids),
        "any_participating_record_count": len(internal_ids | external_ids),
        "count_definition": "all records participating in a duplicate group, not redundant copies",
    }


def _similarity(assessments: list[dict], embeddings: Any) -> dict:
    result = {
        "status": "not_requested",
        "threshold": SIMILARITY_THRESHOLD,
        "threshold_operator": ">",
        "candidate_pairs": [],
        "interpretation": "similarity_candidates_not_semantic_equivalence",
    }
    if embeddings is None:
        return result
    if isinstance(embeddings, Mapping):
        if set(embeddings) != {record["id"] for record in assessments}:
            raise PromptValidationError("Embedding keys must exactly match prompt ids")
        rows = [embeddings[record["id"]] for record in assessments]
    elif isinstance(embeddings, Sequence) and not isinstance(embeddings, (str, bytes)):
        rows = list(embeddings)
        if len(rows) != len(assessments):
            raise PromptValidationError("Embeddings must align one-to-one with prompt records")
    else:
        raise PromptValidationError("Embeddings must be an aligned sequence or id mapping")
    vectors = []
    dimension = None
    for row in rows:
        if not isinstance(row, Sequence) or isinstance(row, (str, bytes)) or not row:
            raise PromptValidationError("Each embedding must be a nonempty numeric sequence")
        if any(
            isinstance(value, bool)
            or not isinstance(value, (int, float))
            or not math.isfinite(value)
            for value in row
        ):
            raise PromptValidationError("Embedding values must be finite numbers")
        if dimension is None:
            dimension = len(row)
        if len(row) != dimension:
            raise PromptValidationError("Embedding dimensions must match")
        norm = math.hypot(*row)
        if norm == 0 or not math.isfinite(norm):
            raise PromptValidationError("Embedding norms must be finite and nonzero")
        vectors.append([value / norm for value in row])
    pairs = []
    eligible_indices = [
        index for index, record in enumerate(assessments) if record["text_complete"]
    ]
    for left, right in itertools.combinations(eligible_indices, 2):
        cosine = max(
            -1.0, min(1.0, sum(a * b for a, b in zip(vectors[left], vectors[right], strict=True)))
        )
        if cosine > SIMILARITY_THRESHOLD:
            pairs.append(
                {
                    "ids": [assessments[left]["id"], assessments[right]["id"]],
                    "cosine_similarity": cosine,
                    "review_status": "review_required",
                }
            )
    result.update(
        status="available",
        candidate_pairs=pairs,
        embedding_source="caller_supplied",
        dimension=dimension,
        eligible_count=len(eligible_indices),
    )
    return result


def audit_prompts(
    records: list[dict], *, profile: str = "baseline", embeddings: Any = None
) -> dict:
    """Measure prompt maintenance; preserve raw text and make exclusions visible.

    Baseline and extension profiles share the paper-aligned descriptive metrics.
    Contract/provenance checks are explicitly labeled extensions in both profiles.
    Optional tools run locally if installed; this function never downloads models.
    """
    if profile not in SUPPORTED_PROFILES:
        raise PromptValidationError(f"Unknown prompt profile: {profile}")
    validate_prompt_records(records)
    assessments = []
    flags = []
    for record in records:
        assessment, record_flags = _record_assessment(record)
        assessments.append(assessment)
        flags.extend(record_flags)
    paths = [
        record["provenance"]["path"]
        for record in assessments
        if record["provenance"]["path"] and record["provenance"]["path"].strip()
    ]
    formats = Counter(
        PurePosixPath(path.replace("\\", "/")).suffix.lower() or "(none)" for path in paths
    )
    repository_formats: dict[str, set[str]] = defaultdict(set)
    for record in assessments:
        repository, path = record["provenance"]["repository"], record["provenance"]["path"]
        if repository and repository.strip() and path and path.strip():
            repository_formats[repository].add(
                PurePosixPath(path.replace("\\", "/")).suffix.lower() or "(none)"
            )
    repositories = {
        record["provenance"]["repository"]
        for record in assessments
        if record["provenance"]["repository"] and record["provenance"]["repository"].strip()
    }
    words = [record["word_count"] for record in assessments if record["word_count"] is not None]
    corpus_kind_counts = Counter(record["corpus_kind"] for record in assessments)
    return {
        "schema_version": 1,
        "audit_kind": "static_prompt_maintenance",
        "profile": profile,
        "profile_version": "prompt-maintenance-v1",
        "corpus_status": "incomplete"
        if any(flag["code"] in {"missing_text", "missing_provenance"} for flag in flags)
        else "complete",
        "corpus_kind_counts": dict(sorted(corpus_kind_counts.items())),
        "record_count": len(assessments),
        "repository_count": len(repositories),
        "text_record_count": len(words),
        "provenance_record_count": sum(record["provenance_complete"] for record in assessments),
        "word_counts": {
            "pattern": r"\w+",
            "eligible_count": len(words),
            "total": sum(words),
            "mean": sum(words) / len(words) if words else None,
        },
        "storage_distribution": {
            "record_denominator": len(paths),
            "records_by_suffix": dict(sorted(formats.items())),
            "repository_denominator": len(repository_formats),
            "repositories_by_suffix": {
                suffix: sum(suffix in values for values in repository_formats.values())
                for suffix in sorted(formats)
            },
        },
        "language_scope": {
            "baseline": "English-only spelling/readability",
            "detection": "none",
            "assumed_english_count": sum(
                record["language"] == "unspecified" for record in assessments
            ),
            "excluded_from_english_metrics": [
                record["id"] for record in assessments if not record["english_metric_eligible"]
            ],
        },
        "exact_duplicates": _exact_duplicates(assessments),
        "measurements": _optional_measurements(assessments),
        "similarity": _similarity(assessments, embeddings),
        "extension_checks": {
            "status": "measured",
            "flags": flags,
            "interpretation": "contract_and_provenance_checks_not_original_quality_metrics",
        },
        "records": assessments,
        "limitations": [
            "Static measurements do not establish LLM output correctness or effectiveness.",
            "Unknown dictionary words require human review, especially technical vocabulary.",
            "Language metadata is declared or assumed; "
            "automatic language detection is not performed.",
            "Readability and spelling implementation details are reconstructed "
            "until original configurations are recovered.",
        ],
    }

"""Contract tests using controlled fixtures, not the paper's measured corpus."""

import hashlib
import json
from copy import deepcopy
from pathlib import Path
from types import SimpleNamespace

import pytest

from prismqa.prompts import (
    PromptValidationError,
    audit_prompts,
    load_prompt_records,
    prompt_hash,
)


def record(record_id="p1", text="Return a JSON object.", repository="fixture/collection", **extra):
    return {
        "id": record_id,
        "text": text,
        "repository": repository,
        "commit": "controlled-fixture-v1",
        "path": f"{record_id}.md",
        "language": "en",
        "corpus_kind": "controlled_fixture",
        **extra,
    }


@pytest.fixture(autouse=True)
def optional_dependencies_missing(monkeypatch):
    def unavailable(name):
        raise ImportError(f"Controlled missing dependency: {name}")

    monkeypatch.setattr("prismqa.prompts.import_module", unavailable)


@pytest.mark.parametrize("corpus", [[], {}, None, ["prompt"], [{"text": "hello"}], [record(" ")]])
def test_malformed_or_empty_corpus_cannot_be_success(corpus):
    with pytest.raises(PromptValidationError):
        audit_prompts(corpus)


def test_duplicate_ids_are_rejected_even_when_text_differs():
    with pytest.raises(PromptValidationError, match="Duplicate prompt id"):
        audit_prompts([record(), record(text="Different instruction.")])


def test_raw_unicode_whitespace_hashes_and_original_word_regex_are_preserved():
    text = "  C++ naïve_thing 42\nJSON!  "
    result = audit_prompts([record(text=text)])
    assert result["records"][0]["text"] == text
    assert result["records"][0]["word_count"] == 4
    assert result["records"][0]["prompt_hash"] == hashlib.sha256(text.encode("utf-8")).hexdigest()
    assert prompt_hash(text) != prompt_hash(text.strip())


def test_exact_duplicates_count_participants_and_keep_repository_denominators():
    corpus = [
        record("a", "Same.", "fixture/A"),
        record("b", "Same.", "fixture/A"),
        record("c", "Same.", "fixture/B"),
        record("d", "Same. ", "fixture/B"),
        record("e", "Unique.", "fixture/B", path="a.json"),
    ]
    result = audit_prompts(corpus)
    duplicate = result["exact_duplicates"]
    assert duplicate["eligible_count"] == 5
    assert duplicate["within_participating_record_count"] == 2
    assert duplicate["across_participating_record_count"] == 3
    assert duplicate["any_participating_record_count"] == 3
    assert duplicate["within_repository_groups"][0]["ids"] == ["a", "b"]
    storage = result["storage_distribution"]
    assert storage["record_denominator"] == 5
    assert storage["records_by_suffix"] == {".json": 1, ".md": 4}
    assert storage["repository_denominator"] == 2
    assert storage["repositories_by_suffix"] == {".json": 1, ".md": 2}


def test_missing_data_is_visible_and_excluded_from_affected_counts():
    bad = {"id": "bad", "repository": "", "commit": None, "path": None}
    result = audit_prompts([record(), bad, record("empty", " \n", repository="fixture/B")])
    assert result["corpus_status"] == "incomplete"
    assert result["record_count"] == 3
    assert result["text_record_count"] == 1
    assert result["provenance_record_count"] == 2
    assert result["word_counts"]["eligible_count"] == 1
    assert result["word_counts"]["mean"] == 4
    assert result["storage_distribution"]["record_denominator"] == 2
    assert {flag["code"] for flag in result["extension_checks"]["flags"]} == {
        "missing_text",
        "missing_provenance",
    }


def test_all_missing_text_means_no_word_average_not_a_fake_zero():
    result = audit_prompts([record(text=None)])
    assert result["word_counts"]["eligible_count"] == 0
    assert result["word_counts"]["mean"] is None
    assert result["corpus_status"] == "incomplete"


def test_unavailable_tools_are_reported_not_zero_measurements():
    result = audit_prompts([record()])
    for measurement in result["measurements"].values():
        assert measurement["status"] == "unavailable"
        assert measurement["eligible_count"] == 1
        assert measurement["measured_count"] == 0
        assert measurement["values"] is None


def test_optional_dictionary_flags_are_review_candidates_not_confirmed_typos(monkeypatch):
    class TechnicalDictionary:
        def __init__(self, **configuration):
            assert configuration == {"language": "en", "case_sensitive": False}

        def unknown(self, words):
            return {word for word in words if word in {"pytest", "llm"}}

    module = SimpleNamespace(
        SpellChecker=TechnicalDictionary,
        set_lang=lambda language: None,
        flesch_reading_ease=lambda text: 57.5,
    )
    monkeypatch.setattr("prismqa.prompts.import_module", lambda name: module)
    result = audit_prompts([record(text="Use pytest for LLM checks.")])
    spelling = result["measurements"]["spelling"]
    assert spelling["status"] == "available"
    assert spelling["values"][0]["unknown_words"] == ["llm", "pytest"]
    assert spelling["values"][0]["review_status"] == "review_required"
    assert spelling["values"][0]["interpretation"] == "dictionary_flags_not_confirmed_errors"
    assert result["measurements"]["readability"]["values"][0]["flesch_reading_ease"] == 57.5


def test_declared_language_exclusion_and_unspecified_language_are_auditable():
    unknown = record("unknown")
    del unknown["language"]
    result = audit_prompts(
        [record("english"), record("french", "Bonjour.", language="fr"), unknown]
    )
    assert result["language_scope"]["assumed_english_count"] == 1
    assert result["language_scope"]["excluded_from_english_metrics"] == ["french"]
    assert result["measurements"]["spelling"]["eligible_count"] == 2
    assert result["records"][2]["language_assessment"] == "assumed_english_unverified"


def test_declared_variables_do_not_treat_json_braces_as_placeholders():
    corpus = [
        record("json", 'Return {"answer": 1}.', declared_variables=[], supplied_variables={}),
        record(
            "template",
            'Write {topic}; emit {"answer": 1}.',
            declared_variables=["topic"],
            supplied_variables={"topic": "QA"},
        ),
    ]
    result = audit_prompts(corpus)
    assert all(item["variable_contract"]["status"] == "matched" for item in result["records"])
    assert result["extension_checks"]["flags"] == []


def test_variable_mismatch_detects_missing_supplied_and_unused_declarations():
    result = audit_prompts(
        [
            record(
                text="Summarize {topic}.",
                declared_variables=["topic", "style"],
                supplied_variables={"extra": "x"},
            )
        ]
    )
    contract = result["records"][0]["variable_contract"]
    assert contract["missing_supplied"] == ["style", "topic"]
    assert contract["declared_not_in_text"] == ["style"]
    assert contract["unexpected_supplied"] == ["extra"]
    assert contract["status"] == "review_required"


@pytest.mark.parametrize(
    "text,syntax", [("{{ topic }}", "double_brace"), ("${topic}", "dollar_brace")]
)
def test_template_syntax_is_explicit(text, syntax):
    result = audit_prompts(
        [
            record(
                text=text,
                template_syntax=syntax,
                declared_variables=["topic"],
                supplied_variables=["topic"],
            )
        ]
    )
    assert result["records"][0]["variable_contract"]["status"] == "matched"


@pytest.mark.parametrize(
    "extra",
    [
        {"declared_variables": "topic"},
        {"declared_variables": ["topic", "topic"]},
        {"declared_variables": [""]},
        {"supplied_variables": {"topic": "QA"}},
        {"template_syntax": "guess"},
        {"recorded_response_prompt_hash": "unknown"},
    ],
)
def test_malformed_contract_fields_are_rejected(extra):
    with pytest.raises(PromptValidationError):
        audit_prompts([record(**extra)])


def test_response_hash_change_is_stale_without_claiming_changed_model_behavior():
    original = "Return one sentence."
    result = audit_prompts(
        [
            record("same", original, recorded_response_prompt_hash=prompt_hash(original)),
            record("changed", original + "\n", recorded_response_prompt_hash=prompt_hash(original)),
        ]
    )
    assert result["records"][0]["recorded_response"]["status"] == "matched"
    assert result["records"][1]["recorded_response"]["status"] == "stale"
    assert len(result["extension_checks"]["flags"]) == 1


def test_similar_embeddings_for_opposite_instructions_do_not_declare_equivalence():
    corpus = [record("allow", "Allow the request."), record("deny", "Do not allow the request.")]
    result = audit_prompts(corpus, embeddings={"deny": [1.0, 0.0], "allow": [1.0, 0.0]})
    similarity = result["similarity"]
    assert similarity["interpretation"] == "similarity_candidates_not_semantic_equivalence"
    assert similarity["candidate_pairs"][0]["ids"] == ["allow", "deny"]
    assert similarity["candidate_pairs"][0]["review_status"] == "review_required"
    assert "semantic_duplicate_count" not in similarity


@pytest.mark.parametrize(
    "embeddings",
    [
        [],
        [[0, 0], [1, 1]],
        [[1], [1, 2]],
        [[float("nan")], [1]],
        [[True], [1]],
        {"a": [1]},
        "model-name",
    ],
)
def test_misaligned_or_invalid_embeddings_fail_explicitly(embeddings):
    with pytest.raises(PromptValidationError):
        audit_prompts([record("a"), record("b")], embeddings=embeddings)


def test_ingests_controlled_fixture_without_claiming_paper_corpus():
    fixture = Path(__file__).resolve().parents[1] / "data" / "fixtures" / "prompts.json"
    corpus = load_prompt_records(fixture)
    result = audit_prompts(corpus, profile="extension")
    assert result["corpus_kind_counts"] == {"controlled_fixture": len(corpus)}
    assert result["record_count"] == 6


@pytest.mark.parametrize(
    "payload",
    [
        "",
        "[]",
        "{}",
        '{"records": []}',
        "[1]",
        "[invalid]",
        '[{"id":"a","id":"b"}]',
        '[{"id":"a","text":NaN}]',
    ],
)
def test_malformed_structured_files_are_rejected(tmp_path, payload):
    path = tmp_path / "prompts.json"
    path.write_text(payload, encoding="utf-8")
    with pytest.raises(PromptValidationError):
        load_prompt_records(path)


def test_jsonl_validation_reports_bad_line_and_preserves_good_text(tmp_path):
    path = tmp_path / "prompts.jsonl"
    path.write_text(json.dumps(record(text="  Preserved.\n")) + "\n\n{bad}\n", encoding="utf-8")
    with pytest.raises(PromptValidationError, match="JSONL line 3"):
        load_prompt_records(path)
    path.write_text(json.dumps(record(text="  Preserved.\n")) + "\n", encoding="utf-8")
    assert load_prompt_records(path)[0]["text"] == "  Preserved.\n"


def test_txt_requires_explicit_single_prompt_adapter(tmp_path):
    path = tmp_path / "prompt.txt"
    path.write_text("  Entire prompt.\n", encoding="utf-8", newline="\n")
    provenance = {"id": "text", "repository": "fixture/text", "commit": "fixture-v1"}
    with pytest.raises(PromptValidationError, match="explicit"):
        load_prompt_records(path, metadata=provenance)
    assert (
        load_prompt_records(path, metadata=provenance, adapter="single-prompt-v1")[0]["text"]
        == "  Entire prompt.\n"
    )


def test_txt_preserves_crlf_without_universal_newline_conversion(tmp_path):
    path = tmp_path / "prompt.txt"
    path.write_bytes(b"First.\r\nSecond.\r\n")
    records = load_prompt_records(
        path,
        metadata={"id": "crlf", "repository": "fixture/text", "commit": "v1"},
        adapter="single-prompt-v1",
    )
    assert records[0]["text"] == "First.\r\nSecond.\r\n"


def test_markdown_boundaries_are_declared_and_unclosed_block_is_rejected(tmp_path):
    path = tmp_path / "prompts.md"
    path.write_text(
        "# Commentary\n```prompt\nFirst.\n```\nIgnored.\n```prompt\nSecond.\n```\n",
        encoding="utf-8",
        newline="\n",
    )
    provenance = {"id": "md", "repository": "fixture/md", "commit": "fixture-v1"}
    with pytest.raises(PromptValidationError):
        load_prompt_records(path, metadata=provenance)
    records = load_prompt_records(path, metadata=provenance, adapter="fenced-prompt-v1")
    assert [(item["id"], item["text"]) for item in records] == [
        ("md:1", "First.\n"),
        ("md:2", "Second.\n"),
    ]
    path.write_text("```prompt\nNever closed.", encoding="utf-8")
    with pytest.raises(PromptValidationError, match="Unclosed"):
        load_prompt_records(path, metadata=provenance, adapter="fenced-prompt-v1")


def test_markdown_does_not_extract_prompt_examples_inside_other_code_fences(tmp_path):
    path = tmp_path / "prompts.md"
    path.write_text(
        "````markdown\n```prompt\nExample, not a prompt asset.\n```\n````\n"
        "```prompt\nActual prompt asset.\n```\n",
        encoding="utf-8",
        newline="\n",
    )
    records = load_prompt_records(
        path,
        adapter="fenced-prompt-v1",
        metadata={"id": "actual", "repository": "fixture/md", "commit": "v1"},
    )
    assert len(records) == 1
    assert records[0]["text"] == "Actual prompt asset.\n"


def test_audit_does_not_mutate_corpus():
    corpus = [record(declared_variables=["topic"], supplied_variables={"topic": "QA"})]
    before = deepcopy(corpus)
    audit_prompts(corpus)
    assert corpus == before

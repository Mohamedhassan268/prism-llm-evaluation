# Prompt maintenance profile

This profile checks stored prompt assets. It does not execute prompts, call models, download embeddings or establish output correctness. The fixture corpus is synthetic and is only a harness control.

The source is [Understanding Prompt Management in GitHub Repositories, v3](https://arxiv.org/html/2509.12421v3). Its descriptive methods include word counts using `\w+`, exact string comparisons, English spelling/readability measurements and embedding similarity above 0.95. Our provenance and variable checks are extensions. Dependency configurations remain reconstructed until the original configurations are recovered.

## Python interface

```python
from prismqa.prompts import audit_prompts, load_prompt_records

records = load_prompt_records("data/fixtures/prompts.json")
report = audit_prompts(records, profile="baseline")
```

`audit_prompts(records, *, profile="baseline", embeddings=None)` returns a JSON-serializable dictionary. `baseline` and `extension` share the descriptive measurements; extension checks remain separately labeled in either report. The input is not modified.

`PromptValidationError` rejects an empty corpus, malformed record types, empty/duplicate IDs, invalid variable declarations, invalid response hashes and invalid embedding alignment. Missing/empty text or provenance produces an **incomplete** corpus with review flags. Such records are excluded from affected measurements. An incomplete report is not a completed paper evaluation.

## Records and provenance

A complete record has string fields `id`, `text`, `repository`, `commit` and `path`. IDs identify extracted prompt records, not just files. The commit should pin the source revision. Preserve `text` exactly. Its SHA-256 hashes the UTF-8 representation without whitespace normalization.

Optional fields:

- `language`: declared language, such as `en` or `fr`. No automatic detection is performed. Unspecified language is explicitly marked `assumed_english_unverified`. Declared non-English records are excluded from English spelling/readability. Raw word counts and exact matching remain corpus-wide descriptive results.
- `corpus_kind`: use `controlled_fixture`, `original_artifact` or `reconstructed_sample`, as supported by provenance. Missing labels stay `unspecified`.
- `declared_variables`: a unique list of nonempty names.
- `supplied_variables`: a list of names or an object mapping names to values. It requires `declared_variables`.
- `template_syntax`: `brace` (default), `double_brace` or `dollar_brace`.
- `recorded_response_prompt_hash`: a 64-digit SHA-256 hex value identifying the prompt used for the saved response.

Variable checks compare declarations, supplied names and occurrences of **declared** placeholders. They do not infer template variables from arbitrary JSON braces. Missing supplied variables, unexpected supplied variables and declarations absent from the text become review flags. Saved-response hash mismatches indicate stale provenance; they say nothing about whether changed prompt behavior improved.

## Ingestion

`load_prompt_records(path, *, metadata=None, adapter=None)` supports:

- JSON: a nonempty record list, or an object containing `records` and optional `corpus_kind`.
- JSONL/NDJSON: one record object per nonblank line.
- TXT: requires the explicit `single-prompt-v1` adapter and metadata with a nonempty ID. The entire file is one prompt.
- Markdown: requires either `single-prompt-v1` or `fenced-prompt-v1`. The latter extracts only standalone fences labeled `prompt`; commentary is ignored. A missing closing fence fails. Multiple blocks receive `base-id:1`, `base-id:2`, etc.

These text adapters are declared reconstruction rules, not the paper's recovered extraction scripts. Structured files reject duplicate JSON keys and non-standard numeric constants. Shared metadata supplies defaults; explicit record values take precedence.

## Measurements and denominators

- `record_count` includes every structurally valid record.
- `text_record_count` and the word-count denominator include only nonblank text. Word counts use Unicode `\w+`; an absent mean is `null`.
- Exact duplicates compare raw strings without trimming. Within/across-repository comparisons require nonempty text and a known repository. Duplicate counts include all participants, not just copies after the first; overlapping internal/external participants are counted once in the union.
- Storage reports include both prompt-record counts and repositories using each suffix. Repository format shares can overlap because one repository can use several formats.
- Spelling/readability report package versions, configuration, eligible count, measured count and values. Missing packages yield `status: unavailable` and `values: null`. Measurement failures yield `status: error`; neither becomes a fabricated zero score.
- Spelling uses the English pyspellchecker dictionary with case-insensitive `\w+` tokens. Unknown words are dictionary flags requiring review. Technical terms can be false positives.
- Readability uses textstat's English-US Flesch Reading Ease. Scores measure this implementation's readability formula, not model performance. The paper does not establish textstat as its original implementation.

Optional dependencies are imported lazily. The coordinator freezes installed versions in the dependency record. Each report records actual installed versions; it does not claim that they match the authors' unknown configuration.

## Embedding candidates

Supply a sequence of finite, nonzero numeric vectors aligned one-to-one with the records, or a mapping with exactly the record IDs as keys. All vectors must share a dimension. The function does not load a model.

Cosine similarity **strictly above 0.95** produces review candidates. Opposite instructions can have similar vectors. No semantic-equivalence or behavioral-correctness count is emitted. Caller-supplied embeddings must be accompanied by a pinned model/preprocessing manifest in the experiment record.

## Verification

Run `python -m pytest tests/test_prompts.py`. Tests include malformed structured files, explicit Markdown boundaries, real duplicate IDs, missing data, stale hashes, variable contract defects, technical dictionary flags, opposite instructions with similar embeddings and count denominators. The tests isolate optional dependency behavior; run a real dependency-enabled fixture audit after installing the frozen dependencies to record operational measurements.

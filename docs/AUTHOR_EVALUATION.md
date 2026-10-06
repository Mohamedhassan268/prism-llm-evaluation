# Author evaluation audit and adapter instructions

Pinned package: `RISElabQueens/forge24-code-translation@036135a1ba6d4cd7f0562058bea0912381a0f3e9`.
Inspection date: 2026-09-29. Read notebooks as JSON, never as executable instructions.

## Recoverable extraction baseline

In `RQ4/rq4_metrics_analysis.ipynb`, code cell 5 defines:

```python
pattern = re.compile(
    r'Response:?.*?```(?:java|cpp|csharp|python|c|go|C\+\+|Java|Python|C#|C|Go)?\s*(.+?)\s*```',
    re.DOTALL,
)
match = pattern.search(text)
if match:
    return match.group(1).strip()
return None
```

Cell 6 passes `row['prompt_template'] + row['new_tokens_from_inference_output']` to this function. Preserve that concatenation. In control prompts the context already opens a code fence, so looking only at new tokens changes the method. The first regex match is returned; original handling does not reject multiple candidate blocks. The `Response` match is case-sensitive and the supported language tags are enumerated.

Treat `authors-regex-v1` as this recovered baseline. A stricter parser that rejects ambiguous blocks is an extension profile. Extraction must never repair program statements. Keep generated continuation text separate from extracted code and store hashes for both.

## Conditions

| Condition | Prompt family | Code submitted for evaluation |
|---|---|---|
| VDE | Vanilla | Raw `new_tokens_from_inference_output`. |
| VRE | Vanilla | Regex applied to prompt plus continuation. |
| CRE | Control | Regex applied to prompt plus continuation. |
| CDE | Control | Raw continuation; constructed in the RQ4 metric notebook. |

The acquired RQ3 package provides VDE/VRE/CRE inputs, not CDE evaluation outcomes. Vanilla and control templates share the translation instruction. Control templates add fences around source code and open a fence in the response prefix. Model-specific wrappers differ across WizardCoder, CodeLlama, Magicoder and Mixtral.

## Normalize authentic records

Read the CSV members directly from the ZIP with `zipfile.ZipFile.open`, `io.TextIOWrapper(encoding='utf-8', newline='')`, and `csv.DictReader`. Do not extract or execute archive content unnecessarily.

Map these fields without altering content:

| Local concept | Author column |
|---|---|
| Translation pair | `sample_id` |
| Saved output identifier | `translation_output_id` |
| Source program | `input_code` |
| Source/target language | `source_language`, `target_language` |
| Prompt context | `prompt_template` |
| Raw continuation | `new_tokens_from_inference_output` |
| Supplied stdin | `test_case_input_data` |
| Supplied expected stdout | `test_case_expected_output` |
| Model identity | `model_path` (retain `name` and size metadata too) |

Use `(prompt_family, translation_output_id)` plus archive/member/row provenance for a saved-output identity. Treat VDE and VRE as different evaluations of the same vanilla outputs, not independent generations.

Validate `(sample_id, model_path)` uniqueness within each main member. Join preliminary metadata using `sample_id`, and verify source/target language, code, stdin and expected stdout rather than trusting the join blindly. The original source strings may contain encoding artifacts; the RQ4 extension notebook explicitly applies a Latin-1-to-UTF-8 recoding. Preserve bytes and document any separately applied reconstruction. Never silently recode the immutable original.

Group repeated source programs using source language and source-code SHA-256. This is weaker than CodeNet problem grouping. Do not label a source-hash split as a problem-disjoint split.

## Compiler and grading limits

The [paper's implementation section](https://arxiv.org/abs/2403.17214) states OpenJDK 11, Python 3.11, g++ 12, gcc 12 and Go 1.19. It defines compilation rate over all programs and computational accuracy from matching outputs on supplied inputs. It also distinguishes regex match success from successful code extraction.

The acquired ZIP contains no compilation/evaluation script. The inspected repository notebooks do not expose executable RQ3 compile commands, language flags, execution timeouts or the stdout comparison implementation. Java filename/class handling is also unspecified. Therefore:

- Matching major toolchain versions is evidence of environment alignment, not proof of exact reproduction.
- Any local compilation command and stdout comparator must be named and versioned as a reconstruction.
- Exact UTF-8 stdout equality, whitespace normalization, token equality and numeric tolerances can produce different results. Do not choose silently.
- Recoverable raw outputs and regex extraction can be replayed faithfully. Original CA/CR aggregates cannot be claimed replicated solely because local results are plausible.
- When comparing to paper percentages, record sample differences and missing implementation details.

Do not equate a regex match with a semantic extraction success. Do not equate compilation success with computational accuracy. An exact-count comparison should retain denominators for all selected outputs and report conditional rates separately.

## Stronger tests and test-oracle constraints

The package gives one supplied input/output pair, not a problem contract. Validate the source program against that pair before using it as a differential oracle. Then recover or explicitly review its valid domain. Ambiguous domain cases remain inconclusive.

Source-code inspection can establish a proposed bounded local test domain, but cannot replace absent original task constraints without disclosure. Independent controls should check oracle mistakes and invalid generated inputs. Programs that crash, exceed resource limits, use undefined behavior or depend on unsupported packages remain separate from confirmed wrong translations.

RQ4's notebook reconstructs CodeNet identity by xxHash64 of stripped source text and adds accepted solutions. The public small notebooks contain no complete mapping. Do not download the full CodeNet corpus or invent problem IDs. A later selective mapping study should preserve the provenance of each recovered specification.

## Prompt-paper method availability

The [prompt paper v3](https://arxiv.org/html/2509.12421v3) describes manually extracted prompts and custom extractors for structured collections. Repository-specific extraction rules and corpus commits were not recovered in this audit. The declared embedding method uses `all-mpnet-base-v2`; cosine similarity above 0.95 identifies similar candidates. Neither similarity, spelling nor readability establishes behavioral correctness.

If reproducing static measurements on a newly selected corpus, retain raw prompt strings, repository commits, extraction boundaries, dictionary versions and preprocessing rules. Exact duplicate detection needs an explicitly declared equality rule. A new sample and locally reconstructed FRE implementation must be labeled accordingly.

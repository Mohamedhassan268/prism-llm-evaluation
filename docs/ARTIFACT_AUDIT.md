# Authors' artifact audit

Audit date: 2026-09-29. This is a static inspection. No author notebook, model, or generated program was executed on the host.

## Track A: acquired originals

Repository: [RISElabQueens/forge24-code-translation](https://github.com/RISElabQueens/forge24-code-translation).
Pinned Git commit: `036135a1ba6d4cd7f0562058bea0912381a0f3e9` (commit date 2024-10-29).
The repository README distinguishes the original FORGE package from files added for the extended EMSE study. An artifact dated 2024 does not imply reproduction of every change in the later manuscript.

The complete Git tree has 33 files. Selective acquisition obtained 16 originals, totaling 58,812,279 bytes:

- Repository `LICENSE` and `README.md`.
- The processed preliminary dataset and preprocessing notebook.
- All nine plain-text prompt templates.
- `RQ3/rq3_files.zip` (55,350,192 bytes).
- The two small RQ4 extension/metric notebooks.

Originals reside under `data/cache/authors/036135a1ba6d4cd7f0562058bea0912381a0f3e9/`. They are marked read-only. `data/manifests/authors_artifacts.json` records each source URL, size, SHA-256, Git blob SHA-1, commit and license context. Read-only flags prevent accidental edits; hashes remain the integrity authority.

The ZIP expands to 316,752,657 bytes. It remains compressed. Its seven members are inspected through streaming readers. Directory entries were checked for absolute paths, traversal, Windows drive syntax, backslashes, symbolic links, duplicate names, encryption, excessive expansion and suspicious compression ratios. CSV reading also exercises ZIP CRC checks for members consumed to completion.

The downloader verifies each acquired byte stream against the blob in the pinned Git tree. It refuses to replace an existing original. It preserves at least 5 GiB free on the workspace volume and caps cache storage at 2 GiB. An interrupted acquisition leaves a `.part` file for explicit inspection; it never treats that partial file as a complete original.

Acquisition or integrity recheck:

```powershell
python scripts/acquire_authors_artifact.py --dry-run
python scripts/acquire_authors_artifact.py
```

The MIT repository license is attributed to RISElabQueens (2024). This covers the repository's stated license. It is not independent proof that every underlying CodeNet submission or third-party component can be redistributed under MIT. Retain upstream attribution and audit provenance before publishing raw benchmark code.

## Processed dataset

`Preliminary/dataset_after_processing.csv` has 3,820 records, exactly 191 for each of the 20 ordered source/target language directions among C, C++, Go, Java and Python.

Fields:

```text
sample_id,input_code,input_lang,desired_output_lang,
test_case_input_data,test_case_expected_output
```

There are 3,820 unique `sample_id` values but only 977 exact unique source-code strings. `sample_id` identifies a translation pair, not a shared original program or problem. The file contains one supplied input/output case for each pair. It contains no target reference code, problem IDs, specification URLs, constraints or accepted input domains.

Use source-language plus source-code hash to group exact repeated programs. That prevents identical-source leakage between calibration and evaluation, but it does not identify different submissions solving the same problem. True problem-level grouping remains unresolved without a CodeNet mapping.

## RQ3 ZIP and authentic inference records

The archive contains:

| Member | Expanded bytes | Role |
|---|---:|---|
| `inference_output_11_models_vre.csv` | 105,406,056 | Vanilla prompt outputs for regex extraction. |
| `inference_output_11_models_cre.csv` | 104,377,310 | Control prompt outputs for regex extraction. |
| `inference_output_11_models_vde.csv` | 105,406,056 | Vanilla outputs for direct evaluation. |
| `rand_sample_350_WizzardCoder-34B_vde.csv` | 414,491 | Manual compilation-failure sample. |
| `rand_sample_350_Magicoder-S-CL-7B_vde.csv` | 393,349 | Manual compilation-failure sample. |
| `rand_sample_350_Mixtral_cre.csv` | 331,347 | Manual compilation-failure sample. |
| `rand_sample_350_Magicoder-CL-7B_vde.csv` | 424,048 | Manual compilation-failure sample. |

Inference-table schema:

```text
sample_id,translation_output_id,input_code,prompt_template,
new_tokens_from_inference_output,test_case_input_data,
test_case_expected_output,target_language,source_language,
model_path,name,size_in_billions
```

`new_tokens_from_inference_output` stores generated continuation text, including wrappers or explanations where produced. `prompt_template` is the instantiated context used by the author extraction procedure. Neither a fully extracted program nor original pass/fail outcomes appear in these main tables. The VRE and VDE member sizes and CRCs are identical; the schema audit additionally records their content hashes.

The four random-sample tables have repeated `id` column names. Do not load them with a plain `DictReader` and assume all identifier columns survived. Their `code_text` and `execution_output` are inspection evidence, not a complete grading history. They do not contain the original input/output comparator implementation.

`data/cache/authors/rq3_schema_audit.json` records row counts, hashes, model counts and joins against the preliminary file. Adapter implementations must retain immutable source bytes and source-row provenance.

## RQ4: directory audit only

The multipart archive requires `rq4.z01` through `rq4.z04` plus `rq4.zip`: 226,544,284 compressed bytes in total. A 65,536-byte range from the last segment was inspected, rather than acquiring or expanding the archive.

The directory reports 1,054,146,569 expanded bytes. It includes three large extended JSONL files (approximately 351 MB each) and the `xlcostcb` metric implementation. There is no separate small source-hash/problem-ID map.

The extension notebook explains how the authors computed xxHash64 on stripped source code, scanned a local full Project_CodeNet tree, used the first matching submission path to obtain `pNNNNN`, and added accepted target-language solutions. Its local `file_hashes_strip.pkl` is not in the public Git tree. The stored notebook output shows only head/tail problem IDs without source hashes or sample IDs. Those rows cannot establish a reliable mapping for the RQ3 sample.

Range-response provenance and directory sizes are recorded in `data/cache/authors/rq4_directory_inspection.json`; the fragment has its own SHA-256. A fragment hash is not verification of the full archive's Git blob. No CodeNet corpus or multipart RQ4 archive was downloaded.

## Track B: original corpus not located in this audit

Primary sources inspected:

- [Prompt paper v3](https://arxiv.org/html/2509.12421v3).
- [Hao Li's publications](https://leo-lihao.github.io/publications/) and linked GitHub account `Leo-LiHao`.
- [Filipe Cogo's publications](https://www.filipecogo.pro/publications).
- [PRISM publications](https://prism.cs.queensu.ca/publications.html).
- Public repository listings for `Leo-LiHao`, `SAILResearch`, and `RISElabQueens`.

Searches on 2026-09-29 included `"Understanding Prompt Management" replication dataset GitHub` and `"Understanding Prompt Management in GitHub Repositories" artifact`.

No linked full 24,800-prompt corpus, 92-repository/commit manifest, extraction scripts or versioned analysis configuration was located in these inspected sources. This is a bounded search result, not proof that no package exists. An author-site title link also resolved to an unrelated Jupyter-notebook review page; it is not a trustworthy corpus link.

Accordingly, Track B remains `artifact-unavailable-in-audit`. A contemporary selected corpus must be labeled a reconstruction/new sample. It must not be described as the original 92-repository experiment. No author was contacted.

## Reproduction labels and gaps

| Item | Current status | Limitation |
|---|---|---|
| Original saved RQ3 continuations | Acquired and integrity-verified | No new inference performed. |
| Prompt templates | Acquired and statically reviewed | Instantiated context in each row is the extraction input. |
| Authors' regex method | Recoverable from RQ4 notebook | Notebook provenance must accompany adapter implementation. |
| Compiler/runtime versions | Documented in paper | Exact invocations/flags are absent from inspected artifacts. |
| Original stdout comparator | Unavailable in inspected artifacts | A local comparator is a documented reconstruction. |
| Original program/problem grouping | Exact source grouping possible | Different submissions to one problem can remain in separate groups. |
| Stronger valid test inputs | Requires oracle/domain review | CSV alone does not justify arbitrary generated inputs. |
| Prompt corpus and extraction rules | Not located | New sample must be labeled as such. |

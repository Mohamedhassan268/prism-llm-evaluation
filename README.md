# PRISM: LLM Evaluation Harness

A Python research prototype that separates extraction, compilation, output-format compliance and functional correctness in LLM-generated code. It reconstructs evaluation from saved outputs; it is not the upstream authors' original grader.

## Features

- Provenance-aware sampling, direct/regex extraction and ambiguity checks.
- Bounded container execution for C, C++, Go, Java and Python.
- Supplied-test and additional-case grading with distinct failure outcomes.
- Frozen identities, resumable records and report-integrity checks.
- Matched-prompt tasks, local llama.cpp collection and semantic/JSON-contract scoring.

## Research status

Checked 6 October 2026. Counts are recorded in the [aggregate summary](reports/PUBLIC_SUMMARY.json).

| Work | Evidence | Limit |
| --- | --- | --- |
| Code calibration | 330 saved-output rows across 11 models; 71 supplied-test passes, 69 passing additional cases | Two false passes concern one problem; held-out grading is pending. |
| Source controls | Ten controls passed 601 additional cases | Covers the reviewed cases only. |
| Prompt pilot | 12 synthetic tasks, 48 requests, 40 Qwen responses collected | Eight requests remain; no completed effect estimate. |

## Install and test

Python 3.11 or newer. Create and activate a virtual environment, then run:

```bash
python -m pip install -e ".[qa]"
python -m pytest -q
python -m ruff check src tests scripts containers
```

**83 tests passed** and Ruff passed locally. CI checks Python 3.11/3.12. Tests use synthetic fixtures and mocked execution, without model downloads or a benchmark campaign. `requirements.lock.txt` records the original Windows environment.

## Prompt pilot

```bash
python -m prismqa.prompt_impact prepare \
  --manifest data/manifests/prompt-impact-pilot-v1.json \
  --output reports/prompt-requests.json
python -m prismqa.prompt_impact audit \
  --manifest data/manifests/prompt-impact-pilot-v1.json \
  --output reports/prompt-pair-audit.json
```

Collection requires a separately installed model/runtime; see `scripts/run_prompt_impact_local.py --help`. Gap-condition answers require human review.

## Reproduction and attribution

See the [protocol](docs/PROTOCOL.md), [artifact audit](docs/ARTIFACT_AUDIT.md), [calibration design](docs/CALIBRATION_DESIGN.md), [design](DESIGN.md) and [release checks](docs/RELEASE_VERIFICATION.md).

Saved translation artifacts originate from [RISElabQueens/forge24-code-translation](https://github.com/RISElabQueens/forge24-code-translation), commit `036135a1ba6d4cd7f0562058bea0912381a0f3e9`. Acquire them separately with `scripts/acquire_authors_artifact.py`. Exact replay requires the ignored artifact bundle and pinned toolchain image; a new image must use a separately reviewed profile.

Run generated benchmark programs through the bounded container executor. Full campaigns require Docker/WSL. Model files, caches, raw responses, benchmark code and full local reports are excluded from this software snapshot. Upstream attribution and licenses remain applicable.

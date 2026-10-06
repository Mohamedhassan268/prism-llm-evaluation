# PRISM: LLM Evaluation Harness

A Python research prototype for evaluating LLM-generated code and controlled prompt variants. It separates code extraction, compilation, output-format compliance and functional correctness so a formatting failure is not confused with an algorithmic fault.

This is an independent evaluation implementation, not the upstream authors' original grader or a complete reproduction of their published results.

## What is implemented

- Provenance-aware ingestion and sampling of saved code-translation outputs.
- Direct and regex code extraction with explicit handling of ambiguous outputs.
- Bounded container execution for C, C++, Go, Java and Python.
- Supplied-test and additional-case grading with distinct wrong-output, compilation, crash, timeout and inconclusive outcomes.
- Frozen artifact identities, resumable records and report-integrity checks.
- A synthetic matched-prompt pilot, local llama.cpp inference collector and semantic/JSON-contract scorer.

## Recorded research status

Checked 6 October 2026 against the local research artifacts. The [aggregate summary](reports/PUBLIC_SUMMARY.json) contains the counts below; raw responses, benchmark code and complete research reports are not distributed in this software release.

| Work | Recorded evidence | Limit |
| --- | --- | --- |
| Code-output calibration | 330 saved-output evaluation rows across 11 models; 71 supplied-test passes, of which 69 passed all additional cases and two failed | Both newly exposed false passes concern one problem. These are saved upstream outputs, not new generations. |
| Source controls | Ten source controls passed all 601 additional cases | Bounded case coverage does not establish correctness on every valid input. |
| Prompt-impact pilot | 12 synthetic tasks, 48 planned requests, 40 recorded Qwen responses | Eight requests remain uncollected. No completed prompt-effect estimate is claimed. |

Held-out translated-output grading remains pending. The prompt pilot is exploratory and incomplete. No training, fine-tuning, production deployment or general model ranking is claimed.

## Install and test

Python 3.11 or newer:

```bash
python -m venv .venv
# Windows: .venv\Scripts\activate
# Linux/macOS: source .venv/bin/activate
python -m pip install -e ".[qa]"
python -m pytest -q
python -m ruff check src tests scripts containers
```

`requirements.lock.txt` preserves the original Windows research environment. The smaller `qa` extra is sufficient for the software tests. Tests use synthetic fixtures and mocked execution paths; they do not download LLM weights or run the benchmark campaign.

The exported source passed **83 software tests** and Ruff locally; see [release verification and static-analysis limits](docs/RELEASE_VERIFICATION.md).

## Prompt pilot without a model

```bash
python -m prismqa.prompt_impact prepare \
  --manifest data/manifests/prompt-impact-pilot-v1.json \
  --output reports/prompt-requests.json
python -m prismqa.prompt_impact audit \
  --manifest data/manifests/prompt-impact-pilot-v1.json \
  --output reports/prompt-pair-audit.json
```

The manifest contains synthetic tasks and scoring references. Preparation writes only the request fields needed for collection; the gap condition requires human review rather than comparison against a hidden reference answer. Model collection is optional and requires a separately installed runtime/model. See `scripts/run_prompt_impact_local.py --help`.

## Benchmark and execution setup

See [artifact provenance](docs/ARTIFACT_AUDIT.md), [calibration design](docs/CALIBRATION_DESIGN.md), [evaluation protocol](docs/PROTOCOL.md) and [implementation design](DESIGN.md).

The authors' artifacts are acquired separately with `scripts/acquire_authors_artifact.py`; caches and raw source/translation code are excluded from this repository. Exact benchmark replay also requires the original ignored artifact bundle and toolchain image. `data/manifests/toolchains.lock.json` records the research image identity: a newly built image needs an explicitly updated local profile and must not silently be substituted into an existing run.

Generated programs must run through the bounded container executor, not on the host. Container checks and full campaigns require Docker/WSL and are separate from the software tests. Consult the protocol before execution.

## Attribution and release contents

The saved translation artifacts originate from [RISElabQueens/forge24-code-translation](https://github.com/RISElabQueens/forge24-code-translation), pinned at `036135a1ba6d4cd7f0562058bea0912381a0f3e9`. The evaluation conditions and reconstruction limits are documented in the artifact audit. Upstream repository licensing does not independently establish redistribution rights for every underlying submission; no raw benchmark code is included here.

This repository is a software snapshot of Mohamed Hassan's research workspace. Model weights, credentials, personal application materials, downloaded third-party source snapshots, raw responses and full local report archives are excluded. Included calibration cases and microtasks support documented bounded checks. No license grant for original project code is added by this release; upstream components retain their own licenses.

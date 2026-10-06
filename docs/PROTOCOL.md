# PRISM pilot review protocol v1

Protocol date: 2026-09-29 (Africa/Cairo). Status: implemented protocol, awaiting user review.
Search cutoff: source versions publicly available by 2026-09-29. Later retrieval is logged.
Scope: the two PRISM papers and methods directly relevant to their evaluation weaknesses.
General QA platform development is outside this milestone.

## Questions

1. Which translation failures arise from formatting/extraction rather than behavior?
2. Which original-test passes fail additional valid tests?
3. Which oracles, input domains and comparators are defensible?
4. Which prompt-maintenance measurements can be reproduced reliably?
5. Which supporting techniques improve fault detection or reduce false alarms locally?

## Search and screening

Search arXiv, publisher metadata/search pages, author/institutional archives, GitHub and
practitioner sources. Log exact queries, date, source location, results actually screened,
eligible records, exclusions, inaccessible material and index/result limits. Search families:

- (code translation OR LLM-generated code) AND (output format OR code extraction OR functional correctness)
- (prompt management OR promptware) AND (versioning OR duplication OR testing OR maintenance)
- (property-based testing OR metamorphic testing OR differential testing OR mutation testing) AND (test oracle OR generated code)

Include relevant empirical methods, artifacts, foundational oracle work and documented
workflows. Exclude unrelated UI/cloud/ML training work, advertisements without usable methods,
duplicate versions (retain version linkage), and unsupported claims from the evidence synthesis.
Preserve excluded candidates and reasons. Keep practitioner claims distinct from empirical
research. Access failure is not evidence of irrelevance. Do not use popularity as efficacy.

Appraise problem definition, dataset/procedure, artifacts, oracle reliability, limitations and
applicability. Follow references and citing sources. Two fully logged zero-yield rounds are
the stopping criterion; until then the review is explicitly ongoing. AI assistance is disclosed;
agents do not count as independent human reviewers. Human review checkpoints remain open.

## Frozen pilot design

Seed 20260929. Ten calibration pairs, 100 evaluation pairs, target 20 per target language.
Keep source program/problem groups disjoint between splits, balance available source directions,
and list undersized strata. Eligibility is decided before extended results. Save exact IDs.
Do not infer valid input domains from a single example. Additional tests require an approved,
versioned domain/oracle profile and independently checked representative expected outputs.
Freeze test inputs before held-out grading. Compile/extraction/behavior failures stay separate.
Preserve authors' originals and grade comparators; reconstructed comparators are labeled.

Prompt pilot: up to 10 repositories/500 prompts, category-aware selection and pinned commits.
Prefer original corpus; otherwise label a contemporary reconstruction. Static metrics do not
measure live LLM behavior. Embedding similarity is a candidate relation, not semantic identity.

## Runtime and storage

D: artifacts/cache cap 2 GiB and minimum 5 GiB free. WSL image/model cache cap 6 GiB.
Two active benchmark jobs maximum; each 1 CPU/1 GiB/64 processes. Compile 30s, test 5s,
additional evaluation 120s/program. Network disabled; non-root; only job workspace mounted;
container filesystem read-only, bounded tmpfs. Resource failures are inconclusive outcomes.
No paid API calls, fresh large-model generation, publishing or outreach changes.

## Review gates

1. Protocol + artifact coverage.
2. Frozen sample + independently checked oracle/test profiles.
3. Track A findings and limitations.
4. Track B findings and project QA skill.

Implementation, source review and controlled acceptance runs can proceed. Authentic held-out
grading remains gated on reviews 1/2 and validated problem domains. Missing prerequisites
must appear in status/reports; synthetic fixtures cannot be presented as paper findings.

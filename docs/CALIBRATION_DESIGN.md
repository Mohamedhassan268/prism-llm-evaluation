# Calibration design and domain record

The user said “next is what start it” on 29 September 2026. This authorizes moving from the
first review package into calibration and final-domain preparation. Protocol/sample review
is recorded as approved. Final held-out test-design approval remains pending.

## Frozen inputs and model order

The original sample is unchanged. Ten calibration translation pairs have 330 saved output
rows across 11 models and three conditions. All models run in lexical identifier order, in
resumable 30-row batches. This ordering is a scheduling choice, not a performance ranking.
Baseline grading uses original tests only, author extraction for CRE/VRE, and raw text for VDE.
Compilation and strict stdout comparison are reconstructed; published CA/CR is not reproduced.

[The additional profile](../data/manifests/calibration-domains-v1.json) was generated and frozen
before extended target grading. It contains 601 unique additional cases, each checked against
an official problem's constraints. Source validation must pass before the extended model runs.
`scripts/run_calibration_batches.py --stage extended` enforces that prerequisite.

## Task attribution and independent expected values

Task attribution was reconstructed by matching official examples and reading source algorithms.
The author artifacts did not provide these IDs. Cached HTML and checksums, official URLs,
constraints, mapping basis and review status appear in
[the mapping manifest](../data/manifests/calibration-task-mapping.json).
This is AI-assisted coordinator review, not independent human review.

| Pair | Official task | Extra cases | Oracle and coverage |
|---|---|---:|---|
| 58801 | [Flipping Signs](https://atcoder.jp/contests/abc125/tasks/abc125_d) | 40 | Exhaustively traverse adjacent-sign-flip states, N<=8; zeros and +/-1e9. |
| 58902 | [Digits](https://atcoder.jp/contests/abc156/tasks/abc156_b) | 97 | Integer division; exact-power neighbors and bases 2..10. |
| 59448 | [Circle](https://atcoder.jp/contests/abc145/tasks/abc145_a) | 99 | Area ratio r squared; all other valid radii. |
| 60194 | [Summer Vacation](https://atcoder.jp/contests/abc137/tasks/abc137_d) | 40 | Exhaustive schedules including idle days; N<=8, M<=6. |
| 60265 | [1%](https://atcoder.jp/contests/abc165/tasks/abc165_b) | 39 | Exact rational compounding and floor; X up to 1e18. |
| 60797 | [Many Requirements](https://atcoder.jp/contests/abc165/tasks/abc165_c) | 40 | Cartesian enumeration then monotonic filtering; N,M<=5; distinct rule triples. |
| 61358 | [Watch](https://judge.u-aizu.ac.jp/onlinejudge/description.jsp?id=ITP1_1_D&lang=en) | 40 | Time-unit division/remainders; 0, minute/hour transitions and 86400. |
| 61692 | [Therefore](https://atcoder.jp/contests/abc168/tasks/abc168_a) | 77 | Official digit/pronunciation table; positive values <=999. |
| 62222 | [September 9](https://atcoder.jp/contests/abc073/tasks/abc073_a) | 89 | Tens/units comparison; all other valid two-digit integers. |
| 62549 | [gacha](https://atcoder.jp/contests/abc164/tasks/abc164_c) | 40 | Linear distinct-string collection; lowercase strings of length 1..10, N<=40. |

These are bounded subsets of the original domains. The small optimization oracles enumerate
possibilities using methods different from the source algorithms. Larger original N/M limits
are not covered. Full-domain performance and asymptotic scalability are not established.
Original official samples are checked against the new oracles. Public known answers include
the maximum bank goal's 3760 years. Target programs never generate expected values.

## Split audit finding

Three selected evaluation pairs implement calibration problems in different languages:
60109 matches 62222 (September 9), 60232 matches 61358 (Watch), and 61669 matches 59448 (Circle).
Their original examples and reviewed algorithms agree. Distinct code hashes hid this overlap.
No held-out translation outcomes were inspected during the audit.

[The overlap audit](../data/manifests/calibration-overlap-audit.json) preserves v1 and proposes
excluding these three before held-out grading, leaving 97: C++ 19, Java 20, Go 20, C 19,
Python 19. Other task overlap is not ruled out; full held-out task mapping remains unfinished.
These are proposed eligibility exclusions, not silently changed scientific results.

## Validation lessons

Hypothesis produced an unpaired Unicode surrogate in an older extraction property generator.
That character is outside the UTF-8 artifact domain and fails hashing. The generator now
excludes surrogate code points. This was a test-input issue, not a translated-program fault.
The supported extraction property remains byte/text preserving for valid UTF-8 strings.

Resource failures and incomplete oracles remain separate from functional wrong-output results.
Extended calibration reuses the completed source-control run, rather than executing identical
sources for every model. The cache verifies the original run and binds source code, language,
ordered input/expected hashes and toolchain identity. Only reference calls use it; targets
still execute. Cache provenance is stored with each oracle check and in the run identity.
Historical source timings are retained as evidence, not charged as fresh execution cost.
Calibration findings are exploratory; they do not constitute the held-out pilot or justify
general claims about the models, languages or candidate skills.

Strict additional mismatches receive separately labeled post-hoc diagnostics. Integer/keyword
or time-value differences can establish a value fault under these contracts. Whitespace,
padding, case or equivalent numeric representations are classified as formatting differences;
extra/unparseable stdout is a contract violation requiring interpretation. These diagnostics
do not alter the frozen exact-output grades or imply acceptance by the original contest judge.

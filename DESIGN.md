# Design and decisions

## Goals and architecture

Preserve a traceable chain from source and immutable artifact to sample, profile, execution,
outcome and report. Keep extraction, compilation, original tests and additional tests separate.
The Python CLI coordinates trusted modules; Docker alone executes generated benchmark code.
Static prompt audits never execute prompt contents or make model calls.

## Key decisions and alternatives

Hashes bind datasets, profiles and environments to runs. Atomic records allow interrupted
runs to resume. Report generation checks completeness and recomputes counts rather than
trusting a summary. Exact stdout and strip comparators are separate reconstructed profiles.
The recovered author regex intentionally chooses the first match; the new conservative profile
rejects ambiguity. Algorithm repair would change the tested artifact and is excluded.

Reference programs are execution comparators after domain and expected-value checks. They
are not automatically correct oracles. Extra-test claims exclude incomplete references and
oracle disagreements. A crash, timeout or environment failure is distinct from wrong output.
Cluster bootstrap intervals require at least two eligible source groups; fixture rates are
only harness demonstrations. Original problem identities are unavailable in the acquired CSV.

## Security and resource boundaries

The executor runs as UID 1000, with no networking, a read-only root, dropped capabilities,
no new privileges, 1 CPU, 1 GiB memory, 64 processes and bounded writable tmpfs mounts.
Only one read-only job folder is bound from the host. Expected answers are not mounted.
Compilation is capped at 30 seconds, each execution at 5 seconds, and each program batch
at 120 seconds. File output is limited to 32 MiB; JSON diagnostics are truncated while the
full stdout hash supports exact comparisons. Surviving process groups are killed after a case.
No more than two benchmark jobs should run concurrently; current CLI executes sequentially.
This is an isolation boundary for this local study, not a proof against all container escapes.

Python subprocess arguments are lists, with no shell evaluation. Runner executable prefixes
and image identities are validated. Job paths cannot escape the project. Retrieved scripts
and prompts remain data; external skill instructions are audited rather than blindly installed.

## Known limitations and tradeoffs

Original graders, source constraints and complete Track B artifacts were not recovered.
The current prompt sample is contemporary and covers a collection only. Embedding analysis
is optional and has not run. Generic scanner thresholds are suggestions rather than research
oracles. Changing the Docker image invalidates resumption; do not rebuild during a run.
Dependency locks capture the tested environment, but base apt package resolution is not a
historical snapshot. Container image IDs preserve the actual resulting toolchain locally.

## Change history

2026-09-29: initial protocol, artifact audit, bounded toolchains, harness, synthetic controls,
identity-checked resumption/reporting, prompt maintenance implementation and local skill draft.

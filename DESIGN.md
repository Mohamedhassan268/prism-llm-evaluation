# Design

## Evaluation pipeline

Source artifact -> sample -> frozen profile -> extraction -> execution -> outcomes -> report.

The CLI coordinates trusted Python modules. Docker executes generated benchmark code. Extraction, compilation, supplied tests and additional cases are graded separately; static prompt audits make no model calls.

Hashes bind artifacts, profiles and environments to each run. Atomic records support resumption. Reports verify completeness and recompute counts. Recovered author regex selects the first match; the conservative profile rejects ambiguity. Neither repairs the tested algorithm.

Reference programs require reviewed domains and expected values. Incomplete references and oracle disagreements cannot support extra-test claims. Crashes, timeouts and environment failures remain separate from wrong outputs. Bootstrap intervals need at least two eligible source groups.

## Execution boundary

The container uses UID 1000, disabled networking, a read-only root/source mount, dropped capabilities and no new privileges. Limits: 1 CPU, 1 GiB RAM, 64 processes, bounded tmpfs and 32 MiB file output. Expected answers are not mounted.

Compilation allows 30 seconds, each case 5 seconds and a program batch 120 seconds. Surviving process groups are killed between cases. Diagnostics are truncated; full stdout hashes support comparisons. The CLI runs benchmark jobs sequentially.

Subprocess commands use argument lists. Executable prefixes, image identities and job paths are validated. Rebuilding the image changes its identity and invalidates an existing run's resumption.

## Limits

Original graders, complete source constraints and the authors' Track B corpus were not recovered. Source hashes cannot establish problem-disjointness across different implementations. The current prompt sample covers one contemporary collection; embedding analysis has not run.

Dependency locks describe the tested environment, but apt resolution is not a historical snapshot. Container boundaries are practical controls, not a formal isolation guarantee.

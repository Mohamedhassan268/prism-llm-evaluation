# Release verification

Checked 6 October 2026 on Windows using the research QA environment.

- 83 software tests passed; Ruff passed.
- No credential patterns found in release files.
- No new model calls or container campaign ran during these checks.

## Static-analysis review

Bandit and the pattern scanner raised warnings; review found no confirmed critical/high issue under the documented local-script use.

| Warning | Reviewed context |
| --- | --- |
| URL opening | HTTPS upstream sources or the collector's loopback server; no remote request handler accepting arbitrary URLs. |
| Subprocesses | Argument lists; benchmark execution uses the bounded container runner. |
| `/tmp` | Bounded container tmpfs, not a host credential file. |
| Seeded randomness | Reproducible sampling, not authentication. |
| SHA-1 | Git blob identity only; SHA-256 also records artifact provenance. |
| Token constants | Evaluation statuses, not credentials. |

These checks do not establish model quality or unrestricted container safety. Raw responses, models, caches, downloaded benchmark code and full research reports are excluded. Local research history is preserved.

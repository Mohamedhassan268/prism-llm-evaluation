# Software release verification

Checked 6 October 2026 on Windows, using the existing research QA environment and the exported source tree.

- Full software suite: **83 tests passed**.
- Ruff: all checks passed.
- Credential-pattern scan: no private-key, GitHub-token or provider-key patterns found in the release files.
- Unit tests do not execute benchmark programs, collect new model responses or establish model accuracy. No container campaign or fresh inference run was performed for this release.

GitHub Actions runs the software tests and Ruff on Python 3.11 and 3.12. Remote CI outcomes are separate from these local checks.

## Reviewed static-analysis findings

Bandit and the shared pattern scanner emit findings for the intended execution/networking code. These findings are retained in the local release audit; the scanners do not give an unqualified clean result.

- URL-opening warnings: artifact acquisition uses HTTPS upstream sources; prompt-sample and task-domain scripts construct fixed upstream URLs. The local inference collector calls the loopback server port that it starts. These are local research scripts, not a network service accepting arbitrary remote URL requests. Redirect/host restrictions beyond the implemented source checks are not claimed.
- Subprocess warnings: commands use argument lists. Generated benchmark code is executed through the bounded container runner, with read-only mounts, disabled networking, non-root user, capability/resource limits and separate failure outcomes. A container is a practical boundary, not a formal isolation guarantee.
- `/tmp` warning: the path is an explicit bounded container tmpfs, not a predictable host file used to hold credentials.
- Seeded randomness: it controls repeatable dataset/task sampling; it is not used for authentication or cryptographic secrets.
- SHA-1 warning: Git blob identity is cross-checked with `usedforsecurity=False`; artifact provenance also records SHA-256. SHA-1 is not presented as the security authority.
- Token-string warnings: evaluation identity/status constants are not authentication credentials.

The shared scanner's URL-open/path-traversal flags are pattern matches on `urlopen`, rather than demonstrated filesystem traversal. Review found no confirmed critical/high vulnerability in those flagged call sites under the documented local-script use. This is a scoped release review, not a penetration test or unrestricted execution guarantee.

## Publication scope

The public snapshot includes software, synthetic fixtures, protocol/domain manifests and an aggregate research summary. Raw collected responses, downloaded benchmark code, model files, source caches and complete local report archives are excluded. The original local research repository and its Git history are preserved.

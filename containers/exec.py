"""Trusted in-container batch executor with bounded tmpfs and output files."""

import hashlib
import json
import os
import signal
import subprocess
import time
from pathlib import Path


def execute(command, input_text, timeout):
    start = time.monotonic()
    status, code = "ok", None
    with open("/work/stdin.bin", "wb") as stream:
        stream.write(input_text.encode("utf-8"))
    with open("/work/stdout.bin", "wb") as output, open("/work/stderr.bin", "wb") as error:
        try:
            with open("/work/stdin.bin", "rb") as input_file:
                child = subprocess.Popen(
                    command, stdin=input_file, stdout=output, stderr=error, start_new_session=True
                )
                try:
                    code = child.wait(timeout=timeout)
                    if code:
                        status = "crash"
                except subprocess.TimeoutExpired:
                    os.killpg(child.pid, signal.SIGKILL)
                    child.wait()
                    status = "timeout"
                finally:
                    # Reap surviving descendants before the next case shares this container.
                    try:
                        os.killpg(child.pid, signal.SIGKILL)
                    except ProcessLookupError:
                        pass
        except OSError as exc:
            status = "environment_error"
            error.write(str(exc).encode())
    stdout = Path("/work/stdout.bin").read_bytes()
    stderr = Path("/work/stderr.bin").read_bytes()
    if code == -signal.SIGXFSZ or max(len(stdout), len(stderr)) >= 32 * 1024**2:
        status = "output_limit"
    if b"No space left on device" in stderr:
        status = "workspace_limit"
    return {
        "status": status,
        "exit_code": code,
        "stdout": stdout[:65536].decode("utf-8", errors="replace"),
        "stdout_sha256": hashlib.sha256(stdout).hexdigest(),
        "stdout_bytes": len(stdout),
        "stdout_truncated": len(stdout) > 65536,
        "stderr": stderr[:4096].decode("utf-8", errors="replace"),
        "seconds": time.monotonic() - start,
    }


def main():
    job = json.loads(Path("/source/job.json").read_text(encoding="utf-8"))
    compilation = execute(job["compile"], "", 30)
    results = []
    start = time.monotonic()
    for input_text in job["inputs"]:
        remaining = job["total_seconds"] - (time.monotonic() - start)
        if compilation["status"] != "ok":
            results.append({"status": "not_run_compile_failure"})
        elif remaining <= 0:
            results.append({"status": "budget_exhausted"})
        else:
            results.append(execute(job["run"], input_text, min(job["case_seconds"], remaining)))
    print(json.dumps({"compilation": compilation, "results": results}))


if __name__ == "__main__":
    main()

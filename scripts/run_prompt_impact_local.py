"""Collect the frozen prompt pilot from a local llama.cpp server, with resumable raw records."""

from __future__ import annotations

import argparse
import hashlib
import json
import socket
import subprocess
import sys
import time
import urllib.error
import urllib.request
from pathlib import Path


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as source:
        for chunk in iter(lambda: source.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def choose_port() -> int:
    with socket.socket() as listener:
        listener.bind(("127.0.0.1", 0))
        return listener.getsockname()[1]


def get_json(url: str, payload: dict | None = None, timeout: int = 30) -> dict:
    body = None if payload is None else json.dumps(payload).encode("utf-8")
    request = urllib.request.Request(
        url,
        data=body,
        headers={"Content-Type": "application/json"},
        method="GET" if body is None else "POST",
    )
    with urllib.request.urlopen(request, timeout=timeout) as response:
        result = json.load(response)
    if not isinstance(result, dict):
        raise ValueError("Local model server returned a non-object response")
    return result


def wait_for_server(port: int, process: subprocess.Popen, seconds: int = 180) -> None:
    deadline = time.monotonic() + seconds
    while time.monotonic() < deadline:
        if process.poll() is not None:
            raise RuntimeError(f"llama-server exited during startup: {process.returncode}")
        try:
            status = get_json(f"http://127.0.0.1:{port}/health", timeout=3)
            if status.get("status") == "ok":
                return
        except (OSError, ValueError, urllib.error.HTTPError):
            pass
        time.sleep(1)
    raise TimeoutError("Local model server did not become healthy")


def load_existing(path: Path, requests: list[dict], model_id: str) -> set[tuple[str, str]]:
    if not path.exists():
        return set()
    expected = {(row["task_id"], row["variant"]): row for row in requests}
    completed: set[tuple[str, str]] = set()
    for line in path.read_text(encoding="utf-8").splitlines():
        if not line.strip():
            continue
        row = json.loads(line)
        identity = (row.get("task_id"), row.get("variant"))
        frozen = expected.get(identity)
        if frozen is None or identity in completed:
            raise ValueError(f"Unexpected or duplicate existing response: {identity}")
        if any(row.get(key) != frozen[key] for key in frozen):
            raise ValueError(f"Existing response does not match frozen request: {identity}")
        if row.get("model_id") != model_id or row.get("trial") != 1:
            raise ValueError(f"Existing response has a different model or trial: {identity}")
        completed.add(identity)
    return completed


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--server-exe", type=Path, required=True)
    parser.add_argument("--model", type=Path, required=True)
    parser.add_argument("--model-sha256", required=True)
    parser.add_argument("--model-id", required=True)
    parser.add_argument("--requests", type=Path, required=True)
    parser.add_argument("--responses", type=Path, required=True)
    parser.add_argument("--log-prefix", type=Path, required=True)
    parser.add_argument("--limit", type=int, default=0)
    args = parser.parse_args()

    repo_root = Path(__file__).resolve().parents[1]
    for output in (args.responses, args.log_prefix):
        if not output.resolve().is_relative_to(repo_root):
            parser.error("Output paths must stay inside the PRISM repository")
    if args.limit < 0:
        parser.error("--limit must be nonnegative")
    for source in (args.server_exe, args.model, args.requests):
        if not source.is_file():
            parser.error(f"Missing file: {source}")
    model_hash = sha256_file(args.model)
    if model_hash.lower() != args.model_sha256.lower():
        parser.error(f"Model SHA-256 mismatch: {model_hash}")
    request_sheet = json.loads(args.requests.read_text(encoding="utf-8"))
    requests = request_sheet["requests"]
    if not requests or len({(r["task_id"], r["variant"]) for r in requests}) != len(requests):
        parser.error("Request sheet is empty or contains duplicate task/variant identities")
    if any(r["manifest_sha256"] != request_sheet["manifest_sha256"] for r in requests):
        parser.error("Request sheet contains a manifest identity mismatch")
    completed = load_existing(args.responses, requests, args.model_id)

    args.responses.parent.mkdir(parents=True, exist_ok=True)
    args.log_prefix.parent.mkdir(parents=True, exist_ok=True)
    port = choose_port()
    command = [
        str(args.server_exe.resolve()),
        "--model", str(args.model.resolve()),
        "--alias", args.model_id,
        "--host", "127.0.0.1",
        "--port", str(port),
        "--ctx-size", "2048",
        "--threads", "4",
        "--n-gpu-layers", "0",
        "--jinja",
        "--chat-template-kwargs", '{"enable_thinking": false}',
    ]
    settings = {
        "model_id": args.model_id,
        "model_sha256": model_hash,
        "server_exe_sha256": sha256_file(args.server_exe),
        "manifest_sha256": request_sheet["manifest_sha256"],
        "request_sheet_sha256": sha256_file(args.requests),
        "server_args": command[1:],
        "request_body_settings": {
            "temperature": 0.0,
            "seed": 20261001,
            "max_tokens": 128,
            "chat_template_kwargs": {"enable_thinking": False},
        },
        "message_roles": ["user"],
        "date": time.strftime("%Y-%m-%dT%H:%M:%S%z"),
        "responses_path": str(args.responses.resolve()),
    }
    settings_path = args.log_prefix.with_suffix(".settings.json")
    if settings_path.exists():
        previous = json.loads(settings_path.read_text(encoding="utf-8"))
        for key in ("model_id", "model_sha256", "server_exe_sha256", "manifest_sha256",
                    "request_sheet_sha256", "request_body_settings", "message_roles"):
            if previous.get(key) != settings[key]:
                parser.error(f"Existing collection settings changed: {key}")
    else:
        settings_path.write_text(json.dumps(settings, indent=2) + "\n", encoding="utf-8")

    creationflags = subprocess.CREATE_NO_WINDOW if sys.platform == "win32" else 0
    stdout_path = args.log_prefix.with_suffix(".stdout.log")
    stderr_path = args.log_prefix.with_suffix(".stderr.log")
    with stdout_path.open("ab") as stdout_log, stderr_path.open("ab") as stderr_log:
        process = subprocess.Popen(
            command, stdout=stdout_log, stderr=stderr_log, creationflags=creationflags
        )
        try:
            wait_for_server(port, process)
            collected = 0
            with args.responses.open("a", encoding="utf-8") as destination:
                for request in requests:
                    identity = (request["task_id"], request["variant"])
                    if identity in completed:
                        continue
                    if args.limit and collected >= args.limit:
                        break
                    payload = {
                        "model": args.model_id,
                        "messages": [{"role": "user", "content": request["prompt"]}],
                        **settings["request_body_settings"],
                    }
                    started = time.monotonic()
                    response = get_json(
                        f"http://127.0.0.1:{port}/v1/chat/completions",
                        payload,
                        timeout=300,
                    )
                    elapsed = round(time.monotonic() - started, 3)
                    choice = response["choices"][0]
                    content = choice["message"]["content"]
                    if not isinstance(content, str):
                        raise ValueError(f"Model returned no text for {identity}")
                    row = {
                        **request,
                        "model_id": args.model_id,
                        "trial": 1,
                        "raw_response": content,
                        "elapsed_seconds": elapsed,
                        "finish_reason": choice.get("finish_reason"),
                        "usage": response.get("usage"),
                        "reasoning_content": choice["message"].get("reasoning_content"),
                    }
                    destination.write(json.dumps(row, ensure_ascii=False) + "\n")
                    destination.flush()
                    collected += 1
                    print(f"{collected} new: {identity[0]}/{identity[1]} ({elapsed}s)", flush=True)
        finally:
            process.terminate()
            try:
                process.wait(timeout=15)
            except subprocess.TimeoutExpired:
                process.kill()
                process.wait()


if __name__ == "__main__":
    main()

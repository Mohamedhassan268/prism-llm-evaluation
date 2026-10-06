"""Isolated Docker batch execution. No generated-code host fallback."""

from __future__ import annotations

import json
import os
import re
import subprocess
import uuid
from pathlib import Path

from .records import inside, read_json, write_json


def linux_path(path: Path) -> str:
    resolved = path.resolve()
    if os.name == "nt":
        return "/mnt/" + resolved.drive[0].lower() + resolved.as_posix()[2:]
    return str(resolved)


def language_commands(language: str, code: str) -> tuple[str, list[str], list[str]]:
    if language == "C":
        return "program.c", ["gcc", "/source/program.c", "-o", "/work/program"], ["/work/program"]
    if language == "C++":
        return (
            "program.cpp",
            ["g++", "/source/program.cpp", "-o", "/work/program"],
            ["/work/program"],
        )
    if language == "Go":
        return (
            "program.go",
            ["go", "build", "-o", "/work/program", "/source/program.go"],
            ["/work/program"],
        )
    if language == "Python":
        return (
            "program.py",
            [
                "python3",
                "-I",
                "-c",
                "import ast; ast.parse(open('/source/program.py',encoding='utf-8').read())",
            ],
            ["python3", "-I", "-B", "/source/program.py"],
        )
    if language == "Java":
        match = re.search(r"\bpublic\s+class\s+([A-Za-z_$][A-Za-z0-9_$]*)", code)
        if not match:
            match = re.search(r"\bclass\s+([A-Za-z_$][A-Za-z0-9_$]*)", code)
        name = match.group(1) if match else "Main"
        return (
            f"{name}.java",
            ["javac", "-d", "/work", f"/source/{name}.java"],
            ["java", "-XX:ActiveProcessorCount=1", "-Xmx256m", "-cp", "/work", name],
        )
    raise ValueError(f"Unsupported language: {language}")


class ContainerRunner:
    def __init__(self, root: Path, lock_path: str = "data/manifests/toolchains.lock.json"):
        self.root = root.resolve()
        self.lock = read_json(inside(self.root, lock_path))
        self.image = self.lock["image_id"]
        if not re.fullmatch(r"sha256:[0-9a-f]{64}", self.image):
            raise ValueError("Toolchain image must be pinned by SHA256 image ID")
        self.prefix = self.lock["docker_prefix"]
        expected = (
            ["wsl", "-d", "Ubuntu", "-u", "root", "--", "docker"] if os.name == "nt" else ["docker"]
        )
        if self.prefix != expected:
            raise ValueError("Unsupported Docker executable prefix in lock")

    def run_program(
        self,
        code: str,
        language: str,
        cases: list[dict],
        directory: Path,
        *,
        total_seconds: float = 120,
        case_seconds: float = 5,
    ) -> dict:
        if not cases or len(cases) > 121 or not 0 < total_seconds <= 120:
            raise ValueError("Require 1..121 cases and total deadline within (0,120]")
        if not 0 < case_seconds <= 5:
            raise ValueError("Case deadline must be within (0,5]")
        job = inside(self.root, directory)
        job.mkdir(parents=True, exist_ok=False)
        filename, compile_command, run_command = language_commands(language, code)
        (job / filename).write_text(code, encoding="utf-8", newline="\n")
        write_json(
            job / "job.json",
            {
                "compile": compile_command,
                "run": run_command,
                "inputs": [case["input"] for case in cases],
                "total_seconds": total_seconds,
                "case_seconds": case_seconds,
            },
        )
        mount_path = linux_path(job)
        if "," in mount_path or "\n" in mount_path:
            raise ValueError("Unsupported container mount path")
        name = "prismqa-" + uuid.uuid4().hex
        arguments = self.prefix + [
            "run",
            "--name",
            name,
            "--network",
            "none",
            "--read-only",
            "--user",
            "1000:1000",
            "--cpus",
            "1",
            "--memory",
            "1g",
            "--memory-swap",
            "1g",
            "--pids-limit",
            "64",
            "--cap-drop",
            "ALL",
            "--security-opt",
            "no-new-privileges",
            "--ulimit",
            "fsize=33554432:33554432",
            "--tmpfs",
            "/tmp:rw,nosuid,nodev,size=128m,mode=1777",
            "--tmpfs",
            "/work:rw,nosuid,nodev,exec,size=192m,mode=1777",
            "--mount",
            f"type=bind,src={mount_path},dst=/source,readonly",
            self.image,
            "python3",
            "-I",
            "/opt/prismqa/exec.py",
        ]
        fallback = {"compilation": {"status": "environment_error"}, "results": []}
        try:
            completed = subprocess.run(
                arguments,
                text=True,
                capture_output=True,
                timeout=total_seconds + 60,
                encoding="utf-8",
                errors="replace",
            )
            if completed.returncode:
                fallback["compilation"]["stderr"] = completed.stderr[-4096:]
                fallback["docker_exit_code"] = completed.returncode
            else:
                fallback = json.loads(completed.stdout)
                if len(fallback["results"]) != len(cases):
                    raise ValueError("Container result count does not match scheduled cases")
            state = subprocess.run(
                self.prefix + ["inspect", "--format", "{{json .State}}", name],
                text=True,
                capture_output=True,
                timeout=10,
            )
            if state.returncode == 0 and json.loads(state.stdout).get("OOMKilled"):
                fallback = {"compilation": {"status": "memory_limit"}, "results": []}
        except subprocess.TimeoutExpired:
            fallback = {"compilation": {"status": "environment_timeout"}, "results": []}
        except (OSError, json.JSONDecodeError) as exc:
            fallback["compilation"]["stderr"] = str(exc)
        finally:
            try:
                subprocess.run(
                    self.prefix + ["rm", "-f", name],
                    text=True,
                    capture_output=True,
                    timeout=15,
                    check=False,
                )
            except (OSError, subprocess.TimeoutExpired) as exc:
                fallback["cleanup_error"] = str(exc)
        return fallback

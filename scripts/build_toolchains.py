"""Resolve official image digests, build locally, and freeze resulting toolchains."""

from __future__ import annotations

import json
import os
import subprocess
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
PREFIX = ["wsl", "-d", "Ubuntu", "-u", "root", "--", "docker"] if os.name == "nt" else ["docker"]
BASES = {
    "PYTHON_IMAGE": "python:3.11-slim-bookworm",
    "JAVA_IMAGE": "eclipse-temurin:11-jdk-jammy",
    "GO_IMAGE": "golang:1.19.13-bullseye",
}


def call(*arguments: str, capture: bool = True) -> str:
    result = subprocess.run(
        PREFIX + list(arguments), check=True, text=True, capture_output=capture, timeout=1200
    )
    return result.stdout.strip() if capture else ""


def linux_path(path: Path) -> str:
    resolved = path.resolve()
    if os.name != "nt":
        return str(resolved)
    return "/mnt/" + resolved.drive[0].lower() + resolved.as_posix()[2:]


pins = {}
for name, tag in BASES.items():
    images = call("image", "ls", "-q").splitlines()
    if images:
        total_size = sum(item["Size"] for item in json.loads(call("image", "inspect", *images)))
        if total_size > 6 * 1024**3:
            raise RuntimeError("WSL image budget exceeded; no automatic deletion performed")
    call("pull", tag, capture=False)
    digest = json.loads(call("image", "inspect", tag))[0]["RepoDigests"][0]
    pins[name] = digest
arguments = ["build", "-t", "prismqa-toolchains:0.1"]
for name, digest in pins.items():
    arguments.extend(["--build-arg", f"{name}={digest}"])
arguments.append(linux_path(ROOT / "containers"))
call(*arguments, capture=False)
image = json.loads(call("image", "inspect", "prismqa-toolchains:0.1"))[0]
versions = call(
    "run",
    "--rm",
    "--network",
    "none",
    "--read-only",
    image["Id"],
    "python3",
    "-c",
    "import subprocess,json; "
    "commands={'python3':['python3','--version'],'gcc':['gcc','--version'],"
    "'g++':['g++','--version'],'go':['go','version'],'java':['java','-version']}; "
    "results={k:subprocess.run(v,capture_output=True,text=True) for k,v in commands.items()}; "
    "assert all(r.returncode==0 for r in results.values()); "
    "print(json.dumps({k:r.stdout+r.stderr for k,r in results.items()}))",
)
lock = {
    "image_id": image["Id"],
    "image_size": image["Size"],
    "base_images": pins,
    "docker_prefix": PREFIX,
    "toolchains": json.loads(versions),
    "authors_versions": {"python": "3.11", "gcc": "12", "g++": "12", "go": "1.19", "openjdk": "11"},
    "compatibility": "Major/minor lines follow paper; patch/vendor/build differences recorded.",
}
output = ROOT / "data/manifests/toolchains.lock.json"
output.write_text(json.dumps(lock, indent=2) + "\n", encoding="utf-8")
print(json.dumps(lock, indent=2))

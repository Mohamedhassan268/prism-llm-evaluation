"""Local research commands. Generated programs execute only through Docker."""

import argparse
import json
import shutil
import subprocess
from importlib import metadata
from pathlib import Path

from .authors import load_pairs, load_saved
from .evaluation import evaluate, verified_report
from .prompts import audit_prompts, load_prompt_records
from .records import file_hash, identity, inside, read_json, write_json
from .runner import ContainerRunner
from .sampling import sample


def doctor(root: Path) -> dict:
    packages = {}
    for name in (
        "prism-paper-qa",
        "pytest",
        "hypothesis",
        "ruff",
        "bandit",
        "pyspellchecker",
        "textstat",
        "sentence-transformers",
    ):
        try:
            packages[name] = metadata.version(name)
        except metadata.PackageNotFoundError:
            packages[name] = None
    cache = root / "data/cache"
    cache_bytes = sum(p.stat().st_size for p in cache.rglob("*") if p.is_file())
    free = shutil.disk_usage(root).free
    report = {
        "packages": packages,
        "free_bytes": free,
        "cache_bytes": cache_bytes,
        "storage_ready": free >= 5 * 1024**3 and cache_bytes <= 2 * 1024**3,
    }
    if Path("C:/").exists():
        report["system_volume_free_bytes"] = shutil.disk_usage("C:/").free
    try:
        runner = ContainerRunner(root)
        probe = subprocess.run(
            runner.prefix + ["image", "inspect", runner.image],
            capture_output=True,
            text=True,
            timeout=30,
        )
        report["container_ready"] = probe.returncode == 0
        report["toolchain_lock"] = runner.lock
        report["container_diagnostic"] = probe.stderr[-1000:]
    except (OSError, ValueError, subprocess.TimeoutExpired) as error:
        report.update(container_ready=False, container_diagnostic=str(error))
    return report


def artifact(root: Path, repository_path: str) -> Path:
    manifest = read_json(root / "data/manifests/authors_artifacts.json")
    matches = [item for item in manifest["artifacts"] if item["repository_path"] == repository_path]
    if len(matches) != 1:
        raise ValueError("Artifact is absent or ambiguous in pinned acquisition manifest")
    item = matches[0]
    path = inside(root, item["path"])
    if path.stat().st_size != item["bytes"] or file_hash(path) != item["sha256"]:
        raise ValueError("Acquired artifact checksum mismatch")
    return path


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(prog="prismqa")
    parser.add_argument("--root", type=Path, default=Path.cwd())
    commands = parser.add_subparsers(dest="command", required=True)
    commands.add_parser("doctor")
    ingest = commands.add_parser("ingest")
    ingest.add_argument("--output", required=True)
    ingest.add_argument("--sample-manifest")
    ingest.add_argument("--split", choices=["calibration", "evaluation"], default="calibration")
    ingest.add_argument("--model")
    selection = commands.add_parser("sample")
    selection.add_argument("--dataset", required=True)
    selection.add_argument("--output", required=True)
    selection.add_argument("--seed", type=int, default=20260929)
    selection.add_argument("--calibration", type=int, default=10)
    selection.add_argument("--evaluation", type=int, default=100)
    for name in ("reproduce", "evaluate"):
        run = commands.add_parser(name)
        run.add_argument("--dataset", required=True)
        run.add_argument("--profile", required=True)
        run.add_argument("--run", required=True)
        run.add_argument("--resume", action="store_true")
    prompts = commands.add_parser("audit-prompts")
    prompts.add_argument("--dataset", required=True)
    prompts.add_argument("--output", required=True)
    prompts.add_argument("--profile", choices=["baseline", "extension"], default="baseline")
    report = commands.add_parser("report")
    report.add_argument("--run", required=True)
    report.add_argument("--output", required=True)
    args = parser.parse_args(argv)
    root = args.root.resolve()
    try:
        if args.command == "doctor":
            result = doctor(root)
        elif args.command == "ingest":
            if args.sample_manifest:
                manifest = read_json(inside(root, args.sample_manifest))
                stored = manifest.pop("manifest_identity")
                if identity(manifest) != stored:
                    raise ValueError("Sample manifest identity mismatch")
                pairs = load_pairs(artifact(root, "Preliminary/dataset_after_processing.csv"))
                if identity(pairs) != manifest["dataset_identity"]:
                    raise ValueError("Sample belongs to a different pair catalog")
                result = load_saved(
                    artifact(root, "RQ3/rq3_files.zip"),
                    manifest["pair_ids"][args.split],
                    split=args.split,
                    model=args.model,
                )
                if not result:
                    raise ValueError("No saved outputs matched the selection")
                catalog = {item["sample_id"]: item for item in pairs}
                for item in result:
                    baseline = catalog[item["sample_id"]]
                    for field in (
                        "source_code",
                        "source_language",
                        "target_language",
                        "original_tests",
                    ):
                        if item[field] != baseline[field]:
                            raise ValueError(f"Saved output disagrees with pair catalog: {field}")
            else:
                result = load_pairs(artifact(root, "Preliminary/dataset_after_processing.csv"))
            write_json(inside(root, args.output), result)
            result = {"records": len(result), "output": args.output}
        elif args.command == "sample":
            result = sample(
                read_json(inside(root, args.dataset)),
                seed=args.seed,
                calibration=args.calibration,
                evaluation=args.evaluation,
            )
            destination = inside(root, args.output)
            if destination.exists() and read_json(destination) != result:
                raise ValueError(
                    "Frozen sample exists with different contents; choose a new version"
                )
            write_json(destination, result)
        elif args.command in ("reproduce", "evaluate"):
            profile = read_json(inside(root, args.profile))
            if args.command == "reproduce" and profile.get("domains"):
                raise ValueError(
                    "Reproduce preserves the original tests; use evaluate for extensions"
                )
            result = evaluate(
                root,
                read_json(inside(root, args.dataset)),
                profile,
                inside(root, args.run),
                resume=args.resume,
            )
        elif args.command == "audit-prompts":
            records = load_prompt_records(inside(root, args.dataset))
            result = audit_prompts(records, profile=args.profile)
            write_json(inside(root, args.output), result)
        else:
            state, result = verified_report(inside(root, args.run))
            text = "# Verified evaluation report\n\n"
            text += f"Run: `{state['run_identity']}`. Counts were recomputed from raw outcomes.\n\n"
            text += "```json\n" + json.dumps(result, indent=2) + "\n```\n\n"
            text += (
                "Compilation and stdout grading are reconstructed. Controlled fixtures "
                "demonstrate harness behavior; they are not paper findings.\n"
            )
            output = inside(root, args.output)
            output.parent.mkdir(parents=True, exist_ok=True)
            output.write_text(text, encoding="utf-8")
        print(json.dumps(result, indent=2))
        return 0
    except (ValueError, OSError, KeyError) as error:
        parser.exit(2, f"prismqa: {error}\n")


if __name__ == "__main__":
    raise SystemExit(main())

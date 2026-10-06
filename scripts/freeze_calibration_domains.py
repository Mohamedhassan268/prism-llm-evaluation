"""Bounded specification-based tests, frozen before extended target grading."""

import random
import urllib.request
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

from prepare_calibration import freeze

from prismqa.calibration_oracles import answer
from prismqa.records import file_hash, identity, read_json
from prismqa.sampling import program_group

ROOT = Path(__file__).resolve().parents[1]
TASKS = {
    "58801": (
        "abc125",
        "d",
        "Flipping Signs",
        "2<=N<=100000; -1e9<=Ai<=1e9",
        "N<=8 for exhaustive adjacent-flip state search",
    ),
    "58902": (
        "abc156",
        "b",
        "Digits",
        "1<=N<=1e9; 2<=K<=10",
        "Integer division oracle; boundaries at exact powers and their neighbors",
    ),
    "59448": ("abc145", "a", "Circle", "1<=r<=100", "All valid radii, except original test"),
    "60194": (
        "abc137",
        "d",
        "Summer Vacation",
        "1<=N,M,Ai<=100000; 1<=Bi<=10000",
        "N<=8 and M<=6 for exhaustive schedule search",
    ),
    "60265": (
        "abc165",
        "b",
        "1%",
        "101<=X<=1e18",
        "Exact rational compound-interest schedule; lower/upper boundaries",
    ),
    "60797": (
        "abc165",
        "c",
        "Many Requirements",
        "2<=N<=10; 1<=M<=10; 1<=Q<=50; 1<=a<b<=N; 0<=c<M; unique (a,b,c); 1<=d<=100000",
        "N,M<=5 for Cartesian enumeration",
    ),
    "61358": ("AOJ", "ITP1_1_D", "Watch", "0<=S<=86400", "Time-unit boundaries"),
    "61692": (
        "abc168",
        "a",
        "Therefore",
        "1<=N<=999",
        "Every final digit, one/two/three-digit inputs; declared pronunciation table",
    ),
    "62222": (
        "abc073",
        "a",
        "September 9",
        "10<=N<=99",
        "All valid two-digit integers, except original test",
    ),
    "62549": (
        "abc164",
        "c",
        "gacha",
        "1<=N<=200000; lowercase strings length 1..10",
        "N<=40; duplicate/all-distinct/prefix and length boundaries",
    ),
}


def candidates(pair):
    rng = random.Random(20260929 + int(pair))
    values = []
    if pair == "58801":
        arrays = [
            [0, 0],
            [-1, 1],
            [-1, -1],
            [1, 1],
            [-(10**9), 10**9],
            [-(10**9), 10**9, 10**9],
            [-1, 0, 2],
        ]
        arrays += [
            [rng.randint(-(10**9), 10**9) for _ in range(rng.randint(2, 8))] for _ in range(33)
        ]
        values = [f"{len(a)}\n" + " ".join(map(str, a)) + "\n" for a in arrays]
    elif pair == "58902":
        pairs = [(1, k) for k in range(2, 11)] + [(10**9, k) for k in range(2, 11)]
        for k in range(2, 11):
            for power in (1, 2, 5):
                pairs += [
                    (k**power + delta, k) for delta in (-1, 0, 1) if 1 <= k**power + delta <= 10**9
                ]
        values = [f"{n} {k}\n" for n, k in pairs]
    elif pair == "59448":
        values = [f"{r}\n" for r in range(1, 101)]
    elif pair == "60194":
        scenarios = [
            (1, [(2, 1)]),
            (1, [(1, 10000)]),
            (2, [(1, 1), (1, 10000)]),
            (6, [(100000, 10000)]),
            (3, [(1, 2), (1, 3), (1, 4), (2, 1), (2, 3)]),
        ]
        scenarios += [
            (
                rng.randint(1, 6),
                [(rng.randint(1, 9), rng.randint(1, 10000)) for _ in range(rng.randint(1, 8))],
            )
            for _ in range(35)
        ]
        values = [
            f"{len(jobs)} {days}\n" + "".join(f"{a} {b}\n" for a, b in jobs)
            for days, jobs in scenarios
        ]
    elif pair == "60265":
        goals = [101, 102, 103, 199, 200, 201, 202, 10**18, 1333333333]
        goals += [rng.randint(101, 10**18) for _ in range(31)]
        values = [f"{goal}\n" for goal in goals]
    elif pair == "60797":
        scenarios = [(2, 1, [(1, 2, 0, 100000)]), (2, 2, [(1, 2, 1, 1)])]
        for _ in range(38):
            n, m = rng.randint(2, 5), rng.randint(1, 5)
            pool = [(a, b, c) for a in range(1, n) for b in range(a + 1, n + 1) for c in range(m)]
            rng.shuffle(pool)
            rules = [
                (*triple, rng.randint(1, 100000))
                for triple in pool[: rng.randint(1, min(12, len(pool)))]
            ]
            scenarios.append((n, m, rules))
        values = [
            f"{n} {m} {len(rules)}\n" + "".join(" ".join(map(str, rule)) + "\n" for rule in rules)
            for n, m, rules in scenarios
        ]
    elif pair == "61358":
        times = [0, 1, 59, 60, 61, 3599, 3600, 3601, 86399, 86400]
        times += [rng.randint(0, 86400) for _ in range(30)]
        values = [f"{s}\n" for s in times]
    elif pair == "61692":
        counts = list(range(1, 21)) + list(range(90, 101)) + list(range(990, 1000))
        counts += [rng.randint(1, 999) for _ in range(40)]
        values = [f"{n}\n" for n in counts]
    elif pair == "62222":
        values = [f"{n}\n" for n in range(10, 100)]
    elif pair == "62549":
        groups = [["a"], ["a"] * 40, ["a", "aa", "aaa", "aaaaaaaaaa"], ["a", "b", "a", "b"]]
        for _ in range(36):
            pool = [
                "".join(rng.choice("abcd") for _ in range(rng.randint(1, 10)))
                for _ in range(rng.randint(1, 20))
            ]
            groups.append([rng.choice(pool) for _ in range(rng.randint(1, 40))])
        values = [f"{len(strings)}\n" + "\n".join(strings) + "\n" for strings in groups]
    return list(dict.fromkeys(values))[:100]


def snapshot(item):
    pair, details = item
    contest, task, title, constraints, coverage = details
    url = (
        f"https://atcoder.jp/contests/{contest}/tasks/{contest}_{task}?lang=en"
        if contest != "AOJ"
        else "https://judge.u-aizu.ac.jp/onlinejudge/description.jsp?id=ITP1_1_D&lang=en"
    )
    path = ROOT / "data/cache/task-statements" / f"{pair}.html"
    path.parent.mkdir(parents=True, exist_ok=True)
    if not path.exists():
        request = urllib.request.Request(url, headers={"User-Agent": "PRISM-QA-domain-audit"})
        with urllib.request.urlopen(request, timeout=60) as response:
            content = response.read(2 * 1024**2 + 1)
        if len(content) > 2 * 1024**2:
            raise ValueError("Task statement exceeds cache limit")
        path.write_bytes(content)
    return {
        "sample_id": pair,
        "task": f"{contest}_{task}",
        "title": title,
        "url": url,
        "constraints": constraints,
        "pilot_coverage": coverage,
        "snapshot": path.relative_to(ROOT).as_posix(),
        "sha256": file_hash(path),
        "retrieved_date": "2026-09-29",
        "mapping_basis": "Exact official sample match and code/contract review. "
        "Task attribution is reconstructed, not supplied by authors.",
        "mapping_review": "AI-assisted coordinator; independent human review pending",
    }


def main():
    sources = read_json(ROOT / "data/cache/calibration-sources.json")
    with ThreadPoolExecutor(max_workers=2) as pool:
        specs = list(pool.map(snapshot, sorted(TASKS.items())))
    domains = {}
    for record in sources:
        pair = record["sample_id"]
        original = record["original_tests"][0]
        if answer(pair, original["input"]) != original["expected"]:
            raise ValueError(f"Spec oracle disagrees with original sample: {pair}")
        inputs = [value for value in candidates(pair) if value != original["input"]]
        tests = [{"input": value, "expected": answer(pair, value)} for value in inputs]
        details = next(spec for spec in specs if spec["sample_id"] == pair)
        domains[program_group(record)] = {
            "status": "independently_checked",
            "sample_id": pair,
            "domain_description": details["constraints"],
            "pilot_coverage": details["pilot_coverage"],
            "specification": details,
            "oracle_implementation": "src/prismqa/calibration_oracles.py",
            "oracle_identity": file_hash(ROOT / "src/prismqa/calibration_oracles.py"),
            "oracle_evidence": "Specification-derived oracle; exhaustive alternative searches "
            "where needed; official sample checked; no source/target calls.",
            "reviewer": "AI-assisted coordinator, not an independent human reviewer",
            "tests": tests,
            "tests_identity": identity(tests),
        }
    profile = {
        **read_json(ROOT / "data/manifests/calibration-baseline-profile.json"),
        "version": "calibration-specification-tests-v1",
        "domains": domains,
    }
    freeze(ROOT / "data/manifests/calibration-domains-v1.json", profile)
    freeze(ROOT / "data/manifests/calibration-task-mapping.json", specs)
    print({entry["sample_id"]: len(entry["tests"]) for entry in domains.values()})


if __name__ == "__main__":
    main()

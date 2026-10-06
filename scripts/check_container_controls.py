"""Execute isolation controls and assert classifications from observed output."""

import uuid
from pathlib import Path

from prismqa.records import write_json
from prismqa.runner import ContainerRunner

ROOT = Path(__file__).resolve().parents[1]
ISOLATION = """import os, socket
assert os.getuid() == 1000
try:
    open('/source/job.json', 'w')
    raise AssertionError('source was writable')
except OSError:
    pass
try:
    open('/opt/prismqa/host-marker', 'w')
    raise AssertionError('root was writable')
except OSError:
    pass
assert [x for x in os.listdir('/sys/class/net') if x != 'lo'] == []
try:
    socket.create_connection(('1.1.1.1', 443), timeout=0.2)
    raise AssertionError('external networking was available')
except OSError:
    pass
print('isolated')
"""


def main():
    runner = ContainerRunner(ROOT)
    outcomes = {}
    cases = [
        ("isolation", ISOLATION, "ok"),
        ("crash", 'raise RuntimeError("control")', "crash"),
        ("timeout", "while True: pass", "timeout"),
    ]
    for name, code, expected in cases:
        result = runner.run_program(
            code,
            "Python",
            [{"input": ""}],
            ROOT / "runs/_jobs" / uuid.uuid4().hex,
            case_seconds=1,
            total_seconds=5,
        )
        outcomes[name] = result
        assert result["compilation"]["status"] == "ok", result
        assert result["results"][0]["status"] == expected, result
        if name == "isolation":
            assert result["results"][0]["stdout"] == "isolated\n", result
    write_json(
        ROOT / "reports/container-controls.json",
        {"toolchain": runner.lock, "outcomes": outcomes, "assertions_passed": True},
    )
    print("Container isolation, crash and timeout controls passed")


if __name__ == "__main__":
    main()

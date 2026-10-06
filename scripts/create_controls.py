"""Create arithmetic controls with independently calculated expected answers."""

from pathlib import Path

from prismqa.records import write_json
from prismqa.sampling import program_group

ROOT = Path(__file__).resolve().parents[1]
SOURCE = "a,b=map(int,input().split()); print(a+b)\n"
PROGRAMS = {
    "Python": SOURCE,
    "C": '#include <stdio.h>\nint main(){int a,b;scanf("%d%d",&a,&b);printf("%d\\n",a+b);}\n',
    "C++": '#include <iostream>\nint main(){int a,b;std::cin>>a>>b;std::cout<<a+b<<"\\n";}\n',
    "Go": 'package main\nimport "fmt"\nfunc main(){var a,b int;fmt.Scan(&a,&b);fmt.Println(a+b)}\n',
    "Java": "import java.util.Scanner;public class Main{public static void main(String[]x){"
    "Scanner s=new Scanner(System.in);int a=s.nextInt(),b=s.nextInt();"
    "System.out.println(a+b);}}\n",
}


def controls():
    records = []
    for language, code in PROGRAMS.items():
        records.append(
            {
                "id": "correct-" + language,
                "source_code": SOURCE,
                "source_language": "Python",
                "target_language": language,
                "raw_output": code,
                "original_tests": [{"input": "1 2\n", "expected": "3\n"}],
                "data_kind": "controlled_fixture",
            }
        )
    for name, code in [
        ("constant", "print(3)\n"),
        ("off-by-one", "a,b=map(int,input().split()); print(a+b if a==1 else a+b+1)\n"),
        ("crash", 'raise RuntimeError("controlled crash")\n'),
        ("timeout", "while True: pass\n"),
    ]:
        records.append({**records[0], "id": name, "raw_output": code})
    records.append({**records[0], "id": "wrapped", "raw_output": "```python\n" + SOURCE + "```\n"})
    records.append(
        {
            **records[0],
            "id": "ambiguous",
            "raw_output": "```python\nprint(3)\n```\n```python\n" + SOURCE + "```\n",
        }
    )
    profile = {
        "version": "controlled-arithmetic-v1",
        "comparator": "strict-exact-v1",
        "extraction": "conservative-fences-v1",
        "domains": {
            program_group(records[0]): {
                "status": "independently_checked",
                "domain_description": "Exactly two signed integers, each within -1000..1000. "
                "Expected sum is calculated independently, within int32.",
                "oracle_evidence": "Elementary integer addition; "
                "generator contains no program calls.",
                "tests": [
                    {"input": f"{a} {b}\n", "expected": f"{a + b}\n"}
                    for a, b in [(-1000, 1000), (0, 0), (2, 3), (1000, 1000), (-7, -9)]
                ],
            }
        },
    }
    return records, profile


if __name__ == "__main__":
    records, profile = controls()
    write_json(ROOT / "data/fixtures/code.json", records)
    write_json(ROOT / "data/fixtures/code-profile.json", profile)

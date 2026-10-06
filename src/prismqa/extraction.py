"""Conservative new extraction profile, kept distinct from the author baseline."""

from __future__ import annotations

import re

from .records import text_hash

FENCES = re.compile(r"^```([^\n]*)\n(.*?)^```[ \t]*\r?$", re.MULTILINE | re.DOTALL)
ALIASES = {
    "C": {"c"},
    "C++": {"cpp", "c++", "cxx"},
    "Go": {"go", "golang"},
    "Java": {"java"},
    "Python": {"python", "py", "python3"},
}
AUTHORS_REGEX = re.compile(
    r"Response:?.*?```(?:java|cpp|csharp|python|c|go|C\+\+|Java|Python|C#|C|Go)?\s*(.+?)\s*```",
    re.DOTALL,
)


def extract(raw: str, language: str, *, profile: str = "direct-v1", prompt: str = "") -> dict:
    if language not in ALIASES:
        raise ValueError(f"Unsupported language: {language}")
    if profile not in ("direct-v1", "conservative-fences-v1", "authors-regex-v1"):
        raise ValueError(f"Unknown extraction profile: {profile}")
    result = {"profile": profile, "raw_hash": text_hash(raw), "status": "ok", "code": raw}
    if not raw.strip():
        result.update(status="empty", code=None)
    elif profile == "authors-regex-v1":
        match = AUTHORS_REGEX.search(prompt + raw)
        result["code"] = match.group(1).strip() if match else None
        result["status"] = "ok" if match else "no_author_match"
        result["prompt_hash"] = text_hash(prompt)
    elif profile == "conservative-fences-v1":
        blocks = list(FENCES.finditer(raw))
        if len(blocks) > 1:
            result.update(status="ambiguous", code=None)
        elif len(blocks) == 1:
            block = blocks[0]
            label = block[1].strip().lower()
            if label and label not in ALIASES[language]:
                result.update(status="language_mismatch", code=None)
            else:
                # Exact fenced contents; no strip, algorithm edits or syntax repair.
                result["code"] = block[2]
        elif "```" in raw:
            result.update(status="malformed_fence", code=None)
    result["code_hash"] = text_hash(result["code"]) if result["code"] is not None else None
    return result

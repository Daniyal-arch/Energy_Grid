"""Append the second research pass (data/dark_evidence.yaml, brief 30 Track 2.3) to the notes of
the dark cells of the families kept by hand in data/coverage.yaml (wave 9 families get theirs
from `scripts/wave9.py render`). Idempotent: a note already holding the text is left alone.

    uv run python scripts/apply_evidence.py && uv run python scripts/coverage.py
"""

from __future__ import annotations

from pathlib import Path

import yaml

ROOT = Path(__file__).resolve().parents[1]


def main() -> None:
    ev = yaml.safe_load((ROOT / "data" / "dark_evidence.yaml").read_text(encoding="utf-8")) or {}
    path = ROOT / "data" / "coverage.yaml"
    text = path.read_text(encoding="utf-8")
    reg = yaml.safe_load(text)
    head = text.split("families:")[0]
    n = 0
    for fam, cells in ev.items():
        f = reg["families"].get(fam)
        if not f:
            continue
        for cc, e in cells.items():
            c = (f.get("cells") or {}).get(cc)
            if not c or c.get("status") not in ("not_published", "blocked") or not e.get("note"):
                continue
            add = f"Second pass ({e.get('checked', '')}): {e['note']}"
            if add not in str(c.get("note", "")):
                c["note"] = f"{c.get('note', '')} {add}".strip()
                c["checked"] = str(e.get("checked") or c.get("checked", ""))
                n += 1
    path.write_text(
        head
        + yaml.safe_dump(
            {"families": reg["families"]}, sort_keys=False, allow_unicode=True, width=200
        ),
        encoding="utf-8",
    )
    print(f"{n} cell notes extended")


if __name__ == "__main__":
    main()

"""Agent Skills (agent/skills/<name>/SKILL.md): progressive disclosure for any model.

The system prompt lists only each skill's name and description; the model loads a skill's body
with `load_skill(name)` and its reference files with `read_skill_file(name, path)` when it needs
them.
"""

from __future__ import annotations

import re
from dataclasses import dataclass
from pathlib import Path

import yaml

FRONT = re.compile(r"^---\n(.*?)\n---\n?(.*)$", re.S)


@dataclass
class Skill:
    name: str
    description: str
    body: str
    root: Path

    def files(self) -> list[str]:
        return sorted(
            p.relative_to(self.root).as_posix()
            for p in self.root.rglob("*")
            if p.is_file() and p.name != "SKILL.md"
        )


def parse(path: Path) -> Skill:
    m = FRONT.match(path.read_text(encoding="utf-8"))
    if not m:
        raise ValueError(f"{path}: no frontmatter")
    meta = yaml.safe_load(m.group(1)) or {}
    if not meta.get("name") or not meta.get("description"):
        raise ValueError(f"{path}: frontmatter needs name and description")
    return Skill(
        str(meta["name"]),
        " ".join(str(meta["description"]).split()),
        m.group(2).strip(),
        path.parent,
    )


class Skills:
    def __init__(self, root: Path) -> None:
        self.skills = {s.name: s for s in (parse(p) for p in sorted(root.glob("*/SKILL.md")))}

    def index(self) -> list[dict[str, str]]:
        return [{"name": s.name, "description": s.description} for s in self.skills.values()]

    def index_text(self) -> str:
        return "\n".join(f"- {s.name}: {s.description}" for s in self.skills.values())

    def load(self, name: str) -> dict[str, object]:
        s = self.skills.get(name)
        if not s:
            return {"error": f"unknown skill {name!r}; known: {sorted(self.skills)}"}
        return {"name": s.name, "body": s.body, "files": s.files()}

    def read_file(self, name: str, path: str) -> dict[str, object]:
        s = self.skills.get(name)
        if not s:
            return {"error": f"unknown skill {name!r}"}
        target = (s.root / path).resolve()
        if not target.is_relative_to(s.root.resolve()) or not target.is_file():
            return {"error": f"no file {path!r} in skill {name}; files: {s.files()}"}
        return {"name": name, "path": path, "text": target.read_text(encoding="utf-8")[:40_000]}


_skills: dict[str, Skills] = {}


def get_skills(agent_dir: Path) -> Skills:
    key = str(agent_dir)
    if key not in _skills:
        _skills[key] = Skills(agent_dir / "skills")
    return _skills[key]

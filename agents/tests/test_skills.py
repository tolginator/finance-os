"""Structural validation tests for Copilot Skills.

Ensures every skill directory contains a valid SKILL.md with required
YAML frontmatter fields, and that referenced resources exist.
"""

import re
from pathlib import Path

SKILLS_DIR = Path(__file__).resolve().parents[2] / ".github" / "skills"
REPO_ROOT = Path(__file__).resolve().parents[2]

REQUIRED_FIELDS = {"name", "description"}


def _parse_frontmatter(path: Path) -> dict[str, str]:
    """Extract YAML frontmatter key-value pairs from a SKILL.md file."""
    text = path.read_text()
    if not text.startswith("---"):
        return {}
    try:
        end = text.index("---", 3)
    except ValueError:
        return {}
    block = text[3:end]
    result: dict[str, str] = {}

    # Handle multi-line values (>- style) first
    for match in re.finditer(
        r"^(\w[\w-]*):\s*>-?\s*\n((?:\s+.+\n?)+)", block, re.MULTILINE
    ):
        result[match.group(1)] = " ".join(
            line.strip() for line in match.group(2).splitlines() if line.strip()
        )

    # Then single-line values (skip keys already parsed as multi-line)
    for match in re.finditer(r"^(\w[\w-]*):\s*(.+?)$", block, re.MULTILINE):
        key, val = match.group(1), match.group(2).strip()
        if key not in result and val not in (">-", ">", "|"):
            result[key] = val

    return result


def _all_skill_dirs() -> list[Path]:
    """Return all subdirectories under .github/skills/."""
    if not SKILLS_DIR.exists():
        return []
    return sorted(d for d in SKILLS_DIR.iterdir() if d.is_dir())


class TestSkillStructure:
    """Validate that all skill directories have valid SKILL.md files."""

    def test_skills_directory_exists(self) -> None:
        assert SKILLS_DIR.exists(), f"{SKILLS_DIR} does not exist"

    def test_every_skill_dir_has_skill_md(self) -> None:
        for skill_dir in _all_skill_dirs():
            skill_file = skill_dir / "SKILL.md"
            assert skill_file.exists(), f"{skill_dir.name}/ missing SKILL.md"

    def test_frontmatter_has_required_fields(self) -> None:
        for skill_dir in _all_skill_dirs():
            skill_file = skill_dir / "SKILL.md"
            if not skill_file.exists():
                continue
            fm = _parse_frontmatter(skill_file)
            missing = REQUIRED_FIELDS - set(fm.keys())
            assert not missing, (
                f"{skill_dir.name}/SKILL.md missing frontmatter: {missing}"
            )

    def test_frontmatter_name_matches_directory(self) -> None:
        for skill_dir in _all_skill_dirs():
            skill_file = skill_dir / "SKILL.md"
            if not skill_file.exists():
                continue
            fm = _parse_frontmatter(skill_file)
            assert fm.get("name") == skill_dir.name, (
                f"{skill_dir.name}/SKILL.md name '{fm.get('name')}' "
                f"doesn't match directory name"
            )

    def test_frontmatter_description_not_empty(self) -> None:
        for skill_dir in _all_skill_dirs():
            skill_file = skill_dir / "SKILL.md"
            if not skill_file.exists():
                continue
            fm = _parse_frontmatter(skill_file)
            desc = fm.get("description", "")
            assert desc and len(desc.strip()) > 10, (
                f"{skill_dir.name}/SKILL.md description too short or empty"
            )

    def test_referenced_scripts_exist(self) -> None:
        for skill_dir in _all_skill_dirs():
            skill_file = skill_dir / "SKILL.md"
            if not skill_file.exists():
                continue
            text = skill_file.read_text()
            # Find `source <path>` references in code blocks
            for line in text.splitlines():
                stripped = line.strip()
                if stripped.startswith("source ") and not stripped.startswith("source_"):
                    script_path = stripped.split("source ", 1)[1].strip()
                    full_path = REPO_ROOT / script_path
                    assert full_path.exists(), (
                        f"{skill_dir.name}/SKILL.md references "
                        f"'{script_path}' which doesn't exist"
                    )

    def test_at_least_one_skill_exists(self) -> None:
        dirs = _all_skill_dirs()
        assert len(dirs) >= 1, "No skills found under .github/skills/"

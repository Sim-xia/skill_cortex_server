from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path


@dataclass(frozen=True)
class SkillFrontmatter:
	title: str
	description: str
	tags: tuple[str, ...]


@dataclass(frozen=True)
class SkillRecord:
	skill_id: str
	source_root: Path
	skill_path: Path
	category_path: tuple[str, ...]
	frontmatter: SkillFrontmatter
	description_snapshot: str
	tag_issues: tuple[str, ...]


@dataclass
class TreeNode:
	name: str
	path: tuple[str, ...]
	children: dict[str, TreeNode] = field(default_factory=dict)
	skills: list[SkillRecord] = field(default_factory=list)


@dataclass(frozen=True)
class ScanResult:
	skills: tuple[SkillRecord, ...]
	tree: TreeNode

from __future__ import annotations

import json
from pathlib import Path

from skill_cortex.models import ScanResult, SkillFrontmatter, SkillRecord, TreeNode


def _skill_to_dict(skill: SkillRecord) -> dict:
	return {
		"skill_id": skill.skill_id,
		"source_root": str(skill.source_root),
		"skill_path": str(skill.skill_path),
		"category_path": list(skill.category_path),
		"title": skill.frontmatter.title,
		"description": skill.frontmatter.description,
		"tags": list(skill.frontmatter.tags),
		"description_snapshot": skill.description_snapshot,
		"tag_issues": list(skill.tag_issues),
	}


def _dict_to_skill(data: dict) -> SkillRecord:
	frontmatter = SkillFrontmatter(
		title=str(data.get("title", "")),
		description=str(data.get("description", "")),
		tags=tuple(str(t) for t in data.get("tags", []) if str(t).strip()),
	)
	return SkillRecord(
		skill_id=str(data.get("skill_id", "")),
		source_root=Path(str(data.get("source_root", ""))),
		skill_path=Path(str(data.get("skill_path", ""))),
		category_path=tuple(str(p) for p in data.get("category_path", []) if str(p).strip()),
		frontmatter=frontmatter,
		description_snapshot=str(data.get("description_snapshot", "")),
		tag_issues=tuple(str(p) for p in data.get("tag_issues", []) if str(p).strip()),
	)


def build_tree(skills: tuple[SkillRecord, ...]) -> TreeNode:
	root_node = TreeNode(name="/", path=())
	for record in skills:
		node = root_node
		for part in record.category_path:
			child = node.children.get(part)
			if child is None:
				child = TreeNode(name=part, path=(*node.path, part))
				node.children[part] = child
			node = child
		node.skills.append(record)
	return root_node


def save_index(cache_path: Path, scan: ScanResult) -> None:
	cache_path.parent.mkdir(parents=True, exist_ok=True)
	payload = {
		"version": 1,
		"skills": [_skill_to_dict(s) for s in scan.skills],
	}
	cache_path.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")


def load_index(cache_path: Path) -> ScanResult | None:
	if not cache_path.exists() or not cache_path.is_file():
		return None

	try:
		data = json.loads(cache_path.read_text(encoding="utf-8"))
	except Exception:
		return None

	if not isinstance(data, dict) or data.get("version") != 1:
		return None
	items = data.get("skills", [])
	if not isinstance(items, list):
		return None

	skills: list[SkillRecord] = []
	for item in items:
		if not isinstance(item, dict):
			continue
		skills.append(_dict_to_skill(item))

	skills_tuple = tuple(skills)
	return ScanResult(skills=skills_tuple, tree=build_tree(skills_tuple))

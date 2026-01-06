from __future__ import annotations

from pathlib import Path

from skill_cortex.frontmatter import make_description_snapshot, parse_skill_markdown
from skill_cortex.models import ScanResult, SkillFrontmatter, SkillRecord, TreeNode
from skill_cortex.tags_registry import TagsRegistry


def _make_skill_id(source_root: Path, skill_md_path: Path) -> str:
	rel = skill_md_path.relative_to(source_root)
	return f"{source_root.name}:{rel.as_posix()}"


def _make_category_path(source_root: Path, skill_md_path: Path) -> tuple[str, ...]:
	rel_parent = skill_md_path.parent.relative_to(source_root)
	return tuple(p for p in rel_parent.parts if p)


def _insert_into_tree(root: TreeNode, record: SkillRecord) -> None:
	node = root
	for part in record.category_path:
		child = node.children.get(part)
		if child is None:
			child = TreeNode(name=part, path=(*node.path, part))
			node.children[part] = child
		node = child
	node.skills.append(record)



def _validate_tags(tags: tuple[str, ...], registry: TagsRegistry) -> tuple[str, ...]:
	issues: list[str] = []
	if not tags:
		issues.append("missing_tags")
		return tuple(issues)

	if registry.allowed_tags:
		invalid_tags = [t for t in tags if t not in registry.allowed_tags]
		if invalid_tags:
			issues.append("invalid_tags:" + ",".join(invalid_tags))
	return tuple(issues)


def scan_skills(roots: tuple[Path, ...], tags_registry: TagsRegistry | None = None) -> ScanResult:
	root_node = TreeNode(name="/", path=())
	skills: list[SkillRecord] = []
	registry = tags_registry or TagsRegistry(allowed_tags=frozenset())

	for root in roots:
		if not root.exists() or not root.is_dir():
			continue

		for skill_md_path in root.rglob("SKILL.md"):
			try:
				text = skill_md_path.read_text(encoding="utf-8")
				extracted = parse_skill_markdown(text)
			except Exception:
				continue

			skill_id = _make_skill_id(root, skill_md_path)
			category_path = _make_category_path(root, skill_md_path)

			frontmatter = SkillFrontmatter(
				title=extracted.title,
				description=extracted.description,
				tags=extracted.tags,
			)
			record = SkillRecord(
				skill_id=skill_id,
				source_root=root,
				skill_path=skill_md_path,
				category_path=category_path,
				frontmatter=frontmatter,
				description_snapshot=make_description_snapshot(extracted.description),
				tag_issues=_validate_tags(extracted.tags, registry),
			)
			skills.append(record)
			_insert_into_tree(root_node, record)

	return ScanResult(skills=tuple(skills), tree=root_node)

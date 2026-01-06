from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path


@dataclass(frozen=True)
class TagsRegistry:
	allowed_tags: frozenset[str]


def load_tags_registry(tags_path: Path) -> TagsRegistry:
	if not tags_path.exists() or not tags_path.is_file():
		return TagsRegistry(allowed_tags=frozenset())

	raw = tags_path.read_text(encoding="utf-8")
	allowed: set[str] = set()
	for raw_line in raw.splitlines():
		line = raw_line.strip()
		if not line:
			continue
		if line.startswith("#"):
			continue
		if line.startswith("-"):
			line = line[1:].strip()
		tag = line.strip().lower()
		if not tag:
			continue
		allowed.add(tag)

	return TagsRegistry(allowed_tags=frozenset(allowed))

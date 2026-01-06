from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class ParsedFrontmatter:
	title: str
	description: str
	tags: tuple[str, ...]


def normalize_tags(tags: list[str] | tuple[str, ...]) -> tuple[str, ...]:
	seen: set[str] = set()
	normalized: list[str] = []
	for raw_tag in tags:
		tag = str(raw_tag).strip().lower()
		if not tag:
			continue
		if tag in seen:
			continue
		seen.add(tag)
		normalized.append(tag)
	return tuple(normalized)


def make_description_snapshot(description: str, max_words: int = 30) -> str:
	words = description.strip().split()
	if len(words) <= max_words:
		return " ".join(words)
	return " ".join(words[:max_words])


def _parse_key_value_line(line: str) -> tuple[str, str] | None:
	if ":" not in line:
		return None
	key, value = line.split(":", 1)
	key = key.strip()
	value = value.strip()
	if not key:
		return None
	return key, value


def _parse_tags_value(value: str) -> list[str]:
	v = value.strip()
	if not v:
		return []
	if v.startswith("[") and v.endswith("]"):
		inner = v[1:-1].strip()
		if not inner:
			return []
		return [p.strip().strip("\"'") for p in inner.split(",") if p.strip()]
	return [p.strip().strip("\"'") for p in v.split(",") if p.strip()]


def parse_skill_markdown(markdown_text: str) -> ParsedFrontmatter:
	text = markdown_text.lstrip("\ufeff")
	lines = text.splitlines()
	if not lines or lines[0].strip() != "---":
		raise ValueError("missing_frontmatter")

	frontmatter_lines: list[str] = []
	end_index = None
	for i in range(1, len(lines)):
		if lines[i].strip() == "---":
			end_index = i
			break
		frontmatter_lines.append(lines[i])
	if end_index is None:
		raise ValueError("unterminated_frontmatter")

	title = ""
	description = ""
	tags: list[str] = []
	in_tags_list = False

	for raw_line in frontmatter_lines:
		line = raw_line.strip()
		if not line:
			continue

		if in_tags_list:
			if line.startswith("-"):
				tags.append(line[1:].strip().strip("\"'"))
				continue
			in_tags_list = False

		parsed = _parse_key_value_line(line)
		if parsed is None:
			continue
		key, value = parsed
		key_lower = key.lower()

		if key_lower == "title":
			title = value.strip().strip("\"'")
		elif key_lower == "name" and not title:
			title = value.strip().strip("\"'")
		elif key_lower == "description":
			description = value.strip().strip("\"'")
		elif key_lower == "tags":
			if value == "" or value == "[]":
				in_tags_list = True
				continue
			tags.extend(_parse_tags_value(value))

	if not title:
		raise ValueError("missing_title")
	if not description:
		raise ValueError("missing_description")

	return ParsedFrontmatter(
		title=title,
		description=description,
		tags=normalize_tags(tags),
	)

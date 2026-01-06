from __future__ import annotations

import os
from dataclasses import dataclass
from pathlib import Path


@dataclass(frozen=True)
class AppConfig:
	roots: tuple[Path, ...]
	cache_path: Path
	tags_path: Path


def _default_roots() -> tuple[Path, ...]:
	return (
		Path(os.path.expanduser("~/.claude/skills")),
		Path.cwd() / ".skills",
	)


def load_config() -> AppConfig:
	roots_env = os.getenv("SKILL_CORTEX_ROOTS", "").strip()
	if roots_env:
		roots = tuple(Path(p.strip()).expanduser() for p in roots_env.split(",") if p.strip())
	else:
		roots = _default_roots()

	cache_path_env = os.getenv("SKILL_CORTEX_CACHE_PATH", "").strip()
	if cache_path_env:
		cache_path = Path(cache_path_env).expanduser()
	else:
		cache_path = Path.cwd() / ".skill_cortex_cache" / "index.json"

	tags_path_env = os.getenv("SKILL_CORTEX_TAGS_PATH", "").strip()
	if tags_path_env:
		tags_path = Path(tags_path_env).expanduser()
	else:
		tags_path = Path.cwd() / "tags.md"

	return AppConfig(roots=roots, cache_path=cache_path, tags_path=tags_path)

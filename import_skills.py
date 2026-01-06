from __future__ import annotations

import argparse
import shutil
import subprocess
import sys
from dataclasses import dataclass
from pathlib import Path


@dataclass(frozen=True)
class RepoSource:
	name: str
	url: str


def _run(cmd: list[str], cwd: Path | None = None) -> None:
	result = subprocess.run(
		cmd,
		cwd=str(cwd) if cwd else None,
		check=False,
		text=True,
		stdout=sys.stdout,
		stderr=sys.stderr,
	)
	if result.returncode != 0:
		raise RuntimeError(f"command_failed: {' '.join(cmd)}")


def _ensure_repo_cloned(repo: RepoSource, sources_dir: Path, update: bool) -> Path:
	sources_dir.mkdir(parents=True, exist_ok=True)
	repo_dir = sources_dir / repo.name

	if repo_dir.exists() and (repo_dir / ".git").exists():
		if update:
			_run(["git", "-C", str(repo_dir), "pull", "--ff-only"])
		return repo_dir

	if repo_dir.exists():
		shutil.rmtree(repo_dir)

	_run(["git", "clone", "--depth", "1", repo.url, str(repo_dir)])
	return repo_dir


def _copy_skill_folder(src_skill_dir: Path, repo_root: Path, dest_root: Path) -> Path:
	rel = src_skill_dir.relative_to(repo_root)
	dest_dir = dest_root / rel
	dest_dir.parent.mkdir(parents=True, exist_ok=True)
	shutil.copytree(src_skill_dir, dest_dir, dirs_exist_ok=True)
	return dest_dir


def import_skills(
	repos: list[RepoSource],
	project_root: Path,
	update: bool,
	clean: bool,
	clone: bool,
	dry_run: bool,
) -> int:
	sources_dir = project_root / ".skill_cortex_sources"
	import_dir = project_root / ".skills" / "imported"

	if clean and import_dir.exists() and not dry_run:
		shutil.rmtree(import_dir)

	count = 0
	for repo in repos:
		repo_root = sources_dir / repo.name
		if clone:
			repo_root = _ensure_repo_cloned(repo, sources_dir=sources_dir, update=update)

		if not repo_root.exists():
			continue

		dest_root = import_dir / repo.name
		seen_dirs: set[Path] = set()
		for skill_md in repo_root.rglob("SKILL.md"):
			src_skill_dir = skill_md.parent
			if src_skill_dir in seen_dirs:
				continue
			seen_dirs.add(src_skill_dir)
			if dry_run:
				rel = src_skill_dir.relative_to(repo_root)
				print(f"[dry-run] {repo.name}: {rel.as_posix()}")
				count += 1
				continue
			_copy_skill_folder(src_skill_dir, repo_root=repo_root, dest_root=dest_root)
			count += 1

	return count


def main() -> None:
	parser = argparse.ArgumentParser()
	parser.add_argument("--clean", action="store_true", help="remove ./.skills/imported before import")
	parser.add_argument("--no-update", action="store_true", help="do not git pull if repo exists")
	parser.add_argument("--dry-run", action="store_true", help="preview what would be imported; no file writes")
	parser.add_argument(
		"--no-clone",
		action="store_true",
		help="do not git clone/pull; only import from existing .skill_cortex_sources",
	)
	parser.add_argument("--only", action="append", default=[], help="limit to a source name (repeatable)")
	args = parser.parse_args()

	repos = [
		RepoSource(name="agentskills_agentskills", url="https://github.com/agentskills/agentskills.git"),
		RepoSource(name="anthropics_skills", url="https://github.com/anthropics/skills.git"),
		RepoSource(name="huggingface_skills", url="https://github.com/huggingface/skills.git"),
	]
	if args.only:
		allowed = set(args.only)
		repos = [r for r in repos if r.name in allowed]

	project_root = Path.cwd()
	try:
		count = import_skills(
			repos=repos,
			project_root=project_root,
			update=not args.no_update,
			clean=args.clean,
			clone=not args.no_clone,
			dry_run=args.dry_run,
		)
	except Exception as exc:
		print(f"error: {exc}", file=sys.stderr)
		raise

	print(f"imported_skill_folders: {count}")


if __name__ == "__main__":
	main()

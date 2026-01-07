from __future__ import annotations

import argparse
import json
import shutil
import subprocess
import sys
import time
from dataclasses import dataclass
from pathlib import Path
from typing import Optional

try:
	import yaml
except ImportError:
	yaml = None


@dataclass(frozen=True)
class RepoSource:
	name: str
	url: str
	enabled: bool = True
	branch: Optional[str] = None


@dataclass
class ImportStats:
	"""Statistics for import operations"""
	total_repos: int = 0
	successful_repos: int = 0
	failed_repos: int = 0
	total_skills: int = 0
	start_time: float = 0.0
	
	def add_repo_success(self, skill_count: int):
		self.successful_repos += 1
		self.total_skills += skill_count
	
	def add_repo_failure(self):
		self.failed_repos += 1
	
	def get_duration(self) -> float:
		return time.time() - self.start_time if self.start_time > 0 else 0.0


@dataclass
class ErrorInfo:
	"""Information about an error that occurred during import"""
	repo_name: str
	error_type: str
	error_message: str
	step: str  # clone, scan, copy, etc.


class ErrorHandler:
	"""Handles errors during import operations with graceful recovery"""
	
	def __init__(self):
		self.errors: list[ErrorInfo] = []
	
	def handle_repo_error(self, repo_name: str, error: Exception, step: str = "unknown") -> bool:
		"""Handle repository-level errors, return True to continue with other repos"""
		error_type = type(error).__name__
		error_message = str(error)
		
		# Log the error for later reporting
		self.errors.append(ErrorInfo(
			repo_name=repo_name,
			error_type=error_type,
			error_message=error_message,
			step=step
		))
		
		# Determine if we should continue based on error type
		if isinstance(error, KeyboardInterrupt):
			# User interrupted - don't continue
			return False
		elif isinstance(error, (OSError, IOError)):
			# File system or network errors - continue with other repos
			return True
		elif isinstance(error, subprocess.CalledProcessError):
			# Git command failed - continue with other repos
			return True
		else:
			# Unknown error - continue but log it
			return True
	
	def handle_skill_error(self, repo_name: str, skill_path: str, error: Exception):
		"""Handle individual skill processing errors"""
		error_type = type(error).__name__
		error_message = f"Skill '{skill_path}': {str(error)}"
		
		self.errors.append(ErrorInfo(
			repo_name=repo_name,
			error_type=error_type,
			error_message=error_message,
			step="copy_skill"
		))
	
	def get_error_summary(self) -> list[str]:
		"""Return list of all errors encountered"""
		if not self.errors:
			return []
		
		summary = []
		summary.append("Detailed error information:")
		
		for error in self.errors:
			summary.append(f"  • {error.repo_name} ({error.step}): {error.error_type} - {error.error_message}")
		
		return summary
	
	def has_errors(self) -> bool:
		"""Check if any errors were encountered"""
		return len(self.errors) > 0
	
	def get_error_count(self) -> int:
		"""Get total number of errors"""
		return len(self.errors)


class ProgressReporter:
	"""Provides clear feedback during the import process"""
	
	def __init__(self, dry_run: bool = False):
		self.dry_run = dry_run
		self.stats = ImportStats()
		self.error_handler = ErrorHandler()
	
	def start_import(self, total_repos: int):
		"""Initialize import progress tracking"""
		self.stats.total_repos = total_repos
		self.stats.start_time = time.time()
		
		mode = "DRY RUN" if self.dry_run else "IMPORT"
		print(f"\n🚀 Starting skills {mode.lower()}...")
		print(f"📦 Processing {total_repos} repositories")
		print("-" * 50)
	
	def start_repo(self, repo_name: str, index: int):
		"""Report starting repository processing"""
		progress = f"[{index}/{self.stats.total_repos}]"
		print(f"\n{progress} 📂 Processing repository: {repo_name}")
		
		if not self.dry_run:
			print(f"  🔄 Cloning/updating repository...")
	
	def report_clone_step(self, repo_name: str):
		"""Report repository cloning step"""
		if not self.dry_run:
			print(f"  ✅ Repository cloned/updated successfully")
	
	def report_scan_step(self, repo_name: str):
		"""Report repository scanning step"""
		print(f"  🔍 Scanning for SKILL.md files...")
	
	def report_skills(self, repo_name: str, skill_count: int):
		"""Report number of skills found in repository"""
		if skill_count > 0:
			print(f"  📋 Found {skill_count} skills")
			if not self.dry_run:
				print(f"  📥 Copying skills...")
		else:
			print(f"  ⚠️  No skills found in repository")
	
	def report_repo_success(self, repo_name: str, skill_count: int):
		"""Report successful repository processing"""
		self.stats.add_repo_success(skill_count)
		if skill_count > 0:
			print(f"  ✅ Successfully processed {skill_count} skills from {repo_name}")
		else:
			print(f"  ✅ Repository processed (no skills found)")
	
	def report_repo_error(self, repo_name: str, error: Exception, step: str = "unknown"):
		"""Report repository processing error"""
		self.stats.add_repo_failure()
		
		# Use ErrorHandler to categorize and log the error
		should_continue = self.error_handler.handle_repo_error(repo_name, error, step)
		
		# Display user-friendly error message
		if isinstance(error, subprocess.CalledProcessError):
			print(f"  ❌ Git operation failed for {repo_name}")
		elif isinstance(error, FileNotFoundError):
			print(f"  ❌ Repository directory not found: {repo_name}")
		elif isinstance(error, PermissionError):
			print(f"  ❌ Permission denied accessing {repo_name}")
		elif isinstance(error, OSError):
			print(f"  ❌ File system error with {repo_name}")
		else:
			print(f"  ❌ Failed to process {repo_name}: {str(error)}")
		
		if should_continue:
			print(f"  ⏭️  Continuing with next repository...")
		
		return should_continue
	
	def report_skill_error(self, repo_name: str, skill_path: str, error: Exception):
		"""Report individual skill processing error"""
		self.error_handler.handle_skill_error(repo_name, skill_path, error)
		print(f"    ⚠️  Failed to process skill {skill_path}: {str(error)}")
	
	def final_summary(self):
		"""Display final import summary"""
		duration = self.stats.get_duration()
		mode = "DRY RUN" if self.dry_run else "IMPORT"
		
		print("\n" + "=" * 50)
		print(f"📊 {mode} SUMMARY")
		print("=" * 50)
		
		print(f"⏱️  Duration: {duration:.1f} seconds")
		print(f"📦 Repositories processed: {self.stats.successful_repos + self.stats.failed_repos}/{self.stats.total_repos}")
		print(f"✅ Successful: {self.stats.successful_repos}")
		
		if self.stats.failed_repos > 0:
			print(f"❌ Failed: {self.stats.failed_repos}")
		
		if self.dry_run:
			print(f"📋 Skills that would be imported: {self.stats.total_skills}")
		else:
			print(f"📥 Skills imported: {self.stats.total_skills}")
		
		# Show error details if any
		if self.error_handler.has_errors():
			print(f"\n⚠️  {self.error_handler.get_error_count()} errors encountered:")
			error_summary = self.error_handler.get_error_summary()
			for line in error_summary:
				print(line)
		
		if self.stats.failed_repos > 0:
			print(f"\n⚠️  Some repositories failed to process. See error details above.")
		elif self.stats.successful_repos > 0:
			print(f"\n🎉 All repositories processed successfully!")
		else:
			print(f"\n⚠️  No repositories were processed successfully.")
		
		print("=" * 50)


class ConfigLoader:
	"""Loads repository configuration from YAML or JSON files"""
	
	def load_config(self, config_path: Optional[str] = None) -> list[RepoSource]:
		"""Load repository configuration from file or use defaults"""
		if config_path:
			if not Path(config_path).exists():
				print(f"Error: Configuration file '{config_path}' not found", file=sys.stderr)
				print("Using default repositories", file=sys.stderr)
				return self._get_default_repos()
			return self._load_from_file(config_path)
		
		# Try to find config files in current directory
		for filename in ["skills-config.yaml", "skills-config.yml", "skills-config.json"]:
			config_file = Path(filename)
			if config_file.exists():
				print(f"Using configuration file: {filename}")
				return self._load_from_file(str(config_file))
		
		# Fall back to default repositories
		print("No configuration file found, using default repositories")
		return self._get_default_repos()
	
	def _load_from_file(self, config_path: str) -> list[RepoSource]:
		"""Load configuration from YAML or JSON file"""
		try:
			if config_path.endswith(('.yaml', '.yml')):
				config_data = self._load_yaml(config_path)
			elif config_path.endswith('.json'):
				config_data = self._load_json(config_path)
			else:
				raise ValueError(f"Unsupported config file format: {config_path}. Supported formats: .yaml, .yml, .json")
			
			repos = self._parse_config_data(config_data, config_path)
			if not repos:
				print(f"Warning: No valid repositories found in {config_path}, using defaults", file=sys.stderr)
				return self._get_default_repos()
			
			print(f"Loaded {len(repos)} repositories from {config_path}")
			return repos
			
		except ImportError as e:
			print(f"Error: {e}", file=sys.stderr)
			print("Falling back to default repositories", file=sys.stderr)
			return self._get_default_repos()
		except (json.JSONDecodeError, yaml.YAMLError if yaml else Exception) as e:
			print(f"Error parsing config file {config_path}: {e}", file=sys.stderr)
			print("Falling back to default repositories", file=sys.stderr)
			return self._get_default_repos()
		except Exception as e:
			print(f"Error loading config file {config_path}: {e}", file=sys.stderr)
			print("Falling back to default repositories", file=sys.stderr)
			return self._get_default_repos()
	
	def _load_yaml(self, path: str) -> dict:
		"""Load YAML configuration file"""
		if yaml is None:
			raise ImportError("PyYAML is required for YAML config files. Install with: pip install PyYAML")
		
		with open(path, 'r', encoding='utf-8') as f:
			data = yaml.safe_load(f)
			if data is None:
				raise ValueError("YAML file is empty or invalid")
			return data
	
	def _load_json(self, path: str) -> dict:
		"""Load JSON configuration file"""
		with open(path, 'r', encoding='utf-8') as f:
			return json.load(f)
	
	def _parse_config_data(self, config_data: dict, config_path: str) -> list[RepoSource]:
		"""Parse configuration data into RepoSource objects"""
		if not isinstance(config_data, dict):
			raise ValueError("Configuration must be a JSON object or YAML mapping")
		
		repositories = config_data.get('repositories', [])
		if not isinstance(repositories, list):
			raise ValueError("'repositories' must be a list")
		
		repos = []
		for i, repo_config in enumerate(repositories):
			if not isinstance(repo_config, dict):
				print(f"Warning: Repository {i+1} in {config_path} is not a valid object, skipping", file=sys.stderr)
				continue
			
			name = repo_config.get('name')
			url = repo_config.get('url')
			enabled = repo_config.get('enabled', True)
			branch = repo_config.get('branch')
			
			# Validate required fields
			if not name:
				print(f"Warning: Repository {i+1} in {config_path} missing 'name' field, skipping", file=sys.stderr)
				continue
			if not url:
				print(f"Warning: Repository '{name}' in {config_path} missing 'url' field, skipping", file=sys.stderr)
				continue
			if not isinstance(enabled, bool):
				print(f"Warning: Repository '{name}' has invalid 'enabled' value, defaulting to true", file=sys.stderr)
				enabled = True
			
			if enabled:
				repos.append(RepoSource(name=name, url=url, enabled=enabled, branch=branch))
			else:
				print(f"Skipping disabled repository: {name}")
		
		return repos
	
	def _get_default_repos(self) -> list[RepoSource]:
		"""Return default repository list including ComposioHQ"""
		return [
			RepoSource(name="agentskills_agentskills", url="https://github.com/agentskills/agentskills.git"),
			RepoSource(name="anthropics_skills", url="https://github.com/anthropics/skills.git"),
			RepoSource(name="huggingface_skills", url="https://github.com/huggingface/skills.git"),
			RepoSource(name="composio_awesome_skills", url="https://github.com/ComposioHQ/awesome-claude-skills.git"),
		]


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
	
	# Initialize progress reporter
	progress = ProgressReporter(dry_run=dry_run)
	progress.start_import(len(repos))

	if clean and import_dir.exists() and not dry_run:
		print("🧹 Cleaning existing imported skills...")
		shutil.rmtree(import_dir)

	total_count = 0
	for i, repo in enumerate(repos, 1):
		progress.start_repo(repo.name, i)
		
		try:
			repo_root = sources_dir / repo.name
			
			# Handle repository cloning/updating
			if clone:
				try:
					progress.report_clone_step(repo.name)
					repo_root = _ensure_repo_cloned(repo, sources_dir=sources_dir, update=update)
				except Exception as e:
					if not progress.report_repo_error(repo.name, e, "clone"):
						break  # Stop if error handler says not to continue
					continue

			# Check if repository exists
			if not repo_root.exists():
				error = FileNotFoundError(f"Repository directory not found: {repo_root}")
				if not progress.report_repo_error(repo.name, error, "check_exists"):
					break
				continue

			progress.report_scan_step(repo.name)
			
			dest_root = import_dir / repo.name
			seen_dirs: set[Path] = set()
			repo_skill_count = 0
			
			# Process skills in repository
			try:
				for skill_md in repo_root.rglob("SKILL.md"):
					src_skill_dir = skill_md.parent
					if src_skill_dir in seen_dirs:
						continue
					seen_dirs.add(src_skill_dir)
					
					try:
						if dry_run:
							rel = src_skill_dir.relative_to(repo_root)
							print(f"    📄 {rel.as_posix()}")
						else:
							_copy_skill_folder(src_skill_dir, repo_root=repo_root, dest_root=dest_root)
						
						repo_skill_count += 1
						
					except Exception as e:
						# Handle individual skill errors but continue with other skills
						rel_path = src_skill_dir.relative_to(repo_root) if repo_root in src_skill_dir.parents else src_skill_dir
						progress.report_skill_error(repo.name, str(rel_path), e)
						continue
				
				progress.report_skills(repo.name, repo_skill_count)
				progress.report_repo_success(repo.name, repo_skill_count)
				total_count += repo_skill_count
				
			except Exception as e:
				# Handle repository-level scanning errors
				if not progress.report_repo_error(repo.name, e, "scan"):
					break
				continue
			
		except KeyboardInterrupt:
			# Handle user interruption
			print(f"\n\n⚠️  Import interrupted by user")
			raise
		except Exception as e:
			# Handle any other unexpected errors
			if not progress.report_repo_error(repo.name, e, "unknown"):
				break
			continue

	progress.final_summary()
	return total_count


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
	parser.add_argument("--config", type=str, help="path to configuration file (YAML or JSON)")
	args = parser.parse_args()

	# Load repositories from configuration file or use defaults
	config_loader = ConfigLoader()
	repos = config_loader.load_config(args.config)
	
	# Filter repositories if --only is specified
	if args.only:
		allowed = set(args.only)
		repos = [r for r in repos if r.name in allowed]
		print(f"Filtering to only process: {', '.join(args.only)}")

	project_root = Path.cwd()
	try:
		import_skills(
			repos=repos,
			project_root=project_root,
			update=not args.no_update,
			clean=args.clean,
			clone=not args.no_clone,
			dry_run=args.dry_run,
		)
	except KeyboardInterrupt:
		print("\n\n⚠️  Import interrupted by user")
		sys.exit(1)
	except Exception as exc:
		print(f"\n❌ Fatal error: {exc}", file=sys.stderr)
		sys.exit(1)


if __name__ == "__main__":
	main()

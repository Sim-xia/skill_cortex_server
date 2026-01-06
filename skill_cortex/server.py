from __future__ import annotations

import logging
import sys
import threading
import time
from pathlib import Path

from skill_cortex.config import AppConfig, load_config
from skill_cortex.frontmatter import normalize_tags
from skill_cortex.index_store import load_index, save_index
from skill_cortex.scanner import scan_skills
from skill_cortex.tags_registry import TagsRegistry, load_tags_registry


_logger = logging.getLogger("skill_cortex")


def _setup_logging() -> None:
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s %(levelname)s %(name)s: %(message)s",
    )


def _not_implemented(name: str) -> dict:
    return {
        "ok": False,
        "error": "not_implemented",
        "tool": name,
    }


def _ensure_parent_dir(path: Path) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)


def _ensure_state_loaded(
    config: AppConfig,
    state: dict[str, object],
    state_lock: threading.Lock,
) -> None:
    with state_lock:
        if state.get("registry") is not None and state.get("scan") is not None:
            return

        start = time.perf_counter()
        registry = load_tags_registry(config.tags_path)
        scan = load_index(config.cache_path)
        if scan is None:
            scan = scan_skills(config.roots, tags_registry=registry)
            save_index(config.cache_path, scan)

        state["registry"] = registry
        state["scan"] = scan
        duration = time.perf_counter() - start
        _logger.info("Index ready in %.2fs (skills=%s)", duration, len(scan.skills))


def _parse_path_arg(path: str | None) -> tuple[str, ...]:
    if not path:
        return ()
    return tuple(p for p in path.split("/") if p)


def _find_node(tree, path: tuple[str, ...]):
    node = tree
    for part in path:
        node = node.children.get(part)
        if node is None:
            return None
    return node


def _summarize_skill(skill) -> dict:
    return {
        "skill_id": skill.skill_id,
        "title": skill.frontmatter.title,
        "description_snapshot": skill.description_snapshot,
        "tags": list(skill.frontmatter.tags),
        "tag_issues": list(skill.tag_issues),
        "category_path": list(skill.category_path),
    }


def _format_tags_inline(tags: tuple[str, ...]) -> str:
    return "[" + ", ".join(tags) + "]"


def _update_tags_in_skill_md(skill_md_path: Path, new_tags: tuple[str, ...]) -> None:
    text = skill_md_path.read_text(encoding="utf-8")
    lines = text.splitlines(keepends=True)
    if not lines:
        raise ValueError("empty_file")
    if lines[0].strip() != "---":
        raise ValueError("missing_frontmatter")

    end_index = None
    for i in range(1, len(lines)):
        if lines[i].strip() == "---":
            end_index = i
            break
    if end_index is None:
        raise ValueError("unterminated_frontmatter")

    open_delim = lines[0]
    front = lines[1:end_index]
    close_delim = lines[end_index]
    body = lines[end_index + 1 :]

    new_tags_line = "tags: " + _format_tags_inline(new_tags) + "\n"
    found = False
    updated_front: list[str] = []
    for raw in front:
        if raw.lstrip().lower().startswith("tags:"):
            updated_front.append(new_tags_line)
            found = True
            continue
        updated_front.append(raw)
    if not found:
        updated_front.append(new_tags_line)

    skill_md_path.write_text(
        open_delim + "".join(updated_front) + close_delim + "".join(body),
        encoding="utf-8",
    )


def main() -> None:
    _setup_logging()
    try:
        sys.stdout.reconfigure(line_buffering=True, write_through=True)
    except Exception:
        pass

    try:
        sys.stderr.reconfigure(line_buffering=True, write_through=True)
    except Exception:
        pass

    config = load_config()
    _logger.info("Starting Skill-Cortex (Lite)")
    _logger.info("roots=%s", ",".join(str(p) for p in config.roots))
    _logger.info("cache_path=%s", str(config.cache_path))
    _logger.info("tags_path=%s", str(config.tags_path))

    try:
        from mcp.server.fastmcp import FastMCP
    except Exception as exc:
        _logger.error("Missing dependency 'mcp': %s", exc)
        print(
            "Missing dependency 'mcp'. Install dependencies first, e.g. `pip install -e .`\n"
            + f"Import error: {exc}",
            file=sys.stderr,
        )
        raise

    mcp = FastMCP("skill-cortex-lite")

    state_lock = threading.Lock()
    state: dict[str, object] = {
        "registry": None,
        "scan": None,
    }

    @mcp.tool()
    def list_skill_tree(path: str | None = None) -> dict:
        _ensure_state_loaded(config, state, state_lock)
        parts = _parse_path_arg(path)
        node = _find_node(state["scan"].tree, parts)
        if node is None:
            return {"ok": False, "error": "path_not_found", "path": list(parts)}
        return {
            "ok": True,
            "path": list(parts),
            "categories": sorted(node.children.keys()),
            "skills": [_summarize_skill(s) for s in node.skills],
        }

    @mcp.tool()
    def search_skills(query: str | None = None, tags: list[str] | None = None) -> dict:
        _ensure_state_loaded(config, state, state_lock)
        q = (query or "").strip().lower()
        filter_tags = normalize_tags(tags or [])
        results = []
        for s in state["scan"].skills:
            if q:
                hay = " ".join(
                    [
                        s.skill_id,
                        s.frontmatter.title,
                        s.description_snapshot,
                        "/".join(s.category_path),
                    ]
                ).lower()
                if q not in hay:
                    continue
            if filter_tags:
                if not set(filter_tags).issubset(set(s.frontmatter.tags)):
                    continue
            results.append(_summarize_skill(s))
        return {"ok": True, "count": len(results), "results": results}

    @mcp.tool()
    def get_skill_details(skill_id: str) -> dict:
        _ensure_state_loaded(config, state, state_lock)
        for s in state["scan"].skills:
            if s.skill_id == skill_id:
                return {
                    "ok": True,
                    "skill_id": s.skill_id,
                    "content": s.skill_path.read_text(encoding="utf-8"),
                }
        return {"ok": False, "error": "skill_not_found", "skill_id": skill_id}

    @mcp.tool()
    def update_tags(mode: str = "list", updates: list[dict] | None = None) -> dict:
        _ensure_state_loaded(config, state, state_lock)
        m = (mode or "list").strip().lower()
        if m == "list":
            bad = [s for s in state["scan"].skills if s.tag_issues]
            return {"ok": True, "count": len(bad), "skills": [_summarize_skill(s) for s in bad]}

        if m != "apply":
            return {"ok": False, "error": "invalid_mode", "mode": mode}

        if not updates:
            return {"ok": False, "error": "missing_updates"}

        allowed = state["registry"].allowed_tags
        results = []
        for upd in updates:
            skill_id = str(upd.get("skill_id", "")).strip()
            tags_tuple = normalize_tags(upd.get("tags", []))
            if not skill_id:
                results.append({"ok": False, "error": "missing_skill_id"})
                continue
            if not tags_tuple:
                results.append({"ok": False, "skill_id": skill_id, "error": "missing_tags"})
                continue
            invalid = [t for t in tags_tuple if t not in allowed]
            if invalid:
                results.append({"ok": False, "skill_id": skill_id, "error": "invalid_tags", "invalid": invalid})
                continue

            skill = next((s for s in state["scan"].skills if s.skill_id == skill_id), None)
            if skill is None:
                results.append({"ok": False, "skill_id": skill_id, "error": "skill_not_found"})
                continue

            try:
                _update_tags_in_skill_md(skill.skill_path, tags_tuple)
                results.append({"ok": True, "skill_id": skill_id, "tags": list(tags_tuple)})
            except Exception as exc:
                results.append({"ok": False, "skill_id": skill_id, "error": "write_failed", "detail": str(exc)})

        state["scan"] = scan_skills(config.roots, tags_registry=state["registry"])
        save_index(config.cache_path, state["scan"])
        return {"ok": True, "results": results}

    mcp.run()


if __name__ == "__main__":
    main()

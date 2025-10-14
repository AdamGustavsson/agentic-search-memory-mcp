# memory_server.py
from __future__ import annotations

import os
import json
import shutil
import itertools
from pathlib import Path
from typing import Literal, Annotated, Optional

from fastmcp import FastMCP, Context
from pydantic import Field

# ----------------------------
# Configuration
# ----------------------------
MEM_ROOT = Path(os.getenv("MEMORY_DIR", "./memories")).resolve()
MEM_ROOT.mkdir(parents=True, exist_ok=True)

# Do not blast huge files into context; Claude docs suggest pagination/limits.
# You can override via env var.
MAX_READ_CHARS = int(os.getenv("MEMORY_MAX_READ_CHARS", "20000"))

# Maximum response size for tool outputs - high limit for safety, use pagination for large files
MAX_RESPONSE_CHARS = int(os.getenv("MEMORY_MAX_RESPONSE_CHARS", "50000"))

# Warn when files exceed this size (to encourage pagination)
LARGE_FILE_WARNING_THRESHOLD = int(os.getenv("MEMORY_LARGE_FILE_THRESHOLD", "10000"))

# Co-visitation tracking for associative memory
COVIS_INDEX_NAME = "_covis.json"
COVIS_MAX_RECOMMENDATIONS = int(os.getenv("MEMORY_COVIS_MAX_RECOMMENDATIONS", "3"))


mcp = FastMCP(name="Memory MCP Server")

# ----------------------------
# Co-visitation Index (Associative Memory)
# ----------------------------
# Track which files are viewed together to provide context-aware recommendations

def _covis_index_path() -> Path:
    """Get path to co-visitation index file."""
    return MEM_ROOT / COVIS_INDEX_NAME


def _load_covis_index() -> dict:
    """Load co-visitation index from disk."""
    try:
        with open(_covis_index_path(), "r", encoding="utf-8") as f:
            return json.load(f)
    except FileNotFoundError:
        return {}
    except (json.JSONDecodeError, ValueError) as e:
        # Corrupted JSON file - reset it
        print(f"Warning: Corrupted co-visitation index, resetting: {e}")
        return {}


def _save_covis_index(idx: dict):
    """Save co-visitation index to disk atomically."""
    tmp_path = _covis_index_path().with_suffix(".json.tmp")
    with open(tmp_path, "w", encoding="utf-8") as f:
        json.dump(idx, f, ensure_ascii=False, indent=2)
    tmp_path.replace(_covis_index_path())


# Session tracking: maps session_id -> list of file paths accessed
_session_files: dict[str, list[str]] = {}

# Cleanup old sessions periodically to prevent memory buildup
_session_access_count = 0
_SESSION_CLEANUP_THRESHOLD = 100  # Cleanup after N file accesses


def _cleanup_old_sessions():
    """
    Clean up old session data to prevent memory buildup.
    Keeps only the most recent sessions based on a simple threshold.
    """
    if len(_session_files) > 50:  # Keep max 50 sessions in memory
        # Keep the 30 most recently updated sessions
        # (Simple heuristic: sessions with more files are likely more recent)
        sorted_sessions = sorted(
            _session_files.items(), 
            key=lambda x: len(x[1]), 
            reverse=True
        )
        _session_files.clear()
        for session_id, files in sorted_sessions[:30]:
            _session_files[session_id] = files


def _record_file_access(file_path: Path, session_id: str):
    """
    Record that a file was accessed in a specific session.
    Tracks which files are viewed together within the same MCP session.
    
    Args:
        file_path: Path to the file being accessed
        session_id: MCP session ID from Context
    """
    global _session_access_count
    
    # Skip tracking internal implementation files
    if file_path.name.startswith("_") or file_path.name.startswith("."):
        return
    
    if session_id not in _session_files:
        _session_files[session_id] = []
    
    # Store as relative path for portability
    try:
        file_str = str(file_path.relative_to(MEM_ROOT))
    except ValueError:
        # Fall back to absolute if not under MEM_ROOT
        file_str = str(file_path)
    
    if file_str not in _session_files[session_id]:
        _session_files[session_id].append(file_str)
    
    # Update co-visitation index periodically (when we have 2+ files)
    if len(_session_files[session_id]) >= 2:
        _update_covis_for_session(_session_files[session_id])
    
    # Periodic cleanup to prevent memory buildup
    _session_access_count += 1
    if _session_access_count >= _SESSION_CLEANUP_THRESHOLD:
        _cleanup_old_sessions()
        _session_access_count = 0


def _update_covis_for_session(files: list[str]):
    """
    Update co-visitation index based on files accessed together in a session.
    Only records pairs of actual files (not directories).
    Stores paths relative to MEM_ROOT for portability.
    
    Args:
        files: List of file paths (relative to MEM_ROOT) accessed in the same session
    """
    if len(files) < 2:
        return
    
    idx = _load_covis_index()
    
    # Get unique files that still exist
    unique_files = []
    seen = set()
    for f in files:
        # Convert relative path back to absolute for validation
        abs_path = MEM_ROOT / f if not Path(f).is_absolute() else Path(f)
        if f not in seen and abs_path.is_file():
            unique_files.append(f)
            seen.add(f)
    
    if len(unique_files) < 2:
        return
    
    # Record co-visitation for all pairs (using relative paths)
    for a, b in itertools.combinations(unique_files, 2):
        idx.setdefault(a, {}).setdefault(b, 0)
        idx[a][b] += 1
        idx.setdefault(b, {}).setdefault(a, 0)
        idx[b][a] += 1
    
    _save_covis_index(idx)


def _get_related_files(file_path: Path, session_id: str, max_count: int = COVIS_MAX_RECOMMENDATIONS) -> list[dict]:
    """
    Get files that have been co-visited with the given file.
    Excludes files already viewed in the current session.
    Returns list of {'file': path_str, 'count': int}
    """
    if not file_path.is_file():
        return []
    
    idx = _load_covis_index()
    
    # Convert file_path to relative path for lookup
    try:
        file_str = str(file_path.relative_to(MEM_ROOT))
    except ValueError:
        file_str = str(file_path)
    
    neighbors = idx.get(file_str, {})
    
    # Get files already viewed in this session (to exclude them)
    session_viewed = set(_session_files.get(session_id, []))
    
    # Keep only neighbors that:
    # 1. Still exist as files
    # 2. Haven't been viewed in this session yet
    # 3. Are not internal implementation files
    valid_neighbors = {}
    for p, c in neighbors.items():
        # Skip internal implementation files
        file_name = Path(p).name
        if file_name.startswith("_") or file_name.startswith("."):
            continue
            
        # Skip if already viewed in this session
        if p in session_viewed:
            continue
            
        # Validate file exists
        abs_path = MEM_ROOT / p if not Path(p).is_absolute() else Path(p)
        if abs_path.is_file():
            valid_neighbors[p] = c
    
    # Sort by co-visitation count (descending), then by path
    top = sorted(valid_neighbors.items(), key=lambda t: (-t[1], t[0]))[:max_count]
    
    # Return just the file paths and counts (no content loading)
    results = []
    for path_str, count in top:
        results.append({
            "file": path_str,
            "count": count
        })
    
    return results

# ----------------------------
# Helpers
# ----------------------------
def _normalize_incoming_path(p: Optional[str]) -> Path:
    """
    Normalizes incoming path and ensures it's within MEM_ROOT for security.
    Returns a resolved Path object.
    """
    if p is None or p.strip() == "":
        return MEM_ROOT

    rel = p.strip()
    candidate = (MEM_ROOT / rel).resolve()
    
    # Path traversal protection: must stay within MEM_ROOT
    try:
        candidate.relative_to(MEM_ROOT)
    except Exception:
        raise ValueError("Invalid path: path traversal not allowed")

    return candidate


def _ensure_parent_dirs(path: Path):
    path.parent.mkdir(parents=True, exist_ok=True)


def _read_file(path: Path, start_line: Optional[int], end_line: Optional[int]) -> str:
    text = path.read_text(encoding="utf-8", errors="replace")
    if start_line or end_line:
        # 1-based inclusive range
        lines = text.splitlines(keepends=True)
        s = 1 if start_line is None else max(1, start_line)
        e = len(lines) if end_line is None else min(len(lines), end_line)
        if s > e:
            return ""
        text = "".join(lines[s - 1 : e])

    if len(text) > MAX_READ_CHARS:
        text = text[:MAX_READ_CHARS] + f"\n…(truncated to {MAX_READ_CHARS} chars)"
    return text


def _truncate_response(text: str, max_chars: int = MAX_RESPONSE_CHARS) -> str:
    """Truncate response text to keep it concise."""
    if len(text) <= max_chars:
        return text
    
    # Count total lines for helpful context
    total_lines = text.count('\n') + 1
    truncated_lines = text[:max_chars].count('\n') + 1
    
    return (text[:max_chars] + 
            f"\n…(truncated to {max_chars:,} chars, showing ~{truncated_lines}/{total_lines} lines)\n"
            f"💡 TIP: Use start_line/end_line parameters to view specific sections of large files.")


def _list_dir(path: Path) -> str:
    """Return simple directory listing as formatted string."""
    items = []
    for p in sorted(path.iterdir(), key=lambda x: (x.is_file(), x.name.lower())):
        # Skip hidden files and internal implementation files
        if p.name.startswith(".") or p.name.startswith("_"):
            continue
        items.append(f"{p.name}/" if p.is_dir() else p.name)
    
    display_path = "." if path == MEM_ROOT else path.relative_to(MEM_ROOT).as_posix()
    if not items:
        return f"Directory: {display_path}\n(empty)"
    
    return f"Directory: {display_path}\n" + "\n".join([f"- {item}" for item in items])


def _build_tree(path: Path, indent: int = 0) -> list[str]:
    """
    Build a recursive tree structure with 1-space indentation.
    Returns a list of lines representing the tree.
    """
    lines = []
    
    try:
        items = sorted(path.iterdir(), key=lambda x: (x.is_file(), x.name.lower()))
        
        for item in items:
            # Skip hidden files and internal implementation files
            if item.name.startswith(".") or item.name.startswith("_"):
                continue
            
            # Add current item with proper indentation
            prefix = " " * indent
            if item.is_dir():
                lines.append(f"{prefix}{item.name}/")
                # Recursively add subdirectory contents
                lines.extend(_build_tree(item, indent + 1))
            else:
                lines.append(f"{prefix}{item.name}")
    except Exception:
        pass  # Skip inaccessible items
    
    return lines


# ----------------------------
# Individual Memory Tools
# ----------------------------

@mcp.tool(
    name="view",
    annotations={
        "title": "View memory content",
        "readOnlyHint": True,
        "openWorldHint": False,
    },
)
def view(
    path: Annotated[str, Field(description="Target path (e.g. 'notes.txt')")] = None,
    start_line: Annotated[int, Field(description="Start line (0-based)")] = None,
    end_line: Annotated[int, Field(description="End line (0-based, inclusive)")] = None,
    ctx: Context | None = None,
) -> str:
    """View memory directory listing or file contents with optional line range."""
    target = _normalize_incoming_path(path)
    
    # Prevent viewing internal implementation files
    if target != MEM_ROOT and (target.name.startswith("_") or target.name.startswith(".")):
        raise RuntimeError(f"Cannot access internal file: {path}")
    
    if not target.exists():
        raise RuntimeError(f"Path not found: {path or '.'}")
    
    if target.is_dir():
        try:
            # Build full tree structure with 1-space indentation
            tree_lines = _build_tree(target, indent=0)
            
            if not tree_lines:  # Empty directory
                result = "(empty)"
            else:
                result = "\n".join(tree_lines)
            
            return _truncate_response(result)
        except Exception as e:
            raise RuntimeError(f"Cannot read directory {path or '.'}: {e}") from e
    
    elif target.is_file():
        try:
            # Record this file access for co-visitation tracking (if Context provided)
            if ctx is not None:
                _record_file_access(target, ctx.session_id)
            
            # Read primary file content
            content = target.read_text(encoding="utf-8")
            lines = content.splitlines()
            
            if start_line is not None or end_line is not None:
                # Use 0-based indexing
                start_idx = start_line if start_line is not None else 0
                end_idx = (end_line + 1) if end_line is not None else len(lines)
                lines = lines[start_idx:end_idx]
            
            result = "\n".join(lines)
            
            # Get related files (associative memory) - exclude files already viewed in this session
            related_files = _get_related_files(target, ctx.session_id) if ctx else []
            
            # Append related files section if any exist
            if related_files:
                result += "\n\n"
                result += "🧠 RELATED FILES (Associative Memory)\n"
                
                for i, related in enumerate(related_files, 1):
                    result += f"  [{i}] {related['file']} (co-visited {related['count']}x)\n"
            
            return _truncate_response(result)
        except Exception as e:
            raise RuntimeError(f"Cannot read file {path}: {e}") from e
    
    else:
        raise RuntimeError(f"Path not found: {path or '.'}")


@mcp.tool(
    name="create",
    annotations={
        "title": "Create or overwrite memory file",
        "readOnlyHint": False,
        "openWorldHint": False,
    },
)
def create(
    path: Annotated[
        str,
        Field(description="Target file path (e.g. 'notes.txt').")
    ],
    file_text: Annotated[
        str, Field(description="File content to write.")
    ] = "",
    ctx: Context | None = None,
) -> str:
    """Create a new memory file or overwrite an existing one."""
    target = _normalize_incoming_path(path)
    
    # Prevent creating internal implementation files
    if target.name.startswith("_") or target.name.startswith("."):
        raise RuntimeError(f"Cannot create internal file: {path}")
    
    _ensure_parent_dirs(target)
    target.write_text(file_text, encoding="utf-8")
    
    # Record this file access for co-visitation tracking (if Context provided)
    # Creating a file after viewing others suggests they're related
    if ctx is not None:
        _record_file_access(target, ctx.session_id)
    
    # Warn about large files
    file_size = len(file_text)
    if file_size > LARGE_FILE_WARNING_THRESHOLD:
        lines = file_text.count('\n') + 1
        return (f"Created: {path}\n"
                f"⚠️ WARNING: Large file created ({file_size:,} chars, ~{lines} lines). "
                f"Consider using start_line/end_line when viewing to avoid truncation.")
    
    return f"Created: {path}"


@mcp.tool(
    name="str_replace",
    annotations={
        "title": "Replace text in memory file",
        "readOnlyHint": False,
        "openWorldHint": False,
    },
)
def str_replace(
    path: Annotated[
        str,
        Field(description="Target file path (e.g. 'notes.txt').")
    ],
    old_str: Annotated[
        str, Field(description="Old substring to replace.")
    ],
    new_str: Annotated[
        str, Field(description="New substring to replace with.")
    ],
    ctx: Context | None = None,
) -> str:
    """Replace all occurrences of old_str with new_str in a memory file."""
    target = _normalize_incoming_path(path)
    
    # Prevent editing internal implementation files
    if target.name.startswith("_") or target.name.startswith("."):
        raise RuntimeError(f"Cannot edit internal file: {path}")
    
    if not target.is_file():
        raise FileNotFoundError(f"File not found: {path}")
    
    content = target.read_text(encoding="utf-8")
    count = content.count(old_str)
    
    if count == 0:
        raise ValueError(f"Text not found in {path}")
    elif count > 1:
        raise ValueError(f"Text appears {count} times in {path}. Must be unique.")
    
    new_content = content.replace(old_str, new_str)
    target.write_text(new_content, encoding="utf-8")
    
    # Record this file access for co-visitation tracking (if Context provided)
    # Editing a file after viewing others suggests they're related
    if ctx is not None:
        _record_file_access(target, ctx.session_id)
    
    # Warn about large files after edit
    file_size = len(new_content)
    if file_size > LARGE_FILE_WARNING_THRESHOLD:
        lines = new_content.count('\n') + 1
        return (f"Updated: {path}\n"
                f"⚠️ WARNING: File is now large ({file_size:,} chars, ~{lines} lines). "
                f"Consider using start_line/end_line when viewing to avoid truncation.")
    
    return f"Updated: {path}"


@mcp.tool(
    name="insert",
    annotations={
        "title": "Insert text into memory file",
        "readOnlyHint": False,
        "openWorldHint": False,
    },
)
def insert(
    path: Annotated[
        str,
        Field(description="Target file path (e.g. 'notes.txt').")
    ],
    insert_line: Annotated[
        int, Field(ge=0, description="0-based line index to insert at.")
    ],
    insert_text: Annotated[
        str, Field(description="Text to insert.")
    ],
    ctx: Context | None = None,
) -> str:
    """Insert text at a specific line in a memory file using 0-based indexing."""
    target = _normalize_incoming_path(path)
    
    # Prevent editing internal implementation files
    if target.name.startswith("_") or target.name.startswith("."):
        raise RuntimeError(f"Cannot edit internal file: {path}")
    
    if not target.is_file():
        raise FileNotFoundError(f"File not found: {path}")
    
    lines = target.read_text(encoding="utf-8").splitlines()
    
    if insert_line < 0 or insert_line > len(lines):
        raise ValueError(f"Invalid insert_line {insert_line}. Must be 0-{len(lines)}")
    
    lines.insert(insert_line, insert_text.rstrip("\n"))
    new_content = "\n".join(lines) + "\n"
    target.write_text(new_content, encoding="utf-8")
    
    # Record this file access for co-visitation tracking (if Context provided)
    # Editing a file after viewing others suggests they're related
    if ctx is not None:
        _record_file_access(target, ctx.session_id)
    
    # Warn about large files after insert
    file_size = len(new_content)
    if file_size > LARGE_FILE_WARNING_THRESHOLD:
        total_lines = len(lines)
        return (f"Inserted at line {insert_line}: {path}\n"
                f"⚠️ WARNING: File is now large ({file_size:,} chars, ~{total_lines} lines). "
                f"Consider refactoring the file to reduce size.")
    
    return f"Inserted at line {insert_line}: {path}"


@mcp.tool(
    name="delete",
    annotations={
        "title": "Delete memory file or directory",
        "readOnlyHint": False,
        "openWorldHint": False,
        "destructive_hint": True,
    },
)
def delete(
    path: Annotated[
        str,
        Field(description="Target path to delete (e.g. 'notes.txt' or 'folder'). Directories are deleted recursively.")
    ],
    ctx: Context | None = None,
) -> str:
    """Delete a memory file or directory (recursively for directories)."""
    target = _normalize_incoming_path(path)
    
    # Prevent deletion of internal implementation files
    if target.name.startswith("_") or target.name.startswith("."):
        raise RuntimeError(f"Cannot delete internal file: {path}")
    
    # Prevent deletion of root memory directory
    if target == MEM_ROOT:
        raise ValueError("Cannot delete the memory directory itself")
    
    if target.is_file():
        target.unlink()
        return f"Deleted: {path}"
    elif target.is_dir():
        shutil.rmtree(target)
        return f"Deleted: {path}"
    else:
        raise FileNotFoundError(f"Path not found: {path}")


@mcp.tool(
    name="rename",
    annotations={
        "title": "Rename or move memory file/directory",
        "readOnlyHint": False,
        "openWorldHint": False,
    },
)
def rename(
    old_path: Annotated[
        str,
        Field(description="Source path to rename/move (e.g. 'old_notes.txt').")
    ],
    new_path: Annotated[
        str,
        Field(description="Destination path (e.g. 'new_notes.txt').")
    ],
    ctx: Context | None = None,
) -> str:
    """Rename or move a memory file or directory."""
    src = _normalize_incoming_path(old_path)
    dst = _normalize_incoming_path(new_path)
    
    # Prevent renaming internal implementation files
    if src.name.startswith("_") or src.name.startswith("."):
        raise RuntimeError(f"Cannot rename internal file: {old_path}")
    
    if dst.name.startswith("_") or dst.name.startswith("."):
        raise RuntimeError(f"Cannot rename to internal file: {new_path}")
    
    if not src.exists():
        raise FileNotFoundError(f"Source path not found: {old_path}")
    
    if dst.exists():
        raise ValueError(f"Destination already exists: {new_path}")
    
    _ensure_parent_dirs(dst)
    src.rename(dst)
    
    return f"Renamed: {old_path} → {new_path}"


@mcp.tool(
    name="clear_all_memory",
    annotations={
        "title": "Clear all memory",
        "readOnlyHint": False,
        "openWorldHint": False,
        "destructive_hint": True,
    },
)
def clear_all_memory(
    ctx: Context | None = None,
) -> str:
    """Clear all memory files and directories."""
    if MEM_ROOT.exists():
        shutil.rmtree(MEM_ROOT)
    MEM_ROOT.mkdir(parents=True, exist_ok=True)
    return "Cleared all memory"


# ----------------------------
# Entrypoint
# ----------------------------
if __name__ == "__main__":
    # Default to stdio; switch to HTTP with: mcp.run(transport="http", host="127.0.0.1", port=8000)
    mcp.run()
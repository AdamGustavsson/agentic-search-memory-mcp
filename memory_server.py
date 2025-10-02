# memory_server.py
from __future__ import annotations

import os
import shutil
from pathlib import Path
from typing import Literal, Annotated, Optional

from fastmcp import FastMCP, Context
from fastmcp.resources import DirectoryResource
from pydantic import Field

# ----------------------------
# Configuration
# ----------------------------
MEM_ROOT = Path(os.getenv("MEMORY_DIR", "./memories")).resolve()
MEM_ROOT.mkdir(parents=True, exist_ok=True)

# Do not blast huge files into context; Claude docs suggest pagination/limits.
# You can override via env var.
MAX_READ_CHARS = int(os.getenv("MEMORY_MAX_READ_CHARS", "20000"))

# Maximum response size for tool outputs to keep responses concise
MAX_RESPONSE_CHARS = int(os.getenv("MEMORY_MAX_RESPONSE_CHARS", "5000"))


mcp = FastMCP(name="Memory MCP Server")

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
    return text[:max_chars] + f"\n…(truncated to {max_chars} chars)"


def _list_dir(path: Path) -> str:
    """Return simple directory listing as formatted string."""
    items = []
    for p in sorted(path.iterdir(), key=lambda x: (x.is_file(), x.name.lower())):
        if p.name.startswith("."):
            continue
        items.append(f"{p.name}/" if p.is_dir() else p.name)
    
    display_path = "." if path == MEM_ROOT else path.relative_to(MEM_ROOT).as_posix()
    if not items:
        return f"Directory: {display_path}\n(empty)"
    
    return f"Directory: {display_path}\n" + "\n".join([f"- {item}" for item in items])


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
    path: Annotated[
        Optional[str],
        Field(
            default=None,
            description="Target path (e.g. 'notes.txt' or directory path). Defaults to root memory directory."
        ),
    ] = None,
    start_line: Annotated[
        Optional[int], Field(default=None, ge=0, description="0-based start line (inclusive) for file viewing. Note: Line numbers in output are for display only and not part of the actual file content.")
    ] = None,
    end_line: Annotated[
        Optional[int], Field(default=None, ge=0, description="0-based end line (inclusive) for file viewing. Note: Line numbers in output are for display only and not part of the actual file content.")
    ] = None,
    ctx: Context | None = None,
) -> str:
    """View memory directory listing or file contents with optional line range. Line numbers in output are for display only and not part of the actual file content."""
    target = _normalize_incoming_path(path)
    
    if not target.exists():
        raise RuntimeError(f"Path not found: {path or '.'}")
    
    if target.is_dir():
        try:
            items = []
            for item in sorted(target.iterdir()):
                if item.name.startswith("."):
                    continue
                items.append(f"{item.name}/" if item.is_dir() else item.name)
            
            # Use relative path from MEM_ROOT for display, not the original path parameter
            display_path = target.relative_to(MEM_ROOT).as_posix() if target != MEM_ROOT else "."
            result = f"Directory: {display_path}" + ("\n" if items else "") + "\n".join([f"- {item}" for item in items])
            return _truncate_response(result)
        except Exception as e:
            raise RuntimeError(f"Cannot read directory {path or '.'}: {e}") from e
    
    elif target.is_file():
        try:
            content = target.read_text(encoding="utf-8")
            lines = content.splitlines()
            
            if start_line is not None or end_line is not None:
                start_idx = start_line or 0
                end_idx = len(lines) if end_line is None else end_line + 1
                lines = lines[start_idx:end_idx]
                start_num = start_idx + 1  # For display numbering (1-based)
            else:
                start_num = 1
            
            numbered_lines = [f"{i + start_num:4d}: {line}" for i, line in enumerate(lines)]
            result = "\n".join(numbered_lines)
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
    _ensure_parent_dirs(target)
    target.write_text(file_text, encoding="utf-8")
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
    
    if not target.is_file():
        raise FileNotFoundError(f"File not found: {path}")
    
    lines = target.read_text(encoding="utf-8").splitlines()
    
    if insert_line < 0 or insert_line > len(lines):
        raise ValueError(f"Invalid insert_line {insert_line}. Must be 0-{len(lines)}")
    
    lines.insert(insert_line, insert_text.rstrip("\n"))
    target.write_text("\n".join(lines) + "\n", encoding="utf-8")
    
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
# Resources (MCP Resources Specification)
# ----------------------------

def _get_memory_resources() -> list[dict]:
    """Get list of memory resources conforming to MCP specification."""
    resources = []
    
    # Add root directory resource
    resources.append({
        "uri": "memory://",
        "name": "memories",
        "title": "📁 Memory Directory",
        "description": "Root memory directory containing all stored memories",
        "mimeType": "inode/directory"
    })
    
    # Add individual file resources
    def add_files_recursive(path: Path, base_uri: str = "memory://"):
        try:
            for item in sorted(path.iterdir()):
                if item.name.startswith("."):
                    continue
                    
                if item.is_dir():
                    dir_uri = f"{base_uri}{item.relative_to(MEM_ROOT).as_posix()}/"
                    resources.append({
                        "uri": dir_uri,
                        "name": item.name,
                        "title": f"📁 {item.name}",
                        "description": f"Memory directory: {item.name}",
                        "mimeType": "inode/directory"
                    })
                    add_files_recursive(item, base_uri)
                else:
                    file_uri = f"{base_uri}{item.relative_to(MEM_ROOT).as_posix()}"
                    try:
                        size = item.stat().st_size
                        mime_type = "text/plain"  # Default for memory files
                        if item.suffix:
                            mime_type = f"text/{item.suffix[1:]}" if item.suffix[1:] in ["txt", "md", "json"] else "application/octet-stream"
                    except Exception:
                        size = None
                        mime_type = "application/octet-stream"
                    
                    resources.append({
                        "uri": file_uri,
                        "name": item.name,
                        "title": f"📄 {item.name}",
                        "description": f"Memory file: {item.name}",
                        "mimeType": mime_type,
                        "size": size
                    })
        except Exception:
            pass  # Skip inaccessible items
    
    add_files_recursive(MEM_ROOT)
    return resources


@mcp.resource("memory://")
def memory_root_resource() -> dict:
    """Root memory directory resource."""
    try:
        items = []
        for item in sorted(MEM_ROOT.iterdir()):
            if item.name.startswith("."):
                continue
            items.append(f"{item.name}/" if item.is_dir() else item.name)
        
        content = f"Memory Directory Contents:\n\n"
        if items:
            content += "\n".join([f"- {item}" for item in items])
        else:
            content += "No memory files found."
        
        return {
            "uri": "memory://",
            "name": "memories",
            "title": "📁 Memory Directory",
            "mimeType": "text/plain",
            "text": content
        }
    except Exception as e:
        return {
            "uri": "memory://",
            "name": "memories", 
            "title": "📁 Memory Directory",
            "mimeType": "text/plain",
            "text": f"Error reading memory directory: {e}"
        }


def _register_memory_resources():
    """Register individual memory files as resources."""
    def register_file_resource(file_path: Path):
        uri = f"memory://{file_path.relative_to(MEM_ROOT).as_posix()}"
        
        @mcp.resource(uri)
        def file_resource() -> dict:
            try:
                content = file_path.read_text(encoding="utf-8")
                return {
                    "uri": uri,
                    "name": file_path.name,
                    "title": f"📄 {file_path.name}",
                    "mimeType": "text/plain",
                    "text": content
                }
            except Exception as e:
                return {
                    "uri": uri,
                    "name": file_path.name,
                    "title": f"📄 {file_path.name}",
                    "mimeType": "text/plain", 
                    "text": f"Error reading file: {e}"
                }
    
    def register_files_recursive(path: Path):
        try:
            for item in path.iterdir():
                if item.name.startswith("."):
                    continue
                if item.is_file():
                    register_file_resource(item)
                elif item.is_dir():
                    register_files_recursive(item)
        except Exception:
            pass
    
    register_files_recursive(MEM_ROOT)


# Register all existing memory files as resources
_register_memory_resources()

# ----------------------------
# Entrypoint
# ----------------------------
if __name__ == "__main__":
    # Default to stdio; switch to HTTP with: mcp.run(transport="http", host="127.0.0.1", port=8000)
    mcp.run()
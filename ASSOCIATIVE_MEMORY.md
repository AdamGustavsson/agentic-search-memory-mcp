# Associative Memory (Co-Visitation Tracking)

## Overview

The memory server now includes **associative memory** capabilities inspired by how human brains work. When you view a file, the server automatically shows you related files that have been viewed together in the past.

## How It Works

### 1. **Session Tracking**
- The server uses FastMCP's built-in session IDs to track file accesses
- Files accessed within the same MCP session (client connection) are considered related
- Each session has a unique ID that persists across multiple tool calls
- **Tracks both read AND write operations**: viewing, creating, and editing files

### 2. **Co-Visitation Index**
- A JSON index (`_covis.json`) tracks which files are accessed together
- Every time 2+ files are accessed in a session, their co-visitation count increases
- The index is stored in: `{MEMORY_DIR}/_covis.json`
- **Robust error handling**: Gracefully handles corrupted JSON data

### 3. **Related File Recommendations**
- When you view a file, the server automatically:
  1. Shows the primary file content
  2. Finds up to 3 related files (configurable)
  3. Lists related file paths (agent must explicitly view to access content)

## Example Output

### Viewing a File with Related Files

```
   1: # My Notes
   2: This is the main content
   3: ...

🧠 RELATED FILES (Associative Memory)
  [1] patterns/similar_topic.md (co-visited 5x)
  [2] accounts/context.txt (co-visited 3x)
```

The agent can then explicitly view any related file to access its content.

### Viewing a Directory (Tree View)

```
docs/
 README.md
src/
 util/
  io.py
  math.py
 main.py
LICENSE
```

Directories are shown as a full recursive tree with 1-space indentation.

## Configuration

Control associative memory behavior via environment variables:

```bash
# Maximum number of related files to show (default: 3)
export MEMORY_COVIS_MAX_RECOMMENDATIONS=5
```

## Benefits

1. **Contextual Awareness**: Automatically surfaces related files when viewing content
2. **Pattern Recognition**: Learns from both viewing and writing patterns over time
3. **Reduced Search Time**: Suggests relevant files without needing to search
4. **Inter-Session Memory**: Recommendations persist across different sessions
5. **Non-Invasive Measurement**: Showing paths (not content) preserves the viewing behavior being measured
6. **Write Operation Tracking**: Creating/editing files after viewing others establishes relationships

## Privacy & Storage

- The co-visitation index only stores file paths and counts
- No file content is stored in the index
- The index is stored locally in your memory directory
- File paths are normalized to prevent path traversal attacks

## Technical Details

### Co-Visitation Algorithm

For each session with file operations [view A, view B, create C]:
- Record pairs: (A,B), (A,C), (B,C)
- Increment co-visitation count for each pair
- Store bidirectional relationships
- **All operations count**: `view()`, `create()`, `str_replace()`, `insert()`

### Recommendation Ranking

Files are ranked by:
1. Co-visitation count (higher = more related)
2. File path (alphabetical tiebreaker)

### Session Definition

A "session" is defined by the **FastMCP session ID**:
- Each MCP client connection has a unique session ID (via `Context.session_id`)
- Files accessed within the same session are tracked together
- Session persists across multiple tool calls
- Co-visitation updated after each file access (if 2+ files in session)
- Old session data is cleaned up periodically to prevent memory buildup

### Tracked Operations

**Read operations:**
- `view()` - Viewing file content

**Write operations:**
- `create()` - Creating new files (tracks relationship with previously viewed files)
- `str_replace()` - Editing file content (indicates working with related concepts)
- `insert()` - Inserting into files (indicates working with related concepts)

**Rationale:** If you view files A and B, then create file C, file C is likely conceptually related to A and B. The same logic applies to editing operations.

## Implementation Notes

Based on the reference implementation provided, with adaptations for:
- **FastMCP session tracking**: Uses `Context.session_id` for proper session management
- **Path security**: Normalization and traversal protection
- **Response truncation**: Optimal token usage
- **Atomic file writes**: Index persistence
- **Memory management**: Automatic cleanup of old session data
- **Error resilience**: Gracefully handles corrupted JSON index files

### Key Improvements Over Reference Implementation

1. **True Session Tracking**: Uses FastMCP's built-in `session_id` instead of a sliding window
2. **Persistent Sessions**: Session data persists across multiple tool calls within the same MCP connection
3. **Automatic Cleanup**: Prevents memory buildup by cleaning old sessions after 100 file accesses
4. **Context-Aware**: Leverages FastMCP Context for session identification
5. **MCP Protocol Compliant**: Follows official MCP recommendations for session management
6. **Non-Invasive Recommendations**: Shows file paths only (not content) to prevent measurement plateau

### Why Path-Only Recommendations?

The system shows **paths without content** for related files. This design prevents the "plateau problem":

- **With inline content**: Once files are recommended together, agents stop explicitly viewing them → co-visitation count plateaus → can't distinguish strong vs weak associations
- **With path-only**: Agents must explicitly view truly useful files → co-visitation continues to grow for strong associations → weak associations naturally decay

This preserves the intentionality of file access and allows the system to learn which associations are genuinely useful over time.

### MCP Protocol Alignment

According to the **Model Context Protocol specification**:
- Sessions maintain continuity across related interactions
- Session IDs group requests within the same "conversation"
- Servers should maintain context for requests with the same session ID

Our implementation correctly uses session IDs to identify which file accesses are contextually related, following MCP's intended purpose for sessions.


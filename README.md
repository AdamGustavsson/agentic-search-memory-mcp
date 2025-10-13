# Agentic Search Memory MCP

A Model Context Protocol (MCP) server that provides persistent memory capabilities for AI agents, inspired by Anthropic's Agent SDK's memory management approach. This server enables AI applications to store, retrieve, and manage contextual information across conversations and sessions.

## 🧠 Overview

This MCP server implements a file-based memory system that allows AI agents to:
- **Persist context** across conversations and sessions
- **Store structured information** in organized memory files
- **Retrieve historical data** for better context awareness
- **Manage memory efficiently** with configurable size limits

The design philosophy follows Anthropic's Agent SDK pattern of maintaining persistent memory that survives context window resets, enabling more sophisticated and context-aware AI interactions.

## ✨ Features

### Core Memory Operations
- **📖 View**: Browse memory directory tree (full recursive with 1-space indentation) and read file contents (with pagination support)
- **📝 Create**: Create new memory files with custom content (warns on large files, tracks co-visitation)
- **✏️ Edit**: Replace text in existing memory files (warns on large results, tracks co-visitation)
- **➕ Insert**: Add content at specific line positions (warns on large results, tracks co-visitation)
- **🗑️ Delete**: Remove memory files or directories
- **📁 Rename**: Move or rename memory files and directories
- **🧹 Clear**: Reset all memory (with safety confirmation)

### Associative Memory
- **🧠 Co-Visitation Tracking**: Automatically learns which files are related based on viewing, creating, and editing patterns
- **🔗 Smart Recommendations**: Suggests related files when viewing content
- **📊 Session-Based Learning**: Tracks file relationships within MCP sessions (read and write operations)
- **🎯 Non-Invasive Design**: Path-only recommendations prevent measurement plateau
- **🛡️ Robust Error Handling**: Gracefully handles corrupted co-visitation data

### Security & Performance
- **🔒 Path Traversal Protection**: Secure file system access within memory boundaries
- **📏 Smart Size Management**: High limits (50K chars) with warnings and pagination guidance
- **⚡ Optimized Responses**: Concise tool responses for efficient LLM context usage
- **🛡️ Input Validation**: Robust parameter validation and error handling
- **⚠️ Large File Warnings**: Proactive alerts when creating/editing large files (>10K chars)

### MCP Integration
- **🔗 Full MCP Compliance**: Implements complete MCP specification
- **📊 Rich Resources**: Exposes memory files as MCP resources with metadata
- **🔄 Real-time Updates**: Dynamic resource discovery and updates
- **🏷️ Proper Annotations**: Comprehensive tool descriptions and metadata

## 🚀 Quick Start

### Installation

1. **Clone the repository**:
   ```bash
   git clone <repository-url>
   cd agentic-search-memory-mcp
   ```

2. **Create and activate virtual environment**:
   ```bash
   python -m venv venv
   source venv/bin/activate  # On Windows: venv\Scripts\activate
   ```

3. **Install dependencies**:
   ```bash
   pip install -r requirements.txt
   ```

### Using with Cursor

1. **Add to Cursor's MCP configuration** (`~/.cursor/mcp.json`):
   ```json
   {
     "mcpServers": {
       "agentic-search-memory-mcp": {
         "command": "/path/to/your/venv/bin/python",
         "args": [
           "/path/to/agentic-search-memory-mcp/memory_server.py"
         ],
         "env": {
           "MEMORY_DIR": "/path/to/memories"
         }
       }
     }
   }
   ```

2. **Replace paths with your actual paths**:
   - Update `command` to point to your virtual environment's Python executable
   - Update `args[0]` to point to your `memory_server.py` file
   - Update `MEMORY_DIR` to point to your desired memory directory


4. **Let the agent use memory tools** in your conversations:
   - Try something like "Remember that my name is Adam"
   - Start a new thread and ask "Do you remember my name?"

5. **Add instructions to use the memory in your AGENTS.md file** 
   - The AGENTS.md file in this project is a good starting point
   - Add meore specific instructions as needed 
### Configuration

Configure the memory system using environment variables:

```bash
# Memory directory location (default: ./memories)
export MEMORY_DIR="/path/to/your/memory/directory"

# Maximum characters to read from files (default: 20000)
export MEMORY_MAX_READ_CHARS=50000

# Maximum response size for tool outputs (default: 50000)
# High limit to prevent agents from losing access to large files
export MEMORY_MAX_RESPONSE_CHARS=50000

# Warning threshold for large files (default: 10000)
# Agents get warnings when creating/editing files above this size
export MEMORY_LARGE_FILE_THRESHOLD=10000

# Maximum number of related files to show (default: 3)
export MEMORY_COVIS_MAX_RECOMMENDATIONS=5
```

## 🏗️ Architecture

### MCP Server Structure

```
memory_server.py
├── Configuration & Setup
├── Security Helpers
│   ├── Path normalization
│   └── Traversal protection
├── Core Tools (7 MCP tools)
│   ├── view() - Read memory content
│   ├── create() - Create memory files
│   ├── str_replace() - Edit memory files
│   ├── insert() - Add content at lines
│   ├── delete() - Remove memory items
│   ├── rename() - Move/rename items
│   └── clear_all_memory() - Reset memory
└── MCP Resources
    ├── Memory directory resources
    └── Individual file resources
```



## 🔧 Development

### Project Structure

```
agentic-search-memory-mcp/
├── memory_server.py          # Main MCP server implementation
├── requirements.txt          # Python dependencies
├── AGENTS.md                 # Development guidelines
└── README.md                 # This file
```

### Key Dependencies

- **FastMCP**: Modern MCP server framework for Python
- **Pydantic**: Data validation and settings management
- **Pathlib**: Modern file system path handling

### Testing with MCP Inspector

Use the MCP Inspector to test and debug the server:

```bash
# Start the MCP Inspector
npx @modelcontextprotocol/inspector

# The inspector will start on http://localhost:6274
# Use the session token to authenticate or set DANGEROUSLY_OMIT_AUTH=true
```

**Note**: If you get port conflicts, kill existing processes:
```bash
# Find and kill processes using the ports
lsof -ti:6274 | xargs kill
lsof -ti:6277 | xargs kill
```

## 🎯 Use Cases

### AI Agent Memory
- **Conversation History**: Store important conversation context
- **Project Knowledge**: Maintain project-specific information
- **User Preferences**: Remember user settings and preferences
- **Learning Data**: Accumulate knowledge from interactions

### Development Workflows
- **Code Documentation**: Store code explanations and patterns
- **Debugging Notes**: Keep track of issues and solutions
- **Research Logs**: Maintain research findings and references
- **Meeting Notes**: Store important decisions and action items

### Content Management
- **Knowledge Base**: Build structured information repositories
- **Reference Materials**: Store frequently accessed information
- **Templates**: Maintain reusable content templates
- **Archives**: Organize historical information

## 🔒 Security Considerations

- **Path Traversal Protection**: All file operations are restricted to the memory directory
- **Input Validation**: Comprehensive validation of all input parameters
- **Error Handling**: Graceful error handling with informative messages
- **Resource Limits**: Configurable limits prevent resource exhaustion


## 📚 Inspiration

This project is inspired by **Anthropic's Agent SDK** memory management approach, which emphasizes:
- **Persistent Context**: Memory that survives beyond single conversations
- **Structured Storage**: Organized, searchable information repositories
- **Efficient Retrieval**: Fast access to relevant historical context
- **Context Window Management**: Smart handling of memory size limits


## 🔗 Related Projects

- [FastMCP](https://gofastmcp.com/) - Modern MCP server framework
- [Model Context Protocol](https://modelcontextprotocol.io/docs/getting-started/intro) - Official MCP specification
- [Anthropic Agent SDK](https://github.com/anthropics/anthropic-sdk-python/blob/main/examples/memory/basic.py) - Inspiration for memory patterns
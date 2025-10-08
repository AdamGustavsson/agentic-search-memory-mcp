# Associative Memory Example

## Scenario

Let's say you're working on a project and frequently access these files together:

**Session 1:**
- `project/requirements.md`
- `project/architecture.md`
- `project/api_spec.md`

**Session 2:**
- `project/requirements.md`
- `project/budget.md`

**Session 3:**
- `project/architecture.md`
- `project/requirements.md`
- `project/team.md`

## What Happens

After these sessions, the co-visitation index (`_covis.json`) will contain:

```json
{
  "/path/to/memories/project/requirements.md": {
    "/path/to/memories/project/architecture.md": 2,
    "/path/to/memories/project/api_spec.md": 1,
    "/path/to/memories/project/budget.md": 1,
    "/path/to/memories/project/team.md": 1
  },
  "/path/to/memories/project/architecture.md": {
    "/path/to/memories/project/requirements.md": 2,
    "/path/to/memories/project/api_spec.md": 1,
    "/path/to/memories/project/team.md": 1
  },
  ...
}
```

## When You View a File

When you view `project/requirements.md`, the output will include:

```
   1: # Project Requirements
   2: 
   3: ## Core Features
   4: - Feature A
   5: - Feature B
   
============================================================
🧠 RELATED FILES (Associative Memory)
============================================================

[1] project/architecture.md (co-visited 2x)
------------------------------------------------------------
# Architecture Overview

This document describes the system architecture...

[2] project/api_spec.md (co-visited 1x)
------------------------------------------------------------
# API Specification

## Endpoints
- GET /api/users
- POST /api/users
...

[3] project/budget.md (co-visited 1x)
------------------------------------------------------------
# Project Budget

Total: $50,000
...
```

## Benefits in Practice

1. **Context Restoration**: When you return to a file after weeks, you immediately see what other files are related
2. **Knowledge Discovery**: Find connections you may have forgotten
3. **Faster Navigation**: No need to manually search for related files
4. **Pattern Learning**: The system learns your workflow patterns over time

## Use Cases

### 1. Research Projects
- View a research paper → see related notes and citations
- View meeting notes → see related action items and documents

### 2. Code Documentation
- View API docs → see related implementation guides
- View architecture diagram → see related design decisions

### 3. Client Work
- View client requirements → see related proposals and contracts
- View project status → see related meeting notes

### 4. Learning & Study
- View lecture notes → see related exercises and references
- View concept explanation → see related examples

## Tips for Best Results

1. **Natural Workflow**: Just use the memory system naturally - access related files together
2. **Multiple Sessions**: The more you use it, the better the recommendations become
3. **Consistent Naming**: Use clear, descriptive file names for better context
4. **Regular Reviews**: Periodically view files together to reinforce relationships

## Privacy Note

The system only tracks:
- File paths
- Co-visitation counts
- No personal data or file content is stored in the index


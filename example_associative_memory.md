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
  [2] project/api_spec.md (co-visited 1x)
  [3] project/budget.md (co-visited 1x)
```

You can then explicitly view any related file to access its full content.

## Benefits in Practice

1. **Context Restoration**: When you return to a file after weeks, you immediately see what other files are related
2. **Knowledge Discovery**: Find connections you may have forgotten
3. **Faster Navigation**: Related files are suggested without needing to search
4. **Pattern Learning**: The system learns your workflow patterns over time
5. **Accurate Association Strength**: Path-only recommendations ensure co-visitation counts reflect genuine usefulness

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
4. **Explicit Viewing**: When a related file is useful, explicitly view it to strengthen the association
5. **Ignore Weak Suggestions**: If a suggested file isn't relevant, simply ignore it - the association will naturally decay

## Privacy Note

The system only tracks:
- File paths
- Co-visitation counts
- No personal data or file content is stored in the index


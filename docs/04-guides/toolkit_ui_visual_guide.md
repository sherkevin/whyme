# 🛠️ Toolkit Management UI - Visual Guide

## What You'll See in the Browser

### 1. Activity Bar (Left Sidebar)
```
┌─────────────────┐
│  Activity Bar   │
├─────────────────┤
│  📁 (Explorer)  │ ← Click to see files
│  🛠️ (Toolkit)   │ ← Click to manage tools ⭐
│  🔍 (Search)    │
│  ⚙️ (Settings)  │
└─────────────────┘
```

**NEW!** The 🛠️ Toolkit icon is now prominent in the activity bar.

### 2. Project Switcher with Toolkit Buttons
```
┌──────────────────────────────────────────┐
│ PROJECTS                                  │
├──────────────────────────────────────────┤
│ 📁 My First Project        [🛠️ Toolkit] ✓│
│    ID: b9bffa2...                         │
├──────────────────────────────────────────┤
│ 📁 Test Python App        [🛠️ Toolkit]   │
│    ID: f99eedc7...                         │
└──────────────────────────────────────────┘
```

**NEW!** Each project now has a **🛠️ Toolkit** button that:
1. Switches to that project
2. Opens its toolkit panel immediately

### 3. Toolkit Panel Header
```
┌────────────────────────────────────────┐
│ 🛠️ Toolkit (My First Project)          │
│                                        │
│ [Skills] [MCP Servers]                 │
├────────────────────────────────────────┤
│ 💡 Skills are Python scripts that...    │
│    Each project has its own...          │
├────────────────────────────────────────┤
│ [+ New Skill] [↻]                      │
│                                        │
│ 🔧 calculator                           │
│    Calculator Skill - 安全的数学...      │
│    [Edit] [Delete]                      │
├────────────────────────────────────────┤
│ 🔧 weather                              │
│    Weather Skill - 获取天气信息          │
│    [Edit] [Delete]                      │
└────────────────────────────────────────┘
```

**Notice the header**: `🛠️ Toolkit (My First Project)`
This tells you **which project's toolkit** you're managing!

## Step-by-Step: Managing Tools for Your Project

### Scenario 1: Create a Custom Skill for Your Project

**Step 1: Open Your Project's Toolkit**
- Method A: Click 📂 → Click [🛠️ Toolkit] button next to your project
- Method B: Click 🛠️ icon in activity bar (opens current project's toolkit)

**Step 2: Verify You're in the Right Project**
- Look at the sidebar header
- It should say: `🛠️ Toolkit (Your Project Name)`

**Step 3: Create the Skill**
1. Click "+ New Skill" button
2. Enter name: `my_calculator`
3. Press Enter
4. Skill opens in Monaco Editor

**Step 4: Edit the Skill**
```python
#!/usr/bin/env python3
"""
My Custom Calculator
"""

def calculate(expression):
    """Evaluate a mathematical expression"""
    try:
        result = eval(expression)
        return result
    except Exception as e:
        return f"Error: {e}"

if __name__ == "__main__":
    import sys
    if len(sys.argv) > 1:
        expr = sys.argv[1]
        print(f"{expr} = {calculate(expr)}")
    else:
        print("Usage: my_calculator.py '2 + 2'")
```

**Step 5: Save the Skill**
- Press `Ctrl+S`
- Skill is now part of **this project only**

**Step 6: Use It with AI**
- In the chat, tell the AI: "Use my_calculator to compute 15 * 3"
- The AI will run: `/run python toolkit/bins/my_calculator.py '15 * 3'`

### Scenario 2: Configure MCP Server for Your Project

**Step 1: Open Toolkit Panel**
- Click 🛠️ in activity bar
- Verify project name in header

**Step 2: Switch to MCP Servers Tab**
- Click "MCP Servers" tab
- See info banner about project isolation

**Step 3: Add MCP Server**
1. Click "+ Add Server" button
2. Enter name: `my_filesystem`
3. Enter command: `npx -y @modelcontextprotocol/server-filesystem C:\MyData`
4. Click OK
5. Server added to **this project only**

**Step 4: Verify**
- Switch to a different project
- Open its toolkit
- The MCP server won't appear there

## Project Isolation Demonstration

### Project A: Weather Dashboard
```
🛠️ Toolkit (Weather Dashboard)
├── Skills
│   ├── weather.py           # Get current weather
│   ├── forecast.py          # 7-day forecast
│   └── alerts.py            # Weather alerts
└── MCP Servers
    └── weather_api.json     # Weather data API
```

### Project B: File Automation
```
🛠️ Toolkit (File Automation)
├── Skills
│   ├── csv_parser.py        # Parse CSV files
│   ├── file_mover.py        # Move files based on rules
│   └── batch_processor.py   # Process multiple files
└── MCP Servers
    └── filesystem.json      # File system access
```

**Result**: Two completely different toolkits for two different purposes!

## UI Color Guide

| Element | Color | Meaning |
|---------|-------|---------|
| 🛠️ Toolkit Icon | Blue accent | Click to manage tools |
| [🛠️ Toolkit] Button | Primary blue | Per-project toolkit access |
| Active Tab | Blue underline | Currently visible tab |
| Project Name | White text | Shows current project |
| Info Banner | Gray text | Explains project isolation |

## Common Workflows

### Workflow 1: Quick Skill Creation
1. Open project (click 📂)
2. Click [🛠️ Toolkit] button
3. Click "+ New Skill"
4. Enter name, edit, save

**Time**: ~30 seconds

### Workflow 2: Compare Toolkits Between Projects
1. Open Project A toolkit
2. Note the skills listed
3. Click 📂 → Click Project B's [🛠️ Toolkit] button
4. See different skills (isolated!)

### Workflow 3: Copy Skill to Another Project
1. In Project A, open skill in editor
2. Copy the code (Ctrl+A, Ctrl+C)
3. Switch to Project B
4. Create new skill with same name
5. Paste code (Ctrl+V)
6. Save

## Keyboard Shortcuts

- `Ctrl+S` - Save current skill
- `Ctrl+N` - New file (in Explorer)
- `Ctrl+W` - Close current tab

## Tips

### Tip 1: Always Check the Project Name
Before creating/editing tools, glance at the sidebar header:
```
🛠️ Toolkit (My Project) ← You're here!
```

### Tip 2: Use Project Switcher for Quick Access
The [🛠️ Toolkit] button in the project list is the fastest way to:
1. Switch projects
2. Open their toolkit
3. Start working immediately

### Tip 3: Refresh After Changes
If you create/delete files outside the UI:
- Click the ↻ Refresh button
- Updates the toolkit list

### Tip 4: Descriptions Help
When creating skills, add good descriptions:
```python
"""
My Awesome Skill

This skill does amazing things for my project.
Usage: my_skill.py arg1 arg2
"""
```

The description appears in the toolkit list!

## FAQ

**Q: Can I have the same skill in two projects?**
A: Yes! Create it in both projects, or copy the `.py` file.

**Q: Where are the skill files stored?**
A: In the project's workspace: `data/workspaces/{session_id}/toolkit/bins/`

**Q: How do I backup my skills?**
A: Copy the entire `toolkit/` folder for that project.

**Q: Can I share skills between projects automatically?**
A: Not currently. Each project is intentionally isolated. Copy skills manually if needed.

**Q: What happens if I delete a project?**
A: The project's toolkit (all skills and MCP configs) is deleted too.

**Q: Can I undo a skill deletion?**
A: No! Make sure to backup important skills before deleting.

---

**Ready to use the toolkit?**

1. Open your browser to `http://127.0.0.1:8003`
2. Click the 🛠️ icon in the activity bar
3. Start creating project-specific tools!

Each project is its own isolated workspace with its own tools. Enjoy! 🚀

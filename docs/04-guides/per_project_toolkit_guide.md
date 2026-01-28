# 🛠️ Per-Project Toolkit Management Guide

## Overview

Each project in AgentOS has its own **isolated toolkit** containing Skills and MCP Servers. This means:
- ✅ Skills created in Project A won't appear in Project B
- ✅ MCP servers configured in Project A won't affect Project B
- ✅ Each project can have completely different tools and capabilities

## How to Access Toolkit Management

### Method 1: From Project Switcher (Recommended)
1. Click the **📂 Projects** button in the sidebar
2. Find your project in the list
3. Click the **🛠️ Toolkit** button next to the project name
4. The toolkit panel will open showing tools for **that specific project**

### Method 2: From Activity Bar
1. Click the **🛠️ Toolkit** icon in the left activity bar
2. The panel header shows which project's toolkit you're managing:
   `🛠️ Toolkit (My First Project)`
3. All changes affect only the currently active project

## Understanding the UI

### Sidebar Header
When you open the toolkit panel, you'll see:
```
🛠️ Toolkit (Project Name)
```
This clearly indicates **which project's toolkit** you're managing.

### Information Banner
At the top of each tab, you'll see:
- **Skills tab**: "💡 Skills are Python scripts that extend this project's capabilities. Each project has its own isolated toolkit."
- **MCP Servers tab**: "🌐 MCP (Model Context Protocol) servers provide external tools and capabilities. Each project has its own isolated MCP server configuration."

This reminds you that changes are **project-specific**.

### Project Switcher with Toolkit Buttons
When you open the project switcher (📂 button), each project row shows:
```
📁 My First Project                    [🛠️ Toolkit]  ✓
   ID: b9bffa2...
```
The **🛠️ Toolkit** button lets you:
1. Switch to that project
2. Immediately open its toolkit panel

## Managing Skills per Project

### Creating a Project-Specific Skill

1. **Open the project's toolkit**:
   - Switch to the desired project
   - Click 🛠️ Toolkit icon or use project switcher

2. **Create a new skill**:
   - Click "+ New Skill" button
   - Enter skill name (e.g., `my_custom_calculator`)
   - The skill is created **only for this project**

3. **Edit the skill**:
   - Click on the skill in the list
   - Edit in Monaco Editor with Python syntax highlighting
   - Save with Ctrl+S

4. **Use the skill**:
   - The AI agent in this project can now use it
   - Other projects won't see this skill

### Example: Different Skills for Different Projects

**Project A - Weather Dashboard:**
- `weather.py` - Get weather data
- `forecast.py` - Get 7-day forecast
- `alerts.py` - Weather alerts

**Project B - File Processor:**
- `csv_parser.py` - Parse CSV files
- `json_validator.py` - Validate JSON
- `file_converter.py` - Convert file formats

Each project has completely different tools!

## Managing MCP Servers per Project

### Adding a Project-Specific MCP Server

1. **Open the project's toolkit**
2. **Switch to "MCP Servers" tab**
3. **Click "+ Add Server"**
4. **Enter server details**:
   - Name: `filesystem_server`
   - Command: `npx -y @modelcontextprotocol/server-filesystem /tmp`
5. **The server is configured only for this project**

### Example: Different MCP Servers per Project

**Project A - Database Tools:**
- PostgreSQL MCP server
- Redis MCP server

**Project B - Cloud Tools:**
- AWS S3 MCP server
- Google Drive MCP server

## Verifying Project Isolation

### Test 1: Create Skill in Project A
1. Switch to Project A
2. Create skill called `project_a_skill.py`
3. Verify skill appears in Project A's toolkit

### Test 2: Check Project B
1. Switch to Project B
2. Open toolkit panel
3. Verify `project_a_skill.py` **does not appear**
4. Project B has its own isolated toolkit

### Test 3: Create Different Skill in Project B
1. In Project B, create `project_b_skill.py`
2. Verify only Project B sees this skill
3. Project A still only has `project_a_skill.py`

## Technical Details

### File System Structure
```
data/workspaces/
├── project_a_session_id/
│   └── toolkit/
│       ├── bins/
│       │   ├── calculator.py
│       │   └── weather.py
│       ├── mcp_servers/
│       │   └── filesystem.json
│       ├── registry.json
│       └── manager.py
│
└── project_b_session_id/
    └── toolkit/
        ├── bins/
        │   ├── custom_tool.py      # Different from Project A
        │   └── helper.py           # Unique to Project B
        ├── mcp_servers/
        │   └── database.json       # Different MCP server
        ├── registry.json
        └── manager.py
```

Each project's toolkit is in its own workspace directory, ensuring complete isolation.

### API Endpoints
All API endpoints are session-specific:
- `/api/sessions/{session_id}/toolkit/skills` - Lists skills for that session only
- `/api/sessions/{session_id}/toolkit/mcp-servers` - Lists MCP servers for that session only

## Best Practices

### 1. Organize Tools by Project Purpose
- Create skills specific to the project's domain
- Keep related tools together
- Avoid duplicating generic skills (use global_toolkit template instead)

### 2. Document Your Skills
- Add clear descriptions in skill docstrings
- Include usage examples
- Document dependencies

### 3. Test Skills in Isolation
- Test each skill in its project before using with AI
- Verify skills don't interfere with each other
- Check error handling

### 4. Share Skills Between Projects (Advanced)
If you need the same skill in multiple projects:
1. Create it in one project
2. Copy the `.py` file to other projects
3. Use the toolkit refresh button
4. Consider moving frequently-used skills to `global_toolkit/` template

## Troubleshooting

### Issue: "I created a skill but can't see it"
**Solution**:
- Make sure you're in the correct project
- Click the project name in the header to verify
- Use the 📂 project switcher to confirm

### Issue: "My other project can't see this skill"
**Explanation**: This is expected behavior! Each project has isolated toolkits.
**Solution**: If you need the skill in both projects, recreate it in the other project or copy the file.

### Issue: "Changed to a different project but see same tools"
**Solution**:
- Click the ↻ Refresh button in the toolkit panel
- Verify the project name in the header
- The browser may have cached the list

## Summary

✅ **Each project = Isolated toolkit**
✅ **Skills in Project A ≠ Skills in Project B**
✅ **MCP servers configured per project**
✅ **Clear UI shows which project you're managing**
✅ **Easy switching between projects**

The per-project isolation ensures that:
1. Projects remain independent
2. Tools are organized by purpose
3. No accidental cross-project interference
4. Clear separation of concerns

## Quick Reference

| Action | How |
|--------|-----|
| Open project toolkit | Click 🛠️ button in project list or activity bar |
| Create project-specific skill | + New Skill button (affects only current project) |
| Add project MCP server | + Add Server button (affects only current project) |
| Switch projects | Use 📂 Projects button, then click project name |
| Verify which project | Check sidebar header: "🛠️ Toolkit (Project Name)" |
| Share skills between projects | Manually copy `.py` files or recreate in each project |

---

**Remember**: When you manage tools, you're always working with the **current project's toolkit**. Changes won't affect other projects!

# EmailBison MCP Server - Installation & Setup Guide

Complete guide for installing and configuring the EmailBison MCP Server to connect with Claude Desktop.

## Table of Contents

1. [Prerequisites](#prerequisites)
2. [Installation Methods](#installation-methods)
3. [Configuration](#configuration)
4. [Connecting to Claude Desktop](#connecting-to-claude-desktop)
5. [Verification](#verification)
6. [Troubleshooting](#troubleshooting)

---

## Prerequisites

Before you begin, ensure you have:

- **Python 3.10 or higher** installed on your system
  - Check your version: `python --version` or `python3 --version`
  - Download from [python.org](https://www.python.org/downloads/) if needed
- **Git** installed (for cloning the repository)
- **Claude Desktop** application installed
  - Download from [Anthropic's website](https://claude.ai/download)
- **EmailBison API Key(s)** provided by your team administrator
- **config.json file** provided by your team administrator

---

## Installation Methods

### Method 1: Install from GitHub (Recommended)

This method allows you to easily update to the latest version.

#### Step 1: Clone the Repository

```bash
git clone https://github.com/max-longrun/bison-mcp.git
cd bison-mcp
```

#### Step 2: Create a Virtual Environment (Recommended)

**Windows (PowerShell):**
```powershell
python -m venv .venv
.venv\Scripts\Activate.ps1
```

**Windows (Command Prompt):**
```cmd
python -m venv .venv
.venv\Scripts\activate.bat
```

**macOS/Linux:**
```bash
python3 -m venv .venv
source .venv/bin/activate
```

#### Step 3: Install the Package

```bash
pip install -e .
```

This installs the package in "editable" mode, so any updates you pull from GitHub will be immediately available.

---

### Method 2: Direct Installation from GitHub (Without Cloning)

If you prefer not to clone the repository:

```bash
pip install git+https://github.com/max-longrun/bison-mcp.git
```

**Note:** With this method, you'll need to manually update by running the command again when new versions are released.

---

### Method 3: Install from Local Directory

If you received the project as a ZIP file or folder:

1. Extract/unzip the project to a location of your choice
2. Open a terminal in that directory
3. Create and activate a virtual environment (see Method 1, Step 2)
4. Install:
   ```bash
   pip install -e .
   ```

---

## Configuration

### Step 1: Locate the Installation Directory

After installation, you need to find where the package is installed:

**If you cloned the repository:**
- The `config.json` file should be placed in the `emailbison_mcp/` directory within the cloned repository

**If you installed directly from GitHub:**
- Find your Python site-packages directory:
  ```bash
  python -c "import site; print(site.getsitepackages())"
  ```
- Navigate to `site-packages/emailbison_mcp/` directory

**Quick way to find it:**
```bash
python -c "import emailbison_mcp; import os; print(os.path.dirname(emailbison_mcp.__file__))"
```

### Step 2: Place Your config.json File

1. Copy the `config.json` file provided by your team administrator
2. Place it in the `emailbison_mcp/` directory (the one you found in Step 1)

**Important:** The file must be named exactly `config.json` and placed in the `emailbison_mcp/` directory.

### Step 3: Verify Configuration File

Your `config.json` should look like this:

```json
{
  "clients": {
    "ClientName1": {
      "mcp_key": "your-api-key-here",
      "mcp_url": "https://send.longrun.agency/api"
    },
    "ClientName2": {
      "mcp_key": "another-api-key-here",
      "mcp_url": "https://send.longrun.agency/api"
    }
  },
  "default_client": "ClientName1"
}
```

**Security Note:** Never share your `config.json` file or commit it to version control. It contains sensitive API keys.

---

## Connecting to Claude Desktop

### Step 1: Locate Claude Desktop Configuration File

The configuration file location depends on your operating system:

**Windows:**
```
%APPDATA%\Claude\claude_desktop_config.json
```

**macOS:**
```
~/Library/Application Support/Claude/claude_desktop_config.json
```

**Linux:**
```
~/.config/Claude/claude_desktop_config.json
```

### Step 2: Edit the Configuration File

1. **Close Claude Desktop** if it's currently running
2. Open the `claude_desktop_config.json` file in a text editor
3. Add the EmailBison MCP server configuration

#### Configuration Structure

Add the following to your `claude_desktop_config.json`:

**Windows:**
```json
{
  "mcpServers": {
    "emailbison": {
      "command": "python",
      "args": [
        "-m",
        "emailbison_mcp.server"
      ],
      "env": {}
    }
  }
}
```

**macOS/Linux:**
```json
{
  "mcpServers": {
    "emailbison": {
      "command": "python3",
      "args": [
        "-m",
        "emailbison_mcp.server"
      ],
      "env": {}
    }
  }
}
```

#### If You're Using a Virtual Environment

If you installed in a virtual environment, you need to use the full path to the Python executable:

**Windows:**
```json
{
  "mcpServers": {
    "emailbison": {
      "command": "C:\\path\\to\\bison-mcp\\.venv\\Scripts\\python.exe",
      "args": [
        "-m",
        "emailbison_mcp.server"
      ],
      "env": {}
    }
  }
}
```

**macOS/Linux:**
```json
{
  "mcpServers": {
    "emailbison": {
      "command": "/path/to/bison-mcp/.venv/bin/python",
      "args": [
        "-m",
        "emailbison_mcp.server"
      ],
      "env": {}
    }
  }
}
```

#### Complete Example Configuration

If you already have other MCP servers configured, your file might look like this:

```json
{
  "mcpServers": {
    "filesystem": {
      "command": "npx",
      "args": ["-y", "@modelcontextprotocol/server-filesystem", "/path/to/allowed/files"]
    },
    "emailbison": {
      "command": "python",
      "args": [
        "-m",
        "emailbison_mcp.server"
      ],
      "env": {}
    }
  }
}
```

### Step 3: Verify Python Path

If you're unsure which Python command to use:

**Check Python command:**
```bash
which python    # macOS/Linux
where python    # Windows
```

**Check Python version:**
```bash
python --version
```

Use `python3` instead of `python` if that's what's installed on your system.

### Step 4: Restart Claude Desktop

1. Save the configuration file
2. Launch Claude Desktop
3. The MCP server should automatically connect

---

## Verification

### Step 1: Check MCP Connection

1. Open Claude Desktop
2. Start a new conversation
3. Look for the MCP indicator (usually in the top-right corner or settings)
4. You should see "emailbison" listed as a connected MCP server

### Step 2: Test the Connection

Try asking Claude:

```
"Can you list my EmailBison leads?"
```

or

```
"What EmailBison tools are available?"
```

If the connection is working, Claude should be able to access EmailBison tools and resources.

### Step 3: Verify Tools Are Available

Claude should be able to:
- List leads from your EmailBison account
- Create new leads
- Manage campaigns
- Send emails
- And many other EmailBison operations

---

## Troubleshooting

### Issue: "Module not found: emailbison_mcp"

**Solution:**
- Ensure you've installed the package: `pip install -e .`
- Verify installation: `python -c "import emailbison_mcp; print('OK')"`
- If using a virtual environment, make sure it's activated
- Check that you're using the correct Python executable in the Claude Desktop config

### Issue: "config.json not found"

**Solution:**
- Verify `config.json` is in the `emailbison_mcp/` directory
- Check the file name is exactly `config.json` (not `config.json.txt`)
- Find the correct directory:
  ```bash
  python -c "import emailbison_mcp; import os; print(os.path.dirname(emailbison_mcp.__file__))"
  ```

### Issue: "Authentication failed" or "Invalid API key"

**Solution:**
- Verify your `config.json` file has the correct API keys
- Check that the `mcp_url` is correct: `https://send.longrun.agency/api`
- Ensure there are no extra spaces or quotes around the API keys
- Contact your team administrator to verify the API keys are valid

### Issue: Claude Desktop doesn't show the MCP server

**Solution:**
- Verify the configuration file is in the correct location
- Check JSON syntax is valid (use a JSON validator)
- Ensure Claude Desktop is completely closed before editing the config
- Restart Claude Desktop after making changes
- Check Claude Desktop logs for error messages

### Issue: "Python command not found"

**Solution:**
- Use the full path to Python in the config file
- Try `python3` instead of `python` (or vice versa)
- Verify Python is in your system PATH
- If using a virtual environment, use the full path to the venv's Python executable

### Issue: Permission errors on macOS/Linux

**Solution:**
- Ensure the Python executable has execute permissions
- You may need to use `chmod +x` on the Python executable
- Check file permissions on `config.json`

### Issue: Updates not working

**Solution:**
- If you cloned the repo, pull the latest changes:
  ```bash
  git pull origin main
  ```
- If you installed directly, reinstall:
  ```bash
  pip install --upgrade git+https://github.com/max-longrun/bison-mcp.git
  ```

---

## Getting Help

If you encounter issues not covered here:

1. Check the main [README.md](README.md) for additional information
2. Review the [DEPLOYMENT.md](DEPLOYMENT.md) for deployment-specific details
3. Contact your team administrator
4. Check the GitHub repository for issues: https://github.com/max-longrun/bison-mcp

---

## Quick Reference

### Installation (One-time setup)
```bash
git clone https://github.com/max-longrun/bison-mcp.git
cd bison-mcp
python -m venv .venv
.venv\Scripts\Activate.ps1  # Windows PowerShell
pip install -e .
```

### Update to Latest Version
```bash
cd bison-mcp
git pull origin main
```

### Configuration File Locations
- **config.json**: `emailbison_mcp/config.json`
- **Claude Desktop Config (Windows)**: `%APPDATA%\Claude\claude_desktop_config.json`
- **Claude Desktop Config (macOS)**: `~/Library/Application Support/Claude/claude_desktop_config.json`
- **Claude Desktop Config (Linux)**: `~/.config/Claude/claude_desktop_config.json`

---

## Security Reminders

- ✅ Never commit `config.json` to version control
- ✅ Never share your `config.json` file publicly
- ✅ Keep your API keys secure
- ✅ Rotate API keys if they're ever exposed
- ✅ Use the `.gitignore` file to prevent accidental commits

---

**Last Updated:** January 2025  
**Repository:** https://github.com/max-longrun/bison-mcp


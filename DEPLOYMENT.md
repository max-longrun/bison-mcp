# EmailBison MCP Server - Deployment Guide

This guide will help you deploy the EmailBison MCP server on a new computer or server.

## Table of Contents

1. [Prerequisites](#prerequisites)
2. [Installation Methods](#installation-methods)
3. [Configuration](#configuration)
4. [Running the Server](#running-the-server)
5. [Connecting to Claude Desktop](#connecting-to-claude-desktop)
6. [Troubleshooting](#troubleshooting)
7. [Production Deployment](#production-deployment)

## Prerequisites

Before deploying, ensure you have:

- **Python 3.10 or higher** - Check with `python --version` or `python3 --version`
- **pip** (Python package installer) - Usually comes with Python
- **EmailBison API Key** - Get this from your EmailBison workspace settings
- **Internet connection** - Required for API calls and package installation

### Checking Python Installation

**Windows:**
```powershell
python --version
```

**macOS/Linux:**
```bash
python3 --version
```

If Python is not installed:
- **Windows**: Download from [python.org](https://www.python.org/downloads/)
- **macOS**: `brew install python3` or download from python.org
- **Linux**: `sudo apt-get install python3 python3-pip` (Ubuntu/Debian) or use your distribution's package manager

## Installation Methods

### Method 1: Direct Installation (Recommended for Development)

1. **Clone or copy the project files** to the target computer:
   ```bash
   # If using git
   git clone <repository-url>
   cd bison-mcp
   
   # Or copy the entire folder manually
   ```

2. **Navigate to the project directory:**
   ```bash
   cd bison-mcp
   ```

3. **Create a virtual environment (recommended):**
   
   **Windows:**
   ```powershell
   python -m venv .venv
   .venv\Scripts\activate
   ```
   
   **macOS/Linux:**
   ```bash
   python3 -m venv .venv
   source .venv/bin/activate
   ```

4. **Install the package:**
   ```bash
   pip install -e .
   ```

### Method 2: Install from Source (Production)

1. **Copy the project folder** to the target location

2. **Install dependencies:**
   ```bash
   pip install httpx pydantic anyio mcp
   ```

3. **Verify installation:**
   ```bash
   python -m emailbison_mcp.server --help
   ```

### Method 3: Using pipx (Isolated Installation)

**Windows:**
```powershell
pip install pipx
pipx install -e .
```

**macOS/Linux:**
```bash
pip3 install --user pipx
pipx install -e .
```

## Configuration

### Step 1: Create Environment File

1. **Copy the example environment file:**
   ```bash
   # Windows
   copy example.env .env
   
   # macOS/Linux
   cp example.env .env
   ```

2. **Edit the `.env` file** with your credentials:

   **Windows (Notepad):**
   ```powershell
   notepad .env
   ```

   **macOS/Linux (nano):**
   ```bash
   nano .env
   ```

3. **Add your EmailBison API key:**
   ```env
   EMAILBISON_API_KEY=your_api_key_here
   EMAILBISON_BASE_URL=https://send.longrun.agency/api
   EMAILBISON_TIMEOUT_SECONDS=30
   ```

   **Important:** Replace `your_api_key_here` with your actual EmailBison API key.

### Step 2: Set Environment Variables (Alternative)

If you prefer not to use a `.env` file, set environment variables directly:

**Windows (PowerShell):**
```powershell
$env:EMAILBISON_API_KEY="your_api_key_here"
$env:EMAILBISON_BASE_URL="https://send.longrun.agency/api"
$env:EMAILBISON_TIMEOUT_SECONDS="30"
```

**Windows (Command Prompt):**
```cmd
set EMAILBISON_API_KEY=your_api_key_here
set EMAILBISON_BASE_URL=https://send.longrun.agency/api
set EMAILBISON_TIMEOUT_SECONDS=30
```

**macOS/Linux (Bash):**
```bash
export EMAILBISON_API_KEY="your_api_key_here"
export EMAILBISON_BASE_URL="https://send.longrun.agency/api"
export EMAILBISON_TIMEOUT_SECONDS="30"
```

**macOS/Linux (Persistent - add to ~/.bashrc or ~/.zshrc):**
```bash
echo 'export EMAILBISON_API_KEY="your_api_key_here"' >> ~/.bashrc
echo 'export EMAILBISON_BASE_URL="https://send.longrun.agency/api"' >> ~/.bashrc
source ~/.bashrc
```

### Configuration Options

| Variable | Required | Default | Description |
|----------|----------|---------|-------------|
| `EMAILBISON_API_KEY` | Yes | - | Your EmailBison workspace API key |
| `EMAILBISON_BASE_URL` | No | `https://send.longrun.agency/api` | API base URL (usually no need to change) |
| `EMAILBISON_TIMEOUT_SECONDS` | No | `30` | Request timeout in seconds |

## Running the Server

### Basic Test Run

Test that the server starts correctly:

```bash
python -m emailbison_mcp.server
```

The server communicates via stdio (standard input/output), so you won't see much output. If there are no errors, the server is ready.

**To stop the server:** Press `Ctrl+C`

### Verify Installation

You can verify the installation works by checking Python can import the module:

```bash
python -c "import emailbison_mcp.server; print('Installation successful!')"
```

## Connecting to Claude Desktop

### Step 1: Locate Claude Desktop Configuration

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

### Step 2: Edit Configuration File

Open the configuration file in a text editor and add the EmailBison MCP server:

**Windows Example:**
```json
{
  "mcpServers": {
    "emailbison": {
      "command": "python",
      "args": [
        "-m",
        "emailbison_mcp.server"
      ],
      "env": {
        "EMAILBISON_API_KEY": "your_api_key_here",
        "EMAILBISON_BASE_URL": "https://send.longrun.agency/api"
      }
    }
  }
}
```

**macOS/Linux Example (using virtual environment):**
```json
{
  "mcpServers": {
    "emailbison": {
      "command": "/path/to/bison-mcp/.venv/bin/python",
      "args": [
        "-m",
        "emailbison_mcp.server"
      ],
      "env": {
        "EMAILBISON_API_KEY": "your_api_key_here",
        "EMAILBISON_BASE_URL": "https://send.longrun.agency/api"
      }
    }
  }
}
```

**Using Full Path (Alternative):**
```json
{
  "mcpServers": {
    "emailbison": {
      "command": "C:\\Users\\YourName\\bison-mcp\\.venv\\Scripts\\python.exe",
      "args": [
        "-m",
        "emailbison_mcp.server"
      ],
      "env": {
        "EMAILBISON_API_KEY": "your_api_key_here"
      }
    }
  }
}
```

### Step 3: Restart Claude Desktop

1. Close Claude Desktop completely
2. Reopen Claude Desktop
3. The EmailBison tools should now be available

### Step 4: Verify Connection

In Claude Desktop, you should see:
- EmailBison tools in the tools list
- Resources available for reading (api-reference, filters, pagination, etc.)
- Ability to use tools like `L_List_Leads`, `C_List_Campaigns`, etc.

## Troubleshooting

### Problem: "Module not found" or "No module named emailbison_mcp"

**Solution:**
- Ensure you're in the project directory
- Verify installation: `pip list | grep emailbison`
- Reinstall: `pip install -e .`
- Check Python path: `python -c "import sys; print(sys.path)"`

### Problem: "EMAILBISON_API_KEY not found" or authentication errors

**Solution:**
- Verify `.env` file exists in the project root
- Check environment variables are set: `echo $EMAILBISON_API_KEY` (Linux/Mac) or `echo %EMAILBISON_API_KEY%` (Windows)
- Ensure API key is correct (no extra spaces or quotes)
- Try setting environment variables directly in Claude Desktop config

### Problem: Server starts but Claude Desktop doesn't see tools

**Solution:**
- Check Claude Desktop config JSON syntax (use a JSON validator)
- Ensure the `command` path is correct (use absolute paths)
- Check Claude Desktop logs for errors
- Restart Claude Desktop completely
- Verify Python executable path: `which python` (Linux/Mac) or `where python` (Windows)

### Problem: "Permission denied" errors

**Solution:**
- Check file permissions: `chmod +x .venv/bin/python` (Linux/Mac)
- Run with appropriate user permissions
- On Windows, ensure you're not blocking script execution

### Problem: Connection timeout errors

**Solution:**
- Check internet connection
- Verify `EMAILBISON_BASE_URL` is correct
- Increase timeout: `EMAILBISON_TIMEOUT_SECONDS=60`
- Check firewall settings

### Problem: Import errors for dependencies

**Solution:**
- Install dependencies: `pip install httpx pydantic anyio mcp`
- Use virtual environment to avoid conflicts
- Check Python version: `python --version` (must be 3.10+)

## Production Deployment

### Running as a Service (Linux)

Create a systemd service file `/etc/systemd/system/emailbison-mcp.service`:

```ini
[Unit]
Description=EmailBison MCP Server
After=network.target

[Service]
Type=simple
User=your_username
WorkingDirectory=/path/to/bison-mcp
Environment="EMAILBISON_API_KEY=your_api_key"
Environment="EMAILBISON_BASE_URL=https://send.longrun.agency/api"
ExecStart=/path/to/bison-mcp/.venv/bin/python -m emailbison_mcp.server
Restart=always
RestartSec=10

[Install]
WantedBy=multi-user.target
```

Enable and start:
```bash
sudo systemctl enable emailbison-mcp
sudo systemctl start emailbison-mcp
sudo systemctl status emailbison-mcp
```

### Running as a Windows Service

Use NSSM (Non-Sucking Service Manager) or Task Scheduler to run the server as a Windows service.

### Security Best Practices

1. **Never commit `.env` file** - Add to `.gitignore`
2. **Use environment variables** instead of hardcoding API keys
3. **Restrict file permissions**: `chmod 600 .env` (Linux/Mac)
4. **Use separate API keys** for development and production
5. **Rotate API keys** regularly
6. **Monitor API usage** in EmailBison dashboard

### Backup and Migration

To move the server to another computer:

1. **Copy the project folder** (excluding `__pycache__` and `.venv`)
2. **Install Python** on the new computer
3. **Follow installation steps** above
4. **Copy `.env` file** with API key (or set environment variables)
5. **Test the installation**

## Quick Start Checklist

- [ ] Python 3.10+ installed
- [ ] Project files copied to target computer
- [ ] Virtual environment created and activated
- [ ] Package installed (`pip install -e .`)
- [ ] `.env` file created with API key
- [ ] Server starts without errors
- [ ] Claude Desktop config updated
- [ ] Claude Desktop restarted
- [ ] Tools visible in Claude Desktop

## Getting Help

If you encounter issues:

1. Check the [troubleshooting section](#troubleshooting)
2. Verify all prerequisites are met
3. Check EmailBison API status
4. Review Claude Desktop logs
5. Test server manually: `python -m emailbison_mcp.server`

## Additional Resources

- **EmailBison API Documentation**: https://docs.emailbison.com/get-started
- **MCP Documentation**: https://docs.anthropic.com/en/docs/model-context-protocol
- **Project README**: See `README.md` for tool documentation

---

**Last Updated:** 2024
**Version:** 0.1.0









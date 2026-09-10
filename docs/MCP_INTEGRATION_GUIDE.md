# VideoMontage — MCP Agent Integration Guide

This guide explains how to connect the **VideoMontage** MCP Server to autonomous AI agents, including **OpenClaw**, **Hermes Agent**, **Claude Desktop**, **Cursor**, and **Antigravity**, with special guidance for deploying via a **Telegram chat-based workflow**.

---

## 1. Overview & Architecture

VideoMontage exposes video production capabilities over the standardized **Model Context Protocol (MCP)**. It requires **no separate server**—it runs as a direct `stdio` child process launched by your agent, natively inheriting your environment variables (`.env`) and system paths.

```
+-------------------------------------------------------------+
|                       Telegram User                         |
|      "Make a 60s vertical product launch for our app"       |
+-------------------------------------------------------------+
                              |
                              v
+-------------------------------------------------------------+
|            Host Agent (OpenClaw / Hermes / Claude)          |
|  - Manages chat context & inline approval buttons           |
|  - Calls VideoMontage MCP tools & prompts                   |
+-------------------------------------------------------------+
                              | stdio (MCP JSON-RPC)
                              v
+-------------------------------------------------------------+
|                   VideoMontage MCP Server                   |
|  - videomontage_check_setup                                 |
|  - videomontage_list_pipelines_and_styles                   |
|  - videomontage_extract_brand                               |
|  - videomontage_init_project                                |
|  - videomontage_list_projects                               |
|  - videomontage_get_project_status                          |
|  - videomontage_record_checkpoint                           |
|  - videomontage_generate_asset                              |
|  - videomontage_compose_and_render                          |
+-------------------------------------------------------------+
                              |
            +-----------------+-----------------+
            |                                   |
            v                                   v
+-----------------------+           +-----------------------+
|  OpenMontage Engines  |           |     Web Dashboard     |
| (Remotion/HyperFrames)|           | (Live progress & link)|
+-----------------------+           +-----------------------+
```

---

## 2. Host Agent Configurations

### A. OpenClaw
Add VideoMontage to your OpenClaw tool configuration (`openclaw.json` or agent config):

```json
{
  "mcpServers": {
    "videomontage": {
      "command": "python",
      "args": ["-m", "mcp_server", "--transport", "stdio"],
      "cwd": "C:/Users/pierr/Documents/Personal/open-montage",
      "env": {
        "PYTHONUNBUFFERED": "1"
      }
    }
  }
}
```

### B. Hermes Agent
Add VideoMontage to Hermes MCP settings:

```json
{
  "mcp_servers": [
    {
      "name": "videomontage",
      "command": "python",
      "args": ["-m", "mcp_server"],
      "cwd": "C:/Users/pierr/Documents/Personal/open-montage"
    }
  ]
}
```

### C. Claude Desktop
Add to `claude_desktop_config.json`:

```json
{
  "mcpServers": {
    "videomontage": {
      "command": "python",
      "args": ["-m", "mcp_server"],
      "cwd": "C:/Users/pierr/Documents/Personal/open-montage"
    }
  }
}
```

### D. Cursor
Add to `.cursor/mcp.json`:

```json
{
  "mcpServers": {
    "videomontage": {
      "command": "python",
      "args": ["-m", "mcp_server"],
      "cwd": "C:/Users/pierr/Documents/Personal/open-montage"
    }
  }
}
```

---

## 3. Telegram Chat Workflow & Bot Integration

When exposing VideoMontage through a Telegram bot (e.g. `aiogram` or `python-telegram-bot`), apply the following patterns:

### A. Checkpoint Gates -> Inline Keyboard Buttons
OpenMontage enforces human approval checkpoints at `script` and `assets` (storyboard) stages. Map these checkpoints into Telegram inline buttons:

```python
from aiogram.types import InlineKeyboardMarkup, InlineKeyboardButton

def create_approval_keyboard(project_id: str, stage: str):
    return InlineKeyboardMarkup(inline_keyboard=[
        [
            InlineKeyboardButton(text="✅ Approve Stage", callback_data=f"approve:{project_id}:{stage}"),
            InlineKeyboardButton(text="🔄 Request Revision", callback_data=f"revise:{project_id}:{stage}")
        ],
        [
            InlineKeyboardButton(text="📊 View Live Dashboard", url=f"http://your-domain:8000/project/{project_id}")
        ]
    ])
```

When the user clicks **Approve**, the bot instructs the agent to call `videomontage_record_checkpoint(..., human_approved=True)`.

### B. Media Delivery Mapping
- **Keyframe Storyboards**: Use `sendMediaGroup` to send generated keyframes as a visual carousel/album.
- **Voiceover Previews**: Use `sendVoice` or `sendAudio` to send narration audio samples.
- **Final Video**: Use `sendVideo` to deliver the rendered MP4.

### C. 50MB File Limit Governance
The Telegram Bot API limits file uploads via direct HTTP bot API to **50MB**.
1. Normal 60s 1080p explainer videos rendered with CRF 23 are typically **8MB – 25MB**, well within the limit.
2. `videomontage_compose_and_render` validates file size and returns `telegram_warning` if the file exceeds 50MB.
3. If an export exceeds 50MB, either apply CRF compression (`crf: 26`) or share the file via the direct Web Dashboard link.

---

## 4. Live Web Dashboard Setup for Remote Chat

The project includes a lightweight web dashboard that allows users to view live progress, scripts, and asset filmstrips from mobile devices (including Telegram's in-app browser).

### Option A: Local / WireGuard / Tailscale
If the bot runs on the same private network or Tailscale tailnet:
```
http://<tailscale-ip>:8000/project/<project_id>
```

### Option B: Cloudflare Tunnel (Recommended for Public Telegram Links)
1. Run a free Cloudflare Tunnel:
   ```bash
   cloudflared tunnel --url http://localhost:8000
   ```
2. Set the public URL in `config.yaml`:
   ```yaml
   dashboard:
     port: 8000
     host: "127.0.0.1"
     public_base_url: "https://your-subdomain.trycloudflare.com"
   ```
VideoMontage MCP server will now automatically return public, clickable dashboard links directly in chat.

---

## 5. Intent Recognition & Trigger Words

The MCP server's tools are equipped with natural language triggers:

| Tool | Common Chat Triggers | What It Does |
|---|---|---|
| `videomontage_check_setup` | "check setup", "check keys", "what can you do?", "diagnostics" | Audits available providers & 1-minute key setup offers |
| `videomontage_list_pipelines_and_styles` | "list styles", "show templates", "available themes" | Shows pipelines and styles (e.g. `midnight-keynote`) |
| `videomontage_extract_brand` | "use my brand colors", "custom style", "our logo/colors" | Saves custom brand playbook (`styles/<slug>.yaml`) |
| `videomontage_init_project` | "make a video", "create video", "start project" | Creates workspace & returns live dashboard link |
| `videomontage_list_projects` | "show my videos", "resume video", "project list" | Discovers previous runs for session resumption |
| `videomontage_get_project_status` | "status of my video", "is it ready?", "progress" | Queries current stage, progress, and gates |
| `videomontage_record_checkpoint` | "approved", "advance stage", "looks good" | Enforces gates and records validated stage artifacts |
| `videomontage_generate_asset` | "generate voiceover", "make keyframes", "generate music" | Calls selectors with Telegram file checks |
| `videomontage_compose_and_render` | "render final video", "export mp4", "compile video" | Triggers Remotion/HyperFrames/FFmpeg render |

---

## 6. Flagship Playbook: Midnight Keynote

VideoMontage includes the **Midnight Keynote** playbook (`styles/midnight-keynote.yaml`) as its flagship aesthetic:
- **Canvas**: Matte obsidian (`#0B0B0E`) with titanium white typography (`#F5F5F7`).
- **Accents**: Electric sapphire (`#0A84FF`) and icy cyan (`#5AC8FA`).
- **Typography**: Inter (Display & Body), JetBrains Mono (Code/Metrics).
- **Transitions**: Smooth spring physics, deliberate holds (2.5s–7s), zero chaotic bounce.

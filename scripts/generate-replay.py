#!/usr/bin/env python3
"""
Generate a beautiful HTML replay of an ensemble collab session.
Usage: python3 generate-replay.py <team-id> [--output replay.html]
"""

import json
import os
import sys
import html
from datetime import datetime

def load_messages(team_id):
    path = f"/tmp/ensemble/{team_id}/messages.jsonl"
    if not os.path.isfile(path):
        print(f"Error: {path} not found", file=sys.stderr)
        sys.exit(1)
    msgs = []
    with open(path) as f:
        for line in f:
            if line.strip():
                try:
                    msgs.append(json.loads(line))
                except json.JSONDecodeError:
                    pass
    return msgs

AGENT_COLORS = {
    "codex": {"bg": "#1e3a5f", "text": "#60a5fa", "badge": "#2563eb", "icon": "◆"},
    "claude": {"bg": "#1a3328", "text": "#4ade80", "badge": "#16a34a", "icon": "●"},
    "gemini": {"bg": "#3b2e1a", "text": "#fbbf24", "badge": "#d97706", "icon": "★"},
    "aider": {"bg": "#2d1a3b", "text": "#c084fc", "badge": "#9333ea", "icon": "▲"},
    "ensemble": {"bg": "#1a1a2e", "text": "#94a3b8", "badge": "#475569", "icon": "◈"},
}

def get_agent_style(name):
    for key, style in AGENT_COLORS.items():
        if key in name.lower():
            return style
    return {"bg": "#1a1a2e", "text": "#94a3b8", "badge": "#475569", "icon": "○"}

def format_content(text):
    """Format message content with basic markdown-like rendering."""
    text = html.escape(text)
    # Bold
    import re
    text = re.sub(r'\*\*(.+?)\*\*', r'<strong>\1</strong>', text)
    # Code blocks
    text = re.sub(r'```(\w*)\n(.*?)```', r'<pre><code>\2</code></pre>', text, flags=re.DOTALL)
    # Inline code
    text = re.sub(r'`([^`]+)`', r'<code class="inline">\1</code>', text)
    # Line breaks
    text = text.replace('\n', '<br>')
    # Findings highlighting
    text = re.sub(r'\[(CRITICAL)\]', r'<span class="severity critical">[\1]</span>', text)
    text = re.sub(r'\[(HIGH)\]', r'<span class="severity high">[\1]</span>', text)
    text = re.sub(r'\[(MEDIUM)\]', r'<span class="severity medium">[\1]</span>', text)
    text = re.sub(r'\[(LOW)\]', r'<span class="severity low">[\1]</span>', text)
    text = re.sub(r'\[(INFO)\]', r'<span class="severity info">[\1]</span>', text)
    return text

def generate_html(msgs, team_id):
    # Collect metadata
    agents = {}
    for m in msgs:
        sender = m.get("from", "")
        if sender and sender != "ensemble":
            if sender not in agents:
                agents[sender] = {"count": 0, "style": get_agent_style(sender)}
            agents[sender]["count"] += 1

    # Task description — try API team data first, fall back to first message
    task = ""
    first_ts = ""
    last_ts = ""

    # Try to get task from API
    try:
        import urllib.request
        with urllib.request.urlopen(f"http://localhost:23000/api/ensemble/teams/{team_id}", timeout=2) as resp:
            team_data = json.loads(resp.read())
            task = team_data.get("team", {}).get("description", "")
    except Exception:
        pass

    for m in msgs:
        if not first_ts and m.get("timestamp"):
            first_ts = m["timestamp"]
        if m.get("timestamp"):
            last_ts = m["timestamp"]

    if not task:
        for m in msgs:
            if m.get("from") == "ensemble" and "Task:" in m.get("content", ""):
                task = m["content"].split("Task:")[-1].strip()[:200]
                break

    if not task:
        # Use command line arg if provided
        if "--task" in sys.argv:
            idx = sys.argv.index("--task")
            if idx + 1 < len(sys.argv):
                task = sys.argv[idx + 1]

    if not task:
        task = "Ensemble Collaboration Session"

    # Calculate duration
    duration = ""
    if first_ts and last_ts:
        try:
            t1 = datetime.fromisoformat(first_ts.replace("Z", "+00:00"))
            t2 = datetime.fromisoformat(last_ts.replace("Z", "+00:00"))
            secs = int((t2 - t1).total_seconds())
            mins = secs // 60
            duration = f"{mins}m {secs % 60}s" if mins else f"{secs}s"
        except Exception:
            pass

    total_msgs = sum(a["count"] for a in agents.values())

    # Build agent badges HTML
    agent_badges = ""
    for name, info in agents.items():
        s = info["style"]
        agent_badges += f'<span class="agent-badge" style="background:{s["badge"]}">{s["icon"]} {html.escape(name)} <span class="count">{info["count"]}</span></span>\n'

    # Build messages HTML
    messages_html = ""
    for m in msgs:
        sender = m.get("from", "unknown")
        content = m.get("content", "")
        ts = m.get("timestamp", "")
        msg_type = m.get("type", "chat")

        if sender == "ensemble":
            messages_html += f'''<div class="message system">
                <div class="system-content">{html.escape(content[:300])}</div>
            </div>\n'''
            continue

        style = get_agent_style(sender)
        time_str = ""
        if ts:
            try:
                t = datetime.fromisoformat(ts.replace("Z", "+00:00"))
                time_str = t.strftime("%H:%M:%S")
            except Exception:
                pass

        formatted = format_content(content)
        messages_html += f'''<div class="message" style="--agent-bg:{style['bg']};--agent-text:{style['text']}">
                <div class="message-header">
                    <span class="agent-name" style="color:{style['text']}">{style['icon']} {html.escape(sender)}</span>
                    <span class="timestamp">{time_str}</span>
                </div>
                <div class="message-body">{formatted}</div>
            </div>\n'''

    return f'''<!DOCTYPE html>
<html lang="en" data-theme="dark">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>Ensemble Replay — {html.escape(task[:60])}</title>
<style>
:root {{
    --bg: #0a0a0f;
    --surface: #12121a;
    --surface-2: #1a1a28;
    --border: #2a2a3a;
    --text: #e2e8f0;
    --text-dim: #64748b;
    --accent: #6366f1;
    --accent-glow: rgba(99, 102, 241, 0.15);
}}
* {{ margin: 0; padding: 0; box-sizing: border-box; }}
body {{
    font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', system-ui, sans-serif;
    background: var(--bg);
    color: var(--text);
    line-height: 1.6;
    min-height: 100vh;
}}

/* Header */
.header {{
    background: linear-gradient(135deg, var(--surface) 0%, var(--surface-2) 100%);
    border-bottom: 1px solid var(--border);
    padding: 2rem 0;
}}
.header-inner {{
    max-width: 800px;
    margin: 0 auto;
    padding: 0 1.5rem;
}}
.logo {{
    display: flex;
    align-items: center;
    gap: 0.5rem;
    margin-bottom: 1rem;
}}
.logo-icon {{
    font-size: 1.5rem;
    color: var(--accent);
}}
.logo-text {{
    font-size: 0.875rem;
    font-weight: 600;
    letter-spacing: 0.05em;
    text-transform: uppercase;
    color: var(--text-dim);
}}
.task-title {{
    font-size: 1.25rem;
    font-weight: 600;
    margin-bottom: 1rem;
    color: var(--text);
}}
.meta {{
    display: flex;
    gap: 1.5rem;
    flex-wrap: wrap;
    font-size: 0.875rem;
    color: var(--text-dim);
    margin-bottom: 1rem;
}}
.meta-item {{
    display: flex;
    align-items: center;
    gap: 0.375rem;
}}
.agents-row {{
    display: flex;
    gap: 0.5rem;
    flex-wrap: wrap;
    margin-top: 0.75rem;
}}
.agent-badge {{
    display: inline-flex;
    align-items: center;
    gap: 0.375rem;
    padding: 0.25rem 0.75rem;
    border-radius: 9999px;
    font-size: 0.8125rem;
    font-weight: 500;
    color: white;
}}
.agent-badge .count {{
    opacity: 0.7;
    font-size: 0.75rem;
}}

/* Messages */
.messages {{
    max-width: 800px;
    margin: 0 auto;
    padding: 1.5rem;
    display: flex;
    flex-direction: column;
    gap: 0.75rem;
}}
.message {{
    background: var(--agent-bg, var(--surface));
    border: 1px solid var(--border);
    border-radius: 12px;
    padding: 1rem 1.25rem;
    transition: transform 0.1s;
}}
.message:hover {{
    transform: translateX(2px);
}}
.message-header {{
    display: flex;
    justify-content: space-between;
    align-items: center;
    margin-bottom: 0.5rem;
}}
.agent-name {{
    font-weight: 600;
    font-size: 0.875rem;
}}
.timestamp {{
    font-size: 0.75rem;
    color: var(--text-dim);
    font-family: 'SF Mono', 'Fira Code', monospace;
}}
.message-body {{
    font-size: 0.9375rem;
    line-height: 1.7;
    color: var(--text);
    word-break: break-word;
}}
.message-body pre {{
    background: rgba(0,0,0,0.3);
    border-radius: 8px;
    padding: 0.75rem 1rem;
    overflow-x: auto;
    margin: 0.5rem 0;
    font-size: 0.8125rem;
    font-family: 'SF Mono', 'Fira Code', monospace;
}}
.message-body code.inline {{
    background: rgba(0,0,0,0.3);
    padding: 0.125rem 0.375rem;
    border-radius: 4px;
    font-size: 0.85em;
    font-family: 'SF Mono', 'Fira Code', monospace;
}}
.message-body strong {{
    color: #f1f5f9;
}}

/* Severity badges */
.severity {{
    display: inline-block;
    padding: 0.0625rem 0.5rem;
    border-radius: 4px;
    font-size: 0.75rem;
    font-weight: 700;
    font-family: 'SF Mono', 'Fira Code', monospace;
    letter-spacing: 0.02em;
}}
.severity.critical {{ background: #7f1d1d; color: #fca5a5; }}
.severity.high {{ background: #7c2d12; color: #fdba74; }}
.severity.medium {{ background: #713f12; color: #fde047; }}
.severity.low {{ background: #1a2e05; color: #bef264; }}
.severity.info {{ background: #0c1a3d; color: #93c5fd; }}

/* System messages */
.message.system {{
    background: transparent;
    border: 1px dashed var(--border);
    padding: 0.5rem 1rem;
    text-align: center;
}}
.system-content {{
    font-size: 0.8125rem;
    color: var(--text-dim);
    font-style: italic;
}}

/* Footer */
.footer {{
    text-align: center;
    padding: 2rem;
    color: var(--text-dim);
    font-size: 0.8125rem;
    border-top: 1px solid var(--border);
    margin-top: 2rem;
}}
.footer a {{
    color: var(--accent);
    text-decoration: none;
}}
.footer a:hover {{
    text-decoration: underline;
}}

/* Responsive */
@media (max-width: 640px) {{
    .header-inner, .messages {{ padding: 1rem; }}
    .meta {{ gap: 0.75rem; }}
    .task-title {{ font-size: 1.1rem; }}
}}
</style>
</head>
<body>

<header class="header">
    <div class="header-inner">
        <div class="logo">
            <span class="logo-icon">◈</span>
            <span class="logo-text">Ensemble Replay</span>
        </div>
        <h1 class="task-title">{html.escape(task[:200])}</h1>
        <div class="meta">
            <span class="meta-item">💬 {total_msgs} messages</span>
            <span class="meta-item">👥 {len(agents)} agents</span>
            {"<span class='meta-item'>⏱ " + duration + "</span>" if duration else ""}
        </div>
        <div class="agents-row">
            {agent_badges}
        </div>
    </div>
</header>

<main class="messages">
{messages_html}
</main>

<footer class="footer">
    Generated by <a href="https://github.com/michelhelsdingen/ensemble">ensemble</a> — multi-agent collaboration engine
</footer>

</body>
</html>'''


def main():
    if len(sys.argv) < 2:
        print("Usage: generate-replay.py <team-id> [--output file.html]", file=sys.stderr)
        sys.exit(1)

    team_id = sys.argv[1]
    output = "replay.html"
    if "--output" in sys.argv:
        idx = sys.argv.index("--output")
        if idx + 1 < len(sys.argv):
            output = sys.argv[idx + 1]

    msgs = load_messages(team_id)
    if not msgs:
        print("No messages found", file=sys.stderr)
        sys.exit(1)

    html_content = generate_html(msgs, team_id)

    with open(output, "w") as f:
        f.write(html_content)

    agent_count = len(set(m.get("from") for m in msgs if m.get("from") != "ensemble"))
    msg_count = len([m for m in msgs if m.get("from") != "ensemble"])
    print(f"✓ Generated {output} ({msg_count} messages, {agent_count} agents)")


if __name__ == "__main__":
    main()

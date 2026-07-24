![Gemini Agent View Header](title.png)

# Gemini Agent View (`gemini-agent-view`)

> Bringing Claude Code 1:1 Agent View, Background Session Manager & Workspace Tree TUI to Antigravity (AGY) & Google Gemini CLI.

---

## Key Features

* **Claude Code 1:1 Agent View (TUI)**: Folder-grouped workspace tree view for managing multiple parallel background sessions.
* **Double-Tap Navigation (`←` `←`)**: Double-tap Left Arrow within 0.6s at an empty prompt to immediately open Agent View.
* **Default YOLO Mode**: Runs in `--dangerously-skip-permissions` by default for fast, uninterrupted tool approvals and automated workflow execution.
* **Minimalist Gemini Theme**: Clean header layout without clutter and custom session renaming support via `/rename <name>`.
* **Background Task Persistence**: Sessions continue executing tools and generating responses in background PTYs with real-time `Running` / `Done` status tracking.
* **Empty Prompt Protection**: Double-tap and `Ctrl+Left` navigation work only when the input prompt is completely empty, ensuring uninterrupted text navigation while typing.

---

## Quick Start

```bash
# Clone repository
git clone https://github.com/leehogwang/gemini-agent-view.git
cd gemini-agent-view

# Install dependencies & build
npm install
npm run build
```

---

## Shortcuts & Controls

| Shortcut | Description |
|---|---|
| `←` `←` (Double-Tap) | Open Agent View (when input prompt is empty) |
| `Ctrl + ←` | Open Agent View |
| `Shift + Tab` | Toggle underlying agent mode |
| `↑` / `↓` | Navigate sessions in Agent View |
| `Enter` | Attach / Switch to selected session |
| `Esc` | Return to origin session |
| `n` / `Ctrl+N` | Start a new session |
| `x` / `Ctrl+X` | Terminate selected session |

---

## License

MIT License.

# TERMNL

**Talk to your terminal.** Type what you want in plain English — termnl translates it into real shell commands, shows you what it'll run, and executes on your confirmation.

No more Googling commands. No more memorizing flags.

---

## ✨ Features

- **Natural Language → Shell Commands** — Describe what you want, get the exact command
- **Smart Input Detection** — Automatically distinguishes between shell commands and natural language (no prefix needed)
- **Confirm Before Running** — Every AI-translated command is shown for approval before execution
- **Multi-Step Workflows** — Complex tasks are broken into numbered steps with run-all or step-through options
- **Session Context** — Remembers your recent commands so you can say things like *"do that again"* or *"undo that"*
- **Learning Mode** — Get explanations of what each command does and why, great for beginners
- **Multiple AI Providers** — Choose between Gemini (free) or OpenRouter (200+ models)
- **Auto-Launch** — Optionally start termnl every time you open a terminal
- **Self-Updating** — Update to the latest version with a single command
- **Works Everywhere** — macOS and Linux, Bash and Zsh

---

## 🚀 Installation

### One-Line Install

```bash
curl -sL https://github.com/nithinworks/termnl/raw/main/install.sh | bash
```

This will:
1. Check prerequisites (Python 3.10+, curl)
2. Download termnl to `~/.termnl`
3. Set up a Python virtual environment and install dependencies
4. Add `termnl` to your PATH
5. Optionally enable auto-launch on terminal start

### Requirements

- **Python 3.10+**
- **curl**
- **macOS** or **Linux**

### Start termnl

```bash
termnl
```

On first run, you'll be prompted to choose a provider and enter your API key.

---

## 🔑 Provider Setup

termnl supports two AI providers:

| Provider | Cost | Models | Setup |
|---|---|---|---|
| **Gemini** | Free | Gemini 2.5 Flash | [Get API Key](https://aistudio.google.com/apikey) |
| **OpenRouter** | Pay-per-use | 200+ models | [Get API Key](https://openrouter.ai/keys) |

Switch providers anytime with `!provider` inside termnl.

---

## 📖 Usage

### Natural Language

Just type what you want in plain English:

```
termnl > show me the 5 largest files in this directory
→ du -ah . | sort -rh | head -5 [Enter]
```

```
termnl > compress the logs folder into a zip
→ zip -r logs.zip logs/ [Enter]
```

```
termnl > find all python files modified in the last 7 days
→ find . -name "*.py" -mtime -7 [Enter]
```

### Shell Commands

Regular shell commands work as-is — termnl detects them and passes them through directly:

```
termnl > ls -la
termnl > git status
termnl > docker ps
```

### Multi-Step Workflows

Complex requests produce numbered steps:

```
termnl > set up a new node project with typescript
Multi-step workflow (4 commands):
  1. mkdir my-project && cd my-project
  2. npm init -y
  3. npm install typescript @types/node --save-dev
  4. npx tsc --init

Run all? [y/n/step]
```

- `y` — Run all sequentially (stops on failure)
- `step` — Step through one at a time, confirming each
- `n` — Cancel

---

## ⚡ Commands

| Command | Description |
|---|---|
| `!help` | Show all available commands |
| `!learn` | Toggle learning mode (get explanations for commands) |
| `!provider` | Switch AI provider (Gemini / OpenRouter) |
| `!model` | Change OpenRouter model |
| `!autolaunch` | Toggle auto-launch on terminal start |
| `!update` | Check for and install updates |
| `!uninstall` | Remove termnl completely |
| `!<cmd>` | Force-run a command without AI translation |
| `exit` / `quit` | Exit termnl, return to normal shell |

---

## 💡 Learning Mode

Enable learning mode to get explanations alongside every translated command:

```
termnl > !learn
💡 Learning mode enabled
```

```
termnl > find duplicate files
→ find . -type f -exec md5sum {} + | sort | uniq -d -w 32 [Enter]

💡 This uses `find` to hash every file with md5sum, then `sort` and
`uniq -d -w 32` to show only files sharing the same 32-char hash prefix
(i.e., duplicates).
```

Toggle off with `!learn` again.

---

## 🔄 Updating

```
termnl > !update
```

This will:
- Check the latest version from GitHub
- Back up your current installation
- Download and apply the update
- Update dependencies
- Offer to restart immediately

---

## 🗑️ Uninstalling

**From inside termnl:**
```
termnl > !uninstall
```

**Or from your shell:**
```bash
curl -sL https://github.com/nithinworks/termnl/raw/main/uninstall.sh | bash
```

This removes:
- `~/.termnl` (app directory)
- `~/.local/bin/termnl` (binary)
- Auto-launch entries from shell configs

---

## 🏗️ How It Works

```
┌─────────────────────────────────────────────────────────┐
│                     User Input                          │
└──────────────────────┬──────────────────────────────────┘
                       │
                       ▼
              ┌────────────────┐
              │   Classifier   │─── Shell? ──→ Execute directly
              │  (heuristic)   │
              └───────┬────────┘
                      │ Natural language
                      ▼
              ┌────────────────┐
              │   AI Provider  │  Gemini / OpenRouter
              │   (translate)  │
              └───────┬────────┘
                      │
                      ▼
              ┌────────────────┐
              │   Confirm &    │  Show command → Wait for [Enter]
              │    Execute     │
              └────────────────┘
```

1. **Classify** — A scoring heuristic checks if input looks like a shell command (executables on PATH, shell operators, flags) or natural language (question words, sentence structure)
2. **Translate** — Natural language is sent to the AI with session context (last 12 commands) for accurate translation
3. **Confirm** — The translated command is displayed; press Enter to run, or type anything to cancel
4. **Execute** — Command runs in your shell with full stdout/stderr and is logged to session context

---

## 📁 File Structure

```
~/.termnl/
├── termnl.py          # Main application
├── requirements.txt   # Python dependencies
├── venv/              # Isolated Python environment
├── .env               # API keys & provider config (gitignored)
├── .config            # Feature toggles (learning mode)
├── .readline_history  # Command history
└── backup/            # Auto-created during updates
```

---

## 🤝 Contributing

1. Fork the repo
2. Create your feature branch (`git checkout -b feature/awesome`)
3. Commit your changes (`git commit -m 'Add awesome feature'`)
4. Push to the branch (`git push origin feature/awesome`)
5. Open a Pull Request

---

## 📄 License

MIT

---

<p align="center">
  <b>termnl</b> — the terminal for everyone
</p>
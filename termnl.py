#!/usr/bin/env python3
__version__ = "1.0.3"

import os
import sys
import signal
import shutil
import subprocess
import platform
import readline
import atexit
from collections import deque, namedtuple
from datetime import datetime

# --- Signal Handling ---
_interrupted = False

def _on_sigint(sig, frame):
    global _interrupted
    _interrupted = True
    print()

signal.signal(signal.SIGINT, _on_sigint)

# --- Paths & State ---
_base_dir = os.path.dirname(os.path.abspath(__file__))
_env_file = os.path.join(_base_dir, ".env")
_cfg_file = os.path.join(_base_dir, ".config")
_os_shell = "macOS/zsh" if platform.system() == "Darwin" else "Linux/bash"

# --- Readline Persistence ---
_history_file = os.path.join(_base_dir, ".readline_history")
try:
    readline.read_history_file(_history_file)
except OSError:
    pass
atexit.register(readline.write_history_file, _history_file)

learning_mode = False
provider = "gemini"
openrouter_model = "google/gemini-2.5-flash"
client = None

# --- Configuration ---

def _read_env():
    """Load environment variables from .env file and provider settings."""
    global provider, openrouter_model
    if os.path.exists(_env_file):
        with open(_env_file) as f:
            for raw in f:
                raw = raw.strip()
                if raw and not raw.startswith("#") and "=" in raw:
                    k, v = raw.split("=", 1)
                    os.environ[k] = v
    provider = os.environ.get("TERMNL_PROVIDER", "gemini")
    openrouter_model = os.environ.get("OPENROUTER_MODEL", "google/gemini-2.5-flash")


def _read_cfg():
    """Load feature toggle state from config file."""
    global learning_mode
    if os.path.exists(_cfg_file):
        with open(_cfg_file) as f:
            for raw in f:
                if "learning_mode=true" in raw:
                    learning_mode = True


def _write_cfg():
    with open(_cfg_file, "w") as f:
        f.write(f"learning_mode={str(learning_mode).lower()}\n")


def _write_env():
    """Persist all provider/env settings."""
    with open(_env_file, "w") as f:
        f.write(f"TERMNL_PROVIDER={provider}\n")
        gemini_key = os.environ.get("GEMINI_API_KEY")
        openrouter_key = os.environ.get("OPENROUTER_API_KEY")
        if gemini_key:
            f.write(f"GEMINI_API_KEY={gemini_key}\n")
        if openrouter_key:
            f.write(f"OPENROUTER_API_KEY={openrouter_key}\n")
        f.write(f"OPENROUTER_MODEL={openrouter_model}\n")


# --- Provider Setup ---

def _validate_openrouter_key(api_key: str) -> bool:
    """Validate an OpenRouter API key. Returns True if valid or indeterminate."""
    print("\033[2mValidating key...\033[0m", end="", flush=True)
    try:
        from openai import OpenAI
        test = OpenAI(base_url="https://openrouter.ai/api/v1", api_key=api_key)
        test.chat.completions.create(
            model="google/gemini-2.5-flash",
            messages=[{"role": "user", "content": "respond with just the word ok"}],
            max_tokens=5,
        )
        print("\r\033[32m✓ API key validated!\033[0m   ")
        return True
    except Exception as e:
        err = str(e).lower()
        if any(s in err for s in ("401", "invalid", "unauthorized")):
            print("\r\033[31m✗ Invalid API key\033[0m   ")
            print("\033[2mPlease check your key and try again\033[0m")
            return False
        print("\r\033[33m⚠ Could not validate (network issue?) — saving anyway\033[0m   ")
        return True


def _validate_gemini_key(api_key: str) -> bool:
    """Validate a Gemini API key. Returns True if valid or indeterminate."""
    print("\033[2mValidating key...\033[0m", end="", flush=True)
    try:
        from google import genai
        test = genai.Client(api_key=api_key)
        test.models.generate_content(
            model="gemini-2.5-flash",
            contents="respond with just the word 'ok'",
        )
        print("\r\033[32m✓ API key validated!\033[0m   ")
        return True
    except Exception as e:
        err = str(e).lower()
        if any(s in err for s in ("401", "invalid", "api_key")):
            print("\r\033[31m✗ Invalid API key\033[0m   ")
            print("\033[2mPlease check your key and try again\033[0m")
            return False
        print("\r\033[33m⚠ Could not validate (network issue?) — saving anyway\033[0m   ")
        return True


def setup_provider(switch_mode=False):
    """Interactive provider setup — called on first run or via /provider."""
    global provider, openrouter_model

    print("\n\033[1mChoose your AI provider:\033[0m")
    print("  \033[36m1.\033[0m Gemini \033[2m(free, recommended)\033[0m")
    print("  \033[36m2.\033[0m OpenRouter \033[2m(200+ models)\033[0m")
    choice = input("\n\033[33m> \033[0m").strip()

    if choice == "2":
        provider = "openrouter"
        print(f"\n\033[36mGet your key at: https://openrouter.ai/keys\033[0m\n")
        api_key = input("\033[33mEnter your OpenRouter API key:\033[0m ").strip()
        if not api_key:
            print("No API key provided.")
            return False if switch_mode else sys.exit(1)

        if not _validate_openrouter_key(api_key):
            return False if switch_mode else sys.exit(1)

        os.environ["OPENROUTER_API_KEY"] = api_key

        print()
        model_input = input(
            "\033[33mEnter model\033[0m \033[2m(default: google/gemini-2.5-flash)\033[0m\033[33m:\033[0m "
        ).strip()
        openrouter_model = model_input or "google/gemini-2.5-flash"

    else:
        provider = "gemini"
        print(f"\n\033[36mGet your free key at: https://aistudio.google.com/apikey\033[0m\n")
        api_key = input("\033[33mEnter your Gemini API key:\033[0m ").strip()
        if not api_key:
            print("No API key provided.")
            return False if switch_mode else sys.exit(1)

        if not _validate_gemini_key(api_key):
            return False if switch_mode else sys.exit(1)

        os.environ["GEMINI_API_KEY"] = api_key

    _write_env()
    print("\033[32m✓ Provider configured!\033[0m\n")
    return True


# --- AI Client ---

def _create_client():
    """Instantiate the AI client for the active provider."""
    global client
    if provider == "openrouter":
        from openai import OpenAI
        client = OpenAI(
            base_url="https://openrouter.ai/api/v1",
            api_key=os.environ.get("OPENROUTER_API_KEY", ""),
        )
    else:
        from google import genai
        client = genai.Client(api_key=os.environ.get("GEMINI_API_KEY", ""))


def _ask_ai(prompt: str) -> str | None:
    """Send a prompt to the active AI provider and return the text response."""
    if provider == "openrouter":
        resp = client.chat.completions.create(
            model=openrouter_model,
            messages=[{"role": "user", "content": prompt}],
        )
        text = resp.choices[0].message.content if resp.choices else None
        return text.strip() if text else None
    else:
        resp = client.models.generate_content(
            model="gemini-2.5-flash",
            contents=prompt,
        )
        return resp.text.strip() if resp.text else None


# --- Session History (ring buffer) ---

HistoryEntry = namedtuple("HistoryEntry", ["cmd", "output", "exit_code", "ts"])

SESSION_CAPACITY = 12
TOKEN_BUDGET = 5000  # rough char budget for context window

_session_log: deque[HistoryEntry] = deque(maxlen=SESSION_CAPACITY)


def _record(cmd: str, output: str = "", exit_code: int = 0):
    """Append a command+output to the session log, evicting oldest if over budget."""
    _session_log.append(HistoryEntry(
        cmd=cmd,
        output=output[:600] if output else "",
        exit_code=exit_code,
        ts=datetime.now(),
    ))
    # Evict oldest entries if total context exceeds budget
    while len(_session_log) > 1 and sum(len(e.cmd) + len(e.output) for e in _session_log) > TOKEN_BUDGET:
        _session_log.popleft()


def _render_context() -> str:
    """Render recent session history as context for the AI prompt."""
    if not _session_log:
        return "(no previous commands)"
    parts = []
    for entry in list(_session_log)[-6:]:
        status = "✓" if entry.exit_code == 0 else "✗"
        parts.append(f"[{status}] $ {entry.cmd}")
        if entry.output:
            for line in entry.output.strip().splitlines()[:3]:
                parts.append(f"    {line}")
    return "\n".join(parts)


# --- Input Classification ---

def _classify_input(text: str) -> str:
    """
    Classify user input as 'builtin', 'shell', or 'natural'.
    
    Uses a scoring heuristic + dynamic PATH lookup instead of
    hardcoded command lists. Returns one of three categories.
    """
    stripped = text.strip()
    if not stripped:
        return "builtin"

    # Builtin commands (termnl-specific)
    if stripped.startswith("!"):
        return "builtin"
    if stripped in ("exit", "quit"):
        return "builtin"

    # --- Scoring: higher = more likely shell ---
    score = 0.0

    # Check if the first token is an executable on PATH
    first_token = stripped.split()[0] if stripped.split() else ""
    
    # Strip leading env vars (e.g., "FOO=bar cmd")
    effective_token = first_token
    if "=" in first_token and not first_token.startswith("="):
        parts = stripped.split()
        for i, p in enumerate(parts):
            if "=" not in p or p.startswith("="):
                effective_token = p
                break

    if effective_token.startswith(("./", "/", "~")):
        score += 3.0  # Path-like — almost certainly a command

    if effective_token.startswith("$"):
        score += 2.5  # Variable expansion

    if shutil.which(effective_token):
        score += 2.0  # Executable exists in PATH

    # Shell operators strongly indicate a command
    shell_operators = ("|", "&&", "||", ">>", ">;", ";", "$(", "`")
    if any(op in stripped for op in shell_operators):
        score += 2.5

    # Redirect with single >
    if ">" in stripped and ">>" not in stripped and "→" not in stripped:
        score += 2.0

    # Natural language signals — reduce score
    nl_words = {"how", "what", "why", "where", "when", "who", "which",
                "can", "could", "would", "should", "please", "help",
                "tell", "give", "is", "are", "do", "does", "the", "my",
                "me", "all", "about", "need", "want"}
    
    tokens_lower = set(stripped.lower().split())
    nl_overlap = len(tokens_lower & nl_words)

    if nl_overlap >= 2:
        score -= 2.0
    elif nl_overlap == 1 and len(tokens_lower) > 2:
        score -= 0.5

    # Multi-word input without shell operators leans natural
    word_count = len(stripped.split())
    if word_count >= 4 and score < 2.0:
        score -= 1.5

    # Starts with uppercase (likely a sentence, not a command)
    if stripped[0].isupper() and word_count > 1:
        score -= 1.0

    # Contains question mark — definitely natural language
    if "?" in stripped:
        score -= 3.0

    # Short, all-lowercase inputs with no NL signals lean toward shell
    # (e.g., "docker ps", "kubectl get pods", "brew update")
    if word_count <= 3 and nl_overlap == 0 and stripped.islower():
        score += 1.0

    # cd is always shell
    if stripped == "cd" or stripped.startswith("cd "):
        return "shell"

    return "shell" if score >= 1.0 else "natural"


# --- Command Translation ---

def _translate(user_input: str, cwd: str) -> dict:
    """
    Translate natural language input to shell commands via AI.
    Returns dict with 'commands' list and optional 'explanation'.
    """
    ctx = _render_context()
    prompt = f"""Convert the following request into executable {_os_shell} commands.
Working directory: {cwd}

Session context:
{ctx}

Guidelines:
- Return ONLY raw commands, one per line — no markdown, no backticks, no commentary
- For multi-step tasks, put each command on its own line
- Leverage session context for references like "do that again" or "undo that"
- When ambiguous, choose the simplest standard approach

Request: {user_input}"""

    raw = _ask_ai(prompt)
    if not raw:
        return {"commands": []}

    commands = [ln.strip() for ln in raw.splitlines() if ln.strip()]
    result = {"commands": commands}

    if learning_mode and commands:
        cmd_repr = commands[0] if len(commands) == 1 else " && ".join(commands)
        tip_prompt = f"""In 1-2 sentences, explain what this command does for someone learning the terminal.
Command: {cmd_repr}
Include a practical tip about the flags or options used. Start with 💡"""
        try:
            tip = _ask_ai(tip_prompt)
            if tip:
                result["explanation"] = tip
        except Exception:
            pass

    return result


# --- Command Execution ---

_PTY_COMMANDS = frozenset({
    "clear", "top", "htop", "vim", "vi", "nano",
    "less", "more", "man", "ssh", "tmux", "screen",
})


def _needs_pty(cmd: str) -> bool:
    """Check if command needs direct terminal (PTY) access."""
    base = cmd.split()[0] if cmd.split() else ""
    return base in _PTY_COMMANDS


def _run(cmd: str) -> tuple[str, str, int]:
    """Execute a shell command and return (stdout, stderr, returncode)."""
    if _needs_pty(cmd):
        rc = subprocess.run(cmd, shell=True).returncode
        return "", "", rc
    proc = subprocess.run(cmd, shell=True, capture_output=True, text=True)
    return proc.stdout, proc.stderr, proc.returncode


# --- Help & Utilities ---

def _print_help():
    print("\033[1mCommands:\033[0m")
    print("\033[36m  !\033[0m<cmd>      - Force run command without AI")
    print("\033[36m  !learn\033[0m      - Toggle learning mode")
    print("\033[36m  !provider\033[0m   - Switch AI provider (Gemini/OpenRouter)")
    print("\033[36m  !model\033[0m      - Change OpenRouter model")
    print("\033[36m  !autolaunch\033[0m - Toggle auto-launch on terminal start")
    print("\033[36m  !update\033[0m     - Update to latest version")
    print("\033[36m  !uninstall\033[0m  - Remove termnl")
    print("\033[36m  !help\033[0m       - Show this help")
    print("\033[36m  exit/quit\033[0m   - Exit termnl, return to normal shell")
    print()


def _toggle_autolaunch():
    """Toggle auto-launch in shell config files."""
    shell_configs = [
        os.path.expanduser("~/.zshrc"),
        os.path.expanduser("~/.bashrc"),
        os.path.expanduser("~/.zprofile"),
        os.path.expanduser("~/.bash_profile"),
    ]

    marker = "termnl # auto-launch"
    comment = "# termnl - auto-launch on terminal start"
    launch_line = (
        '[ -t 0 ] && [ -z "$TERMNL_RUNNING" ] && [ -x "$HOME/.local/bin/termnl" ]'
        ' && export TERMNL_RUNNING=1 && termnl # auto-launch'
    )

    is_enabled = False
    for cfg in shell_configs:
        if os.path.exists(cfg):
            with open(cfg) as f:
                if marker in f.read():
                    is_enabled = True
                    break

    if is_enabled:
        for cfg in shell_configs:
            if not os.path.exists(cfg):
                continue
            with open(cfg) as f:
                lines = f.readlines()
            with open(cfg, "w") as f:
                skip_next_blank = False
                for line in lines:
                    if marker in line or comment in line:
                        skip_next_blank = True
                        continue
                    if skip_next_blank and line.strip() == "":
                        skip_next_blank = False
                        continue
                    skip_next_blank = False
                    f.write(line)
        print("\033[33m✗ Auto-launch disabled\033[0m")
        print("\033[2mType 'termnl' to start manually\033[0m")
    else:
        for cfg in shell_configs:
            if not os.path.exists(cfg):
                continue
            with open(cfg) as f:
                content = f.read()
            if marker not in content:
                with open(cfg, "a") as f:
                    f.write(f"\n{comment}\n{launch_line}\n")
        print("\033[32m✓ Auto-launch enabled\033[0m")
        print("\033[2mtermnl will start when you open a new terminal\033[0m")


def _self_update():
    """Check for and apply updates from GitHub."""
    print(f"\n\033[36mChecking for updates...\033[0m")
    print(f"\033[2mCurrent version: v{__version__}\033[0m")

    app_dir = os.path.expanduser("~/.termnl")
    repo_url = "https://github.com/nithinworks/termnl"
    tmp_dir = "/tmp/termnl-update"

    backup_dir = os.path.join(app_dir, "backup")
    os.makedirs(backup_dir, exist_ok=True)

    ts = datetime.now().strftime("%Y%m%d_%H%M%S")
    backup_file = os.path.join(backup_dir, f"termnl_{ts}.py")
    current_file = os.path.join(app_dir, "termnl.py")

    try:
        # Fetch latest version string
        result = subprocess.run(
            ["curl", "-sL", f"{repo_url}/raw/main/termnl.py"],
            capture_output=True, text=True,
        )

        new_version = None
        if result.returncode == 0 and result.stdout:
            for line in result.stdout.split("\n"):
                if line.startswith("__version__"):
                    new_version = line.split("=")[1].strip().strip('"').strip("'")
                    break

        if new_version:
            print(f"\033[2mLatest version: v{new_version}\033[0m")
            if new_version == __version__:
                print("\n\033[32m✓ Already up to date!\033[0m\n")
                return

        # Backup current
        if os.path.exists(current_file):
            shutil.copy2(current_file, backup_file)
            print("\033[2m✓ Backed up current version\033[0m")

        # Download
        print("\033[36mDownloading update...\033[0m")
        subprocess.run(["rm", "-rf", tmp_dir], capture_output=True)
        os.makedirs(tmp_dir, exist_ok=True)

        dl = subprocess.run(
            f"curl -sL {repo_url}/archive/main.tar.gz | tar xz -C {tmp_dir} --strip-components=1",
            shell=True, capture_output=True, text=True,
        )
        if dl.returncode != 0:
            print("\033[31m✗ Download failed — check your internet connection\033[0m")
            return

        for fname in ("termnl.py", "requirements.txt"):
            src = os.path.join(tmp_dir, fname)
            dst = os.path.join(app_dir, fname)
            if os.path.exists(src):
                shutil.copy2(src, dst)

        shutil.rmtree(tmp_dir, ignore_errors=True)
        print("\033[32m✓ Files updated\033[0m")

        # Dependencies
        print("\033[36mUpdating dependencies...\033[0m")
        venv_pip = os.path.join(app_dir, "venv", "bin", "pip")
        req_file = os.path.join(app_dir, "requirements.txt")

        if os.path.exists(req_file):
            dep_result = subprocess.run(
                [venv_pip, "install", "-q", "--upgrade", "-r", req_file],
                capture_output=True, text=True,
            )
            if dep_result.returncode == 0:
                print("\033[32m✓ Dependencies updated\033[0m")
            else:
                print("\033[33m⚠ Some dependencies may not have updated\033[0m")

        # Prune old backups (keep 5)
        backups = sorted(f for f in os.listdir(backup_dir) if f.startswith("termnl_"))
        for stale in backups[:-5]:
            os.remove(os.path.join(backup_dir, stale))

        print("\n\033[32m✓ Update complete!\033[0m")
        if new_version and new_version != __version__:
            print(f"\033[2mUpdated to v{new_version}\033[0m")
        print("\033[2mRestart termnl to use the new version\033[0m\n")

        if input("\033[33mRestart now? [y/N]\033[0m ").strip().lower() == "y":
            print("\033[2mRestarting...\033[0m\n")
            os.execv(sys.executable, [sys.executable] + sys.argv)

    except Exception as e:
        print(f"\n\033[31m✗ Update failed: {e}\033[0m")
        if os.path.exists(backup_file):
            if input("\033[33mRestore from backup? [y/N]\033[0m ").strip().lower() == "y":
                shutil.copy2(backup_file, current_file)
                print("\033[32m✓ Restored from backup\033[0m")


# --- Uninstall ---

def _uninstall():
    confirm = input("\033[33mRemove termnl? [y/N]\033[0m ")
    if confirm.lower() != "y":
        return
    install_dir = os.path.expanduser("~/.termnl")
    bin_path = os.path.expanduser("~/.local/bin/termnl")
    if os.path.exists(install_dir):
        shutil.rmtree(install_dir)
    if os.path.exists(bin_path):
        os.remove(bin_path)
    for rc in ("~/.zshrc", "~/.bashrc", "~/.zprofile", "~/.bash_profile"):
        rc_path = os.path.expanduser(rc)
        if not os.path.exists(rc_path):
            continue
        with open(rc_path) as f:
            lines = f.readlines()
        with open(rc_path, "w") as f:
            for line in lines:
                if "termnl" not in line:
                    f.write(line)
    print("\033[32m✓ termnl uninstalled\033[0m")
    sys.exit(0)


# --- Boot ---

_read_env()
_read_cfg()

_has_key = (
    (provider == "gemini" and os.environ.get("GEMINI_API_KEY"))
    or (provider == "openrouter" and os.environ.get("OPENROUTER_API_KEY"))
)
if not _has_key:
    setup_provider()
    print("\033[1mtermnl\033[0m - talk to your terminal\n")
    _print_help()

_create_client()


# --- REPL: Builtin Handlers ---

def _handle_cd(args: str):
    path = os.path.expanduser(args.strip()) if args.strip() else os.path.expanduser("~")
    try:
        os.chdir(path)
    except Exception as e:
        print(f"cd: {e}")


def _handle_provider():
    if setup_provider(switch_mode=True):
        _create_client()


def _handle_model():
    global openrouter_model
    if provider == "openrouter":
        print(f"\033[2mCurrent model: {openrouter_model}\033[0m")
        new_model = input("\033[33mEnter new model:\033[0m ").strip()
        if new_model:
            openrouter_model = new_model
            _write_env()
            print(f"\033[32m✓ Model set to {openrouter_model}\033[0m")
    else:
        print("\033[2mModel selection is only available with OpenRouter\033[0m")
        print("\033[2mSwitch with !provider first\033[0m")


def _handle_learn():
    global learning_mode
    learning_mode = not learning_mode
    _write_cfg()
    status = "enabled" if learning_mode else "disabled"
    print(f"\033[36m💡 Learning mode {status}\033[0m")


def _handle_force_run(cmd: str):
    stdout, stderr, rc = _run(cmd)
    if stdout:
        print(stdout, end="")
    if stderr:
        print(stderr, end="")
    _record(cmd, stdout + stderr, rc)


# --- REPL: Execution Handlers ---

def _exec_single(command: str, explanation: str | None = None):
    """Handle a single translated command — confirm and run."""
    confirm = input(f"\033[33m→ {command}\033[0m [Enter] ")
    if confirm != "":
        return
    if command.startswith("cd "):
        _handle_cd(command[3:])
    else:
        stdout, stderr, rc = _run(command)
        if stdout:
            print(stdout, end="")
        if stderr:
            print(stderr, end="")
        _record(command, stdout + stderr, rc)

        if learning_mode and explanation:
            print(f"\n\033[2m{explanation}\033[0m\n")


def _exec_multi(commands: list[str], explanation: str | None = None):
    """Handle a multi-step workflow — confirm strategy and run."""
    print(f"\033[33mMulti-step workflow ({len(commands)} commands):\033[0m")
    for i, cmd in enumerate(commands, 1):
        print(f"  {i}. {cmd}")

    confirm = input(f"\n\033[33mRun all?\033[0m [y/n/step] ").strip().lower()

    if confirm in ("y", "yes", ""):
        _run_sequence(commands)
        if learning_mode and explanation:
            print(f"\n\033[2m{explanation}\033[0m\n")

    elif confirm == "step":
        _run_stepping(commands)

    else:
        print("\033[2mCancelled\033[0m")


def _run_sequence(commands: list[str]):
    """Run all commands sequentially, stopping on failure."""
    for i, cmd in enumerate(commands, 1):
        print(f"\033[2m[{i}/{len(commands)}]\033[0m {cmd}")
        if cmd.startswith("cd "):
            try:
                os.chdir(os.path.expanduser(cmd[3:].strip()))
                print("\033[32m✓\033[0m")
            except Exception as e:
                print(f"\033[31m✗ cd: {e}\033[0m")
                break
        else:
            stdout, stderr, rc = _run(cmd)
            if stdout:
                print(stdout, end="")
            if stderr:
                print(f"\033[31m{stderr}\033[0m", end="")
            _record(cmd, stdout + stderr, rc)
            print("\033[32m✓\033[0m" if rc == 0 else "\033[31m✗\033[0m")
            if rc != 0:
                break


def _run_stepping(commands: list[str]):
    """Run commands one at a time, asking before each."""
    for i, cmd in enumerate(commands, 1):
        choice = input(f"\033[33m[{i}/{len(commands)}] {cmd}\033[0m [y/n/q] ").strip().lower()
        if choice in ("y", "yes", ""):
            if cmd.startswith("cd "):
                try:
                    os.chdir(os.path.expanduser(cmd[3:].strip()))
                    print("\033[32m✓\033[0m")
                except Exception as e:
                    print(f"\033[31m✗ cd: {e}\033[0m")
            else:
                stdout, stderr, _ = _run(cmd)
                if stdout:
                    print(stdout, end="")
                if stderr:
                    print(f"\033[31m{stderr}\033[0m", end="")
                _record(cmd, stdout + stderr)
        elif choice == "q":
            print("\033[2mStopped\033[0m")
            break


# --- Main REPL ---

# Dispatch table for builtin commands
_BUILTINS = {
    "!provider": lambda: _handle_provider(),
    "!model":    lambda: _handle_model(),
    "!learn":    lambda: _handle_learn(),
    "!autolaunch": lambda: _toggle_autolaunch(),
    "!update":   lambda: _self_update(),
    "!uninstall": lambda: _uninstall(),
    "!help":     lambda: _print_help(),
}


def main():
    global _interrupted

    while True:
        # Check interrupt flag from signal handler
        if _interrupted:
            _interrupted = False
            continue

        try:
            cwd = os.getcwd()
            # Wrap ANSI escapes in \001..\002 so readline knows their display width is 0.
            # Without this, up-arrow history recall corrupts the prompt display.
            prompt_prefix = f"\001\033[32m\002{os.path.basename(cwd)}\001\033[0m\002"

            if learning_mode:
                prompt_prefix += " \001\033[2m\002[learn]\001\033[0m\002"
            if provider == "openrouter" and openrouter_model != "google/gemini-2.5-flash":
                short_model = openrouter_model.rsplit("/", 1)[-1]
                prompt_prefix += f" \001\033[2m\002[{short_model}]\001\033[0m\002"

            prompt_prefix += " > "
            user_input = input(prompt_prefix).strip()

            if not user_input:
                continue

            # --- Exit ---
            if user_input in ("exit", "quit"):
                print("\033[2mbye 👋\033[0m")
                break

            # --- CD (special: changes process state) ---
            if user_input == "cd" or user_input.startswith("cd "):
                _handle_cd(user_input[3:])
                continue

            # --- Builtins (dispatch table) ---
            if user_input in _BUILTINS:
                _BUILTINS[user_input]()
                continue

            # --- Force-run with ! prefix ---
            if user_input.startswith("!"):
                cmd = user_input[1:]
                if cmd:
                    _handle_force_run(cmd)
                continue

            # --- Classify input (only reached for non-builtins) ---
            kind = _classify_input(user_input)

            # --- Shell passthrough ---
            if kind == "shell":
                stdout, stderr, rc = _run(user_input)
                if stdout:
                    print(stdout, end="")
                if stderr:
                    print(stderr, end="")
                _record(user_input, stdout + stderr, rc)
                continue

            # --- Natural language → AI translation ---
            result = _translate(user_input, cwd)
            commands = result["commands"]
            explanation = result.get("explanation")

            if not commands:
                print("\033[31mcouldn't translate that - try rephrasing or use !<cmd>\033[0m")
                continue

            if len(commands) == 1:
                _exec_single(commands[0], explanation)
            else:
                _exec_multi(commands, explanation)

        except EOFError:
            print("\n\033[2mbye 👋\033[0m")
            break
        except KeyboardInterrupt:
            _interrupted = False
            continue
        except Exception as e:
            err = str(e)
            if "429" in err or "quota" in err.lower():
                print("\033[31mrate limit hit - wait a moment and try again\033[0m")
            elif "Interrupt" not in err:
                print(f"\033[31merror: {err[:100]}\033[0m")


if __name__ == "__main__":
    main()
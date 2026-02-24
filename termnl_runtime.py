import shutil
import subprocess
from collections import deque, namedtuple
from datetime import datetime
from typing import Callable

HistoryEntry = namedtuple("HistoryEntry", ["cmd", "output", "exit_code", "ts"])

SESSION_CAPACITY = 12
TOKEN_BUDGET = 5000  # rough char budget for context window


class SessionLog:
    def __init__(self, capacity: int = SESSION_CAPACITY, token_budget: int = TOKEN_BUDGET):
        self._entries: deque[HistoryEntry] = deque(maxlen=capacity)
        self._token_budget = token_budget

    def record(self, cmd: str, output: str = "", exit_code: int = 0) -> None:
        """Append a command+output to the session log, evicting oldest if over budget."""
        self._entries.append(
            HistoryEntry(
                cmd=cmd,
                output=output[:600] if output else "",
                exit_code=exit_code,
                ts=datetime.now(),
            )
        )

        while len(self._entries) > 1 and sum(len(e.cmd) + len(e.output) for e in self._entries) > self._token_budget:
            self._entries.popleft()

    def render_context(self) -> str:
        """Render recent session history as context for the AI prompt."""
        if not self._entries:
            return "(no previous commands)"

        parts: list[str] = []
        for entry in list(self._entries)[-6:]:
            status = "✓" if entry.exit_code == 0 else "✗"
            parts.append(f"[{status}] $ {entry.cmd}")
            if entry.output:
                for line in entry.output.strip().splitlines()[:3]:
                    parts.append(f"    {line}")
        return "\n".join(parts)


def classify_input(text: str) -> str:
    """
    Classify user input as 'builtin', 'shell', or 'natural'.

    Uses a scoring heuristic + dynamic PATH lookup instead of
    hardcoded command lists. Returns one of three categories.
    """
    stripped = text.strip()
    if not stripped:
        return "builtin"

    if stripped.startswith("!"):
        return "builtin"
    if stripped in ("exit", "quit"):
        return "builtin"

    score = 0.0

    first_token = stripped.split()[0] if stripped.split() else ""

    effective_token = first_token
    if "=" in first_token and not first_token.startswith("="):
        parts = stripped.split()
        for p in parts:
            if "=" not in p or p.startswith("="):
                effective_token = p
                break

    if effective_token.startswith(("./", "/", "~")):
        score += 3.0

    if effective_token.startswith("$"):
        score += 2.5

    if shutil.which(effective_token):
        score += 2.0

    shell_operators = ("|", "&&", "||", ">>", ">;", ";", "$(", "`")
    if any(op in stripped for op in shell_operators):
        score += 2.5

    if ">" in stripped and ">>" not in stripped and "→" not in stripped:
        score += 2.0

    nl_words = {
        "how",
        "what",
        "why",
        "where",
        "when",
        "who",
        "which",
        "can",
        "could",
        "would",
        "should",
        "please",
        "help",
        "tell",
        "give",
        "is",
        "are",
        "do",
        "does",
        "the",
        "my",
        "me",
        "all",
        "about",
        "need",
        "want",
    }

    tokens_lower = set(stripped.lower().split())
    nl_overlap = len(tokens_lower & nl_words)

    if nl_overlap >= 2:
        score -= 2.0
    elif nl_overlap == 1 and len(tokens_lower) > 2:
        score -= 0.5

    word_count = len(stripped.split())
    if word_count >= 4 and score < 2.0:
        score -= 1.5

    if stripped[0].isupper() and word_count > 1:
        score -= 1.0

    if "?" in stripped:
        score -= 3.0

    if word_count <= 3 and nl_overlap == 0 and stripped.islower():
        score += 1.0

    if stripped == "cd" or stripped.startswith("cd "):
        return "shell"

    return "shell" if score >= 1.0 else "natural"


def translate(
    user_input: str,
    cwd: str,
    os_shell: str,
    learning_mode: bool,
    session_context: str,
    ask_ai_fn: Callable[[str], str | None],
) -> dict:
    """
    Translate natural language input to shell commands via AI.
    Returns dict with 'commands' list and optional 'explanation'.
    """
    prompt = f"""Convert the following request into executable {os_shell} commands.
Working directory: {cwd}

Session context:
{session_context}

Guidelines:
- Return ONLY raw commands, one per line — no markdown, no backticks, no commentary
- For multi-step tasks, put each command on its own line
- Leverage session context for references like "do that again" or "undo that"
- When ambiguous, choose the simplest standard approach

Request: {user_input}"""

    raw = ask_ai_fn(prompt)
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
            tip = ask_ai_fn(tip_prompt)
            if tip:
                result["explanation"] = tip
        except Exception:
            pass

    return result


_PTY_COMMANDS = frozenset(
    {
        "clear",
        "top",
        "htop",
        "vim",
        "vi",
        "nano",
        "less",
        "more",
        "man",
        "ssh",
        "tmux",
        "screen",
    }
)


def needs_pty(cmd: str) -> bool:
    """Check if command needs direct terminal (PTY) access."""
    base = cmd.split()[0] if cmd.split() else ""
    return base in _PTY_COMMANDS


def run(cmd: str) -> tuple[str, str, int]:
    """Execute a shell command and return (stdout, stderr, returncode)."""
    if needs_pty(cmd):
        rc = subprocess.run(cmd, shell=True).returncode
        return "", "", rc

    proc = subprocess.run(cmd, shell=True, capture_output=True, text=True)
    return proc.stdout, proc.stderr, proc.returncode
